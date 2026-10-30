"""Turn verified core facts into short explanations without inventing chess reasons."""

BAD_LABELS = {"inaccuracy", "mistake", "blunder"}


def _join(items):
    if len(items) < 2:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def grounded_options(move):
    """Build two grounded 2–3 sentence variants, or return None for legacy records."""
    facts = move.get("facts") or {}
    played = facts.get("move")
    if not played:
        return None
    san = move["move_san"]
    side = played["side"]
    active_piece = played.get("promotion") or played["piece"]
    opponent = "Black" if side == "White" else "White"
    best = move.get("best_move_san")
    reply = facts.get("opponent_reply")
    reply_piece = (reply.get("promotion") or reply["piece"]) if reply else None
    diagonal = facts.get("opened_king_diagonal")
    bad = move["label"] in BAD_LABELS
    sentences = []
    alternate = None

    if played["checkmate"]:
        sentences = [f"{san} delivers checkmate.",
                     f"Your {active_piece} on {played['to']} checks the king on {played['checked_king']}, and {opponent} has no legal reply."]
        alternate = f"{opponent}'s king on {played['checked_king']} is checkmated by {san}."
    elif played["stalemate"]:
        sentences = [f"After {san}, {opponent} has no legal move but is not in check.",
                     "This is stalemate, so the game is drawn."]
    elif reply and reply["checkmate"]:
        sentences = [f"After {san}, {opponent} can play {reply['san']}, which checkmates your king on {reply['checked_king']}."]
        alternate = f"This allows {reply['san']}: {opponent}'s {reply_piece} delivers checkmate to your king on {reply['checked_king']}."
        defense = facts.get("alternative_defense")
        if defense and defense["moves"] and best:
            answers = " or ".join(defense["moves"][:2])
            sentences.append(f"With Stockfish's alternative {best}, {defense['reply']} can be answered by {answers}.")
        elif facts.get("best_avoids_immediate_mate") and best:
            sentences.append(f"Stockfish's alternative {best} avoids an immediate mate.")
    elif bad and reply and reply.get("capture"):
        victim = reply["capture"]
        sentences = [f"After {san}, Stockfish's reply {reply['san']} captures your {victim['piece']} on {victim['square']}."]
        alternate = f"In Stockfish's continuation, {opponent} answers with {reply['san']} and takes your {victim['piece']} on {victim['square']}."
        recapture = facts.get("reply_recapture")
        capturing_piece = reply.get("promotion") or reply["piece"]
        if recapture:
            sentences.append(f"The reply {recapture['san']} then recaptures the {capturing_piece}, exchanging your {victim['piece']} for that {capturing_piece} in this line.")
        elif reply["can_be_recaptured"] is False:
            sentences.append(f"The capturing {capturing_piece} cannot be immediately recaptured on {reply['to']}.")
    elif bad and diagonal:
        sentences = [f"Moving the pawn from {played['from']} to {played['to']} opens the {diagonal['king']}-{diagonal['end']} diagonal toward your king."]
        alternate = f"The pawn on {diagonal['vacated']} no longer blocks the diagonal from your king on {diagonal['king']} to {diagonal['end']}."
        if facts.get("mate_for") and facts["mate_for"]["side"] == opponent:
            sentences.append(f"Stockfish now finds a forced mate in {facts['mate_for']['moves']} for {opponent}.")
    elif facts.get("mate_for") and facts["mate_for"]["side"] == opponent:
        mate = facts["mate_for"]
        sentences = [f"After {san}, Stockfish finds a forced mate in {mate['moves']} for {opponent}."]
    elif bad and reply and facts.get("reply_attacks"):
        targets = _join([f"your {target['piece']} on {target['square']}" for target in facts["reply_attacks"]])
        sentences = [f"Stockfish's reply {reply['san']} puts {opponent}'s {reply_piece} on {reply['to']}, attacking {targets}."]
    elif facts.get("double_attack"):
        targets = _join([f"{opponent}'s {target['piece']} on {target['square']}" for target in facts["double_attack"]])
        sentences = [f"Your {active_piece} on {played['to']} attacks {targets} at the same time."]
        if played["check"]:
            sentences.append(f"Because this is check, {opponent} must deal with the threat to the king.")
    elif facts.get("castling"):
        sentences = [f"{san} castles {facts['castling']}, moving your king to {played['to']}."]
        if facts["king_pawn_cover"]:
            sentences.append(f"The king now has friendly pawns directly in front of it on {_join(facts['king_pawn_cover'])}.")
    elif played.get("promotion"):
        sentences = [f"{san} promotes your pawn to a {played['promotion']} on {played['to']}."]
    elif played.get("capture"):
        victim = played["capture"]
        sentences = [f"{san} captures {opponent}'s {victim['piece']} on {victim['square']}."]
        if played["check"]:
            sentences.append(f"It also gives check, so {opponent} must respond to the king threat.")
    elif facts.get("develops_piece"):
        sentences = [f"{san} brings your {played['piece']} off the back rank into play."]
        if facts.get("center_attacks"):
            noun = "square" if len(facts["center_attacks"]) == 1 else "squares"
            sentences.append(f"From {played['to']}, it covers the central {noun} {_join(facts['center_attacks'])}.")
    elif played["check"]:
        sentences = [f"{san} checks {opponent}'s king on {played['checked_king']}.",
                     f"{opponent} must answer the check on the next move."]
    elif facts.get("center_attacks"):
        squares = _join(facts["center_attacks"])
        sentences = [f"Your {active_piece} on {played['to']} now covers {squares} in the center."]
    elif played["piece"] == "pawn" and facts.get("attacks"):
        sentences = [f"The pawn on {played['to']} covers {_join(facts['attacks'])}."]
    else:
        sentences = ["No specific tactical consequence was verified for this move at the current search limit."]

    if len(sentences) < 2:
        line = facts.get("continuation", [])[:4]
        if line and (bad or not best or best == san):
            sentences.append(f"Stockfish's continuation begins {' '.join(line)}.")
        elif best and best != san:
            sentences.append(f"Stockfish's alternative is {best}.")
        else:
            sentences.append("It matches Stockfish's preferred move in this position." if best == san
                             else "The engine did not provide a best-move alternative.")
    if bad and best and best != san and len(sentences) < 3 and best not in " ".join(sentences):
        sentences.append(f"Stockfish's alternative is {best}.")
    primary = " ".join(sentences[:3])
    secondary = " ".join([alternate or sentences[0], *sentences[1:3]])
    return list(dict.fromkeys([primary, secondary]))
