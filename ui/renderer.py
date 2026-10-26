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
        self.font_small = pygame.font.SysFont("Arial", 22)

        self.pvp_rect = pygame.Rect(BUTTON_X, 340, BUTTON_W, BUTTON_H)
        self.pve_rect = pygame.Rect(BUTTON_X, 430, BUTTON_W, BUTTON_H)
        self.evs_rect = pygame.Rect(BUTTON_X, 520, BUTTON_W, BUTTON_H)

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

        # difficulty 1-5 (search depth), and "max": no depth limit, only the time per move
        DIFF_BTN, DIFF_GAP = 70, 10
        levels = [1, 2, 3, 4, 5, "max"]
        diff_total_w = DIFF_BTN * len(levels) + DIFF_GAP * (len(levels) - 1)
        diff_x = WIDTH // 2 - diff_total_w // 2
        diff_y = HEIGHT // 2 - DIFF_BTN // 2
        self.difficulty_rects = {}
        for i in range(len(levels)):
            self.difficulty_rects[levels[i]] = pygame.Rect(diff_x + i * (DIFF_BTN + DIFF_GAP), diff_y, DIFF_BTN, DIFF_BTN)

        # max time per engine move in seconds, None = unlimited
        # "custom" opens a screen to type your own number of seconds
        self.time_rects = {}
        time_y = 215
        for limit in [1, 5, 10, 15, 30, "custom", None]:
            self.time_rects[limit] = pygame.Rect(BUTTON_X, time_y, BUTTON_W, BUTTON_H)
            time_y += BUTTON_H + 10
        self.custom_box = pygame.Rect(BUTTON_X, 330, BUTTON_W, BUTTON_H)

        # Stockfish's strength: an Elo cap, None = full strength
        self.stockfish_rects = {}
        stockfish_y = 220
        for elo in [1400, 1700, 2000, 2300, 2600, None]:
            self.stockfish_rects[elo] = pygame.Rect(BUTTON_X, stockfish_y, BUTTON_W, BUTTON_H)
            stockfish_y += BUTTON_H + 15

    def draw_menu(self):
        self.screen.fill((30, 30, 30))
        title = self.font_large.render("Chess", True, (255, 255, 255))
        self.screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 200))

        for rect, label in [
            (self.pvp_rect, "Player vs Player"),
            (self.pve_rect, "Player vs Engine"),
            (self.evs_rect, "Engine vs Stockfish"),
        ]:
            pygame.draw.rect(self.screen, (60, 120, 60), rect, border_radius=8)
            text = self.font_med.render(label, True, (255, 255, 255))
            self.screen.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))

    def draw_colour_select(self, heading="Choose Your Colour", white_label="Play as White", black_label="Play as Black"):
        self.screen.fill((30, 30, 30))
        title = self.font_large.render(heading, True, (255, 255, 255))
        self.screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 200))

        for rect, label in [
            (self.white_rect, white_label),
            (self.black_rect, black_label),
        ]:
            pygame.draw.rect(self.screen, (60, 120, 60), rect, border_radius=8)
            text = self.font_med.render(label, True, (255, 255, 255))
            self.screen.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))

    def draw_difficulty_select(self):
        self.screen.fill((30, 30, 30))
        title = self.font_large.render("Choose Difficulty", True, (255, 255, 255))
        self.screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 200))

        for level, rect in self.difficulty_rects.items():
            if level == "max":
                label = "Max"
            else:
                label = str(level)
            pygame.draw.rect(self.screen, (60, 120, 60), rect, border_radius=8)
            text = self.font_med.render(label, True, (255, 255, 255))
            self.screen.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))

    def draw_time_select(self, include_unlimited=True):
        self.screen.fill((30, 30, 30))
        title = self.font_large.render("Time Per Move", True, (255, 255, 255))
        self.screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 110))

        for limit, rect in self.time_rects.items():
            if limit is None:
                # Stockfish (or max difficulty) would think forever with no limit
                if not include_unlimited:
                    continue
                label = "Unlimited"
            elif limit == "custom":
                label = "Custom..."
            elif limit == 1:
                label = "1 second"
            else:
                label = f"{limit} seconds"
            pygame.draw.rect(self.screen, (60, 120, 60), rect, border_radius=8)
            text = self.font_med.render(label, True, (255, 255, 255))
            self.screen.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))

    def draw_custom_time(self, typed, error):
        self.screen.fill((30, 30, 30))
        title = self.font_large.render("Custom Time", True, (255, 255, 255))
        self.screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 200))

        # the box with what's been typed so far
        box = self.custom_box
        pygame.draw.rect(self.screen, (255, 255, 255), box, width=2, border_radius=8)
        if typed == "":
            text = self.font_med.render("type seconds", True, (120, 120, 120))
        else:
            text = self.font_med.render(typed + " seconds", True, (255, 255, 255))
        self.screen.blit(text, (box.centerx - text.get_width() // 2, box.centery - text.get_height() // 2))

        lines = [
            ("Press Enter to start, Esc to go back", (200, 200, 200)),
            ("Times over 30 seconds mean long waits per move", (255, 200, 0)),
        ]
        if error != "":
            lines.append((error, (255, 90, 90)))
        line_y = box.bottom + 25
        for line, colour in lines:
            text = self.font_small.render(line, True, colour)
            self.screen.blit(text, (WIDTH // 2 - text.get_width() // 2, line_y))
            line_y += 35

    def draw_stockfish_select(self):
        self.screen.fill((30, 30, 30))
        title = self.font_large.render("Stockfish Strength", True, (255, 255, 255))
        self.screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 120))

        for elo, rect in self.stockfish_rects.items():
            if elo is None:
                label = "Full strength"
            else:
                label = f"{elo} Elo"
            pygame.draw.rect(self.screen, (60, 120, 60), rect, border_radius=8)
            text = self.font_med.render(label, True, (255, 255, 255))
            self.screen.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))

    def draw_thinking(self, label="Felis is thinking..."):
        text = self.font_med.render(label, True, (255, 255, 0))
        self.screen.blit(text, (10, 10))

    def draw_caption(self, label):
        # a line under the board, e.g. who is playing who
        text = self.font_med.render(label, True, (255, 255, 255))
        self.screen.blit(text, (WIDTH // 2 - text.get_width() // 2, HEIGHT - 55))

    def draw_game_over_popup(self, title, reason):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0, 0))
        title_text = self.font_large.render(title, True, (255, 215, 0))
        reason_text = self.font_med.render(reason, True, (255, 255, 255))
        self.screen.blit(title_text, (WIDTH // 2 - title_text.get_width() // 2, HEIGHT // 2 - title_text.get_height()))
        self.screen.blit(reason_text, (WIDTH // 2 - reason_text.get_width() // 2, HEIGHT // 2 + 10))

    def draw_promotion_picker(self, colour):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0, 0))

        for kind, rect in self.promotion_rects.items():
            pygame.draw.rect(self.screen, (60, 60, 60), rect, border_radius=8)
            self.screen.blit(self.pieces[f"{colour}_{kind}"], rect.topleft)

    def draw(self, grid, highlights=[], last_move=None):
        self.screen.blit(self.board_image, (0, 0))

        # the last move: the squares it went from and to glow green
        if last_move is not None:
            glow = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
            glow.fill((80, 200, 80, 110))
            for (row, col) in last_move:
                self.screen.blit(glow, (col * SQUARE_SIZE + OFFSET, row * SQUARE_SIZE + OFFSET))

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
