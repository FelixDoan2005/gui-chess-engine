"""Texel tuning, step 1: self-play games, saving quiet positions and how each
game ended (1 = White won, 0.5 = draw, 0 = Black won).

Each game starts from a few random moves, then the engine plays both sides
at TIME_PER_MOVE seconds a move. From each game, up to SAMPLES_PER_GAME
"quiet" positions are kept: not in check, still with pawns on the board, and
where quiescence search agrees with the evaluation (no captures pending).

Every game is saved as it finishes, so it can be stopped and run again later.
Best run on PyPy:
    pypy tests/tuning/texel_selfplay.py [games]
"""
import json
import os
import random
import sys
import time
from multiprocessing import Pool

TUNING_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(TUNING_DIR))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests", "matches"))

import all_heuristics_test as heuristic_test  # progress formatting, keep_awake, ignore_ctrl_c
import engine.ai as ai
from ui.chess_logic import Board, piece_moves, get_all_legal_moves, in_check, draw_reason

TEXEL_DIR = os.environ.get("TEXEL_DIR", os.path.join(ROOT, "tests", "results", "texel"))
POSITIONS_FILE = os.path.join(TEXEL_DIR, "selfplay_positions.jsonl")

GAMES = 20000
TIME_PER_MOVE = 0.1
RANDOM_PLIES = 6       # random moves first, so the games are all different
SKIP_PLIES = 10        # positions this early are mostly still the random moves
SAMPLES_PER_GAME = 10  # positions from one game are alike, so keep only a few
MAX_PLIES = 400        # a game this long counts as a draw

FEN_LETTERS = {"pawn": "p", "knight": "n", "bishop": "b", "rook": "r", "queen": "q", "king": "k"}


def position_text(board):
    # the 64 squares in one string, row 0 first: FEN letters, "." for empty
    text = ""
    for row in board.grid:
        for piece in row:
            if piece is None:
                text += "."
            else:
                colour, kind = piece.split("_")
                letter = FEN_LETTERS[kind]
                if colour == "white":
                    letter = letter.upper()
                text += letter
    return text


def random_start(rng):
    # a few random legal moves; None if that ends the game or loses material
    board = Board()
    for _ in range(RANDOM_PLIES):
        moves = get_all_legal_moves(board, piece_moves)
        if len(moves) == 0:
            return None
        ai.make_move(board, *rng.choice(moves))
    white, black = heuristic_test.material(board)
    if white != black or len(get_all_legal_moves(board, piece_moves)) == 0:
        return None
    return board


def has_pawns(board):
    for row in board.grid:
        for piece in row:
            if piece is not None and piece.endswith("pawn"):
                return True
    return False


def is_quiet(board, checked):
    if checked:
        return False
    if board.turn == "white":
        stand_pat = ai.evaluate(board)
    else:
        stand_pat = -ai.evaluate(board)
    settled = ai.quiescence(board, piece_moves, -float("inf"), float("inf"))
    return abs(settled - stand_pat) < 1e-9


def play_game(seed):
    rng = random.Random(seed)
    board = random_start(rng)
    if board is None:
        return {"seed": seed, "result": None, "positions": []}

    engine = ai.AI()
    engine.new_game()
    candidates = []
    result = 0.5
    for ply in range(MAX_PLIES):
        if draw_reason(board):
            break
        if board.turn == "white":
            king_pos = board.white_king
        else:
            king_pos = board.black_king
        checked = in_check(board.grid, board.turn, king_pos)

        if len(get_all_legal_moves(board, piece_moves)) == 0:
            if checked:
                # the side to move is checkmated
                if board.turn == "white":
                    result = 0
                else:
                    result = 1
            break

        # pawnless positions are left out: mop-up evaluation works differently there
        if ply >= SKIP_PLIES and has_pawns(board) and is_quiet(board, checked):
            candidates.append(position_text(board))

        move = engine.choose_move(board, piece_moves, 20, time_limit=TIME_PER_MOVE, keep_table=True)
        ai.make_move(board, *move)

    if len(candidates) > SAMPLES_PER_GAME:
        candidates = rng.sample(candidates, SAMPLES_PER_GAME)
    return {"seed": seed, "result": result, "positions": candidates}


def run():
    games = GAMES
    if len(sys.argv) > 1:
        games = int(sys.argv[1])
    os.makedirs(TEXEL_DIR, exist_ok=True)

    # carry on where an earlier run stopped
    done = set()
    if os.path.exists(POSITIONS_FILE):
        with open(POSITIONS_FILE) as f:
            for line in f:
                try:
                    done.add(json.loads(line)["seed"])
                except json.JSONDecodeError:
                    pass  # a half-written last line from a run that was cut off
    seeds = []
    for seed in range(games):
        if seed not in done:
            seeds.append(seed)
    print(f"Self-play: {len(seeds):,} games to play ({len(done):,} already saved), "
          f"{TIME_PER_MOVE:g}s per move", flush=True)
    if len(seeds) == 0:
        return

    heuristic_test.keep_awake()
    started = time.time()
    with Pool(initializer=heuristic_test.ignore_ctrl_c) as pool, open(POSITIONS_FILE, "a") as out:
        for count, game in enumerate(pool.imap_unordered(play_game, seeds), start=1):
            out.write(json.dumps(game) + "\n")
            out.flush()
            if count % 50 == 0 or count == len(seeds):
                elapsed = time.time() - started
                left = elapsed / count * (len(seeds) - count)
                print(f"  {count:,}/{len(seeds):,} games | {heuristic_test.duration(elapsed)} so far | "
                      f"about {heuristic_test.duration(left)} left", flush=True)


if __name__ == "__main__":
    run()
