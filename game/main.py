import pyxel


class App:
    def __init__(self):
        # Janela do jogo
        pyxel.init(160, 120, title="Hunter of mitop")

        # Carrega seu arquivo de recursos (sprites/som/musica)
        pyxel.load("assets/recurso-mitop.pyxres")

        # -------------------------
        # Estado do jogador (nave)
        # -------------------------
        self.px = pyxel.width // 2 - 8
        self.py = pyxel.height - 20
        self.pspeed = 2
        self.lives = 3
        self.invincible_timer = 0  # tempo de invencibilidade após hit

        # -------------------------
        # Tiros do jogador
        # Cada tiro = [x, y]
        # -------------------------
        self.bullets = []
        self.bullet_speed = 4
        self.shoot_cooldown = 0  # trava de tiro

        # -------------------------
        # Inimigos
        # Cada inimigo = [x, y, hp]
        # -------------------------
        self.enemies = []
        self.enemy_speed = 1
        self.spawn_timer = 0

        # -------------------------
        # Fundo (estrelas)
        # Cada estrela = [x, y, speed]
        # -------------------------
        self.stars = []
        for _ in range(40):
            self.stars.append([pyxel.rndi(0, pyxel.width - 1),
                               pyxel.rndi(0, pyxel.height - 1),
                               pyxel.rndi(1, 3)])

        # Pontuação
        self.score = 0

        # Estado do jogo
        self.game_over = False

        # Música (se você tiver)
        # pyxel.playm(0, loop=True)

        pyxel.run(self.update, self.draw)

    # -------------------------
    # UPDATE: lógica do jogo
    # -------------------------
    def update(self):
        if pyxel.btnp(pyxel.KEY_Q):
            pyxel.quit()

        # Reiniciar no game over
        if self.game_over:
            if pyxel.btnp(pyxel.KEY_R):
                self.__init__()
            return

        self.update_background()
        self.update_player()
        self.update_bullets()
        self.update_enemies()
        self.check_collisions()

    # Fundo com estrelas descendo
    def update_background(self):
        for s in self.stars:
            s[1] += s[2]
            if s[1] >= pyxel.height:
                s[0] = pyxel.rndi(0, pyxel.width - 1)
                s[1] = 0
                s[2] = pyxel.rndi(1, 3)

    # Jogador: movimento + tiro
    def update_player(self):
        # Movimento livre (4 direções)
        if pyxel.btn(pyxel.KEY_LEFT) or pyxel.btn(pyxel.GAMEPAD1_BUTTON_DPAD_LEFT):
            self.px = max(self.px - self.pspeed, 0)
        if pyxel.btn(pyxel.KEY_RIGHT) or pyxel.btn(pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT):
            self.px = min(self.px + self.pspeed, pyxel.width - 16)
        if pyxel.btn(pyxel.KEY_UP) or pyxel.btn(pyxel.GAMEPAD1_BUTTON_DPAD_UP):
            self.py = max(self.py - self.pspeed, 0)
        if pyxel.btn(pyxel.KEY_DOWN) or pyxel.btn(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN):
            self.py = min(self.py + self.pspeed, pyxel.height - 16)

        # Cooldowns
        if self.shoot_cooldown > 0:
            self.shoot_cooldown -= 1
        if self.invincible_timer > 0:
            self.invincible_timer -= 1

        # Tiro (SPACE) com cadência
        if pyxel.btn(pyxel.KEY_SPACE) or pyxel.btn(pyxel.GAMEPAD1_BUTTON_A):
            if self.shoot_cooldown == 0:
                # Tiro nasce no "nariz" da nave
                bx = self.px + 7
                by = self.py - 2
                self.bullets.append([bx, by])
                self.shoot_cooldown = 8  # quanto menor, mais metralhadora
                # pyxel.play(3, 0)  # ajuste seu som

    # Atualiza tiros
    def update_bullets(self):
        for b in self.bullets:
            b[1] -= self.bullet_speed

        # Remove tiros fora da tela
        self.bullets = [b for b in self.bullets if b[1] > -8]

    # Spawn e movimento dos inimigos
    def update_enemies(self):
        # Spawn controlado por timer
        self.spawn_timer += 1
        if self.spawn_timer >= 30:  # a cada 30 frames
            self.spawn_timer = 0
            ex = pyxel.rndi(0, pyxel.width - 16)
            ey = -16
            hp = 1
            self.enemies.append([ex, ey, hp])

        # Movimento dos inimigos
        for e in self.enemies:
            e[1] += self.enemy_speed

        # Remove inimigos que passaram da tela
        self.enemies = [e for e in self.enemies if e[1] < pyxel.height + 20]

    # Colisões: tiro-inimigo e inimigo-player
    def check_collisions(self):
        # --- Tiro x inimigo ---
        remaining_bullets = []
        for b in self.bullets:
            hit = False
            for e in self.enemies:
                if self.aabb(b[0], b[1], 2, 6, e[0], e[1], 16, 16):
                    e[2] -= 1
                    hit = True
                    # pyxel.play(3, 1)  # som hit
                    if e[2] <= 0:
                        self.score += 100
                        # pyxel.play(3, 2)  # som explode
                    break
            if not hit:
                remaining_bullets.append(b)
        self.bullets = remaining_bullets

        # Remove inimigos mortos
        self.enemies = [e for e in self.enemies if e[2] > 0]

        # --- Inimigo x player ---
        if self.invincible_timer == 0:
            for e in self.enemies:
                if self.aabb(self.px, self.py, 16, 16, e[0], e[1], 16, 16):
                    self.lives -= 1
                    self.invincible_timer = 60  # 1 segundo de invencibilidade (~60fps)
                    # pyxel.play(3, 5)  # som dano

                    # Empurra inimigo pra fora (ou remove)
                    e[2] = 0

                    if self.lives <= 0:
                        self.game_over = True
                    break

    # Função de colisão retângulo x retângulo (AABB)
    def aabb(self, ax, ay, aw, ah, bx, by, bw, bh):
        return (
            ax < bx + bw and
            ax + aw > bx and
            ay < by + bh and
            ay + ah > by
        )

    # -------------------------
    # DRAW: renderização
    # -------------------------
    def draw(self):
        pyxel.cls(0)  # preto

        # Desenha estrelas
        for x, y, spd in self.stars:
            pyxel.pset(x, y, 7 if spd == 1 else 6)  # brilho varia pelo speed

        # HUD
        pyxel.text(5, 5, f"SCORE {self.score:05d}", 7)
        pyxel.text(5, 15, f"LIVES {self.lives}", 7)

        # Game over
        if self.game_over:
            pyxel.text(50, 55, "GAME OVER", 8)
            pyxel.text(38, 65, "Press R to restart", 7)
            return

        # Desenha inimigos
        for ex, ey, hp in self.enemies:
            # Se você tiver sprite de inimigo no banco:
            # pyxel.blt(ex, ey, 0, u, v, 16, 16, colkey)
            # Placeholder (quadrado)
            pyxel.rect(ex, ey, 16, 16, 8)

        # Desenha tiros
        for bx, by in self.bullets:
            pyxel.rect(bx, by, 2, 6, 10)

        # Desenha player (pisca quando invencível)
        if self.invincible_timer > 0 and (pyxel.frame_count // 4) % 2 == 0:
            return  # não desenha em alguns frames (efeito piscando)

        # Se você tiver sprite de nave no banco:
        # pyxel.blt(self.px, self.py, 0, u, v, 16, 16, colkey)
        # Placeholder (triângulo/nave simples)
        pyxel.tri(self.px + 8, self.py, self.px, self.py + 16, self.px + 16, self.py + 16, 11)


App()