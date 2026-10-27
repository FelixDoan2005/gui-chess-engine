"""Texel tuning, step 2: fit the evaluation numbers to the self-play results.

Each position's evaluation is turned into a predicted result for White,
    predicted = 1 / (1 + 10 ** (-K * evaluation / 4))      (evaluation in pawns)
and the error is the average of (real result - predicted) squared. The
numbers in engine/tuning.py are nudged up and down one at a time, keeping
every change that lowers the error, until none does (Peter Österlund's
method for his engine Texel, chessprogramming.org/Texel's_Tuning_Method).

The evaluation is a sum of terms, each multiplied by one of these numbers, so
each position is broken into those terms once ("features") and every error
after that is just multiplication: fast, even with hundreds of thousands of
positions. 10% of the positions are held back to check it isn't overfitting.

Writes tuned_params.json (used by engine/uci.py via ENGINE_PARAMS) and
tuning_results.txt. Best run on PyPy:
    pypy tests/tuning/texel_tune.py
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

import engine.ai as ai
from engine.tuning import PARAMS, param_name, get_params, set_params

TEXEL_DIR = os.environ.get("TEXEL_DIR", os.path.join(ROOT, "tests", "results", "texel"))
POSITIONS_FILE = os.path.join(TEXEL_DIR, "selfplay_positions.jsonl")
PARAMS_FILE = os.path.join(TEXEL_DIR, "tuned_params.json")
REPORT_FILE = os.path.join(TEXEL_DIR, "tuning_results.txt")

VALIDATION_SHARE = 0.1  # held back to check for overfitting
STEP_SHARE = 0.05       # each nudge starts at 5% of the number's size...
MIN_STEP = 0.001        # ...but never smaller than this
ROUNDS = 3              # after each round with no more gains, the steps are halved
MAX_SHARE = 3           # every number stays between 0 and 3x its starting (sourced) value

PIECE_LETTERS = {"p": "pawn", "n": "knight", "b": "bishop", "r": "rook", "q": "queen", "k": "king"}


class Position:
    # just what evaluate() needs: the grid and where the kings are
    def __init__(self, text):
        self.grid = []
        for row in range(8):
            cells = []
            for col in range(8):
                letter = text[row * 8 + col]
                if letter == ".":
                    cells.append(None)
                else:
                    if letter.isupper():
                        colour = "white"
                    else:
                        colour = "black"
                    piece = colour + "_" + PIECE_LETTERS[letter.lower()]
                    cells.append(piece)
                    if piece == "white_king":
                        self.white_king = (row, col)
                    if piece == "black_king":
                        self.black_king = (row, col)
            self.grid.append(cells)


def features(chunk):
    # each position as: evaluation = constant + sum of (number * feature)
    start = get_params(ai)
    rows = []
    for text, result in chunk:
        position = Position(text)
        base = ai.evaluate(position)
        feature_list = []
        for i in range(len(start)):
            values = list(start)
            values[i] += 1
            set_params(ai, values)
            feature_list.append(ai.evaluate(position) - base)
        set_params(ai, start)
        constant = base
        for i in range(len(start)):
            constant -= start[i] * feature_list[i]
        rows.append((constant, feature_list, result))
    return rows


def evaluations(rows, values):
    scores = []
    for constant, feature_list, _ in rows:
        score = constant
        for i in range(len(values)):
            score += values[i] * feature_list[i]
        scores.append(score)
    return scores


def error(rows, values, k):
    total = 0
    scores = evaluations(rows, values)
    for i in range(len(rows)):
        predicted = 1 / (1 + 10 ** (-k * scores[i] / 4))
        total += (rows[i][2] - predicted) ** 2
    return total / len(rows)


def fit_k(rows, values):
    # the K that makes the current evaluation predict the results best
    low = 0.05
    high = 5.0
    for _ in range(40):
        third = (high - low) / 3
        if error(rows, values, low + third) < error(rows, values, high - third):
            high = high - third
        else:
            low = low + third
    return (low + high) / 2


def load_positions():
    data = []
    with open(POSITIONS_FILE) as f:
        for line in f:
            try:
                game = json.loads(line)
            except json.JSONDecodeError:
                continue
            if game["result"] is None:
                continue
            for text in game["positions"]:
                data.append((text, game["result"]))
    return data


def run():
    data = load_positions()
    random.Random(0).shuffle(data)
    print(f"Tuning on {len(data):,} positions", flush=True)

    # break every position into features, on all cores
    started = time.time()
    chunks = []
    size = max(1, len(data) // 200)
    for i in range(0, len(data), size):
        chunks.append(data[i:i + size])
    rows = []
    with Pool() as pool:
        for chunk_rows in pool.imap(features, chunks):
            rows += chunk_rows
    print(f"  features worked out in {time.time() - started:.0f}s", flush=True)

    # check the features rebuild the real evaluation
    start = get_params(ai)
    for check in range(min(20, len(data))):
        real = ai.evaluate(Position(data[check][0]))
        rebuilt = evaluations([rows[check]], start)[0]
        if abs(real - rebuilt) > 1e-6:
            sys.exit(f"features don't match the evaluation: {real} vs {rebuilt}")

    held_back = int(len(rows) * VALIDATION_SHARE)
    validation = rows[:held_back]
    training = rows[held_back:]

    k = fit_k(training, start)
    error_before = error(training, start, k)
    validation_before = error(validation, start, k)
    print(f"  K = {k:.3f}, error before: training {error_before:.6f}, held back {validation_before:.6f}", flush=True)

    # nudge each number up or down, keep what lowers the error
    values = list(start)
    best = error_before
    steps = []
    for value in start:
        steps.append(max(abs(value) * STEP_SHARE, MIN_STEP))

    # early stopping: keep the numbers from the pass where the held-back
    # positions were predicted best, in case later passes start overfitting
    best_values = list(start)
    best_validation = validation_before
    passes = 0
    for round_number in range(ROUNDS):
        improved = True
        while improved:
            improved = False
            passes += 1
            for i in range(len(values)):
                for direction in (1, -1):
                    trial = list(values)
                    trial[i] += direction * steps[i]
                    # limits: no sign flips, and no more than MAX_SHARE x the sourced value
                    if trial[i] < 0 or trial[i] > abs(start[i]) * MAX_SHARE:
                        continue
                    trial_error = error(training, trial, k)
                    if trial_error < best:
                        values = trial
                        best = trial_error
                        improved = True
                        break

            pass_validation = error(validation, values, k)
            if pass_validation < best_validation:
                best_validation = pass_validation
                best_values = list(values)
            print(f"  round {round_number + 1}, pass {passes}: error {best:.6f}, held back "
                  f"{pass_validation:.6f} ({time.time() - started:.0f}s)", flush=True)
        for i in range(len(steps)):
            steps[i] = steps[i] / 2

    values = best_values
    best = error(training, values, k)
    validation_after = best_validation
    names = []
    for param in PARAMS:
        names.append(param_name(param))
    with open(PARAMS_FILE, "w") as f:
        json.dump({"names": names, "before": start, "after": values,
                   "K": k, "positions": len(rows), "training_error": [error_before, best],
                   "validation_error": [validation_before, validation_after]}, f, indent=1)

    lines = [
        f"Texel tuning on {len(rows):,} self-play positions ({len(training):,} training, "
        f"{len(validation):,} held back), K = {k:.3f}",
        f"  error, training:  {error_before:.6f} -> {best:.6f}",
        f"  error, held back: {validation_before:.6f} -> {validation_after:.6f}"
        "   (should drop too, or it's overfitting)",
        "",
        f"  {'number':40} {'before':>8} {'after':>8}",
    ]
    for i in range(len(PARAMS)):
        lines.append(f"  {param_name(PARAMS[i]):40} {start[i]:8.3f} {values[i]:8.3f}")
    report = "\n".join(lines)
    print("\n" + report, flush=True)
    with open(REPORT_FILE, "w") as f:
        f.write(report + "\n")


if __name__ == "__main__":
    run()
