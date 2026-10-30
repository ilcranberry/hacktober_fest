"""Connect to Stockfish and analyze a single position."""

import os
import shutil
from pathlib import Path

import chess
import chess.engine


def open_engine() -> chess.engine.SimpleEngine:
    """Find Stockfish using STOCKFISH_PATH, PATH, or the local stockfish folder."""
    path = os.getenv("STOCKFISH_PATH") or shutil.which("stockfish")
    if not path:
        folder = Path(__file__).resolve().parents[1] / "stockfish"
        pattern = "stockfish*.exe" if os.name == "nt" else "stockfish*"
        local_binary = next(
            (file for file in sorted(folder.rglob(pattern))
             if file.is_file() and (os.name == "nt" or os.access(file, os.X_OK))),
            None,
        )
        path = str(local_binary) if local_binary else "stockfish"
    return chess.engine.SimpleEngine.popen_uci(path)


def analyze_position(
    engine: chess.engine.SimpleEngine,
    board: chess.Board,
    time_limit: float = 0.1,
) -> dict:
    """Evaluate the position from White's perspective and find the best move."""
    if time_limit <= 0:
        raise ValueError("Analysis time must be greater than zero.")

    info = engine.analyse(
        board,
        chess.engine.Limit(time=time_limit),
    )

    # Convert the engine's score to White's perspective regardless of whose turn it is.
    score = info["score"].pov(chess.WHITE)

    # The principal variation can be empty in a finished position.
    continuation = info.get("pv", [])
    best_move = continuation[0] if continuation else None

    return {
        "eval_cp": score.score(),
        "mate": score.mate(),
        "best_move_uci": best_move.uci() if best_move else None,
        "best_move_san": board.san(best_move) if best_move else None,
        "pv_uci": [move.uci() for move in continuation[:6]],
    }
