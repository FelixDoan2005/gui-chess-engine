"""Sanity checks that the engine makes obviously-correct moves.

Run from the project root:
    python tests/test_ai.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.ai import AI, CHECKMATE_SCORE, negamax, pawn_files, bishop_pair, BISHOP_PAIR_BONUS, game_phase
from ui.chess_logic import Board, piece_moves, get_all_legal_moves, in_check, draw_reason, insufficient_material


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


def test_bishop_pair_cancels_out_when_both_sides_have_it():
    assert bishop_pair(Board()) == 0


def test_bishop_pair_bonus_for_white_only():
    board = empty_board((7, 4), (0, 4), "white")
    board.grid[7][2] = "white_bishop"
    board.grid[7][5] = "white_bishop"
    board.grid[0][2] = "black_bishop"
    board.grid[0][1] = "black_knight"
    assert bishop_pair(board) == BISHOP_PAIR_BONUS["endgame"]


def test_bishop_pair_bonus_for_black_only():
    board = empty_board((7, 4), (0, 4), "black")
    board.grid[0][2] = "black_bishop"
    board.grid[0][5] = "black_bishop"
    assert bishop_pair(board) == -BISHOP_PAIR_BONUS["endgame"]


def test_game_phase_opening_at_start():
    assert game_phase(Board()) == "opening"


def test_game_phase_middlegame_after_move_15_with_queens():
    board = Board()
    board.ply = 30
    assert game_phase(board) == "middlegame"


def test_game_phase_endgame_when_little_material_left():
    board = empty_board((7, 4), (0, 4), "white")
    board.grid[7][0] = "white_rook"     # 2
    board.grid[7][1] = "white_knight"   # 1
    board.grid[0][0] = "black_rook"     # 2
    board.grid[0][2] = "black_bishop"   # 1  -> 6 total, <= 8
    assert game_phase(board) == "endgame"


def test_game_phase_queens_traded_early_is_not_endgame():
    board = Board()
    board.grid[7][3] = None   # white queen
    board.grid[0][3] = None   # black queen -> 24 - 8 = 16 left, > 8
    assert game_phase(board) == "opening"


def test_move_piece_counts_plies():
    board = Board()
    board.move_piece((6, 4), (4, 4))
    board.move_piece((1, 4), (3, 4))
    assert board.ply == 2


def test_threefold_repetition_is_a_draw():
    board = Board()
    knight_shuffle = [((7, 6), (5, 5)), ((0, 6), (2, 5)), ((5, 5), (7, 6)), ((2, 5), (0, 6))]
    for move in knight_shuffle:          # start position now seen twice
        board.move_piece(*move)
    assert draw_reason(board) is None
    for move in knight_shuffle:          # third time
        board.move_piece(*move)
    assert draw_reason(board) == "threefold repetition"


def test_halfmove_clock_resets_on_pawn_move_and_capture():
    board = Board()
    board.move_piece((7, 6), (5, 5))     # knight move
    assert board.halfmove_clock == 1
    board.move_piece((1, 4), (3, 4))     # pawn move
    assert board.halfmove_clock == 0
    board.move_piece((5, 5), (3, 4))     # knight takes pawn
    assert board.halfmove_clock == 0


def test_fifty_move_rule_is_a_draw():
    board = Board()
    board.halfmove_clock = 100
    assert draw_reason(board) == "50-move rule"


def test_insufficient_material():
    def grid_with(pieces):
        grid = [[None] * 8 for _ in range(8)]
        grid[7][4] = "white_king"
        grid[0][4] = "black_king"
        for (r, c), piece in pieces.items():
            grid[r][c] = piece
        return grid

    assert insufficient_material(grid_with({}))                                   # K v K
    assert insufficient_material(grid_with({(5, 5): "white_knight"}))            # KN v K
    assert insufficient_material(grid_with({(5, 5): "white_bishop",
                                            (2, 2): "black_bishop"}))            # same-colour bishops
    assert not insufficient_material(grid_with({(5, 5): "white_bishop",
                                                (2, 3): "black_bishop"}))        # opposite-colour bishops
    assert not insufficient_material(grid_with({(5, 5): "white_rook"}))          # KR v K can mate
    assert not insufficient_material(grid_with({(6, 0): "white_pawn"}))          # pawn can promote


def test_search_leaves_history_unchanged():
    board = Board()
    board.move_piece((6, 4), (4, 4))
    history_before = list(board.history)
    counts_before = dict(board.position_counts)
    AI().choose_move(board, piece_moves, 3)
    assert board.history == history_before
    assert {k: v for k, v in board.position_counts.items() if v} == counts_before




if __name__ == "__main__":
    tests = [value for name, value in list(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"PASS  {test.__name__}")
    print(f"\n{len(tests)} tests passed")
