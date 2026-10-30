# Open ChessReviewer

A local, open-source chess game review app powered by Stockfish and Gemma.

Paste a Lichess game URL or PGN, step through the game, and review move classifications with short explanations based on verified chess facts.

Built during Hacktoberfest Hack Day.

## Features

- Import games from Lichess URLs or pasted PGN.
- Review Chess.com games through exported PGN.
- Navigate the board move by move.
- See evaluations before and after each move.
- View Stockfish's recommended move and continuation.
- Get move labels: Best, Excellent, Good, Inaccuracy, Mistake, and Blunder.
- Read explanations generated from verified analysis facts.
- Use local Gemma through Ollama, with automatic template fallback.
- Adjust Stockfish analysis time in the UI.

Analysis and explanation generation run locally. No paid APIs or subscriptions are required.

Internet access is needed to download dependencies and models, and to import games from Lichess.

## How It Works

Stockfish performs all position evaluation and best-move analysis.

Application code converts evaluation changes into move classifications. python-chess reconstructs positions and verifies facts such as captures, checks, checkmate, and legal continuations.

Gemma selects wording from explanations built using these verified facts. Its response is validated against the approved alternatives. It cannot add unsupported tactics or analyze positions independently.

If Ollama is unavailable or its response fails validation, the app uses a template based on the same facts.

Explanations for important mistakes are prepared during analysis. Other moves are explained when selected. Explanations are cached for the current game.

## Requirements

- Python 3.10+
- Stockfish installed separately
- Python dependencies from `requirements.txt`
- Ollama with `gemma4:e4b` for AI-assisted explanations

Ollama is optional: the app can use template explanations.

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

Set `STOCKFISH_PATH` to the path printed by `which stockfish`.

For example, on an Apple Silicon Mac:

```bash
export STOCKFISH_PATH=/opt/homebrew/bin/stockfish
```

For other platforms, download Stockfish from:
https://stockfishchess.org/download/

Windows PowerShell example:

```powershell
$env:STOCKFISH_PATH = "C:\path\to\stockfish.exe"
```

Replace the example path with your actual executable path.

The app searches for Stockfish in this order:

1. `STOCKFISH_PATH`
2. The system `PATH`
3. The repository's local `stockfish/` directory

### 4. Set up Ollama

Install Ollama from:
https://ollama.com/

Start the Ollama application. Alternatively, start its server in a separate terminal:

```bash
ollama serve
```

Download the default model:

```bash
ollama pull gemma4:e4b
ollama list
```

The configured model must match an installed model tag exactly. Requests use `think: false` and `stream: false` for direct structured responses.
For lower memory use, an installed `gemma3:1b` can still be selected with `OLLAMA_MODEL`.

## Run the App

From the repository root, with the virtual environment activated:

```bash
python app.py
```

On Windows:

```powershell
.\.venv\Scripts\python.exe app.py
```

Open the local URL printed in the terminal, usually:
http://127.0.0.1:7860

Press `Ctrl+C` to stop the server.

## Usage

1. Paste a Lichess game URL or the full PGN text.
2. Optionally adjust **Analysis settings**.
3. Click **Analyze game**.
4. Wait for analysis to complete.
5. Use **Previous**, **Next**, and **Go to start** to navigate.
6. Review the evaluation, move label, recommended move, and explanation.

The explanation card shows whether its text came from Ollama or a template.

### Lichess Links

The importer supports:

- Standard game links with an 8-character game ID.
- Player links with a 12-character ID.
- Links containing `/game/`.
- `/white` or `/black` orientation suffixes.
- Move fragments such as `#12`.

Study and profile links are not supported. Public game export does not require a Lichess API token.

### PGN Input

Paste the complete PGN, including headers and moves:

```pgn
[Event "Example"]
[White "White"]
[Black "Black"]
[Result "0-1"]

1. f3 e5 2. g4 Qh4# 0-1
```

PGN exported from Chess.com can be pasted directly. Direct Chess.com URL import is not supported.

## Configuration

| Setting | Default | Purpose |
| --- | --- | --- |
| `STOCKFISH_PATH` | Automatic discovery | Path to the Stockfish executable |
| `OLLAMA_MODEL` | `gemma4:e4b` | Installed Ollama model tag |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama server address |
| `OLLAMA_TIMEOUT` | `60` seconds | Timeout for one generation request, including cold model loading |
| `time_limit` | `0.1` seconds | Stockfish analysis time per position |

Set environment variables in the terminal used to launch the app.

For example, on macOS or Linux:

```bash
export OLLAMA_MODEL=gemma4:e4b
export OLLAMA_HOST=http://127.0.0.1:11434
export OLLAMA_TIMEOUT=60
```

Restart the app after changing its environment settings.

Increasing Stockfish analysis time can improve search quality but makes game review slower.

## Project Structure

```text
app.py                  # Application entry point
nikitosik/
    app.py              # Gradio UI, game loading, and navigation
timurchik/
    __init__.py
    engine.py           # Stockfish connection and position analysis
    labels.py           # Move classification
    facts.py            # Verified board and continuation facts
    analyzer.py         # Full-game PGN analysis
    example.py          # Standalone analysis example
explain/
    prompts.py          # Instructions for grounded explanations
    explainer.py        # Ollama integration and template fallback
    reasons.py          # Fact-based explanation wording
    test_explainer.py
tests/
    test_ui_core.py     # Input and module integration tests
    test_facts.py       # Fact and explanation tests
requirements.txt
README.md
LICENSE
```

## Stockfish Module

Run the standalone example:

```bash
python -m timurchik.example
```

Use the analyzer from Python:

```python
from timurchik.analyzer import analyze

pgn = """
[Result "0-1"]

1. f3 e5 2. g4 Qh4# 0-1
"""

results = analyze(pgn, time_limit=0.1)
```

The analyzer accepts PGN text. The application resolves Lichess URLs before passing the resulting PGN to both the board parser and analyzer.

An optional callback reports progress:

```python
def show_progress(done: int, total: int):
    print(f"Analyzed {done}/{total} half-moves")


results = analyze(
    pgn,
    time_limit=0.1,
    progress_callback=show_progress,
)
```

### Result Format

`analyze()` returns a `list[dict]`, with one dictionary per half-move.

| Field | Description |
| --- | --- |
| `ply` | Half-move number, starting at 1 |
| `move_san` | Played move in SAN notation |
| `fen_before`, `fen_after` | Positions before and after the move |
| `eval_before`, `eval_after` | Evaluations in centipawns, or `None` for mate scores |
| `mate_before`, `mate_after` | Mate scores, or `None` |
| `best_move_san` | Stockfish's recommendation before the played move |
| `label` | Move classification |
| `facts` | Verified board and continuation facts |
| `explanation` | Explanation text, or `None` |

All evaluations use White's perspective:

- Positive values favor White.
- Negative values favor Black.
- `100` centipawns equals approximately one pawn.
- Positive mate scores favor White; negative scores favor Black.
- A mate score of `0` means checkmate has already occurred. The board position identifies the winner.

The analyzer populates `facts` and initially returns `explanation=None`. The UI fills explanations during analysis or navigation.

## Troubleshooting

### Stockfish Was Not Found

Check that Stockfish is installed and `STOCKFISH_PATH` points to the executable, not its containing directory.

On macOS or Linux, check automatic discovery with:

```bash
which stockfish
```

### HTTPS Certificate Errors on macOS

If importing a Lichess game fails with:

```text
CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate
```

and Python was installed from python.org, run:

```bash
open "/Applications/Python 3.13/Install Certificates.command"
```

Replace `3.13` with your installed Python version.

Wait for the script to finish successfully, then restart the app. This configures the local Python installation and does not require changing `requirements.txt`.

### Template Explanations Instead of Ollama

Check that:

- Ollama is running.
- `ollama list` includes the configured model.
- **Use local Ollama model when available** is enabled.

Analyze the game again after starting Ollama or installing the model.

The app uses templates if a model request fails or produces an unapproved response.

### Lichess Import Failed

Check that the link points to an accessible game.

If Lichess returns a rate-limit error, wait before retrying. You can also export the game as PGN and paste it directly.

## Limitations

- Only the first game in a PGN and its main line are analyzed.
- Move classifications are heuristic and their thresholds need calibration.
- Short analysis limits can produce varying evaluations and labels.
- The Brilliant label is outside the current MVP.
- Direct Chess.com URL import is not supported.
- Engine continuations are possible lines, not a record of the moves actually played.

## Tests

Run unit tests from the repository root:

```bash
python -m unittest discover -s tests -v
python -m unittest explain.test_explainer -v
```

Unit tests mock external services. The real Stockfish integration test is optional and requires `RUN_STOCKFISH_TESTS=1`.

On macOS or Linux:

```bash
RUN_STOCKFISH_TESTS=1 python -m unittest discover -s tests -v
```

On Windows PowerShell:

```powershell
$env:RUN_STOCKFISH_TESTS = "1"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## License

This project is licensed under GPL-3.0. See [LICENSE](LICENSE).

Stockfish and Gemma are distributed separately under their respective licenses.
