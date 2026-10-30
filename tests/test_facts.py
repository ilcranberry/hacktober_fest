"""Regressions for useful, verifiable move explanations without an engine."""

import copy
import io
import json
import unittest
from unittest.mock import patch

import chess

from explain.explainer import explain_move, explain_move_with_source
from explain.reasons import grounded_options
from timurchik.facts import move_facts


def position(moves):
    board = chess.Board()
    for san in moves:
        board.push_san(san)
    return board


def record(board, san, before_pv=(), after_pv=(), label="mistake", mate=None):
    move = board.parse_san(san)
    before = {"pv_uci": list(before_pv)}
    after = {"pv_uci": list(after_pv), "mate": mate}
    return {"move_san": san, "label": label,
            "best_move_san": board.san(board.parse_uci(before_pv[0])) if before_pv else None,
            "facts": move_facts(board, move, before, after)}


class FactExplanationTests(unittest.TestCase):
    def test_f_pawn_opens_a_specific_diagonal_without_inventing_an_attack(self):
        board = chess.Board()
        original = board.fen()
        row = record(board, "f3", ["e2e4"], ["e7e5"], label="inaccuracy")
        self.assertEqual(board.fen(), original)
        self.assertEqual(row["facts"]["opened_king_diagonal"],
                         {"king": "e1", "end": "h4", "vacated": "f2"})
        text = explain_move(row, use_llm=False)
        self.assertIn("e1-h4 diagonal", text)
        self.assertNotIn("classified", text)
        self.assertNotIn("checkmate", text)

    def test_fools_mate_explains_the_threat_and_verified_safe_alternative(self):
        board = position(["f3", "e5"])
        row = record(board, "g4", ["g2g3"], ["d8h4"], label="blunder", mate=-1)
        self.assertTrue(row["facts"]["best_avoids_immediate_mate"])
        self.assertIsNone(row["facts"]["opened_king_diagonal"])
        text = explain_move(row, use_llm=False)
        self.assertIn("Qh4#", text)
        self.assertIn("checkmates your king on e1", text)
        self.assertIn("g3 avoids an immediate mate", text)
        self.assertNotIn("opens", text)

    def test_the_alternative_explains_which_defense_remains_available(self):
        board = position(["f3", "e5"])
        row = record(board, "g4", ["b1c3"], ["d8h4"], label="blunder", mate=-1)
        self.assertEqual(row["facts"]["alternative_defense"], {"reply": "Qh4+", "moves": ["g3"]})
        text = explain_move(row, use_llm=False)
        self.assertIn("Qh4+ can be answered by g3", text)

    def test_hanging_queen_is_explained_by_the_actual_engine_capture(self):
        board = position(["e4", "e5", "Qh5", "Nc6"])
        row = record(board, "Qxe5+", ["f1c4"], ["c6e5"], label="blunder")
        self.assertEqual(row["facts"]["opponent_reply"]["capture"]["piece"], "queen")
        self.assertFalse(row["facts"]["opponent_reply"]["can_be_recaptured"])
        text = explain_move(row, use_llm=False)
        self.assertIn("Nxe5 captures your queen on e5", text)
        self.assertIn("cannot be immediately recaptured", text)

    def test_a_recapturable_piece_is_not_called_unprotected(self):
        board = position(["e4", "e5", "Nf3", "Nc6", "d4", "exd4"])
        row = record(board, "Nxd4", ["f3d4"], ["c6d4", "d1d4"])
        self.assertTrue(row["facts"]["opponent_reply"]["can_be_recaptured"])
        self.assertEqual(row["facts"]["reply_recapture"]["san"], "Qxd4")
        text = explain_move(row, use_llm=False)
        self.assertNotIn("cannot be immediately recaptured", text)
        self.assertIn("recaptures the knight", text)

    def test_a_pinned_defender_does_not_count_as_a_legal_recapture(self):
        board = chess.Board("4r1k1/8/8/8/4b3/8/1N2Q3/4K3 w - - 0 1")
        self.assertTrue(board.is_valid())
        row = record(board, "Nd3", [], ["e4d3"])
        self.assertFalse(row["facts"]["opponent_reply"]["can_be_recaptured"])
        board.push_san("Nd3")
        board.push_san("Bxd3")
        self.assertIn(chess.D3, board.attacks(chess.E2))
        self.assertNotIn(chess.Move.from_uci("e2d3"), board.legal_moves)
        self.assertIn("cannot be immediately recaptured", explain_move(row, use_llm=False))

    def test_development_and_center_control_are_explained_for_quiet_moves(self):
        board = position(["e4", "e5"])
        row = record(board, "Nf3", ["g1f3"], ["b8c6"], label="best")
        text = explain_move(row, use_llm=False)
        self.assertIn("knight off the back rank", text)
        self.assertIn("d4 and e5", text)
        self.assertNotIn("checkmate", text)

    def test_reply_can_attack_a_queen_without_already_capturing_it(self):
        board = position(["e4", "e5"])
        row = record(board, "Qh5", ["g1f3"], ["g8f6"])
        self.assertIsNone(row["facts"]["opponent_reply"]["capture"])
        self.assertIn({"piece": "queen", "square": "h5"}, row["facts"]["reply_attacks"])
        text = explain_move(row, use_llm=False)
        self.assertIn("attacking your queen on h5", text)
        self.assertNotIn("captures your queen", text)

    def test_en_passant_names_the_actual_captured_square(self):
        board = position(["e4", "a6", "e5", "d5"])
        row = record(board, "exd6", [], [], label="good")
        self.assertEqual(row["facts"]["move"]["capture"]["square"], "d5")
        self.assertIn("pawn on d5", explain_move(row, use_llm=False))

    def test_illegal_engine_lines_and_null_moves_are_not_presented_as_evidence(self):
        row = record(chess.Board(), "e4", [], ["d8h4", "0000"])
        self.assertEqual(row["facts"]["continuation"], [])
        row = record(chess.Board(), "e4", [], ["0000"])
        self.assertIsNone(row["facts"]["opponent_reply"])

    def test_facts_are_not_modified_by_the_explainer(self):
        row = record(chess.Board(), "f3", ["e2e4"], ["e7e5"])
        original = copy.deepcopy(row)
        explain_move(row, use_llm=False)
        self.assertEqual(row, original)

    def test_castling_explains_the_king_and_its_actual_pawn_cover(self):
        board = position(["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5"])
        row = record(board, "O-O", [], [], label="good")
        self.assertEqual(row["facts"]["castling"], "kingside")
        self.assertEqual(row["facts"]["king_pawn_cover"], ["f2", "g2", "h2"])
        text = explain_move(row, use_llm=False)
        self.assertIn("king to g1", text)
        self.assertIn("f2, g2 and h2", text)
        self.assertNotIn("unprotected", text)

    def test_a_pinned_knight_is_not_presented_as_a_working_fork(self):
        board = chess.Board("2r4k/8/8/r3q3/2p5/4N3/8/2K5 w - - 0 1")
        self.assertTrue(board.is_valid())
        row = record(board, "Nxc4", [], [])
        board.push_san("Nxc4")
        self.assertTrue(board.is_pinned(chess.WHITE, chess.C4))
        self.assertEqual(row["facts"]["double_attack"], [])

    def test_a_promoted_queen_is_not_described_as_a_checking_pawn(self):
        board = chess.Board("7k/5P2/6K1/8/8/8/8/8 w - - 0 1")
        row = record(board, "f8=Q#", [], [], label="best")
        self.assertTrue(row["facts"]["move"]["checkmate"])
        text = explain_move(row, use_llm=False)
        self.assertIn("queen on f8 checks", text)
        self.assertNotIn("pawn on f8", text)

    def test_a_promoted_queen_double_attack_names_the_correct_piece(self):
        board = chess.Board("r6k/2P5/8/8/8/8/8/6K1 w - - 0 1")
        row = record(board, "c8=Q+", [], [], label="best")
        self.assertTrue(row["facts"]["double_attack"])
        self.assertIn("queen on c8 attacks", explain_move(row, use_llm=False))

    def test_rich_model_wording_is_accepted_but_an_invented_tactic_is_rejected(self):
        row = record(chess.Board(), "f3", ["e2e4"], ["e7e5"])
        approved = grounded_options(row)[-1]
        for answer, source in [(approved, "ollama"), ("This loses your queen and forces checkmate.", "template")]:
            body = json.dumps({"response": json.dumps({"explanation": answer})}).encode()
            with patch("explain.explainer.urlopen", return_value=io.BytesIO(body)):
                text, actual_source = explain_move_with_source(row)
            self.assertEqual(actual_source, source)
            self.assertIn("diagonal", text)
            self.assertNotIn("loses your queen", text)


if __name__ == "__main__":
    unittest.main()
