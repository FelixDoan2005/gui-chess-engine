"""Simplification test: is the engine just as strong without these heuristics?

The full engine (all heuristics) plays the same engine with REMOVED
switched off, from the same openings as all_heuristics_test.py, each played
twice with colours swapped. It also times both engines.

  Elo  = what the REMOVED heuristics add together, for the full engine.
  PASS = the 95% range includes 0 (or is below it): no proof they help, so
         it's safe to remove them.
  FAIL = the whole range is above 0: together they do help, so keep them.

If it fails, remove them one after another instead, running this test after
each removal, to find which ones matter.

Run from the project root (or click Run in VS Code):
    python tests/matches/simplification_test.py
"""
import os
import sys
import time
from multiprocessing import Pool

import all_heuristics_test as heuristic_test  # same folder; also puts the project on sys.path

from engine.ai import AI, make_move
from ui.chess_logic import Board, piece_moves, get_all_legal_moves, in_check, draw_reason

DEPTH = 3
OPENINGS = 500  # each played twice = 1,000 games, about 80 min at depth 3 with quiescence search
# heuristics to test removing, e.g. {"bishop_pair", "king_attackers"}. the last
# test removed centre_control, hanging_pieces, knight_outposts, bishop_pawn_pairs
# and rook_open_files (PASS, see simplification_results.txt)
REMOVED = set()

RESULTS_FILE = os.path.join(heuristic_test.RESULTS_DIR, "simplification_results.txt")

FULL = set(heuristic_test.HEURISTICS)
SLIM = FULL - REMOVED


def play_game(task):
    depth, opening_index, full_colour, opening = task

    board = Board()
    for move in opening:
        board.move_piece(*move)

    engine = AI()
    winner, reason = None, "move limit"
    thinking = {"full": 0.0, "slim": 0.0}  # seconds each engine spent choosing moves
    moves = {"full": 0, "slim": 0}

    for _ in range(heuristic_test.MAX_PLIES):
        draw = draw_reason(board)
        if draw:
            reason = draw
            break

        if not get_all_legal_moves(board, piece_moves):
            if board.turn == "white":
                king_pos = board.white_king
                checkmate_winner = "black"
            else:
                king_pos = board.black_king
                checkmate_winner = "white"
            if in_check(board.grid, board.turn, king_pos):
                winner = checkmate_winner
                reason = "checkmate"
            else:
                reason = "stalemate"
            break

        if board.turn == full_colour:
            side = "full"
            heuristic_test.use_heuristics(FULL)
        else:
            side = "slim"
            heuristic_test.use_heuristics(SLIM)

        started = time.perf_counter()
        from_sq, to_sq = engine.choose_move(board, piece_moves, depth)
        thinking[side] += time.perf_counter() - started
        moves[side] += 1
        make_move(board, from_sq, to_sq)
    else:
        white, black = heuristic_test.material(board)
        if white - black >= heuristic_test.ADJUDICATE_MARGIN:
            winner = "white"
        elif black - white >= heuristic_test.ADJUDICATE_MARGIN:
            winner = "black"

    if winner is None:
        score = 0.5
    elif winner == full_colour:
        score = 1
    else:
        score = 0

    # "full_colour" and "opening" are what heuristic_test.match_result pairs up.
    return {"opening": opening_index, "full_colour": full_colour, "score": score,
            "reason": reason, "thinking": thinking, "moves": moves}


def report_lines(games):
    result = heuristic_test.match_result(games)
    full_time = sum(game["thinking"]["full"] for game in games) / sum(game["moves"]["full"] for game in games)
    slim_time = sum(game["thinking"]["slim"] for game in games) / sum(game["moves"]["slim"] for game in games)
    change = (full_time - slim_time) / full_time
    if change >= 0:
        speed = f"{change:.0%} faster"
    else:
        speed = f"{-change:.0%} slower"

    endings = {}
    for game in games:
        endings[game["reason"]] = endings.get(game["reason"], 0) + 1
    ended = []
    for reason in sorted(endings, key=endings.get, reverse=True):
        ended.append(f"{reason} {endings[reason] / len(games):.0%}")

    if result["low"] > 0:
        verdict = "FAIL: together they help, so keep them"
    else:
        verdict = "PASS: no proof they help, so it's safe to remove them"

    return [
        f"Simplification test at depth {DEPTH}: full engine (all {len(FULL)}) vs without "
        f"{', '.join(sorted(REMOVED))}",
        f"  {result['games']:,} games: {result['wins']} W / {result['draws']} D / {result['losses']} L "
        f"for the full engine, score {result['score']:.1%}",
        f"  Elo the {len(REMOVED)} removed heuristics add together: {result['elo']:+.0f}   "
        f"95% range [{result['low']:+.0f}, {result['high']:+.0f}]",
        f"  Time per move: full {full_time:.3f}s, without them {slim_time:.3f}s ({speed})",
        "  Games ended by: " + ", ".join(ended),
        f"  {verdict}",
    ]


def run():
    if len(REMOVED) == 0:
        sys.exit("Put the heuristics to test removing in REMOVED first. "
                 f"Choose from: {', '.join(heuristic_test.HEURISTICS)}")

    unknown = REMOVED - FULL
    if unknown:
        sys.exit(f"Not heuristic names: {', '.join(sorted(unknown))}. "
                 f"Choose from: {', '.join(heuristic_test.HEURISTICS)}")

    heuristic_test.keep_awake()
    tasks = []
    for index, opening in enumerate(heuristic_test.make_openings(OPENINGS)):
        for full_colour in ("white", "black"):
            tasks.append((DEPTH, index, full_colour, opening))

    print(f"Full engine vs without {', '.join(sorted(REMOVED))}: "
          f"{len(tasks):,} games at depth {DEPTH} on {os.cpu_count()} cores", flush=True)
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

    report = "\n".join(report_lines(games))
    print("\n" + report)
    with open(RESULTS_FILE, "w") as f:
        f.write(report + "\n")
    print(f"\nSaved to {RESULTS_FILE}")


if __name__ == "__main__":
    run()
