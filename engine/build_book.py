"""Builds Felis an opening book, engine/book.json, from the Lichess list of named
chess openings: https://github.com/lichess-org/chess-openings
That list is CC0 (public domain), so the book can be shared freely.
"""
import json
import os
import urllib.request

import chess

SOURCE = "https://raw.githubusercontent.com/lichess-org/chess-openings/master/{}.tsv"
FILES = ["a", "b", "c", "d", "e"]
MIN_SHARE = 0.1   # keep a move only if it's at least 10% as common as the most common one
BOOK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "book.json")


def read_lines():
    # every named opening's moves, e.g. "1. e4 e5 2. Nf3 Nc6 3. Bb5"
    lines = []
    for name in FILES:
        with urllib.request.urlopen(SOURCE.format(name)) as response:
            text = response.read().decode("utf-8")
        rows = text.strip().split("\n")
        for row in rows[1:]:   # the first row is the column names
            # columns: eco code, opening name, moves (only the moves are needed)
            pgn = row.split("\t")[2]
            lines.append(pgn)
    return lines


def to_uci(pgn):
    # "1. e4 e5 2. Nf3" -> ["e2e4", "e7e5", "g1f3"]
    board = chess.Board()
    moves = []
    for word in pgn.split():
        if word.endswith("."):
            continue   # a move number
        move = board.push_san(word)
        moves.append(move.uci())
    return moves


def build():
    lines = read_lines()

    # counts["e2e4 e7e5"]["g1f3"] = how many named openings play Nf3 there
    counts = {}
    for pgn in lines:
        moves = to_uci(pgn)
        for i in range(len(moves)):
            key = " ".join(moves[:i])
            if key not in counts:
                counts[key] = {}
            if moves[i] not in counts[key]:
                counts[key][moves[i]] = 0
            counts[key][moves[i]] += 1

    # drop moves much rarer than the most common one in that position
    positions = {}
    for key, options in counts.items():
        most = max(options.values())
        kept = {}
        for move, count in options.items():
            if count >= MIN_SHARE * most:
                kept[move] = count
        positions[key] = kept

    book = {
        "source": "https://github.com/lichess-org/chess-openings (CC0-1.0)",
        "openings": len(lines),
        "positions": positions,
    }
    with open(BOOK_PATH, "w") as f:
        json.dump(book, f, sort_keys=True)
    print(f"{len(lines)} named openings -> {len(positions)} book positions, saved to {BOOK_PATH}")


if __name__ == "__main__":
    build()
