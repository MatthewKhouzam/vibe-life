import pygame
import random
import sys

# --- Configuration ---
WIDTH, HEIGHT = 800, 800
GRID_SIZE = 20  # Size of each cell in pixels
COLS = WIDTH // GRID_SIZE
ROWS = HEIGHT // GRID_SIZE

# Colors
COLOR_WATER = (30, 64, 175)
COLOR_LAND = (34, 139, 34)
COLOR_PLANT = (0, 255, 0)
COLOR_HERBIVORE = (255, 165, 0)
COLOR_CARNIVORE = (255, 0, 0)

# Simulation Constants
INITIAL_PLANTS = 200
INITIAL_HERBIVORES = 50
INITIAL_CARNIVORES = 15

PLANT_REGEN = 1
ANIMAL_STARVATION = 0.5
EATING_BOOST = 40
MAX_HP = 100

class Organism:
    def __init__(self, x, y, hp, type):
        self.x = x
        self.y = y
        self.hp = hp
        self.type = type  # "plant", "herbivore", "carnivore"

    def get_color(self):
        if self.type == "plant": return COLOR_PLANT
        if self.type == "herbivore": return COLOR_HERBIVORE
        if self.type == "carnivore": return COLOR_CARNIVORE
        return (255, 255, 255)

class World:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Gemma Life Simulation")
        self.clock = pygame.time.Clock()
        
        # Terrain: 0 for Water, 1 for Land
        self.terrain = [[(random.random() > 0.3) for _ in range(ROWS)] for _ in range(COLS)]
        
        # Grid to hold entities
        self.grid = [[None for _ in range(ROWS)] for _ in range(COLS)]
        
        self.populate()

    def populate(self):
        # Seed Plants
        for _ in range(INITIAL_PLANTS):
            x, y = random.randint(0, COLS-1), random.randint(0, ROWS-1)
            if self.terrain[x][y] == 1:
                self.grid[x][y] = Organism(x, y, 50, "plant")

        # Seed Herbivores
        for _ in range(INITIAL_HERBIVORES):
            x, y = random.randint(0, COLS-1), random.randint(0, ROWS-1)
            if self.terrain[x][y] == 1:
                self.grid[x][y] = Organism(x, y, 50, "herbivore")

        # Seed Carnivores
        for _ in range(INITIAL_CARNIVORES):
            x, y = random.randint(0, COLS-1), random.randint(0, ROWS-1)
            if self.terrain[x][y] == 1:
                self.grid[x][y] = Organism(x, y, 50, "carnivore")

    def get_neighbors(self, x, y):
        neighbors = []
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0: continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < COLS and 0 <= ny < ROWS:
                    neighbors.append((nx, ny))
        return neighbors

    def update(self):
        new_grid = [[None for _ in range(ROWS)] for _ in range(COLS)]
        # We use a temporary list to process moves to avoid processing the same cell twice
        processed_cells = set()

        for x in range(COLS):
            for y in range(ROWS):
                entity = self.grid[x][y]
                
                if entity is None:
                    new_grid[x][y] = None
                    continue

                if entity.type == "plant":
                    entity.hp += PLANT_REGEN
                    if entity.hp > MAX_HP: entity.hp = MAX_HP
                    new_grid[x][y] = entity
                
                elif entity.type in ["herbivore", "carnivore"]:
                    # Starvation
                    entity.hp -= ANIMAL_STARVATION
                    
                    # Death check
                    if entity.hp <= 0:
                        new_grid[x][y] = None
                        continue

                    # Movement and Eating logic
                    neighbors = self.get_neighbors(x, y)
                    random.shuffle(neighbors)
                    
                    moved = False
                    for nx, ny in neighbors:
                        target = self.grid[nx][ny]
                        
                        # Carnivore logic
                        if entity.type == "carnivore":
                            # Can't cross water
                            if self.terrain[nx][ny] == 0: continue
                            # Eat herbivore if present
                            if target and target.type == "herbivore":
                                entity.hp += EATING_BOOST
                                new_grid[nx][ny] = entity
                                new_grid[x][y] = None
                                moved = True
                                break
                        
                        # Herbivore logic
                        elif entity.type == "herbivore":
                            # Eat plant if present
                            if target and target.type == "plant":
                                entity.hp += EATING_BOOST
                                new_grid[nx][ny] = entity
                                new_grid[x][y] = None
                                moved = True
                                break
                            # Otherwise just move to empty land
                            if target is None and self.terrain[nx][ny] == 1:
                                new_grid[nx][ny] = entity
                                new_grid[x][y] = None
                                moved = True
                                break
                    
                    # If no eating/moving happened, stay in place
                    if not moved:
                        new_grid[x][y] = entity

                    # Reproduction logic
                    if entity.hp >= MAX_HP:
                        entity.hp = 50
                        # Create clone in a random neighbor spot
                        neighbors = self.get_neighbors(x, y)
                        for nx, ny in neighbors:
                            if new_grid[nx][ny] is None and self.terrain[nx][ny] == 1:
                                new_grid[nx][ny] = Organism(nx, ny, 50, entity.type)
                                break

        self.grid = new_grid

    def draw(self):
        for x in range(COLS):
            for y in range(ROWS):
                # Draw Terrain
                color = COLOR_LAND if self.terrain[x][y] == 1 else COLOR_WATER
                pygame.draw.rect(self.screen, color, (x*GRID_SIZE, y*GRID_SIZE, GRID_SIZE, GRID_SIZE))
                
                # Draw Entity
                entity = self.grid[x][y]
                if entity:
                    pygame.draw.rect(self.screen, entity.get_color(), 
                                     (x*GRID_SIZE+2, y*GRID_SIZE+2, GRID_SIZE-4, GRID_SIZE-4))

        pygame.display.flip()

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
            
            self.update()
            self.draw()
            self.clock.tick(10) # Speed of simulation
        pygame.quit()

if __name__ == "__main__":
    world = World()
    world.run()
