"""Convert evaluations to win probabilities and classify moves."""

import math


# Initial MVP thresholds, to be calibrated on real games.
# A probability loss of 0.03 means three percentage points.
THRESHOLDS = (
    (0.01, "excellent"),
    (0.03, "good"),
    (0.08, "inaccuracy"),
    (0.20, "mistake"),
)


def win_probability(eval_cp: float) -> float:
    """Estimate White's win probability from an evaluation in centipawns."""
    # Clamp the score to prevent overflow in math.exp.
    bounded_cp = max(-10000, min(10000, eval_cp))
    return 1 / (1 + math.exp(-0.00368208 * bounded_cp))


def classify_move(
    probability_before: float,
    probability_after: float,
    mover_is_white: bool,
    is_best_move: bool = False,
) -> str:
    """Classify a move by the mover's loss in win probability."""
    if is_best_move:
        return "best"

    if mover_is_white:
        loss = probability_before - probability_after
    else:
        loss = probability_after - probability_before

    loss = max(0.0, loss)

    for threshold, label in THRESHOLDS:
        if loss <= threshold:
            return label

    return "blunder"
