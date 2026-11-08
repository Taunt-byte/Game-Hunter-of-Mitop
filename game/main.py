import math
from collections import deque

import pyxel

# =========================
# Configuracoes gerais
# =========================
W, H = 160, 120
FPS = 60

PLAYER_SPEED = 2
BULLET_SPEED = 4
SHOOT_COOLDOWN = 7
MAX_POWER = 4

# ---- Voltar no tempo ----
MAX_CHARGES = 3                  # maximo de cargas de rewind
REWIND_SECONDS = 3               # quanto tempo da pra voltar
HISTORY_MAX = FPS * REWIND_SECONDS
REWIND_SPEED = 3                 # frames desfeitos por frame (rewind 3x mais rapido)
CHRONO_INTERVAL = FPS * 12       # um inimigo Cronos a cada ~12 segundos

ENEMY_DATA = {
    "basic":   {"hp": 1, "score": 100},
    "zigzag":  {"hp": 2, "score": 150},
    "shooter": {"hp": 3, "score": 250},
    "chrono":  {"hp": 6, "score": 500},   # o inimigo especial que da carga
}


def aabb(ax, ay, aw, ah, bx, by, bw, bh):
    return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by


class App:
    def __init__(self):
        pyxel.init(W, H, title="Hunter of mitop", fps=FPS)
        try:
            pyxel.load("assets/recurso-mitop.pyxres")
        except Exception:
            pass  # roda mesmo sem o arquivo de recursos
        self.reset()
        pyxel.run(self.update, self.draw)

    # Reinicia o jogo SEM chamar pyxel.init/run de novo
    def reset(self):
        self.px = W // 2 - 8
        self.py = H - 20
        self.lives = 3
        self.power = 1
        self.invincible_timer = 0
        self.shoot_cooldown = 0
        self.score = 0
        self.game_time = 0

        self.bullets = []        # [x, y, vx, vy]
        self.enemy_bullets = []  # [x, y, vx, vy]
        self.enemies = []        # dicts
        self.powerups = []       # [x, y, t]
        self.particles = []      # [x, y, vx, vy, vida, cor]

        self.spawn_timer = 0
        self.chrono_timer = 0
        self.chrono_count = 0
        self.next_id = 0

        # ---- Voltar no tempo ----
        self.charges = 1                          # comeca com 1 pra testar
        self.history = deque(maxlen=HISTORY_MAX)  # "fita" com os ultimos 3s
        self.rewinding = False
        self.killed_chronos = set()               # Cronos ja destruidos (anti-exploit)

        self.msg = ""
        self.msg_timer = 0
        self.game_over = False

        self.stars = [[pyxel.rndi(0, W - 1), pyxel.rndi(0, H - 1), pyxel.rndi(1, 3)]
                      for _ in range(40)]

    # =========================
    # UPDATE
    # =========================
    def update(self):
        if pyxel.btnp(pyxel.KEY_Q):
            pyxel.quit()

        self.update_particles()
        if self.msg_timer > 0:
            self.msg_timer -= 1

        if self.rewinding:
            self.update_rewind()
            return

        rewind_pressed = pyxel.btnp(pyxel.KEY_X) or pyxel.btnp(pyxel.GAMEPAD1_BUTTON_B)

        if self.game_over:
            self.update_background()
            # Ultima chance: da pra voltar no tempo ate depois de morrer
            if rewind_pressed and self.can_rewind():
                self.start_rewind()
            elif pyxel.btnp(pyxel.KEY_R):
                self.reset()
            return

        if rewind_pressed and self.can_rewind():
            self.start_rewind()
            return

        # Grava o estado ANTES de atualizar o frame
        self.save_snapshot()
        self.game_time += 1

        self.update_background()
        self.update_player()
        self.update_bullets()
        self.update_enemies()
        self.update_powerups()
        self.check_collisions()

    # -------------------------
    # Sistema de voltar no tempo
    # -------------------------
    def save_snapshot(self):
        # Tudo que "volta" com o tempo fica aqui.
        # Cargas e Cronos destruidos NAO entram, de proposito.
        self.history.append({
            "px": self.px, "py": self.py,
            "lives": self.lives, "power": self.power, "score": self.score,
            "invincible_timer": self.invincible_timer,
            "game_time": self.game_time,
            "spawn_timer": self.spawn_timer,
            "chrono_timer": self.chrono_timer,
            "chrono_count": self.chrono_count,
            "bullets": [b[:] for b in self.bullets],
            "enemy_bullets": [b[:] for b in self.enemy_bullets],
            "enemies": [dict(e) for e in self.enemies],
            "powerups": [p[:] for p in self.powerups],
        })

    def load_snapshot(self, snap):
        for key, value in snap.items():
            setattr(self, key, value)
        # Cronos que voce ja matou nao voltam (senao daria pra farmar cargas)
        self.enemies = [e for e in self.enemies if e["id"] not in self.killed_chronos]

    def can_rewind(self):
        return self.charges > 0 and len(self.history) > FPS // 2

    def start_rewind(self):
        self.charges -= 1
        self.rewinding = True
        self.particles.clear()

    def update_rewind(self):
        for _ in range(REWIND_SPEED):
            if not self.history:
                break
            self.load_snapshot(self.history.pop())

        # Estrelas andam pra tras durante o rewind
        for s in self.stars:
            s[1] -= s[2] * 2
            if s[1] < 0:
                s[1] = H - 1
                s[0] = pyxel.rndi(0, W - 1)

        # Fim da fita: volta ao jogo normal
        if not self.history:
            self.rewinding = False
            self.game_over = False
            self.invincible_timer = 60
            self.shoot_cooldown = 0

    # -------------------------
    # Fundo
    # -------------------------
    def update_background(self):
        for s in self.stars:
            s[1] += s[2]
            if s[1] >= H:
                s[0] = pyxel.rndi(0, W - 1)
                s[1] = 0
                s[2] = pyxel.rndi(1, 3)

    # -------------------------
    # Jogador
    # -------------------------
    def update_player(self):
        if pyxel.btn(pyxel.KEY_LEFT) or pyxel.btn(pyxel.GAMEPAD1_BUTTON_DPAD_LEFT):
            self.px = max(self.px - PLAYER_SPEED, 0)
        if pyxel.btn(pyxel.KEY_RIGHT) or pyxel.btn(pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT):
            self.px = min(self.px + PLAYER_SPEED, W - 16)
        if pyxel.btn(pyxel.KEY_UP) or pyxel.btn(pyxel.GAMEPAD1_BUTTON_DPAD_UP):
            self.py = max(self.py - PLAYER_SPEED, 0)
        if pyxel.btn(pyxel.KEY_DOWN) or pyxel.btn(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN):
            self.py = min(self.py + PLAYER_SPEED, H - 16)

        if self.shoot_cooldown > 0:
            self.shoot_cooldown -= 1
        if self.invincible_timer > 0:
            self.invincible_timer -= 1

        shooting = (pyxel.btn(pyxel.KEY_SPACE) or pyxel.btn(pyxel.KEY_Z)
                    or pyxel.btn(pyxel.GAMEPAD1_BUTTON_A))
        if shooting and self.shoot_cooldown == 0:
            self.fire()
            self.shoot_cooldown = SHOOT_COOLDOWN

    def fire(self):
        cx = self.px + 7
        y = self.py - 2
        # Padrao de tiro cresce com o power (estilo Aero Fighters)
        if self.power == 1:
            shots = [(cx, 0)]
        elif self.power == 2:
            shots = [(cx - 3, 0), (cx + 3, 0)]
        elif self.power == 3:
            shots = [(cx - 3, 0), (cx + 3, 0), (cx - 5, -1), (cx + 5, 1)]
        else:
            shots = [(cx, 0), (cx - 4, 0), (cx + 4, 0), (cx - 6, -1.2), (cx + 6, 1.2)]
        for x, vx in shots:
            self.bullets.append([x, y, vx, -BULLET_SPEED])
        # pyxel.play(3, 0)  # som de tiro

    # -------------------------
    # Tiros
    # -------------------------
    def update_bullets(self):
        for b in self.bullets:
            b[0] += b[2]
            b[1] += b[3]
        self.bullets = [b for b in self.bullets if b[1] > -8 and -4 < b[0] < W + 4]

        for b in self.enemy_bullets:
            b[0] += b[2]
            b[1] += b[3]
        self.enemy_bullets = [b for b in self.enemy_bullets
                              if -4 < b[0] < W + 4 and -4 < b[1] < H + 4]

    # -------------------------
    # Inimigos
    # -------------------------
    def difficulty(self):
        return min(self.game_time // (FPS * 20), 5)  # sobe a cada 20s

    def spawn_enemy(self, kind, eid=None):
        if eid is None:
            eid = self.next_id
            self.next_id += 1
        x = pyxel.rndi(20, W - 36) if kind == "zigzag" else pyxel.rndi(8, W - 24)
        if kind == "chrono":
            x = W // 2 - 8
        self.enemies.append({"id": eid, "type": kind, "x": x, "y": -16, "bx": x,
                             "hp": ENEMY_DATA[kind]["hp"], "t": 0})

    def update_enemies(self):
        d = self.difficulty()

        self.spawn_timer += 1
        if self.spawn_timer >= max(14, 34 - d * 4):
            self.spawn_timer = 0
            r = pyxel.rndi(0, 99)
            if d >= 2 and r < 20 + d * 3:
                kind = "shooter"
            elif d >= 1 and r < 55:
                kind = "zigzag"
            else:
                kind = "basic"
            self.spawn_enemy(kind)

        # Inimigo especial Cronos
        self.chrono_timer += 1
        if self.chrono_timer >= CHRONO_INTERVAL:
            self.chrono_timer = 0
            cid = f"cronos-{self.chrono_count}"
            self.chrono_count += 1
            if cid not in self.killed_chronos:
                self.spawn_enemy("chrono", cid)
                self.show_msg("CRONOS APARECEU!")

        for e in self.enemies:
            e["t"] += 1
            t = e["t"]
            k = e["type"]
            if k == "basic":
                e["y"] += 1 + d * 0.2
            elif k == "zigzag":
                e["y"] += 0.9
                e["x"] = e["bx"] + pyxel.sin(t * 4) * 20
            elif k == "shooter":
                if t < 50:
                    e["y"] += 0.8          # entra na tela
                elif t > 300:
                    e["y"] += 1.2          # vai embora
                elif t % 50 == 0:
                    self.enemy_shoot(e)    # para e atira mirando em voce
            elif k == "chrono":
                if e["y"] < 22:
                    e["y"] += 0.5
                elif t > 600:
                    e["y"] += 0.8          # foge se voce demorar
                e["x"] = e["bx"] + pyxel.sin(t * 2) * 50
                if e["y"] >= 22 and t % 70 == 0:
                    for ang in (-25, 0, 25):
                        self.enemy_bullets.append([e["x"] + 8, e["y"] + 12,
                                                   pyxel.sin(ang) * 1.2,
                                                   pyxel.cos(ang) * 1.2])

        self.enemies = [e for e in self.enemies if e["y"] < H + 20]

    def enemy_shoot(self, e):
        cx, cy = e["x"] + 8, e["y"] + 8
        dx = (self.px + 8) - cx
        dy = (self.py + 8) - cy
        dist = math.hypot(dx, dy) or 1
        spd = 1.3 + self.difficulty() * 0.1
        self.enemy_bullets.append([cx, cy, dx / dist * spd, dy / dist * spd])

    # -------------------------
    # Power-ups
    # -------------------------
    def update_powerups(self):
        for p in self.powerups:
            p[2] += 1
            p[1] += 0.5
            p[0] += pyxel.sin(p[2] * 3) * 0.5
        self.powerups = [p for p in self.powerups if p[1] < H + 8]

    # -------------------------
    # Colisoes
    # -------------------------
    def check_collisions(self):
        # Tiro x inimigo
        remaining = []
        for b in self.bullets:
            hit = False
            for e in self.enemies:
                if e["hp"] > 0 and aabb(b[0], b[1], 2, 6, e["x"], e["y"], 16, 16):
                    e["hp"] -= 1
                    hit = True
                    self.spawn_particles(b[0], b[1], 2, [7, 10])
                    if e["hp"] <= 0:
                        self.kill_enemy(e)
                    break
            if not hit:
                remaining.append(b)
        self.bullets = remaining
        self.enemies = [e for e in self.enemies if e["hp"] > 0]

        # Player x power-up
        keep = []
        for p in self.powerups:
            if aabb(self.px, self.py, 16, 16, p[0] - 4, p[1] - 4, 8, 8):
                if self.power < MAX_POWER:
                    self.power += 1
                    self.show_msg("POWER UP!")
                else:
                    self.score += 500
            else:
                keep.append(p)
        self.powerups = keep

        if self.invincible_timer > 0:
            return

        # Hitbox pequena no centro da nave (como nos shmups classicos)
        hx, hy, hw, hh = self.px + 5, self.py + 6, 6, 8

        for e in self.enemies:
            if aabb(hx, hy, hw, hh, e["x"], e["y"], 16, 16):
                if e["type"] != "chrono":
                    e["hp"] = 0
                    self.spawn_particles(e["x"] + 8, e["y"] + 8, 10, [8, 9, 10])
                self.player_hit()
                break
        self.enemies = [e for e in self.enemies if e["hp"] > 0]
        if self.invincible_timer > 0:
            return

        for b in self.enemy_bullets:
            if aabb(hx, hy, hw, hh, b[0] - 1, b[1] - 1, 3, 3):
                self.enemy_bullets.remove(b)
                self.player_hit()
                return

    def kill_enemy(self, e):
        self.score += ENEMY_DATA[e["type"]]["score"]
        cx, cy = e["x"] + 8, e["y"] + 8
        if e["type"] == "chrono":
            self.killed_chronos.add(e["id"])
            self.spawn_particles(cx, cy, 30, [10, 9, 7, 12])
            if self.charges < MAX_CHARGES:
                self.charges += 1
                self.show_msg("+1 VOLTA NO TEMPO!")
            else:
                self.score += 1000
                self.show_msg("CARGAS CHEIAS +1000")
        else:
            self.spawn_particles(cx, cy, 12, [8, 9, 10, 7])
            chance = 40 if e["type"] == "shooter" else 4
            if pyxel.rndi(0, 99) < chance:
                self.powerups.append([cx, cy, 0])
        # pyxel.play(3, 2)  # som de explosao

    def player_hit(self):
        self.lives -= 1
        self.power = max(1, self.power - 1)
        self.invincible_timer = 90
        self.spawn_particles(self.px + 8, self.py + 8, 20, [8, 9, 10, 7])
        # pyxel.play(3, 5)  # som de dano
        if self.lives <= 0:
            self.game_over = True

    # -------------------------
    # Particulas e mensagens
    # -------------------------
    def spawn_particles(self, x, y, n, colors):
        for _ in range(n):
            a = pyxel.rndf(0, 360)
            s = pyxel.rndf(0.5, 2.5)
            self.particles.append([x, y, pyxel.cos(a) * s, pyxel.sin(a) * s,
                                   pyxel.rndi(10, 25), colors[pyxel.rndi(0, len(colors) - 1)]])

    def update_particles(self):
        for p in self.particles:
            p[0] += p[2]
            p[1] += p[3]
            p[2] *= 0.92
            p[3] *= 0.92
            p[4] -= 1
        self.particles = [p for p in self.particles if p[4] > 0]

    def show_msg(self, text):
        self.msg = text
        self.msg_timer = 90

    # =========================
    # DRAW
    # =========================
    def draw(self):
        pyxel.cls(0)

        for x, y, spd in self.stars:
            pyxel.pset(x, y, 7 if spd == 3 else (6 if spd == 2 else 5))

        for p in self.powerups:
            col = 12 if pyxel.frame_count % 10 < 5 else 6
            pyxel.circ(p[0], p[1], 4, col)
            pyxel.text(p[0] - 1, p[1] - 2, "P", 7)

        for e in self.enemies:
            self.draw_enemy(e)

        for b in self.bullets:
            pyxel.rect(b[0], b[1], 2, 6, 10)

        for b in self.enemy_bullets:
            pyxel.circ(b[0], b[1], 1, 8 if pyxel.frame_count % 6 < 3 else 7)

        if not self.game_over or self.rewinding:
            self.draw_player()

        for p in self.particles:
            pyxel.pset(p[0], p[1], p[5])

        if self.rewinding:
            self.draw_rewind_fx()

        self.draw_hud()

        if self.game_over and not self.rewinding:
            self.draw_game_over()

    def draw_player(self):
        if (self.invincible_timer > 0 and not self.rewinding
                and (pyxel.frame_count // 4) % 2 == 0):
            return
        x, y = self.px, self.py
        # Troque por: pyxel.blt(x, y, 0, u, v, 16, 16, colkey)
        if pyxel.frame_count % 4 < 2:
            pyxel.tri(x + 6, y + 16, x + 10, y + 16, x + 8, y + 20, 10)  # chama do motor
        pyxel.tri(x + 8, y, x, y + 16, x + 16, y + 16, 11)
        pyxel.rect(x + 7, y + 6, 2, 4, 12)  # cockpit

    def draw_enemy(self, e):
        x, y, k = e["x"], e["y"], e["type"]
        # Troque cada forma por pyxel.blt(...) quando tiver os sprites
        if k == "basic":
            pyxel.rect(x + 2, y + 2, 12, 12, 8)
            pyxel.rectb(x + 2, y + 2, 12, 12, 2)
        elif k == "zigzag":
            pyxel.tri(x, y, x + 16, y, x + 8, y + 16, 14)
        elif k == "shooter":
            pyxel.rect(x, y + 4, 16, 8, 9)
            pyxel.circ(x + 8, y + 8, 3, 4)
            pyxel.rect(x + 7, y + 11, 2, 5, 13)
        elif k == "chrono":
            cx, cy = x + 8, y + 8
            ring = 10 if pyxel.frame_count % 10 < 5 else 9
            pyxel.circ(cx, cy, 7, 10)
            pyxel.circb(cx, cy, 8, ring)
            a = e["t"] * 6
            pyxel.line(cx, cy, cx + pyxel.cos(a) * 5, cy + pyxel.sin(a) * 5, 0)
            pyxel.line(cx, cy, cx, cy - 4, 0)

    def draw_rewind_fx(self):
        off = (pyxel.frame_count * 2) % 4
        for y in range(off, H, 4):
            pyxel.line(0, y, W - 1, y, 1)  # efeito de fita VHS
        pyxel.rectb(0, 0, W, H, 12)
        if pyxel.frame_count % 20 < 14:
            pyxel.text(W // 2 - 18, H // 2 - 3, "<< REWIND", 12)

    def draw_hud(self):
        pyxel.text(4, 4, f"SCORE {self.score:06d}", 7)
        pyxel.text(4, 12, f"LIVES {self.lives}", 7)
        pyxel.text(4, 20, f"PWR {self.power}", 11)

        # Cargas de voltar no tempo (reloginhos)
        for i in range(MAX_CHARGES):
            cx, cy = W - 30 + i * 10, 8
            filled = i < self.charges
            col = 10 if filled else 5
            if filled:
                pyxel.circ(cx, cy, 3, 1)
            pyxel.circb(cx, cy, 3, col)
            pyxel.line(cx, cy, cx, cy - 2, col)
            pyxel.line(cx, cy, cx + 2, cy, col)

        if self.msg_timer > 0 and (self.msg_timer > 30 or (self.msg_timer // 5) % 2 == 0):
            pyxel.text(W // 2 - len(self.msg) * 2, 40, self.msg, 10)

    def draw_game_over(self):
        pyxel.text(W // 2 - 18, 50, "GAME OVER", 8)
        if self.can_rewind() and pyxel.frame_count % 30 < 20:
            pyxel.text(W // 2 - 38, 62, "X: VOLTAR NO TEMPO!", 10)
        pyxel.text(W // 2 - 24, 72, "R: REINICIAR", 7)


App()