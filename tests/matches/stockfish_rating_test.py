"""Rating test: how strong is the engine, measured against Stockfish?

Stockfish can be capped to play at a set Elo (UCI_LimitStrength / UCI_Elo).
The engine plays it at a few Elo levels, from the same openings as the other
tests, each opening played twice with colours swapped, both sides getting the
same time per move. The engine's rating is the one that best fits all the
results together (a "performance rating"). Each level's own result is shown
too: Stockfish's capped levels don't always agree with each other, so treat
the rating as approximate, a computer rating rather than a FIDE or online one.

The engine runs exactly as in the game: as its own program (engine/uci.py),
on PyPy if it's found (see engine_command in engine/uci.py). python-chess
referees the games: every move must be legal, and a copy of the engine's own
board must match after each move.

Needs: pip install chess, and Stockfish (stockfishchess.org): either on the
PATH as "stockfish", or with the STOCKFISH_PATH setting pointing at it.

Run from the project root (or click Run in VS Code):
    python tests/matches/stockfish_rating_test.py [seconds per move] [openings per level]
    e.g. python tests/matches/stockfish_rating_test.py 5 25
"""
import math
import os
import shutil
import sys
import time
from multiprocessing import Pool

import chess
import chess.engine

import all_heuristics_test as heuristic_test  # same folder; also puts the project on sys.path

from engine.uci import engine_command, move_to_uci, play_uci_move
from ui.chess_logic import Board

ELO_LEVELS = [1500, 1750, 2000, 2250]
TIME_PER_MOVE = 1.0      # seconds, for both sides (or the 1st command line argument)
OPENINGS_PER_LEVEL = 50  # each played twice (or the 2nd command line argument)
MAX_PLIES = 500          # safety net; the draw rules end games well before this

FEN_LETTERS = {"pawn": "p", "knight": "n", "bishop": "b", "rook": "r", "queen": "q", "king": "k"}


def stockfish_path():
    # the STOCKFISH_PATH setting if it's set, otherwise "stockfish" on the PATH
    path = os.environ.get("STOCKFISH_PATH")
    if path is not None and os.path.exists(path):
        return path
    return shutil.which("stockfish")


def board_fen(board):
    # the piece placement part of a FEN, to compare with the referee's board
    rows = []
    for row in board.grid:
        text = ""
        empty = 0
        for piece in row:
            if piece is None:
                empty += 1
            else:
                if empty > 0:
                    text += str(empty)
                    empty = 0
                colour, kind = piece.split("_")
                letter = FEN_LETTERS[kind]
                if colour == "white":
                    letter = letter.upper()
                text += letter
        if empty > 0:
            text += str(empty)
        rows.append(text)
    return "/".join(rows)


def play_game(task):
    elo, opening_index, our_colour, opening, time_per_move = task
    stockfish = chess.engine.SimpleEngine.popen_uci(stockfish_path())
    stockfish.configure({"UCI_LimitStrength": True, "UCI_Elo": elo, "Threads": 1, "Hash": 16})
    engine = chess.engine.SimpleEngine.popen_uci(engine_command())

    board = Board()          # a copy of the engine's board, updated the way the GUI does it
    referee = chess.Board()  # python-chess's board
    for move in opening:
        uci = move_to_uci(board, move)
        referee.push_uci(uci)
        play_uci_move(board, uci)

    problem = None
    try:
        for _ in range(MAX_PLIES):
            if referee.is_game_over(claim_draw=True):
                break

            if board.turn == our_colour:
                played = engine.play(referee, chess.engine.Limit(time=time_per_move))
            else:
                played = stockfish.play(referee, chess.engine.Limit(time=time_per_move))

            # referee: the move must be legal
            if played.move not in referee.legal_moves:
                problem = f"illegal move {played.move.uci()} in {referee.fen()}"
                break
            referee.push(played.move)
            play_uci_move(board, played.move.uci())

            # referee: both boards must still show the same position
            if board_fen(board) != referee.board_fen():
                problem = f"boards differ after {played.move.uci()}: {referee.fen()}"
                break
    except chess.engine.EngineError as error:
        problem = f"engine error: {error}"
    finally:
        engine.quit()
        stockfish.quit()

    outcome = referee.outcome(claim_draw=True)
    if problem is not None:
        score = 0  # count it as a loss
    elif outcome is None or outcome.winner is None:
        score = 0.5
    else:
        if outcome.winner == chess.WHITE:
            winner = "white"
        else:
            winner = "black"
        if winner == our_colour:
            score = 1
        else:
            score = 0

    return {"elo": elo, "opening": opening_index, "full_colour": our_colour,
            "score": score, "problem": problem}


def expected_score(rating, opponent):
    return 1 / (1 + 10 ** ((opponent - rating) / 400))


def performance_rating(games, points):
    # the rating whose expected total score against these opponents is points
    low = 0
    high = 4000
    for _ in range(60):
        middle = (low + high) / 2
        expected = 0
        for game in games:
            expected += expected_score(middle, game["elo"])
        if expected < points:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def points_spread(games):
    # how uncertain the total points are, from each opening's pair of games
    pairs = {}
    for game in games:
        key = (game["elo"], game["opening"])
        if key not in pairs:
            pairs[key] = []
        pairs[key].append(game["score"])

    variance = 0
    for elo in ELO_LEVELS:
        pair_points = []
        for key, scores in pairs.items():
            if key[0] == elo and len(scores) == 2:
                pair_points.append(scores[0] + scores[1])
        if len(pair_points) == 0:
            continue
        mean = sum(pair_points) / len(pair_points)
        for points in pair_points:
            variance += (points - mean) ** 2
    return math.sqrt(variance)


def report_lines(games, time_per_move, minutes):
    lines = [
        f"Engine (on {os.path.basename(engine_command()[0])}) vs Stockfish capped to set Elo levels, "
        f"{time_per_move:g}s per move each, {len(games)} games in {minutes:.0f} min",
        "",
        f"  {'Stockfish Elo':>13}   {'W /  D /  L':>11}   {'score':>6}   rating it implies on its own",
    ]
    for elo in ELO_LEVELS:
        wins = draws = losses = 0
        for game in games:
            if game["elo"] == elo:
                if game["score"] == 1:
                    wins += 1
                elif game["score"] == 0:
                    losses += 1
                else:
                    draws += 1
        total = wins + draws + losses
        if total > 0:
            score = (wins + draws / 2) / total
            implied = elo + heuristic_test.elo(score)
            lines.append(f"  {elo:>13}   {wins:>3} /{draws:>3} /{losses:>3}   {score:6.1%}   {implied:.0f}")

    points = 0
    for game in games:
        points += game["score"]
    spread = 1.96 * points_spread(games)
    rating = performance_rating(games, points)
    low = performance_rating(games, max(points - spread, 0.5))
    high = performance_rating(games, min(points + spread, len(games) - 0.5))
    lines.append("")
    lines.append(f"  Rating (best fit to all levels): about {rating:.0f}   "
                 f"95% range from the games alone [{low:.0f}, {high:.0f}]")

    problems = []
    for game in games:
        if game["problem"] is not None:
            problems.append(game["problem"])
    lines.append(f"  Referee: {len(problems)} games with an illegal move, mismatched boards or an engine error")
    for problem in problems[:5]:
        lines.append(f"    {problem}")
    return lines


def run():
    if stockfish_path() is None:
        sys.exit("Stockfish not found. Put it on the PATH as \"stockfish\", or set "
                 "STOCKFISH_PATH to the Stockfish program (download it from stockfishchess.org).")
    print(f"Stockfish: {stockfish_path()}")
    print(f"Engine runs on: {engine_command()[0]}")

    time_per_move = TIME_PER_MOVE
    openings_per_level = OPENINGS_PER_LEVEL
    if len(sys.argv) > 1:
        time_per_move = float(sys.argv[1])
    if len(sys.argv) > 2:
        openings_per_level = int(sys.argv[2])
    results_file = os.path.join(heuristic_test.RESULTS_DIR, f"stockfish_rating_results_{time_per_move:g}s.txt")

    heuristic_test.keep_awake()
    tasks = []
    openings = heuristic_test.make_openings(openings_per_level)
    for index, opening in enumerate(openings):
        for elo in ELO_LEVELS:
            for our_colour in ("white", "black"):
                tasks.append((elo, index, our_colour, opening, time_per_move))

    print(f"Engine vs Stockfish at {ELO_LEVELS} Elo: {len(tasks)} games, "
          f"{time_per_move:g}s per move", flush=True)
    games = []
    started = time.time()
    with Pool(initializer=heuristic_test.ignore_ctrl_c) as pool:
        for count, game in enumerate(pool.imap_unordered(play_game, tasks), start=1):
            games.append(game)
            elapsed = time.time() - started
            left = elapsed / count * (len(tasks) - count)
            print(f"\r  {count:,}/{len(tasks):,} games | {heuristic_test.duration(elapsed)} so far | "
                  f"about {heuristic_test.duration(left)} left   ", end="", flush=True)
    print()

    report = "\n".join(report_lines(games, time_per_move, (time.time() - started) / 60))
    print("\n" + report)
    with open(results_file, "w") as f:
        f.write(report + "\n")
    print(f"\nSaved to {results_file}")


if __name__ == "__main__":
    run()
