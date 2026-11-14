# Tilt plotter
#
# Flash this, then click Plotter: tilt the micro:bit and watch the lines move.
# The micro:bit prints how much it's tilted left-right (x) and forwards-back
# (y), and Nu's plotter draws a graph of any numbers printed like this, in
# brackets with a comma.
#
# Try: add accelerometer.get_z() to see up-down too.

from microbit import *

while True:
    x = accelerometer.get_x()
    y = accelerometer.get_y()
    print((x, y))
    sleep(100)
