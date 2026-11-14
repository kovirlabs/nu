# Buttons
#
# Press button A for a happy face, button B for a sad one, and both together
# for a surprise. The program checks the buttons over and over, forever.
#
# Try: show a different image for each button, or count the presses with
# button_a.get_presses() and scroll the number.

from microbit import *

while True:
    if button_a.is_pressed() and button_b.is_pressed():
        display.show(Image.SURPRISED)
    elif button_a.is_pressed():
        display.show(Image.HAPPY)
    elif button_b.is_pressed():
        display.show(Image.SAD)
    else:
        display.clear()
    sleep(100)
