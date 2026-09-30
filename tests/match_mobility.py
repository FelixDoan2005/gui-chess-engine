"""Engine vs engine match: mobility ON vs mobility OFF.

Run from the project root:
    python tests/match_mobility.py
"""
import os
import random
import sys
import time
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import engine.ai as ai_module
from engine.ai import AI, PIECE_VALUES, make_move
from ui.chess_logic import Board, piece_moves, get_all_legal_moves, in_check

WHITE_MOBILITY_GAMES = 100   # X: games where White has mobility, Black doesn't
BLACK_MOBILITY_GAMES = 100   # Y: games where Black has mobility, White doesn't
DEPTHS = (2, 3, 4)

MAX_PLIES = 150        # stop a game after this many moves
OPENING_PLIES = 4      # random moves played before the engines take over
ADJUDICATE_MARGIN = 3  # at the move cap, this much material ahead = win

real_mobility = ai_module.mobility


def no_mobility(*args):
    return 0


def material(board):
    white = black = 0
    for row in board.grid:
        for piece in row:
            if piece is None or piece.endswith("king"):
                continue
            colour, kind = piece.split("_")
            if colour == "white":
                white += PIECE_VALUES[kind]
            else:
                black += PIECE_VALUES[kind]
    return white, black


def position_key(board):
    return (
        tuple(tuple(row) for row in board.grid),
        board.turn,
        board.en_passant_ts,
        board.white_king_moved, board.white_rook_kingside_moved, board.white_rook_queenside_moved,
        board.black_king_moved, board.black_rook_kingside_moved, board.black_rook_queenside_moved,
    )


def random_opening(seed):
    rng = random.Random(seed)
    board = Board()
    line = []
    for _ in range(OPENING_PLIES):
        move = rng.choice(get_all_legal_moves(board, piece_moves))
        board.move_piece(*move)
        line.append(move)
    return line


def play_game(task):
    depth, opening, mobility_side = task

    board = Board()
    for move in opening:
        board.move_piece(*move)

    ai = AI()
    seen = {}

    for _ in range(MAX_PLIES):
        key = position_key(board)
        seen[key] = seen.get(key, 0) + 1
        if seen[key] >= 3:
            return depth, mobility_side, None, "repetition"

        if not get_all_legal_moves(board, piece_moves):
            if board.turn == "white":
                king_pos = board.white_king
                winner = "black"
            else:
                king_pos = board.black_king
                winner = "white"
            if in_check(board.grid, board.turn, king_pos):
                return depth, mobility_side, winner, "checkmate"
            return depth, mobility_side, None, "stalemate"

        # Turn mobility on only when it's the mobility side's move.
        if board.turn == mobility_side:
            ai_module.mobility = real_mobility
        else:
            ai_module.mobility = no_mobility

        from_sq, to_sq = ai.choose_move(board, piece_moves, depth)
        make_move(board, from_sq, to_sq)

    white, black = material(board)
    if white - black >= ADJUDICATE_MARGIN:
        return depth, mobility_side, "white", "move limit"
    if black - white >= ADJUDICATE_MARGIN:
        return depth, mobility_side, "black", "move limit"
    return depth, mobility_side, None, "move limit"


def print_group(label, games):
    wins = draws = losses = 0
    for _, mobility_side, winner, _ in games:
        if winner is None:
            draws += 1
        elif winner == mobility_side:
            wins += 1
        else:
            losses += 1

    score = (wins + 0.5 * draws) / len(games) * 100
    print(f"  {label:22} {wins:3} W / {draws:3} D / {losses:3} L   score {score:5.1f}%")


if __name__ == "__main__":
    tasks = []
    for depth in DEPTHS:
        for i in range(WHITE_MOBILITY_GAMES):
            tasks.append((depth, random_opening(i), "white"))
        for i in range(BLACK_MOBILITY_GAMES):
            tasks.append((depth, random_opening(i), "black"))

    print(f"Running {len(tasks)} games on {os.cpu_count()} cores...", flush=True)
    start = time.time()
    with Pool() as pool:
        results = []
        for result in pool.imap_unordered(play_game, tasks):
            results.append(result)
            print(f"  {len(results)}/{len(tasks)} done", end="\r", flush=True)
    print(f"\nFinished in {time.time() - start:.1f}s")

    print("\nScore = wins + half of draws, for the MOBILITY engine. 50% = no difference.")
    for depth in DEPTHS:
        at_depth = [r for r in results if r[0] == depth]
        white_games = [r for r in at_depth if r[1] == "white"]
        black_games = [r for r in at_depth if r[1] == "black"]

        print(f"\nDepth {depth}")
        print_group(f"Mobility as White ({len(white_games)})", white_games)
        print_group(f"Mobility as Black ({len(black_games)})", black_games)
        print_group(f"Total ({len(at_depth)})", at_depth)

        endings = {}
        for _, _, _, reason in at_depth:
            endings[reason] = endings.get(reason, 0) + 1
        print(f"  Games ended by: {endings}")

# 600/600 done
# Finished in 2019.6s

# Score = wins + half of draws, for the MOBILITY engine. 50% = no difference.

# Depth 2
#   Mobility as White (100)  29 W /  51 D /  20 L   score  54.5%
#   Mobility as Black (100)  22 W /  56 D /  22 L   score  50.0%
#   Total (200)             51 W / 107 D /  42 L   score  52.2%
#   Games ended by: {'repetition': 107, 'checkmate': 93}

# Depth 3
#   Mobility as White (100)  23 W /  56 D /  21 L   score  51.0%
#   Mobility as Black (100)  19 W /  64 D /  17 L   score  51.0%
#   Total (200)             42 W / 120 D /  38 L   score  51.0%
#   Games ended by: {'repetition': 119, 'checkmate': 80, 'stalemate': 1}

# Depth 4
#   Mobility as White (100)  19 W /  70 D /  11 L   score  54.0%
#   Mobility as Black (100)  14 W /  76 D /  10 L   score  52.0%
#   Total (200)             33 W / 146 D /  21 L   score  53.0%
#   Games ended by: {'repetition': 146, 'checkmate': 54}