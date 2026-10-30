"""Проверка анализа партии."""

from timurchik.analyzer import analyze


PGN = """
[Event "Test"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 d6 4. O-O Bg4
5. d4 Bxf3 6. Qxf3 exd4 7. Qxf7# 1-0
"""


def show_progress(done: int, total: int):
    print(f"Анализ: {done}/{total}")


def main():
    results = analyze(PGN, progress_callback=show_progress)

    for item in results:
        if item["mate_after"] is not None:
            evaluation = f"мат: {item['mate_after']}"
        else:
            evaluation = f"{item['eval_after'] / 100:+.2f}"

        print(
            f"{item['ply']:>2}. {item['move_san']:<7}"
            f" {item['label']:<12}"
            f" оценка: {evaluation};"
            f" лучший: {item['best_move_san']}"
        )


if __name__ == "__main__":
    main()