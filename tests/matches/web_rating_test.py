"""Rating test for the web version: how strong is Felis on Google Cloud Run?

The same test as stockfish_rating_test.py (same random openings, same Elo levels,
each opening played twice with colours swapped), but Felis's moves come from the
live website (POST /move) instead of an engine on this PC. Stockfish runs on this
PC with the same time. python-chess referees every move.

The time can be seconds per move ("3") or a game clock ("5m" = 5 minutes each).
With a clock, Felis's time includes the trip to the website and back, like for
someone playing it in the browser.

Two ways to start the games (the 4th argument):
    random  random 4-move openings (the default)
    book    the normal starting position (the site's opening book is always on)

Each game in progress uses one Cloud Run container, so WORKERS should not be more
than the containers the sites can run at once, or moves have to wait for a free one.
To spread the games over several copies of the site, give WEB_URL several
addresses separated by commas.

Needs: Stockfish (see stockfish_rating_test.py) and an internet connection.

Run from the project root (or click Run in VS Code):
    python tests/matches/web_rating_test.py [seconds per move, or minutes + m] [openings per level] [workers] [random/book]
    e.g. python tests/matches/web_rating_test.py 1 10 3
         python tests/matches/web_rating_test.py 5m 15 20 book
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
MODES = {
    "random": "random openings",
    "book": "from the starting position, with the opening book",
}


def ask_felis(url, moves, seconds, clocks=None):
    # POST the game so far to the website, get Felis's move back, e.g. "e7e5",
    # and how long the answer took (the try that worked, not the waits before it)
    request_body = {"moves": moves, "seconds": seconds}
    if clocks is not None:
        request_body["white_clock"] = clocks["white"]
        request_body["black_clock"] = clocks["black"]
    body = json.dumps(request_body).encode()
    request = urllib.request.Request(url + "/move", data=body,
                                     headers={"Content-Type": "application/json"})
    for attempt in range(RETRIES):
        try:
            started = time.time()
            with urllib.request.urlopen(request, timeout=60) as response:
                move = json.loads(response.read())["move"]
            return move, time.time() - started
        except (urllib.error.URLError, TimeoutError):
            # includes 429 Too Many Requests: every container is busy, so wait and ask again
            if attempt == RETRIES - 1:
                raise
            time.sleep(10)


def play_game(task):
    elo, opening_index, our_colour, opening, time_per_move, clock_minutes, url = task
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

            if referee.turn == chess.WHITE:
                turn = "white"
            else:
                turn = "black"

            if turn == our_colour:
                uci, used = ask_felis(url, moves, time_per_move, clocks)
                if uci is None:
                    problem = f"no move from the website in {referee.fen()}"
                    break
                move = chess.Move.from_uci(uci)
            else:
                if clocks is None:
                    limit = chess.engine.Limit(time=time_per_move)
                else:
                    limit = chess.engine.Limit(white_clock=clocks["white"], black_clock=clocks["black"])
                started = time.time()
                move = stockfish.play(referee, limit).move
                used = time.time() - started

            # game clock: take off the time used, out of time loses
            if clocks is not None:
                clocks[turn] -= used
                if clocks[turn] <= 0:
                    flagged = turn
                    break

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

    score = rating_test.game_score(referee, problem, flagged, our_colour)
    return {"elo": elo, "opening": opening_index, "full_colour": our_colour,
            "score": score, "problem": problem, "flagged": flagged}


def run():
    if stockfish_path() is None:
        sys.exit("Stockfish not found. Put it on the PATH as \"stockfish\", or set "
                 "STOCKFISH_PATH to the Stockfish program (download it from stockfishchess.org).")

    time_per_move = TIME_PER_MOVE
    clock_minutes = None
    openings_per_level = OPENINGS_PER_LEVEL
    workers = WORKERS
    mode = "random"
    if len(sys.argv) > 1:
        # "5" = 5 seconds per move, "5m" = a 5 minute clock each
        if sys.argv[1].endswith("m"):
            clock_minutes = float(sys.argv[1][:-1])
            time_per_move = 1  # not used with a clock
        else:
            time_per_move = float(sys.argv[1])
    if len(sys.argv) > 2:
        openings_per_level = int(sys.argv[2])
    if len(sys.argv) > 3:
        workers = int(sys.argv[3])
    if len(sys.argv) > 4:
        mode = sys.argv[4]
    if mode not in MODES:
        sys.exit(f"The 4th argument must be one of: {', '.join(MODES)}")

    # e.g. ratings/web/random_3s.txt, or book_5min.txt with a clock
    if clock_minutes is None:
        name = f"{mode}_{time_per_move:g}s"
    else:
        name = f"{mode}_{clock_minutes:g}min"
    results_file = os.path.join(heuristic_test.RESULTS_DIR, "ratings", "web", name + ".txt")

    # one or more copies of the site, separated by commas
    urls = []
    for url in WEB_URL.split(","):
        if url.strip() != "":
            urls.append(url.strip().rstrip("/"))

    # check every site answers before starting
    for url in urls:
        try:
            first, used = ask_felis(url, [], 1)
        except (urllib.error.URLError, TimeoutError) as error:
            sys.exit(f"Can't reach {url}: {error}")
        print(f"Website: {url} (answered 1.{first})")
    print(f"Stockfish: {stockfish_path()}")

    heuristic_test.keep_awake()
    if mode == "random":
        openings = heuristic_test.make_openings(openings_per_level)
    else:
        openings = []
        for _ in range(openings_per_level):
            openings.append([])
    tasks = []
    for index, opening in enumerate(openings):
        for elo in rating_test.ELO_LEVELS:
            for our_colour in ("white", "black"):
                # spread the games evenly over the sites
                url = urls[len(tasks) % len(urls)]
                tasks.append((elo, index, our_colour, opening, time_per_move, clock_minutes, url))

    label = rating_test.time_label(time_per_move, clock_minutes)
    print(f"Web Felis vs Stockfish at {rating_test.ELO_LEVELS} Elo: {len(tasks)} games, "
          f"{label}, {MODES[mode]}, {workers} at once on {len(urls)} site(s)", flush=True)
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

    minutes = (time.time() - started) / 60
    lines = rating_test.report_lines(games, time_per_move, minutes, clock_minutes=clock_minutes)
    # the first line describes a local engine: say it's the website instead
    if len(urls) == 1:
        sites = urls[0]
    else:
        sites = f"split across {len(urls)} copies of the site: {', '.join(urls)}"
    lines[0] = (f"Web Felis ({sites}) vs Stockfish capped to set Elo levels, "
                f"{label}, {len(games)} games in {minutes:.0f} min, {MODES[mode]}")
    report = "\n".join(lines)
    print("\n" + report)
    with open(results_file, "w") as f:
        f.write(report + "\n")
    print(f"\nSaved to {results_file}")


if __name__ == "__main__":
    run()
