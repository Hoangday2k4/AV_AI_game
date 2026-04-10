import os
import zipfile

import pygame
from pytmx.util_pygame import load_pygame


class TileMapLevel:
    """Load a Tiled TMX map and provide collision/hazard/goal rectangles."""

    def __init__(self, tmx_filename=None):
        if tmx_filename is None:
            tmx_filename = self._resolve_default_map()

        self.tmx_data = load_pygame(tmx_filename)
        self.tilewidth = self.tmx_data.tilewidth
        self.tileheight = self.tmx_data.tileheight
        self.width = self.tmx_data.width * self.tilewidth
        self.height = self.tmx_data.height * self.tileheight

        self.collide_rects = []
        self.hazard_rects = []
        self.goal_rects = []
        self._generate_rects()

        self.player_start = self._find_player_start()
        self._base_map_surface = None
        self._scaled_map_surface = None
        self._scaled_cache_scale = None

    def _resolve_default_map(self):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        map2_runtime_dir = os.path.join(project_root, "Project", "assets", "Map2")
        map2_tmx = os.path.join(map2_runtime_dir, "map.tmx")

        if not os.path.exists(map2_tmx):
            os.makedirs(map2_runtime_dir, exist_ok=True)
            map2_zip = os.path.join(project_root, "Map", "Map2", "map2.zip")
            if os.path.exists(map2_zip):
                with zipfile.ZipFile(map2_zip, "r") as zf:
                    for name in ("map.tmx", "spritesheet.png"):
                        try:
                            zf.extract(name, map2_runtime_dir)
                        except KeyError:
                            pass

        if os.path.exists(map2_tmx):
            return map2_tmx

        # Fallback to map1 if map2 is unavailable.
        return os.path.join(project_root, "Map", "Map1", "map.tmx")

    def _generate_rects(self):
        """Populate collision/hazard/goal rect arrays based on layer names/properties."""
        solid_layers = {"Ground", "Blocks", "Bridge"}
        hazard_keywords = {"water", "thorn", "lava", "spike", "hazard"}
        goal_keywords = {"pickup", "goal", "exit", "door", "checkpoint"}

        for layer in self.tmx_data.visible_layers:
            if not hasattr(layer, "tiles"):
                continue
            name = getattr(layer, "name", "")
            name_lower = name.lower()
            is_collider = bool(getattr(layer, "properties", {}).get("collider", False))
            is_hazard = any(key in name_lower for key in hazard_keywords)
            is_goal = any(key in name_lower for key in goal_keywords)

            for x, y, gid in layer.tiles():
                # gid may already be a Surface if using pytmx util_pygame
                if not gid:
                    continue
                rect = pygame.Rect(x * self.tilewidth, y * self.tileheight, self.tilewidth, self.tileheight)
                if is_collider or name in solid_layers:
                    self.collide_rects.append(rect)
                if is_hazard:
                    self.hazard_rects.append(rect)
                if is_goal:
                    self.goal_rects.append(rect)

    def _find_player_start(self):
        """Return a default start position on the first solid tile from the left."""
        if not self.collide_rects:
            return pygame.Vector2(0, 0)

        leftmost = min(self.collide_rects, key=lambda r: (r.x, r.y))
        # Position player slightly above the ground tile
        return pygame.Vector2(leftmost.x + 10, leftmost.y - 40)

    def _build_base_surface(self):
        """Render full map once at native resolution to avoid tile seam artifacts."""
        if self._base_map_surface is not None:
            return

        base = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        for layer in self.tmx_data.visible_layers:
            if not hasattr(layer, "tiles"):
                continue
            for x, y, gid in layer.tiles():
                if gid == 0:
                    continue
                image = gid if isinstance(gid, pygame.Surface) else self.tmx_data.get_tile_image_by_gid(gid)
                if image:
                    base.blit(image, (x * self.tilewidth, y * self.tileheight))

        self._base_map_surface = base

    def draw(self, surface, offset_x=0, offset_y=0, scale=1.0):
        """Render the tilemap at the given offset."""
        if scale <= 0:
            return

        self._build_base_surface()
        if self._base_map_surface is None:
            return

        if scale == 1.0:
            draw_image = self._base_map_surface
        else:
            if self._scaled_map_surface is None or self._scaled_cache_scale != scale:
                scaled_size = (
                    max(1, int(self.width * scale)),
                    max(1, int(self.height * scale)),
                )
                self._scaled_map_surface = pygame.transform.scale(self._base_map_surface, scaled_size)
                self._scaled_cache_scale = scale
            draw_image = self._scaled_map_surface

        surface.blit(draw_image, (int(offset_x), int(offset_y)))

    def world_to_screen(self, world_pos):
        return pygame.Vector2(world_pos)  # No camera by default
