# Hello, micro:bit!
#
# Click Flash to put this program on your micro:bit. It scrolls a message
# across the lights, then shows a smiley face.
#
# Try: change the message, or show Image.HEART instead of Image.HAPPY.

from microbit import *

display.scroll("Hello!")
display.show(Image.HAPPY)
