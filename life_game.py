import pygame
import random
import sys
import math

# ─── CONFIG ───────────────────────────────────────────────────────────────────
GRID_W, GRID_H = 60, 60
CELL = 12
UI_H = 60
WIDTH  = GRID_W * CELL
HEIGHT = GRID_H * CELL + UI_H
FPS    = 30

# Terrain
T_WATER   = 0
T_GRASS   = 1
T_SHALLOW = 2   # shallow water – herbivores OK, carnivores NOT

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
COL_WATER   = ( 40,  80, 140)
COL_SHALLOW = ( 70, 110, 170)
COL_GRASS_D = ( 50, 110,  50)
COL_GRASS_L = ( 65, 130,  60)
COL_PLANT   = ( 30, 190,  60)
COL_HERB    = (210, 170,  60)
COL_CARN    = (200,  50,  50)
COL_UI_BG   = ( 20,  20,  30)
COL_WHITE   = (240, 240, 240)
COL_HP_BG   = ( 60,  60,  60)
COL_HP_GOOD = ( 50, 200,  80)
COL_HP_BAD  = (220,  50,  50)


# ─── TERRAIN GENERATION (simple blob noise) ──────────────────────────────────
def generate_terrain():
    """Create a random terrain with water blobs using seeded random walks."""
    terrain = [[T_GRASS] * GRID_W for _ in range(GRID_H)]

    # drop random water "seeds" and grow them
    n_blobs = random.randint(5, 10)
    for _ in range(n_blobs):
        sx, sy = random.randint(2, GRID_W - 3), random.randint(2, GRID_H - 3)
        radius = random.randint(2, 5)
        size   = random.randint(15, 40)
        # grow blob outward
        for _ in range(size):
            x = sx + random.randint(-radius, radius)
            y = sy + random.randint(-radius, radius)
            if 0 <= x < GRID_W and 0 <= y < GRID_H:
                terrain[y][x] = T_WATER

    # add some shallow water adjacent to water
    for y in range(GRID_H):
        for x in range(GRID_W):
            if terrain[y][x] == T_GRASS: # count water neighbours
                wn = 0
                for dy, dx in ((-1,0),(1,0),(0,-1),(0,1)):
                    ny, nx = y+dy, x+dx
                    if 0 <= ny < GRID_H and 0 <= nx < GRID_W and terrain[ny][nx] == T_WATER:
                        wn += 1
                if wn >= 2 and random.random() < 0.5:
                    terrain[y][x] = T_SHALLOW

    return terrain


# ─── HELPERS ──────────────────────────────────────────────────────────────────
def in_grid(x, y):
    return 0 <= x < GRID_W and 0 <= y < GRID_H

def neighbours4(x, y):
    """4-neighbours (N,S,E,W)."""
    for dy, dx in ((-1,0),(1,0),(0,-1),(0,1)):
        nx, ny = x+dx, y+dy
        if in_grid(nx, ny):
            yield nx, ny

def neighbours8(x, y):
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x+dx, y+dy
            if in_grid(nx, ny):
                yield nx, ny


# ─── ENTITY ───────────────────────────────────────────────────────────────────
class Entity:
    __slots__ = ('x','y','kind','hp','max_hp')

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
        self.counts = {E_PLANT:0, E_HERB:0, E_CARN:0}
        self._seed_pop()

    # ── initial population ──────────────────────────────────────────────────
    def _seed_pop(self):
        # scatter plants
        for _ in range(200):
            x, y = random.randint(0, GRID_W-1), random.randint(0, GRID_H-1)
            if self.terrain[y][x] == T_GRASS and self.grid[y][x] == E_NONE:
                self._place(x, y, E_PLANT, 40, PLANT_MAX)
        # a few herbivores
        for _ in range(15):
            x, y = random.randint(0, GRID_W-1), random.randint(0, GRID_H-1)
            if self.terrain[y][x] == T_GRASS and self.grid[y][x] == E_NONE:
                self._place(x, y, E_HERB, 50, SPLIT_HP)
        # a few carnivores
        for _ in range(8):
            x, y = random.randint(0, GRID_W-1), random.randint(0, GRID_H-1)
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
            self.counts[e.kind] = self.counts.get(e.kind, 1) - 1
        self.grid[y][x] = E_NONE

    # ── can an entity stand on a cell? ──────────────────────────────────────
    def _can_stand(self, x, y, kind):
        t = self.terrain[y][x]
        if t == T_WATER:
            return False                       # nobody swims
        if t == T_SHALLOW:
            return kind == E_HERB              # carnivores blocked, herbivores ok
        return True                             # grass

    # ── ONE SIMULATION TICK ─────────────────────────────────────────────────
    def tick(self):
        self.ticks += 1
        to_remove = []
        to_spawn  = []          # (x, y, kind, hp)
        moved     = set()       # cells that just got occupied by a mover

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
                if e.kind==E_HERB:
                    e.hp -= ANIMAL_DECAY
                if e.kind == E_CARN:
                    e.hp -= ANIMAL_DECAY/2

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
                            moved.add((nx, ny))
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

    # ── RENDER ───────────────────────────────────────────────────────────────
    def draw(self, surf, font):
        # terrain
        for y in range(GRID_H):
            for x in range(GRID_W):
                t = self.terrain[y][x]
                if t == T_WATER:
                    c = COL_WATER
                elif t == T_SHALLOW:
                    c = COL_SHALLOW
                else:
                    # subtle checker
                    c = COL_GRASS_D if (x + y) % 2 else COL_GRASS_L
                pygame.draw.rect(surf, c, (x*CELL, y*CELL, CELL, CELL))

        # entities
        for (x, y), e in self.entities.items():
            px, py = x * CELL, y * CELL
            if e.kind == E_PLANT:
                # size scales with hp
                r = max(2, int(CELL * 0.4 * (e.hp / PLANT_MAX)))
                pygame.draw.circle(surf, COL_PLANT, (px + CELL//2, py + CELL//2), r)
            elif e.kind == E_HERB:
                pygame.draw.rect(surf, COL_HERB, (px+1, py+1, CELL-2, CELL-2), border_radius=2)
                # tiny "face" dot
                pygame.draw.circle(surf, (40,40,40), (px + CELL//2, py + CELL//2), 2)
            else:
                pygame.draw.rect(surf, COL_CARN, (px+1, py+1, CELL-2, CELL-2), border_radius=3)
                pygame.draw.circle(surf, (255,255,255), (px + CELL//2, py + CELL//2), 2)

            # HP bar for animals
            if e.kind in (E_HERB, E_CARN):
                bar_w = CELL - 2
                bar_h = 2
                bx, by = px + 1, py + CELL - bar_h - 1
                frac = max(0, e.hp / SPLIT_HP)
                col = COL_HP_GOOD if frac > 0.4 else COL_HP_BAD
                pygame.draw.rect(surf, COL_HP_BG, (bx, by, bar_w, bar_h))
                pygame.draw.rect(surf, col,      (bx, by, int(bar_w * frac), bar_h))

        # ── UI panel ─────────────────────────────────────────────────────────
        uy = GRID_H * CELL
        pygame.draw.rect(surf, COL_UI_BG, (0, uy, WIDTH, UI_H))
        self.counts = {E_PLANT:0, E_HERB:0, E_CARN:0}
        for e in self.entities.values():
            self.counts[e.kind] = self.counts.get(e.kind, 0) + 1

        stats = (
            f"Tick: {self.ticks}",
            f"🌿 Plants: {self.counts.get(E_PLANT,0)}",
            f"🐇 Herbivores: {self.counts.get(E_HERB,0)}",
            f"🦊 Carnivores: {self.counts.get(E_CARN,0)}",
            "Keys: [R]estart  [S]top  [H]elp",
        )
        for i, line in enumerate(stats):
            surf.blit(font.render(line, True, COL_WHITE), (10, uy + 4 + i * 12))


# ─── MAIN LOOP ────────────────────────────────────────────────────────────────
def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Three-Layer Life – Pygame")
    clock  = pygame.time.Clock()
    font   = pygame.font.SysFont("consolas", 13)
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

        world.draw(screen, font)
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()