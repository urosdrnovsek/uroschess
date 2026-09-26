"""Strict annotated-PGN import for bundled teaching content."""

from dataclasses import dataclass, field
import re

from .chess_adapter import ChessAdapter, MoveResolutionError
from .models import GameRecord, MoveNode, SourceInfo


_RESULTS = {"1-0", "0-1", "1/2-1/2", "*"}
_SYMBOLIC_NAGS = {"!": 1, "?": 2, "!!": 3, "??": 4, "!?": 5, "?!": 6}
_HEADER_RE = re.compile(
    r'^\[\s*([A-Za-z][A-Za-z0-9_]*)\s+"((?:\\.|[^"\\])*)"\s*\]$')
_MOVE_PREFIX_RE = re.compile(r"^(\d+)\.(\.\.)?(.*)$")


class PgnParseError(ValueError):
    """An annotated game could not be imported without losing meaning."""

    def __init__(self, message, source="<string>", line=None, column=None):
        self.source = source
        self.line = line
        self.column = column
        location = source
        if line is not None:
            location += ":" + str(line)
            if column is not None:
                location += ":" + str(column)
        super().__init__(location + ": " + message)


@dataclass(frozen=True)
class _Token:
    kind: str
    value: object
    line: int
    column: int


@dataclass
class _MutableNode:
    uci: str = None
    parent: "_MutableNode" = None
    comments: list = field(default_factory=list)
    starting_comments: list = field(default_factory=list)
    nags: list = field(default_factory=list)
    children: list = field(default_factory=list)


def _unescape_header(value):
    output = []
    index = 0
    while index < len(value):
        if value[index] == "\\" and index + 1 < len(value):
            output.append(value[index + 1])
            index += 2
        else:
            output.append(value[index])
            index += 1
    return "".join(output)


def _comment_text(value):
    return " ".join(value.split())


def _classify_atom(atom, line, column, tokens):
    if not atom:
        return
    if atom in _RESULTS:
        tokens.append(_Token("RESULT", atom, line, column))
        return
    if atom in _SYMBOLIC_NAGS:
        tokens.append(_Token("NAG", _SYMBOLIC_NAGS[atom], line, column))
        return
    if atom in ("...", "e.p.", "ep"):
        tokens.append(_Token("MOVE_NUMBER" if atom == "..." else "EP", atom,
                             line, column))
        return

    prefix = _MOVE_PREFIX_RE.match(atom)
    if prefix:
        marker_length = len(prefix.group(1)) + 1 + len(prefix.group(2) or "")
        tokens.append(_Token("MOVE_NUMBER", atom[:marker_length], line, column))
        tail = prefix.group(3)
        if tail:
            _classify_atom(tail, line, column + marker_length, tokens)
        return

    annotation = None
    for suffix in ("!!", "??", "!?", "?!", "!", "?"):
        if atom.endswith(suffix) and len(atom) > len(suffix):
            atom = atom[:-len(suffix)]
            annotation = _SYMBOLIC_NAGS[suffix]
            break
    tokens.append(_Token("SAN", atom, line, column))
    if annotation is not None:
        tokens.append(_Token("NAG", annotation, line,
                             column + len(atom)))


def _lex(text, source):
    tokens = []
    index = 0
    line = 1
    column = 1
    line_has_content = False

    def advance(character):
        nonlocal line, column, line_has_content
        if character == "\n":
            line += 1
            column = 1
            line_has_content = False
        else:
            column += 1
            if not character.isspace():
                line_has_content = True

    while index < len(text):
        character = text[index]
        if character.isspace():
            advance(character)
            index += 1
            continue
        if character == "%" and not line_has_content:
            while index < len(text) and text[index] != "\n":
                advance(text[index])
                index += 1
            continue

        token_line, token_column = line, column
        if character == "[":
            end = text.find("\n", index)
            if end < 0:
                end = len(text)
            raw = text[index:end].strip()
            match = _HEADER_RE.match(raw)
            if not match:
                raise PgnParseError("invalid PGN header", source,
                                    token_line, token_column)
            tokens.append(_Token(
                "HEADER", (match.group(1), _unescape_header(match.group(2))),
                token_line, token_column))
            while index < end:
                advance(text[index])
                index += 1
            continue

        if character == "{":
            advance(character)
            index += 1
            start = index
            while index < len(text) and text[index] != "}":
                advance(text[index])
                index += 1
            if index >= len(text):
                raise PgnParseError("unterminated brace comment", source,
                                    token_line, token_column)
            value = _comment_text(text[start:index])
            advance(text[index])
            index += 1
            tokens.append(_Token("COMMENT", value, token_line, token_column))
            continue

        if character == ";":
            advance(character)
            index += 1
            start = index
            while index < len(text) and text[index] != "\n":
                advance(text[index])
                index += 1
            tokens.append(_Token(
                "COMMENT", _comment_text(text[start:index]),
                token_line, token_column))
            continue

        if character in "()":
            tokens.append(_Token("LPAREN" if character == "(" else "RPAREN",
                                 character, token_line, token_column))
            advance(character)
            index += 1
            continue

        if character == "$":
            advance(character)
            index += 1
            start = index
            while index < len(text) and text[index].isdigit():
                advance(text[index])
                index += 1
            if start == index:
                raise PgnParseError("numeric annotation requires digits", source,
                                    token_line, token_column)
            tokens.append(_Token("NAG", int(text[start:index]),
                                 token_line, token_column))
            continue

        if character in "]}":
            raise PgnParseError("unexpected {!r}".format(character), source,
                                token_line, token_column)

        start = index
        while (index < len(text) and not text[index].isspace()
               and text[index] not in "{}();$[]"):
            advance(text[index])
            index += 1
        _classify_atom(text[start:index], token_line, token_column, tokens)

    return tokens


def _freeze(node):
    return MoveNode(
        uci=node.uci,
        comment="\n\n".join(part for part in node.comments if part),
        starting_comment="\n\n".join(
            part for part in node.starting_comments if part),
        nags=tuple(node.nags),
        children=tuple(_freeze(child) for child in node.children),
    )


def _slug(value):
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "game"


def _validate_fen(fen):
    fields = fen.split()
    if len(fields) != 6:
        raise ValueError("FEN must contain six fields")
    placement, side, rights, ep, halfmove, fullmove = fields
    ranks = placement.split("/")
    if len(ranks) != 8:
        raise ValueError("FEN placement must contain eight ranks")
    pieces = "prnbqkPRNBQK"
    for rank in ranks:
        squares = 0
        for character in rank:
            if character in "12345678":
                squares += int(character)
            elif character in pieces:
                squares += 1
            else:
                raise ValueError("FEN contains an invalid piece")
        if squares != 8:
            raise ValueError("each FEN rank must contain eight squares")
    if placement.count("K") != 1 or placement.count("k") != 1:
        raise ValueError("FEN must contain one king for each side")
    if side not in ("w", "b"):
        raise ValueError("FEN side to move must be w or b")
    if rights != "-" and (any(value not in "KQkq" for value in rights)
                           or len(set(rights)) != len(rights)):
        raise ValueError("FEN castling rights are invalid")
    if ep != "-" and not re.match(r"^[a-h][36]$", ep):
        raise ValueError("FEN en-passant square is invalid")
    try:
        halfmove_value = int(halfmove)
        fullmove_value = int(fullmove)
    except ValueError as error:
        raise ValueError("FEN move counters must be integers") from error
    if halfmove_value < 0 or fullmove_value < 1:
        raise ValueError("FEN move counters are out of range")


class _Parser:
    def __init__(self, tokens, source, source_info):
        self.tokens = tokens
        self.source = source
        self.source_info = source_info
        self.index = 0

    def _peek(self):
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def _error(self, message, token=None):
        token = token or self._peek()
        if token is None:
            return PgnParseError(message, self.source)
        return PgnParseError(message, self.source, token.line, token.column)

    def parse_games(self):
        games = []
        while self._peek() is not None:
            headers = {}
            while self._peek() is not None and self._peek().kind == "HEADER":
                token = self._peek()
                name, value = token.value
                if name in headers:
                    raise self._error("duplicate header " + name, token)
                headers[name] = value
                self.index += 1

            root = _MutableNode()
            starting_fen = headers.get("FEN")
            if headers.get("SetUp") == "1" and not starting_fen:
                raise self._error('SetUp "1" requires a FEN header')
            try:
                if starting_fen:
                    _validate_fen(starting_fen)
                    board = ChessAdapter.from_fen(starting_fen)
                else:
                    board = ChessAdapter.initial_board()
            except (ValueError, IndexError, KeyError) as error:
                raise self._error("invalid starting FEN: " + str(error)) from error

            result = self._parse_line(root, board, in_variation=False)
            if not headers and not root.children:
                token = self._peek()
                if token is not None and token.kind == "HEADER":
                    continue
                raise self._error("expected a PGN game")

            header_result = headers.get("Result", "*")
            if header_result not in _RESULTS:
                raise self._error("unsupported Result header: " + header_result)
            if result is None:
                result = header_result
            elif header_result != "*" and header_result != result:
                raise self._error(
                    "movetext result {} disagrees with Result header {}".format(
                        result, header_result))

            identity = headers.get("GameId") or headers.get("Id")
            if not identity:
                identity = "-".join(filter(None, (
                    headers.get("White", ""), headers.get("Black", ""),
                    headers.get("Date", ""))))
            game_id = "{}-{}".format(_slug(identity), len(games) + 1)
            games.append(GameRecord(
                game_id=game_id,
                root=_freeze(root),
                headers=headers,
                starting_fen=starting_fen,
                result=result,
                source=self.source_info,
            ))
        return tuple(games)

    def _parse_line(self, parent, board, in_variation):
        current = parent
        position_before_current = None
        pending_starting_comments = []
        moves_seen = 0

        while True:
            token = self._peek()
            if token is None:
                if in_variation:
                    raise self._error("unterminated variation")
                return None
            if token.kind == "HEADER":
                if in_variation:
                    raise self._error("header encountered inside a variation", token)
                return None
            if token.kind == "RESULT":
                if in_variation:
                    raise self._error("result marker inside a variation", token)
                self.index += 1
                while (self._peek() is not None
                       and self._peek().kind == "COMMENT"):
                    current.comments.append(self._peek().value)
                    self.index += 1
                return token.value
            if token.kind == "RPAREN":
                if not in_variation:
                    raise self._error("unexpected closing parenthesis", token)
                if moves_seen == 0:
                    raise self._error("empty variation", token)
                self.index += 1
                return None
            if token.kind in ("MOVE_NUMBER", "EP"):
                self.index += 1
                continue
            if token.kind == "COMMENT":
                self.index += 1
                if moves_seen == 0:
                    if in_variation:
                        pending_starting_comments.append(token.value)
                    else:
                        parent.comments.append(token.value)
                else:
                    current.comments.append(token.value)
                continue
            if token.kind == "NAG":
                if moves_seen == 0:
                    raise self._error("annotation appears before a move", token)
                if token.value not in current.nags:
                    current.nags.append(token.value)
                self.index += 1
                continue
            if token.kind == "LPAREN":
                if moves_seen == 0 or current.parent is None:
                    raise self._error("variation has no preceding move", token)
                self.index += 1
                self._parse_line(current.parent, position_before_current.clone(),
                                 in_variation=True)
                continue
            if token.kind != "SAN":
                raise self._error("unsupported PGN token", token)

            try:
                move = ChessAdapter.resolve_san(board, token.value)
            except MoveResolutionError as error:
                raise self._error(str(error), token) from error
            position_before_current = board.clone()
            node = _MutableNode(uci=str(move), parent=current)
            node.starting_comments.extend(pending_starting_comments)
            pending_starting_comments = []
            current.children.append(node)
            current = node
            board.make_move(move)
            moves_seen += 1
            self.index += 1


def parse_pgn_games(text, source="<string>", source_info=None):
    """Parse one or more annotated standard-chess games.

    The returned game trees preserve headers, comments, variations, numeric
    annotations, custom starting positions, and the recorded result.
    """
    if source_info is None:
        source_info = SourceInfo(name=source)
    return _Parser(_lex(text, source), source, source_info).parse_games()


def load_pgn_file(path, source_info=None):
    """Read UTF-8 PGN from ``path`` and return parsed games."""
    try:
        with open(path, encoding="utf-8-sig") as handle:
            text = handle.read()
    except OSError as error:
        raise PgnParseError(str(error), str(path)) from error
    return parse_pgn_games(text, source=str(path), source_info=source_info)
