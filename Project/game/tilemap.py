import os
import shutil
import zipfile

import pygame
from pytmx.util_pygame import load_pygame


class TileMapLevel:
    """Load a Tiled TMX map and provide collision/hazard/goal rectangles."""

    def __init__(self, tmx_filename=None):
        if tmx_filename is None:
            tmx_filename = self._resolve_default_map()

        self.tmx_filename = os.path.abspath(tmx_filename)
        self.map_id = self._make_map_id(self.tmx_filename)

        self.tmx_data = load_pygame(self.tmx_filename)
        self.tilewidth = self.tmx_data.tilewidth
        self.tileheight = self.tmx_data.tileheight
        self.width = self.tmx_data.width * self.tilewidth
        self.height = self.tmx_data.height * self.tileheight

        self.collide_rects = []
        self.hazard_rects = []
        self.goal_rects = []
        self.layer_tile_entries = {}
        self.hidden_tiles = set()
        self._generate_rects()

        self.player_start = self._find_player_start()
        self._base_map_surface = None
        self._scaled_map_surface = None
        self._scaled_cache_scale = None

        self.reset_runtime_state()

    def _make_map_id(self, tmx_filename):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        try:
            rel = os.path.relpath(tmx_filename, project_root)
            return rel.replace("\\", "/")
        except ValueError:
            return os.path.basename(tmx_filename)

    def _resolve_default_map(self):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        source_map2_dir = os.path.join(project_root, "Map", "Map2")
        source_map2_tmx = os.path.join(source_map2_dir, "map.tmx")
        source_map2_sheet = os.path.join(source_map2_dir, "spritesheet.png")
        map2_runtime_dir = os.path.join(project_root, "Project", "assets", "Map2")
        map2_tmx = os.path.join(map2_runtime_dir, "map.tmx")
        runtime_sheet = os.path.join(map2_runtime_dir, "spritesheet.png")

        # Source of truth: always prefer Map/Map2 and sync into assets/Map2.
        if os.path.exists(source_map2_tmx):
            os.makedirs(map2_runtime_dir, exist_ok=True)
            try:
                shutil.copy2(source_map2_tmx, map2_tmx)
            except OSError:
                pass
            if os.path.exists(source_map2_sheet):
                try:
                    shutil.copy2(source_map2_sheet, runtime_sheet)
                except OSError:
                    pass
            return source_map2_tmx

        if not os.path.exists(map2_tmx):
            os.makedirs(map2_runtime_dir, exist_ok=True)
            map2_zip = os.path.join(source_map2_dir, "map2.zip")
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
            self.layer_tile_entries.setdefault(name, [])
            is_collider = bool(getattr(layer, "properties", {}).get("collider", False))
            is_hazard = any(key in name_lower for key in hazard_keywords)
            is_goal = any(key in name_lower for key in goal_keywords)

            for x, y, gid in layer.tiles():
                if not gid:
                    continue
                rect = pygame.Rect(x * self.tilewidth, y * self.tileheight, self.tilewidth, self.tileheight)
                self.layer_tile_entries[name].append((x, y, gid, rect.copy()))

                if is_collider or name in solid_layers:
                    self.collide_rects.append(rect)
                if is_hazard:
                    self.hazard_rects.append(rect)
                if is_goal:
                    self.goal_rects.append(rect)

        self.gift_rects = [entry[3].copy() for entry in self.layer_tile_entries.get("Gift", [])]
        self.key_rects = [entry[3].copy() for entry in self.layer_tile_entries.get("Key", [])]
        self.exit_rects = [entry[3].copy() for entry in self.layer_tile_entries.get("Exit door", [])]
        self.sewer_rects = [entry[3].copy() for entry in self.layer_tile_entries.get("Sewer pipes", [])]
        self.thorn_entries = list(self.layer_tile_entries.get("Thorn", []))
        self.checkpoint_rects = [entry[3].copy() for entry in self.layer_tile_entries.get("Checkpoint", [])]
        self.checkpoint_rects.sort(key=lambda r: (r.x, r.y))

        coin_entries = list(self.layer_tile_entries.get("Coin", []))
        coin_entries.sort(key=lambda e: (e[1], e[0]))
        self.coin_rect_by_key = {}
        for x, y, _gid, rect in coin_entries:
            key = f"{x},{y}"
            self.coin_rect_by_key[key] = rect.copy()
        self.total_coin_count = len(self.coin_rect_by_key)

        # Thorns to disable by Gift: the upper thorn row near Key.
        self.switch_thorn_entries = []
        if self.thorn_entries:
            min_y = min(entry[3].y for entry in self.thorn_entries)
            self.switch_thorn_entries = [entry for entry in self.thorn_entries if entry[3].y == min_y]
        self.switch_thorn_rects = [entry[3].copy() for entry in self.switch_thorn_entries]

        # Also disable 2 thorns nearest to Gift when Gift is collected.
        self.gift_side_thorn_entries = []
        if self.gift_rects and self.thorn_entries:
            gift_center = self.gift_rects[0].center
            self.gift_side_thorn_entries = sorted(
                self.thorn_entries,
                key=lambda entry: (entry[3].centerx - gift_center[0]) ** 2 + (entry[3].centery - gift_center[1]) ** 2,
            )[:2]
        self.gift_side_thorn_rects = [entry[3].copy() for entry in self.gift_side_thorn_entries]

        # Sewer teleport pair: only real sewer tiles (exclude water tiles on same layer).
        self.sewer_portal_entries = [
            entry for entry in self.layer_tile_entries.get("Sewer pipes", []) if entry[2] != 2
        ]
        self.sewer_portal_rects = [entry[3].copy() for entry in self.sewer_portal_entries]

        self.sewer_top_rect = None
        self.sewer_bottom_rect = None
        if self.sewer_portal_rects:
            self.sewer_top_rect = min(self.sewer_portal_rects, key=lambda r: (r.y, r.x)).copy()
            self.sewer_bottom_rect = max(self.sewer_portal_rects, key=lambda r: (r.y, r.x)).copy()

        self._base_hazard_rects = [r.copy() for r in self.hazard_rects]

    def _invalidate_render_cache(self):
        self._base_map_surface = None
        self._scaled_map_surface = None
        self._scaled_cache_scale = None

    def _hide_tile(self, layer_name, x, y):
        self.hidden_tiles.add((layer_name, x, y))

    def _hide_layer(self, layer_name):
        for x, y, _gid, _rect in self.layer_tile_entries.get(layer_name, []):
            self._hide_tile(layer_name, x, y)

    def _hide_switch_thorns(self):
        targets = self.switch_thorn_entries + self.gift_side_thorn_entries
        if not targets:
            return

        for x, y, _gid, _rect in targets:
            self._hide_tile("Thorn", x, y)

        removed_rects = self.switch_thorn_rects + self.gift_side_thorn_rects
        removed = {(r.x, r.y, r.w, r.h) for r in removed_rects}
        self.hazard_rects = [
            r for r in self.hazard_rects if (r.x, r.y, r.w, r.h) not in removed
        ]

    def _hide_coin_by_key(self, key):
        if key not in self.coin_rect_by_key:
            return
        x_str, y_str = key.split(",", 1)
        self._hide_tile("Coin", int(x_str), int(y_str))

    def apply_collected_coins(self, collected_keys):
        """Hide coins already collected in a completed run."""
        if not collected_keys:
            return

        changed = False
        for key in collected_keys:
            if key in self.coin_rect_by_key and key not in self.collected_coin_keys:
                self.collected_coin_keys.add(key)
                self._hide_coin_by_key(key)
                changed = True

        if changed:
            self._invalidate_render_cache()

    def reset_runtime_state(self):
        """Reset per-run gameplay state."""
        self.hidden_tiles.clear()
        self.gift_collected = False
        self.key_collected = False
        self.exit_unlocked = False
        self.hazard_rects = [r.copy() for r in self._base_hazard_rects]
        self.collected_coin_keys = set()
        self._invalidate_render_cache()

    def handle_player_interactions(self, player):
        """Apply interactions and return event flags."""
        events = {
            "teleported": False,
            "key_collected": False,
            "gift_collected": False,
            "coins_collected": [],
            "win": False,
        }

        if not self.gift_collected and any(player.rect.colliderect(r) for r in self.gift_rects):
            self.gift_collected = True
            self._hide_layer("Gift")
            self._hide_switch_thorns()
            events["gift_collected"] = True
            self._invalidate_render_cache()

        if not self.key_collected and any(player.rect.colliderect(r) for r in self.key_rects):
            self.key_collected = True
            self.exit_unlocked = True
            self._hide_layer("Key")
            events["key_collected"] = True
            self._invalidate_render_cache()

        new_coin_keys = []
        for key, rect in self.coin_rect_by_key.items():
            if key in self.collected_coin_keys:
                continue
            if player.rect.colliderect(rect):
                self.collected_coin_keys.add(key)
                new_coin_keys.append(key)
                self._hide_coin_by_key(key)

        if new_coin_keys:
            events["coins_collected"] = new_coin_keys
            self._invalidate_render_cache()

        if self.sewer_top_rect and self.sewer_bottom_rect:
            top = self.sewer_top_rect.top
            feet_near_top = (top - 5) <= player.rect.bottom <= (top + 5)
            from_above = player.rect.centery < self.sewer_top_rect.bottom and player.vel_y >= 0
            horizontal_overlap = (
                player.rect.right > (self.sewer_top_rect.left + 2)
                and player.rect.left < (self.sewer_top_rect.right - 2)
            )
            if feet_near_top and from_above and horizontal_overlap:
                player.rect.midbottom = (
                    self.sewer_bottom_rect.centerx,
                    self.sewer_bottom_rect.top,
                )
                player.vel_x = 0
                player.vel_y = 0
                player.on_ground = False
                events["teleported"] = True

        if self.exit_unlocked and any(player.rect.colliderect(r) for r in self.exit_rects):
            events["win"] = True

        return events

    def _find_player_start(self):
        """Return a default start position on the first solid tile from the left."""
        if not self.collide_rects:
            return pygame.Vector2(0, 0)

        leftmost = min(self.collide_rects, key=lambda r: (r.x, r.y))
        return pygame.Vector2(leftmost.x + 10, leftmost.y - 40)

    def _build_base_surface(self):
        """Render full map once at native resolution to avoid tile seam artifacts."""
        if self._base_map_surface is not None:
            return

        base = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        for layer in self.tmx_data.visible_layers:
            if not hasattr(layer, "tiles"):
                continue
            name = getattr(layer, "name", "")
            for x, y, gid in layer.tiles():
                if gid == 0:
                    continue
                if (name, x, y) in self.hidden_tiles:
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
        return pygame.Vector2(world_pos)
