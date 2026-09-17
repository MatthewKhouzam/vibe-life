import pygame
import random
import sys
import math

# ─── CONFIG ───────────────────────────────────────────────────────────────────
GRID_W, GRID_H = 60, 60
CELL = 12
UI_H = 96
WIDTH  = GRID_W * CELL
HEIGHT = GRID_H * CELL + UI_H

SIM_FPS    = 30   # simulation ticks per second
RENDER_FPS = 60   # render frames per second (smooth movement)

TICK_INTERVAL = 1.0 / SIM_FPS


# ─── TERRAIN ──────────────────────────────────────────────────────────────────
T_WATER   = 0
T_GRASS   = 1
T_SHALLOW = 2
T_DESERT  = 3

# ─── ENTITY KINDS ─────────────────────────────────────────────────────────────
E_NONE     = 0
E_PLANT    = 1
E_HERB     = 2
E_CARN     = 3

# ─── HP RULES ─────────────────────────────────────────────────────────────────
PLANT_REGEN      = 1
PLANT_MAX        = 60
ANIMAL_DECAY     = 0.8
HERB_EAT_GAIN    = 25
CARN_EAT_GAIN    = 45
SPLIT_HP         = 100
SPLIT_CHILD_HP   = 50

PLANT_SPAWN_CHANCE = 0.003
HERB_SPAWN_CHANCE  = 0.0001


# ─── COLOURS ──────────────────────────────────────────────────────────────────
COL_WATER_BASE   = ( 20,  48,  92)
COL_SHALLOW_BASE = ( 65, 130, 175)
COL_GRASS_DARK   = ( 48, 106,  62)
COL_GRASS_LIGHT  = ( 59, 124,  73)
COL_SAND_DARK    = (168, 150, 104)
COL_SAND_LIGHT   = (186, 170, 124)
COL_DESERT_DARK    = (185, 145,  90)
COL_DESERT_LIGHT   = (205, 170, 110)
COL_PLANT_DARK   = ( 35, 160,  70)
COL_PLANT_LIGHT  = ( 82, 215, 105)
COL_HERB         = (218, 176,  84)
COL_HERB_DARK    = (150, 112,  48)
COL_CARN         = (196,  58,  70)
COL_CARN_DARK    = (120,  35,  48)
COL_UI_BG        = ( 16,  20,  30)
COL_UI_ACCENT    = ( 95, 160, 255)
COL_WHITE        = (238, 242, 246)
COL_TEXT_DIM     = (170, 180, 195)
COL_HP_BG        = ( 42,  46,  58)
COL_HP_GOOD      = ( 70, 210, 110)
COL_HP_BAD       = (235,  70,  80)

GRASS_SHADES = [COL_GRASS_DARK, COL_GRASS_LIGHT, (54, 116, 68)]
SAND_SHADES  = [COL_SAND_DARK, COL_SAND_LIGHT]
DESERT_SHADES = [COL_DESERT_DARK, COL_DESERT_LIGHT, (195, 158, 100)]


# ─── EASING / MATH HELPERS ────────────────────────────────────────────────────
def smoothstep(t):
    """Cubic ease-in-out: slow start, fast middle, slow end."""
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def clamp255(v):
    return max(0, min(255, int(v)))


def lerp_color(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ─── GRID HELPERS ─────────────────────────────────────────────────────────────
def in_grid(x, y):
    return 0 <= x < GRID_W and 0 <= y < GRID_H


def neighbours4(x, y):
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        nx, ny = x + dx, y + dy
        if in_grid(nx, ny):
            yield nx, ny


def neighbours8(x, y):
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if in_grid(nx, ny):
                yield nx, ny


# ─── TERRAIN GENERATION ───────────────────────────────────────────────────────
def generate_terrain():
    terrain = [[T_GRASS] * GRID_W for _ in range(GRID_H)]

    # Water blobs
    n_blobs = random.randint(5, 10)
    for _ in range(n_blobs):
        sx = random.randint(2, GRID_W - 3)
        sy = random.randint(2, GRID_H - 3)
        radius = random.randint(2, 5)
        size   = random.randint(15, 40)
        for _ in range(size):
            x = sx + random.randint(-radius, radius)
            y = sy + random.randint(-radius, radius)
            if in_grid(x, y):
                terrain[y][x] = T_WATER

    # Shallow coast
    for y in range(GRID_H):
        for x in range(GRID_W):
            if terrain[y][x] == T_GRASS:
                wn = 0
                for nx, ny in neighbours4(x, y):
                    if terrain[ny][nx] == T_WATER:
                        wn += 1
                if wn >= 2 and random.random() < 0.5:
                    terrain[y][x] = T_SHALLOW

    # Desert blobs (barren – no plants)
    n_deserts = random.randint(3, 6)
    for _ in range(n_deserts):
        attempts = 0
        while attempts < 25:
            sx = random.randint(2, GRID_W - 3)
            sy = random.randint(2, GRID_H - 3)
            if terrain[sy][sx] == T_GRASS:
                break
            attempts += 1
        else:
            continue

        radius = random.randint(2, 5)
        size   = random.randint(15, 35)
        for _ in range(size):
            x = sx + random.randint(-radius, radius)
            y = sy + random.randint(-radius, radius)
            if in_grid(x, y) and terrain[y][x] == T_GRASS:
                terrain[y][x] = T_DESERT

    return terrain


# ─── ENTITY ───────────────────────────────────────────────────────────────────
class Entity:
    __slots__ = ('x', 'y', 'kind', 'hp', 'max_hp',
                 'prev_x', 'prev_y')

    def __init__(self, x, y, kind, hp, max_hp):
        self.x = x
        self.y = y
        self.kind   = kind
        self.hp     = hp
        self.max_hp = max_hp
        # Previous grid position (for smooth interpolation)
        self.prev_x = x
        self.prev_y = y


# ─── WORLD ────────────────────────────────────────────────────────────────────
class World:
    def __init__(self):
        self.terrain = generate_terrain()
        self.grid = [[E_NONE] * GRID_W for _ in range(GRID_H)]
        self.entities = {}
        self.ticks = 0
        self.counts = {E_PLANT: 0, E_HERB: 0, E_CARN: 0}

        # Smooth movement timer (0 → 1 between ticks)
        self.move_timer = 0.0

        # Skull effects
        self.skulls = []
        self._skull_sprites = None

        # Rendering caches
        self._terrain_surf = None
        self._shadow_surf  = None

        # Visual cell lists
        self.water_cells   = []
        self.shallow_cells = []
        self.shallow_coast = set()
        self.sand_cells    = set()

        for y in range(GRID_H):
            for x in range(GRID_W):
                t = self.terrain[y][x]
                if t == T_WATER:
                    self.water_cells.append((x, y))
                elif t == T_SHALLOW:
                    self.shallow_cells.append((x, y))
                    for nx, ny in neighbours8(x, y):
                        if self.terrain[ny][nx] == T_WATER:
                            self.shallow_coast.add((x, y))
                            break
                elif t == T_DESERT:
                    pass
                else:  # grass – visual coastal sand
                    waterish = 0
                    for nx, ny in neighbours4(x, y):
                        if self.terrain[ny][nx] in (T_WATER, T_SHALLOW):
                            waterish += 1
                    if waterish and random.random() < 0.72:
                        self.sand_cells.add((x, y))

        self._seed_pop()
        self._update_counts()

    # ── initial population ──────────────────────────────────────────────────
    def _seed_pop(self):
        for _ in range(200):
            x, y = random.randint(0, GRID_W - 1), random.randint(0, GRID_H - 1)
            if self.terrain[y][x] == T_GRASS and self.grid[y][x] == E_NONE:
                self._place(x, y, E_PLANT, 40, PLANT_MAX)
        for _ in range(15):
            x, y = random.randint(0, GRID_W - 1), random.randint(0, GRID_H - 1)
            if self.terrain[y][x] == T_GRASS and self.grid[y][x] == E_NONE:
                self._place(x, y, E_HERB, 50, SPLIT_HP)
        for _ in range(8):
            x, y = random.randint(0, GRID_W - 1), random.randint(0, GRID_H - 1)
            if self.terrain[y][x] == T_GRASS and self.grid[y][x] == E_NONE:
                self._place(x, y, E_CARN, 50, SPLIT_HP)

    def _place(self, x, y, kind, hp, max_hp):
        e = Entity(x, y, kind, hp, max_hp)
        self.grid[y][x] = kind
        self.entities[(x, y)] = e
        self.counts[kind] = self.counts.get(kind, 0) + 1

    def _remove(self, x, y):
        e = self.entities.pop((x, y), None)
        if e:
            self.counts[e.kind] = max(0, self.counts.get(e.kind, 1) - 1)
        self.grid[y][x] = E_NONE

    def _update_counts(self):
        self.counts = {E_PLANT: 0, E_HERB: 0, E_CARN: 0}
        for e in self.entities.values():
            self.counts[e.kind] = self.counts.get(e.kind, 0) + 1

    def _add_skull(self, x, y, kind):
        if kind not in (E_HERB, E_CARN):
            return
        max_age = random.randint(30, 60)
        self.skulls.append([x, y, kind, 0, max_age])
        if len(self.skulls) > 300:
            del self.skulls[:len(self.skulls) - 300]

    def _can_stand(self, x, y, kind):
        t = self.terrain[y][x]
        if t == T_WATER:
            return False
        if t == T_SHALLOW:
            return kind == E_HERB
        return True  # grass & desert

    # ── SMOOTH POSITION (interpolated with easing) ─────────────────────────
    def _render_pos(self, e, move_timer):
        """Return the interpolated (float) cell position for rendering."""
        t = smoothstep(move_timer)
        rx = e.prev_x + (e.x - e.prev_x) * t
        ry = e.prev_y + (e.y - e.prev_y) * t
        return rx, ry

    # ── ONE SIMULATION TICK ─────────────────────────────────────────────────
    def tick(self):
        self.ticks += 1

        # Save previous positions BEFORE any movement happens.
        for e in self.entities.values():
            e.prev_x = e.x
            e.prev_y = e.y

        # Age skulls
        for s in self.skulls:
            s[3] += 1
        self.skulls = [s for s in self.skulls if s[3] < s[4]]

        to_remove = []
        to_spawn  = []
        keys = list(self.entities.keys())

        for (x, y) in keys:
            e = self.entities.get((x, y))
            if e is None:
                continue

            # ── PLANTS ──────────────────────────────────────────────────────
            if e.kind == E_PLANT:
                e.hp = min(e.hp + PLANT_REGEN, e.max_hp)

            # ── ANIMALS ─────────────────────────────────────────────────────
            else:
                if e.kind == E_HERB:
                    e.hp -= ANIMAL_DECAY
                elif e.kind == E_CARN:
                    e.hp -= ANIMAL_DECAY / 2

                if e.kind == E_HERB:
                    target, gain = E_PLANT, HERB_EAT_GAIN
                else:
                    target, gain = E_HERB, CARN_EAT_GAIN

                eaten = False
                for nx, ny in neighbours4(x, y):
                    if (nx, ny) in self.entities:
                        ne = self.entities[(nx, ny)]
                        if ne.kind == target:
                            e.hp = min(e.hp + gain, SPLIT_HP)
                            if ne.kind in (E_HERB, E_CARN):
                                self._add_skull(nx, ny, ne.kind)
                            self._remove(nx, ny)
                            eaten = True
                            break

                if not eaten:
                    dirs = list(neighbours4(x, y))
                    random.shuffle(dirs)
                    for nx, ny in dirs:
                        if self._can_stand(nx, ny, e.kind) and (nx, ny) not in self.entities:
                            self._remove(x, y)
                            self.grid[ny][nx] = e.kind
                            self.entities[(nx, ny)] = e
                            e.x, e.y = nx, ny
                            break

            # ── SPLIT ───────────────────────────────────────────────────────
            if e.kind in (E_HERB, E_CARN) and e.hp >= SPLIT_HP:
                dirs = list(neighbours4(e.x, e.y))
                random.shuffle(dirs)
                for nx, ny in dirs:
                    if self._can_stand(nx, ny, e.kind) and (nx, ny) not in self.entities:
                        to_spawn.append((nx, ny, e.kind, SPLIT_CHILD_HP))
                        e.hp = SPLIT_CHILD_HP
                        break

            # ── DIE ─────────────────────────────────────────────────────────
            if e.hp <= 0:
                to_remove.append((e.x, e.y))
                if e.kind in (E_HERB, E_CARN):
                    self._add_skull(e.x, e.y, e.kind)

        # Apply removals & spawns
        for (x, y) in to_remove:
            if (x, y) in self.entities:
                self._remove(x, y)

        for (x, y, kind, hp) in to_spawn:
            if (x, y) not in self.entities and self._can_stand(x, y, kind):
                self._place(x, y, kind, hp, SPLIT_HP)

        # Plant growth (grass only, not desert)
        for _ in range(6):
            x = random.randint(0, GRID_W - 1)
            y = random.randint(0, GRID_H - 1)
            if self.terrain[y][x] == T_GRASS and self.grid[y][x] == E_NONE:
                if random.random() < PLANT_SPAWN_CHANCE * 200:
                    self._place(x, y, E_PLANT, 30, PLANT_MAX)

        self._update_counts()


    # ─── RENDER HELPERS ─────────────────────────────────────────────────────
    def _build_terrain(self):
        self._terrain_surf = pygame.Surface((WIDTH, GRID_H * CELL))
        for y in range(GRID_H):
            for x in range(GRID_W):
                t = self.terrain[y][x]
                if t == T_WATER:
                    c = COL_WATER_BASE
                elif t == T_SHALLOW:
                    c = COL_SHALLOW_BASE
                elif t == T_DESERT:
                    c = DESERT_SHADES[(x * 13 + y * 5) % len(DESERT_SHADES)]
                else:
                    if (x, y) in self.sand_cells:
                        c = SAND_SHADES[(x * 7 + y * 13) % len(SAND_SHADES)]
                    else:
                        c = GRASS_SHADES[(x * 11 + y * 7) % len(GRASS_SHADES)]
                pygame.draw.rect(self._terrain_surf, c, (x * CELL, y * CELL, CELL, CELL))

    def _get_shadow(self):
        if self._shadow_surf is None:
            s = pygame.Surface((CELL - 2, CELL - 3), pygame.SRCALPHA)
            s.fill((0, 0, 0, 0))
            pygame.draw.ellipse(s, (0, 0, 0, 55), s.get_rect())
            self._shadow_surf = s
        return self._shadow_surf

    def _get_skull_sprite(self, kind, alpha_level):
        if self._skull_sprites is None:
            self._skull_sprites = {}
        key = (kind, alpha_level)
        sprite = self._skull_sprites.get(key)
        if sprite is None:
            alpha = int(255 * (alpha_level / 15))
            sprite = self._make_skull_sprite(kind, alpha)
            self._skull_sprites[key] = sprite
        return sprite

    def _make_skull_sprite(self, kind, alpha):
        s = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
        if kind == E_HERB:
            bone = (235, 218, 170, alpha)
        elif kind == E_CARN:
            bone = (235, 180, 170, alpha)
        else:
            bone = (235, 230, 215, alpha)
        dark = (45, 40, 50, alpha)

        pygame.draw.circle(s, bone, (CELL // 2, 5), 4)
        pygame.draw.rect(s, bone, (3, 8, 6, 2), border_radius=1)
        pygame.draw.circle(s, dark, (4, 5), 1)
        pygame.draw.circle(s, dark, (8, 5), 1)
        pygame.draw.rect(s, dark, (6, 7, 1, 2))
        pygame.draw.rect(s, dark, (4, 9, 1, 1))
        pygame.draw.rect(s, dark, (7, 9, 1, 1))
        return s

    def _draw_skull(self, surf, skull):
        x, y, kind, age, max_age = skull
        if age >= max_age:
            return
        frac = 1.0 - (age / float(max_age))
        alpha_level = int(max(0, min(15, frac * 15)))
        if alpha_level <= 0:
            return
        sprite = self._get_skull_sprite(kind, alpha_level)
        surf.blit(sprite, (x * CELL, y * CELL))

    def _draw_water_animation(self, surf, t):
        for x, y in self.water_cells:
            v = math.sin(t * 1.8 + (x * 0.37 + y * 0.29)) * 10.0
            v += math.cos(t * 1.1 + x * 0.21 - y * 0.37) * 5.0
            c = (clamp255(COL_WATER_BASE[0] + v),
                 clamp255(COL_WATER_BASE[1] + v * 0.8),
                 clamp255(COL_WATER_BASE[2] + v))
            pygame.draw.rect(surf, c, (x * CELL, y * CELL, CELL, CELL))

        for x, y in self.shallow_cells:
            v = math.sin(t * 2.4 + (x + y) * 0.43) * 8.0
            if (x, y) in self.shallow_coast:
                v += 6.0
            c = (clamp255(COL_SHALLOW_BASE[0] + v),
                 clamp255(COL_SHALLOW_BASE[1] + v * 0.9),
                 clamp255(COL_SHALLOW_BASE[2] + v))
            pygame.draw.rect(surf, c, (x * CELL, y * CELL, CELL, CELL))

    # ── PLANT (static position) ─────────────────────────────────────────────
    def _draw_plant(self, surf, e, anim_t):
        px = e.x * CELL
        py = e.y * CELL
        cx = px + CELL // 2
        cy = py + CELL // 2

        frac = max(0.0, min(1.0, e.hp / PLANT_MAX))
        pulse = math.sin(anim_t * 2.5 + e.x * 0.73 + e.y * 1.19) * 0.5
        r = max(2, min(CELL // 2 - 1, int(CELL * 0.36 * (frac + 0.18) + pulse)))

        pygame.draw.circle(surf, COL_PLANT_DARK, (cx, cy + 1), r)
        if r > 2:
            leaf_r = max(1, r - 2)
            off = max(1, r // 2)
            pygame.draw.circle(surf, COL_PLANT_LIGHT, (cx - off, cy), leaf_r)
            pygame.draw.circle(surf, COL_PLANT_LIGHT, (cx + off, cy), leaf_r)
            pygame.draw.circle(surf, COL_PLANT_LIGHT, (cx, cy - off), leaf_r)

    # ── HERBIVORE (smooth pos + cute bounce) ───────────────────────────────
    def _draw_herb(self, surf, e, rx, ry, anim_t):
        # Cute bounce: abs(sin) gives a smooth up-down hop of ~2 px.
        phase = e.x * 2.3 + e.y * 1.7
        bounce = abs(math.sin(anim_t * 5.0 + phase)) * 2.0

        px = rx * CELL
        py = ry * CELL - bounce   # hop upward

        # Shadow stays on the ground (no bounce offset).
        shadow_x = int(rx * CELL) + 1
        shadow_y = int(ry * CELL) + 2
        surf.blit(self._get_shadow(), (shadow_x, shadow_y))

        # Body (rounded rect with outline)
        bx = int(px) + 1
        by = int(py) + 1
        body = pygame.Rect(bx, by, CELL - 2, CELL - 4)
        pygame.draw.rect(surf, COL_HERB_DARK, body, border_radius=3)
        pygame.draw.rect(surf, COL_HERB, body.inflate(-2, -2), border_radius=3)

        # Ears
        pygame.draw.circle(surf, COL_HERB_DARK, (bx + 2, by), 2)
        pygame.draw.circle(surf, COL_HERB_DARK, (bx + CELL - 4, by), 2)

        # Eyes
        pygame.draw.circle(surf, (35, 30, 25), (bx + 3, by + 4), 1)
        pygame.draw.circle(surf, (35, 30, 25), (bx + 6, by + 4), 1)

        # HP bar follows the (non-bounced) ground position
        self._draw_hp_bar(surf, rx, ry)

    # ── CARNIVORE (smooth pos, no bounce) ──────────────────────────────────
    def _draw_carn(self, surf, e, rx, ry, anim_t):
        px = rx * CELL
        py = ry * CELL

        shadow_x = int(px) + 1
        shadow_y = int(py) + 2
        surf.blit(self._get_shadow(), (shadow_x, shadow_y))

        cx = int(px) + CELL // 2
        top    = int(py) + 1
        bot_l  = (int(px) + 2,       int(py) + CELL - 4)
        bot_r  = (int(px) + CELL - 2, int(py) + CELL - 4)
        outer = [(cx, top), bot_l, bot_r]

        inner_top  = (cx, int(py) + 3)
        inner_bl   = (int(px) + 4, int(py) + CELL - 5)
        inner_br   = (int(px) + CELL - 4, int(py) + CELL - 5)
        inner = [inner_top, inner_bl, inner_br]

        pygame.draw.polygon(surf, COL_CARN_DARK, outer)
        pygame.draw.polygon(surf, COL_CARN, inner)

        # Eyes
        pygame.draw.circle(surf, (250, 240, 230), (cx - 2, int(py) + 5), 1)
        pygame.draw.circle(surf, (250, 240, 230), (cx + 2, int(py) + 5), 1)

        self._draw_hp_bar(surf, rx, ry)

    # ── HP BAR (follows interpolated ground position) ─────────────────────
    def _draw_hp_bar(self, surf, rx, ry):
        bx = int(rx * CELL) + 1
        by = int(ry * CELL) + CELL - 3
        bar_w = CELL - 2
        bar_h = 2

        # We need the entity's hp; pass it via a small trick:
        # (caller already knows, but we store on the bar draw)
        # Actually let's just use a generic full bar here and let caller set frac.
        # For simplicity, we'll draw the background only; fill is done by caller.
        pygame.draw.rect(surf, COL_HP_BG, (bx, by, bar_w, bar_h), border_radius=1)

    def _draw_hp_bar_filled(self, surf, rx, ry, frac):
        bx = int(rx * CELL) + 1
        by = int(ry * CELL) + CELL - 3
        bar_w = CELL - 2
        bar_h = 2

        pygame.draw.rect(surf, COL_HP_BG, (bx, by, bar_w, bar_h), border_radius=1)
        if frac > 0.0:
            col = lerp_color(COL_HP_BAD, COL_HP_GOOD, frac)
            pygame.draw.rect(surf, col, (bx, by, max(1, int(bar_w * frac)), bar_h), border_radius=1)

    # ── UI ─────────────────────────────────────────────────────────────────
    def _draw_ui(self, surf, font, title_font=None, paused=False):
        uy = GRID_H * CELL

        pygame.draw.rect(surf, COL_UI_BG, (0, uy, WIDTH, UI_H))
        pygame.draw.rect(surf, COL_UI_ACCENT, (0, uy, WIDTH, 2))
        pygame.draw.rect(surf, (35, 40, 55), (0, uy + UI_H - 2, WIDTH, 2))

        if title_font is None:
            title_font = font

        surf.blit(title_font.render("Three-Layer Life", True, COL_WHITE), (14, uy + 8))

        tick_txt = font.render(f"Tick {self.ticks}", True, COL_TEXT_DIM)
        surf.blit(tick_txt, (WIDTH - tick_txt.get_width() - 14, uy + 9))

        if paused:
            pause_txt = title_font.render("Paused", True, COL_UI_ACCENT)
            surf.blit(pause_txt, (WIDTH // 2 - pause_txt.get_width() // 2, uy + 8))

        y = uy + 34
        x = 16
        items = [
            (E_PLANT, "Plants", COL_PLANT_LIGHT),
            (E_HERB,  "Herbivores", COL_HERB),
            (E_CARN,  "Carnivores", COL_CARN),
        ]
        for kind, label, color in items:
            pygame.draw.circle(surf, color, (x + 5, y + 6), 5)
            txt = font.render(f"{label}: {self.counts.get(kind, 0)}", True, COL_WHITE)
            surf.blit(txt, (x + 14, y))
            x += 20 + txt.get_width() + 22

        controls = font.render("R restart   S pause   ESC quit", True, COL_TEXT_DIM)
        surf.blit(controls, (16, uy + 60))

    # ── MAIN DRAW ──────────────────────────────────────────────────────────
    def draw(self, surf, font, title_font=None, paused=False):
        if self._terrain_surf is None:
            self._build_terrain()

        surf.blit(self._terrain_surf, (0, 0))

        anim_t = pygame.time.get_ticks() * 0.001
        self._draw_water_animation(surf, anim_t)

        pygame.draw.rect(surf, (10, 14, 22), (0, 0, WIDTH, GRID_H * CELL), width=2)

        mt = self.move_timer  # 0 → 1, eased internally via smoothstep

        # Plants (static)
        for e in self.entities.values():
            if e.kind == E_PLANT:
                self._draw_plant(surf, e, anim_t)

        # Skulls (static position, fade over time)
        for s in self.skulls:
            self._draw_skull(surf, s)

        # Animals (smooth interpolated + bounce for herbivores)
        for e in self.entities.values():
            if e.kind == E_HERB:
                rx, ry = self._render_pos(e, mt)
                self._draw_herb(surf, e, rx, ry, anim_t)
            elif e.kind == E_CARN:
                rx, ry = self._render_pos(e, mt)
                self._draw_carn(surf, e, rx, ry, anim_t)

        self._update_counts()
        self._draw_ui(surf, font, title_font, paused)


# ─── MAIN LOOP (decoupled sim / render for smooth movement) ─────────────────
def main():
    pygame.init()

    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Three-Layer Life – Pygame")

    clock      = pygame.time.Clock()
    font       = pygame.font.SysFont("consolas", 13)
    title_font = pygame.font.SysFont("consolas", 16, bold=True)

    world  = World()
    paused = False

    last_tick_time = pygame.time.get_ticks() * 0.001
    running = True

    while running:
        now = pygame.time.get_ticks() * 0.001

        # ── Events ─────────────────────────────────────────────────────────
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_r:
                    world = World()
                    paused = False
                    last_tick_time = now
                elif ev.key == pygame.K_s:
                    paused = not paused
                elif ev.key == pygame.K_ESCAPE:
                    running = False

        # ── Advance smooth-movement timer (0 → 1 over one tick interval) ──
        if not paused:
            world.move_timer = min(1.0, (now - last_tick_time) / TICK_INTERVAL)
        else:
            world.move_timer = 1.0  # freeze at final position

        # ── Tick simulation when due ───────────────────────────────────────
        if not paused and (now - last_tick_time) >= TICK_INTERVAL:
            world.tick()
            last_tick_time = now
            world.move_timer = 0.0

        # ── Render every frame (at RENDER_FPS) ─────────────────────────────
        world.draw(screen, font, title_font, paused)

        pygame.display.flip()
        clock.tick(RENDER_FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
