from ui.chess_logic import get_all_legal_moves, select_piece, in_check

CHECKMATE_SCORE = 999999

# Difficulty level -> search depth. One level per depth for now; each
# level will also toggle a specific evaluation feature on/off later.
DIFFICULTY_DEPTH = {
    1: 1,
    2: 2,
    3: 3,
    4: 4,
    5: 5,
}

# Piece-square tables: from https://chessprogramming.org/Simplified_Evaluation_Function
# posted by Tomasz Michniewski
PAWN_TABLE = [
    [0,   0,   0,   0,   0,   0,   0,   0],
    [50, 50,  50,  50,  50,  50,  50,  50],
    [10, 10,  20,  30,  30,  20,  10,  10],
    [5,   5,  10,  25,  25,  10,   5,   5],
    [0,   0,   0,  20,  20,   0,   0,   0],
    [5,  -5, -10,   0,   0, -10,  -5,   5],
    [5,  10,  10, -20, -20,  10,  10,   5],
    [0,   0,   0,   0,   0,   0,   0,   0],
]

KNIGHT_TABLE = [
    [-50, -40, -30, -30, -30, -30, -40, -50],
    [-40, -20,   0,   0,   0,   0, -20, -40],
    [-30,   0,  10,  15,  15,  10,   0, -30],
    [-30,   5,  15,  20,  20,  15,   5, -30],
    [-30,   0,  15,  20,  20,  15,   0, -30],
    [-30,   5,  10,  15,  15,  10,   5, -30],
    [-40, -20,   0,   5,   5,   0, -20, -40],
    [-50, -40, -30, -30, -30, -30, -40, -50],
]

BISHOP_TABLE = [
    [-20, -10, -10, -10, -10, -10, -10, -20],
    [-10,   0,   0,   0,   0,   0,   0, -10],
    [-10,   0,   5,  10,  10,   5,   0, -10],
    [-10,   5,   5,  10,  10,   5,   5, -10],
    [-10,   0,  10,  10,  10,  10,   0, -10],
    [-10,  10,  10,  10,  10,  10,  10, -10],
    [-10,   5,   0,   0,   0,   0,   5, -10],
    [-20, -10, -10, -10, -10, -10, -10, -20],
]

ROOK_TABLE = [
    [0,   0,   0,   0,   0,   0,   0,   0],
    [5,  10,  10,  10,  10,  10,  10,   5],
    [-5,  0,   0,   0,   0,   0,   0,  -5],
    [-5,  0,   0,   0,   0,   0,   0,  -5],
    [-5,  0,   0,   0,   0,   0,   0,  -5],
    [-5,  0,   0,   0,   0,   0,   0,  -5],
    [-5,  0,   0,   0,   0,   0,   0,  -5],
    [0,   0,   0,   5,   5,   0,   0,   0],
]

QUEEN_TABLE = [
    [-20, -10, -10,  -5,  -5, -10, -10, -20],
    [-10,   0,   0,   0,   0,   0,   0, -10],
    [-10,   0,   5,   5,   5,   5,   0, -10],
    [-5,    0,   5,   5,   5,   5,   0,  -5],
    [0,     0,   5,   5,   5,   5,   0,  -5],
    [-10,   5,   5,   5,   5,   5,   0, -10],
    [-10,   0,   5,   0,   0,   0,   0, -10],
    [-20, -10, -10,  -5,  -5, -10, -10, -20],
]

KING_TABLE = [
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-20, -30, -30, -40, -40, -30, -30, -20],
    [-10, -20, -20, -20, -20, -20, -20, -10],
    [20,   20,   0,   0,   0,   0,  20,  20],
    [20,   30,  10,   0,   0,  10,  30,  20],
]

PIECE_SQUARE_TABLES = {
    "pawn": PAWN_TABLE,
    "knight": KNIGHT_TABLE,
    "bishop": BISHOP_TABLE,
    "rook": ROOK_TABLE,
    "queen": QUEEN_TABLE,
    "king": KING_TABLE,
}


def piece_square_value(kind, colour, row, col):
    table = PIECE_SQUARE_TABLES[kind]
    if colour == "white":
        return table[row][col]
    return table[7 - row][col]


PIECE_VALUES = {
    "pawn": 1,
    "bishop": 3,
    "knight": 3,
    "rook": 5,
    "queen": 9,
    "king": 100
}


def evaluate(board):
    score = 0

    for r in range(8):
        for c in range(8):
            piece = board.grid[r][c]
            if piece is not None:
                colour, kind = piece.split("_")
                value = PIECE_VALUES[kind]
                positional = piece_square_value(kind, colour, r, c) / 100

                total_gain = value + positional

                if colour == "white":
                    score += total_gain
                else:
                    score -= total_gain

    return score


def order_moves(board, moves):
    def capture_value(move):
        _, to_sq = move
        target = board.get_piece(*to_sq)
        if target is None:
            return 0
        return PIECE_VALUES[target.split("_")[1]]

    return sorted(moves, key=capture_value, reverse=True)

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
    if depth == 0:
        if board.turn == "white":
            return evaluate(board)
        else:
            return -evaluate(board)
    
    moves = get_all_legal_moves(board, piece_moves)

    if len(moves) == 0:
        king_pos = board.white_king if board.turn == "white" else board.black_king
        if in_check(board.grid, board.turn, king_pos):
            return -CHECKMATE_SCORE
        return 0
    for (from_sq, to_sq) in order_moves(board, moves):
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
    def choose_move(self, board, piece_moves, depth):
        moves = get_all_legal_moves(board, piece_moves)
        alpha = -float('inf')
        beta = float('inf')
        best_move = None
        for (from_sq, to_sq) in order_moves(board, moves):
            state = save_state(board)
            board.move_piece(from_sq, to_sq)
            score = -negamax(board, piece_moves, depth - 1, -beta, -alpha)
            restore_state(board, state)
            if score > alpha:
                alpha = score
                best_move = (from_sq, to_sq)
        return best_move


