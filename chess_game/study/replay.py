"""Navigation controller for immutable recorded games."""

from .chess_adapter import ChessAdapter, MoveResolutionError


class ReplayNavigationError(ValueError):
    """A requested path does not exist in the recorded game tree."""


class ReplayController:
    """Navigate a GameRecord without mutating its source move tree."""

    def __init__(self, game, adapter=None):
        self.game = game
        self.adapter = adapter or ChessAdapter()
        self._path = ()
        self._board = None
        self._node = None
        self._sans = ()
        self._resolved_moves = ()
        self._rebuild()

    @property
    def path(self):
        return self._path

    @property
    def ply(self):
        return len(self._path)

    @property
    def board(self):
        return self._board.clone()

    @property
    def current_node(self):
        return self._node

    @property
    def sans(self):
        return self._sans

    @property
    def current_move(self):
        return self._resolved_moves[-1] if self._resolved_moves else None

    @property
    def current_comment(self):
        if self._node is self.game.root:
            return self.game.root.comment
        return self._node.comment

    @property
    def variation_count(self):
        return len(self._node.children)

    def variations(self):
        variations = []
        for child in self._node.children:
            board = self._board.clone()
            _, san = self.adapter.apply_uci(board, child.uci)
            variations.append(san)
        return tuple(variations)

    @property
    def can_go_back(self):
        return bool(self._path)

    @property
    def can_go_forward(self):
        return bool(self._node.children)

    def uci_path(self):
        node = self.game.root
        moves = []
        for child_index in self._path:
            node = node.children[child_index]
            moves.append(node.uci)
        return tuple(moves)

    def go_first(self):
        return self.jump(())

    def go_last(self):
        path = list(self._path)
        node = self._node
        while node.children:
            path.append(0)
            node = node.children[0]
        return self.jump(tuple(path))

    def previous(self):
        if not self._path:
            return False
        self.jump(self._path[:-1])
        return True

    def next(self, variation_index=0):
        if not 0 <= variation_index < len(self._node.children):
            if not self._node.children and variation_index == 0:
                return False
            raise ReplayNavigationError(
                "variation index {} is unavailable at ply {}".format(
                    variation_index, self.ply))
        self.jump(self._path + (variation_index,))
        return True

    def jump(self, path):
        path = tuple(path)
        old_path = self._path
        self._path = path
        try:
            self._rebuild()
        except (IndexError, MoveResolutionError) as error:
            self._path = old_path
            self._rebuild()
            raise ReplayNavigationError(
                "invalid replay path {!r}".format(path)) from error
        return True

    def mainline_length(self):
        count = 0
        node = self.game.root
        while node.children:
            node = node.children[0]
            count += 1
        return count

    def mainline_sans(self):
        board = (self.adapter.from_fen(self.game.starting_fen)
                 if self.game.starting_fen else self.adapter.initial_board())
        node = self.game.root
        sans = []
        while node.children:
            node = node.children[0]
            _, san = self.adapter.apply_uci(board, node.uci)
            sans.append(san)
        return tuple(sans)

    def jump_mainline(self, ply):
        if ply < 0:
            raise ReplayNavigationError("ply cannot be negative")
        node = self.game.root
        path = []
        for _ in range(ply):
            if not node.children:
                raise ReplayNavigationError(
                    "main line ends before ply {}".format(ply))
            path.append(0)
            node = node.children[0]
        return self.jump(tuple(path))

    def _rebuild(self):
        board = (self.adapter.from_fen(self.game.starting_fen)
                 if self.game.starting_fen else self.adapter.initial_board())
        node = self.game.root
        sans = []
        resolved_moves = []
        for child_index in self._path:
            if (not isinstance(child_index, int) or child_index < 0
                    or child_index >= len(node.children)):
                raise IndexError(child_index)
            node = node.children[child_index]
            move, san = self.adapter.apply_uci(board, node.uci)
            resolved_moves.append(move)
            sans.append(san)
        self._board = board
        self._node = node
        self._sans = tuple(sans)
        self._resolved_moves = tuple(resolved_moves)
