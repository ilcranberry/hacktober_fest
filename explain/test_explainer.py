"""Run with: python -m unittest explain.test_explainer -v"""

import io
import json
import os
import unittest
from unittest.mock import patch
from urllib.error import URLError

from explain.explainer import explain_move, explain_move_with_source, ollama_available


MOVE = {
    "move_san": "Nf3",
    "label": "mistake",
    "best_move_san": "Nc3",
}


def fake_response(model_text):
    body = json.dumps({"response": model_text}).encode("utf-8")
    return io.BytesIO(body)


class ExplainerTests(unittest.TestCase):
    def test_source_identifies_actual_fallback_or_model(self):
        approved = "The analysis labels Nf3 as Mistake. Stockfish recommends Nc3."
        with patch("explain.explainer.urlopen", side_effect=URLError("offline")):
            text, source = explain_move_with_source(MOVE)
        self.assertEqual(source, "template")
        self.assertEqual(text, explain_move(MOVE, use_llm=False))
        with patch("explain.explainer.urlopen", return_value=fake_response(json.dumps({"explanation": approved}))):
            self.assertEqual(explain_move_with_source(MOVE), (approved, "ollama"))

    def test_availability_checks_the_selected_installed_tag(self):
        tags = {"models": [{"name": "gemma3:1b"}, {"name": "gemma3:latest"}]}
        for requested, expected in [("gemma3:1b", True), ("gemma3", True), ("gemma3:4b", False)]:
            with self.subTest(model=requested):
                with patch.dict(os.environ, {"OLLAMA_MODEL": requested}):
                    with patch("explain.explainer.urlopen", return_value=io.BytesIO(json.dumps(tags).encode())):
                        self.assertEqual(ollama_available(), expected)

    def test_offline_and_timeout_use_fallback(self):
        expected = explain_move(MOVE, use_llm=False)
        for error in (URLError("offline"), TimeoutError("timeout")):
            with self.subTest(error=type(error).__name__):
                with patch("explain.explainer.urlopen", side_effect=error):
                    self.assertEqual(explain_move(MOVE), expected)

    def test_invented_reason_is_rejected(self):
        invented = json.dumps({
            "explanation": "Nf3 loses the queen and allows checkmate."
        })
        with patch(
            "explain.explainer.urlopen",
            return_value=fake_response(invented),
        ):
            answer = explain_move(MOVE)
        self.assertEqual(answer, explain_move(MOVE, use_llm=False))
        self.assertNotIn("queen", answer)
        self.assertNotIn("checkmate", answer)

    def test_invalid_json_uses_fallback(self):
        with patch(
            "explain.explainer.urlopen",
            return_value=fake_response("This is not JSON"),
        ):
            answer = explain_move(MOVE)
        self.assertEqual(answer, explain_move(MOVE, use_llm=False))

    def test_approved_model_wording_is_accepted(self):
        approved = (
            "The analysis labels Nf3 as Mistake. "
            "Stockfish recommends Nc3."
        )
        with patch(
            "explain.explainer.urlopen",
            return_value=fake_response(
                json.dumps({"explanation": approved})
            ),
        ):
            self.assertEqual(explain_move(MOVE), approved)


if __name__ == "__main__":
    unittest.main()
