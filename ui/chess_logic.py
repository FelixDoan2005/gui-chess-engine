from ui.constants import OFFSET, SQUARE_SIZE

STARTING_POSITION = [
    ["black_rook", "black_knight", "black_bishop", "black_queen", "black_king", "black_bishop", "black_knight", "black_rook"],
    ["black_pawn"] * 8,
    [None] * 8,
    [None] * 8,
    [None] * 8,
    [None] * 8,
    ["white_pawn"] * 8,
    ["white_rook", "white_knight", "white_bishop", "white_queen", "white_king", "white_bishop", "white_knight", "white_rook"],
]

def pixel_to_square(x, y):
    col = (x - OFFSET) // SQUARE_SIZE
    row = (y - OFFSET) // SQUARE_SIZE
    if 0 <= row < 8 and 0 <= col < 8:
        return (row, col)
    return None

class Board:
    def __init__(self):
        self.grid = [row[:] for row in STARTING_POSITION]
        self.turn = "white"

    def get_piece(self, row, col):
        return self.grid[row][col]

    def move_piece(self, from_sq, to_sq):
        fr, fc = from_sq
        tr, tc = to_sq
        self.grid[tr][tc] = self.grid[fr][fc]
        self.grid[fr][fc] = None
        self.turn = "black" if self.turn == "white" else "white"

def legal_moves(grid):
    for row in range(8):
        for col in range(8):
            if grid[row][col] == "white_pawn":
                moves = pawn_moves(row, col, grid, "white")
                print(f"Pawn at ({row}, {col}) can move to: {moves}")

def pawn_moves(row, col, grid, colour):
    moves = []
    if colour == 'white':
        direction = -1
    else:
        direction = 1

    one_step = row + direction
    two_steps = row + direction * 2

    square_in_front = grid[one_step][col]
    square_two_ahead = grid[two_steps][col]
    squares_in_left_diagonal = grid[one_step][col-1]
    squares_in_right_diagonal = grid[one_step][col+1]

    # move forward 1
    if square_in_front == None:
        moves.append((one_step, col))

        # move forward 2 from starting row
        if row == 6 and colour == 'white' and square_two_ahead == None:
            moves.append((two_steps, col))

        if row == 1 and colour == 'black' and square_two_ahead == None:
            moves.append((two_steps, col))

    #captures
    if squares_in_left_diagonal is not None and not grid[one_step][col-1].startswith(colour):
        moves.append((one_step, col-1))
    if squares_in_right_diagonal is not None and not grid[one_step][col+1].startswith(colour):
        moves.append((one_step, col+1))

    return moves

def knight_moves(row, col, grid, colour):
    moves = []
    jumps = [
        (-2, -1), (-2, +1),  # two up, one side
        (+2, -1), (+2, +1),  # two down, one side
        (-1, -2), (-1, +2),  # one up, two side
        (+1, -2), (+1, +2),  # one down, two side
    ]
    for jump_row, jump_col in jumps:

        if 0 <= (row + jump_row) <= 7 and 0 <= col + jump_col <= 7:
            landing_row = row + jump_row
            landing_col = col + jump_col
            landing_piece = grid[landing_row][landing_col]
            if landing_piece is None or not landing_piece.startswith(colour):
                moves.append((landing_row,landing_col))

    return moves

def bishop_moves(row, col, grid, colour):
    moves = []

    # down-right
    for i in range(1, 8):
        if 0 <= row + i <= 7 and 0 <= col + i <= 7:
            piece = grid[row+i][col+i]
            if piece is None:
                moves.append((row+i, col+i))
            elif not piece.startswith(colour):
                moves.append((row+i, col+i))
                break
            else:
                break

    # down-left
    for i in range(1, 8):
        if 0 <= row + i <= 7 and 0 <= col - i <= 7:
            piece = grid[row+i][col-i]
            if piece is None:
                moves.append((row+i, col-i))
            elif not piece.startswith(colour):
                moves.append((row+i, col-i))
                break
            else:
                break

    # up-right
    for i in range(1, 8):
        if 0 <= row - i <= 7 and 0 <= col + i <= 7:
            piece = grid[row-i][col+i]
            if piece is None:
                moves.append((row-i, col+i))
            elif not piece.startswith(colour):
                moves.append((row-i, col+i))
                break
            else:
                break

    # up-left
    for i in range(1, 8):
        if 0 <= row - i <= 7 and 0 <= col - i <= 7:
            piece = grid[row-i][col-i]
            if piece is None:
                moves.append((row-i, col-i))
            elif not piece.startswith(colour):
                moves.append((row-i, col-i))
                break
            else:
                break

    return moves