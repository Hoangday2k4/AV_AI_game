import pygame


class Platform:

    def __init__(self, x, y, w, h):

        self.rect = pygame.Rect(x, y, w, h)

    def draw(self, screen):

        # Draw platform as bricks
        brick_width = 20
        brick_height = 10
        for x in range(self.rect.left, self.rect.right, brick_width):
            for y in range(self.rect.top, self.rect.bottom, brick_height):
                brick_rect = pygame.Rect(x, y, min(brick_width, self.rect.right - x), min(brick_height, self.rect.bottom - y))
                pygame.draw.rect(screen, (100, 60, 20), brick_rect)
                pygame.draw.rect(screen, (80, 40, 10), brick_rect, 1)  # Dark border for each brick