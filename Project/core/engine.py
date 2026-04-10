import pygame
from config.settings import *

class Engine:

    def __init__(self):

        pygame.init()

        self.screen = pygame.display.set_mode((WIDTH,HEIGHT))
        self.clock = pygame.time.Clock()

    def tick(self):

        self.clock.tick(FPS)

    def update(self):

        pygame.display.update()