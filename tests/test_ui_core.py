"""UI/core boundary checks: python -m unittest discover -s tests -v."""

import copy
import os
import unittest
from unittest.mock import patch

import chess
import chess.engine
import gradio as gr

from nikitosik import app
from timurchik.engine import open_engine


def analysis_rows(pgn=app.EXAMPLE):
    """Build a deterministic core result fixture, without running an engine."""
    game = app.parse_game(pgn)
    return [
        {
            "ply": i + 1,
            "move_san": san,
            "fen_before": game["positions"][i],
            "fen_after": game["positions"][i + 1],
            "eval_before": 20.0,
            "eval_after": -100.0,
            "mate_before": None,
            "mate_after": None,
            "best_move_san": san,
            "label": "mistake",
            "facts": {"source": "test fixture"},
            "explanation": "An explanation supplied by the analysis module.",
        }
        for i, san in enumerate(game["moves"])
    ]


class UICoreTests(unittest.TestCase):
    def setUp(self):
        available = patch.object(app, "ollama_available", return_value=False)
        available.start()
        self.addCleanup(available.stop)

    def test_load_uses_core_and_reports_real_move_counts(self):
        rows = analysis_rows()
        updates = []

        def analyze(pgn, time_limit, progress_callback):
            self.assertEqual(pgn, app.EXAMPLE)
            self.assertEqual(time_limit, 0.2)
            for done in range(len(rows) + 1):
                progress_callback(done, len(rows))
            return rows

        with patch.object(app, "analyze", side_effect=analyze):
            result = app.load_game(
                app.EXAMPLE, 0.2,
                progress=lambda value, **kwargs: updates.append((value, kwargs.get("desc", ""))),
            )
        game, index, _, counter, _, status = result
        self.assertEqual(game["analysis"], rows)
        self.assertEqual(index, 0)
        self.assertIn("0 / 4", counter)
        self.assertIn("Analysis complete", status)
        self.assertEqual([desc for _, desc in updates if desc.startswith("Stockfish:")],
                         [f"Stockfish: half-move {i} / 4" for i in range(5)])
        _, _, _, details = app.navigate(game, index, 1)
        self.assertIn("Mistake", details)
        self.assertIn("+0.20", details)
        self.assertIn("-1.00", details)
        self.assertIn(rows[0]["explanation"], details)
        self.assertEqual(app.navigate(game, 0, -1)[0], 0)
        self.assertEqual(app.navigate(game, 4, 1)[0], 4)

    def test_rejects_core_results_for_another_game(self):
        rows = analysis_rows()
        rows[0]["fen_after"] = chess.STARTING_FEN
        with patch.object(app, "analyze", return_value=rows):
            with self.assertRaisesRegex(gr.Error, "do not match"):
                app.load_game(app.EXAMPLE)

    def test_missing_engine_and_engine_crash_have_english_errors(self):
        cases = [
            (FileNotFoundError("missing"), "STOCKFISH_PATH"),
            (chess.engine.EngineTerminatedError("terminated"), "Stockfish could not complete"),
        ]
        for error, message in cases:
            with self.subTest(error=type(error).__name__):
                with patch.object(app, "analyze", side_effect=error):
                    with self.assertRaisesRegex(gr.Error, message):
                        app.load_game(app.EXAMPLE)

    def test_mate_scores_are_not_shown_as_centipawns(self):
        row = analysis_rows()[0]
        for mate, expected in [(3, "Mate in 3 (White)"), (-2, "Mate in 2 (Black)")]:
            row["mate_after"] = mate
            row["eval_after"] = None
            self.assertEqual(app.format_evaluation(row, "after"), expected)
        last = analysis_rows()[-1]
        last["mate_after"] = 0
        last["eval_after"] = None
        self.assertEqual(app.format_evaluation(last, "after"), "Checkmate (Black wins)")

    def test_custom_starting_position_and_new_game_reset(self):
        pgn = ('[SetUp "1"]\n'
               '[FEN "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1"]\n\n'
               '1... e5 *')
        with patch.object(app, "analyze", return_value=analysis_rows(pgn)):
            game, index, *_ = app.load_game(pgn)
        self.assertEqual(index, 0)
        self.assertEqual(chess.Board(game["positions"][0]).turn, chess.BLACK)
        self.assertEqual(app.navigate(game, 0, 1)[0], 1)

    def test_render_preserves_core_explanations_and_empty_state(self):
        game = app.parse_game(app.EXAMPLE)
        game["analysis"] = analysis_rows()
        original = copy.deepcopy(game)
        app.render_position(game, 1)
        self.assertEqual(game, original)
        game["analysis"][0]["explanation"] = None
        self.assertIn("No explanation has been generated yet", app.render_position(game, 1)[3])

    def test_explicit_engine_path_takes_precedence(self):
        with patch.dict(os.environ, {"STOCKFISH_PATH": "custom engine.exe"}):
            with patch("timurchik.engine.chess.engine.SimpleEngine.popen_uci") as popen:
                open_engine()
        popen.assert_called_once_with("custom engine.exe")

    def test_navigation_explains_other_moves_automatically_and_caches_them(self):
        rows = analysis_rows()
        for row, label in zip(rows, ["inaccuracy", "good", "mistake", "best"]):
            row["label"] = label
            row["explanation"] = None
        original = copy.deepcopy(rows)
        with patch.object(app, "analyze", return_value=rows):
            with patch.object(app, "explain_move_with_source", wraps=app.explain_move_with_source) as explain:
                game, *_ = app.load_game(app.EXAMPLE)
                self.assertEqual(explain.call_count, 2)
                self.assertIsNone(game["analysis"][1]["explanation"])
                self.assertIsNone(game["analysis"][3]["explanation"])
                new_index, _, _, details = app.navigate(game, 1, 1)
                self.assertEqual(new_index, 2)
                self.assertIn("Explanation source: Template", details)
                self.assertTrue(game["analysis"][1]["explanation"])
                self.assertEqual(explain.call_count, 3)
                app.navigate(game, 3, -1)
                app.navigate(game, 0, -1)
                self.assertEqual(explain.call_count, 3)
        for before, after in zip(original, game["analysis"]):
            self.assertEqual({k: v for k, v in before.items() if k != "explanation"},
                             {k: v for k, v in after.items() if k != "explanation"})

    def test_one_llm_failure_disables_repeated_requests_for_the_game(self):
        rows = analysis_rows()
        for row in rows:
            row["explanation"] = None
        with patch.object(app, "analyze", return_value=rows):
            with patch.object(app, "ollama_available", return_value=True):
                with patch.object(app, "explain_move_with_source", return_value=("Safe wording.", "template")) as explain:
                    game, *_ = app.load_game(app.EXAMPLE)
        self.assertEqual([call.kwargs["use_llm"] for call in explain.call_args_list],
                         [True, False, False, False])
        self.assertFalse(game["ollama_ready"])

    def test_navigation_without_a_loaded_game_does_not_request_an_explanation(self):
        empty = {"positions": [chess.STARTING_FEN], "moves": [], "analysis": []}
        with patch.object(app, "explain_move_with_source") as explain:
            self.assertEqual(app.navigate(empty, 0, 1)[0], 0)
            self.assertEqual(app.navigate(empty, 0, -1)[0], 0)
        explain.assert_not_called()


@unittest.skipUnless(os.getenv("RUN_STOCKFISH_TESTS") == "1", "Set RUN_STOCKFISH_TESTS=1 for real engine checks")
class StockfishSmokeTests(unittest.TestCase):
    def test_game_analysis_with_real_stockfish(self):
        game, index, *_, status = app.load_game(app.EXAMPLE, time_limit=0.1, use_llm=False)
        self.assertEqual(len(game["analysis"]), 4)
        self.assertEqual(index, 0)
        self.assertIn("Analysis complete", status)
        for row in game["analysis"]:
            self.assertIn(row["label"], app.LABELS)
            self.assertTrue(row["eval_after"] is not None or row["mate_after"] is not None)
        self.assertIn("Checkmate (Black wins)", app.render_position(game, 4)[3])


if __name__ == "__main__":
    unittest.main()
