WIDTH = 800
HEIGHT = 800
SQUARE_SIZE = 80
OFFSET = 80   # board squares start at pixel (80, 80)
FPS = 60

BOARD_IMAGE_PATH = "assets/images/board.png"
PIECES_DIR = "assets/images/pieces"

PIECES = [
    "white_king", "white_queen", "white_rook", "white_knight", "white_bishop", "white_pawn",
    "black_king", "black_queen", "black_rook", "black_knight", "black_bishop", "black_pawn",
]

# SQUARES[(row, col)] = (x, y) top-left pixel of each square
# row 0 = rank 8 (black back rank), row 7 = rank 1 (white back rank)
SQUARES = {
    (row, col): (OFFSET + col * SQUARE_SIZE, OFFSET + row * SQUARE_SIZE)
    for row in range(8)
    for col in range(8)
}


