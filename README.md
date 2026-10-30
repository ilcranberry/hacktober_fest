# Open Chess Review

A local interface for reviewing chess games. Python 3.10+; GPL-3.0.

## Run in Windows PowerShell

This workspace already has a `.conda` environment:

```powershell
.\.conda\python.exe -m pip install -r requirements.txt
.\.conda\python.exe app.py
```

Open http://127.0.0.1:7860. Press Ctrl+C to stop the server.
You can also run `nikitosik/app.py`.

On another machine, create a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

## Current features

PGN loading and validation, an example game, an SVG chessboard, previous/next
and return-to-start navigation, separate game state for each user, and a progress indicator.
Without the core module, the app runs in viewing mode without fabricated evaluations.
Lichess, Stockfish, and Ollama integration is not implemented yet.

## Team integration

- Core: `core.engine.analyze(pgn: str) -> list[dict]` follows the agreed data contract;
  handles PGN/Lichess, Stockfish, move classification, and structured facts. The UI
  automatically calls the function when the module is available. Engine errors are shown to the user.
- Explain: prompts based only on supplied facts, Ollama/Gemma, and a template fallback;
  coordinate with core to populate `explanation` for key moves. Generate explanations in English.
- UI: `nikitosik/app.py`, the chessboard, navigation, loading, and analysis result integration.

The data contract is unchanged. The UI reads `fen_before`, `fen_after`, `label`,
`best_move_san`, and `explanation`; it does not compute evaluations or tactics.
When `explanation=None`, the UI displays a message that no explanation has been generated yet.
Do not commit Stockfish binaries, models, or secrets to Git.

Four-hour plan: spend the first 30 minutes on interfaces and a shared working app;
the next 90 minutes on modules; one hour on integration; and the final hour on testing and demo rehearsal.
