"""Texel tuning, step 3: does the tuned engine actually win more?

The tuned engine (engine/ai.py with the numbers from tuned_params.json) plays
the current one at equal time per move, from the same openings as the other
tests, each opening played twice with colours swapped. Best run on PyPy:
    pypy tests/tuning/texel_verify.py [seconds per move] [openings]
"""
import importlib.util
import os
import sys
import time
from multiprocessing import Pool

TUNING_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(TUNING_DIR))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests", "matches"))

import all_heuristics_test as heuristic_test  # openings, game-pair statistics
import engine.ai as current
from engine.tuning import load_params
from ui.chess_logic import Board, piece_moves, get_all_legal_moves, in_check, draw_reason

TEXEL_DIR = os.environ.get("TEXEL_DIR", os.path.join(ROOT, "tests", "results", "texel"))
PARAMS_FILE = os.path.join(TEXEL_DIR, "tuned_params.json")
RESULTS_FILE = os.path.join(TEXEL_DIR, "verify_match.txt")

TIME_PER_MOVE = 1.0
OPENINGS = 200  # each played twice = 400 games

# a second copy of engine/ai.py with its own numbers and tables, for the tuned side
spec = importlib.util.spec_from_file_location("tuned_ai", os.path.join(ROOT, "engine", "ai.py"))
tuned = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tuned)
if os.path.exists(PARAMS_FILE):
    load_params(tuned, PARAMS_FILE)


def play_game(task):
    index, tuned_colour, opening, time_per_move = task
    board = Board()
    for move in opening:
        board.move_piece(*move)

    tuned_engine = tuned.AI()
    tuned_engine.new_game()
    current_engine = current.AI()
    current_engine.new_game()
    winner = None
    for _ in range(heuristic_test.MAX_PLIES):
        if draw_reason(board):
            break
        if len(get_all_legal_moves(board, piece_moves)) == 0:
            if board.turn == "white":
                king_pos = board.white_king
                other = "black"
            else:
                king_pos = board.black_king
                other = "white"
            if in_check(board.grid, board.turn, king_pos):
                winner = other
            break

        if board.turn == tuned_colour:
            move = tuned_engine.choose_move(board, piece_moves, 20, time_limit=time_per_move, keep_table=True)
        else:
            move = current_engine.choose_move(board, piece_moves, 20, time_limit=time_per_move, keep_table=True)
        current.make_move(board, *move)

    if winner is None:
        score = 0.5
    elif winner == tuned_colour:
        score = 1
    else:
        score = 0
    # "full_colour" is the side heuristic_test.match_result scores for: here, the tuned engine
    return {"opening": index, "full_colour": tuned_colour, "score": score}


def run():
    if not os.path.exists(PARAMS_FILE):
        sys.exit(f"No tuned numbers yet: run texel_tune.py first ({PARAMS_FILE})")
    time_per_move = TIME_PER_MOVE
    openings_count = OPENINGS
    if len(sys.argv) > 1:
        time_per_move = float(sys.argv[1])
    if len(sys.argv) > 2:
        openings_count = int(sys.argv[2])

    tasks = []
    openings = heuristic_test.make_openings(openings_count)
    for index in range(openings_count):
        for tuned_colour in ("white", "black"):
            tasks.append((index, tuned_colour, openings[index], time_per_move))
    print(f"Tuned vs current engine: {len(tasks)} games, {time_per_move:g}s per move", flush=True)

    heuristic_test.keep_awake()
    games = []
    started = time.time()
    with Pool(initializer=heuristic_test.ignore_ctrl_c) as pool:
        for count, game in enumerate(pool.imap_unordered(play_game, tasks), start=1):
            games.append(game)
            if count % 20 == 0 or count == len(tasks):
                elapsed = time.time() - started
                left = elapsed / count * (len(tasks) - count)
                print(f"  {count}/{len(tasks)} games | {heuristic_test.duration(elapsed)} so far | "
                      f"about {heuristic_test.duration(left)} left", flush=True)

    result = heuristic_test.match_result(games)
    if result["low"] > 0:
        verdict = "the tuned numbers are stronger"
    elif result["high"] < 0:
        verdict = "the tuned numbers are weaker"
    else:
        verdict = "no clear difference"
    report = "\n".join([
        f"Tuned vs current engine, {time_per_move:g}s per move each, {result['games']} games "
        f"in {(time.time() - started) / 60:.0f} min",
        f"  tuned: {result['wins']} W / {result['draws']} D / {result['losses']} L, score {result['score']:.1%}",
        f"  Elo the tuning adds: {result['elo']:+.0f}   95% range [{result['low']:+.0f}, {result['high']:+.0f}]",
        f"  {verdict}",
    ])
    print("\n" + report, flush=True)
    with open(RESULTS_FILE, "w") as f:
        f.write(report + "\n")


if __name__ == "__main__":
    run()
