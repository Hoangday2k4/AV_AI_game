from game.tilemap import TileMapLevel


class Level(TileMapLevel):
    def __init__(self, tmx_filename=None):
        super().__init__(tmx_filename)
