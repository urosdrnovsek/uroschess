"""Short, original introductions for the character gallery."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CharacterStory:
    favourite_piece: str
    story: str


STORIES = {
    "chicky": CharacterStory(
        "Pawn",
        "Chicky called a pawn his tiny bodyguard. He moved it one square, "
        "cheered, then asked if it could carry him home. It could not, so he "
        "gave it a gold star."),
    "pippa-pomeranian": CharacterStory(
        "Horse (knight)",
        "Pippa offered her horse a carrot before the game. It jumped over a "
        "pawn instead. She clapped so loudly that she startled herself."),
    "tina-turtle": CharacterStory(
        "Pawn",
        "Tina carried a pawn to the board on her shell. 'Such a long trip,' "
        "she sighed. The board was two steps away. She still needed a rest."),
    "tom-rabbit": CharacterStory(
        "Rook",
        "Tom called his rooks to a team meeting. 'Find a clear path!' he "
        "squeaked. When they could not move past the pawns, he moved a pawn "
        "and called another meeting."),
    "bruno-bear": CharacterStory(
        "Queen",
        "Bruno promised his queen a grand entrance. Then he saw his king "
        "needed help first. 'A good captain waits for the team,' he said. "
        "The queen nodded wisely."),
    "olive-owl": CharacterStory(
        "Bishop",
        "Olivia watched everyone rush to move. She saw a path for her bishop "
        "after one pawn stepped aside. 'There it is,' she said, as if the "
        "board had whispered a secret."),
    "monty-cat": CharacterStory(
        "King",
        "Monty made a paper crown for his king and announced a royal parade. "
        "The king moved one square. Monty bowed as if a crowd had cheered. "
        "He still calls it his finest parade."),
}
