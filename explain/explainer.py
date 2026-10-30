"""Explain moves using supplied Stockfish results."""

LABELS = {
    "best": "Best",
    "excellent": "Excellent",
    "good": "Good",
    "inaccuracy": "Inaccuracy",
    "mistake": "Mistake",
    "blunder": "Blunder",
    "brilliant": "Brilliant",
}


def explain_move(move: dict) -> str:
    """Describe supplied analysis without inventing chess facts."""
    san = move["move_san"]
    label = LABELS.get(move["label"], move["label"])
    best = move.get("best_move_san")

    text = f"The move {san} is classified as {label}."

    if best == san:
        return text + " It matches Stockfish's recommendation."
    if best:
        return text + f" Stockfish recommends {best}."
    return text + " No best-move recommendation was provided."


if __name__ == "__main__":
    example = {
        "move_san": "Nf3",
        "label": "mistake",
        "best_move_san": "Nc3",
    }
    print(explain_move(example))
