"""How much does each evaluation heuristic add? Engine-vs-engine matches.

For each heuristic, the full engine (all of them on) plays the same
engine with only that heuristic switched off. One more match, all vs none
(material only), shows what they add together. Everything else is identical:
same search, same depth, same openings, each opening played twice with colours
swapped.

  score     = wins + half the draws, for the full engine. 50% = no difference.
  Elo       = 400 * log10(score / (1 - score)). Above 0 = the heuristic makes the engine stronger.
  95% range = how sure that Elo is, from the spread of each opening's pair of
              games (the way Stockfish's testing framework, fishtest, does it).
  verdict   = helps: whole range above 0 / hurts: whole range below 0 /
              no clear effect: range includes 0.

Run from the project root (or click Run in VS Code):
    python tests/all_heuristics_test.py

Every finished game is saved to GAMES_FILE, so you can stop at any time
(Ctrl+C) and run it again later to carry on where it stopped. SUMMARY_FILE and
GRAPH_FILE are updated every few minutes and after each depth, so you can look
at them while it runs. Delete GAMES_FILE to start over.
"""
import ctypes
import hashlib
import importlib.util
import json
import math
import os
import random
import signal
import sys
import time
from multiprocessing import Pool

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS_DIR)
sys.path.insert(0, ROOT)

# ui/__init__.py imports pygame, which would print its hello message once per
# worker process, over the top of the progress line.
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import engine.ai as ai_module
from engine.ai import AI, PIECE_VALUES, make_move
from ui.chess_logic import Board, piece_moves, get_all_legal_moves, in_check, draw_reason

DEPTHS = (2, 3)

# Openings per match at each depth. Each one is played twice (colours swapped),
# so 500 openings = 1,000 games per match = 14,000 games per depth.
# Measured on this PC (28 cores), with quiescence search: a depth 2 game takes
# ~13 s, so 250 openings ~1 h. A depth 3 game takes ~136 s, so 100 openings ~4 h.
# Raise a number and run again to add more games to what's already saved.
OPENINGS_PER_MATCH = {2: 250, 3: 100}

OPENING_PLIES = 4       # random moves played before the engines take over
MAX_PLIES = 1000        # safety net only; the draw rules end games well before this
ADJUDICATE_MARGIN = 3   # if the safety net is ever hit, this much material ahead = win
SUMMARY_EVERY = 5 * 60  # seconds between summary updates while it runs

GAMES_FILE = os.path.join(TESTS_DIR, "all_heuristics_games.jsonl")
SUMMARY_FILE = os.path.join(TESTS_DIR, "all_heuristics_results.txt")
GRAPH_FILE = os.path.join(TESTS_DIR, "all_heuristics_results.png")

# The 6 heuristics evaluate() calls by name...
FUNCTION_HEURISTICS = [
    "mobility",
    "pawn_structure",
    "bishop_pair",
    "mop_up",
    "king_pawn_shield",
    "king_attackers",
]
# ...and the 2 that work through piece_square_value.
HEURISTICS = ["piece_square_tables", "king_endgame_table"] + FUNCTION_HEURISTICS

# One match per heuristic, named after the heuristic the other engine is
# missing, plus all vs none.
NONE = "none"
MATCHES = [NONE] + HEURISTICS

VERDICT_COLOURS = {"helps": "tab:green", "hurts": "tab:red", "no clear effect": "tab:gray"}

# evaluate() looks these names up in engine.ai every time it runs, so
# reassigning them switches a heuristic on or off for the next search.
real_piece_square_value = ai_module.piece_square_value
real_king_endgame_table = ai_module.KING_ENDGAME_TABLE
real_functions = {name: getattr(ai_module, name) for name in FUNCTION_HEURISTICS}


def off(*args):
    return 0


def use_heuristics(switched_on):
    if "piece_square_tables" in switched_on:
        ai_module.piece_square_value = real_piece_square_value
    else:
        ai_module.piece_square_value = off

    # Off: the king blends from KING_TABLE to KING_TABLE, so it keeps its
    # middlegame table all game.
    if "king_endgame_table" in switched_on:
        ai_module.KING_ENDGAME_TABLE = real_king_endgame_table
    else:
        ai_module.KING_ENDGAME_TABLE = ai_module.KING_TABLE

    for name in FUNCTION_HEURISTICS:
        if name in switched_on:
            setattr(ai_module, name, real_functions[name])
        else:
            setattr(ai_module, name, off)


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


def make_openings(count):
    # Random openings, all different, with equal material and a game still to
    # play. Seeded, so every run and every depth gets the same list.
    openings = []
    seen = set()
    seed = 0
    while len(openings) < count:
        rng = random.Random(seed)
        seed += 1
        board = Board()
        line = []
        for _ in range(OPENING_PLIES):
            move = rng.choice(get_all_legal_moves(board, piece_moves))
            board.move_piece(*move)
            line.append(move)

        white, black = material(board)
        if white != black:
            continue
        if not get_all_legal_moves(board, piece_moves):
            continue  # e.g. fool's mate
        if board.position_key() in seen:
            continue
        seen.add(board.position_key())
        openings.append(line)
    return openings


def play_game(task):
    depth, match, opening_index, full_colour, opening = task
    full = set(HEURISTICS)
    if match == NONE:
        other = set()
    else:
        other = full - {match}

    board = Board()
    for move in opening:
        board.move_piece(*move)

    engine = AI()
    winner, reason = None, "move limit"
    started = time.time()

    for _ in range(MAX_PLIES):
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
            use_heuristics(full)
        else:
            use_heuristics(other)

        from_sq, to_sq = engine.choose_move(board, piece_moves, depth)
        make_move(board, from_sq, to_sq)
    else:
        white, black = material(board)
        if white - black >= ADJUDICATE_MARGIN:
            winner = "white"
        elif black - white >= ADJUDICATE_MARGIN:
            winner = "black"

    if winner is None:
        score = 0.5
    elif winner == full_colour:
        score = 1
    else:
        score = 0

    return {"depth": depth, "match": match, "opening": opening_index, "full_colour": full_colour,
            "score": score, "reason": reason, "seconds": round(time.time() - started, 1)}


def engine_fingerprint():
    # Changes whenever the engine or the rules change, so games played by an
    # old version never get mixed in with new ones.
    digest = hashlib.sha1()
    for path in ("engine/ai.py", "ui/chess_logic.py"):
        with open(os.path.join(ROOT, path), "rb") as f:
            digest.update(f.read()) 
    return digest.hexdigest()[:12]


def load_games(fingerprint):
    # Games saved by earlier runs, so this run can carry on where they stopped.
    lines = []
    if os.path.exists(GAMES_FILE):
        with open(GAMES_FILE) as f:
            lines = f.read().splitlines()

    if not lines:
        with open(GAMES_FILE, "w") as f:
            f.write(json.dumps({"engine": fingerprint}) + "\n")
        return []

    try:
        saved_fingerprint = json.loads(lines[0]).get("engine")
    except json.JSONDecodeError:
        saved_fingerprint = None
    if saved_fingerprint != fingerprint:
        sys.exit(f"{GAMES_FILE} holds games from a different version of the engine "
                 "(engine/ai.py or ui/chess_logic.py has changed since).\n"
                 "Delete it to start over with the current engine.")

    games = []
    for line in lines[1:]:
        try:
            games.append(json.loads(line))
        except json.JSONDecodeError:
            pass  # a half-written last line from a run that was cut off
    return games


def elo(score):
    score = min(max(score, 0.001), 0.999)  # 0% or 100% would be infinite
    return 400 * math.log10(score / (1 - score))


def match_result(games):
    # Each opening gives a pair of games: the full engine as White and as
    # Black. Openings still missing one of the two are left out.
    pairs = {}
    for game in games:
        if game["opening"] not in pairs:
            pairs[game["opening"]] = {}
        pairs[game["opening"]][game["full_colour"]] = game["score"]

    pair_scores = []
    wins = draws = losses = 0
    for colours in pairs.values():
        if len(colours) < 2:
            continue
        pair_scores.append((colours["white"] + colours["black"]) / 2)
        for score in colours.values():
            if score == 1:
                wins += 1
            elif score == 0:
                losses += 1
            else:
                draws += 1

    if not pair_scores:
        return None

    n = len(pair_scores)
    score = sum(pair_scores) / n
    variance = sum((pair_score - score) ** 2 for pair_score in pair_scores) / n
    margin = 1.96 * math.sqrt(variance / n)
    low = elo(score - margin)
    high = elo(score + margin)

    if low > 0:
        verdict = "helps"
    elif high < 0:
        verdict = "hurts"
    else:
        verdict = "no clear effect"

    return {"games": 2 * n, "wins": wins, "draws": draws, "losses": losses, "score": score,
            "elo": elo(score), "low": low, "high": high, "verdict": verdict}


def all_results(games):
    # {depth: {match: result}} for every depth with at least one finished pair.
    by_depth = {}
    for depth in DEPTHS:
        by_match = {match: [] for match in MATCHES}
        for game in games:
            if game["depth"] == depth and game["match"] in by_match:
                by_match[game["match"]].append(game)

        results = {match: match_result(match_games) for match, match_games in by_match.items()}
        if any(result is not None for result in results.values()):
            by_depth[depth] = results
    return by_depth


def table_row(name, result):
    wdl = f"{result['wins']:>4} /{result['draws']:>4} /{result['losses']:>4}"
    elo_range = f"[{result['low']:+.0f}, {result['high']:+.0f}]"
    return (f"  {name:20} {wdl}   {result['score'] * 100:5.1f}%  {result['elo']:+5.0f}   "
            f"{elo_range:14}  {result['verdict']}")


def summary_lines(games, by_depth):
    lines = [
        f"Full engine (all {len(HEURISTICS)} heuristics) vs the same engine without one of them.",
        "Score = wins + half the draws, for the full engine. Elo above 0 = the heuristic makes it stronger.",
        "helps = whole 95% range above 0, hurts = whole range below 0, no clear effect = range includes 0.",
    ]
    header = f"  {'heuristic':20} {'   W /   D /   L'}   {'score':>6}  {'Elo':>5}   {'95% range':14}  verdict"

    for depth, results in by_depth.items():
        played = [result for result in results.values() if result is not None]
        per_match = min(result["games"] for result in played)
        title = f"DEPTH {depth}   ({per_match:,} games per match)"
        if len(played) < len(MATCHES) or per_match < 2 * OPENINGS_PER_MATCH[depth]:
            title += "   - unfinished, run again to carry on"
        lines += ["", title, header]

        if results[NONE] is not None:
            lines.append(table_row(f"ALL {len(HEURISTICS)} vs none", results[NONE]))
            lines.append("  " + "-" * 87)

        ranked = [name for name in HEURISTICS if results[name] is not None]
        ranked.sort(key=lambda name: results[name]["elo"], reverse=True)
        for name in ranked:
            lines.append(table_row(name, results[name]))

        endings = {}
        for game in games:
            if game["depth"] == depth:
                endings[game["reason"]] = endings.get(game["reason"], 0) + 1
        total = sum(endings.values())
        ended = []
        for reason in sorted(endings, key=endings.get, reverse=True):
            ended.append(f"{reason} {endings[reason] / total:.0%}")
        lines.append("  Games ended by: " + ", ".join(ended))
    return lines


def save_graph(by_depth, show=False):
    # Imported here rather than at the top, so the worker processes (which
    # also load this file) don't each load matplotlib.
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    if not by_depth:
        return

    depths = list(by_depth)
    rows = (len(depths) + 1) // 2
    fig, axes = plt.subplots(rows, 2, figsize=(15, 5.5 * rows), squeeze=False)
    for ax in axes.ravel()[len(depths):]:
        ax.axis("off")

    for ax, depth in zip(axes.ravel(), depths):
        results = by_depth[depth]
        names = [name for name in HEURISTICS if results[name] is not None]
        names.sort(key=lambda name: results[name]["elo"])  # barh draws the first one at the bottom
        elos = [results[name]["elo"] for name in names]
        below = [results[name]["elo"] - results[name]["low"] for name in names]
        above = [results[name]["high"] - results[name]["elo"] for name in names]
        colours = [VERDICT_COLOURS[results[name]["verdict"]] for name in names]

        ax.barh(names, elos, xerr=[below, above], color=colours, capsize=3)
        ax.axvline(0, color="black", linewidth=0.8)
        title = f"Depth {depth}"
        if results[NONE] is not None:
            title += f"   (all {len(HEURISTICS)} vs none: {results[NONE]['elo']:+.0f} Elo)"
        ax.set_title(title)
        ax.set_xlabel("Elo the heuristic adds, with 95% range")

    legend = [Patch(color=colour, label=verdict) for verdict, colour in VERDICT_COLOURS.items()]
    fig.legend(handles=legend, loc="lower center", ncol=3)
    fig.suptitle("Full engine vs the same engine without each heuristic")
    fig.tight_layout(rect=(0, 0.04, 1, 0.96))
    fig.savefig(GRAPH_FILE, dpi=120)

    if show:
        plt.show()
    else:
        plt.close(fig)


def write_summary(games):
    by_depth = all_results(games)
    report = "\n".join(summary_lines(games, by_depth))
    try:
        with open(SUMMARY_FILE, "w") as f:
            f.write(report + "\n")
        save_graph(by_depth)
    except OSError as error:
        # e.g. the file is open somewhere that locks it; the games are still saved
        print(f"\n  Couldn't update the summary files: {error}")
    return report

def ignore_ctrl_c():
    # Workers ignore Ctrl+C; the main process catches it and stops them.
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def keep_awake():
    # Stops Windows going to sleep while this runs (back to normal when it
    # ends). Closing a laptop's lid can still put it to sleep.
    if sys.platform == "win32":
        ES_CONTINUOUS = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)


def duration(seconds):
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes:02}m"
    return f"{minutes}m {seconds:02}s"


def run():
    # save_graph only imports matplotlib when it first draws, so check it's
    # installed now rather than crash after the first depth.
    if importlib.util.find_spec("matplotlib") is None:
        sys.exit(f"matplotlib isn't installed for this Python ({sys.executable}).\n"
                 f'Install it with:  "{sys.executable}" -m pip install matplotlib')

    keep_awake()
    games = load_games(engine_fingerprint())
    done = set()
    for game in games:
        done.add((game["depth"], game["match"], game["opening"], game["full_colour"]))
    if games:
        print(f"Carrying on: {len(games):,} games already saved in {GAMES_FILE}")

    openings = make_openings(max(OPENINGS_PER_MATCH.values()))
    last_update = time.time()

    try:
        with Pool(initializer=ignore_ctrl_c) as pool, open(GAMES_FILE, "a") as games_file:
            for depth in DEPTHS:
                # Opening by opening, so if the run stops partway, every match
                # has played about the same number of games.
                tasks = []
                for index in range(OPENINGS_PER_MATCH[depth]):
                    for match in MATCHES:
                        for full_colour in ("white", "black"):
                            if (depth, match, index, full_colour) not in done:
                                tasks.append((depth, match, index, full_colour, openings[index]))
                if not tasks:
                    continue

                print(f"Depth {depth}: {len(tasks):,} games to play on {os.cpu_count()} cores", flush=True)
                started = time.time()
                for count, game in enumerate(pool.imap_unordered(play_game, tasks), start=1):
                    games.append(game)
                    games_file.write(json.dumps(game) + "\n")
                    games_file.flush()

                    elapsed = time.time() - started
                    left = elapsed / count * (len(tasks) - count)
                    print(f"\r  {count:,}/{len(tasks):,} games | {duration(elapsed)} so far | "
                          f"about {duration(left)} left   ", end="", flush=True)

                    if time.time() - last_update > SUMMARY_EVERY:
                        write_summary(games)
                        last_update = time.time()
                print()
                write_summary(games)
    except KeyboardInterrupt:
        print("\nStopped. Every finished game is saved; run again to carry on.")

    report = write_summary(games)
    print("\n" + report)
    print(f"\nSaved to {SUMMARY_FILE}")
    print(f"     and {GRAPH_FILE}")
    save_graph(all_results(games), show=True)

if __name__ == "__main__":
    run()
