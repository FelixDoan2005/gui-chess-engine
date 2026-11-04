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

Three ways to start the games (the 3rd command line argument):
    random  random 4-move openings, opening book off (the default; the engine on its own)
    start   the normal starting position, opening book off
    book    the normal starting position, opening book on (how people play it)
start vs book at the same time per move measures what the opening book adds.

The time can also be a game clock: "5m" gives each side 5 minutes for the whole
game, and each engine decides its own time per move. Running out of time loses,
unless the other side can't possibly checkmate (then it's a draw).

Run from the project root (or click Run in VS Code):
    python tests/matches/stockfish_rating_test.py [seconds per move, or minutes + m] [openings per level] [random/start/book]
    e.g. python tests/matches/stockfish_rating_test.py 5 25 book
         python tests/matches/stockfish_rating_test.py 10m 25 book
"""
import math
import os
import sys
import time
from multiprocessing import Pool

import chess
import chess.engine

import all_heuristics_test as heuristic_test  # same folder; also puts the project on sys.path

from engine.uci import engine_command, stockfish_path, move_to_uci, play_uci_move
from ui.chess_logic import Board

ELO_LEVELS = [1500, 1750, 2000, 2250]
TIME_PER_MOVE = 1.0      # seconds, for both sides (or the 1st command line argument)
OPENINGS_PER_LEVEL = 50  # each played twice (or the 2nd command line argument)
MAX_PLIES = 500          # safety net; the draw rules end games well before this
MODES = {
    "random": "random openings, no opening book",
    "start": "from the starting position, no opening book",
    "book": "from the starting position, with the opening book",
}

FEN_LETTERS = {"pawn": "p", "knight": "n", "bishop": "b", "rook": "r", "queen": "q", "king": "k"}


def tuned_note():
    if os.environ.get("ENGINE_PARAMS") is not None:
        return ", tuned numbers"
    return ""


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


def time_label(time_per_move, clock_minutes):
    # e.g. "5s per move each" or "10 min clock each"
    if clock_minutes is None:
        return f"{time_per_move:g}s per move each"
    return f"{clock_minutes:g} min clock each"


def game_score(referee, problem, flagged, our_colour):
    # the engine's score for one game: 1 win, 0.5 draw, 0 loss
    if problem is not None:
        return 0  # count it as a loss
    if flagged is not None:
        # out of time loses, unless the other side can't possibly checkmate
        if flagged == "white":
            other = chess.BLACK
        else:
            other = chess.WHITE
        if referee.has_insufficient_material(other):
            return 0.5
        if flagged == our_colour:
            return 0
        return 1

    outcome = referee.outcome(claim_draw=True)
    if outcome is None or outcome.winner is None:
        return 0.5
    if outcome.winner == chess.WHITE:
        winner = "white"
    else:
        winner = "black"
    if winner == our_colour:
        return 1
    return 0


def play_game(task):
    elo, opening_index, our_colour, opening, time_per_move, clock_minutes, use_book = task
    stockfish = chess.engine.SimpleEngine.popen_uci(stockfish_path())
    stockfish.configure({"UCI_LimitStrength": True, "UCI_Elo": elo, "Threads": 1, "Hash": 16})
    engine = chess.engine.SimpleEngine.popen_uci(engine_command())
    engine.configure({"OwnBook": use_book})

    board = Board()          # a copy of the engine's board, updated the way the GUI does it
    referee = chess.Board()  # python-chess's board
    for move in opening:
        uci = move_to_uci(board, move)
        referee.push_uci(uci)
        play_uci_move(board, uci)

    # game clock: seconds left for each side, None = time per move instead
    clocks = None
    if clock_minutes is not None:
        clocks = {"white": clock_minutes * 60, "black": clock_minutes * 60}
    flagged = None  # the colour that ran out of time

    problem = None
    try:
        for _ in range(MAX_PLIES):
            if referee.is_game_over(claim_draw=True):
                break

            if clocks is None:
                limit = chess.engine.Limit(time=time_per_move)
            else:
                limit = chess.engine.Limit(white_clock=clocks["white"], black_clock=clocks["black"])
            started = time.time()
            if board.turn == our_colour:
                played = engine.play(referee, limit)
            else:
                played = stockfish.play(referee, limit)

            # game clock: take off the time used, out of time loses
            if clocks is not None:
                clocks[board.turn] -= time.time() - started
                if clocks[board.turn] <= 0:
                    flagged = board.turn
                    break

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

    score = game_score(referee, problem, flagged, our_colour)
    return {"elo": elo, "opening": opening_index, "full_colour": our_colour,
            "score": score, "problem": problem, "flagged": flagged}


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


def report_lines(games, time_per_move, minutes, mode="random", clock_minutes=None):
    lines = [
        f"Engine (on {os.path.basename(engine_command()[0])}{tuned_note()}) vs Stockfish capped to set Elo levels, "
        f"{time_label(time_per_move, clock_minutes)}, {len(games)} games in {minutes:.0f} min, {MODES[mode]}",
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

    # game clock: who ran out of time
    if clock_minutes is not None:
        felis_flags = 0
        stockfish_flags = 0
        for game in games:
            if game.get("flagged") is None:
                continue
            if game["flagged"] == game["full_colour"]:
                felis_flags += 1
            else:
                stockfish_flags += 1
        lines.append(f"  Ran out of time: Felis {felis_flags}, Stockfish {stockfish_flags}")
    return lines


def run():
    if stockfish_path() is None:
        sys.exit("Stockfish not found. Put it on the PATH as \"stockfish\", or set "
                 "STOCKFISH_PATH to the Stockfish program (download it from stockfishchess.org).")
    print(f"Stockfish: {stockfish_path()}")
    print(f"Engine runs on: {engine_command()[0]}")

    time_per_move = TIME_PER_MOVE
    clock_minutes = None
    openings_per_level = OPENINGS_PER_LEVEL
    if len(sys.argv) > 1:
        # "5" = 5 seconds per move, "5m" = a 5 minute clock each
        if sys.argv[1].endswith("m"):
            clock_minutes = float(sys.argv[1][:-1])
            time_per_move = None
        else:
            time_per_move = float(sys.argv[1])
    if len(sys.argv) > 2:
        openings_per_level = int(sys.argv[2])
    mode = "random"
    if len(sys.argv) > 3:
        mode = sys.argv[3]
    if mode not in MODES:
        sys.exit(f"The 3rd argument must be one of: {', '.join(MODES)}")
    # e.g. ratings/local/book_5s.txt, or book_10min.txt with a clock
    results_dir = os.path.join(heuristic_test.RESULTS_DIR, "ratings", "local")
    if clock_minutes is None:
        name = f"{mode}_{time_per_move:g}s"
    else:
        name = f"{mode}_{clock_minutes:g}min"
    # with tuned numbers (the ENGINE_PARAMS setting, see engine/uci.py), keep the results apart
    if os.environ.get("ENGINE_PARAMS") is not None:
        results_dir = os.path.join(heuristic_test.RESULTS_DIR, "texel")
        name += "_tuned"
        print(f"Engine uses tuned numbers from: {os.environ.get('ENGINE_PARAMS')}")
    results_file = os.path.join(results_dir, name + ".txt")

    # random openings, or every game from the starting position (an empty opening)
    if mode == "random":
        openings = heuristic_test.make_openings(openings_per_level)
    else:
        openings = []
        for _ in range(openings_per_level):
            openings.append([])
    use_book = mode == "book"

    heuristic_test.keep_awake()
    tasks = []
    for index, opening in enumerate(openings):
        for elo in ELO_LEVELS:
            for our_colour in ("white", "black"):
                tasks.append((elo, index, our_colour, opening, time_per_move, clock_minutes, use_book))

    print(f"Engine vs Stockfish at {ELO_LEVELS} Elo: {len(tasks)} games, "
          f"{time_label(time_per_move, clock_minutes)}, {MODES[mode]}", flush=True)
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

    report = "\n".join(report_lines(games, time_per_move, (time.time() - started) / 60, mode, clock_minutes))
    print("\n" + report)
    with open(results_file, "w") as f:
        f.write(report + "\n")
    print(f"\nSaved to {results_file}")


if __name__ == "__main__":
    run()
