# Heartbeat
#
# A heart that beats forever: a big heart, then a small one, again and again.
#
# Try: make it beat faster by changing the numbers in sleep() (they're in
# milliseconds: 1000 is one second).

from microbit import *

while True:
    display.show(Image.HEART)
    sleep(500)
    display.show(Image.HEART_SMALL)
    sleep(500)
