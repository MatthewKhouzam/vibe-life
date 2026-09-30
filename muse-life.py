import math
import random

import pygame

"""
Make me a simulation game in pygame. it is a game of life. This game will play out with 3 types of entities. Plants, herbivores and carnivores. A plant will grow until eaten. A herbivore and carivore will start with high health, when it eats, it gains health. Every turn causes it to lose health. At 0 hp they die. Carnivores gain HP by eating herbivores. Herbivores gain HP by eating plants. Herbivores run away from carnivores. Carnivores run towards herbivores to eat them.
1m 39
"""
WIDTH, HEIGHT = 800, 600
FPS = 60

# Colors
GREEN = (60, 180, 75)
DARK_GREEN = (40, 120, 50)
BROWN = (180, 120, 60)
RED = (220, 60, 60)
BG = (20, 20, 30)

PLANT_GROW_TIME = 180   # frames to mature
HERB_SPEED = 1.5
CARN_SPEED = 2.0
FLEE_DIST = 150
CHASE_DIST = 200
SEEK_DIST = 150
ANIMAL_RADIUS = 8
COLLISION_DIST = ANIMAL_RADIUS * 2
EAT_DIST = COLLISION_DIST + 1


def dist(a,b):
    return math.hypot(a.x - b.x, a.y - b.y)

def resolve_collision(a, b, min_dist):
    d = dist(a, b)
    if d < min_dist and d > 0:
        overlap = min_dist - d
        angle = math.atan2(b.y - a.y, b.x - a.x)
        push = overlap / 2
        a.x -= math.cos(angle) * push
        a.y -= math.sin(angle) * push
        b.x += math.cos(angle) * push
        b.y += math.sin(angle) * push
    elif d == 0:
        a.x += random.uniform(-1,1)
        a.y += random.uniform(-1,1)

class Plant:
    def __init__(self):
        self.x = random.randint(10, WIDTH-10)
        self.y = random.randint(10, HEIGHT-10)
        self.age = 0
        self.mature = False

    def update(self):
        self.age += 1
        if self.age > PLANT_GROW_TIME:
            self.mature = True

    def draw(self, screen):
        size = 3 + min(self.age/PLANT_GROW_TIME,1)*4
        col = GREEN if self.mature else DARK_GREEN
        pygame.draw.circle(screen, col, (int(self.x), int(self.y)), int(size))

class Animal:
    def __init__(self, x, y, color, speed, health):
        self.x = x
        self.y = y
        self.color = color
        self.speed = speed
        self.health = health
        self.angle = random.uniform(0, 2*math.pi)
        self.wander_timer = 0

    def wander(self):
        self.wander_timer -= 1
        if self.wander_timer <= 0:
            self.angle += random.uniform(-0.5, 0.5)
            self.wander_timer = random.randint(20, 60)
        self.x += math.cos(self.angle) * self.speed
        self.y += math.sin(self.angle) * self.speed
        self.bounce()

    def bounce(self):
        if self.x < 5 or self.x > WIDTH-5:
            self.angle = math.pi - self.angle
            self.x = max(5, min(WIDTH-5, self.x))
        if self.y < 5 or self.y > HEIGHT-5:
            self.angle = -self.angle
            self.y = max(5, min(HEIGHT-5, self.y))

    def move_towards(self, tx, ty):
        dx = tx - self.x
        dy = ty - self.y
        d = math.hypot(dx, dy) or 1
        self.x += dx/d * self.speed
        self.y += dy/d * self.speed
        self.bounce()

    def move_away(self, tx, ty):
        dx = self.x - tx
        dy = self.y - ty
        d = math.hypot(dx, dy) or 1
        self.x += dx/d * self.speed
        self.y += dy/d * self.speed
        self.bounce()

    def draw(self, screen):
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), 8)

class Herbivore(Animal):
    def __init__(self):
        super().__init__(random.randint(10,WIDTH-10), random.randint(10,HEIGHT-10),
                         BROWN, HERB_SPEED, 100)

    def update(self, plants, carnivores):
        self.health -= 0.08

        # flee from carnivores
        nearest_carn = None
        nearest_carn_d = float('inf')
        for c in carnivores:
            d = dist(self, c)
            if d < nearest_carn_d:
                nearest_carn_d = d
                nearest_carn = c
        if nearest_carn and nearest_carn_d < FLEE_DIST:
            self.move_away(nearest_carn.x, nearest_carn.y)
            # still can eat if already adjacent
        else:
            # seek mature plant
            nearest_plant = None
            nearest_plant_d = float('inf')
            for p in plants:
                if not p.mature: continue
                d = dist(self, p)
                if d < nearest_plant_d:
                    nearest_plant_d = d
                    nearest_plant = p
            if nearest_plant and nearest_plant_d < SEEK_DIST:
                self.move_towards(nearest_plant.x, nearest_plant.y)
            else:
                self.wander()

        # eat any adjacent mature plant
        for p in plants:
            if p.mature and dist(self, p) < EAT_DIST:
                self.health += 35
                return p  # signal eat
        return None

class Carnivore(Animal):
    def __init__(self):
        super().__init__(random.randint(10,WIDTH-10), random.randint(10,HEIGHT-10),
                         RED, CARN_SPEED, 120)

class Carnivore(Animal):
    def __init__(self):
        super().__init__(random.randint(10,WIDTH-10), random.randint(10,HEIGHT-10),
                         RED, CARN_SPEED, 120)

    def update(self, herbivores):
        self.health -= 0.08

        nearest_h = None
        nearest_h_d = float('inf')
        for h in herbivores:
            d = dist(self, h)
            if d < nearest_h_d:
                nearest_h_d = d
                nearest_h = h
        if nearest_h and nearest_h_d < CHASE_DIST:
            self.move_towards(nearest_h.x, nearest_h.y)
        else:
            self.wander()

        # eat any adjacent herbivore
        for h in herbivores:
            if dist(self, h) < EAT_DIST:
                self.health += 45
                return h  # signal eat
        return None


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 24)

    plants = [Plant() for _ in range(40)]
    herbivores = [Herbivore() for _ in range(20)]
    carnivores = [Carnivore() for _ in range(6)]

    spawn_timer = 0
    running = True
    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False

        screen.fill(BG)

        # spawn plants
        spawn_timer += 1
        if spawn_timer % 60 == 0:
            plants.append(Plant())
            spawn_timer = 0

        # update plants
        for p in plants[:]:
            p.update()
            p.draw(screen)

        # update herbivores
        for h in herbivores[:]:
            eaten = h.update(plants, carnivores)
            if eaten and eaten in plants:
                plants.remove(eaten)
            h.draw(screen)
            if h.health <= 0:
                herbivores.remove(h)

        # update carnivores
        for c in carnivores[:]:
            eaten = c.update(herbivores)
            if eaten and eaten in herbivores:
                herbivores.remove(eaten)
            c.draw(screen)
            if c.health <= 0:
                carnivores.remove(c)

        # collision detection between animals
        for i, a1 in enumerate(herbivores):
            for a2 in herbivores[i+1:]:
                resolve_collision(a1, a2, COLLISION_DIST)
            for c in carnivores:
                resolve_collision(a1, c, COLLISION_DIST)
        for i, c1 in enumerate(carnivores):
            for c2 in carnivores[i+1:]:
                resolve_collision(c1, c2, COLLISION_DIST)

        # UI
        txt = f"Plants: {len(plants)}  Herbivores: {len(herbivores)}  Carnivores: {len(carnivores)}"
        screen.blit(font.render(txt, True, (240,240,240)), (10,10))

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    main()
