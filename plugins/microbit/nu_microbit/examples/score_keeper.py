# Score keeper
#
# Count points with the buttons: A adds one, B takes one away. The score is
# saved in a file on the micro:bit, called score.txt, every time it changes,
# so it's still there after you unplug the micro:bit.
#
# Click Files to see score.txt on the micro:bit, and copy it to your computer.
#
# Try: show a happy face when the score reaches 10.


from microbit import *


def load_score():
    try:
        with open("score.txt") as f:
            return int(f.read())
    except (OSError, ValueError):
        return 0  # No file yet, or it doesn't hold a number.


def save_score(score):
    with open("score.txt", "w") as f:
        f.write(str(score))


score = load_score()
display.show(score)
while True:
    if button_a.was_pressed():
        score = score + 1
        save_score(score)
        display.show(score)
    if button_b.was_pressed():
        score = score - 1
        save_score(score)
        display.show(score)
    sleep(50)
