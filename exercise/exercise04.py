'''
Exercise 4: Render a map

Task:
- Successfully render .tmx data
- python exercise/exercise04.py
'''

import sys
import pygame as pg
from pytmx.util_pygame import load_pygame
from pytmx import TiledTileLayer

pg.init()
screen = pg.display.set_mode((640, 480))
pg.display.set_caption("Tilemap")

tmxdata = load_pygame("assets/maps/map.tmx")

# Create a canvas for images
tile_w, tile_h = tmxdata.tilewidth, tmxdata.tileheight
pixel_w, pixel_h = tmxdata.width * tile_w, tmxdata.height * tile_h
surface = pg.Surface((pixel_w, pixel_h), pg.SRCALPHA)

# Build a map once to the surface
for layer in tmxdata.visible_layers:
    if isinstance(layer, TiledTileLayer):
        for x, y, gid in layer:
            pass

running = True
while running:
    for event in pg.event.get():
        if event.type == pg.QUIT:
            running = False

    screen.fill((0, 0, 0))
    screen.blit(surface, (0, 0))
    pg.display.flip()

pg.quit()
sys.exit()