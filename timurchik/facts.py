"""Replay engine lines and extract literal board facts; no position evaluation."""

import chess

CENTRE = {chess.D4, chess.E4, chess.D5, chess.E5}


def _side(color):
    return "White" if color == chess.WHITE else "Black"


def _captured_square(board, move):
    if board.is_en_passant(move):
        return move.to_square + (-8 if board.turn == chess.WHITE else 8)
    return move.to_square


def _capture(board, move):
    if not board.is_capture(move):
        return None
    square = _captured_square(board, move)
    piece = board.piece_at(square)
    return {
        "piece": chess.piece_name(piece.piece_type),
        "square": chess.square_name(square),
        "side": _side(piece.color),
    } if piece else None


def _event(board, move):
    """Describe a legal move, including whether an immediate recapture exists."""
    piece = board.piece_at(move.from_square)
    after = board.copy(stack=False)
    after.push(move)
    capture = _capture(board, move)
    can_recapture = None
    if capture:
        can_recapture = any(
            after.is_capture(reply) and _captured_square(after, reply) == move.to_square
            for reply in after.legal_moves
        )
    return {
        "san": board.san(move),
        "uci": move.uci(),
        "side": _side(board.turn),
        "piece": chess.piece_name(piece.piece_type),
        "from": chess.square_name(move.from_square),
        "to": chess.square_name(move.to_square),
        "capture": capture,
        "check": after.is_check(),
        "checked_king": chess.square_name(after.king(after.turn)) if after.is_check() else None,
        "checkmate": after.is_checkmate(),
        "stalemate": after.is_stalemate(),
        "can_be_recaptured": can_recapture,
        "promotion": chess.piece_name(move.promotion) if move.promotion else None,
    }


def _line(board, uci_moves):
    """Validate and replay at most six engine half-moves on a copy."""
    position = board.copy(stack=False)
    events = []
    for uci in uci_moves[:6]:
        try:
            move = position.parse_uci(uci)
        except ValueError:
            break
        if not move or not position.is_legal(move):
            break
        events.append(_event(position, move))
        position.push(move)
    return events


def _opened_king_diagonal(before, after, move):
    """Identify a pawn vacating a diagonal next to its unmoved king."""
    piece = before.piece_at(move.from_square)
    king = before.king(piece.color)
    if piece.piece_type != chess.PAWN or king is None or after.king(piece.color) != king:
        return None
    dx = chess.square_file(move.from_square) - chess.square_file(king)
    dy = chess.square_rank(move.from_square) - chess.square_rank(king)
    if abs(dx) != 1 or abs(dy) != 1:
        return None
    file, rank = chess.square_file(king) + dx, chess.square_rank(king) + dy
    empty = []
    while 0 <= file < 8 and 0 <= rank < 8:
        square = chess.square(file, rank)
        if after.piece_at(square):
            break
        empty.append(square)
        file += dx
        rank += dy
    if len(empty) < 2:
        return None
    return {"king": chess.square_name(king), "end": chess.square_name(empty[-1]),
            "vacated": chess.square_name(move.from_square)}


def _has_mate_in_one(board):
    """Verify legal immediate mates, without guessing from attack counts."""
    for move in board.legal_moves:
        position = board.copy(stack=False)
        position.push(move)
        if position.is_checkmate():
            return True
    return False


def _targets(board, square):
    """List non-pawn enemy pieces geometrically attacked from a square."""
    attacker = board.piece_at(square)
    return [
        {"piece": chess.piece_name(target.piece_type), "square": chess.square_name(target_square)}
        for target_square in board.attacks(square)
        if (target := board.piece_at(target_square))
        and target.color != attacker.color and target.piece_type != chess.PAWN
    ]


def move_facts(before, move, analysis_before, analysis_after):
    """Return JSON facts for one move; example: see python -m timurchik.example."""
    event = _event(before, move)
    after = before.copy(stack=False)
    after.push(move)
    continuation = _line(after, analysis_after.get("pv_uci", []))
    best_line = _line(before, analysis_before.get("pv_uci", []))
    piece = after.piece_at(move.to_square)
    targets = _targets(after, move.to_square)
    reply_attacks = []
    if continuation:
        reply_move = after.parse_uci(continuation[0]["uci"])
        reply_position = after.copy(stack=False)
        reply_position.push(reply_move)
        if not reply_position.is_pinned(after.turn, reply_move.to_square):
            reply_attacks = [target for target in _targets(reply_position, reply_move.to_square)
                             if target["piece"] != "king"]

    avoids_mate = False
    alternative_defense = None
    if continuation and continuation[0]["checkmate"] and best_line:
        alternative = before.copy(stack=False)
        alternative.push_uci(best_line[0]["uci"])
        avoids_mate = not _has_mate_in_one(alternative)
        mating_move = chess.Move.from_uci(continuation[0]["uci"])
        if avoids_mate and alternative.is_legal(mating_move):
            reply_san = alternative.san(mating_move)
            alternative.push(mating_move)
            if alternative.is_check() and not alternative.is_checkmate():
                alternative_defense = {
                    "reply": reply_san,
                    "moves": sorted([alternative.san(reply) for reply in alternative.legal_moves], key=str.casefold),
                }

    mate = analysis_after.get("mate")
    mate_for = None
    if mate is not None and not event["checkmate"]:
        mate_for = {"side": "White" if mate > 0 else "Black", "moves": abs(mate)}

    recapture = None
    if len(continuation) >= 2 and continuation[1]["capture"]:
        if continuation[1]["capture"]["square"] == continuation[0]["to"]:
            recapture = continuation[1]
    king_cover = []
    king = after.king(before.turn)
    if before.is_castling(move) and king is not None:
        rank = chess.square_rank(king) + (1 if before.turn else -1)
        for file in range(max(0, chess.square_file(king) - 1), min(7, chess.square_file(king) + 1) + 1):
            square = chess.square(file, rank)
            if after.piece_at(square) == chess.Piece(chess.PAWN, before.turn):
                king_cover.append(chess.square_name(square))

    return {
        "move": event,
        "opened_king_diagonal": _opened_king_diagonal(before, after, move),
        "develops_piece": event["piece"] in {"knight", "bishop"}
            and chess.square_rank(move.from_square) == (0 if before.turn else 7)
            and chess.square_rank(move.to_square) != chess.square_rank(move.from_square),
        "center_attacks": [chess.square_name(s) for s in sorted(after.attacks(move.to_square) & CENTRE)],
        "attacks": [chess.square_name(s) for s in after.attacks(move.to_square)],
        "double_attack": targets if len(targets) >= 2 and piece.piece_type != chess.KING
            and not after.is_pinned(piece.color, move.to_square) else [],
        "castling": ("kingside" if before.is_kingside_castling(move) else "queenside")
            if before.is_castling(move) else None,
        "king_pawn_cover": king_cover,
        "opponent_reply": continuation[0] if continuation else None,
        "reply_attacks": reply_attacks,
        "reply_recapture": recapture,
        "continuation": [event["san"] for event in continuation],
        "best_continuation": [event["san"] for event in best_line],
        "best_avoids_immediate_mate": avoids_mate,
        "alternative_defense": alternative_defense,
        "mate_for": mate_for,
    }
