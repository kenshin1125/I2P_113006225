'''
Exercise 1: Hello Window

Task:
- Successfully run this program
- python exercise/exercise01.py
'''
import pygame

pygame.init()

screen = pygame.display.set_mode((640, 480))
pygame.display.set_caption("Hello Window")

while True:
   for event in pygame.event.get():
      if event.type == pygame.QUIT:
         pygame.quit()
         
         