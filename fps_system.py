"""
FPS Controller, Camera, Interaction & Fishing System for Ursina Engine.
Розділ 4: FPS-режим, камера, фізика та взаємодія.
"""

from ursina import *
import math
import random


class Interactable(Entity):
    """
    Інтерактивний об'єкт з підказкою та дією.
    """
    def __init__(self, prompt_text="Взаємодія", on_interact=None, **kwargs):
        super().__init__(**kwargs)
        self.prompt_text = prompt_text
        self.on_interact = on_interact
        if not self.collider:
            self.collider = 'box'

    def interact(self, player):
        if self.on_interact:
            self.on_interact(player)


class CustomFPSController(Entity):
    """
    Повноцінний контролер від першої особи (FPS):
    - Огляд мишкою 360° по горизонталі, -85°..+85° по вертикалі
    - Блокування/розблокування курсора (ESC)
    - W, A, S, D, Shift (біг), Space (стрибок), Ctrl (присідання)
    - Плавне прискорення, інерція та Camera Bobbing
    - Колізії зі стінами, землею, деревами та об'єктами
    - Центральний приціл та динамічна підказка 'E — Взаємодія'
    - Режим риболовлі з поплавком, волосінню, тремтінням та виловом риби
    """
    def __init__(self, **kwargs):
        super().__init__()

        # Швидкості пересування
        self.walk_speed = 5.0
        self.run_speed = 8.5
        self.crouch_speed = 2.5
        self.velocity = Vec3(0, 0, 0)
        self.acceleration = 12.0
        self.friction = 10.0

        # Фізика стрибка та гравітація
        self.jump_height = 1.2
        self.gravity = 24.0
        self.vertical_velocity = 0.0
        self.grounded = False

        # Висота очей / присідання
        self.standing_height = 1.8
        self.crouch_height = 1.0
        self.current_eye_height = self.standing_height
        self.is_crouching = False

        # Камера і миша
        self.mouse_sensitivity = Vec2(40, 40)
        self.camera_pitch = 0.0
        self.camera_yaw = 0.0
        self.pitch_range = (-85, 85)

        # Camera Bobbing (хитання камери)
        self.bob_timer = 0.0
        self.bob_freq_walk = 8.0
        self.bob_freq_run = 12.0
        self.bob_amp_walk = 0.035
        self.bob_amp_run = 0.075

        # Позиція та колізія сутності гравця
        self.position = Vec3(0, 2, 0)
        self.collider = BoxCollider(self, center=Vec3(0, 0.9, 0), size=Vec3(0.6, 1.8, 0.6))

        # Налаштування камери Ursina
        camera.parent = self
        camera.position = Vec3(0, self.current_eye_height, 0)
        camera.rotation = Vec3(0, 0, 0)
        camera.fov = 85

        # UI: Центральний приціл (хрестик/крапка)
        self.crosshair = Entity(
            parent=camera.ui,
            model='quad',
            texture='circle',
            scale=0.008,
            color=color.rgba(255, 255, 255, 220)
        )

        # UI: Підказка взаємодії
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

        # UI: Панель Меню (ESC)
        self.menu_panel = Entity(
            parent=camera.ui,
            model='quad',
            scale=(0.5, 0.4),
            color=color.rgba(15, 15, 20, 220),
            enabled=False
        )
        self.menu_title = Text(
            text="МЕНЮ ГРИ\n\n[ESC] Повернутися до гри",
            parent=self.menu_panel,
            origin=(0, 0),
            position=(0, 0),
            scale=1.5,
            color=color.white
        )

        # Стан взаємодії
        self.interaction_distance = 3.5
        self.current_target = None

        # Режим риболовлі
        self.is_fishing = False
        self.fishing_camera_locked = False
        self.bobber = None
        self.fishing_line = None
        self.bite_sequence = None

        # Стан меню / курсора
        self.in_menu = False
        mouse.locked = True
        mouse.visible = False

        for key, value in kwargs.items():
            setattr(self, key, value)

    def update(self):
        if self.in_menu:
            return

        dt = time.dt

        # Огляд мишкою
        if not self.fishing_camera_locked:
            self.handle_camera_look(dt)

        # Пересування, колізії або стан риболовлі
        if not self.is_fishing:
            self.handle_movement(dt)
            self.handle_bobbing(dt)
            self.check_interaction()
        else:
            self.update_fishing(dt)

    def handle_camera_look(self, dt):
        self.camera_yaw += mouse.velocity[0] * self.mouse_sensitivity.x
        self.camera_pitch -= mouse.velocity[1] * self.mouse_sensitivity.y
        self.camera_pitch = clamp(self.camera_pitch, self.pitch_range[0], self.pitch_range[1])

        # Горизонтальний поворот персонажа, вертикальний — лише камери
        self.rotation_y = self.camera_yaw
        camera.rotation_x = self.camera_pitch

    def handle_movement(self, dt):
        # 1. Присідання (Ctrl)
        self.is_crouching = held_keys['left control'] or held_keys['control']
        target_height = self.crouch_height if self.is_crouching else self.standing_height
        self.current_eye_height = lerp(self.current_eye_height, target_height, dt * 10)
        camera.y = self.current_eye_height

        # 2. Вибір цільової швидкості (W, A, S, D, Shift)
        if self.is_crouching:
            target_speed = self.crouch_speed
        elif held_keys['shift'] or held_keys['left shift']:
            target_speed = self.run_speed
        else:
            target_speed = self.walk_speed

        # Вектор введення
        move_dir = Vec3(
            (held_keys['d'] - held_keys['a']),
            0,
            (held_keys['w'] - held_keys['s'])
        ).normalized()

        is_moving = move_dir.length() > 0

        # Плавне прискорення та гальмування
        target_vel = (self.forward * move_dir.z + self.right * move_dir.x) * (target_speed if is_moving else 0)
        self.velocity = lerp(self.velocity, target_vel, dt * (self.acceleration if is_moving else self.friction))

        # Горизонтальні колізії (стіни, дерева, NPC, каміння)
        horizontal_move = self.velocity * dt
        if horizontal_move.length() > 0.0001:
            ray_origin = self.position + Vec3(0, 0.6, 0)
            hit = raycast(ray_origin, horizontal_move.normalized(), distance=0.6, ignore=(self,))
            if not hit.hit:
                self.position += horizontal_move
            else:
                # Ковзання вздовж перешкоди
                slide_dir = horizontal_move - hit.normal * horizontal_move.dot(hit.normal)
                self.position += slide_dir

        # Вертикальний рух, гравітація та стрибок (Space)
        ground_ray = raycast(self.position + Vec3(0, 0.2, 0), Vec3(0, -1, 0), distance=0.4, ignore=(self,))
        self.grounded = ground_ray.hit

        if self.grounded:
            self.vertical_velocity = 0
            if ground_ray.world_point:
                self.y = ground_ray.world_point.y
            if held_keys['space'] and not self.is_crouching:
                self.vertical_velocity = math.sqrt(2 * self.gravity * self.jump_height)
        else:
            self.vertical_velocity -= self.gravity * dt

        self.y += self.vertical_velocity * dt

    def handle_bobbing(self, dt):
        horiz_speed = Vec2(self.velocity.x, self.velocity.z).length()
        if horiz_speed > 0.4 and self.grounded:
            is_running = (held_keys['shift'] or held_keys['left shift']) and not self.is_crouching
            freq = self.bob_freq_run if is_running else self.bob_freq_walk
            amp = self.bob_amp_run if is_running else self.bob_amp_walk

            self.bob_timer += dt * freq
            camera.y = self.current_eye_height + math.sin(self.bob_timer) * amp
            camera.x = math.cos(self.bob_timer * 0.5) * (amp * 0.5)
        else:
            self.bob_timer = 0.0
            camera.y = lerp(camera.y, self.current_eye_height, dt * 10)
            camera.x = lerp(camera.x, 0, dt * 10)

    def check_interaction(self):
        # Raycast із центру камери вперед
        hit = raycast(camera.world_position, camera.forward, distance=self.interaction_distance, ignore=(self,))
        if hit.hit and hasattr(hit.entity, 'prompt_text'):
            self.current_target = hit.entity
            self.prompt_text.text = f"Натисніть E — {hit.entity.prompt_text}"
            self.prompt_text.enabled = True
        else:
            self.current_target = None
            self.prompt_text.enabled = False

    def input(self, key):
        # ESC: Меню та курсор
        if key == 'escape':
            self.toggle_menu()

        # I: Інвентар
        if key == 'i' and not self.is_fishing:
            self.toggle_menu(title="ІНВЕНТАР\n\n[ESC] або [I] Закрити")

        # E: Взаємодія
        if key == 'e' and not self.in_menu:
            if self.is_fishing:
                self.catch_fish()
            elif self.current_target and hasattr(self.current_target, 'interact'):
                self.current_target.interact(self)

    def toggle_menu(self, title=None):
        self.in_menu = not self.in_menu
        if self.in_menu:
            mouse.locked = False
            mouse.visible = True
            if title:
                self.menu_title.text = title
            else:
                self.menu_title.text = "МЕНЮ ГРИ\n\n[ESC] Повернутися до гри"
            self.menu_panel.enabled = True
            self.prompt_text.enabled = False
        else:
            mouse.locked = True
            mouse.visible = False
            self.menu_panel.enabled = False

    # --- КАМЕРА ТА ЛОГІКА РИБОЛОВЛІ ---
    def start_fishing(self, water_target_pos):
        self.is_fishing = True
        self.fishing_camera_locked = True
        self.prompt_text.text = "Очікування клювання..."
        self.prompt_text.enabled = True

        # Спрямовуємо погляд камери на воду/поплавок
        camera.animate('rotation_x', 25, duration=0.8)

        # Створюємо поплавок на воді
        self.bobber = Entity(
            model='sphere',
            color=color.orange,
            scale=0.15,
            position=water_target_pos
        )

        self.update_fishing_line()

        # Випадковий час до клювання (2.5 - 4.5 сек)
        self.bite_delay = random.uniform(2.5, 4.5)
        self.has_bite = False
        invoke(self.on_bite, delay=self.bite_delay)

    def update_fishing_line(self):
        if not self.bobber:
            return
        hand_pos = camera.world_position + camera.forward * 0.6 + camera.down * 0.3 + camera.right * 0.35
        if self.fishing_line:
            destroy(self.fishing_line)
        self.fishing_line = Entity(
            model=Pipe(path=[hand_pos, self.bobber.position], thicknesses=[0.008, 0.008]),
            color=color.rgba(255, 255, 255, 120)
        )

    def on_bite(self):
        if not self.is_fishing:
            return
        self.has_bite = True
        # Тремтіння камери та вібрація поплавка
        camera.shake(duration=0.6, magnitude=0.02)
        if self.bobber:
            self.bobber.animate_y(self.bobber.y - 0.15, duration=0.25, loop=True)
        self.prompt_text.text = "КЛЮЄ! Натисніть E — Витягнути!"

    def update_fishing(self, dt):
        if self.bobber:
            self.update_fishing_line()

    def catch_fish(self):
        if not self.is_fishing:
            return

        # Анімація виловленої риби перед камерою
        fish = Entity(
            parent=camera,
            model='cube',
            scale=(0.35, 0.18, 0.6),
            color=color.cyan,
            position=(0, -0.3, 0.9),
            rotation=(10, 45, 15)
        )
        fish.animate_position((0, 0, 0.65), duration=0.4)
        destroy(fish, delay=1.8)

        self.prompt_text.text = "Ви зловили рибу!"
        invoke(self.reset_fishing, delay=1.5)

    def reset_fishing(self):
        if self.bobber:
            destroy(self.bobber)
            self.bobber = None
        if self.fishing_line:
            destroy(self.fishing_line)
            self.fishing_line = None

        self.is_fishing = False
        self.fishing_camera_locked = False
        self.prompt_text.enabled = False
        camera.animate('rotation_x', self.camera_pitch, duration=0.5)


if __name__ == '__main__':
    app = Ursina()

    # 1. Оточення: небо, земля, сонце
    Sky()
    ground = Entity(model='plane', scale=60, texture='grass', collider='box')
    sun = DirectionalLight(y=10, rotation=(45, -45, 0))

    # Стіни будинку
    wall = Entity(model='cube', scale=(8, 3, 0.5), position=(0, 1.5, 6), color=color.dark_gray, collider='box')

    # Дерево (стовбур + крона)
    tree_trunk = Entity(model='cylinder', scale=(0.5, 3, 0.5), position=(-5, 1.5, 3), color=color.brown, collider='box')
    tree_top = Entity(model='sphere', scale=2.5, position=(-5, 4, 3), color=color.green, collider='box')

    # Камінь
    rock = Entity(model='cube', scale=(1.5, 1, 1.5), position=(4, 0.5, 2), color=color.gray, collider='box')

    # Водойма для риболовлі
    water = Entity(model='plane', scale=16, position=(0, 0.02, 14), color=color.rgba(0, 150, 255, 180), collider='box')

    # 2. Інтерактивні сутності
    # Двері
    door = Interactable(
        prompt_text="Відкрити",
        model='cube',
        scale=(1.2, 2.4, 0.15),
        position=(0, 1.2, 5.7),
        color=color.orange,
        on_interact=lambda p: print("Двері відчинено!")
    )

    # NPC
    npc = Interactable(
        prompt_text="Поговорити",
        model='cube',
        scale=(0.6, 1.8, 0.6),
        position=(-2, 0.9, 4),
        color=color.azure,
        on_interact=lambda p: print("NPC: Привіт, рибалко!")
    )

    # Магазин
    shop = Interactable(
        prompt_text="Магазин",
        model='cube',
        scale=(1.5, 1.5, 1.5),
        position=(5, 0.75, -2),
        color=color.gold,
        on_interact=lambda p: print("Магазин спорядження відкрито!")
    )

    # Місце риболовлі
    fishing_spot = Interactable(
        prompt_text="Рибалити",
        model='cylinder',
        scale=(1.2, 0.1, 1.2),
        position=(0, 0.05, 8.5),
        color=color.lime,
        on_interact=lambda p: p.start_fishing(water_target_pos=Vec3(0, 0.1, 13))
    )

    # 3. Гравець FPS
    player = CustomFPSController(position=Vec3(0, 2, 0))

    print("FPS система успішно запущена.")
    app.run()
