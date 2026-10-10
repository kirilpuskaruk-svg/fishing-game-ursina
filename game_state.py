import json
import os
import random

SAVE_FILE = "save_data.json"

class GameState:
    def __init__(self):
        self.money = 50
        self.xp = 0
        self.level = 1
        self.inventory = {
            "Карась": 0,
            "Окунь": 0,
            "Щука": 0,
            "Сом": 0,
            "Хробаки": 10,
            "Кукурудза": 0,
            "Спеціальна наживка": 0
        }
        self.current_rod = "Початкова вудка"
        self.owned_rods = ["Початкова вудка"]
        self.player_pos = None  # [x, y, z] безпечні координати

        # Завдання (Quests)
        self.quests = [
            {"id": "q1", "title": "Перший улов", "desc": "Зловити 2 Карасі", "target": "Карась", "count": 2, "current": 0, "reward_money": 40, "reward_xp": 50, "completed": False, "claimed": False},
            {"id": "q2", "title": "Хижак озера", "desc": "Зловити 1 Щуку", "target": "Щука", "count": 1, "current": 0, "reward_money": 100, "reward_xp": 120, "completed": False, "claimed": False},
            {"id": "q3", "title": "Майстер риболовлі", "desc": "Зловити будь-які 5 риб", "target": "ANY", "count": 5, "current": 0, "reward_money": 150, "reward_xp": 200, "completed": False, "claimed": False}
        ]

        self.fish_prices = {
            "Карась": 15,
            "Окунь": 25,
            "Щука": 60,
            "Сом": 120
        }

        self.shop_rods = {
            "Початкова вудка": {
                "price": 60,
                "luck_mult": 1.15,
                "level_req": 1,
                "desc": "Легка дерев'яна вудка для новачків. Трохи підвищує шанс клювання (+15%)."
            },
            "Покращена вудка": {
                "price": 140,
                "luck_mult": 1.45,
                "level_req": 1,
                "desc": "Надійне вудилище з міцною жилкою. Чудово підходить для окуня (+45% удачі)."
            },
            "Професійна вудка": {
                "price": 320,
                "luck_mult": 1.95,
                "level_req": 2,
                "desc": "Карбоновий бланк з чутливим кінчиком. Дозволяє витягувати щуку (+95% удачі)."
            },
            "Рідкісна вудка для великої риби": {
                "price": 650,
                "luck_mult": 2.80,
                "level_req": 3,
                "desc": "Елітна титанова снасть для озерних гігантів та трофейних сомів (+180% удачі)."
            }
        }

        self.shop_baits = {
            "Хробаки (x5)": {
                "price": 20,
                "item": "Хробаки",
                "qty": 5,
                "desc": "Універсальна природна наживка для карася та окуня."
            },
            "Кукурудза (x5)": {
                "price": 35,
                "item": "Кукурудза",
                "qty": 5,
                "desc": "Солодка ароматна наживка, приваблює велику мирну рибу."
            },
            "Спеціальна наживка для хижої риби (x3)": {
                "price": 75,
                "item": "Спеціальна наживка",
                "qty": 3,
                "desc": "Спеціальна силіконова рибка з атрактантом для щуки та сома."
            }
        }

    def add_xp(self, amount):
        self.xp += amount
        needed_xp = self.level * 100
        while self.xp >= needed_xp:
            self.xp -= needed_xp
            self.level += 1
            needed_xp = self.level * 100
            print(f"[GAME] Вітаємо! Новий рівень: {self.level}!")

    def on_fish_caught(self, fish_name):
        self.inventory[fish_name] = self.inventory.get(fish_name, 0) + 1
        xp_gain = 25
        if fish_name == "Окунь": xp_gain = 40
        elif fish_name == "Щука": xp_gain = 80
        elif fish_name == "Сом": xp_gain = 150
        self.add_xp(xp_gain)

        for q in self.quests:
            if not q["completed"]:
                if q["target"] == "ANY" or q["target"] == fish_name:
                    q["current"] += 1
                    if q["current"] >= q["count"]:
                        q["completed"] = True
                        print(f"[QUEST] Завдання виконано: {q['title']}!")

    def claim_quest(self, quest_id):
        for q in self.quests:
            if q["id"] == quest_id and q["completed"] and not q["claimed"]:
                q["claimed"] = True
                self.money += q["reward_money"]
                self.add_xp(q["reward_xp"])
                return True, f"Отримано: +{q['reward_money']} монет, +{q['reward_xp']} XP!"
        return False, "Не вдалося отримати нагороду."

    def sell_all_fish(self):
        total_income = 0
        fish_sold = 0
        for fish, price in self.fish_prices.items():
            qty = self.inventory.get(fish, 0)
            if qty > 0:
                income = qty * price
                total_income += income
                fish_sold += qty
                self.inventory[fish] = 0
        self.money += total_income
        return fish_sold, total_income

    def buy_rod(self, rod_name):
        rod_info = self.shop_rods.get(rod_name)
        if not rod_info:
            return False, "Вудку не знайдено."
        if rod_name in self.owned_rods:
            self.current_rod = rod_name
            self.save_to_file()
            return True, f"Ви вже володієте цією вудкою. Вона екіпірована: {rod_name}!"
        if self.level < rod_info["level_req"]:
            return False, f"Потрібен {rod_info['level_req']} рівень гравця!"
        if self.money < rod_info["price"]:
            return False, f"Недостатньо грошей! Ціна: {rod_info['price']} грн (у вас {self.money} грн)."
        
        self.money -= rod_info["price"]
        self.owned_rods.append(rod_name)
        self.current_rod = rod_name
        self.save_to_file()
        return True, f"Успішно придбано та екіпіровано: {rod_name}!"

    def buy_bait(self, bait_key):
        bait_info = self.shop_baits.get(bait_key)
        if not bait_info:
            return False, "Товар не знайдено."
        if self.money < bait_info["price"]:
            return False, f"Недостатньо грошей! Ціна: {bait_info['price']} грн (у вас {self.money} грн)."
        self.money -= bait_info["price"]
        item = bait_info["item"]
        self.inventory[item] = self.inventory.get(item, 0) + bait_info["qty"]
        self.save_to_file()
        return True, f"Куплено {item} (+{bait_info['qty']} шт.)!"

    def save_to_file(self, player_pos=None, filepath=SAVE_FILE):
        if player_pos is not None:
            self.player_pos = [float(player_pos[0]), float(player_pos[1]), float(player_pos[2])]
        data = {
            "money": self.money,
            "xp": self.xp,
            "level": self.level,
            "inventory": self.inventory,
            "current_rod": self.current_rod,
            "owned_rods": self.owned_rods,
            "quests": self.quests,
            "player_pos": self.player_pos
        }
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True, "Гру збережено!"
        except Exception as e:
            return False, f"Помилка збереження: {e}"

    def load_from_file(self, filepath=SAVE_FILE):
        if not os.path.exists(filepath):
            return False, "Збережень не знайдено."
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.money = data.get("money", self.money)
            self.xp = data.get("xp", self.xp)
            self.level = data.get("level", self.level)
            loaded_inv = data.get("inventory", {})
            for k, v in loaded_inv.items():
                if k == "Черв'яки":
                    self.inventory["Хробаки"] = self.inventory.get("Хробаки", 0) + v
                elif k == "Блешня":
                    self.inventory["Спеціальна наживка"] = self.inventory.get("Спеціальна наживка", 0) + v
                else:
                    self.inventory[k] = v

            self.current_rod = data.get("current_rod", self.current_rod)
            if self.current_rod == "Стара вудка":
                self.current_rod = "Початкова вудка"

            self.owned_rods = data.get("owned_rods", self.owned_rods)
            if "Стара вудка" in self.owned_rods:
                self.owned_rods = [r if r != "Стара вудка" else "Початкова вудка" for r in self.owned_rods]
            if "Початкова вудка" not in self.owned_rods:
                self.owned_rods.insert(0, "Початкова вудка")

            self.quests = data.get("quests", self.quests)
            raw_pos = data.get("player_pos")
            # Валідація координат: якщо y занадто низький, не використовуємо зіпсоване збереження
            if raw_pos and isinstance(raw_pos, list) and len(raw_pos) == 3:
                if raw_pos[1] > -1.0:
                    self.player_pos = raw_pos
                else:
                    self.player_pos = None
            else:
                self.player_pos = None
            return True, "Гру завантажено!"
        except Exception as e:
            return False, f"Помилка завантаження: {e}"
