import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.chess_logic import Board

# The starting position written out by hand (row 0 = rank 8, column 0 = file a),
# so the test doesn't just compare the code's STARTING_POSITION with itself.
BACK_RANK = ["rook", "knight", "bishop", "queen", "king", "bishop", "knight", "rook"]
EXPECTED = (
    [["black_" + piece for piece in BACK_RANK]]
    + [["black_pawn"] * 8]
    + [[None] * 8 for _ in range(4)]
    + [["white_pawn"] * 8]
    + [["white_" + piece for piece in BACK_RANK]]
)


def test_every_square_of_the_starting_position():
    board = Board()
    for row in range(8):
        for col in range(8):
            square = "abcdefgh"[col] + str(8 - row)
            assert board.grid[row][col] == EXPECTED[row][col], f"wrong piece on {square}"


def test_starting_state():
    board = Board()
    assert board.turn == "white"
    assert board.white_king == (7, 4)
    assert board.black_king == (0, 4)
    assert board.en_passant_ts is None
    assert board.halfmove_clock == 0
    # Nothing has moved yet, so all four castling options are still open.
    assert not board.white_king_moved
    assert not board.white_rook_kingside_moved
    assert not board.white_rook_queenside_moved
    assert not board.black_king_moved
    assert not board.black_rook_kingside_moved
    assert not board.black_rook_queenside_moved
