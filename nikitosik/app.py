"""Gradio game viewer. Run from the repository root with python app.py."""

import html
import importlib
import io
import re
import sys
from pathlib import Path

import chess
import chess.pgn
import chess.svg
import gradio as gr

EXAMPLE = '[Event "Demo"]\n[White "White"]\n[Black "Black"]\n[Result "0-1"]\n\n1. f3 e5 2. g4 Qh4# 0-1'
LABELS = {
    "best": "Best", "excellent": "Excellent", "good": "Good",
    "inaccuracy": "Inaccuracy", "mistake": "Mistake",
    "blunder": "Blunder", "brilliant": "Brilliant",
}


def parse_game(text):
    """Validate one pasted PGN, preserving its initial FEN."""
    if not text.strip():
        raise ValueError('Paste a PGN game or click "Example game".')
    if text.strip().startswith(("https://", "http://")):
        raise ValueError("Lichess URL loading is not available yet. Please paste the game's PGN.")
    # python-chess can silently skip unknown tokens; reject obvious broken SAN.
    movetext = re.sub(r'(?m)^\s*\[.*\]\s*$', '', text)
    movetext = re.sub(r'\{[^}]*\}|;[^\n]*|(?m:^%[^\n]*)', ' ', movetext)
    movetext = re.sub(r'\d+\.(?:\.\.)?|\$\d+|[()]', ' ', movetext)
    san_pattern = r'(?:[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=?[QRBN])?|[O0]-[O0](?:-[O0])?)[+#]?[!?]*'
    for token in movetext.split():
        if token not in {'*', '1-0', '0-1', '1/2-1/2', '...'} and not re.fullmatch(san_pattern, token):
            raise ValueError(f"Invalid move notation: {token}")
    game = chess.pgn.read_game(io.StringIO(text))
    if game is None or game.errors:
        raise ValueError("Could not read the PGN. Please check the move notation.")
    board = game.board()
    positions = [board.fen()]
    moves = []
    for move in game.mainline_moves():
        moves.append(board.san(move))
        board.push(move)
        positions.append(board.fen())
    if not moves:
        raise ValueError("The PGN contains no moves.")
    return {"positions": positions, "moves": moves, "analysis": []}


def render_position(game, index):
    """Render a position and only facts supplied by the analysis module."""
    index = max(0, min(int(index), len(game["moves"])))
    board = chess.Board(game["positions"][index])
    lastmove = None
    if index:
        before = chess.Board(game["positions"][index - 1])
        lastmove = before.parse_san(game["moves"][index - 1])
    svg = chess.svg.board(board, lastmove=lastmove, size=460)
    caption = f"Half-move {index} / {len(game['moves'])}"
    detail = 'Starting position. Click "Next" to step through the game.'
    if index:
        detail = f"### Half-move {index}: {html.escape(game['moves'][index - 1])}\n\n"
        if game["analysis"]:
            row = game["analysis"][index - 1]
            label = LABELS.get(row["label"], row["label"])
            detail += f"**{html.escape(label)}**\n\n"
            detail += html.escape(row.get("explanation") or "No explanation has been generated yet.")
            detail += "\n\nBest move: " + html.escape(row.get("best_move_san") or "—")
        else:
            detail += "Viewing mode: game analysis is not available yet. Evaluations and explanations will appear once analysis is connected."
    return index, svg, caption, detail


def load_game(text, progress=gr.Progress()):
    """Load PGN and use the team's analyze(pgn) contract when available."""
    try:
        progress(0, desc="Reading PGN")
        game = parse_game(text)
        try:
            engine = importlib.import_module("core.engine")
        except ModuleNotFoundError as exc:
            if exc.name not in {"core", "core.engine"}:
                raise
            engine = None
        status = "Game loaded. Viewing mode without analysis."
        if engine is not None:
            progress(0.1, desc="Stockfish is analyzing the game")
            rows = engine.analyze(text)
            if len(rows) != len(game["moves"]):
                raise ValueError("The analysis returned an incorrect number of half-moves.")
            for i, row in enumerate(rows):
                if (row["fen_before"] != game["positions"][i]
                        or row["fen_after"] != game["positions"][i + 1]):
                    raise ValueError("The analyzed positions do not match the PGN.")
            game["analysis"] = rows
            status = "Analysis complete. Step through the moves to review the game."
        progress(1, desc="Done")
        return game, *render_position(game, 0), status
    except Exception as exc:
        raise gr.Error(f"Could not load the game: {exc}") from exc


def navigate(game, index, direction):
    """Move within game bounds; each browser session has its own state."""
    return render_position(game, index + direction)


def build_app():
    """Build the UI without starting a server (example: build_app().launch())."""
    empty = {"positions": [chess.STARTING_FEN], "moves": [], "analysis": []}
    _, svg, caption, detail = render_position(empty, 0)
    with gr.Blocks(title="Open Chess Review", analytics_enabled=False) as demo:
        state = gr.State(empty)
        index = gr.State(0)
        gr.Markdown("# ♟ Open Chess Review\nReview your chess game, move by move. Runs locally with Gradio.")
        source = gr.Textbox(label="Game PGN", lines=5, placeholder="1. e4 e5 2. Nf3 Nc6 …")
        with gr.Row():
            example = gr.Button("Example game")
            load = gr.Button("Load / analyze", variant="primary")
        status = gr.Markdown("Paste a PGN or load the example game.")
        with gr.Row():
            with gr.Column():
                board = gr.HTML(svg)
                counter = gr.Markdown(caption)
            with gr.Column():
                info = gr.Markdown(detail)
        with gr.Row():
            start = gr.Button("Go to start")
            previous = gr.Button("← Previous")
            following = gr.Button("Next →")
        outputs = [index, board, counter, info]
        example.click(lambda: EXAMPLE, outputs=source)
        load.click(load_game, inputs=source, outputs=[state, *outputs, status], concurrency_limit=1)
        start.click(lambda game: render_position(game, 0), inputs=state, outputs=outputs)
        previous.click(lambda game, i: navigate(game, i, -1), inputs=[state, index], outputs=outputs)
        following.click(lambda game, i: navigate(game, i, 1), inputs=[state, index], outputs=outputs)
    return demo


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    build_app().queue().launch(server_name="127.0.0.1", share=False)
