"""Sanity checks that the engine makes obviously-correct moves.

Run from the project root:
    python tests/test_ai.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.ai import AI, CHECKMATE_SCORE, negamax, pawn_files
from ui.chess_logic import Board, piece_moves, get_all_legal_moves, in_check


def empty_board(white_king, black_king, turn):
    board = Board()
    board.grid = [[None] * 8 for _ in range(8)]
    board.grid[white_king[0]][white_king[1]] = "white_king"
    board.grid[black_king[0]][black_king[1]] = "black_king"
    board.white_king = white_king
    board.black_king = black_king
    board.turn = turn
    return board


def test_starting_position_returns_a_move():
    assert AI().choose_move(Board(), piece_moves, 2) is not None


def test_captures_hanging_queen():
    board = empty_board((7, 4), (0, 4), "white")
    board.grid[5][3] = "white_knight"
    board.grid[3][4] = "black_queen"
    assert AI().choose_move(board, piece_moves, 2) == ((5, 3), (3, 4))


def test_finds_back_rank_mate_in_one():
    board = empty_board((7, 4), (0, 7), "white")
    board.grid[1][7] = "black_pawn"
    board.grid[1][6] = "black_pawn"
    board.grid[5][0] = "white_rook"

    assert negamax(board, piece_moves, 2, -float("inf"), float("inf")) == CHECKMATE_SCORE
    move = AI().choose_move(board, piece_moves, 2)
    assert move == ((5, 0), (0, 0))

    board.move_piece(*move)
    assert in_check(board.grid, "black", board.black_king)
    assert get_all_legal_moves(board, piece_moves) == []


def test_black_promotion_does_not_crash_search():
    board = empty_board((7, 7), (0, 4), "black")
    board.grid[6][0] = "black_pawn"
    assert AI().choose_move(board, piece_moves, 3) == ((6, 0), (7, 0))

def test_pawn_files_ignores_other_colour_and_other_pieces():
    grid = [[None] * 8 for _ in range(8)]
    grid[6][4] = "white_pawn"
    grid[1][4] = "black_pawn"
    grid[5][2] = "white_knight"
    assert pawn_files(grid, "white") == {4: [6]}




if __name__ == "__main__":
    tests = [value for name, value in list(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"PASS  {test.__name__}")
    print(f"\n{len(tests)} tests passed")
