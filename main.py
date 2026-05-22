import pygame
from ui import create_window
from ui import Renderer
from ui import InputHandler
from ui import FPS
from engine import Board

def main():
    screen = create_window()
    clock = pygame.time.Clock()
    board = Board()
    renderer = Renderer(screen)
    handler = InputHandler()

    running = True
    while running:
        events = pygame.event.get()
        running = handler.handle(events)
        renderer.draw(board.grid)
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    main()
