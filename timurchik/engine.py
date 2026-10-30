"""Подключение Stockfish и анализ отдельной позиции."""

import os

import chess
import chess.engine


def open_engine() -> chess.engine.SimpleEngine:
    """Запустить Stockfish. Путь можно задать через STOCKFISH_PATH."""
    path = os.getenv("STOCKFISH_PATH", "stockfish")
    return chess.engine.SimpleEngine.popen_uci(path)


def analyze_position(
    engine: chess.engine.SimpleEngine,
    board: chess.Board,
    time_limit: float = 0.1,
) -> dict:
    """Оценить позицию со стороны белых и найти лучший ход."""
    if time_limit <= 0:
        raise ValueError("Время анализа должно быть больше нуля.")

    info = engine.analyse(
        board,
        chess.engine.Limit(time=time_limit),
    )

    # Stockfish может возвращать оценку со стороны ходящего.
    # Всегда приводим её к точке зрения белых.
    score = info["score"].pov(chess.WHITE)

    # PV — лучшее продолжение, найденное движком.
    # В завершённой позиции продолжение может отсутствовать.
    continuation = info.get("pv", [])
    best_move = continuation[0] if continuation else None

    return {
        "eval_cp": score.score(),
        "mate": score.mate(),
        "best_move_uci": best_move.uci() if best_move else None,
        "best_move_san": board.san(best_move) if best_move else None,
    }