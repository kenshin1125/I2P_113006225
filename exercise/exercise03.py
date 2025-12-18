'''
Exercise 3: Moving a player

Task:
- Successfully move a character using input
- python exercise/exercise03.py
'''
import pygame

pygame.init()

screen = pygame.display.set_mode((640, 480))
pygame.display.set_caption("Moving Character")

player = pygame.image.load('assets/images/menu_sprites/menusprite1.png')
player_position = (0, 0)
player_speed = 25

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFT:
                pass
            elif event.key == pygame.K_RIGHT:
                pass
            elif event.key == pygame.K_UP:
                pass
            elif event.key == pygame.K_DOWN:
                pass
    screen.fill((255, 255, 255))
    screen.blit(player, player_position)
    pygame.display.flip()
         
         