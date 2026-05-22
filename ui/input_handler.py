import pygame


class InputHandler:
    def handle(self, events):
        for event in events:
            if event.type == pygame.QUIT:
                return False
        return True
