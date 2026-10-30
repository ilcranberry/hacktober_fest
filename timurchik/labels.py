"""Перевод оценок в вероятность победы и классификация ходов."""

import math


# Начальные пороги для MVP. Позже проверим их на реальных партиях.
# Потеря вероятности: 0.03 означает 3 процентных пункта.
THRESHOLDS = (
    (0.01, "excellent"),
    (0.03, "good"),
    (0.08, "inaccuracy"),
    (0.20, "mistake"),
)


def win_probability(eval_cp: float) -> float:
    """Приблизительная вероятность победы белых из оценки в сантипешках."""
    # Ограничение защищает math.exp от переполнения.
    bounded_cp = max(-10000, min(10000, eval_cp))
    return 1 / (1 + math.exp(-0.00368208 * bounded_cp))


def classify_move(
    probability_before: float,
    probability_after: float,
    mover_is_white: bool,
    is_best_move: bool = False,
) -> str:
    """Определить метку по потере вероятности ходившего игрока."""
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