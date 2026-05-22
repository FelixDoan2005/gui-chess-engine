import pygame

pygame.init()

WIDTH, HEIGHT = 800, 800
SQUARE_SIZE = WIDTH // 10
OFF_SET = 78

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Chess Engine")

board_image = pygame.image.load("images/board.png")
board_image = pygame.transform.scale(board_image, (WIDTH, HEIGHT))

PIECE_NAMES = [
    "white_king", "white_queen", "white_rook", "white_knight", "white_bishop", "white_pawn",
    "black_king", "black_queen", "black_rook", "black_knight", "black_bishop", "black_pawn",
]
pieces = {}
for name in PIECE_NAMES:
    img = pygame.image.load(f"images/{name}.png")
    pieces[name] = pygame.transform.scale(img, (SQUARE_SIZE, SQUARE_SIZE))

# Board is an 8x8 list, row 0 = top (rank 8), row 7 = bottom (rank 1)
board = [
    ["black_rook", "black_knight", "black_bishop", "black_queen", "black_king", "black_bishop", "black_knight", "black_rook"],
    ["black_pawn"] * 8,
    [None] * 8,
    [None] * 8,
    [None] * 8,
    [None] * 8,
    ["white_pawn"] * 8,
    ["white_rook", "white_knight", "white_bishop", "white_queen", "white_king", "white_bishop", "white_knight", "white_rook"],
]

def draw_board():
    screen.blit(board_image, (0, 0))
    for row in range(8):
        for col in range(8):
            piece = board[row][col]
            if piece:
                screen.blit(pieces[piece], (col * SQUARE_SIZE + OFF_SET, row * SQUARE_SIZE + OFF_SET))

clock = pygame.time.Clock()

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    draw_board()
    pygame.display.flip()
    clock.tick(60)

pygame.quit()
