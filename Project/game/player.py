import pygame
from config.settings import *
from game.player_model import PlayerModel


class Player:

    def __init__(self, model_name="fireboy"):

        # Physics hitbox focuses body/feet (sprite head can extend outside this box).
        self.rect = pygame.Rect(250, 400, 22, 30)

        self.vel_y = 0

        self.vel_x = 0

        self.on_ground = False

        self.last_direction = "RIGHT"

        self.animation_frame = 0
        self.animation_tick = 0
        self.animation_tick_delay = 3

        self.model = PlayerModel(model_name)

    def update(self, action, min_x=0, max_x=None):

        if self.rect.left < min_x:
            self.rect.left = min_x
            self.vel_x = 0  # Stop when hitting left boundary

        if max_x is not None and self.rect.right > max_x:
            self.rect.right = max_x
            self.vel_x = 0  # Stop when hitting right boundary

        if action == "LEFT":
            self.vel_x = -PLAYER_SPEED
            self.last_direction = "LEFT"

        elif action == "RIGHT":
            self.vel_x = PLAYER_SPEED
            self.last_direction = "RIGHT"

        else:
            self.vel_x = 0
            # Keep last_direction to preserve facing direction when idle

        if action == "JUMP" and self.on_ground:

            self.vel_y = JUMP_FORCE

            # Maintain horizontal momentum when jumping
            if self.last_direction == "LEFT":
                self.vel_x = -PLAYER_SPEED
            elif self.last_direction == "RIGHT":
                self.vel_x = PLAYER_SPEED

            self.on_ground = False

        if action == "DOUBLE_JUMP" and self.on_ground:

            self.vel_y = JUMP_FORCE * 1.5  # Higher jump for double jump

            if self.last_direction == "LEFT":
                self.vel_x = -PLAYER_SPEED
            elif self.last_direction == "RIGHT":
                self.vel_x = PLAYER_SPEED

            self.on_ground = False

        # Update animation frame based on available sprite count
        frame_count = self.model.frame_count(action, self.last_direction)
        if action in ["LEFT", "RIGHT", "JUMP"] and frame_count > 0:
            self.animation_tick += 1
            if self.animation_tick >= self.animation_tick_delay:
                self.animation_tick = 0
                self.animation_frame = (self.animation_frame + 1) % frame_count
        else:
            self.animation_frame = 0
            self.animation_tick = 0

    def apply_gravity(self):

        self.vel_y += GRAVITY

    def move_and_collide(self, platforms):
        """Move on X then Y axis and resolve collisions on each axis."""
        # Horizontal pass: block movement by side walls/blocks.
        self.rect.x += int(round(self.vel_x))
        for p in platforms:
            platform_rect = p.rect if hasattr(p, 'rect') else p
            if self.rect.colliderect(platform_rect):
                if self.vel_x > 0:
                    self.rect.right = platform_rect.left
                elif self.vel_x < 0:
                    self.rect.left = platform_rect.right
                self.vel_x = 0

        # Vertical pass: land on top and block from below (head hit).
        self.on_ground = False
        self.rect.y += int(round(self.vel_y))
        for p in platforms:
            platform_rect = p.rect if hasattr(p, 'rect') else p

            if self.rect.colliderect(platform_rect):
                if self.vel_y > 0:
                    self.rect.bottom = platform_rect.top
                    self.vel_y = 0
                    self.on_ground = True
                elif self.vel_y < 0:
                    self.rect.top = platform_rect.bottom
                    self.vel_y = 0

        # Keep a little horizontal damping for smoother stop.
        self.vel_x *= 0.9

    def collide_platforms(self, platforms):
        """Backward-compatible wrapper."""
        self.move_and_collide(platforms)

    def draw(
        self,
        screen,
        action="IDLE",
        offset_x=0,
        offset_y=0,
        scale=1.0,
        sprite_scale=1.75,
        foot_offset=0,
    ):

        # Draw player using model sprite
        direction = self.last_direction if self.last_direction in ["LEFT", "RIGHT"] else "RIGHT"
        hitbox_rect = pygame.Rect(
            int(offset_x + self.rect.x * scale),
            int(offset_y + self.rect.y * scale),
            max(1, int(self.rect.width * scale)),
            max(1, int(self.rect.height * scale)),
        )

        render_w = max(1, int(hitbox_rect.width * sprite_scale))
        render_h = max(1, int(hitbox_rect.height * sprite_scale))
        draw_rect = pygame.Rect(
            hitbox_rect.centerx - render_w // 2,
            hitbox_rect.bottom - render_h + int(foot_offset),
            render_w,
            render_h,
        )
        self.model.draw(screen, draw_rect, action, direction, self.animation_frame)
