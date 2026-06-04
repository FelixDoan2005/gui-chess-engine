import pygame
from ui.constants import WIDTH, HEIGHT, SQUARE_SIZE, OFFSET, BOARD_IMAGE_PATH, PIECES_DIR, PIECES

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
            for name in PIECES
        }

    def draw(self, grid, highlights=[]):
        self.screen.blit(self.board_image, (0, 0))

        for (row, col) in highlights:
            # find the top-left pixel of this square
            square_x = col * SQUARE_SIZE + OFFSET
            square_y = row * SQUARE_SIZE + OFFSET

            # draw a small transparent grey circle at the centre
            # shows legal moves
            circle_surface = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
            pygame.draw.circle(circle_surface, (20, 20, 20, 100), (SQUARE_SIZE // 2, SQUARE_SIZE // 2), 15)
            self.screen.blit(circle_surface, (square_x, square_y))

        for row in range(8):
            for col in range(8):
                piece = grid[row][col]
                if piece:
                    x = col * SQUARE_SIZE + OFFSET
                    y = row * SQUARE_SIZE + OFFSET
                    self.screen.blit(self.pieces[piece], (x, y))
