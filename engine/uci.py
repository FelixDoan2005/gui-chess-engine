"""UCI engine: lets the GUI (and other chess programs) talk to this engine
through text commands, the Universal Chess Interface that Stockfish uses too.
That way the engine runs as its own program, on PyPy if it's installed (about
3x faster), while the pygame GUI stays on normal Python.

    python engine/uci.py        (or: pypy engine/uci.py)

Understands: uci, isready, ucinewgame, position startpos [moves ...],
go [depth n] [movetime ms] [wtime ms btime ms winc ms binc ms], quit
"""
import os
import shutil
import sys

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(ENGINE_DIR))

import engine.ai as ai_module
from engine.ai import AI
from engine.tuning import load_params
from ui.chess_logic import Board, piece_moves

MAX_DEPTH = 20  # when there's only a time limit, the time decides
PROMOTION_PIECES = {"q": "queen", "r": "rook", "b": "bishop", "n": "knight"}


def engine_command():
    # the command that starts this engine: on PyPy if it's on the PATH (or
    # PYPY_PATH points at it), otherwise on the Python running this code
    python = sys.executable
    pypy_path = os.environ.get("PYPY_PATH")
    if pypy_path is not None and os.path.exists(pypy_path):
        python = pypy_path
    else:
        for name in ("pypy3", "pypy"):
            found = shutil.which(name)
            if found is not None:
                python = found
                break
    return [python, os.path.join(ENGINE_DIR, "uci.py")]


def stockfish_path():
    # the STOCKFISH_PATH setting if it's set, otherwise "stockfish" on the PATH
    # (None if it can't be found): used by Engine vs Stockfish and the rating test
    path = os.environ.get("STOCKFISH_PATH")
    if path is not None and os.path.exists(path):
        return path
    return shutil.which("stockfish")


def square_name(square):
    row, col = square
    return "abcdefgh"[col] + str(8 - row)


def square_from_name(name):
    col = "abcdefgh".index(name[0])
    row = 8 - int(name[1])
    return (row, col)


def move_to_uci(board, move):
    from_sq, to_sq = move
    uci = square_name(from_sq) + square_name(to_sq)
    # the engine always promotes to a queen
    piece = board.grid[from_sq[0]][from_sq[1]]
    if piece.endswith("pawn") and to_sq[0] in (0, 7):
        uci += "q"
    return uci


def play_uci_move(board, uci):
    # e.g. e2e4, or e7e8q: the 5th letter is the piece a pawn promotes to
    colour = board.turn
    from_sq = square_from_name(uci[0:2])
    to_sq = square_from_name(uci[2:4])
    board.move_piece(from_sq, to_sq)
    if len(uci) == 5:
        board.grid[to_sq[0]][to_sq[1]] = colour + "_" + PROMOTION_PIECES[uci[4]]


def set_position(words):
    # position startpos moves e2e4 e7e5 ...
    board = Board()
    if "moves" in words:
        start = words.index("moves") + 1
        for uci in words[start:]:
            play_uci_move(board, uci)
    return board


def search_limits(words, board):
    # returns (depth, time limit in seconds or None)
    depth = MAX_DEPTH
    time_limit = None
    for i in range(len(words) - 1):
        if words[i] == "depth":
            depth = int(words[i + 1])
        elif words[i] == "movetime":
            time_limit = int(words[i + 1]) / 1000

    # a game clock: use about 1/30 of the time left, plus the increment
    if time_limit is None:
        if board.turn == "white":
            clock_word = "wtime"
            increment_word = "winc"
        else:
            clock_word = "btime"
            increment_word = "binc"
        if clock_word in words:
            time_left = int(words[words.index(clock_word) + 1]) / 1000
            increment = 0
            if increment_word in words:
                increment = int(words[words.index(increment_word) + 1]) / 1000
            time_limit = time_left / 30 + increment
    return depth, time_limit


def load_tuned_params():
    # tuned evaluation numbers, if the ENGINE_PARAMS setting points at a file
    # saved by the tuning (tests/tuning); otherwise the ones in engine/ai.py
    path = os.environ.get("ENGINE_PARAMS")
    if path is not None and os.path.exists(path):
        load_params(ai_module, path)
        return True
    return False


def main():
    load_tuned_params()
    board = Board()
    ai = AI()
    while True:
        line = sys.stdin.readline()
        if line == "":
            break  # the program that started us has gone
        words = line.split()
        if len(words) == 0:
            continue

        command = words[0]
        if command == "uci":
            print("id name Felis")
            print("id author Felix Doan") # me hehe
            print("uciok", flush=True)
        elif command == "isready":
            print("readyok", flush=True)
        elif command == "ucinewgame":
            board = Board()
            ai.new_game()
        elif command == "position":
            board = set_position(words)
        elif command == "go":
            depth, time_limit = search_limits(words, board)
            # keep what earlier moves in this game worked out
            move = ai.choose_move(board, piece_moves, depth, time_limit=time_limit, keep_table=True)
            if move is None:
                print("bestmove 0000", flush=True)  # no legal moves
            else:
                print("bestmove " + move_to_uci(board, move), flush=True)
        elif command == "quit":
            break


if __name__ == "__main__":
    main()
