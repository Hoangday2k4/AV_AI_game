import pygame
import os
import re


class PlayerModel:
    """Manages player sprites and animations."""

    def __init__(self, model_name="fireboy"):
        self.model_name = model_name
        self.sprites = {}
        self.current_sprite = None
        # Delay loading until pygame is initialized
        # self.load_sprites()

    def ensure_loaded(self):
        """Ensure sprites are loaded (call after pygame init)."""
        if not self.sprites:
            self.load_sprites()

    def _load_frames_from_folder(self, folder, action, direction):
        """Load and sort all PNG frames in a folder for a specific action/direction."""
        frames = []
        if not os.path.exists(folder):
            return frames

        for fname in os.listdir(folder):
            if not fname.lower().endswith(".png"):
                continue

            # Only load files for the expected action/direction (e.g., jump_left, run_right)
            lower = fname.lower()
            if direction not in lower:
                continue
            if action == "jump" and "jump" not in lower:
                continue
            if action == "run" and "jump" in lower:
                continue

            # Parse the frame number at the end of the filename
            match = re.search(r"(\d+)\.png$", lower)
            if not match:
                continue

            idx = int(match.group(1))
            try:
                img = pygame.image.load(os.path.join(folder, fname))
                # Try convert_alpha, but don't fail if it doesn't work
                try:
                    img = img.convert_alpha()
                except pygame.error:
                    pass  # Keep original surface if convert fails

                # Trim transparent padding so feet alignment matches platform collision.
                try:
                    bounds = img.get_bounding_rect(min_alpha=1)
                    if bounds.width > 0 and bounds.height > 0:
                        img = img.subsurface(bounds).copy()
                except Exception:
                    pass

                frames.append((idx, img))
            except Exception:
                continue

        frames.sort(key=lambda x: x[0])
        return [img for _, img in frames]

    def load_sprites(self):
        """Load sprite images from Player/ subfolders."""
        # Resolve Player folder from current project root (no hardcoded machine path).
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        base_path = os.path.join(project_root, "Player")

        if not os.path.exists(base_path):
            self.current_sprite = None
            return

        self.sprites = {
            "run_left": [],
            "run_right": [],
            "jump_left": [],
            "jump_right": [],
        }

        for action in ["run", "jump"]:
            for direction in ["left", "right"]:
                folder = os.path.join(base_path, action.capitalize(), direction.capitalize())
                self.sprites[f"{action}_{direction}"] = self._load_frames_from_folder(
                    folder, action, direction
                )

        # Set current_sprite to first available sprite (prefer run_right)
        for key in ["run_right", "run_left", "jump_right", "jump_left"]:
            if self.sprites.get(key):
                self.current_sprite = self.sprites[key][0]
                break

    def get_sprite(self, action="IDLE", direction="RIGHT", frame=0):
        """Return appropriate sprite based on action, direction, and frame."""
        self.ensure_loaded()
        if not self.sprites:
            return None

        action = (action or "").lower()
        direction = (direction or "").lower() or "right"

        if action in ["left", "right"]:
            key = f"run_{action}"
        elif action == "jump":
            key = f"jump_{direction}"
        elif action == "idle":
            key = f"run_{direction}"
        else:
            return self.current_sprite

        frames = self.sprites.get(key, [])
        if not frames:
            return self.current_sprite

        idx = frame % len(frames)
        return frames[idx]

    def frame_count(self, action="IDLE", direction="RIGHT"):
        """Return number of frames available for given action/direction."""
        action = (action or "").lower()
        direction = (direction or "").lower() or "right"

        if action in ["left", "right"]:
            key = f"run_{action}"
        elif action == "jump":
            key = f"jump_{direction}"
        elif action == "idle":
            key = f"run_{direction}"
        else:
            key = None

        if key is None:
            return 1

        return max(1, len(self.sprites.get(key, [])))

    def draw(self, screen, rect, action="IDLE", direction="RIGHT", frame=0):
        """Draw the player sprite at the given rect."""
        sprite = self.get_sprite(action, direction, frame)
        if sprite:
            scaled_sprite = pygame.transform.scale(sprite, (rect.width, rect.height))
            screen.blit(scaled_sprite, rect.topleft)
        else:
            pygame.draw.rect(screen, (255, 100, 0), rect)
            pygame.draw.rect(screen, (255, 150, 50), rect, 2)
