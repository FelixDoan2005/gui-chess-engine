import pygame
from ui.constants import WIDTH, HEIGHT, SQUARE_SIZE, OFFSET, BOARD_IMAGE_PATH, PIECES_DIR, PIECES

BUTTON_W, BUTTON_H = 300, 60
BUTTON_X = WIDTH // 2 - BUTTON_W // 2

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
        self.font_large = pygame.font.SysFont("Arial", 64, bold=True)
        self.font_med = pygame.font.SysFont("Arial", 32)

        self.pvp_rect = pygame.Rect(BUTTON_X, 340, BUTTON_W, BUTTON_H)
        self.pve_rect = pygame.Rect(BUTTON_X, 430, BUTTON_W, BUTTON_H)

        self.promotion_pieces = ["queen", "rook", "bishop", "knight"]
        promo_total_w = SQUARE_SIZE * len(self.promotion_pieces)
        promo_x = WIDTH // 2 - promo_total_w // 2
        promo_y = HEIGHT // 2 - SQUARE_SIZE // 2
        self.promotion_rects = {
            kind: pygame.Rect(promo_x + i * SQUARE_SIZE, promo_y, SQUARE_SIZE, SQUARE_SIZE)
            for i, kind in enumerate(self.promotion_pieces)
        }

        self.white_rect = pygame.Rect(BUTTON_X, 340, BUTTON_W, BUTTON_H)
        self.black_rect = pygame.Rect(BUTTON_X, 430, BUTTON_W, BUTTON_H)

        DIFF_BTN, DIFF_GAP = 60, 10
        diff_total_w = DIFF_BTN * 10 + DIFF_GAP * 9
        diff_x = WIDTH // 2 - diff_total_w // 2
        diff_y = HEIGHT // 2 - DIFF_BTN // 2
        self.difficulty_rects = {
            level: pygame.Rect(diff_x + (level - 1) * (DIFF_BTN + DIFF_GAP), diff_y, DIFF_BTN, DIFF_BTN)
            for level in range(1, 11)
        }

    def draw_menu(self):
        self.screen.fill((30, 30, 30))
        title = self.font_large.render("Chess", True, (255, 255, 255))
        self.screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 200))

        for rect, label in [
            (self.pvp_rect, "Player vs Player"),
            (self.pve_rect, "Player vs Engine"),
        ]:
            pygame.draw.rect(self.screen, (60, 120, 60), rect, border_radius=8)
            text = self.font_med.render(label, True, (255, 255, 255))
            self.screen.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))

    def draw_colour_select(self):
        self.screen.fill((30, 30, 30))
        title = self.font_large.render("Choose Your Colour", True, (255, 255, 255))
        self.screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 200))

        for rect, label in [
            (self.white_rect, "Play as White"),
            (self.black_rect, "Play as Black"),
        ]:
            pygame.draw.rect(self.screen, (60, 120, 60), rect, border_radius=8)
            text = self.font_med.render(label, True, (255, 255, 255))
            self.screen.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))

    def draw_difficulty_select(self):
        self.screen.fill((30, 30, 30))
        title = self.font_large.render("Choose Difficulty", True, (255, 255, 255))
        self.screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 200))

        for level, rect in self.difficulty_rects.items():
            pygame.draw.rect(self.screen, (60, 120, 60), rect, border_radius=8)
            text = self.font_med.render(str(level), True, (255, 255, 255))
            self.screen.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))

    def draw_thinking(self):
        text = self.font_med.render("Engine is thinking...", True, (255, 255, 0))
        self.screen.blit(text, (10, 10))

    def draw_checkmate_popup(self, winner):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0, 0))
        msg = self.font_large.render(f"{winner.capitalize()} wins!", True, (255, 215, 0))
        self.screen.blit(msg, (WIDTH // 2 - msg.get_width() // 2, HEIGHT // 2 - msg.get_height() // 2))

    def draw_promotion_picker(self, colour):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0, 0))

        for kind, rect in self.promotion_rects.items():
            pygame.draw.rect(self.screen, (60, 60, 60), rect, border_radius=8)
            self.screen.blit(self.pieces[f"{colour}_{kind}"], rect.topleft)

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
