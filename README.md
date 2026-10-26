# Chess Engine & GUI

A complete chess game with a built-in chess engine, written in Python with a Pygame GUI. The engine uses the same core techniques as real chess engines, runs as a standard **UCI engine** (on PyPy when available), and every change to it was measured with engine-vs-engine matches before being kept. **Rated about 1900 Elo against Stockfish at 10 seconds per move.**

## Features

- **All FIDE rules**: castling, en passant, promotion (with a piece picker), check, checkmate, stalemate, and draws by threefold repetition, the 50-move rule and insufficient material
- **Three modes**:
  - **Player vs Player**
  - **Player vs Engine**: play as White or Black
  - **Engine vs Stockfish**: pick your engine's level and Stockfish's strength (1400 Elo up to full strength), then watch them play
- **Difficulty**: levels 1–5 (search depth 1 to 5), or **Max**, where the engine searches as deep as its time allows
- **Time per move**: 1, 5, 10, 15 or 30 seconds, a custom number of seconds, or unlimited
- **Last move highlighted**: the squares the last move went from and to glow green
- **Engine as a separate program**: the GUI talks to the engine through the UCI protocol (the one Stockfish uses), so the engine can run on PyPy, up to 3.2× faster, while the GUI stays on normal Python

## The engine

**Search**
- Negamax with alpha-beta pruning
- Iterative deepening, with a transposition table kept between moves
- Move ordering: transposition table move, MVV-LVA captures, killer moves
- Quiescence search (with delta pruning) to avoid the horizon effect
- Check extensions, principal variation search (PVS) and late move reductions
- Time limit: plays the best move from the deepest search completed

**Evaluation**: a tapered evaluation (blending middlegame and endgame values as pieces come off) of 8 heuristics, with every value taken from established engines and literature rather than invented. It started with 13; testing showed 5 of them added nothing, so they were removed, making the engine 16% faster at the same strength.

| Heuristic | Source |
|---|---|
| Piece-square tables, king endgame table | Tomasz Michniewski (Simplified Evaluation Function) |
| Mobility, pawn structure, king pawn shelter, king attack, tapered phase | Fruit 2.1 |
| Bishop pair | Larry Kaufman |
| Mop-up (endgames) | Chess 4.x (Slate & Atkin) |

## How changes were tested

Every engine change was checked with engine-vs-engine matches: both versions play the same openings, each played twice with colours swapped. Results are Elo with 95% confidence intervals from the paired games, the same statistics used by Stockfish's testing framework (Fishtest).

| Change | Test | Result |
|---|---|---|
| Move ordering, transposition table, iterative deepening | 200 games + timing | 2.4× faster at depth 5, no loss in strength |
| Quiescence search | 200 games vs the old engine searching one move deeper | **+288 Elo** [+236, +353], using 44% less time |
| In-check quiescence + check extension | 200 games, same depth | **+149 Elo** [+107, +196] |
| Captures-only legality checks + delta pruning | 200 games + timing | 1.4–1.6× faster, same strength |
| Principal variation search | 200 games + timing | 5–13% faster, same moves |
| Late move reductions | 800 games at 1 second per move | about +19 Elo, 2.25× faster at depth 5 |
| Null-move pruning | 400 games (same depth and same time) | no gain at this depth, so **removed** |
| Removing 5 of the 13 heuristics | per-heuristic test + 1,000-game simplification test | same strength, **16% faster** |
| Running on PyPy | timing on 36 searches | up to 3.2× faster, identical moves |
| Keeping the transposition table between moves | timing + 100 games | 1.3× faster, no loss in strength |

**Rating against Stockfish 19**, capped at 1500, 1750, 2000 and 2250 Elo:

| Time per move | Games | Rating (best fit) |
|---|---|---|
| 1 second | 400 | about 1725 |
| 5 seconds | 200 | about 1920 |
| 10 seconds | 200 | about 1970 |

Stockfish's capped levels don't fully agree with each other, so treat these as approximate (about ±100). The engine gains much more from extra thinking time than capped Stockfish does, so longer time controls favour it. python-chess refereed every move of all 1,200 games: **0 illegal moves**.

## Getting started

Requires Python 3.11 (other recent versions should work).

```bash
git clone https://github.com/FelixDoan2005/gui-chess-engine.git
cd gui-chess-engine
pip install -r requirements.txt
python main.py
```

**Optional(recommended): run the engine about 3× faster with [PyPy](https://pypy.org).** If `pypy3` or `pypy` is on your PATH, the game uses it automatically; otherwise set `PYPY_PATH` to the PyPy executable. Without PyPy, it runs on normal Python.

**For Engine vs Stockfish**, download [Stockfish](https://stockfishchess.org) and either put it on your PATH as `stockfish`, or set `STOCKFISH_PATH` to it.

## Running the tests

```bash
pip install -r requirements-dev.txt
python -m pytest                                    # 43 unit tests: rules, search, evaluation and UCI
python tests/matches/all_heuristics_test.py         # how much each heuristic adds (runs for hours, on all CPU cores)
python tests/matches/simplification_test.py         # checks removing heuristics doesn't cost strength
python tests/matches/stockfish_rating_test.py 10 25 # rating vs Stockfish at 10s per move (needs Stockfish, as above)
```

Every result above is saved in `tests/results/`.

## Project structure

```
main.py                 game loop and screens (talks to the engines through UCI)
engine/uci.py           the UCI engine program
engine/ai.py            search and evaluation
ui/chess_logic.py       board, move generation and rules
ui/renderer.py          drawing the board and menus
tests/                  unit tests (pytest)
tests/matches/          engine-vs-engine tests
tests/results/          every test result
```
