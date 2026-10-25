"""Checks for the UCI engine (engine/uci.py), the program the GUI talks to.

Run from the project root:
    python -m pytest tests/test_uci.py
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.uci import play_uci_move, move_to_uci, set_position, search_limits
from ui.chess_logic import Board, piece_moves, get_all_legal_moves

UCI_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engine", "uci.py")


def test_engine_answers_uci_commands():
    commands = "uci\nisready\nposition startpos moves e2e4\ngo depth 2\nquit\n"
    output = subprocess.run([sys.executable, UCI_PATH], input=commands, capture_output=True,
                            text=True, timeout=60).stdout
    lines = output.split("\n")
    assert "uciok" in lines
    assert "readyok" in lines

    # its move has to be one of black's legal replies to e4
    best = ""
    for line in lines:
        if line.startswith("bestmove"):
            best = line.split()[1]
    board = set_position(["position", "startpos", "moves", "e2e4"])
    legal = []
    for move in get_all_legal_moves(board, piece_moves):
        legal.append(move_to_uci(board, move))
    assert best in legal


def test_castling_en_passant_and_underpromotion():
    # castling: the rook comes across too
    board = set_position(["position", "startpos", "moves", "e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "g8f6", "e1g1"])
    assert board.grid[7][6] == "white_king"
    assert board.grid[7][5] == "white_rook"

    # en passant: the captured pawn disappears
    board = set_position(["position", "startpos", "moves", "e2e4", "a7a6", "e4e5", "d7d5", "e5d6"])
    assert board.grid[2][3] == "white_pawn"
    assert board.grid[3][3] is None

    # promotion to the piece in the 5th letter, even a knight
    board = Board()
    board.grid[1][0] = "white_pawn"
    board.grid[0][0] = None
    play_uci_move(board, "a7a8n")
    assert board.grid[0][0] == "white_knight"


def test_search_limits():
    board = Board()
    assert search_limits(["go", "depth", "3"], board) == (3, None)
    assert search_limits(["go", "movetime", "1500"], board)[1] == 1.5
    # a game clock: about 1/30 of white's time left, plus the increment
    depth, time_limit = search_limits(["go", "wtime", "60000", "btime", "60000", "winc", "1000"], board)
    assert abs(time_limit - (60 / 30 + 1)) < 1e-9
