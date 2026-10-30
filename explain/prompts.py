"""Instructions for grounded English explanations."""

import json


def build_prompt(options: list[str]) -> str:
    """Ask the model to choose an approved explanation."""
    return (
        "You are an English-language editor, not a chess analyst. "
        "The approved explanations below contain only supplied analysis facts. "
        "Choose the clearest explanation and copy it exactly. "
        "Do not analyze chess, add reasons, or invent tactics. "
        "Return a JSON object with one key: explanation.\n"
        "Approved explanations:\n"
        + json.dumps(options, ensure_ascii=False)
    )
