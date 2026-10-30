"""Local Ollama explanations with a deterministic template fallback."""

import json
import math
import os
from urllib.error import URLError
from urllib.request import Request, urlopen

from .prompts import build_prompt
from .reasons import grounded_options


LABELS = {
    "best": "Best",
    "excellent": "Excellent",
    "good": "Good",
    "inaccuracy": "Inaccuracy",
    "mistake": "Mistake",
    "blunder": "Blunder",
    "brilliant": "Brilliant",
}


def ollama_model() -> str:
    """Return the configured local model tag."""
    return os.getenv("OLLAMA_MODEL", "gemma3:1b")


def _ollama_url(endpoint: str) -> str:
    """Build an API URL using the local server by default."""
    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    if "://" not in host:
        host = "http://" + host
    return host + endpoint


def ollama_available() -> bool:
    """Check once whether the configured model is installed, without loading it."""
    try:
        with urlopen(_ollama_url("/api/tags"), timeout=1) as response:
            data = json.load(response)
        requested = ollama_model()
        if ":" not in requested.rsplit("/", 1)[-1]:
            requested += ":latest"
        return isinstance(data, dict) and any(
            isinstance(model, dict) and model.get("name", model.get("model")) == requested
            for model in data.get("models", [])
        )
    except (URLError, OSError, ValueError, TypeError):
        return False


def _options(move: dict) -> list[str]:
    """Build approved wording from supplied analysis."""
    grounded = grounded_options(move)
    if grounded:
        return grounded
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
        "model": ollama_model(),
        "prompt": build_prompt(options),
        "stream": False,
        "options": {"temperature": 0, "num_predict": 180, "num_ctx": 1024},
        "format": {
            "type": "object",
            "properties": {
                "explanation": {"type": "string", "enum": options}
            },
            "required": ["explanation"],
            "additionalProperties": False,
        },
    }

    try:
        timeout = float(os.getenv("OLLAMA_TIMEOUT", "20"))
        if not math.isfinite(timeout) or timeout <= 0:
            return None
        request = Request(
            _ollama_url("/api/generate"),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=timeout) as response:
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


def explain_move_with_source(move: dict, use_llm: bool = True) -> tuple[str, str]:
    """Return grounded wording and its actual source: ollama or template."""
    options = _options(move)
    if use_llm:
        answer = _ask_ollama(options)
        if answer is not None:
            return answer, "ollama"
    return options[0], "template"


def explain_move(move: dict, use_llm: bool = True) -> str:
    """Return an English explanation, preserving the team's string API."""
    return explain_move_with_source(move, use_llm=use_llm)[0]


if __name__ == "__main__":
    from timurchik.analyzer import analyze

    example = analyze("1. f3 e5 2. g4 Qh4# 0-1")[2]
    options = _options(example)
    answer = _ask_ollama(options)
    print("Source:", "Ollama" if answer is not None else "Template fallback")
    print(answer if answer is not None else options[0])
