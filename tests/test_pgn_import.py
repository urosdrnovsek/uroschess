"""Annotated PGN import checks."""

from chess_game.study import PgnParseError, parse_pgn_games


ANNOTATED_PGN = r'''
[Event "Rosenwald \"Training\" Trophy"]
[Site "New York, USA"]
[Date "1956.10.17"]
[Round "8"]
[White "White, Donald"]
[Black "Black, Robert James"]
[Result "1-0"]

{Introductory note.}
1. e4! {Controls the centre.} e5
(1... c5 {The Sicilian Defence.} 2. Nf3 (2. Nc3))
2. Nf3 $1 Nc6 1-0

[Event "Endgame sample"]
[SetUp "1"]
[FEN "8/8/8/4k3/8/8/8/4K2R b K - 0 1"]
[Result "*"]

1... Kf4 2. Kf2 *
'''


def test_multiple_games_headers_comments_variations_and_nags():
    games = parse_pgn_games(ANNOTATED_PGN, source="annotated.pgn")
    assert len(games) == 2

    game = games[0]
    assert game.headers["Event"] == 'Rosenwald "Training" Trophy'
    assert game.headers["White"] == "White, Donald"
    assert game.result == "1-0"
    assert game.root.comment == "Introductory note."

    e4 = game.root.children[0]
    assert e4.uci == "e2e4"
    assert e4.nags == (1,)
    assert e4.comment == "Controls the centre."
    assert [child.uci for child in e4.children] == ["e7e5", "c7c5"]

    c5 = e4.children[1]
    assert c5.comment == "The Sicilian Defence."
    assert [child.uci for child in c5.children] == ["g1f3", "b1c3"]
    assert e4.children[0].children[0].nags == (1,)

    custom = games[1]
    assert custom.starting_fen.startswith("8/8/8/4k3")
    assert custom.root.children[0].uci == "e5f4"
    assert custom.root.children[0].children[0].uci == "e1f2"


def test_recorded_result_is_kept_when_position_is_not_terminal():
    game = parse_pgn_games("[Result \"1-0\"]\n\n1. e4 e5 1-0")[0]
    assert game.result == "1-0"


def test_comment_after_result_stays_with_game():
    games = parse_pgn_games(
        "1. e4 e5 1-0 {The recorded result is not implied by the board.}\n"
        "1. d4 d5 1/2-1/2")
    assert len(games) == 2
    first_last_move = games[0].root.children[0].children[0]
    assert first_last_move.comment == "The recorded result is not implied by the board."
    assert games[1].result == "1/2-1/2"


def test_invalid_move_has_source_and_location():
    try:
        parse_pgn_games("1. e4 e5 2. Qh9 *", source="broken.pgn")
    except PgnParseError as error:
        message = str(error)
        assert "broken.pgn:1:" in message
        assert "Qh9" in message
    else:
        raise AssertionError("invalid SAN must fail rather than be skipped")


def test_unclosed_variation_is_rejected():
    try:
        parse_pgn_games("1. e4 (1. d4 d5 *", source="broken.pgn")
    except PgnParseError as error:
        assert "result marker inside a variation" in str(error)
    else:
        raise AssertionError("unterminated variation must fail")


def test_comment_without_a_game_is_rejected():
    try:
        parse_pgn_games("{This is not a game.}", source="empty.pgn")
    except PgnParseError as error:
        assert "expected a PGN game" in str(error)
        assert "empty.pgn" in str(error)
    else:
        raise AssertionError("comment-only input must fail")


def test_invalid_fen_is_rejected_before_move_parsing():
    broken = '[SetUp "1"]\n[FEN "8/8/8/8/8/8/8 w - - 0 1"]\n\n*'
    try:
        parse_pgn_games(broken, source="bad-fen.pgn")
    except PgnParseError as error:
        assert "eight ranks" in str(error)
        assert "bad-fen.pgn" in str(error)
    else:
        raise AssertionError("malformed FEN must fail")


def main():
    for name, function in sorted(globals().items()):
        if name.startswith("test_") and callable(function):
            function()
            print("ok ", name)
    print("\nall annotated PGN tests passed")


if __name__ == "__main__":
    main()
