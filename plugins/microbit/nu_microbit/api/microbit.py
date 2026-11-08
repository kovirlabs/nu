"""
Contains definitions for the MicroPython micro:bit related APIs so they can be
used in the editor for autocomplete and call tips.

Covers MicroPython for the BBC micro:bit V2 (firmware 2.x) and V1 (firmware
1.x). Entries for features that only work on the micro:bit V2 say so at the
end of their description.

Copyright (c) 2015-2017 Nicholas H.Tollervey and others (see the AUTHORS file).
Copyright (c) 2026 the Nu contributors (see the AUTHORS file).

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""


MICROBIT_APIS = [
    # RNG
    _("random.getrandbits(n) \nReturn a whole number made from n random bits."),
    _(
        "random.seed(n) \nStart the random number generator from a known whole number 'n'.\nUsing the same seed gives the same sequence of random numbers."
    ),
    _(
        "random.randint(a, b) \nReturn a random whole number between a and b (inclusive)."
    ),
    _(
        "random.randrange(start, stop, step=1) \nReturn a random whole number from range(start, stop, step).\nUse randrange(stop) to pick from 0 up to (but not including) stop."
    ),
    _(
        "random.choice(seq) \nReturn a randomly chosen item from a sequence (such as a list)."
    ),
    _(
        "random.random() \nReturn a random decimal number from 0.0 up to (but not including) 1.0."
    ),
    _(
        "random.uniform(a, b) \nReturn a random decimal number between a and b (inclusive)."
    ),
    # OS
    _(
        "os.listdir() \nReturn a list of the names of all the files stored on the micro:bit."
    ),
    _("os.remove(filename) \nRemove (delete) the file called filename."),
    _("os.size(filename) \nReturn the size, in bytes, of the file called filename."),
    _(
        "os.uname() \nReturn information about MicroPython and the device,\nsuch as the version numbers."
    ),
    # SYS
    _(
        "sys.version \nThe version of the Python language that MicroPython follows, as a string."
    ),
    _(
        "sys.version_info \nThe version of the Python language that MicroPython follows, as a tuple of numbers."
    ),
    _(
        "sys.implementation \nInformation about the Python being used: its name ('micropython') and version."
    ),
    _("sys.platform \nThe name of the platform MicroPython is running on, 'microbit'."),
    _("sys.byteorder \nThe order of bytes in a number on this device, 'little'."),
    _(
        "sys.exit(retval=0) \nStop the program straight away by raising a SystemExit exception."
    ),
    _(
        "sys.print_exception(exc) \nPrint information about the exception 'exc' (and where it happened) to the REPL."
    ),
    # System state objects.
    _(
        "microbit.panic(n) \nStop everything and show a sad face and the error code 'n' (0 to 255) on the display.\nPress the reset button to restart."
    ),
    _("microbit.reset() \nRestart the micro:bit, just like pressing the reset button."),
    _(
        "microbit.sleep(n) \nWait for 'n' milliseconds (1 second = 1000 ms).\nsleep(2000) pauses your program for 2 seconds."
    ),
    _(
        "microbit.running_time() \nReturn the number of milliseconds since the micro:bit was switched on or restarted."
    ),
    _(
        "microbit.temperature() \nReturn the temperature of the micro:bit in degrees Celsius."
    ),
    _(
        "microbit.scale(value, from_, to) \nConvert 'value' from one range to another, e.g.\nscale(accelerometer.get_x(), from_=(-2000, 2000), to=(0, 255))."
    ),
    _(
        "microbit.set_volume(v) \nSet the volume of the speaker and sound pins to 'v', a number from 0 (silent) to 255 (loudest). (micro:bit V2)"
    ),
    _(
        "microbit.run_every(callback=None, days=0, h=0, min=0, s=0, ms=0) \nRun the function 'callback' again and again, every time the given time passes.\nYou can also put @run_every(s=1) above a function to run it every second. (micro:bit V2)"
    ),
    # Accelerometer 3D orientation
    _(
        "microbit.accelerometer.get_x() \nReturn micro:bit's tilt (X acceleration) in milli-g's."
    ),
    _(
        "microbit.accelerometer.get_y() \nReturn micro:bit's tilt (Y acceleration) in milli-g's."
    ),
    _(
        "microbit.accelerometer.get_z() \nReturn micro:bit's up-down motion (Z acceleration) in milli-g's."
    ),
    _(
        "microbit.accelerometer.get_values() \nGet the acceleration in all three directions at once, as a tuple of numbers (X, Y, Z)."
    ),
    _(
        "microbit.accelerometer.get_strength() \nGet the strength of the acceleration in all directions added together, as a positive number in milli-g's."
    ),
    _(
        "microbit.accelerometer.current_gesture() \nReturn the name of the gesture happening right now, such as 'up', 'face up' or 'shake'."
    ),
    _(
        "microbit.accelerometer.is_gesture(name) \nReturn True or False to show if the named gesture is happening right now.\nGestures are: 'up', 'down', 'left', 'right', 'face up', 'face down',\n'freefall', '3g', '6g', '8g' and 'shake'."
    ),
    _(
        "microbit.accelerometer.was_gesture(name) \nReturn True or False to show if the named gesture happened since the last call.\nGestures are: 'up', 'down', 'left', 'right', 'face up', 'face down',\n'freefall', '3g', '6g', '8g' and 'shake'."
    ),
    _(
        "microbit.accelerometer.get_gestures() \nReturn a tuple of the gestures that have happened, with the most recent last.\nCalling this also clears the gesture history."
    ),
    _(
        "microbit.accelerometer.set_range(value) \nSet how much acceleration can be measured, in g: 2, 4 or 8.\nThe default is 2."
    ),
    # Pushbutton
    _(
        "microbit.button_a.is_pressed() \nReturn True if button A is being pressed down right now, else False."
    ),
    _(
        "microbit.button_a.was_pressed() \nReturn True if button A was pressed since the micro:bit started or since\nthe last time was_pressed() was called, else False."
    ),
    _(
        "microbit.button_a.get_presses() \nReturn how many times button A has been pressed, and reset this count to zero."
    ),
    _(
        "microbit.button_b.is_pressed() \nReturn True if button B is being pressed down right now, else False."
    ),
    _(
        "microbit.button_b.was_pressed() \nReturn True if button B was pressed since the micro:bit started or since\nthe last time was_pressed() was called, else False."
    ),
    _(
        "microbit.button_b.get_presses() \nReturn how many times button B has been pressed, and reset this count to zero."
    ),
    # Compass 3D direction heading
    _(
        "microbit.compass.calibrate() \nStart calibrating the compass so it is accurate.\nYou will be asked to tilt the micro:bit to light up every LED on the display."
    ),
    _(
        "microbit.compass.is_calibrated() \nReturn True if the compass has been calibrated, else False."
    ),
    _(
        "microbit.compass.clear_calibration() \nUndo the calibration, so the compass is uncalibrated again."
    ),
    _(
        "microbit.compass.get_x() \nReturn the strength of the magnetic field along micro:bit's X axis, in nano-tesla.\nThe number is bigger near a magnet!"
    ),
    _(
        "microbit.compass.get_y() \nReturn the strength of the magnetic field along micro:bit's Y axis, in nano-tesla.\nThe number is bigger near a magnet!"
    ),
    _(
        "microbit.compass.get_z() \nReturn the strength of the magnetic field along micro:bit's Z axis, in nano-tesla.\nThe number is bigger near a magnet!"
    ),
    _(
        "microbit.compass.get_field_strength() \nReturn the strength of the magnetic field around the micro:bit, in nano-tesla."
    ),
    _(
        "microbit.compass.heading() \nReturn a number from 0 to 360 for the direction the micro:bit is pointing. 0 is north.\nCall calibrate() first for accurate results."
    ),
    # Display 5x5 LED grid
    _(
        "microbit.display.show(image, delay=400, wait=True, loop=False, clear=False) \nShow an image, a letter or a number on the display. If 'image' is a list of\nimages (or a string) they are shown one after another, 'delay' milliseconds apart.\nIf wait is False this happens in the background. If loop is True it repeats forever.\nIf clear is True the display is cleared at the end."
    ),
    _(
        "microbit.display.scroll(text, delay=150, wait=True, loop=False, monospace=False) \nScroll text (or a number) across the display. 'delay' sets how fast it scrolls.\nIf wait is False it scrolls in the background. If loop is True it repeats forever.\nIf monospace is True every character takes up 5 pixel-columns."
    ),
    _("microbit.display.clear() \nTurn off all the LEDs on the display."),
    _(
        "microbit.display.get_pixel(x, y) \nReturn the brightness of the LED at column x and row y,\nfrom 0 (off) to 9 (brightest)."
    ),
    _(
        "microbit.display.set_pixel(x, y, value) \nSet the brightness of the LED at column x and row y to 'value',\nfrom 0 (off) to 9 (brightest)."
    ),
    _("microbit.display.on() \nTurn on the display."),
    _(
        "microbit.display.off() \nTurn off the display. This lets you use the display's pins for other things."
    ),
    _(
        "microbit.display.is_on() \nReturn True if the display is on, or False if it is off."
    ),
    _(
        "microbit.display.read_light_level() \nUse the LEDs to measure how much light is falling on the display.\nReturns a number from 0 (dark) to 255 (bright)."
    ),
    # Pins
    _(
        "microbit.pin0.read_digital() \nRead the digital value of pin0: 1 if the pin is high, 0 if it is low."
    ),
    _(
        "microbit.pin0.write_digital(value) \nSet pin0 to high if value is 1, or to low if it is 0."
    ),
    _(
        "microbit.pin0.read_analog() \nRead the voltage on pin0, as a number between 0 (meaning 0V)\nand 1023 (meaning 3.3V)."
    ),
    _(
        "microbit.pin0.write_analog(value) \nOutput a PWM signal on pin0. 'value' goes from 0 (always off)\nto 1023 (always on)."
    ),
    _(
        "microbit.pin0.set_analog_period(period) \nSet the period of the PWM signal on pin0 to 'period' milliseconds (at least 1 ms)."
    ),
    _(
        "microbit.pin0.set_analog_period_microseconds(period) \nSet the period of the PWM signal on pin0 to 'period' microseconds (at least 256)."
    ),
    _(
        "microbit.pin0.get_analog_period_microseconds() \nReturn the period of the PWM signal on pin0, in microseconds."
    ),
    _(
        "microbit.pin0.is_touched() \nReturn True if pin0 is being touched with a finger, else False.\nFor the best results also touch the GND pin with your other hand."
    ),
    _(
        "microbit.pin0.set_touch_mode(value) \nSet how pin0 detects touch: pin0.RESISTIVE (the default) or pin0.CAPACITIVE. (micro:bit V2)"
    ),
    _(
        "microbit.pin0.set_pull(value) \nSet the pull state of pin0 to pin0.PULL_UP, pin0.PULL_DOWN or pin0.NO_PULL."
    ),
    _(
        "microbit.pin0.get_pull() \nReturn the pull state of pin0: PULL_UP, PULL_DOWN or NO_PULL."
    ),
    _(
        "microbit.pin0.get_mode() \nReturn what pin0 is being used for right now, as a string,\nsuch as 'unused', 'read_digital', 'write_analog', 'touch' or 'music'."
    ),
    _(
        "microbit.pin0.PULL_UP \nUse with set_pull() to pull the pin up to high when nothing is connected."
    ),
    _(
        "microbit.pin0.PULL_DOWN \nUse with set_pull() to pull the pin down to low when nothing is connected."
    ),
    _(
        "microbit.pin0.NO_PULL \nUse with set_pull() to leave the pin floating when nothing is connected."
    ),
    _(
        "microbit.pin0.RESISTIVE \nUse with set_touch_mode() for resistive touch, where you also need to touch GND. (micro:bit V2)"
    ),
    _(
        "microbit.pin0.CAPACITIVE \nUse with set_touch_mode() for capacitive touch, which works without touching GND. (micro:bit V2)"
    ),
    _(
        "microbit.pin1.read_digital() \nRead the digital value of pin1: 1 if the pin is high, 0 if it is low."
    ),
    _(
        "microbit.pin1.write_digital(value) \nSet pin1 to high if value is 1, or to low if it is 0."
    ),
    _(
        "microbit.pin1.read_analog() \nRead the voltage on pin1, as a number between 0 (meaning 0V)\nand 1023 (meaning 3.3V)."
    ),
    _(
        "microbit.pin1.write_analog(value) \nOutput a PWM signal on pin1. 'value' goes from 0 (always off)\nto 1023 (always on)."
    ),
    _(
        "microbit.pin1.is_touched() \nReturn True if pin1 is being touched with a finger, else False.\nFor the best results also touch the GND pin with your other hand."
    ),
    _(
        "microbit.pin1.set_touch_mode(value) \nSet how pin1 detects touch: pin1.RESISTIVE (the default) or pin1.CAPACITIVE. (micro:bit V2)"
    ),
    _(
        "microbit.pin2.read_digital() \nRead the digital value of pin2: 1 if the pin is high, 0 if it is low."
    ),
    _(
        "microbit.pin2.write_digital(value) \nSet pin2 to high if value is 1, or to low if it is 0."
    ),
    _(
        "microbit.pin2.read_analog() \nRead the voltage on pin2, as a number between 0 (meaning 0V)\nand 1023 (meaning 3.3V)."
    ),
    _(
        "microbit.pin2.write_analog(value) \nOutput a PWM signal on pin2. 'value' goes from 0 (always off)\nto 1023 (always on)."
    ),
    _(
        "microbit.pin2.is_touched() \nReturn True if pin2 is being touched with a finger, else False.\nFor the best results also touch the GND pin with your other hand."
    ),
    _(
        "microbit.pin2.set_touch_mode(value) \nSet how pin2 detects touch: pin2.RESISTIVE (the default) or pin2.CAPACITIVE. (micro:bit V2)"
    ),
    _(
        "microbit.pin3 \nEdge connector pin 3. It can read and write digital and analog values\n(see pin0 for the methods). It is shared with the display."
    ),
    _(
        "microbit.pin4 \nEdge connector pin 4. It can read and write digital and analog values\n(see pin0 for the methods). It is shared with the display."
    ),
    _(
        "microbit.pin5 \nEdge connector pin 5. It can read and write digital values and write analog values\n(see pin0 for the methods). It is shared with button A."
    ),
    _(
        "microbit.pin6 \nEdge connector pin 6. It can read and write digital values and write analog values\n(see pin0 for the methods). It is shared with the display."
    ),
    _(
        "microbit.pin7 \nEdge connector pin 7. It can read and write digital values and write analog values\n(see pin0 for the methods). It is shared with the display."
    ),
    _(
        "microbit.pin8 \nEdge connector pin 8. It can read and write digital values and write analog values\n(see pin0 for the methods)."
    ),
    _(
        "microbit.pin9 \nEdge connector pin 9. It can read and write digital values and write analog values\n(see pin0 for the methods)."
    ),
    _(
        "microbit.pin10 \nEdge connector pin 10. It can read and write digital and analog values\n(see pin0 for the methods). It is shared with the display."
    ),
    _(
        "microbit.pin11 \nEdge connector pin 11. It can read and write digital values and write analog values\n(see pin0 for the methods). It is shared with button B."
    ),
    _(
        "microbit.pin12 \nEdge connector pin 12. It can read and write digital values and write analog values\n(see pin0 for the methods)."
    ),
    _(
        "microbit.pin13 \nEdge connector pin 13. It can read and write digital values and write analog values\n(see pin0 for the methods). It is shared with SPI (SCK)."
    ),
    _(
        "microbit.pin14 \nEdge connector pin 14. It can read and write digital values and write analog values\n(see pin0 for the methods). It is shared with SPI (MISO)."
    ),
    _(
        "microbit.pin15 \nEdge connector pin 15. It can read and write digital values and write analog values\n(see pin0 for the methods). It is shared with SPI (MOSI)."
    ),
    _(
        "microbit.pin16 \nEdge connector pin 16. It can read and write digital values and write analog values\n(see pin0 for the methods)."
    ),
    _(
        "microbit.pin19 \nEdge connector pin 19. It can read and write digital values and write analog values\n(see pin0 for the methods). It is shared with I2C (SCL)."
    ),
    _(
        "microbit.pin20 \nEdge connector pin 20. It can read and write digital values and write analog values\n(see pin0 for the methods). It is shared with I2C (SDA)."
    ),
    _(
        "microbit.pin_logo.is_touched() \nReturn True if the gold logo on the front of the micro:bit is being touched, else False. (micro:bit V2)"
    ),
    _(
        "microbit.pin_logo.set_touch_mode(value) \nSet how the logo detects touch: pin_logo.CAPACITIVE (the default) or pin_logo.RESISTIVE. (micro:bit V2)"
    ),
    _(
        "microbit.pin_speaker \nThe pin connected to the built-in speaker. Use it for PWM,\ne.g. pin_speaker.write_analog(128), or as the pin for music and audio. (micro:bit V2)"
    ),
    # Microphone
    _(
        "microbit.microphone.current_event() \nReturn the last sound event heard: SoundEvent.LOUD, SoundEvent.QUIET or None. (micro:bit V2)"
    ),
    _(
        "microbit.microphone.was_event(event) \nReturn True if the sound event (e.g. SoundEvent.LOUD) was heard at least once\nsince the last call. This also clears the sound history. (micro:bit V2)"
    ),
    _(
        "microbit.microphone.is_event(event) \nReturn True if the sound event (e.g. SoundEvent.LOUD) is the most recent one heard. (micro:bit V2)"
    ),
    _(
        "microbit.microphone.get_events() \nReturn a tuple of the sound events heard, with the most recent last.\nThis also clears the sound history. (micro:bit V2)"
    ),
    _(
        "microbit.microphone.set_threshold(event, value) \nSet how loud (0 to 255) a sound must be to count as SoundEvent.LOUD,\nor how quiet for SoundEvent.QUIET. (micro:bit V2)"
    ),
    _(
        "microbit.microphone.sound_level() \nReturn how loud the sound is right now, as a number from 0 (quiet) to 255 (loud). (micro:bit V2)"
    ),
    _(
        "microbit.SoundEvent.LOUD \nThe sound event for when the sound changes from quiet to loud, like a clap or a shout. (micro:bit V2)"
    ),
    _(
        "microbit.SoundEvent.QUIET \nThe sound event for when the sound changes from loud to quiet. (micro:bit V2)"
    ),
    # Speaker
    _("microbit.speaker.on() \nTurn the built-in speaker on. (micro:bit V2)"),
    _(
        "microbit.speaker.off() \nTurn the built-in speaker off. Sound still goes to pin0. (micro:bit V2)"
    ),
    # Built-in sounds
    _(
        "microbit.Sound \nThe built-in sounds. Play one with audio.play(Sound.HAPPY). (micro:bit V2)"
    ),
    _(
        "microbit.Sound.GIGGLE \nA built-in sound. Play it with audio.play(Sound.GIGGLE). (micro:bit V2)"
    ),
    _(
        "microbit.Sound.HAPPY \nA built-in sound. Play it with audio.play(Sound.HAPPY). (micro:bit V2)"
    ),
    _(
        "microbit.Sound.HELLO \nA built-in sound. Play it with audio.play(Sound.HELLO). (micro:bit V2)"
    ),
    _(
        "microbit.Sound.MYSTERIOUS \nA built-in sound. Play it with audio.play(Sound.MYSTERIOUS). (micro:bit V2)"
    ),
    _(
        "microbit.Sound.SAD \nA built-in sound. Play it with audio.play(Sound.SAD). (micro:bit V2)"
    ),
    _(
        "microbit.Sound.SLIDE \nA built-in sound. Play it with audio.play(Sound.SLIDE). (micro:bit V2)"
    ),
    _(
        "microbit.Sound.SOARING \nA built-in sound. Play it with audio.play(Sound.SOARING). (micro:bit V2)"
    ),
    _(
        "microbit.Sound.SPRING \nA built-in sound. Play it with audio.play(Sound.SPRING). (micro:bit V2)"
    ),
    _(
        "microbit.Sound.TWINKLE \nA built-in sound. Play it with audio.play(Sound.TWINKLE). (micro:bit V2)"
    ),
    _(
        "microbit.Sound.YAWN \nA built-in sound. Play it with audio.play(Sound.YAWN). (micro:bit V2)"
    ),
    # I2C
    _(
        "microbit.i2c.init(freq=100000, sda=pin20, scl=pin19) \nSet up the I2C bus with the frequency 'freq' and the 'sda' and 'scl' pins."
    ),
    _(
        "microbit.i2c.scan() \nReturn a list of the 7-bit addresses of all the devices connected to the I2C bus."
    ),
    _(
        "microbit.i2c.read(addr, n, repeat=False) \nRead 'n' bytes from the device with the 7-bit address 'addr'.\nIf repeat is True, no stop bit will be sent."
    ),
    _(
        "microbit.i2c.write(addr, buf, repeat=False) \nWrite the bytes in 'buf' to the device with the 7-bit address 'addr'.\nIf repeat is True, no stop bit will be sent."
    ),
    # Image
    _(
        "microbit.Image(string) \nMake a new image from a string of numbers 0 (off) to 9 (brightest), e.g.\nImage('09090:99999:99999:09990:00900') makes a heart. The colon ':' ends a row.\nImage(width, height) makes an empty image."
    ),
    _("microbit.Image.width() \nReturn the number of columns in the image."),
    _("microbit.Image.height() \nReturn the number of rows in the image."),
    _(
        "microbit.Image.get_pixel(x, y) \nReturn the brightness of the pixel at column x and row y, from 0 (off) to 9 (brightest)."
    ),
    _(
        "microbit.Image.set_pixel(x, y, value) \nSet the brightness of the pixel at column x and row y to 'value', from 0 (off) to 9 (brightest).\nThis does not work on the built-in images like Image.HEART."
    ),
    _(
        "microbit.Image.shift_left(n) \nReturn a copy of the image moved 'n' pixels to the left."
    ),
    _(
        "microbit.Image.shift_right(n) \nReturn a copy of the image moved 'n' pixels to the right."
    ),
    _("microbit.Image.shift_up(n) \nReturn a copy of the image moved 'n' pixels up."),
    _(
        "microbit.Image.shift_down(n) \nReturn a copy of the image moved 'n' pixels down."
    ),
    _(
        "microbit.Image.crop(x, y, w, h) \nReturn a cut-out of the image, 'w' pixels wide and 'h' pixels high,\nstarting at column x and row y."
    ),
    _("microbit.Image.copy() \nReturn an exact copy of the image."),
    _(
        "microbit.Image.invert() \nReturn a negative copy of the image: bright pixels become dim and dim pixels become bright."
    ),
    _(
        "microbit.Image.fill(value) \nSet every pixel in the image to brightness 'value', from 0 (off) to 9 (brightest).\nThis does not work on the built-in images like Image.HEART."
    ),
    _(
        "microbit.Image.blit(src, x, y, w, h, xdest=0, ydest=0) \nCopy the area 'w' wide and 'h' high at (x, y) from the image 'src' into this image at (xdest, ydest)."
    ),
    _(
        "microbit.Image.HEART \nA built-in image. Show it with display.show(Image.HEART)."
    ),
    _(
        "microbit.Image.HEART_SMALL \nA built-in image. Show it with display.show(Image.HEART_SMALL)."
    ),
    _(
        "microbit.Image.HAPPY \nA built-in image. Show it with display.show(Image.HAPPY)."
    ),
    _(
        "microbit.Image.SMILE \nA built-in image. Show it with display.show(Image.SMILE)."
    ),
    _("microbit.Image.SAD \nA built-in image. Show it with display.show(Image.SAD)."),
    _(
        "microbit.Image.CONFUSED \nA built-in image. Show it with display.show(Image.CONFUSED)."
    ),
    _(
        "microbit.Image.ANGRY \nA built-in image. Show it with display.show(Image.ANGRY)."
    ),
    _(
        "microbit.Image.ASLEEP \nA built-in image. Show it with display.show(Image.ASLEEP)."
    ),
    _(
        "microbit.Image.SURPRISED \nA built-in image. Show it with display.show(Image.SURPRISED)."
    ),
    _(
        "microbit.Image.SILLY \nA built-in image. Show it with display.show(Image.SILLY)."
    ),
    _(
        "microbit.Image.FABULOUS \nA built-in image. Show it with display.show(Image.FABULOUS)."
    ),
    _("microbit.Image.MEH \nA built-in image. Show it with display.show(Image.MEH)."),
    _("microbit.Image.YES \nA built-in image. Show it with display.show(Image.YES)."),
    _("microbit.Image.NO \nA built-in image. Show it with display.show(Image.NO)."),
    _(
        "microbit.Image.CLOCK12 \nA built-in image. Show it with display.show(Image.CLOCK12)."
    ),
    _(
        "microbit.Image.CLOCK11 \nA built-in image. Show it with display.show(Image.CLOCK11)."
    ),
    _(
        "microbit.Image.CLOCK10 \nA built-in image. Show it with display.show(Image.CLOCK10)."
    ),
    _(
        "microbit.Image.CLOCK9 \nA built-in image. Show it with display.show(Image.CLOCK9)."
    ),
    _(
        "microbit.Image.CLOCK8 \nA built-in image. Show it with display.show(Image.CLOCK8)."
    ),
    _(
        "microbit.Image.CLOCK7 \nA built-in image. Show it with display.show(Image.CLOCK7)."
    ),
    _(
        "microbit.Image.CLOCK6 \nA built-in image. Show it with display.show(Image.CLOCK6)."
    ),
    _(
        "microbit.Image.CLOCK5 \nA built-in image. Show it with display.show(Image.CLOCK5)."
    ),
    _(
        "microbit.Image.CLOCK4 \nA built-in image. Show it with display.show(Image.CLOCK4)."
    ),
    _(
        "microbit.Image.CLOCK3 \nA built-in image. Show it with display.show(Image.CLOCK3)."
    ),
    _(
        "microbit.Image.CLOCK2 \nA built-in image. Show it with display.show(Image.CLOCK2)."
    ),
    _(
        "microbit.Image.CLOCK1 \nA built-in image. Show it with display.show(Image.CLOCK1)."
    ),
    _(
        "microbit.Image.ARROW_N \nA built-in image. Show it with display.show(Image.ARROW_N)."
    ),
    _(
        "microbit.Image.ARROW_NE \nA built-in image. Show it with display.show(Image.ARROW_NE)."
    ),
    _(
        "microbit.Image.ARROW_E \nA built-in image. Show it with display.show(Image.ARROW_E)."
    ),
    _(
        "microbit.Image.ARROW_SE \nA built-in image. Show it with display.show(Image.ARROW_SE)."
    ),
    _(
        "microbit.Image.ARROW_S \nA built-in image. Show it with display.show(Image.ARROW_S)."
    ),
    _(
        "microbit.Image.ARROW_SW \nA built-in image. Show it with display.show(Image.ARROW_SW)."
    ),
    _(
        "microbit.Image.ARROW_W \nA built-in image. Show it with display.show(Image.ARROW_W)."
    ),
    _(
        "microbit.Image.ARROW_NW \nA built-in image. Show it with display.show(Image.ARROW_NW)."
    ),
    _(
        "microbit.Image.TRIANGLE \nA built-in image. Show it with display.show(Image.TRIANGLE)."
    ),
    _(
        "microbit.Image.TRIANGLE_LEFT \nA built-in image. Show it with display.show(Image.TRIANGLE_LEFT)."
    ),
    _(
        "microbit.Image.CHESSBOARD \nA built-in image. Show it with display.show(Image.CHESSBOARD)."
    ),
    _(
        "microbit.Image.DIAMOND \nA built-in image. Show it with display.show(Image.DIAMOND)."
    ),
    _(
        "microbit.Image.DIAMOND_SMALL \nA built-in image. Show it with display.show(Image.DIAMOND_SMALL)."
    ),
    _(
        "microbit.Image.SQUARE \nA built-in image. Show it with display.show(Image.SQUARE)."
    ),
    _(
        "microbit.Image.SQUARE_SMALL \nA built-in image. Show it with display.show(Image.SQUARE_SMALL)."
    ),
    _(
        "microbit.Image.RABBIT \nA built-in image. Show it with display.show(Image.RABBIT)."
    ),
    _("microbit.Image.COW \nA built-in image. Show it with display.show(Image.COW)."),
    _(
        "microbit.Image.MUSIC_CROTCHET \nA built-in image. Show it with display.show(Image.MUSIC_CROTCHET)."
    ),
    _(
        "microbit.Image.MUSIC_QUAVER \nA built-in image. Show it with display.show(Image.MUSIC_QUAVER)."
    ),
    _(
        "microbit.Image.MUSIC_QUAVERS \nA built-in image. Show it with display.show(Image.MUSIC_QUAVERS)."
    ),
    _(
        "microbit.Image.PITCHFORK \nA built-in image. Show it with display.show(Image.PITCHFORK)."
    ),
    _("microbit.Image.XMAS \nA built-in image. Show it with display.show(Image.XMAS)."),
    _(
        "microbit.Image.PACMAN \nA built-in image. Show it with display.show(Image.PACMAN)."
    ),
    _(
        "microbit.Image.TARGET \nA built-in image. Show it with display.show(Image.TARGET)."
    ),
    _(
        "microbit.Image.TSHIRT \nA built-in image. Show it with display.show(Image.TSHIRT)."
    ),
    _(
        "microbit.Image.ROLLERSKATE \nA built-in image. Show it with display.show(Image.ROLLERSKATE)."
    ),
    _("microbit.Image.DUCK \nA built-in image. Show it with display.show(Image.DUCK)."),
    _(
        "microbit.Image.HOUSE \nA built-in image. Show it with display.show(Image.HOUSE)."
    ),
    _(
        "microbit.Image.TORTOISE \nA built-in image. Show it with display.show(Image.TORTOISE)."
    ),
    _(
        "microbit.Image.BUTTERFLY \nA built-in image. Show it with display.show(Image.BUTTERFLY)."
    ),
    _(
        "microbit.Image.STICKFIGURE \nA built-in image. Show it with display.show(Image.STICKFIGURE)."
    ),
    _(
        "microbit.Image.GHOST \nA built-in image. Show it with display.show(Image.GHOST)."
    ),
    _(
        "microbit.Image.SWORD \nA built-in image. Show it with display.show(Image.SWORD)."
    ),
    _(
        "microbit.Image.GIRAFFE \nA built-in image. Show it with display.show(Image.GIRAFFE)."
    ),
    _(
        "microbit.Image.SKULL \nA built-in image. Show it with display.show(Image.SKULL)."
    ),
    _(
        "microbit.Image.UMBRELLA \nA built-in image. Show it with display.show(Image.UMBRELLA)."
    ),
    _(
        "microbit.Image.SNAKE \nA built-in image. Show it with display.show(Image.SNAKE)."
    ),
    _(
        "microbit.Image.SCISSORS \nA built-in image. Show it with display.show(Image.SCISSORS)."
    ),
    _(
        "microbit.Image.ALL_CLOCKS \nA list of the twelve clock images. Show them all with display.show(Image.ALL_CLOCKS)."
    ),
    _(
        "microbit.Image.ALL_ARROWS \nA list of the eight arrow images. Show them all with display.show(Image.ALL_ARROWS)."
    ),
    # uart
    _(
        "microbit.uart.init(baudrate=9600, bits=8, parity=None, stop=1, tx=None, rx=None) \nSet up serial communication. Change the defaults with named arguments,\ne.g. uart.init(baudrate=115200, tx=pin0, rx=pin1). Parity can be None, uart.ODD or uart.EVEN."
    ),
    _(
        "microbit.uart.any() \nReturn True if there is incoming data waiting to be read, else False."
    ),
    _(
        "microbit.uart.read(nbytes=None) \nRead bytes. Use read() to read as much as possible,\nor read(nbytes) to read at most 'nbytes' bytes."
    ),
    _(
        "microbit.uart.readinto(buf, nbytes=None) \nRead bytes into the buffer 'buf'. Use readinto(buf, nbytes) to read at most 'nbytes'."
    ),
    _(
        "microbit.uart.readline() \nRead a line of data, ending with a newline character."
    ),
    _(
        "microbit.uart.write(buf) \nWrite the bytes (or string) in 'buf' to the connected device."
    ),
    # SPI
    _(
        "microbit.spi.init(baudrate=1000000, bits=8, mode=0, sclk=pin13, mosi=pin15, miso=pin14) \nSet up SPI communication. Change the defaults for the speed, mode and pins\nwith named arguments."
    ),
    _(
        "microbit.spi.read(nbytes, out=0) \nRead at most 'nbytes' bytes, while sending the byte 'out' again and again."
    ),
    _(
        "microbit.spi.write(buffer) \nWrite the bytes in 'buffer' to the connected device."
    ),
    _(
        "microbit.spi.write_readinto(out, in_) \nWrite the 'out' buffer to the connected device and read the reply into the 'in_' buffer.\nBoth buffers must be the same length."
    ),
    # Music module
    _(
        "music.set_tempo(ticks=4, bpm=120) \nSet the speed of the music: 'ticks' in a beat, and 'bpm' beats per minute.\nmusic.set_tempo() goes back to the default."
    ),
    _("music.get_tempo() \nReturn the current tempo as a tuple (ticks, bpm)."),
    _(
        "music.play(music, pin=pin0, wait=True, loop=False) \nPlay 'music', a string or a list of notes, e.g. music.play(music.PUNCHLINE).\nSound plays on pin0 (and the speaker on V2). If wait is False the music plays in the\nbackground. If loop is True it repeats forever."
    ),
    _(
        "music.pitch(frequency, duration=-1, pin=pin0, wait=True) \nPlay a note at 'frequency' Hz for 'duration' milliseconds, e.g. pitch(440, 1000)\nplays concert A for 1 second. A negative duration plays the note until stopped."
    ),
    _("music.stop(pin=pin0) \nStop all music playing on the speaker and on the pin."),
    _(
        "music.reset() \nReset the tempo, note length and octave to their default values."
    ),
    _("music.DADADADUM \nA built-in tune. Play it with music.play(music.DADADADUM)."),
    _(
        "music.ENTERTAINER \nA built-in tune. Play it with music.play(music.ENTERTAINER)."
    ),
    _("music.PRELUDE \nA built-in tune. Play it with music.play(music.PRELUDE)."),
    _("music.ODE \nA built-in tune. Play it with music.play(music.ODE)."),
    _("music.NYAN \nA built-in tune. Play it with music.play(music.NYAN)."),
    _("music.RINGTONE \nA built-in tune. Play it with music.play(music.RINGTONE)."),
    _("music.FUNK \nA built-in tune. Play it with music.play(music.FUNK)."),
    _("music.BLUES \nA built-in tune. Play it with music.play(music.BLUES)."),
    _("music.BIRTHDAY \nA built-in tune. Play it with music.play(music.BIRTHDAY)."),
    _("music.WEDDING \nA built-in tune. Play it with music.play(music.WEDDING)."),
    _("music.FUNERAL \nA built-in tune. Play it with music.play(music.FUNERAL)."),
    _("music.PUNCHLINE \nA built-in tune. Play it with music.play(music.PUNCHLINE)."),
    _("music.PYTHON \nA built-in tune. Play it with music.play(music.PYTHON)."),
    _("music.BADDY \nA built-in tune. Play it with music.play(music.BADDY)."),
    _("music.CHASE \nA built-in tune. Play it with music.play(music.CHASE)."),
    _("music.BA_DING \nA built-in tune. Play it with music.play(music.BA_DING)."),
    _("music.WAWAWAWAA \nA built-in tune. Play it with music.play(music.WAWAWAWAA)."),
    _("music.JUMP_UP \nA built-in tune. Play it with music.play(music.JUMP_UP)."),
    _("music.JUMP_DOWN \nA built-in tune. Play it with music.play(music.JUMP_DOWN)."),
    _("music.POWER_UP \nA built-in tune. Play it with music.play(music.POWER_UP)."),
    _("music.POWER_DOWN \nA built-in tune. Play it with music.play(music.POWER_DOWN)."),
    # Antigravity
    _("antigravity \nImport this module and see what happens!"),
    # This module
    _("this.authors() \nReveal the names of the people who made this software."),
    # Love module
    _(
        "love.badaboom() \nHear my soul speak:\nThe very instant that I saw you, did\nMy heart fly to your service."
    ),
    # NeoPixel module
    _(
        "neopixel.NeoPixel(pin, n, bpp=3) \nSet up a strip of 'n' NeoPixels connected to 'pin'. Use bpp=4 for RGBW pixels.\nSet a pixel's colour with np[0] = (255, 0, 128), then call np.show()."
    ),
    _("neopixel.NeoPixel.clear() \nTurn off all the pixels."),
    _(
        "neopixel.NeoPixel.show() \nShow the pixels. You must call this to see any changes."
    ),
    _("neopixel.NeoPixel.write() \nShow the pixels, just like show(). (micro:bit V2)"),
    _(
        "neopixel.NeoPixel.fill(colour) \nSet all the pixels to the same colour, e.g. np.fill((0, 0, 255)).\nCall show() to see the change. (micro:bit V2)"
    ),
    # Radio
    _(
        "radio.on() \nTurn the radio on. The radio is already on when you import the radio module."
    ),
    _("radio.off() \nTurn the radio off, saving power and memory."),
    _(
        "radio.config(length=32, queue=3, channel=7, power=6, address=0x75626974, group=0, data_rate=radio.RATE_1MBIT) \nChange the radio settings with named arguments. 'length' is the biggest message\n(up to 251 bytes), 'queue' how many messages are stored, 'channel' 0-83,\n'power' 0-7, 'group' 0-255. Only micro:bits with the same channel and group can talk."
    ),
    _("radio.reset() \nReset the radio settings to their default values."),
    _("radio.send(message) \nSend a message string."),
    _(
        "radio.receive() \nReceive the next incoming message as a string. Returns None if there are no messages."
    ),
    _("radio.send_bytes(message) \nSend a message made of bytes."),
    _(
        "radio.receive_bytes() \nReceive the next incoming message as bytes. Returns None if there are no messages."
    ),
    _(
        "radio.receive_bytes_into(buffer) \nCopy the next incoming message into 'buffer' and return its length.\nReturns None if there are no messages."
    ),
    _(
        "radio.receive_full() \nReceive the next incoming message as a tuple (message, signal strength, time).\nReturns None if there are no messages."
    ),
    _(
        "radio.RATE_1MBIT \nUse with radio.config(data_rate=...) to send data at 1 Mbit a second (the default)."
    ),
    _(
        "radio.RATE_2MBIT \nUse with radio.config(data_rate=...) to send data at 2 Mbit a second."
    ),
    # Audio
    _(
        "audio.play(source, wait=True, pin=pin0, return_pin=None) \nPlay a built-in Sound, a SoundEffect, or a list of AudioFrames.\nIf wait is False the sound plays in the background. Use pin=None for no sound on the pins."
    ),
    _("audio.is_playing() \nReturn True if a sound is playing, else False."),
    _("audio.stop() \nStop all sound that is playing."),
    _(
        "audio.AudioFrame() \nMake a frame of 32 sound samples, each a number from 0 to 255.\nPlay a list of frames with audio.play()."
    ),
    _(
        "audio.SoundEffect(freq_start=500, freq_end=2500, duration=500, vol_start=255, vol_end=0, waveform=WAVEFORM_SQUARE, fx=FX_NONE, shape=SHAPE_LOG) \nMake your own sound effect: it slides from freq_start to freq_end Hz over 'duration'\nmilliseconds. Play it with audio.play(my_effect). (micro:bit V2)"
    ),
    _("audio.SoundEffect.copy() \nReturn a copy of this sound effect. (micro:bit V2)"),
    _(
        "audio.SoundEffect.WAVEFORM_SINE \nUse as the waveform for a smooth sine wave sound. (micro:bit V2)"
    ),
    _(
        "audio.SoundEffect.WAVEFORM_SAWTOOTH \nUse as the waveform for a sawtooth wave sound. (micro:bit V2)"
    ),
    _(
        "audio.SoundEffect.WAVEFORM_TRIANGLE \nUse as the waveform for a triangle wave sound. (micro:bit V2)"
    ),
    _(
        "audio.SoundEffect.WAVEFORM_SQUARE \nUse as the waveform for a square wave sound (the default). (micro:bit V2)"
    ),
    _(
        "audio.SoundEffect.WAVEFORM_NOISE \nUse as the waveform for random noise. (micro:bit V2)"
    ),
    _(
        "audio.SoundEffect.SHAPE_LINEAR \nUse as the shape to change the frequency at a steady rate. (micro:bit V2)"
    ),
    _(
        "audio.SoundEffect.SHAPE_CURVE \nUse as the shape to change the frequency along a curve. (micro:bit V2)"
    ),
    _(
        "audio.SoundEffect.SHAPE_LOG \nUse as the shape to change the frequency along a logarithmic curve (the default). (micro:bit V2)"
    ),
    _(
        "audio.SoundEffect.FX_NONE \nUse as the fx for no extra effect (the default). (micro:bit V2)"
    ),
    _(
        "audio.SoundEffect.FX_TREMOLO \nUse as the fx to add a tremolo (wobbling volume) effect. (micro:bit V2)"
    ),
    _(
        "audio.SoundEffect.FX_VIBRATO \nUse as the fx to add a vibrato (wobbling pitch) effect. (micro:bit V2)"
    ),
    _(
        "audio.SoundEffect.FX_WARBLE \nUse as the fx to add a warble effect. (micro:bit V2)"
    ),
    # Data logging
    _(
        "log.set_labels(*labels, timestamp=log.SECONDS) \nSet the column headings of the data log, e.g. log.set_labels('temp', 'light').\nThe first column is a timestamp; use timestamp=None to turn it off. (micro:bit V2)"
    ),
    _(
        "log.add(data_dictionary, **kwargs) \nAdd a row of data to the log, e.g. log.add(temp=temperature())\nor log.add({'temp': temperature()}). (micro:bit V2)"
    ),
    _(
        "log.delete(full=False) \nDelete everything in the log, including the headings.\nIf full is True the data is wiped completely, which is slower. (micro:bit V2)"
    ),
    _(
        "log.set_mirroring(serial) \nIf serial is True, every row added to the log is also printed to the serial output (the REPL). (micro:bit V2)"
    ),
    _(
        "log.MILLISECONDS \nUse with log.set_labels(timestamp=...) to timestamp each row in milliseconds. (micro:bit V2)"
    ),
    _(
        "log.SECONDS \nUse with log.set_labels(timestamp=...) to timestamp each row in seconds (the default). (micro:bit V2)"
    ),
    _(
        "log.MINUTES \nUse with log.set_labels(timestamp=...) to timestamp each row in minutes. (micro:bit V2)"
    ),
    _(
        "log.HOURS \nUse with log.set_labels(timestamp=...) to timestamp each row in hours. (micro:bit V2)"
    ),
    _(
        "log.DAYS \nUse with log.set_labels(timestamp=...) to timestamp each row in days. (micro:bit V2)"
    ),
    # Power management
    _(
        "power.off() \nTurn the micro:bit off to save as much power as possible.\nPress the reset button to start your program again from the beginning. (micro:bit V2)"
    ),
    _(
        "power.deep_sleep(ms=None, wake_on=None, run_every=True) \nSleep using very little power, then carry on where you left off.\nWake up after 'ms' milliseconds, or when a pin or button in 'wake_on' is used, e.g. wake_on=button_a. (micro:bit V2)"
    ),
    # Speech
    _(
        "speech.translate(words) \nReturn a string of the phonemes (sounds) for the English 'words'."
    ),
    _(
        "speech.say(words, pitch=64, speed=72, mouth=128, throat=128, pin=pin0) \nSay the English 'words' out loud. Change pitch, speed, mouth and throat\n(each 0 to 255) to change the voice."
    ),
    _(
        "speech.pronounce(phonemes, pitch=64, speed=72, mouth=128, throat=128, pin=pin0) \nSay the 'phonemes' (speech sounds) out loud. Change pitch, speed, mouth and throat\n(each 0 to 255) to change the voice."
    ),
    _(
        "speech.sing(phonemes, pitch=64, speed=72, mouth=128, throat=128, pin=pin0) \nSing the 'phonemes'. Set the pitch of each phoneme with a hash and a number,\nlike this: '#112DOWWWWWWWW'."
    ),
    # Machine
    _(
        "machine.unique_id() \nReturn a byte string that is different for every micro:bit."
    ),
    _("machine.reset() \nRestart the micro:bit, just like pressing the reset button."),
    _("machine.freq() \nReturn the speed of the processor in hertz."),
    _(
        "machine.disable_irq() \nTurn off interrupts and return the previous state.\nPass that state to enable_irq() to turn them back on."
    ),
    _(
        "machine.enable_irq(state) \nTurn interrupts back on, using the 'state' returned by disable_irq()."
    ),
    _(
        "machine.time_pulse_us(pin, pulse_level, timeout_us=1000000) \nTime how long a pulse on 'pin' at 'pulse_level' (0 or 1) lasts, in microseconds.\nReturns a negative number if it takes longer than 'timeout_us'."
    ),
    # Utime
    _(
        "utime.sleep(seconds) \nWait for 'seconds' seconds. You can use a decimal number, like 0.5."
    ),
    _("utime.sleep_ms(ms) \nWait for 'ms' milliseconds."),
    _("utime.sleep_us(us) \nWait for 'us' microseconds."),
    _(
        "utime.ticks_ms() \nReturn a counter that goes up every millisecond.\nUse ticks_diff() to compare two values."
    ),
    _(
        "utime.ticks_us() \nReturn a counter that goes up every microsecond.\nUse ticks_diff() to compare two values."
    ),
    _(
        "utime.ticks_add(ticks, delta) \nReturn the ticks value 'ticks' moved on by 'delta', which can be positive or negative."
    ),
    _(
        "utime.ticks_diff(ticks1, ticks2) \nReturn how much time passed between two ticks values (ticks1 - ticks2),\nsafely handling the counter wrapping around."
    ),
    # Time
    _(
        "time.sleep(seconds) \nWait for 'seconds' seconds. You can use a decimal number, like 0.5."
    ),
    _("time.sleep_ms(ms) \nWait for 'ms' milliseconds."),
    _("time.sleep_us(us) \nWait for 'us' microseconds."),
    _(
        "time.ticks_ms() \nReturn a counter that goes up every millisecond.\nUse ticks_diff() to compare two values."
    ),
    _(
        "time.ticks_us() \nReturn a counter that goes up every microsecond.\nUse ticks_diff() to compare two values."
    ),
    _(
        "time.ticks_add(ticks, delta) \nReturn the ticks value 'ticks' moved on by 'delta', which can be positive or negative."
    ),
    _(
        "time.ticks_diff(ticks1, ticks2) \nReturn how much time passed between two ticks values (ticks1 - ticks2),\nsafely handling the counter wrapping around."
    ),
    # Math functions
    _("math.sqrt(x) \nReturn the square root of 'x'."),
    _("math.pow(x, y) \nReturn 'x' raised to the power 'y'."),
    _("math.exp(x) \nReturn math.e**'x'."),
    _(
        "math.log(x, base=math.e) \nWith one argument, return the natural logarithm of 'x' (to base e).\nWith two arguments, return the logarithm of 'x' to the given 'base'."
    ),
    _("math.cos(x) \nReturn the cosine of 'x' radians."),
    _("math.sin(x) \nReturn the sine of 'x' radians."),
    _("math.tan(x) \nReturn the tangent of 'x' radians."),
    _("math.acos(x) \nReturn the arc cosine of 'x', in radians."),
    _("math.asin(x) \nReturn the arc sine of 'x', in radians."),
    _("math.atan(x) \nReturn the arc tangent of 'x', in radians."),
    _("math.atan2(y, x) \nReturn the arc tangent of y / x, in radians."),
    _(
        "math.ceil(x) \nReturn the ceiling of 'x', the smallest integer greater than or equal to 'x'."
    ),
    _(
        "math.copysign(x, y) \nReturn a float with the magnitude (absolute value) of 'x' but the sign of 'y'."
    ),
    _("math.fabs(x) \nReturn the absolute value of 'x'."),
    _(
        "math.floor(x) \nReturn the floor of 'x', the largest integer less than or equal to 'x'."
    ),
    _("math.fmod(x, y) \nReturn the remainder of 'x' divided by 'y'."),
    _("math.frexp(x) \nReturn the mantissa and exponent of 'x' as the pair (m, e)."),
    _("math.ldexp(x, exp) \nReturn 'x' * (2**'exp')."),
    _(
        "math.modf(x) \nReturn the fractional and integer parts of x.\nBoth results carry the sign of x and are floats."
    ),
    _(
        "math.isfinite(x) \nReturn True if 'x' is neither an infinity nor a NaN, and False otherwise."
    ),
    _(
        "math.isinf(x) \nReturn True if 'x' is a positive or negative infinity, and False otherwise."
    ),
    _(
        "math.isnan(x) \nReturn True if 'x' is a NaN (not a number), and False otherwise."
    ),
    _("math.trunc(x) \nReturn 'x' with the decimal part removed, as an integer."),
    _("math.radians(x) \nConvert angle 'x' from degrees to radians."),
    _("math.degrees(x) \nConvert angle 'x' from radians to degrees."),
    _(
        "math.pi \nThe number pi (3.14159...), the ratio of a circle's circumference to its diameter."
    ),
    _("math.e \nThe number e (2.71828...), the base of natural logarithms."),
]
