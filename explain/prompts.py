"""Instructions for grounded English explanations."""

import json


def build_prompt(options: list[str]) -> str:
    """Ask the model to choose an approved explanation."""
    return (
        "You are an English-language editor, not a chess analyst. "
        "Explain the concrete consequence of the move, not just its rating. "
        "The approved explanations below are built from verified legal-move facts "
        "and Stockfish's actual continuation, including king exposure, captures and mate. "
        "Choose the clearest causal explanation and copy it exactly. "
        "Do not analyze chess, add reasons, invent tactics, or turn a short engine line into a guaranteed result. "
        "Return a JSON object with one key: explanation.\n"
        "Approved explanations:\n"
        + json.dumps(options, ensure_ascii=False)
    )
