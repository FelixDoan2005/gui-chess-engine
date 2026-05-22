import pygame
from ui.constants import WIDTH, HEIGHT

def create_window():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Chess Engine")
    return screen
