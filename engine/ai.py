from ui.chess_logic import get_all_legal_moves, select_piece, in_check

CHECKMATE_SCORE = 999999

def evaluate(board):
    pieces = {
        "pawn": 1,
        "bishop": 3,
        "knight": 3,
        "rook": 5,
        "queen": 9,
        "king": 100
    }

    score = 0

    for r in range(8):
        for c in range(8):
            piece = board.grid[r][c]
            if piece is not None:
                value = pieces[piece.split("_")[1]]
                if piece.startswith("white"):
                    score += value
                else:
                    score -= value

    return score


# NOTE: negamax needs get_all_legal_moves(board, piece_moves), which currently
# lives in main.py. Since main.py shouldn't really be imported as a module,
# consider moving get_all_legal_moves (and select_piece) into chess_logic.py
# so both main.py and engine/ai.py can import it from there.

def save_state(board):
    grid_copy = []
    for row in board.grid:
        grid_copy.append(row[:])

    return {
        "grid": grid_copy,
        "turn": board.turn,
        "en_passant_ts": board.en_passant_ts,
        "white_king": board.white_king,
        "black_king": board.black_king,
        "white_king_moved": board.white_king_moved,
        "white_rook_kingside_moved": board.white_rook_kingside_moved,
        "white_rook_queenside_moved": board.white_rook_queenside_moved,
        "black_king_moved": board.black_king_moved,
        "black_rook_kingside_moved": board.black_rook_kingside_moved,
        "black_rook_queenside_moved": board.black_rook_queenside_moved,
    }


def restore_state(board, state):
    board.grid = state["grid"]
    board.turn = state["turn"]
    board.en_passant_ts = state["en_passant_ts"]
    board.white_king = state["white_king"]
    board.black_king = state["black_king"]
    board.white_king_moved = state["white_king_moved"]
    board.white_rook_kingside_moved = state["white_rook_kingside_moved"]
    board.white_rook_queenside_moved = state["white_rook_queenside_moved"]
    board.black_king_moved = state["black_king_moved"]
    board.black_rook_kingside_moved = state["black_rook_kingside_moved"]
    board.black_rook_queenside_moved = state["black_rook_queenside_moved"]


def negamax(board, piece_moves, depth, alpha, beta):
    # TODO base case: if depth == 0, return evaluate(board) from the
    # perspective of the side to move (flip the sign when board.turn == "black")
    if depth == 0:
        if board.turn == "white":
            return evaluate(board)
        else:
            return -evaluate(board)
    
    # TODO: get every legal move for board.turn
    moves = get_all_legal_moves(board, piece_moves)  # returns destination squares only right now —
    #                                                     # you'll need (from_sq, to_sq) pairs to actually replay moves

    if len(moves) == 0:
        king_pos = board.white_king if board.turn == "white" else board.black_king
        if in_check(board.grid, board.turn, king_pos):
            return -CHECKMATE_SCORE
        return 0
    for (from_sq, to_sq) in moves:
        state = save_state(board)
        board.move_piece(from_sq, to_sq)
        score = -negamax(board, piece_moves, depth - 1, -beta, -alpha)
        restore_state(board, state)

        if score >= beta:
            return beta
        if score > alpha:
            alpha = score

    return alpha


class AI:
    def choose_move(self, board, piece_moves, depth=2):
        # TODO: like negamax's loop, but instead of just tracking the best score,
        # also remember which (from_sq, to_sq) produced it, and return that move.
        moves = get_all_legal_moves(board, piece_moves)
        alpha = -float('inf')
        beta = float('inf')
        best_move = None
        for (from_sq, to_sq) in moves:
            state = save_state(board)
            board.move_piece(from_sq, to_sq)
            score = -negamax(board, piece_moves, depth - 1, -beta, -alpha)
            restore_state(board, state)
            if score > alpha:
                alpha = score
                best_move = (from_sq, to_sq)
        return best_move


