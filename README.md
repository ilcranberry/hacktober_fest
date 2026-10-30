# Open ChessReviewer

An open-source chess game review app powered by Stockfish and local AI.

Paste a PGN, step through the game, and get move classifications with short explanations of verified consequences. Lichess URL import is planned; export the game as PGN for now.

Built during Hacktoberfest Hack Day using Python, Stockfish, Gemma, Ollama, and Gradio.

## Features

- Import games using pasted PGN.
- Review games exported from Chess.com through PGN.
- Navigate an interactive chessboard move by move.
- See Stockfish evaluations and best-move suggestions.
- Get move labels: Best, Excellent, Good, Inaccuracy, Mistake, and Blunder.
- Get explanations automatically when navigating with Next or Previous; revisiting a move uses its cached explanation.
- Read verified reasons such as exposed king diagonals, captures, mate threats, development, and central square coverage.
- See the actual explanation source: Ollama, Template, or Provided.
- Use template-based explanations when Ollama is unavailable.
- Run analysis and explanation generation locally, without paid APIs.

Downloading dependencies and models requires internet access. Analysis and inference run locally.

## How It Works

Stockfish performs all chess analysis. The language model does not analyze positions independently.

The pipeline is:

1. Load and parse the game.
2. Reconstruct positions using python-chess.
3. Analyze positions with Stockfish.
4. Classify moves by the change in estimated win probability.
5. Build explanations from supplied analysis facts.
6. Display the results in Gradio.

Gemma is restricted to approved information. It must not invent tactics or add unsupported reasons. If the model is unavailable or its response fails validation, the explanation module uses a deterministic template.

## Requirements

- Python 3.10+
- Stockfish installed as a separate executable
- Ollama with `gemma3:1b` for AI-assisted explanations
- Python packages from `requirements.txt`

Stockfish binaries and model weights are not included in the repository.

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/ilcranberry/hacktober_fest.git
cd hacktober_fest
```

### 2. Install Python dependencies

On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. Install Stockfish

On macOS with Homebrew:

```bash
brew install stockfish
which stockfish
```

On other platforms, download Stockfish from:
https://stockfishchess.org/download/

Set `STOCKFISH_PATH` to the executable's location.

macOS example:

```bash
export STOCKFISH_PATH=/opt/homebrew/bin/stockfish
```

Windows PowerShell example — replace the path with your installation:

```powershell
$env:STOCKFISH_PATH = "C:\path\to\stockfish.exe"
```

If the variable is unset, the analyzer looks for `stockfish` on the system `PATH`, then for an executable extracted into the repository's `stockfish/` directory. `STOCKFISH_PATH` takes precedence. The local directory and its binaries are ignored by Git.

### 4. Set up Ollama

Install Ollama from:
https://ollama.com/

Start the Ollama application. Alternatively, run its server in a separate terminal:

```bash
ollama serve
```

Download the default model and check that it is installed:

```bash
ollama pull gemma3:1b
ollama list
```

The explanation module uses `gemma3:1b` by default. To select another installed model, set `OLLAMA_MODEL`.

macOS or Linux:

```bash
export OLLAMA_MODEL=gemma3:1b
```

Windows PowerShell:

```powershell
$env:OLLAMA_MODEL = "gemma3:1b"
```

The default local Ollama endpoint is `http://127.0.0.1:11434`.
The app checks `/api/tags` once per analysis to confirm that the selected model is installed.
If Ollama or the selected model is unavailable, templates are used immediately.
After a failed or rejected model response, the remaining explanations for that game use templates.
Uncheck **Use local Ollama model when available** for template-only mode.

For a portable standalone runtime extracted into `models/ollama`, use a separate PowerShell terminal:

```powershell
$env:OLLAMA_MODELS = "$PWD\models\weights"
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_NO_CLOUD = '1'
.\models\ollama\ollama.exe serve
```

Keep that terminal open. In a second terminal, use
`.\models\ollama\ollama.exe pull gemma3:1b` and
`.\models\ollama\ollama.exe list` instead of the global `ollama` command.
Runtime files and weights under `models/` are ignored by Git.

## Run the App

From the repository root, with your virtual environment activated:

```bash
python app.py
```

On Windows, you can also run:

```powershell
.\.venv\Scripts\python.exe app.py
```

Open the local URL printed in the terminal, usually:
http://127.0.0.1:7860

Press `Ctrl+C` to stop the server. You can also run `nikitosik/app.py` directly.

If this workspace already has a `.conda` environment:

```powershell
.\.conda\python.exe -m pip install -r requirements.txt
.\.conda\python.exe app.py
```

## Review a Game

1. Paste the full PGN text, or click **Example game** to fill the input.
2. Click **Analyze game**.
3. Wait for analysis to complete.
4. Use **Previous**, **Next**, and **Go to start** to navigate.
5. Read the classification, evaluation before and after the move, best move, and explanation.

Explanations for inaccuracies, mistakes, blunders, and brilliant moves are generated during analysis.
Other moves are explained automatically when selected with **Next** or **Previous**.
All explanations are cached for the current game. Controls are disabled during generation
and restored after success or failure. If analysis fails, the previous game remains available.
Use **Analysis settings** to set the time per position (default: 0.1 seconds).

### Explanation evidence

`timurchik/facts.py` validates and replays up to six half-moves of Stockfish's actual principal
variation. It records captures, legal recaptures, checks, mate, double attacks, opened king
diagonals, castling pawn cover, development, and central square coverage. Mate defenses in
an alternative line are verified as legal moves. Pinned pieces are not presented as working forks.

Gemma chooses readable wording from fact-derived alternatives. Its answer is validated
against those alternatives; template fallback uses the same evidence. Neither the model
nor the UI evaluates positions or invents strategic reasons. A possible attack is not called
a guaranteed material win, and a short engine line is not treated as proof of a full game result.
When no concrete consequence is verified, the explanation says so.
The card includes the engine continuation so the explanation can be checked.

### Example PGN

```pgn
[Event "Example"]
[White "White"]
[Black "Black"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 d6 4. O-O Bg4
5. d4 Bxf3 6. Qxf3 exd4 7. Qxf7# 1-0
```

Text exported from Chess.com with headers such as `[Event "..."]` and a move list is already PGN and can be pasted directly.

## Configuration

| Setting | Default | Purpose |
| --- | --- | --- |
| `STOCKFISH_PATH` | PATH or local `stockfish/` | Explicit Stockfish executable path |
| `OLLAMA_MODEL` | `gemma3:1b` | Exact installed Ollama model tag |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Local Ollama server URL |
| `OLLAMA_TIMEOUT` | `20` seconds | Timeout for one generation request |
| `time_limit` | `0.1` seconds | Stockfish time per position; UI slider or Python API argument |

Environment variables must be set in the terminal used to launch the app. Restart Gradio after changing them; analyze the game again after starting Ollama or installing a model.

## Stockfish Module

The analysis module can run independently of the UI and Ollama.

Run the example from the repository root:

```bash
python -m timurchik.example
```

Use it from Python:

```python
from timurchik.analyzer import analyze

pgn = """
[Result "0-1"]

1. f3 e5 2. g4 Qh4# 0-1
"""

results = analyze(pgn, time_limit=0.1)
```

To track progress:

```python
def show_progress(done: int, total: int):
    print(f"Analyzed {done}/{total} half-moves")


results = analyze(
    pgn,
    time_limit=0.1,
    progress_callback=show_progress,
)
```

The analyzer accepts PGN text. URL fetching is not connected yet.

### Result Format

`analyze()` returns a `list[dict]`, with one dictionary per half-move.

| Field | Description |
| --- | --- |
| `ply` | Half-move number, starting at 1 |
| `move_san` | Played move in SAN notation |
| `fen_before`, `fen_after` | Positions before and after the move |
| `eval_before`, `eval_after` | Evaluations in centipawns, or `None` for mate scores |
| `mate_before`, `mate_after` | Mate scores, or `None` when no mate is reported |
| `best_move_san` | Stockfish's recommendation before the played move |
| `label` | Move classification |
| `facts` | Structured facts for explanations |
| `explanation` | Explanation text, or `None` |

All evaluations use White's perspective:

- Positive values favor White.
- Negative values favor Black.
- `100` centipawns equals approximately one pawn.
- Positive mate scores favor White; negative scores favor Black.
- A mate score of `0` means checkmate has already occurred. The corresponding board position identifies the winner.

The analyzer populates `facts` with verified board and continuation facts, and initially returns `explanation=None`. The UI fills explanations eagerly or on navigation. The outer result contract is unchanged. The existing `explain_move(move, use_llm=True) -> str` API is preserved; the UI uses `explain_move_with_source` to report the actual source.

## Project Structure

```text
app.py                  # Application entry point
nikitosik/
    app.py              # Gradio interface and game navigation
timurchik/
    __init__.py
    engine.py           # Stockfish connection and position analysis
    labels.py           # Evaluation conversion and move classification
    facts.py            # Verified board facts and engine continuation replay
    analyzer.py         # PGN analysis pipeline
    example.py          # Standalone analysis example
explain/
    prompts.py          # Grounded explanation instructions
    explainer.py        # Ollama integration and template fallback
    reasons.py          # Fact-derived explanation wording
    test_explainer.py
tests/
    test_ui_core.py     # UI/core/explainer integration checks
    test_facts.py       # Tactical fact and explanation regressions
requirements.txt
README.md
LICENSE
```

## Limitations

- Analysis processes the first game in a PGN and its main line only.
- Move classifications are heuristic; thresholds still need calibration.
- Short analysis limits can produce varying evaluations and labels.
- The Brilliant label is outside the current MVP.
- Chess.com games are supported through pasted PGN, not direct URL import.
- Increasing analysis time improves search depth but slows down game review.

## Verification

```powershell
.\.conda\python.exe -m unittest discover -s tests -v
.\.conda\python.exe -m unittest explain.test_explainer -v
.\.conda\python.exe -m timurchik.example
```

Replace `.\.conda\python.exe` with your environment's Python executable as needed.
Unit tests run without Stockfish or Ollama. To include the real Stockfish integration test,
set `$env:RUN_STOCKFISH_TESTS = '1'` before running the first command.
The standalone example requires Stockfish. `python -m explain.explainer` demonstrates
an explanation using Stockfish and Ollama, with template fallback if Ollama is unavailable.

Tests cover automatic explanation generation on navigation, caching, game boundaries,
source reporting, rejected model responses, exposed king diagonals, immediate mate and
its avoidance, queen captures, pinned defenders, castling, promotion, en passant,
and invalid engine continuations.

## License

This project is licensed under GPL-3.0. See [LICENSE](LICENSE).

Stockfish and Gemma are distributed separately under their respective licenses.
