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
FPS    = 30

# Terrain
T_WATER   = 0
T_GRASS   = 1
T_SHALLOW = 2

# Entity kinds
E_NONE     = 0
E_PLANT    = 1
E_HERB     = 2
E_CARN     = 3

# HP rules
PLANT_REGEN       = 1          # plant HP gained per tick
PLANT_MAX         = 60
ANIMAL_DECAY      = 0.8        # HP lost per tick (both animal types)
HERB_EAT_GAIN     = 25
CARN_EAT_GAIN     = 45
SPLIT_HP          = 100        # split threshold
SPLIT_CHILD_HP    = 50

# Spawn rates (per tick, per empty land cell)
PLANT_SPAWN_CHANCE  = 0.003
HERB_SPAWN_CHANCE   = 0.0001


# ─── COLOURS ──────────────────────────────────────────────────────────────────
COL_WATER_BASE   = ( 20,  48,  92)
COL_SHALLOW_BASE = ( 65, 130, 175)

COL_GRASS_DARK   = ( 48, 106,  62)
COL_GRASS_LIGHT  = ( 59, 124,  73)

COL_SAND_DARK    = (168, 150, 104)
COL_SAND_LIGHT   = (186, 170, 124)

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

GRASS_SHADES = [
    COL_GRASS_DARK,
    COL_GRASS_LIGHT,
    (54, 116, 68),
]

SAND_SHADES = [
    COL_SAND_DARK,
    COL_SAND_LIGHT,
]


# ─── HELPERS ──────────────────────────────────────────────────────────────────
def in_grid(x, y):
    return 0 <= x < GRID_W and 0 <= y < GRID_H


def neighbours4(x, y):
    """4-neighbours (N,S,E,W)."""
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


def clamp255(v):
    return max(0, min(255, int(v)))


def lerp_color(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ─── TERRAIN GENERATION (simple blob noise) ──────────────────────────────────
def generate_terrain():
    """Create a random terrain with water blobs using seeded random walks."""
    terrain = [[T_GRASS] * GRID_W for _ in range(GRID_H)]

    # drop random water "seeds" and grow them
    n_blobs = random.randint(5, 10)
    for _ in range(n_blobs):
        sx = random.randint(2, GRID_W - 3)
        sy = random.randint(2, GRID_H - 3)
        radius = random.randint(2, 5)
        size   = random.randint(15, 40)

        # grow blob outward
        for _ in range(size):
            x = sx + random.randint(-radius, radius)
            y = sy + random.randint(-radius, radius)
            if in_grid(x, y):
                terrain[y][x] = T_WATER

    # add some shallow water adjacent to water
    for y in range(GRID_H):
        for x in range(GRID_W):
            if terrain[y][x] == T_GRASS:
                wn = 0
                for nx, ny in neighbours4(x, y):
                    if terrain[ny][nx] == T_WATER:
                        wn += 1

                if wn >= 2 and random.random() < 0.5:
                    terrain[y][x] = T_SHALLOW

    return terrain


# ─── ENTITY ───────────────────────────────────────────────────────────────────
class Entity:
    __slots__ = ('x', 'y', 'kind', 'hp', 'max_hp')

    def __init__(self, x, y, kind, hp, max_hp):
        self.x = x
        self.y = y
        self.kind   = kind
        self.hp     = hp
        self.max_hp = max_hp


# ─── WORLD ────────────────────────────────────────────────────────────────────
class World:
    def __init__(self):
        self.terrain = generate_terrain()
        self.grid = [[E_NONE] * GRID_W for _ in range(GRID_H)]
        self.entities = {}          # (x,y) → Entity
        self.ticks = 0
        self.counts = {E_PLANT: 0, E_HERB: 0, E_CARN: 0}

        # Rendering helpers
        self._terrain_surf = None
        self._shadow_surf = None

        # Precomputed visual cell lists
        self.water_cells = []
        self.shallow_cells = []
        self.shallow_coast = set()
        self.sand_cells = set()

        for y in range(GRID_H):
            for x in range(GRID_W):
                t = self.terrain[y][x]

                if t == T_WATER:
                    self.water_cells.append((x, y))

                elif t == T_SHALLOW:
                    self.shallow_cells.append((x, y))

                    # Mark shallow cells touching deep water for a brighter "foam" look.
                    for nx, ny in neighbours8(x, y):
                        if self.terrain[ny][nx] == T_WATER:
                            self.shallow_coast.add((x, y))
                            break

                else:  # grass
                    # Visual-only sandy coastline. This does not change simulation rules;
                    # it only makes coastal grass look like beach/sand.
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
        # scatter plants
        for _ in range(200):
            x, y = random.randint(0, GRID_W - 1), random.randint(0, GRID_H - 1)
            if self.terrain[y][x] == T_GRASS and self.grid[y][x] == E_NONE:
                self._place(x, y, E_PLANT, 40, PLANT_MAX)

        # a few herbivores
        for _ in range(15):
            x, y = random.randint(0, GRID_W - 1), random.randint(0, GRID_H - 1)
            if self.terrain[y][x] == T_GRASS and self.grid[y][x] == E_NONE:
                self._place(x, y, E_HERB, 50, SPLIT_HP)

        # a few carnivores
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

    # ── can an entity stand on a cell? ──────────────────────────────────────
    def _can_stand(self, x, y, kind):
        t = self.terrain[y][x]

        if t == T_WATER:
            return False                       # nobody swims

        if t == T_SHALLOW:
            return kind == E_HERB              # carnivores blocked, herbivores ok

        return True                            # grass


    # ── ONE SIMULATION TICK ─────────────────────────────────────────────────
    def tick(self):
        self.ticks += 1

        to_remove = []
        to_spawn  = []          # (x, y, kind, hp)

        # work on a copy of keys so we can modify safely
        keys = list(self.entities.keys())

        for (x, y) in keys:
            e = self.entities.get((x, y))
            if e is None:
                continue

            # ── PLANTS ──────────────────────────────────────────────────────
            if e.kind == E_PLANT:
                e.hp = min(e.hp + PLANT_REGEN, e.max_hp)

            # ── ANIMALS (herbivore / carnivore) ────────────────────────────
            else:
                if e.kind == E_HERB:
                    e.hp -= ANIMAL_DECAY

                if e.kind == E_CARN:
                    e.hp -= ANIMAL_DECAY / 2

                # try to eat
                if e.kind == E_HERB:
                    target = E_PLANT
                    gain   = HERB_EAT_GAIN
                else:
                    target = E_HERB
                    gain   = CARN_EAT_GAIN

                eaten = False
                for nx, ny in neighbours4(x, y):
                    if (nx, ny) in self.entities:
                        ne = self.entities[(nx, ny)]
                        if ne.kind == target:
                            # eat!
                            e.hp = min(e.hp + gain, SPLIT_HP)
                            self._remove(nx, ny)
                            eaten = True
                            break

                if not eaten:
                    # random walk to a free, walkable cell
                    dirs = list(neighbours4(x, y))
                    random.shuffle(dirs)

                    for nx, ny in dirs:
                        if self._can_stand(nx, ny, e.kind) and (nx, ny) not in self.entities:
                            # move
                            self._remove(x, y)
                            self.grid[ny][nx] = e.kind
                            self.entities[(nx, ny)] = e
                            e.x, e.y = nx, ny
                            break

            # ── SPLIT ───────────────────────────────────────────────────────
            if e.kind in (E_HERB, E_CARN) and e.hp >= SPLIT_HP:
                # find a free adjacent cell
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

        # apply removals & spawns
        for (x, y) in to_remove:
            if (x, y) in self.entities:
                self._remove(x, y)

        for (x, y, kind, hp) in to_spawn:
            if (x, y) not in self.entities and self._can_stand(x, y, kind):
                self._place(x, y, kind, hp, SPLIT_HP)

        # ── PLANT GROWTH (new plants appear on empty grass) ─────────────────
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

                else:  # grass, possibly visually sandy near the coast
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

    def _draw_water_animation(self, surf, t):
        # Deep water shimmer.
        for x, y in self.water_cells:
            v = math.sin(t * 1.8 + (x * 0.37 + y * 0.29)) * 10.0
            v += math.cos(t * 1.1 + x * 0.21 - y * 0.37) * 5.0

            c = (
                clamp255(COL_WATER_BASE[0] + v),
                clamp255(COL_WATER_BASE[1] + v * 0.8),
                clamp255(COL_WATER_BASE[2] + v)
            )

            pygame.draw.rect(surf, c, (x * CELL, y * CELL, CELL, CELL))

        # Shallow water shimmer, with a little extra brightness near deep water.
        for x, y in self.shallow_cells:
            v = math.sin(t * 2.4 + (x + y) * 0.43) * 8.0

            if (x, y) in self.shallow_coast:
                v += 6.0

            c = (
                clamp255(COL_SHALLOW_BASE[0] + v),
                clamp255(COL_SHALLOW_BASE[1] + v * 0.9),
                clamp255(COL_SHALLOW_BASE[2] + v)
            )

            pygame.draw.rect(surf, c, (x * CELL, y * CELL, CELL, CELL))

    def _draw_plant(self, surf, e, t):
        px = e.x * CELL
        py = e.y * CELL

        cx = px + CELL // 2
        cy = py + CELL // 2

        frac = max(0.0, min(1.0, e.hp / PLANT_MAX))

        # Gentle pulse so plants feel alive even while paused.
        pulse = math.sin(t * 2.5 + e.x * 0.73 + e.y * 1.19) * 0.5

        r = max(2, min(CELL // 2 - 1, int(CELL * 0.36 * (frac + 0.18) + pulse)))

        pygame.draw.circle(surf, COL_PLANT_DARK, (cx, cy + 1), r)

        if r > 2:
            leaf_r = max(1, r - 2)
            off = max(1, r // 2)

            pygame.draw.circle(surf, COL_PLANT_LIGHT, (cx - off, cy), leaf_r)
            pygame.draw.circle(surf, COL_PLANT_LIGHT, (cx + off, cy), leaf_r)
            pygame.draw.circle(surf, COL_PLANT_LIGHT, (cx, cy - off), leaf_r)

    def _draw_herb(self, surf, e):
        px = e.x * CELL
        py = e.y * CELL

        surf.blit(self._get_shadow(), (px + 1, py + 2))

        body = pygame.Rect(px + 1, py + 1, CELL - 2, CELL - 4)

        pygame.draw.rect(surf, COL_HERB_DARK, body, border_radius=3)
        pygame.draw.rect(surf, COL_HERB, body.inflate(-2, -2), border_radius=3)

        # Ears.
        pygame.draw.circle(surf, COL_HERB_DARK, (px + 3, py + 2), 2)
        pygame.draw.circle(surf, COL_HERB_DARK, (px + CELL - 4, py + 2), 2)

        # Eyes.
        pygame.draw.circle(surf, (35, 30, 25), (px + 4, py + 5), 1)
        pygame.draw.circle(surf, (35, 30, 25), (px + 7, py + 5), 1)

        self._draw_hp_bar(surf, e)

    def _draw_carn(self, surf, e):
        px = e.x * CELL
        py = e.y * CELL

        cx = px + CELL // 2

        surf.blit(self._get_shadow(), (px + 1, py + 2))

        outer = [
            (cx, py + 1),
            (px + 2, py + CELL - 4),
            (px + CELL - 2, py + CELL - 4)
        ]

        inner = [
            (cx, py + 3),
            (px + 4, py + CELL - 5),
            (px + CELL - 4, py + CELL - 5)
        ]

        pygame.draw.polygon(surf, COL_CARN_DARK, outer)
        pygame.draw.polygon(surf, COL_CARN, inner)

        # Eyes.
        pygame.draw.circle(surf, (250, 240, 230), (cx - 2, py + 5), 1)
        pygame.draw.circle(surf, (250, 240, 230), (cx + 2, py + 5), 1)

        self._draw_hp_bar(surf, e)

    def _draw_hp_bar(self, surf, e):
        px = e.x * CELL
        py = e.y * CELL

        bar_w = CELL - 2
        bar_h = 2
        bx, by = px + 1, py + CELL - 3

        frac = max(0.0, min(1.0, e.hp / SPLIT_HP))

        pygame.draw.rect(surf, COL_HP_BG, (bx, by, bar_w, bar_h), border_radius=1)

        if frac > 0.0:
            col = lerp_color(COL_HP_BAD, COL_HP_GOOD, frac)
            pygame.draw.rect(surf, col, (bx, by, max(1, int(bar_w * frac)), bar_h), border_radius=1)

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

        # Population chips.
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


    # ── RENDER ───────────────────────────────────────────────────────────────
    def draw(self, surf, font, title_font=None, paused=False):
        if self._terrain_surf is None:
            self._build_terrain()

        surf.blit(self._terrain_surf, (0, 0))

        anim_t = pygame.time.get_ticks() * 0.001
        self._draw_water_animation(surf, anim_t)

        # Subtle frame around the simulation area.
        pygame.draw.rect(surf, (10, 14, 22), (0, 0, WIDTH, GRID_H * CELL), width=2)

        # Draw plants first, then animals on top.
        for e in self.entities.values():
            if e.kind == E_PLANT:
                self._draw_plant(surf, e, anim_t)

        for e in self.entities.values():
            if e.kind == E_HERB:
                self._draw_herb(surf, e)
            elif e.kind == E_CARN:
                self._draw_carn(surf, e)

        self._update_counts()
        self._draw_ui(surf, font, title_font, paused)


# ─── MAIN LOOP ────────────────────────────────────────────────────────────────
def main():
    pygame.init()

    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Three-Layer Life – Pygame")

    clock  = pygame.time.Clock()
    font   = pygame.font.SysFont("consolas", 13)
    title_font = pygame.font.SysFont("consolas", 16, bold=True)

    world  = World()
    paused = False

    running = True
    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False

            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_r:
                    world = World()
                    paused = False

                elif ev.key == pygame.K_s:
                    paused = not paused

                elif ev.key == pygame.K_ESCAPE:
                    running = False

        if not paused:
            world.tick()

        world.draw(screen, font, title_font, paused)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
