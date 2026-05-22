import pygame

class InputHandler:
    def handle(self, events):
        for event in events:
            if event.type == pygame.QUIT:
                return False
        return True

    def get_mouse_click(self, events):
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN:
                return pygame.mouse.get_pos()
        return None