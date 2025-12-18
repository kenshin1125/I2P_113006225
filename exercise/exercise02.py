'''
Exercise 2: Hello Green

Task:
- Successfully update the screen to become green and red
- python exercise/exercise02.py
'''
import pygame

pygame.init()

screen = pygame.display.set_mode((640, 480))
pygame.display.set_caption("Hello Green")

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
    
    pygame.time.wait(10)
    screen.fill((0, 255, 0))
    '''TODO: Flip Display'''
    
    pygame.time.wait(10)
    screen.fill((255, 0, 0))
    '''TODO: Flip Display'''
         
         