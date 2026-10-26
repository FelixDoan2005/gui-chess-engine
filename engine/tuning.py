"""The evaluation numbers Texel tuning adjusts, and how to read and set them.

Used by tests/tuning (the tuning itself), and by engine/uci.py, which loads
tuned numbers from a file when the ENGINE_PARAMS setting points at one.
"""
import json

# (constant in engine/ai.py, the key inside it, or None for a plain number).
# The pawn stays at 1, so every other number keeps its meaning "in pawns".
PARAMS = [
    ("PIECE_VALUES", "knight"),
    ("PIECE_VALUES", "bishop"),
    ("PIECE_VALUES", "rook"),
    ("PIECE_VALUES", "queen"),
    ("MOBILITY_WEIGHTS", "knight"),
    ("MOBILITY_WEIGHTS", "bishop"),
    ("MOBILITY_WEIGHTS", "rook"),
    ("MOBILITY_WEIGHTS", "queen"),
    ("MOBILITY_WEIGHTS_ENDGAME", "knight"),
    ("MOBILITY_WEIGHTS_ENDGAME", "bishop"),
    ("MOBILITY_WEIGHTS_ENDGAME", "rook"),
    ("MOBILITY_WEIGHTS_ENDGAME", "queen"),
    ("DOUBLED_PAWN_PENALTY", "middlegame"),
    ("DOUBLED_PAWN_PENALTY", "endgame"),
    ("ISOLATED_PAWN_PENALTY", "middlegame"),
    ("ISOLATED_PAWN_PENALTY", "endgame"),
    ("ISOLATED_OPEN_PAWN_PENALTY", "middlegame"),
    ("ISOLATED_OPEN_PAWN_PENALTY", "endgame"),
    ("PASSED_PAWN_MIN", "middlegame"),
    ("PASSED_PAWN_MIN", "endgame"),
    ("PASSED_PAWN_MAX", "middlegame"),
    ("PASSED_PAWN_MAX", "endgame"),
    ("BISHOP_PAIR_BONUS", "middlegame"),
    ("BISHOP_PAIR_BONUS", "endgame"),
    ("KING_ATTACK_OPENING", None),
]


def param_name(param):
    name, key = param
    if key is None:
        return name
    return f"{name}[{key}]"


def get_params(ai):
    values = []
    for name, key in PARAMS:
        if key is None:
            values.append(getattr(ai, name))
        else:
            values.append(getattr(ai, name)[key])
    return values


def set_params(ai, values):
    for i in range(len(PARAMS)):
        name, key = PARAMS[i]
        if key is None:
            setattr(ai, name, values[i])
        else:
            getattr(ai, name)[key] = values[i]


def load_params(ai, path):
    # a file saved by the tuning: {"after": [the tuned numbers, in PARAMS order], ...}
    with open(path) as f:
        saved = json.load(f)
    set_params(ai, saved["after"])
