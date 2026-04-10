import cv2
import numpy as np
import pygame


class CameraPanel:

    def draw(self, screen, frame, panel_width, panel_height):

        if frame is None:
            return

        h, w, _ = frame.shape

        aspect = w / h

        new_width = panel_width
        new_height = int(new_width / aspect)

        if new_height > panel_height:
            new_height = panel_height
            new_width = int(new_height * aspect)

        frame = cv2.resize(frame, (new_width, new_height))

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        frame = np.rot90(frame)

        surface = pygame.surfarray.make_surface(frame)

        x = (panel_width - new_width) // 2
        y = (panel_height - new_height) // 2

        screen.blit(surface, (x, y))