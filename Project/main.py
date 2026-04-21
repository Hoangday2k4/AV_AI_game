import json
import os
import threading

import pygame

from config.settings import *
from core.engine import Engine
from game.player import Player
from game.level import Level
from ui.hud import HUD

try:
    from ui.camera_panel import CameraPanel
    from vision.camera import Camera
    from vision.pose_estimator import HandEstimator
    from vision.gesture_recognizer import GestureRecognizer
    VISION_AVAILABLE = True
except Exception:
    CameraPanel = None
    Camera = None
    HandEstimator = None
    GestureRecognizer = None
    VISION_AVAILABLE = False


CAMERA_ENABLED = True
FINGER_CONTROL_ENABLED = True
MAX_LIVES = 3
IMMORTAL_MODE = False  # Hazard death enabled
PROGRESS_FILE = os.path.join(os.path.dirname(__file__), "assets", "progress.json")

TARGET_WIN_MS = 90_000
STAR2_COIN_RATIO = 0.8
LEVEL_COUNT = 10
AVAILABLE_LEVELS = {1}


def load_progress():
    data = {"wallet": 0, "maps": {}}
    if not os.path.exists(PROGRESS_FILE):
        return data

    try:
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            data["wallet"] = int(raw.get("wallet", 0))
            maps = raw.get("maps", {})
            if isinstance(maps, dict):
                data["maps"] = maps
    except (OSError, ValueError, TypeError):
        pass
    return data


def save_progress(data):
    os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=True, indent=2)


def get_map_record(progress, map_id):
    maps = progress.setdefault("maps", {})
    rec = maps.get(map_id)
    if not isinstance(rec, dict):
        rec = {"completed": False, "coins_collected": [], "best_stars": 0, "best_time_ms": 0}
        maps[map_id] = rec
    if "completed" not in rec:
        rec["completed"] = False
    if "coins_collected" not in rec or not isinstance(rec["coins_collected"], list):
        rec["coins_collected"] = []
    rec["best_stars"] = int(rec.get("best_stars", 0))
    rec["best_time_ms"] = int(rec.get("best_time_ms", 0))
    return rec


def format_mmss(elapsed_ms):
    total_sec = max(0, int(elapsed_ms // 1000))
    mm = total_sec // 60
    ss = total_sec % 60
    return f"{mm:02d}:{ss:02d}"



def calc_stars(elapsed_ms, coin_collected, coin_total, lives_left):
    if coin_total <= 0:
        coin_total = 1

    # 3 stars: strict perfect clear.
    if elapsed_ms <= TARGET_WIN_MS and coin_collected >= coin_total and lives_left == MAX_LIVES:
        return 3

    # User-adjusted rule: if not 3 stars, then 2 stars with coin/life condition.
    coin_need_2 = max(1, int(coin_total * STAR2_COIN_RATIO + 0.9999))
    if coin_collected >= coin_need_2 and lives_left >= 2:
        return 2

    return 1


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


def draw_hearts(screen, lives, max_lives, origin_x=18, origin_y=12):
    heart_font = pygame.font.SysFont("Segoe UI Symbol", 36, bold=True)
    x0 = int(origin_x)
    y = int(origin_y)
    gap = 34
    for i in range(max_lives):
        color = (220, 45, 55) if i < lives else (95, 95, 95)
        heart = heart_font.render("♥", True, color)
        screen.blit(heart, (x0 + i * gap, y))


def draw_coin_hud(screen, map_coin_count, map_coin_total, wallet, left_x, top_y):
    font = pygame.font.SysFont("Georgia", 30, bold=True)
    coin_text = font.render(f"Coin {map_coin_count}/{map_coin_total}", True, (248, 233, 88))
    wallet_text = font.render(f"$ {wallet}", True, (245, 245, 245))

    coin_rect = coin_text.get_rect(topleft=(int(left_x), int(top_y)))
    wallet_rect = wallet_text.get_rect(topleft=(int(left_x), int(top_y + 38)))

    screen.blit(coin_text, coin_rect)
    screen.blit(wallet_text, wallet_rect)


def draw_timer(screen, elapsed_ms, center_x, top_y):
    text = format_mmss(elapsed_ms)
    font = pygame.font.SysFont("Georgia", 36, bold=True)
    surf = font.render(text, True, (245, 245, 245))
    rect = surf.get_rect(midtop=(int(center_x), int(top_y)))
    screen.blit(surf, rect)



def draw_loading_screen(screen, width, height, progress, title="Gr. 14 AV_AI"):
    p = max(0.0, min(1.0, float(progress)))
    screen.fill((28, 26, 18))

    title_font = pygame.font.SysFont("Georgia", 110, bold=True)
    title_surf = title_font.render(title, True, (236, 199, 69))
    title_rect = title_surf.get_rect(center=(width // 2, height // 2 - 40))
    screen.blit(title_surf, title_rect)

    bar_w, bar_h = 520, 26
    bar_rect = pygame.Rect(width // 2 - bar_w // 2, height // 2 + 30, bar_w, bar_h)
    fill_rect = pygame.Rect(bar_rect.x + 4, bar_rect.y + 4, int((bar_w - 8) * p), bar_h - 8)
    pygame.draw.rect(screen, (55, 55, 55), bar_rect, border_radius=10)
    pygame.draw.rect(screen, (210, 178, 66), fill_rect, border_radius=8)
    pygame.draw.rect(screen, (170, 170, 170), bar_rect, 3, border_radius=10)

    pct_font = pygame.font.SysFont("Georgia", 26, bold=True)
    pct_surf = pct_font.render(f"{int(p * 100)}%", True, (232, 232, 232))
    screen.blit(pct_surf, pct_surf.get_rect(center=(width // 2, height // 2 + 80)))

    pygame.event.pump()
    pygame.display.update()
def show_toast(message, duration_ms=2000):
    global toast_text, toast_until_ms
    toast_text = str(message)
    toast_until_ms = pygame.time.get_ticks() + int(duration_ms)


def draw_toast(screen):
    if not toast_text:
        return

    now = pygame.time.get_ticks()
    if now >= toast_until_ms:
        return

    toast_font = pygame.font.SysFont("Georgia", 28, bold=True)
    text = toast_font.render(toast_text, True, (35, 35, 35))
    pad_x, pad_y = 22, 12
    box_w = text.get_width() + pad_x * 2
    box_h = text.get_height() + pad_y * 2
    box = pygame.Rect(0, 0, box_w, box_h)
    box.centerx = int(map_offset_x + map_draw_w / 2)
    box.top = int(map_offset_y + 56)

    pygame.draw.rect(screen, (250, 246, 220), box, border_radius=10)
    pygame.draw.rect(screen, (45, 45, 45), box, 3, border_radius=10)
    screen.blit(text, text.get_rect(center=box.center))


def draw_star_row(screen, stars, center_x, y, size=54):
    stars = max(0, min(3, int(stars)))
    font = pygame.font.SysFont("Segoe UI Symbol", size, bold=True)
    gap = int(size * 0.85)
    start_x = int(center_x - gap)
    for i in range(3):
        color = (245, 216, 78) if i < stars else (105, 105, 105)
        surf = font.render("★", True, color)
        rect = surf.get_rect(center=(start_x + i * gap, int(y)))
        screen.blit(surf, rect)


def build_level_buttons():
    buttons = []
    cols = 5
    btn_w, btn_h = 132, 92
    gap_x, gap_y = 22, 20
    total_w = cols * btn_w + (cols - 1) * gap_x
    x0 = WIDTH // 2 - total_w // 2
    y0 = HEIGHT // 2 - 55

    for idx in range(1, LEVEL_COUNT + 1):
        row = (idx - 1) // cols
        col = (idx - 1) % cols
        rect = pygame.Rect(x0 + col * (btn_w + gap_x), y0 + row * (btn_h + gap_y), btn_w, btn_h)
        buttons.append((idx, rect))

    return buttons


def set_current_level(level_idx):
    global current_level, level

    current_level = level_idx
    # Temporary: only level 1 exists, others are placeholders.
    level = Level()


def checkpoint_spawn_from_rect(rect):
    return pygame.Vector2(rect.centerx - player.rect.width / 2, rect.top - player.rect.height - 2)


def respawn_player(spawn_point):
    player.rect.topleft = (int(spawn_point.x), int(spawn_point.y))
    player.vel_x = 0
    player.vel_y = 0
    player.on_ground = False
    player.last_direction = "RIGHT"


def get_elapsed_ms(current_state):
    if current_state == "game":
        return pygame.time.get_ticks() - level_start_ticks - paused_accum_ms
    if current_state == "pause" and pause_started_ticks is not None:
        return pause_started_ticks - level_start_ticks - paused_accum_ms
    return final_elapsed_ms


def reset_run():
    global lives, active_checkpoint, checkpoint2_spawn, checkpoint2_activated
    global control_locked_after_respawn, run_base_collected_keys
    global level_start_ticks, paused_accum_ms, pause_started_ticks, final_elapsed_ms
    global best_stars_current, best_time_current, last_win_stars
    global toast_text, toast_until_ms

    level.reset_runtime_state()
    lives = MAX_LIVES

    checkpoint1_spawn = pygame.Vector2(level.player_start)
    active_checkpoint = pygame.Vector2(checkpoint1_spawn)

    checkpoint2_spawn = None
    checkpoint2_activated = False
    control_locked_after_respawn = False

    if len(level.checkpoint_rects) >= 2:
        cp2_rect = max(level.checkpoint_rects, key=lambda r: (r.x, r.y))
        checkpoint2_spawn = checkpoint_spawn_from_rect(cp2_rect)

    rec = get_map_record(progress_data, level.map_id)
    best_stars_current = int(rec.get("best_stars", 0))
    best_time_current = int(rec.get("best_time_ms", 0))

    if rec.get("completed", False):
        base = set(str(k) for k in rec.get("coins_collected", []))
    else:
        base = set()
    run_base_collected_keys = set(base)
    level.apply_collected_coins(base)

    level_start_ticks = pygame.time.get_ticks()
    paused_accum_ms = 0
    pause_started_ticks = None
    final_elapsed_ms = 0
    last_win_stars = 0
    toast_text = ""
    toast_until_ms = 0

    respawn_player(active_checkpoint)


def commit_win_progress(stars_earned, elapsed_ms):
    global wallet_coins, best_stars_current, best_time_current

    rec = get_map_record(progress_data, level.map_id)
    current = set(level.collected_coin_keys)
    newly_collected = current - run_base_collected_keys

    if newly_collected:
        wallet_coins += len(newly_collected)

    rec["completed"] = True
    rec["coins_collected"] = sorted(current)
    rec["best_stars"] = max(int(rec.get("best_stars", 0)), int(stars_earned))

    prev_best_time = int(rec.get("best_time_ms", 0))
    if prev_best_time <= 0 or elapsed_ms < prev_best_time:
        rec["best_time_ms"] = int(elapsed_ms)

    best_stars_current = int(rec["best_stars"])
    best_time_current = int(rec.get("best_time_ms", 0))
    progress_data["wallet"] = wallet_coins
    save_progress(progress_data)


def render_game(current_action, state_for_timer):
    engine.screen.fill((18, 18, 18))
    if view_camera_width > 0:
        pygame.draw.rect(
            engine.screen,
            (10, 10, 10),
            (0, 0, view_camera_width, HEIGHT),
        )
        if camera_panel is not None:
            camera_panel.draw(engine.screen, camera_frame, view_camera_width, HEIGHT)

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

    draw_hearts(engine.screen, lives, MAX_LIVES, origin_x=map_offset_x + 12, origin_y=map_offset_y + 8)

    draw_coin_hud(
        engine.screen,
        map_coin_count=len(level.collected_coin_keys),
        map_coin_total=level.total_coin_count,
        wallet=wallet_coins,
        left_x=map_offset_x + 12,
        top_y=map_offset_y + 48,
    )

    draw_timer(
        engine.screen,
        elapsed_ms=get_elapsed_ms(state_for_timer),
        center_x=map_offset_x + map_draw_w / 2,
        top_y=map_offset_y + 8,
    )
    draw_toast(engine.screen)


engine = Engine()
WIDTH, HEIGHT = engine.screen.get_size()


loading_progress = 0.0

def update_loading(progress, smooth=True):
    global loading_progress
    target = max(0.0, min(1.0, float(progress)))

    if smooth and target > loading_progress:
        start = loading_progress
        steps = max(1, int((target - start) * 50))
        for i in range(1, steps + 1):
            p = start + (target - start) * (i / steps)
            draw_loading_screen(engine.screen, WIDTH, HEIGHT, p)
            pygame.time.delay(10)
    else:
        draw_loading_screen(engine.screen, WIDTH, HEIGHT, target)

    loading_progress = target


update_loading(0.05)
CAMERA_WIDTH = int(WIDTH * 0.2)

update_loading(0.12)
player = Player()

update_loading(0.35)
level = Level()

update_loading(0.50)
hud = HUD()

camera = None
hand_estimator = None
gesture_recognizer = None
camera_panel = None
camera_ready = False

update_loading(0.62)
if FINGER_CONTROL_ENABLED and VISION_AVAILABLE:
    camera_init = {
        "ready": False,
        "camera": None,
        "hand_estimator": None,
        "gesture_recognizer": None,
        "camera_panel": None,
    }

    def _init_camera_worker():
        try:
            local_camera = Camera()
            local_hand = HandEstimator()
            local_gesture = GestureRecognizer()
            local_panel = CameraPanel()
            camera_init["camera"] = local_camera
            camera_init["hand_estimator"] = local_hand
            camera_init["gesture_recognizer"] = local_gesture
            camera_init["camera_panel"] = local_panel
            camera_init["ready"] = True
        except Exception:
            camera_init["ready"] = False

    worker = threading.Thread(target=_init_camera_worker, daemon=True)
    worker.start()

    while worker.is_alive():
        next_progress = min(0.86, loading_progress + 0.006)
        update_loading(next_progress, smooth=False)
        pygame.time.delay(16)

    worker.join()

    if camera_init["ready"]:
        camera = camera_init["camera"]
        hand_estimator = camera_init["hand_estimator"]
        gesture_recognizer = camera_init["gesture_recognizer"]
        camera_panel = camera_init["camera_panel"]
        camera_ready = True
    else:
        camera = None
        hand_estimator = None
        gesture_recognizer = None
        camera_panel = None
        camera_ready = False

update_loading(0.88)
progress_data = load_progress()
wallet_coins = int(progress_data.get("wallet", 0))

view_camera_width = CAMERA_WIDTH if (CAMERA_ENABLED and camera_ready) else 0
view_game_width = WIDTH - view_camera_width
map_scale = min(view_game_width / level.width, HEIGHT / level.height)
map_draw_w = level.width * map_scale
map_draw_h = level.height * map_scale
map_offset_x = view_camera_width + (view_game_width - map_draw_w) / 2
map_offset_y = (HEIGHT - map_draw_h) / 2
player_sprite_scale = 1.4
player_foot_offset = int(8 * map_scale)

current_level = 1

lives = MAX_LIVES
active_checkpoint = pygame.Vector2(level.player_start)
checkpoint2_spawn = None
checkpoint2_activated = False
control_locked_after_respawn = False
run_base_collected_keys = set()

level_start_ticks = pygame.time.get_ticks()
paused_accum_ms = 0
pause_started_ticks = None
final_elapsed_ms = 0

last_win_stars = 0
best_stars_current = 0
best_time_current = 0
toast_text = ""
toast_until_ms = 0

reset_run()
update_loading(1.0)
pygame.time.delay(180)

state = "menu"  # menu | level_select | game | pause | game_over | win
action = "IDLE"
running = True

title_font = pygame.font.SysFont("Georgia", 86, bold=True)
menu_btn_font = pygame.font.SysFont("Georgia", 44, bold=True)
small_font = pygame.font.SysFont("Georgia", 32, bold=True)
while running:
    camera_frame = None
    gesture_action = "IDLE"
    if camera_ready and camera is not None and hand_estimator is not None and gesture_recognizer is not None:
        camera_frame = camera.read()
        landmarks = hand_estimator.detect(camera_frame)
        gesture_action = gesture_recognizer.predict(landmarks)

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
                if pause_started_ticks is None:
                    pause_started_ticks = pygame.time.get_ticks()
            elif state == "pause" and event.key in (pygame.K_ESCAPE, pygame.K_p):
                state = "game"
                if pause_started_ticks is not None:
                    paused_accum_ms += pygame.time.get_ticks() - pause_started_ticks
                    pause_started_ticks = None

    if state == "menu":
        engine.screen.fill((45, 37, 19))

        menu_center_y = HEIGHT // 2
        title = title_font.render("FOREST TEMPLE", True, (236, 199, 69))
        engine.screen.blit(title, title.get_rect(center=(WIDTH // 2, menu_center_y - 170)))

        btn_w, btn_h, btn_gap = 300, 80, 24
        first_btn_y = menu_center_y - (btn_h + btn_gap // 2)
        play_rect = pygame.Rect(WIDTH // 2 - btn_w // 2, first_btn_y, btn_w, btn_h)
        quit_rect = pygame.Rect(WIDTH // 2 - btn_w // 2, first_btn_y + btn_h + btn_gap, btn_w, btn_h)

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

        back_rect = pygame.Rect(70, HEIGHT - 110, 180, 60)
        draw_button(engine.screen, back_rect, "BACK", small_font)

        for idx, rect in build_level_buttons():
            active = idx in AVAILABLE_LEVELS
            draw_button(engine.screen, rect, str(idx), menu_btn_font, active=active)

        if mouse_clicked:
            if back_rect.collidepoint(mouse_pos):
                state = "menu"
            else:
                for idx, rect in build_level_buttons():
                    if rect.collidepoint(mouse_pos) and idx in AVAILABLE_LEVELS:
                        set_current_level(idx)
                        reset_run()
                        state = "game"
                        break

    elif state == "game":
        pause_rect = pygame.Rect(WIDTH - 95, 18, 70, 48)
        pause_requested = mouse_clicked and pause_rect.collidepoint(mouse_pos)

        action = "IDLE"
        keys = pygame.key.get_pressed()
        moving_left = keys[pygame.K_LEFT] or (gesture_action == "LEFT")
        moving_right = keys[pygame.K_RIGHT] or (gesture_action == "RIGHT")
        jumping = keys[pygame.K_UP] or (gesture_action == "JUMP")

        movement_keys_down = moving_left or moving_right or jumping
        if control_locked_after_respawn:
            if movement_keys_down:
                moving_left = False
                moving_right = False
                jumping = False
            else:
                control_locked_after_respawn = False

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

            if (not checkpoint2_activated) and checkpoint2_spawn is not None and len(level.checkpoint_rects) >= 2:
                cp2_rect = max(level.checkpoint_rects, key=lambda r: (r.x, r.y))
                if player.rect.colliderect(cp2_rect):
                    checkpoint2_activated = True
                    active_checkpoint = pygame.Vector2(checkpoint2_spawn)
                    show_toast("Checkpointed")

            interaction = level.handle_player_interactions(player)
            if interaction["key_collected"]:
                show_toast("Gate opened")
            if interaction["win"]:
                final_elapsed_ms = get_elapsed_ms("game")
                last_win_stars = calc_stars(
                    elapsed_ms=final_elapsed_ms,
                    coin_collected=len(level.collected_coin_keys),
                    coin_total=level.total_coin_count,
                    lives_left=lives,
                )
                commit_win_progress(last_win_stars, final_elapsed_ms)
                state = "win"
                action = "IDLE"
            else:
                lose = (not IMMORTAL_MODE) and any(player.rect.colliderect(hazard) for hazard in level.hazard_rects)
                if lose:
                    lives -= 1
                    if lives > 0:
                        respawn_player(active_checkpoint)
                        control_locked_after_respawn = True
                        action = "IDLE"
                    else:
                        final_elapsed_ms = get_elapsed_ms("game")
                        state = "game_over"
                        action = "IDLE"
        else:
            state = "pause"
            pause_started_ticks = pygame.time.get_ticks()
            action = "IDLE"

        render_game(action, "game")
        draw_button(engine.screen, pause_rect, "II", small_font)

    elif state == "pause":
        render_game(action, "pause")
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
                reset_run()
                state = "game"
            elif resume_rect.collidepoint(mouse_pos):
                if pause_started_ticks is not None:
                    paused_accum_ms += pygame.time.get_ticks() - pause_started_ticks
                    pause_started_ticks = None
                state = "game"

    elif state == "game_over":
        render_game("IDLE", "game_over")
        panel = draw_overlay_panel(engine.screen, "GAME OVER")
        menu_rect = pygame.Rect(panel.x + 65, panel.y + 300, 220, 70)
        retry_rect = pygame.Rect(panel.x + 375, panel.y + 300, 220, 70)

        draw_button(engine.screen, menu_rect, "BACK", small_font)
        draw_button(engine.screen, retry_rect, "RETRY", small_font)

        if mouse_clicked:
            if menu_rect.collidepoint(mouse_pos):
                state = "level_select"
            elif retry_rect.collidepoint(mouse_pos):
                reset_run()
                state = "game"

    elif state == "win":
        render_game("IDLE", "win")
        panel = draw_overlay_panel(engine.screen, "YOU WIN")

        info_font = pygame.font.SysFont("Georgia", 28)
        symbol_font = pygame.font.SysFont("Segoe UI Symbol", 30, bold=True)

        time_ok = final_elapsed_ms <= TARGET_WIN_MS
        coin_ok = (level.total_coin_count == 0) or (len(level.collected_coin_keys) >= level.total_coin_count)
        heart_ok = lives >= 2

        draw_star_row(engine.screen, last_win_stars, panel.centerx, panel.y + 158, size=52)

        row_w, row_h = 520, 38
        row_x = panel.centerx - row_w // 2
        row_y0 = panel.y + 186
        row_gap = 6

        stats = [
            ("TIME", f"{format_mmss(final_elapsed_ms)} / {format_mmss(TARGET_WIN_MS)}", time_ok),
            ("COIN", f"{len(level.collected_coin_keys)}/{level.total_coin_count}", coin_ok),
            ("HEART", f"{lives}/{MAX_LIVES}", heart_ok),
        ]

        for idx, (label, value, ok) in enumerate(stats):
            ry = row_y0 + idx * (row_h + row_gap)
            row_rect = pygame.Rect(row_x, ry, row_w, row_h)
            pygame.draw.rect(engine.screen, (236, 236, 236), row_rect, border_radius=7)
            pygame.draw.rect(engine.screen, (35, 35, 35), row_rect, 2, border_radius=7)

            color = (20, 20, 20) if ok else (200, 35, 35)
            symbol = "✓" if ok else "✗"

            label_surf = info_font.render(f"{label}:", True, color)
            value_surf = info_font.render(value, True, color)
            symbol_surf = symbol_font.render(symbol, True, color)

            label_x = row_rect.x + 16
            value_x = row_rect.x + 150
            engine.screen.blit(label_surf, label_surf.get_rect(midleft=(label_x, row_rect.centery)))
            engine.screen.blit(value_surf, value_surf.get_rect(midleft=(value_x, row_rect.centery)))
            engine.screen.blit(symbol_surf, symbol_surf.get_rect(center=(row_rect.right - 24, row_rect.centery)))

        next_rect = pygame.Rect(panel.x + 65, panel.y + 372, 220, 46)
        retry_rect = pygame.Rect(panel.x + 375, panel.y + 372, 220, 46)

        draw_button(engine.screen, next_rect, "NEXT", small_font)
        draw_button(engine.screen, retry_rect, "RETRY", small_font)

        if mouse_clicked:
            if next_rect.collidepoint(mouse_pos):
                state = "level_select"
            elif retry_rect.collidepoint(mouse_pos):
                reset_run()
                state = "game"

    engine.update()
    engine.tick()

if camera is not None:
    camera.release()

pygame.quit()











































