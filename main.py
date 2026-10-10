"""
Main entry point for Fishing Game FPS (Low Fish).
Повна гра: FPS-рух, надійна фізика заземлення та спавну, захист від провалювання крізь карту,
риболовля, NPC, магазин, інвентар, квести, збереження/завантаження, пауза/меню.
"""

import sys
import os

# --- Windowed mode: redirect stdout/stderr to log file ---
def _setup_logging():
    """Redirect output to logs/game.log when running as frozen EXE (no console)."""
    if getattr(sys, 'frozen', False):
        # Determine base dir: next to the EXE
        base_dir = os.path.dirname(sys.executable)
        log_dir = os.path.join(base_dir, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, 'game.log')
        try:
            sys.stdout = open(log_path, 'w', encoding='utf-8', buffering=1)
            sys.stderr = sys.stdout
        except Exception:
            pass

_setup_logging()

from ursina import *
from panda3d.core import NodePath
import gltf
import math
import random
from game_state import GameState, SAVE_FILE

# Ініціалізація Ursina
app = Ursina(
    title="Fishing Game FPS - 3D Озерна Риболовля",
    borderless=False,
    fullscreen=False,
    development_mode=False
)
window.size = (1280, 720)
window.color = color.rgb(135, 206, 235)  # колір неба

# Спільний стан гри
state = GameState()
state.load_from_file()

# Безпечна резервна позиція за замовчуванням (всередині будинку на підлозі)
DEFAULT_SPAWN_INSIDE_HOUSE = Vec3(0, 0.45, 6.5)


class Interactable(Entity):
    def __init__(self, prompt_text="Взаємодія", on_interact=None, **kwargs):
        super().__init__(**kwargs)
        self.prompt_text = prompt_text
        self.on_interact = on_interact
        if not self.collider:
            self.collider = 'box'

    def interact(self, player):
        if self.on_interact:
            self.on_interact(player)


# --- ПОБУДОВА СВІТУ (Створюється ДО появи гравця) ---
Sky()

# 1. Тверда земля (товстий куб, крізь який фізично неможливо провалитися)
ground = Entity(
    model='cube',
    scale=(120, 4.0, 120),
    position=(0, -2.0, 0),
    texture='grass',
    collider='box'
)

sun = DirectionalLight(y=15, rotation=(45, -45, 0))

# 2. Будинок рибалки (стіни, підлога, дах, відкритий прохід для дверей)
# Підлога будинку (товста платформа, щоб гравець надійно стояв усередині)
house_floor = Entity(
    model='cube',
    scale=(8.0, 0.4, 6.0),
    position=(0, 0.2, 7.0),
    color=color.rgb(120, 85, 55),
    collider='box'
)

# Задня та бічні стіни
house_wall_back = Entity(model='cube', scale=(8.0, 3.5, 0.5), position=(0, 1.95, 10.0), color=color.dark_gray, collider='box')
house_wall_left = Entity(model='cube', scale=(0.5, 3.5, 6.0), position=(-4.0, 1.95, 7.0), color=color.dark_gray, collider='box')
house_wall_right = Entity(model='cube', scale=(0.5, 3.5, 6.0), position=(4.0, 1.95, 7.0), color=color.dark_gray, collider='box')

# Передня стіна з реальним проходом для дверей (лівий сегмент, правий сегмент і перемичка над дверима)
# Прохід шириною 1.6 по центру (від x=-0.8 до x=0.8)
house_wall_front_left = Entity(model='cube', scale=(3.2, 3.5, 0.5), position=(-2.4, 1.95, 4.0), color=color.dark_gray, collider='box')
house_wall_front_right = Entity(model='cube', scale=(3.2, 3.5, 0.5), position=(2.4, 1.95, 4.0), color=color.dark_gray, collider='box')
house_wall_front_top = Entity(model='cube', scale=(1.6, 1.1, 0.5), position=(0, 3.15, 4.0), color=color.dark_gray, collider='box')

# Дах будинку
house_roof = Entity(model='cube', scale=(8.6, 0.5, 6.6), position=(0, 3.9, 7.0), color=color.brown, collider='box')

# 3. Інтерактивні двері (повертаються/відчиняються або сповіщають)
door_opened = False
door_pivot = Entity(position=(-0.7, 0.4, 4.0))
door_panel = Entity(
    parent=door_pivot,
    model='cube',
    scale=(1.4, 2.3, 0.1),
    position=(0.7, 1.15, 0),
    color=color.orange,
    collider='box'
)

def toggle_door(p):
    global door_opened
    door_opened = not door_opened
    target_rot = -90 if door_opened else 0
    door_pivot.animate_rotation_y(target_rot, duration=0.4)
    status_msg = "Двері відчинено!" if door_opened else "Двері зачинено!"
    p.show_notification(status_msg, duration=1.5, col=color.azure)

door_interactable = Interactable(
    prompt_text="Відкрити/Зачинити двері",
    parent=door_pivot,
    model='cube',
    scale=(1.4, 2.3, 0.3),
    position=(0.7, 1.15, 0),
    visible=False,
    collider='box',
    on_interact=toggle_door
)

# Допоміжна функція для завантаження повноцінних 3D GLB/glTF моделей
def load_gltf_entity(model_path, **kwargs):
    entity = Entity(**kwargs)
    try:
        if os.path.exists(model_path):
            model_root = gltf.load_model(model_path)
            np = NodePath(model_root)
            np.reparentTo(entity)
        else:
            # Резервна геометрія, якщо файл відсутній
            Entity(parent=entity, model='cube', scale=(0.6, 1.8, 0.6), color=color.azure)
    except Exception as e:
        print(f"[WARN] Не вдалося завантажити 3D модель {model_path}: {e}")
        Entity(parent=entity, model='cube', scale=(0.6, 1.8, 0.6), color=color.azure)
    return entity

# 4. NPC: Дід Василь (Рибалка біля будинку)
npc_3d = load_gltf_entity(
    'assets/fisherman_npc.glb',
    position=(-3.0, 0.0, 1.5),
    scale=0.7,
    rotation_y=135
)
npc = Interactable(
    prompt_text="Поговорити",
    model='cube',
    scale=(0.8, 2.0, 0.8),
    position=(-3.0, 1.0, 1.5),
    visible=False,
    collider='box',
    on_interact=lambda p: open_dialogue(
        "Дід Василь",
        "Здоровенькі були! Озеро тут багате на карасів, окунів та щук.\n"
        "Візьми наживку в магазині ліворуч від озера та вирушай на риболовний місток!"
    )
)

# 5. Магазин рибалки та 3D Моделька Продавця вудок
shop_booth = Entity(model='cube', scale=(3.2, 2.6, 2.8), position=(7.0, 1.3, -2.0), color=color.rgb(75, 50, 30), collider='box')
shop_counter = Entity(model='cube', scale=(2.2, 1.1, 0.6), position=(7.0, 0.55, -3.2), color=color.rgb(130, 90, 50), collider='box')

# 3D Моделька продавця вудок (стоячи за прилавком магазину)
shopkeeper_3d = load_gltf_entity(
    'assets/shopkeeper.glb',
    position=(7.0, 0.0, -2.1),
    scale=0.72,
    rotation_y=0
)

# Вудка як вітринний товар біля продавця
shop_display_rod = Entity(
    model='cylinder',
    scale=(0.04, 2.2, 0.04),
    position=(7.7, 1.1, -3.1),
    rotation=(15, 0, -15),
    color=color.rgb(200, 160, 40)
)

shop_interaction = Interactable(
    prompt_text="Магазин вудок та наживки",
    model='cube',
    scale=(2.4, 2.0, 1.2),
    position=(7.0, 1.0, -3.0),
    visible=False,
    collider='box',
    on_interact=lambda p: open_shop_ui()
)

# 6. Дерева та каміння
for tree_pos in [(-9, 0, 8), (-13, 0, -2), (11, 0, 7), (8, 0, 13), (-7, 0, -8), (-4, 0, 14)]:
    Entity(model='cylinder', scale=(0.6, 3.5, 0.6), position=Vec3(*tree_pos) + Vec3(0, 1.75, 0), color=color.brown, collider='box')
    Entity(model='sphere', scale=3.0, position=Vec3(*tree_pos) + Vec3(0, 4.5, 0), color=color.green, collider='box')

for rock_pos in [(-5, 0.4, 3), (4, 0.5, 1.5), (-8, 0.6, -4)]:
    Entity(model='cube', scale=(1.2, 0.8, 1.2), position=rock_pos, color=color.gray, collider='box')

# 7. Водойма, пірс та точка риболовлі
water = Entity(model='plane', scale=32, position=(0, 0.05, -18), color=color.rgba(30, 144, 255, 200), collider='box')
pier = Entity(model='cube', scale=(2.6, 0.3, 9.0), position=(0, 0.15, -11.5), color=color.brown, collider='box')

fishing_spot = Interactable(
    prompt_text="Рибалити",
    model='cylinder',
    scale=(1.5, 0.08, 1.5),
    position=(0, 0.31, -15.0),
    color=color.lime,
    on_interact=lambda p: p.start_fishing(target_water_pos=Vec3(0, 0.1, -20.0))
)


class FPSPlayer(Entity):
    """
    Надійний FPS-контролер з повною системою заземлення, колізій та захисту від провалювання.
    """
    def __init__(self, **kwargs):
        super().__init__()

        # Швидкості
        self.walk_speed = 5.2
        self.run_speed = 9.0
        self.crouch_speed = 2.5
        self.velocity = Vec3(0, 0, 0)
        self.acceleration = 14.0
        self.friction = 11.0

        # Фізика стрибка та гравітація
        self.jump_height = 1.25
        self.gravity = 25.0
        self.vertical_velocity = 0.0
        self.grounded = True

        # Висота очей
        self.standing_height = 1.8
        self.crouch_height = 1.0
        self.current_eye_height = self.standing_height
        self.is_crouching = False

        # Огляд мишкою
        self.mouse_sensitivity = Vec2(40, 40)
        self.camera_pitch = 0.0
        self.camera_yaw = 0.0
        self.pitch_range = (-85, 85)

        # Camera Bobbing
        self.bob_timer = 0.0

        # Безпечна точка повернення
        self.last_safe_position = Vec3(DEFAULT_SPAWN_INSIDE_HOUSE)
        self.position = Vec3(DEFAULT_SPAWN_INSIDE_HOUSE)

        # Колідер гравця
        self.collider = BoxCollider(self, center=Vec3(0, 0.9, 0), size=Vec3(0.6, 1.8, 0.6))

        # Камера
        camera.parent = self
        camera.position = Vec3(0, self.current_eye_height, 0)
        camera.rotation = Vec3(0, 0, 0)
        camera.fov = 85

        # HUD: Приціл
        self.crosshair = Entity(
            parent=camera.ui,
            model='quad',
            texture='circle',
            scale=0.008,
            color=color.rgba(255, 255, 255, 220)
        )

        # HUD: Підказка взаємодії (E)
        self.prompt_text = Text(
            text='',
            parent=camera.ui,
            origin=(0, 0),
            position=(0, -0.08),
            scale=1.2,
            color=color.yellow,
            background=True
        )
        self.prompt_text.enabled = False

        # HUD: Інформаційна панель гравця
        self.hud_text = Text(
            text='',
            parent=camera.ui,
            position=(-0.85, 0.45),
            scale=1.1,
            color=color.white,
            background=True
        )
        self.update_hud()

        # Повідомлення на екрані
        self.notify_text = Text(
            text='',
            parent=camera.ui,
            origin=(0, 0),
            position=(0, 0.2),
            scale=1.3,
            color=color.lime,
            background=True
        )
        self.notify_text.enabled = False

        # Взаємодія
        self.interaction_distance = 3.8
        self.current_target = None

        # Риболовля
        self.is_fishing = False
        self.fishing_camera_locked = False
        self.bobber = None
        self.fishing_line = None
        self.has_bite = False

        # UI стан
        self.active_ui = None
        self.lock_mouse()

        for key, value in kwargs.items():
            setattr(self, key, value)

    def lock_mouse(self):
        mouse.locked = True
        mouse.visible = False

    def unlock_mouse(self):
        mouse.locked = False
        mouse.visible = True

    def show_notification(self, msg, duration=2.5, col=color.lime):
        self.notify_text.text = msg
        self.notify_text.color = col
        self.notify_text.enabled = True
        invoke(lambda: setattr(self.notify_text, 'enabled', False), delay=duration)

    def update_hud(self):
        needed_xp = state.level * 100
        self.hud_text.text = (
            f"Рівень: {state.level}  |  XP: {state.xp}/{needed_xp}\n"
            f"Баланс: {state.money} грн  |  Вудка: {state.current_rod}\n"
            f"Черв'яки: {state.inventory.get('Черв\'яки', 0)}  |  Блешня: {state.inventory.get('Блешня', 0)}"
        )

    def safe_spawn_at(self, target_coord):
        """
        Перевіряє поверхню під цільовою координатою за допомогою Raycast вниз.
        Якщо знайдено поверхню — ставимо гравця точно на неї (підлога/земля).
        Якщо ні — ставимо в резервний дефолтний спавн всередині будинку.
        """
        # Стріляємо променем з висоти очей або трохи вище (не вище даху)
        probe_start_y = min(target_coord.y + 1.5, 3.2)
        start_probe = Vec3(target_coord.x, probe_start_y, target_coord.z)
        hit = raycast(start_probe, Vec3(0, -1, 0), distance=8.0, ignore=(self, house_roof))

        if hit.hit and hit.world_point is not None:
            surface_y = hit.world_point.y
            self.position = Vec3(target_coord.x, surface_y + 0.05, target_coord.z)
        else:
            self.position = Vec3(DEFAULT_SPAWN_INSIDE_HOUSE)

        self.vertical_velocity = 0.0
        self.grounded = True
        self.last_safe_position = Vec3(self.position)

    def update(self):
        if self.active_ui:
            return

        # Обмежуємо дельта-час, щоб стрибки кадрів (лаг) не спричиняли тунелювання крізь колізії
        dt = min(time.dt, 0.05)

        # Огляд мишкою
        if not self.fishing_camera_locked:
            self.handle_camera_look(dt)

        # Рух чи риболовля
        if not self.is_fishing:
            self.handle_movement(dt)
            self.handle_bobbing(dt)
            self.check_interaction()
            self.check_safety_bounds()
        else:
            self.update_fishing(dt)

    def check_safety_bounds(self):
        """
        Анти-провалювання: якщо гравець опустився нижче допустимої висоти (y < -1.5),
        миттєво повертаємо його на останню безпечну позицію з нульовою швидкістю.
        """
        if self.y < -1.5:
            self.position = Vec3(self.last_safe_position)
            self.vertical_velocity = 0.0
            self.grounded = True
            self.show_notification("Повернено до безпечної точки!", duration=2.0, col=color.orange)

    def handle_camera_look(self, dt):
        self.camera_yaw += mouse.velocity[0] * self.mouse_sensitivity.x
        self.camera_pitch -= mouse.velocity[1] * self.mouse_sensitivity.y
        self.camera_pitch = clamp(self.camera_pitch, self.pitch_range[0], self.pitch_range[1])

        self.rotation_y = self.camera_yaw
        camera.rotation_x = self.camera_pitch

    def handle_movement(self, dt):
        # Присідання (Ctrl)
        self.is_crouching = held_keys['left control'] or held_keys['control']
        target_height = self.crouch_height if self.is_crouching else self.standing_height
        self.current_eye_height = lerp(self.current_eye_height, target_height, dt * 10)
        camera.y = self.current_eye_height

        # Швидкість (Shift)
        if self.is_crouching:
            target_speed = self.crouch_speed
        elif held_keys['shift'] or held_keys['left shift']:
            target_speed = self.run_speed
        else:
            target_speed = self.walk_speed

        move_dir = Vec3(
            (held_keys['d'] - held_keys['a']),
            0,
            (held_keys['w'] - held_keys['s'])
        ).normalized()

        is_moving = move_dir.length() > 0
        target_vel = (self.forward * move_dir.z + self.right * move_dir.x) * (target_speed if is_moving else 0)
        self.velocity = lerp(self.velocity, target_vel, dt * (self.acceleration if is_moving else self.friction))

        # Горизонтальні колізії (Raycast з перевіркою на рівні грудей)
        horiz_step = self.velocity * dt
        if horiz_step.length() > 0.0001:
            ray_origin = self.position + Vec3(0, 0.7, 0)
            hit = raycast(ray_origin, horiz_step.normalized(), distance=0.6, ignore=(self,))
            if not hit.hit:
                self.position += horiz_step
            else:
                slide = horiz_step - hit.normal * horiz_step.dot(hit.normal)
                self.position += slide

        # --- НАДІЙНЕ ЗАЗЕМЛЕННЯ ТА ГРАВІТАЦІЯ ---
        # Промінь пускаємо з висоти +0.6 від ніг гравця вниз
        ground_ray = raycast(self.position + Vec3(0, 0.6, 0), Vec3(0, -1, 0), distance=1.2, ignore=(self,))

        # Стрибок (Space)
        if held_keys['space'] and self.grounded and not self.is_crouching:
            self.vertical_velocity = math.sqrt(2 * self.gravity * self.jump_height)
            self.grounded = False
            self.y += self.vertical_velocity * dt
        else:
            if ground_ray.hit and ground_ray.world_point is not None:
                surface_y = ground_ray.world_point.y
                # Якщо ноги близько до поверхні або трохи нижче/вище
                dist_to_surface = self.y - surface_y

                if self.vertical_velocity <= 0 and dist_to_surface <= 0.25:
                    # Гравець надійно стоїть на поверхні
                    self.y = surface_y
                    self.vertical_velocity = 0.0
                    self.grounded = True
                    # Фіксуємо останню перевірену безпечну координату
                    if self.y >= -0.5:
                        self.last_safe_position = Vec3(self.position)
                else:
                    # Гравець у повітрі (падає до землі)
                    self.grounded = False
                    self.vertical_velocity -= self.gravity * dt
                    self.y += self.vertical_velocity * dt
                    if self.y < surface_y:
                        self.y = surface_y
                        self.vertical_velocity = 0.0
                        self.grounded = True
            else:
                # Поверхні під ногами взагалі немає (падіння)
                self.grounded = False
                self.vertical_velocity -= self.gravity * dt
                self.y += self.vertical_velocity * dt

    def handle_bobbing(self, dt):
        horiz_speed = Vec2(self.velocity.x, self.velocity.z).length()
        if horiz_speed > 0.4 and self.grounded:
            is_running = (held_keys['shift'] or held_keys['left shift']) and not self.is_crouching
            freq = 12.0 if is_running else 8.0
            amp = 0.07 if is_running else 0.035

            self.bob_timer += dt * freq
            camera.y = self.current_eye_height + math.sin(self.bob_timer) * amp
            camera.x = math.cos(self.bob_timer * 0.5) * (amp * 0.5)
        else:
            self.bob_timer = 0.0
            camera.y = lerp(camera.y, self.current_eye_height, dt * 10)
            camera.x = lerp(camera.x, 0, dt * 10)

    def check_interaction(self):
        hit = raycast(camera.world_position, camera.forward, distance=self.interaction_distance, ignore=(self,))
        if hit.hit and hasattr(hit.entity, 'prompt_text'):
            self.current_target = hit.entity
            self.prompt_text.text = f"Натисніть E — {hit.entity.prompt_text}"
            self.prompt_text.enabled = True
        else:
            self.current_target = None
            self.prompt_text.enabled = False

    def input(self, key):
        if key == 'escape':
            if self.active_ui:
                close_ui()
            else:
                open_pause_menu()
            return

        if self.active_ui:
            return

        if key == 'i' and not self.is_fishing:
            open_inventory_ui()
            return

        if key == 'q' and not self.is_fishing:
            open_quests_ui()
            return

        if key == 'e':
            if self.is_fishing:
                self.hook_fish()
            elif self.current_target and hasattr(self.current_target, 'interact'):
                self.current_target.interact(self)

    # --- РИБОЛОВЛЯ ---
    def start_fishing(self, target_water_pos):
        if state.inventory.get("Черв'яки", 0) <= 0 and state.inventory.get("Блешня", 0) <= 0:
            self.show_notification("Немає наживки! Купіть у магазині.", duration=3, col=color.red)
            return

        if state.inventory.get("Черв'яки", 0) > 0:
            state.inventory["Черв'яки"] -= 1
        elif state.inventory.get("Блешня", 0) > 0:
            state.inventory["Блешня"] -= 1
        self.update_hud()

        self.is_fishing = True
        self.fishing_camera_locked = True
        self.has_bite = False
        self.prompt_text.text = "Вудка закинута... Очікуйте клювання!"
        self.prompt_text.enabled = True

        camera.animate('rotation_x', 24, duration=0.8)

        self.bobber = Entity(
            model='sphere',
            color=color.orange,
            scale=0.18,
            position=target_water_pos
        )
        self.update_fishing_line()

        delay = random.uniform(2.5, 4.5)
        invoke(self.on_bite, delay=delay)

    def update_fishing_line(self):
        if not self.bobber:
            return
        hand_pos = camera.world_position + camera.forward * 0.6 + camera.down * 0.3 + camera.right * 0.35
        if self.fishing_line:
            destroy(self.fishing_line)
        self.fishing_line = Entity(
            model=Pipe(path=[hand_pos, self.bobber.position], thicknesses=[0.008, 0.008]),
            color=color.rgba(255, 255, 255, 140)
        )

    def update_fishing(self, dt):
        if self.bobber:
            self.update_fishing_line()

    def on_bite(self):
        if not self.is_fishing:
            return
        self.has_bite = True
        camera.shake(duration=0.6, magnitude=0.02)
        if self.bobber:
            self.bobber.animate_y(self.bobber.y - 0.2, duration=0.25, loop=True)
        self.prompt_text.text = "КЛЮЄ! Тисніть E для підсікання!"
        self.prompt_text.color = color.red

    def hook_fish(self):
        if not self.is_fishing:
            return

        if not self.has_bite:
            self.show_notification("Занадто рано! Риба зірвалася.", duration=2, col=color.red)
            self.finish_fishing_session()
            return

        rod_info = state.shop_rods.get(state.current_rod, {"luck_mult": 1.0})
        luck = rod_info.get("luck_mult", 1.0)

        roll = random.random() * luck
        if roll > 1.8:
            caught = "Сом"
        elif roll > 1.2:
            caught = "Щука"
        elif roll > 0.6:
            caught = "Окунь"
        else:
            caught = "Карась"

        state.on_fish_caught(caught)
        self.update_hud()

        fish_model = Entity(
            parent=camera,
            model='cube',
            scale=(0.35, 0.2, 0.7),
            color=color.cyan if caught != "Сом" else color.black90,
            position=(0, -0.25, 0.85),
            rotation=(15, 45, 10)
        )
        fish_model.animate_position((0, 0, 0.65), duration=0.35)
        destroy(fish_model, delay=1.8)

        self.prompt_text.text = f"УСПІХ! Ви виловили: {caught}!"
        self.prompt_text.color = color.lime
        invoke(self.finish_fishing_session, delay=1.6)

    def finish_fishing_session(self):
        if self.bobber:
            destroy(self.bobber)
            self.bobber = None
        if self.fishing_line:
            destroy(self.fishing_line)
            self.fishing_line = None

        self.is_fishing = False
        self.fishing_camera_locked = False
        self.prompt_text.color = color.yellow
        self.prompt_text.enabled = False
        camera.animate('rotation_x', self.camera_pitch, duration=0.4)


# --- ГЛОБАЛЬНІ МЕНЮ ТА UI ---
active_menu = None

def close_ui():
    global active_menu
    if active_menu:
        destroy(active_menu)
        active_menu = None
    player.active_ui = None
    player.lock_mouse()

def open_pause_menu():
    global active_menu
    if active_menu:
        close_ui()
        return

    player.active_ui = "PAUSE"
    player.unlock_mouse()

    active_menu = Entity(parent=camera.ui, model='quad', scale=(0.55, 0.72), color=color.rgba(20, 20, 28, 235))
    Text("ГОЛОВНЕ МЕНЮ", parent=active_menu, y=0.40, origin=(0, 0), scale=1.6, color=color.azure)

    def on_resume():
        close_ui()

    def on_new_game():
        # Скидання даних гри та надійний респавн всередині будинку
        global state
        if os.path.exists(SAVE_FILE):
            os.remove(SAVE_FILE)
        state = GameState()
        player.safe_spawn_at(DEFAULT_SPAWN_INSIDE_HOUSE)
        player.update_hud()
        player.show_notification("Розпочато Нову Гру!", col=color.lime)
        close_ui()

    def on_save():
        ok, msg = state.save_to_file(player_pos=(player.x, player.y, player.z))
        player.show_notification(msg, col=color.lime if ok else color.red)
        close_ui()

    def on_load():
        ok, msg = state.load_from_file()
        if ok and state.player_pos:
            player.safe_spawn_at(Vec3(state.player_pos[0], state.player_pos[1], state.player_pos[2]))
        player.update_hud()
        player.show_notification(msg, col=color.lime if ok else color.red)
        close_ui()

    def on_quit():
        application.quit()

    Button(text="Продовжити гру", parent=active_menu, y=0.22, scale=(0.7, 0.09), color=color.azure, on_click=on_resume)
    Button(text="Нова гра (New Game)", parent=active_menu, y=0.10, scale=(0.7, 0.09), color=color.rgb(180, 100, 30), on_click=on_new_game)
    Button(text="Зберегти гру", parent=active_menu, y=-0.02, scale=(0.7, 0.09), color=color.teal, on_click=on_save)
    Button(text="Завантажити збереження", parent=active_menu, y=-0.14, scale=(0.7, 0.09), color=color.olive, on_click=on_load)
    Button(text="Вийти з гри", parent=active_menu, y=-0.26, scale=(0.7, 0.09), color=color.red, on_click=on_quit)

def open_inventory_ui():
    global active_menu
    player.active_ui = "INVENTORY"
    player.unlock_mouse()

    active_menu = Entity(parent=camera.ui, model='quad', scale=(0.65, 0.7), color=color.rgba(20, 25, 35, 240))
    Text("ІНВЕНТАР ГРАВЦЯ", parent=active_menu, y=0.4, origin=(0, 0), scale=1.5, color=color.gold)

    inv_lines = []
    inv_lines.append(f"Вудка в руках: {state.current_rod}")
    inv_lines.append(f"Усі вудки: {', '.join(state.owned_rods)}")
    inv_lines.append("-----------------------------")
    inv_lines.append("Виловлена риба:")
    for fish in ["Карась", "Окунь", "Щука", "Сом"]:
        inv_lines.append(f"  • {fish}: {state.inventory.get(fish, 0)} шт. (Ціна продажу: {state.fish_prices[fish]} грн)")
    inv_lines.append("-----------------------------")
    inv_lines.append(f"Наживка: Черв'яки: {state.inventory.get('Черв\'яки', 0)} | Блешня: {state.inventory.get('Блешня', 0)}")

    Text("\n".join(inv_lines), parent=active_menu, position=(-0.42, 0.28), scale=1.05, color=color.white)
    Button(text="Закрити (ESC / I)", parent=active_menu, y=-0.38, scale=(0.6, 0.1), color=color.azure, on_click=close_ui)

def open_shop_ui():
    global active_menu
    player.active_ui = "SHOP"
    player.unlock_mouse()

    active_menu = Entity(parent=camera.ui, model='quad', scale=(0.75, 0.8), color=color.rgba(25, 25, 35, 245))
    Text("МАГАЗИН РИБАЛКИ", parent=active_menu, y=0.42, origin=(0, 0), scale=1.6, color=color.gold)

    def do_sell():
        qty, money = state.sell_all_fish()
        player.update_hud()
        if qty > 0:
            player.show_notification(f"Продано {qty} риб на суму {money} грн!", col=color.lime)
        else:
            player.show_notification("У вас немає риби для продажу!", col=color.yellow)
        close_ui()

    Button(text="ПРОДАТИ ВСЮ РИБУ", parent=active_menu, y=0.28, scale=(0.7, 0.09), color=color.green, on_click=do_sell)

    def buy_worms():
        ok, msg = state.buy_bait("Черв'яки (x5)")
        player.update_hud()
        player.show_notification(msg, col=color.lime if ok else color.red)

    def buy_lure():
        ok, msg = state.buy_bait("Блешня (x2)")
        player.update_hud()
        player.show_notification(msg, col=color.lime if ok else color.red)

    Button(text="Купити: Черв'яки (x5) - 20 грн", parent=active_menu, y=0.15, scale=(0.7, 0.08), color=color.azure, on_click=buy_worms)
    Button(text="Купити: Блешня (x2) - 50 грн", parent=active_menu, y=0.05, scale=(0.7, 0.08), color=color.azure, on_click=buy_lure)

    def buy_rod_action(name):
        ok, msg = state.buy_rod(name)
        player.update_hud()
        player.show_notification(msg, col=color.lime if ok else color.red)

    Button(text="Бамбукова вудка (Рівень 1) - 100 грн", parent=active_menu, y=-0.07, scale=(0.7, 0.08), color=color.teal, on_click=lambda: buy_rod_action("Бамбукова вудка"))
    Button(text="Професійний спінінг (Рівень 2) - 250 грн", parent=active_menu, y=-0.17, scale=(0.7, 0.08), color=color.teal, on_click=lambda: buy_rod_action("Професійний спінінг"))
    Button(text="Титан Pro (Рівень 3) - 500 грн", parent=active_menu, y=-0.27, scale=(0.7, 0.08), color=color.teal, on_click=lambda: buy_rod_action("Титан Pro"))

    Button(text="Вийти з магазину (ESC)", parent=active_menu, y=-0.38, scale=(0.5, 0.08), color=color.dark_gray, on_click=close_ui)

def open_quests_ui():
    global active_menu
    player.active_ui = "QUESTS"
    player.unlock_mouse()

    active_menu = Entity(parent=camera.ui, model='quad', scale=(0.7, 0.75), color=color.rgba(20, 25, 40, 245))
    Text("ЖУРНАЛ ЗАВДАНЬ", parent=active_menu, y=0.4, origin=(0, 0), scale=1.5, color=color.azure)

    y_pos = 0.25
    for q in state.quests:
        status_text = "ГОТОВО (Забрати нагороду)" if (q["completed"] and not q["claimed"]) else ("ВИКОНАНО" if q["claimed"] else f"Прогрес: {q['current']}/{q['count']}")
        Text(f"• {q['title']}: {q['desc']}\n  Статус: {status_text} | Нагорода: {q['reward_money']} грн, {q['reward_xp']} XP",
             parent=active_menu, position=(-0.4, y_pos), scale=0.95, color=color.yellow if q["completed"] else color.white)
        
        if q["completed"] and not q["claimed"]:
            qid = q["id"]
            Button(text="Забрати", parent=active_menu, position=(0.35, y_pos - 0.02), scale=(0.2, 0.06), color=color.green, on_click=lambda q_id=qid: claim_reward(q_id))
        y_pos -= 0.16

    Button(text="Закрити (ESC / Q)", parent=active_menu, y=-0.4, scale=(0.6, 0.09), color=color.dark_gray, on_click=close_ui)

def claim_reward(quest_id):
    ok, msg = state.claim_quest(quest_id)
    player.update_hud()
    player.show_notification(msg, col=color.lime if ok else color.red)
    close_ui()
    open_quests_ui()

def open_dialogue(npc_name, text):
    global active_menu
    player.active_ui = "DIALOGUE"
    player.unlock_mouse()

    active_menu = Entity(parent=camera.ui, model='quad', scale=(0.7, 0.4), color=color.rgba(15, 20, 30, 240))
    Text(f"NPC: {npc_name}", parent=active_menu, y=0.3, origin=(0, 0), scale=1.4, color=color.azure)
    Text(text, parent=active_menu, y=0.08, origin=(0, 0), scale=1.1, color=color.white)

    Button(text="До завдань (Q)", parent=active_menu, position=(-0.18, -0.25), scale=(0.3, 0.1), color=color.green, on_click=lambda: [close_ui(), open_quests_ui()])
    Button(text="До побачення (ESC)", parent=active_menu, position=(0.18, -0.25), scale=(0.3, 0.1), color=color.dark_gray, on_click=close_ui)


# --- СТВОРЕННЯ ГРАВЦЯ (ПІСЛЯ побудови світу) ---
player = FPSPlayer()

# Визначення точки початкового спавну:
# Якщо є коректне збереження позиції — використовуємо його, інакше ставимо всередині будинку
init_target = DEFAULT_SPAWN_INSIDE_HOUSE
if state.player_pos is not None:
    init_target = Vec3(state.player_pos[0], state.player_pos[1], state.player_pos[2])

player.safe_spawn_at(init_target)

if __name__ == '__main__':
    print("[SYSTEM] Fishing Game FPS повністю завантажено! Спавн перевірено.")
    app.run()
