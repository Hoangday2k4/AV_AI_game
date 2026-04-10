import pygame


class HUD:

    def __init__(self):

        self.font = pygame.font.SysFont("Arial", 28)

    def draw(self, screen, action):

        text = self.font.render(f"Action: {action}", True, (255, 0, 0))

        screen.blit(text, (20, 20))