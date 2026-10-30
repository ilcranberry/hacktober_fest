"""Gradio game viewer. Run from the repository root with python app.py."""

import html
import io
import math
import re
import sys
from pathlib import Path

# Keep both entry points working: python app.py and python nikitosik/app.py.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import chess
import chess.engine
import chess.pgn
import chess.svg
import gradio as gr

from timurchik.analyzer import analyze
from explain.explainer import explain_move_with_source, ollama_available, ollama_model

EXAMPLE = '[Event "Demo"]\n[White "White"]\n[Black "Black"]\n[Result "0-1"]\n\n1. f3 e5 2. g4 Qh4# 0-1'
LABELS = {
    "best": "Best", "excellent": "Excellent", "good": "Good",
    "inaccuracy": "Inaccuracy", "mistake": "Mistake",
    "blunder": "Blunder", "brilliant": "Brilliant",
}
KEY_LABELS = {"inaccuracy", "mistake", "blunder", "brilliant"}


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
            before_eval = format_evaluation(row, "before")
            after_eval = format_evaluation(row, "after")
            detail += f"Evaluation (White's perspective): **{before_eval} → {after_eval}**\n\n"
            detail += html.escape(row.get("explanation") or "No explanation has been generated yet.")
            if row.get("explanation"):
                source = game.get("explanation_sources", {}).get(row["ply"], "provided")
                source_label = {"ollama": "Ollama", "template": "Template", "provided": "Provided"}[source]
                detail += f"\n\nExplanation source: {source_label}"
            detail += "\n\nBest move: " + html.escape(row.get("best_move_san") or "—")
            line = row.get("facts", {}).get("continuation", [])
            if line:
                detail += "\n\nStockfish line after this move: " + html.escape(" ".join(line))
        else:
            detail += "Load and analyze the game to see evaluations and move labels."
    return index, svg, caption, detail


def format_evaluation(row, phase):
    """Display core scores in pawns, keeping mate scores separate."""
    board = chess.Board(row[f"fen_{phase}"])
    if board.is_checkmate():
        winner = "Black" if board.turn == chess.WHITE else "White"
        return f"Checkmate ({winner} wins)"
    mate = row.get(f"mate_{phase}")
    if mate is not None:
        winner = "White" if mate > 0 else "Black"
        return f"Mate in {abs(mate)} ({winner})"
    score = row.get(f"eval_{phase}")
    return "Unavailable" if score is None else f"{score / 100:+.2f}"


def _explain_row(game, index):
    """Cache one explanation using only the core result; stop retrying failed LLM calls."""
    row = game["analysis"][index - 1]
    if not row.get("explanation"):
        text, source = explain_move_with_source(row, use_llm=game.get("ollama_ready", False))
        row["explanation"] = text
        game.setdefault("explanation_sources", {})[row["ply"]] = source
        if source == "template":
            game["ollama_ready"] = False


def load_game(text, time_limit=0.1, use_llm=True, progress=gr.Progress()):
    """Analyze with Stockfish, then explain only key moves eagerly."""
    try:
        if not math.isfinite(time_limit) or time_limit <= 0:
            raise ValueError("Analysis time must be a positive, finite number.")
        progress(0, desc="Reading PGN")
        game = parse_game(text)

        def report_progress(done, total):
            progress(0.8 * done / total, desc=f"Stockfish: half-move {done} / {total}")

        rows = analyze(text, time_limit=time_limit, progress_callback=report_progress)
        if len(rows) != len(game["moves"]):
            raise ValueError("The analysis returned an incorrect number of half-moves.")
        for i, row in enumerate(rows):
            if (row["fen_before"] != game["positions"][i]
                    or row["fen_after"] != game["positions"][i + 1]
                    or row["move_san"] != game["moves"][i]
                    or row["ply"] != i + 1):
                raise ValueError("The analyzed moves or positions do not match the PGN.")
        game["analysis"] = rows
        progress(0.8, desc="Checking local explanation model")
        game["ollama_ready"] = bool(use_llm and ollama_available())
        key_moves = [row for row in rows if row["label"] in KEY_LABELS]
        for done, row in enumerate(key_moves, start=1):
            progress(0.8 + 0.2 * (done - 1) / len(key_moves), desc=f"Explaining key move {done} / {len(key_moves)}")
            _explain_row(game, row["ply"])
        mode = f"Ollama ({ollama_model()}) with template fallback" if game["ollama_ready"] else "Template explanations"
        status = f"Analysis complete: {len(rows)} half-moves. {mode}. Explanations appear automatically as you navigate."
        progress(1, desc="Done")
        return game, *render_position(game, 0), status
    except FileNotFoundError as exc:
        raise gr.Error(
            "Stockfish was not found. Set STOCKFISH_PATH to the executable, "
            "add it to PATH, or extract it into the project's stockfish folder."
        ) from exc
    except (chess.engine.EngineError, chess.engine.EngineTerminatedError) as exc:
        raise gr.Error(f"Stockfish could not complete the analysis: {exc}") from exc
    except Exception as exc:
        raise gr.Error(f"Could not load the game: {exc}") from exc


def navigate(game, index, direction):
    """Select a move and generate its explanation once before displaying it."""
    new_index = max(0, min(int(index + direction), len(game["moves"])))
    if 0 < new_index <= len(game["analysis"]):
        _explain_row(game, new_index)
    return render_position(game, new_index)


def review_move(game, index, direction):
    """Return the updated session state, board, and automatic explanation together."""
    result = navigate(game, index, direction)
    status = "Starting position." if result[0] == 0 else f"Reviewing half-move {result[0]} / {len(game['moves'])}."
    return game, *result, status


def build_app():
    """Build the UI without starting a server (example: build_app().launch())."""
    empty = {"positions": [chess.STARTING_FEN], "moves": [], "analysis": []}
    _, svg, caption, detail = render_position(empty, 0)
    with gr.Blocks(title="Open Chess Review", analytics_enabled=False) as demo:
        state = gr.State(empty)
        index = gr.State(0)
        gr.Markdown("# ♟ Open Chess Review\nReview your chess game, move by move. Runs locally with Gradio.")
        source = gr.Textbox(label="Game PGN", lines=5, placeholder="1. e4 e5 2. Nf3 Nc6 …")
        with gr.Accordion("Analysis settings", open=False):
            time_limit = gr.Slider(
                minimum=0.05, maximum=0.5, step=0.05, value=0.1,
                label="Seconds per position",
                info="Higher values take longer. Evaluations and labels come from Stockfish.",
            )
            use_llm = gr.Checkbox(
                value=True, label="Use local Ollama model when available",
                info=f"Configured model: {ollama_model()}. Templates are used if the model is unavailable.",
            )
        with gr.Row():
            example = gr.Button("Example game")
            load = gr.Button("Analyze game", variant="primary")
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
        controls = [source, time_limit, use_llm, example, load, start, previous, following]
        example.click(lambda: EXAMPLE, outputs=source)

        def bind_action(button, fn, inputs, result_outputs, api_name, message):
            running = button.click(
                lambda: [gr.update(interactive=False) for _ in controls] + [message],
                outputs=[*controls, status], queue=False, api_visibility="private",
            ).then(
                fn, inputs=inputs, outputs=result_outputs, concurrency_id="review",
                concurrency_limit=1, api_name=api_name,
            )
            running.then(
                lambda: [gr.update(interactive=True) for _ in controls],
                outputs=controls, queue=False, api_visibility="private",
            )
            running.failure(
                lambda: "Could not complete the request. Check the error message and try again.",
                outputs=status, queue=False, api_visibility="private",
            )

        bind_action(load, load_game, [source, time_limit, use_llm], [state, *outputs, status],
                    "analyze_game", "Analyzing the game with Stockfish…")
        bind_action(start, lambda game: review_move(game, 0, 0), [state], [state, *outputs, status],
                    "go_to_start", "Returning to the starting position…")
        bind_action(previous, lambda game, i: review_move(game, i, -1), [state, index], [state, *outputs, status],
                    "previous_move", "Loading the move and its explanation…")
        bind_action(following, lambda game, i: review_move(game, i, 1), [state, index], [state, *outputs, status],
                    "next_move", "Loading the move and its explanation…")
    return demo


if __name__ == "__main__":
    build_app().queue().launch(server_name="127.0.0.1", share=False)
