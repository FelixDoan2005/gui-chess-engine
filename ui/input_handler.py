import pygame

class InputHandler:
    def handle(self, events):
        for event in events:
            if event.type == pygame.QUIT:
                return False
        return True

    def get_mouse_click(self, events):
        for event in events:
            # left button only (1), not right click or the scroll wheel
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                return pygame.mouse.get_pos()
        return None

    def get_right_click(self, events):
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                return True
        return False