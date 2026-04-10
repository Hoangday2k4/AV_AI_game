import pygame

from config.settings import *
from core.engine import Engine
from game.player import Player
from game.level import Level
from ui.hud import HUD


CAMERA_ENABLED = False


def draw_button(screen, rect, label, font, active=True):
    fill = (170, 170, 170) if active else (100, 100, 100)
    border = (45, 45, 45)
    pygame.draw.rect(screen, fill, rect, border_radius=8)
    pygame.draw.rect(screen, border, rect, 3, border_radius=8)
    text_color = (25, 25, 25) if active else (60, 60, 60)
    text = font.render(label, True, text_color)
    screen.blit(text, text.get_rect(center=rect.center))


def draw_overlay_panel(screen, title, subtitle=None):
    panel = pygame.Rect(WIDTH // 2 - 330, HEIGHT // 2 - 210, 660, 420)
    pygame.draw.rect(screen, (35, 35, 35), panel, border_radius=14)
    pygame.draw.rect(screen, (180, 180, 180), panel, 4, border_radius=14)

    title_font = pygame.font.SysFont("Georgia", 70, bold=True)
    title_text = title_font.render(title, True, (235, 218, 92))
    screen.blit(title_text, title_text.get_rect(center=(panel.centerx, panel.y + 85)))

    if subtitle:
        subtitle_font = pygame.font.SysFont("Georgia", 34)
        sub = subtitle_font.render(subtitle, True, (230, 230, 230))
        screen.blit(sub, sub.get_rect(center=(panel.centerx, panel.y + 155)))

    return panel


engine = Engine()
player = Player()
level = Level()
hud = HUD()

view_camera_width = CAMERA_WIDTH if CAMERA_ENABLED else 0
view_game_width = WIDTH - view_camera_width
map_scale = min(view_game_width / level.width, HEIGHT / level.height)
map_draw_w = level.width * map_scale
map_draw_h = level.height * map_scale
map_offset_x = view_camera_width + (view_game_width - map_draw_w) / 2
map_offset_y = (HEIGHT - map_draw_h) / 2
player_sprite_scale = 1.4
player_foot_offset = int(11 * map_scale)


def reset_player():
    start = level.player_start
    player.rect.topleft = (int(start.x), int(start.y))
    player.vel_x = 0
    player.vel_y = 0
    player.on_ground = False
    player.last_direction = "RIGHT"


def render_game(current_action):
    engine.screen.fill((18, 18, 18))
    pygame.draw.rect(
        engine.screen,
        (10, 10, 10),
        (view_camera_width, 0, view_game_width, HEIGHT),
    )
    level.draw(
        engine.screen,
        offset_x=map_offset_x,
        offset_y=map_offset_y,
        scale=map_scale,
    )
    player.draw(
        engine.screen,
        current_action,
        offset_x=map_offset_x,
        offset_y=map_offset_y,
        scale=map_scale,
        sprite_scale=player_sprite_scale,
        foot_offset=player_foot_offset,
    )
    hud.draw(engine.screen, current_action)


reset_player()

state = "menu"  # menu | level_select | game | pause | game_over
action = "IDLE"
running = True

title_font = pygame.font.SysFont("Georgia", 86, bold=True)
menu_btn_font = pygame.font.SysFont("Georgia", 44, bold=True)
small_font = pygame.font.SysFont("Georgia", 32, bold=True)

while running:
    mouse_pos = pygame.mouse.get_pos()
    mouse_clicked = False

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_clicked = True
        elif event.type == pygame.KEYDOWN:
            if state == "game" and event.key in (pygame.K_ESCAPE, pygame.K_p):
                state = "pause"
            elif state == "pause" and event.key in (pygame.K_ESCAPE, pygame.K_p):
                state = "game"

    if state == "menu":
        engine.screen.fill((45, 37, 19))
        title = title_font.render("FOREST TEMPLE", True, (236, 199, 69))
        engine.screen.blit(title, title.get_rect(center=(WIDTH // 2, 150)))

        play_rect = pygame.Rect(WIDTH // 2 - 150, 280, 300, 80)
        quit_rect = pygame.Rect(WIDTH // 2 - 150, 400, 300, 80)

        draw_button(engine.screen, play_rect, "PLAY", menu_btn_font)
        draw_button(engine.screen, quit_rect, "QUIT", menu_btn_font)

        if mouse_clicked:
            if play_rect.collidepoint(mouse_pos):
                state = "level_select"
            elif quit_rect.collidepoint(mouse_pos):
                running = False

    elif state == "level_select":
        engine.screen.fill((63, 52, 24))
        title = menu_btn_font.render("LEVEL SELECT", True, (236, 199, 69))
        engine.screen.blit(title, title.get_rect(center=(WIDTH // 2, 95)))

        level1_rect = pygame.Rect(WIDTH // 2 - 70, HEIGHT // 2 - 70, 140, 140)
        back_rect = pygame.Rect(70, HEIGHT - 110, 180, 60)

        draw_button(engine.screen, level1_rect, "1", title_font)
        draw_button(engine.screen, back_rect, "BACK", small_font)

        if mouse_clicked:
            if level1_rect.collidepoint(mouse_pos):
                reset_player()
                state = "game"
            elif back_rect.collidepoint(mouse_pos):
                state = "menu"

    elif state == "game":
        pause_rect = pygame.Rect(WIDTH - 95, 18, 70, 48)
        pause_requested = mouse_clicked and pause_rect.collidepoint(mouse_pos)

        action = "IDLE"
        keys = pygame.key.get_pressed()
        moving_left = keys[pygame.K_LEFT]
        moving_right = keys[pygame.K_RIGHT]
        jumping = keys[pygame.K_UP]

        move_action = "IDLE"
        if moving_left and not moving_right:
            move_action = "LEFT"
        elif moving_right and not moving_left:
            move_action = "RIGHT"

        if jumping:
            action = "JUMP"
            if move_action in ("LEFT", "RIGHT"):
                player.last_direction = move_action
        else:
            action = move_action

        if not pause_requested:
            player.update(action, min_x=0, max_x=level.width)
            player.apply_gravity()
            player.move_and_collide(level.collide_rects)

            # Immortal mode off: touching hazards causes game over.
            lose = any(player.rect.colliderect(hazard) for hazard in level.hazard_rects)
            if lose:
                state = "game_over"
                action = "IDLE"
        else:
            state = "pause"
            action = "IDLE"

        render_game(action)
        draw_button(engine.screen, pause_rect, "II", small_font)

    elif state == "pause":
        render_game(action)
        panel = draw_overlay_panel(engine.screen, "PAUSED")
        end_rect = pygame.Rect(panel.x + 65, panel.y + 220, 180, 70)
        retry_rect = pygame.Rect(panel.x + 415, panel.y + 220, 180, 70)
        resume_rect = pygame.Rect(panel.centerx - 120, panel.y + 315, 240, 70)

        draw_button(engine.screen, end_rect, "END", small_font)
        draw_button(engine.screen, retry_rect, "RETRY", small_font)
        draw_button(engine.screen, resume_rect, "RESUME", small_font)

        if mouse_clicked:
            if end_rect.collidepoint(mouse_pos):
                state = "menu"
            elif retry_rect.collidepoint(mouse_pos):
                reset_player()
                state = "game"
            elif resume_rect.collidepoint(mouse_pos):
                state = "game"

    elif state == "game_over":
        render_game("IDLE")
        panel = draw_overlay_panel(engine.screen, "GAME OVER")
        menu_rect = pygame.Rect(panel.x + 65, panel.y + 300, 220, 70)
        retry_rect = pygame.Rect(panel.x + 375, panel.y + 300, 220, 70)

        draw_button(engine.screen, menu_rect, "MENU", small_font)
        draw_button(engine.screen, retry_rect, "RETRY", small_font)

        if mouse_clicked:
            if menu_rect.collidepoint(mouse_pos):
                state = "menu"
            elif retry_rect.collidepoint(mouse_pos):
                reset_player()
                state = "game"

    engine.update()
    engine.tick()

pygame.quit()
