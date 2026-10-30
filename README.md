# Open ChessReviewer

An open-source chess game review app powered by Stockfish and local AI.

Paste a Lichess game URL or a PGN, step through the game, and get move classifications with short, plain-language explanations.

Built during Hacktoberfest Hack Day using Python, Stockfish, Gemma, Ollama, and Gradio.

## Features

- Import games using a Lichess URL or pasted PGN.
- Review games exported from Chess.com through PGN.
- Navigate an interactive chessboard move by move.
- See Stockfish evaluations and best-move suggestions.
- Get move labels: Best, Excellent, Good, Inaccuracy, Mistake, and Blunder.
- Read short explanations based on verified analysis.
- Use template-based explanations when Ollama is unavailable.
- Run analysis and explanation generation locally, without paid APIs.

Downloading dependencies and models, and importing games from Lichess, require internet access.

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

If the variable is unset, the analyzer looks for `stockfish` on the system `PATH`.

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

The local Ollama endpoint is `http://localhost:11434`.

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

Press `Ctrl+C` to stop the server.

## Review a Game

1. Paste a Lichess game URL or the full PGN text.
2. Click **Load / analyze**.
3. Wait for analysis to complete.
4. Use **Previous**, **Next**, and **Go to start** to navigate.
5. Review the classification, best-move suggestion, and explanation for each move.

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
| `STOCKFISH_PATH` | `stockfish` | Stockfish executable path |
| `OLLAMA_MODEL` | `gemma3:1b` | Installed Ollama model tag |
| `time_limit` | `0.1` seconds | Stockfish analysis time per position; Python API argument |

Environment variables must be set in the terminal used to launch the app.

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

The analyzer accepts PGN text, not a URL. URL fetching is handled by the application input layer.

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

The analyzer initially returns `facts={}` and `explanation=None`. These fields are populated by the other application modules.

## Project Structure

```text
app.py                  # Application entry point
nikitosik/
    app.py              # Gradio interface and game navigation
timurchik/
    __init__.py
    engine.py           # Stockfish connection and position analysis
    labels.py           # Evaluation conversion and move classification
    analyzer.py         # PGN analysis pipeline
    example.py          # Standalone analysis example
explain/
    prompts.py          # Grounded explanation instructions
    explainer.py        # Ollama integration and template fallback
    test_explainer.py
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

## License

This project is licensed under GPL-3.0. See [LICENSE](LICENSE).

Stockfish and Gemma are distributed separately under their respective licenses.