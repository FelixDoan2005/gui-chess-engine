"""Sanity checks that the engine makes obviously-correct moves.

Run from the project root:
    python tests/test_ai.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.ai import AI, CHECKMATE_SCORE, negamax, quiescence, game_phase, make_move, pawn_files, bishop_pair, BISHOP_PAIR_BONUS, piece_square_value, evaluate, mop_up, centre_distance
from engine.ai import pawn_structure
from engine.ai import king_pawn_shield, king_attackers
from engine.ai import endgame_weight, blend
from ui.chess_logic import Board, piece_moves, get_all_legal_moves, in_check, draw_reason, insufficient_material, select_piece


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


def test_quiescence_sees_checkmate():
    # back rank mate: black is in check, so it can't stand pat
    board = empty_board((7, 6), (0, 6), "black")
    board.grid[1][5] = "black_pawn"
    board.grid[1][6] = "black_pawn"
    board.grid[1][7] = "black_pawn"
    board.grid[0][4] = "white_rook"
    assert quiescence(board, piece_moves, -float("inf"), float("inf")) == -CHECKMATE_SCORE


def test_quiescence_sees_stalemate():
    # black is a queen down but stalemated, so it's a draw
    board = empty_board((1, 5), (0, 7), "black")
    board.grid[2][6] = "white_queen"
    assert quiescence(board, piece_moves, -float("inf"), float("inf")) == 0


def test_game_phase_counts_down_from_24():
    assert game_phase(Board()) == 24
    # only kings and pawns left
    board = empty_board((7, 4), (0, 4), "white")
    board.grid[6][0] = "white_pawn"
    assert game_phase(board) == 0


def test_time_limit_stops_the_search_in_time():
    # depth 10 would take far longer than half a second
    board = Board()
    start = time.time()
    move = AI().choose_move(board, piece_moves, 10, time_limit=0.5)
    took = time.time() - start
    assert move in get_all_legal_moves(board, piece_moves)
    assert took < 1.5


def test_time_limit_puts_the_board_back():
    # the search gets cut off in the middle of a line, with moves still made
    board = Board()
    grid_before = [row[:] for row in board.grid]
    history_before = list(board.history)
    counts_before = dict(board.position_counts)
    AI().choose_move(board, piece_moves, 10, time_limit=0.3)
    assert board.grid == grid_before
    assert board.history == history_before
    assert board.position_counts == counts_before
    assert board.turn == "white"


def test_check_extension_finds_mate_in_2_at_depth_2():
    # 1.Rg5+ then Ra8# or Rh4#: the mate is 3 moves deep, past depth 2,
    # found only because the check makes that line search 1 deeper
    board = empty_board((2, 4), (0, 6), "white")
    board.grid[3][7] = "white_rook"
    board.grid[4][0] = "white_rook"
    assert AI().choose_move(board, piece_moves, 2) == ((3, 7), (3, 6))


def test_black_promotion_does_not_crash_search():
    board = empty_board((7, 7), (0, 4), "black")
    board.grid[6][0] = "black_pawn"
    # Nothing can stop the pawn, and quiescence search sees it can promote
    # whenever it likes, so it may make one king move first. It must promote
    # within its next two moves.
    promoted = False
    for _ in range(4):
        make_move(board, *AI().choose_move(board, piece_moves, 3))
        if board.grid[7][0] == "black_queen":
            promoted = True
            break
    assert promoted

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
    expected = blend(BISHOP_PAIR_BONUS["middlegame"], BISHOP_PAIR_BONUS["endgame"], endgame_weight(board))
    assert close(bishop_pair(board), expected)


def test_bishop_pair_bonus_for_black_only():
    board = empty_board((7, 4), (0, 4), "black")
    board.grid[0][2] = "black_bishop"
    board.grid[0][5] = "black_bishop"
    expected = blend(BISHOP_PAIR_BONUS["middlegame"], BISHOP_PAIR_BONUS["endgame"], endgame_weight(board))
    assert close(bishop_pair(board), -expected)


def test_bishop_pair_matches_kaufman_at_each_stage():
    board = empty_board((7, 4), (0, 4), "white")
    board.grid[7][2] = "white_bishop"
    board.grid[7][5] = "white_bishop"
    assert close(bishop_pair(board, 0.0), 0.3)   # middlegame
    assert close(bishop_pair(board, 0.5), 0.4)   # in between
    assert close(bishop_pair(board, 1.0), 0.5)   # endgame


def test_endgame_weight():
    assert endgame_weight(Board()) == 0                  # all pieces on

    board = Board()
    board.grid[7][3] = None                              # white queen
    board.grid[0][3] = None                              # black queen
    assert close(endgame_weight(board), 8 / 24)          # queens gone: 16 of 24 left

    board = empty_board((7, 4), (0, 4), "white")
    board.grid[7][0] = "white_rook"                      # 2
    board.grid[7][1] = "white_knight"                    # 1
    board.grid[0][0] = "black_rook"                      # 2
    board.grid[0][2] = "black_bishop"                    # 1 -> 6 of 24 left
    assert close(endgame_weight(board), 18 / 24)

    assert endgame_weight(empty_board((7, 4), (0, 4), "white")) == 1   # kings only


def test_king_table_blends_towards_centre():
    centre, corner = (4, 4), (7, 6)
    # Middlegame (weight 0): corner (castled) beats centre.
    assert piece_square_value("king", "white", *corner, 0.0) > piece_square_value("king", "white", *centre, 0.0)
    # Endgame (weight 1): centre beats corner.
    assert piece_square_value("king", "white", *centre, 1.0) > piece_square_value("king", "white", *corner, 1.0)
    # Same for black, whose table is read with the row flipped.
    assert piece_square_value("king", "black", 3, 3, 1.0) > piece_square_value("king", "black", 0, 6, 1.0)


def test_evaluate_rewards_central_king_in_endgame():
    def rook_endgame(white_king):
        board = empty_board(white_king, (0, 0), "white")
        board.grid[7][0] = "white_rook"
        board.grid[0][7] = "black_rook"
        return board

    assert endgame_weight(rook_endgame((4, 4))) > 0.5
    assert evaluate(rook_endgame((4, 4))) > evaluate(rook_endgame((7, 7)))


def test_centre_distance():
    assert centre_distance(3, 3) == 0
    assert centre_distance(4, 4) == 0
    assert centre_distance(0, 0) == 6
    assert centre_distance(7, 7) == 6


def test_mop_up_rewards_cornering_the_losing_king():
    def rook_vs_king(white_king, black_king):
        board = empty_board(white_king, black_king, "white")
        board.grid[7][0] = "white_rook"
        return board

    # Black king in the corner scores better for White than in the centre.
    assert mop_up(rook_vs_king((5, 5), (0, 7))) > mop_up(rook_vs_king((5, 5), (3, 3)))
    # White king closer to the black king scores better than further away.
    assert mop_up(rook_vs_king((2, 5), (0, 7))) > mop_up(rook_vs_king((7, 3), (0, 7)))


def test_mop_up_is_negative_when_black_is_winning():
    board = empty_board((7, 7), (4, 4), "black")
    board.grid[0][0] = "black_queen"
    assert mop_up(board) < 0


def test_mop_up_off_with_pawns_or_close_material():
    board = empty_board((7, 4), (0, 7), "white")
    board.grid[7][0] = "white_rook"
    board.grid[1][0] = "black_pawn"
    assert mop_up(board) == 0          # pawns on the board

    board = empty_board((7, 4), (0, 7), "white")
    board.grid[7][0] = "white_rook"
    board.grid[0][0] = "black_rook"
    assert mop_up(board) == 0          # nobody is clearly winning


def king_legal_moves(board, colour):
    if colour == "white":
        square = board.white_king
    else:
        square = board.black_king
    _, moves = select_piece(square, f"{colour}_king", board, piece_moves)
    return moves


def test_castling_still_works_normally():
    board = Board()
    board.grid[7][5] = None   # clear f1
    board.grid[7][6] = None   # clear g1
    assert (7, 6) in king_legal_moves(board, "white")

    board.move_piece((7, 4), (7, 6))
    assert board.grid[7][6] == "white_king"
    assert board.grid[7][5] == "white_rook"
    assert board.grid[7][7] is None


def test_cannot_castle_after_rook_captured_at_home():
    board = empty_board((7, 4), (0, 4), "black")
    board.grid[7][7] = "white_rook"
    board.grid[5][6] = "black_knight"
    board.move_piece((5, 6), (7, 7))   # knight takes the rook on h1 before it ever moved

    assert board.white_rook_kingside_moved      # castling right gone
    assert (7, 6) not in king_legal_moves(board, "white")


def test_cannot_castle_with_no_rook_in_the_corner():
    board = empty_board((7, 4), (0, 4), "white")   # castling flags untouched, but no rooks
    moves = king_legal_moves(board, "white")
    assert (7, 6) not in moves
    assert (7, 2) not in moves


def test_black_loses_castling_when_rook_captured_at_home():
    board = empty_board((7, 4), (0, 4), "white")
    board.grid[0][0] = "black_rook"
    board.grid[2][1] = "white_knight"
    board.move_piece((2, 1), (0, 0))   # knight takes the rook on a8

    assert board.black_rook_queenside_moved
    board.move_piece((7, 4), (7, 3))   # any white move, so it's black's turn
    assert (0, 2) not in king_legal_moves(board, "black")


def test_passed_pawn_bonus_grows_as_it_advances():
    def lone_white_pawn(row):
        board = empty_board((7, 4), (0, 4), "white")
        board.grid[row][2] = "white_pawn"
        return board

    scores = [pawn_structure(lone_white_pawn(row)) for row in (6, 5, 4, 3, 2, 1)]
    assert scores == sorted(scores)          # never shrinks as it advances
    assert scores[-1] > scores[0]            # and is bigger near promotion


def close(a, b):
    return abs(a - b) < 1e-9


def test_king_pawn_shield():
    board = Board()
    assert king_pawn_shield(board) == 0             # both shields intact

    board.grid[7][4] = None                         # "castle" the white king to g1
    board.grid[7][6] = "white_king"
    board.white_king = (7, 6)
    assert king_pawn_shield(board) == 0             # f2, g2, h2 all home

    board.grid[6][6] = None
    board.grid[5][6] = "white_pawn"                 # g-pawn one step up: 11, doubled on the king's file
    assert close(king_pawn_shield(board), -0.22)

    board.grid[5][6] = None                         # g-pawn gone: 36, doubled
    assert close(king_pawn_shield(board), -0.72)

    board.grid[0][3] = None                         # black queen gone: 8/12 of black's attackers left
    assert close(king_pawn_shield(board), -0.72 * 8 / 12)


def test_king_can_step_in_front_of_enemy_pawn():
    board = empty_board((5, 4), (0, 0), "white")   # white king e3
    board.grid[3][4] = "black_pawn"                  # black pawn e5 attacks d4 and f4, not e4
    moves = king_legal_moves(board, "white")
    assert (4, 4) in moves          # e4: legal, pawns don't attack straight ahead
    assert (4, 3) not in moves      # d4: attacked by the pawn
    assert (4, 5) not in moves      # f4: attacked by the pawn


def test_cannot_castle_through_square_attacked_by_pawn():
    board = Board()
    board.grid[7][5] = None          # clear f1
    board.grid[7][6] = None          # clear g1
    board.grid[6][4] = "black_pawn"  # black pawn on e2 attacks d1 and f1
    board.turn = "white"
    assert (7, 6) not in king_legal_moves(board, "white")   # O-O would pass through f1


def test_pawn_gives_check_diagonally_not_straight():
    board = empty_board((7, 4), (0, 0), "white")
    board.grid[6][3] = "black_pawn"                   # d2 attacks e1
    assert in_check(board.grid, "white", (7, 4))

    board.grid[6][3] = None
    board.grid[6][4] = "black_pawn"                   # e2, straight in front of the king
    assert not in_check(board.grid, "white", (7, 4))


def test_king_attackers():
    board = empty_board((7, 6), (0, 0), "white")   # white king g1, black king a8
    board.grid[4][3] = "black_queen"               # d4 queen aims at f2 (4 units)
    board.grid[3][7] = "black_rook"                # h5 rook aims at h2 (2 units)
    board.grid[7][0] = "white_queen"               # a single white attacker on a8: counts 0
    # 2 attackers: (4 + 2) units * 20 * 128/256 = 60 centipawns, in the full middlegame
    assert close(king_attackers(board, 0.0), -0.60)
    # ...fading out towards the endgame (middlegame-only in Fruit)
    assert close(king_attackers(board), -0.60 * (1 - endgame_weight(board)))

    board.grid[3][7] = None
    board.grid[0][7] = "black_knight"              # h8 knight, not aimed at g1
    assert king_attackers(board, 0.0) == 0         # one attacker alone counts 0


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
