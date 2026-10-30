"""Parse PGN and analyze every half-move in a game."""

import io
from typing import Callable

import chess
import chess.pgn

from timurchik.engine import analyze_position, open_engine
from timurchik.facts import move_facts
from timurchik.labels import classify_move, win_probability


def _probability(position: dict, board: chess.Board) -> float:
    """Return White's win probability, treating mate separately."""
    if board.is_checkmate():
        # The player to move has lost in a checkmated position.
        return 0.0 if board.turn == chess.WHITE else 1.0

    if position["mate"] is not None:
        return 1.0 if position["mate"] > 0 else 0.0

    if position["eval_cp"] is None:
        raise ValueError("Stockfish did not return a position evaluation.")

    return win_probability(position["eval_cp"])


def analyze(
    pgn: str,
    time_limit: float = 0.1,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[dict]:
    """Analyze the first game in a PGN.

    progress_callback receives the completed and total half-move counts.
    """
    game = chess.pgn.read_game(io.StringIO(pgn))

    if game is None:
        raise ValueError("Could not read the PGN.")

    if game.errors:
        raise ValueError(f"Invalid PGN: {game.errors[0]}")

    moves = list(game.mainline_moves())

    if not moves:
        raise ValueError("The PGN contains no moves.")

    board = game.board()
    results = []

    if progress_callback:
        progress_callback(0, len(moves))

    with open_engine() as engine:
        before = analyze_position(engine, board, time_limit)

        for ply, move in enumerate(moves, start=1):
            board_before = board.copy(stack=False)
            fen_before = board.fen()
            move_san = board.san(move)
            mover_is_white = board.turn == chess.WHITE
            probability_before = _probability(before, board)

            is_best_move = move.uci() == before["best_move_uci"]

            board.push(move)

            after = analyze_position(engine, board, time_limit)
            probability_after = _probability(after, board)

            label = classify_move(
                probability_before,
                probability_after,
                mover_is_white=mover_is_white,
                is_best_move=is_best_move,
            )

            results.append({
                "ply": ply,
                "move_san": move_san,
                "fen_before": fen_before,
                "fen_after": board.fen(),
                "eval_before": before["eval_cp"],
                "eval_after": after["eval_cp"],
                "mate_before": before["mate"],
                "mate_after": after["mate"],
                "best_move_san": before["best_move_san"],
                "label": label,
                "facts": move_facts(board_before, move, before, after),
                "explanation": None,
            })

            # Reuse the resulting position's analysis before the next move.
            before = after

            if progress_callback:
                progress_callback(ply, len(moves))

    return results
