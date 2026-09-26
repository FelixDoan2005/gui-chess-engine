"""Engine vs engine matches between different sets of eval heuristics.

  ps = pawn_structure, m = mobility. Piece-square tables are always on.

Run from the project root (or click Run in VS Code):
    python tests/match_heuristics.py

Results are printed and also saved to RESULTS_FILE.
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

# Each matchup is (engine A's heuristics, engine B's heuristics).
# Scores are reported from engine A's side.
MATCHUPS = [
    ({"ps"}, set()),
    ({"ps", "m"}, set()),
    ({"ps", "m"}, {"m"}),
    ({"ps"}, {"m"}),
]
DEPTHS = (2, 3, 4)
GAMES_PER_MATCHUP = 200   # per depth; half with A as White, half with A as Black

MAX_PLIES = 150        # stop a game after this many moves
OPENING_PLIES = 4      # random moves played before the engines take over
ADJUDICATE_MARGIN = 3  # at the move cap, this much material ahead = win
RESULTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "match_heuristics_results.txt")

real_mobility = ai_module.mobility
real_pawn_structure = ai_module.pawn_structure


def off(board):
    return 0


def label(features):
    if not features:
        return "none"
    return " + ".join(sorted(features))


def use_features(features):
    # evaluate() looks these names up every time it runs, so reassigning
    # them switches each heuristic on or off for the next search.
    if "m" in features:
        ai_module.mobility = real_mobility
    else:
        ai_module.mobility = off

    if "ps" in features:
        ai_module.pawn_structure = real_pawn_structure
    else:
        ai_module.pawn_structure = off


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
    matchup_index, depth, opening, a_colour = task
    a_features, b_features = MATCHUPS[matchup_index]

    board = Board()
    for move in opening:
        board.move_piece(*move)

    ai = AI()
    seen = {}
    winner, reason = None, "move limit"

    for _ in range(MAX_PLIES):
        key = position_key(board)
        seen[key] = seen.get(key, 0) + 1
        if seen[key] >= 3:
            reason = "repetition"
            break

        if not get_all_legal_moves(board, piece_moves):
            king_pos = board.white_king if board.turn == "white" else board.black_king
            if in_check(board.grid, board.turn, king_pos):
                winner = "black" if board.turn == "white" else "white"
                reason = "checkmate"
            else:
                reason = "stalemate"
            break

        if board.turn == a_colour:
            use_features(a_features)
        else:
            use_features(b_features)

        from_sq, to_sq = ai.choose_move(board, piece_moves, depth)
        make_move(board, from_sq, to_sq)
    else:
        white, black = material(board)
        if white - black >= ADJUDICATE_MARGIN:
            winner = "white"
        elif black - white >= ADJUDICATE_MARGIN:
            winner = "black"

    return matchup_index, depth, a_colour, winner, reason


def record(games):
    wins = draws = losses = 0
    for _, _, a_colour, winner, _ in games:
        if winner is None:
            draws += 1
        elif winner == a_colour:
            wins += 1
        else:
            losses += 1
    score = (wins + 0.5 * draws) / len(games) * 100
    return wins, draws, losses, score


def run():
    half = GAMES_PER_MATCHUP // 2
    tasks = []
    for matchup_index in range(len(MATCHUPS)):
        for depth in DEPTHS:
            for i in range(half):
                opening = random_opening(i)
                tasks.append((matchup_index, depth, opening, "white"))
                tasks.append((matchup_index, depth, opening, "black"))

    print(f"Running {len(tasks)} games on {os.cpu_count()} cores...", flush=True)
    start = time.time()
    results = []
    with Pool() as pool:
        for result in pool.imap_unordered(play_game, tasks):
            results.append(result)
            print(f"  {len(results)}/{len(tasks)} done", end="\r", flush=True)
    elapsed = time.time() - start

    lines = [
        f"Finished {len(tasks)} games in {elapsed / 60:.1f} min",
        "Score = wins + half of draws, for engine A. 50% = no difference.",
        "ps = pawn structure, m = mobility. Piece-square tables always on.",
    ]

    for matchup_index, (a_features, b_features) in enumerate(MATCHUPS):
        lines.append("")
        lines.append(f"=== {label(a_features)}  vs  {label(b_features)} ===")
        for depth in DEPTHS:
            games = [r for r in results if r[0] == matchup_index and r[1] == depth]
            wins, draws, losses, score = record(games)
            lines.append(f"  depth {depth}: {wins:3} W / {draws:3} D / {losses:3} L   score {score:5.1f}%")

    lines.append("")
    lines.append("===== SUMMARY (engine A score) =====")
    header = f"{'matchup':22}" + "".join(f"  depth {d:<3}" for d in DEPTHS)
    lines.append(header)
    for matchup_index, (a_features, b_features) in enumerate(MATCHUPS):
        row = f"{label(a_features) + ' vs ' + label(b_features):22}"
        for depth in DEPTHS:
            games = [r for r in results if r[0] == matchup_index and r[1] == depth]
            row += f"  {record(games)[3]:6.1f}%  "
        lines.append(row)

    report = "\n".join(lines)
    print("\n" + report)
    with open(RESULTS_FILE, "w") as f:
        f.write(report + "\n")
    print(f"\nSaved to {RESULTS_FILE}")


if __name__ == "__main__":
    run()
