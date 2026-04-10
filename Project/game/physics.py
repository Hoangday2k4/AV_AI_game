from config.settings import *

class Physics:

    @staticmethod
    def apply_gravity(player):

        player.vel_y += GRAVITY
        player.rect.y += player.vel_y