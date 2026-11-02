"""Rating test for the web version: how strong is Felis on Google Cloud Run?

The same test as stockfish_rating_test.py (same random openings, same Elo levels,
each opening played twice with colours swapped), but Felis's moves come from the
live website (POST /move) instead of an engine on this PC. Stockfish runs on this
PC with the same time per move. python-chess referees every move.

Each game in progress uses one Cloud Run container, so WORKERS should not be more
than the containers the site can run at once, or moves have to wait for a free one.

Needs: Stockfish (see stockfish_rating_test.py) and an internet connection.

Run from the project root (or click Run in VS Code):
    python tests/matches/web_rating_test.py [seconds per move] [openings per level] [workers]
    e.g. python tests/matches/web_rating_test.py 1 10 3
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from multiprocessing import Pool

import chess
import chess.engine

import all_heuristics_test as heuristic_test  # same folder; also puts the project on sys.path
import stockfish_rating_test as rating_test

from engine.uci import stockfish_path, move_to_uci, play_uci_move
from ui.chess_logic import Board

WEB_URL = os.environ.get("WEB_URL", "https://felis-97966352715.europe-west2.run.app")
TIME_PER_MOVE = 1.0      # seconds, for both sides (or the 1st command line argument)
OPENINGS_PER_LEVEL = 10  # each played twice (or the 2nd command line argument)
WORKERS = 3              # games at once (or the 3rd argument)
MAX_PLIES = 500
RETRIES = 30             # tries per move if the website doesn't answer, or every container is busy


def ask_felis(moves, seconds):
    # POST the game so far to the website, get Felis's move back, e.g. "e7e5"
    body = json.dumps({"moves": moves, "seconds": seconds}).encode()
    request = urllib.request.Request(WEB_URL + "/move", data=body,
                                     headers={"Content-Type": "application/json"})
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read())["move"]
        except (urllib.error.URLError, TimeoutError):
            # includes 429 Too Many Requests: every container is busy, so wait and ask again
            if attempt == RETRIES - 1:
                raise
            time.sleep(10)


def play_game(task):
    elo, opening_index, our_colour, opening, time_per_move = task
    stockfish = chess.engine.SimpleEngine.popen_uci(stockfish_path())
    stockfish.configure({"UCI_LimitStrength": True, "UCI_Elo": elo, "Threads": 1, "Hash": 16})

    board = Board()          # to turn the opening into UCI text
    referee = chess.Board()  # python-chess's board
    moves = []
    for move in opening:
        uci = move_to_uci(board, move)
        play_uci_move(board, uci)
        referee.push_uci(uci)
        moves.append(uci)

    problem = None
    try:
        for _ in range(MAX_PLIES):
            if referee.is_game_over(claim_draw=True):
                break

            if referee.turn == chess.WHITE:
                turn = "white"
            else:
                turn = "black"

            if turn == our_colour:
                uci = ask_felis(moves, time_per_move)
                if uci is None:
                    problem = f"no move from the website in {referee.fen()}"
                    break
                move = chess.Move.from_uci(uci)
            else:
                move = stockfish.play(referee, chess.engine.Limit(time=time_per_move)).move

            # referee: the move must be legal
            if move not in referee.legal_moves:
                problem = f"illegal move {move.uci()} in {referee.fen()}"
                break
            referee.push(move)
            moves.append(move.uci())
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as error:
        problem = f"website error: {error}"
    except chess.engine.EngineError as error:
        problem = f"engine error: {error}"
    finally:
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


def run():
    if stockfish_path() is None:
        sys.exit("Stockfish not found. Put it on the PATH as \"stockfish\", or set "
                 "STOCKFISH_PATH to the Stockfish program (download it from stockfishchess.org).")

    time_per_move = TIME_PER_MOVE
    openings_per_level = OPENINGS_PER_LEVEL
    workers = WORKERS
    if len(sys.argv) > 1:
        time_per_move = float(sys.argv[1])
    if len(sys.argv) > 2:
        openings_per_level = int(sys.argv[2])
    if len(sys.argv) > 3:
        workers = int(sys.argv[3])
    results_file = os.path.join(heuristic_test.RESULTS_DIR, f"web_rating_results_{time_per_move:g}s.txt")

    # check the website answers before starting
    try:
        first = ask_felis([], time_per_move)
    except (urllib.error.URLError, TimeoutError) as error:
        sys.exit(f"Can't reach {WEB_URL}: {error}")
    print(f"Website: {WEB_URL} (answered 1.{first})")
    print(f"Stockfish: {stockfish_path()}")

    heuristic_test.keep_awake()
    tasks = []
    openings = heuristic_test.make_openings(openings_per_level)
    for index, opening in enumerate(openings):
        for elo in rating_test.ELO_LEVELS:
            for our_colour in ("white", "black"):
                tasks.append((elo, index, our_colour, opening, time_per_move))

    print(f"Web Felis vs Stockfish at {rating_test.ELO_LEVELS} Elo: {len(tasks)} games, "
          f"{time_per_move:g}s per move, {workers} at once", flush=True)
    games = []
    started = time.time()
    with Pool(workers, initializer=heuristic_test.ignore_ctrl_c) as pool:
        for count, game in enumerate(pool.imap_unordered(play_game, tasks), start=1):
            games.append(game)
            elapsed = time.time() - started
            left = elapsed / count * (len(tasks) - count)
            print(f"\r  {count:,}/{len(tasks):,} games | {heuristic_test.duration(elapsed)} so far | "
                  f"about {heuristic_test.duration(left)} left   ", end="", flush=True)
    print()

    lines = rating_test.report_lines(games, time_per_move, (time.time() - started) / 60)
    # the first line describes a local engine: say it's the website instead
    lines[0] = (f"Web Felis ({WEB_URL}) vs Stockfish capped to set Elo levels, "
                f"{time_per_move:g}s per move each, {len(games)} games in "
                f"{(time.time() - started) / 60:.0f} min")
    report = "\n".join(lines)
    print("\n" + report)
    with open(results_file, "w") as f:
        f.write(report + "\n")
    print(f"\nSaved to {results_file}")


if __name__ == "__main__":
    run()
