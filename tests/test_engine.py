from engine.board import Board


def test_starting_position():
    board = Board()
    assert board.grid[0][0] == "black_rook"
    assert board.grid[7][4] == "white_king"
    assert board.grid[4][4] is None
