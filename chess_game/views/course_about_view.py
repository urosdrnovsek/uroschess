"""Credits shown on a player course's Sources screen."""


def _fit_text(font, text, width):
    if font.size(text)[0] <= width:
        return text
    text = text.rstrip("…")
    while text and font.size(text + "…")[0] > width:
        text = text[:-1]
    return text.rstrip() + "…"


def draw_course_about(surface, card, course, player, game, small_font,
                      tag_font, palette):
    white = game.headers.get("White", "White").split(",")[0]
    black = game.headers.get("Black", "Black").split(",")[0]
    compact = card.w < 400
    labels = (
        ("Practice boards by Uroschess" if compact else
         "Practice boards; advice by Uroschess.", 68),
        (course.association_source.name.split(":")[0], 137),
        ("{} vs {}".format(white, black), 193),
        ("Generated portrait · Uroschess" if compact
         else player.portrait_attribution, 253),
    )
    font = tag_font if compact else small_font
    for label, offset in labels:
        line = _fit_text(font, label, card.w - 44)
        surface.blit(font.render(line, True, palette.text),
                     (card.x + 22, card.y + offset))
