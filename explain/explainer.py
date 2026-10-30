"""Local Ollama explanations with a deterministic template fallback."""

import json
import os
from urllib.error import URLError
from urllib.request import Request, urlopen

from .prompts import build_prompt


LABELS = {
    "best": "Best",
    "excellent": "Excellent",
    "good": "Good",
    "inaccuracy": "Inaccuracy",
    "mistake": "Mistake",
    "blunder": "Blunder",
    "brilliant": "Brilliant",
}


def _options(move: dict) -> list[str]:
    """Build approved wording from supplied analysis."""
    san = move["move_san"]
    label = LABELS.get(move["label"], move["label"])
    best = move.get("best_move_san")

    if best and best == san:
        detail = "It matches Stockfish's recommendation."
    elif best:
        detail = f"Stockfish recommends {best}."
    else:
        detail = "No best-move recommendation was provided."

    return [
        f"The move {san} is classified as {label}. {detail}",
        f"The analysis labels {san} as {label}. {detail}",
    ]


def _ask_ollama(options: list[str]) -> str | None:
    """Accept only approved wording; return None on failure."""
    payload = {
        "model": os.getenv("OLLAMA_MODEL", "gemma3:1b"),
        "prompt": build_prompt(options),
        "stream": False,
        "options": {"temperature": 0, "num_predict": 180},
        "format": {
            "type": "object",
            "properties": {
                "explanation": {"type": "string", "enum": options}
            },
            "required": ["explanation"],
            "additionalProperties": False,
        },
    }

    request = Request(
        "http://localhost:11434/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=20) as response:
            envelope = json.load(response)

        result = json.loads(envelope["response"])
        if not isinstance(result, dict):
            return None

        answer = result.get("explanation")
        if isinstance(answer, str) and answer in options:
            return answer
    except (URLError, OSError, ValueError, KeyError, TypeError):
        return None

    return None


def explain_move(move: dict, use_llm: bool = True) -> str:
    """Return an English explanation, falling back when needed."""
    options = _options(move)
    if use_llm:
        answer = _ask_ollama(options)
        if answer is not None:
            return answer
    return options[0]


if __name__ == "__main__":
    example = {
        "move_san": "Nf3",
        "label": "mistake",
        "best_move_san": "Nc3",
    }
    options = _options(example)
    answer = _ask_ollama(options)
    print("Source:", "Ollama" if answer is not None else "Template fallback")
    print(answer if answer is not None else options[0])
