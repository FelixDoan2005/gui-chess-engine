"""Texel tuning, all steps one after the other:
    1. texel_selfplay.py   self-play games -> quiet positions with results
    2. texel_tune.py       fit the evaluation numbers -> tuned_params.json
    3. texel_verify.py     tuned vs current engine, equal time
    4. tests/matches/stockfish_rating_test.py with the tuned numbers, at 1s and 10s

Each step saves its results and is skipped next time if already done, so the
whole thing can be stopped and started again. Steps 1-3 run on PyPy if it's
found (see engine_command in engine/uci.py). Everything is logged to
pipeline_log.txt. Nothing in engine/ai.py is changed: the tuned numbers stay
in tuned_params.json until you decide to keep them.

    python tests/tuning/run_texel_pipeline.py          the real run, about 6 hours
    python tests/tuning/run_texel_pipeline.py quick    a tiny version of every step, a few minutes
"""
import os
import subprocess
import sys
import time

TUNING_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(TUNING_DIR))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests", "matches"))

import all_heuristics_test as heuristic_test  # keep_awake, duration
from engine.uci import engine_command

GAMES = 20000
VERIFY = (1.0, 200)          # seconds per move, openings (x2 games)
RATINGS = [(1, 50), (10, 25)]

QUICK_GAMES = 40
QUICK_VERIFY = (0.2, 4)
QUICK_RATINGS = [(0.2, 1)]


def run_step(title, command, log_path, env):
    with open(log_path, "a") as log:
        log.write(f"\n===== {title} ({time.strftime('%H:%M')}) =====\n")
        log.flush()
        print(f"{time.strftime('%H:%M')}  {title}", flush=True)
        started = time.time()
        finished = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        log.write(f"===== exit code {finished.returncode} after {heuristic_test.duration(time.time() - started)} =====\n")
    if finished.returncode != 0:
        sys.exit(f"{title} failed (exit code {finished.returncode}): see {log_path}")


def run():
    quick = len(sys.argv) > 1 and sys.argv[1] == "quick"
    if quick:
        texel_dir = os.path.join(ROOT, "tests", "results", "texel_quick")
        games = QUICK_GAMES
        verify = QUICK_VERIFY
        ratings = QUICK_RATINGS
    else:
        texel_dir = os.path.join(ROOT, "tests", "results", "texel")
        games = GAMES
        verify = VERIFY
        ratings = RATINGS
    os.makedirs(texel_dir, exist_ok=True)
    log_path = os.path.join(texel_dir, "pipeline_log.txt")
    params_file = os.path.join(texel_dir, "tuned_params.json")

    env = dict(os.environ)
    env["TEXEL_DIR"] = texel_dir
    pypy = engine_command()[0]
    if "pypy" not in os.path.basename(pypy).lower():
        print("PyPy not found (set PYPY_PATH): steps 1-3 will run on normal Python, about 3x slower")
    print(f"Texel tuning pipeline, logging to {log_path}", flush=True)
    heuristic_test.keep_awake()

    run_step(f"1. self-play, {games:,} games", [pypy, os.path.join(TUNING_DIR, "texel_selfplay.py"), str(games)],
             log_path, env)

    if os.path.exists(params_file):
        print("2. tuning: already done, skipped")
    else:
        run_step("2. tuning", [pypy, os.path.join(TUNING_DIR, "texel_tune.py")], log_path, env)

    if os.path.exists(os.path.join(texel_dir, "verify_match.txt")):
        print("3. verification match: already done, skipped")
    else:
        run_step(f"3. verification match, {verify[0]:g}s per move",
                 [pypy, os.path.join(TUNING_DIR, "texel_verify.py"), str(verify[0]), str(verify[1])], log_path, env)

    # the rating test runs the tuned engine through engine/uci.py, which reads ENGINE_PARAMS
    rating_env = dict(env)
    rating_env["ENGINE_PARAMS"] = params_file
    for seconds, openings in ratings:
        rating_file = os.path.join(heuristic_test.RESULTS_DIR, f"stockfish_rating_results_{seconds:g}s_tuned.txt")
        if os.path.exists(rating_file):
            print(f"4. rating at {seconds:g}s: already done, skipped")
            continue
        run_step(f"4. Stockfish rating with the tuned numbers, {seconds:g}s per move",
                 [sys.executable, os.path.join(ROOT, "tests", "matches", "stockfish_rating_test.py"),
                  str(seconds), str(openings)], log_path, rating_env)

    print(f"{time.strftime('%H:%M')}  all done: results in {texel_dir} and tests/results", flush=True)


if __name__ == "__main__":
    run()
