# Dice
#
# Shake the micro:bit to roll a dice: it shows a number from 1 to 6.
#
# Try: roll two dice and show their total, or make a coin (heads or tails).

from microbit import *
import random

display.show("?")
while True:
    if accelerometer.was_gesture("shake"):
        display.show(random.randint(1, 6))
    sleep(50)
