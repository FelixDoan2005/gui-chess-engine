import pygame
from ui.constants import WIDTH, HEIGHT, SQUARE_SIZE, OFFSET, BOARD_IMAGE_PATH, PIECES_DIR, PIECE_NAMES

class Renderer:
    def __init__(self, screen):
        self.screen = screen
        self.board_image = pygame.transform.scale(
            pygame.image.load(BOARD_IMAGE_PATH), (WIDTH, HEIGHT)
        )
        self.pieces = {
            name: pygame.transform.scale(
                pygame.image.load(f"{PIECES_DIR}/{name}.png"), (SQUARE_SIZE, SQUARE_SIZE)
            )
            for name in PIECE_NAMES
        }

    def draw(self, grid):
        self.screen.blit(self.board_image, (0, 0))
        for row in range(8):
            for col in range(8):
                piece = grid[row][col]
                if piece:
                    x = col * SQUARE_SIZE + OFFSET
                    y = row * SQUARE_SIZE + OFFSET
                    self.screen.blit(self.pieces[piece], (x, y))
