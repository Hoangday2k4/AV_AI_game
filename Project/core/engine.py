import pygame

from config.settings import *


class Engine:

    def __init__(self):

        pygame.init()

        self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        pygame.display.set_caption("Forest Temple")

        self.width, self.height = self.screen.get_size()
        self.clock = pygame.time.Clock()

    def tick(self):

        self.clock.tick(FPS)

    def update(self):

        pygame.display.update()
