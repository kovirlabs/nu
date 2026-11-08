# Copyright & image credits

## Copyright

Nu is a continuation of Mu. Mu, its source code and associated assets are
copyright Nicholas H. Tollervey and others; Nu's additions are copyright the
Nu contributors. Those who have made significant contributions are listed in
the [authors](authors.md). Nu, like Mu, is free software under the
[GNU General Public License v3](license.md).

## Images in these docs

All images in this documentation fall under Nu's (and Mu's) copyright status,
except for the following images sourced from third parties.

### beautifully_useless.jpg

Permission was sought and obtained from Katerina Kamprani (the creator of
[the uncomfortable](http://theuncomfortable.com)):

```
Hello Nicholas, 

Thank you very much for asking and for your kind words. 
As long as there is no commercial use of the image, and since you
mention my project, it is absolutely fine!
I am very happy the images help to prove a point!

Many greetings from Athens, Greece,
Katerina
```

### circuit_playground.jpg

Permission was sought and obtained from
[Adafruit Industries](https://adafruit.com/), the source of the
image:

```
yup! 100%! please use!

> Hi Folks,
>
> Is it OK to use a picture of a Circuit Playground Express taken
> from your website in the developer docs for Mu. Like this..?
>
> https://mu.readthedocs.io/en/latest/modes.html#adafruit-mode
```

### pygame.png

Permission was sought and obtained from René Dudfield, the current core
maintainer of [Pygame](https://pygame.org):

```
public domain

Go for it! Feel free to do whatever weird(and not weird) things you
like with it.

It's a modification (by me) of a logo by Gareth Noyce, who also put
the logo files in public domain.

Gareth Noyce said of the logo files:
They're public domain but I'd like attribution if they're used
anywhere.  Just a "logo by Gareth Noyce" would do, but I won't be
complaining if people forget. :)'
```

### python.png

This is a copy of the Python logo owned by the
[Python Software Foundation](https://python.org/psf)
(PSF). Mu was originally written by a PSF Fellow on behalf of the PSF as part
of the PSF's contribution to the BBC's micro:bit project. Furthermore, the PSF
say of the [use of the Python logo](https://www.python.org/community/logos/)):

    "Projects and companies that use Python are encouraged to incorporate
    the Python logo on their websites, brochures, packaging, and elsewhere
    to indicate suitability for use with Python or implementation in
    Python. Use of the "two snakes" logo element alone, without the
    accompanying wordmark is permitted on the same terms as the combined
    logo.

    In general, we want the logo to be used as widely as possible to
    indicate use of Python or suitability for Python."

### microbit.png

The photograph of a BBC micro:bit (used on [modes](modes.md)) came with Mu's
developer documentation.

## Images in the app and the plugins

Nu's own icons (`mu/resources/images`) and the bundled plugins' icons
(`plugins/<name>/nu_<name>/images`) come from Mu and fall under its copyright
status, with these notes:

* **Plugin icons.** When a mode moved out of the core into a plugin, its
  icons moved with it, unchanged: `pygamezero` and the Play, Images, Fonts,
  Sounds and Music buttons to `plugins/pygamezero`, `circuitpython` and its
  Serial button to `plugins/circuitpython`. The Pygame Zero example game
  assets in `plugins/pygamezero/nu_pygamezero/assets` came with Mu's Pygame
  Zero mode.
* **micro:bit icons.** `microbit.png` and the Flash button
  (`microbit-flash.png`, `microbit-flash.svg`) in `plugins/microbit` are Mu's
  micro:bit mode icons. When Mu's micro:bit mode was removed they stayed
  behind as unused files in `mu/resources/images`; the micro:bit plugin moved
  them in (the Flash icon renamed from `flash`), byte-for-byte identical to
  upstream Mu's, so they carry Mu's copyright and licence, nothing new.
* **The Python logo** (`python.svg`): see python.png above.
* **Nu's own artwork.** The app icon (`icon.png`, and `package/icons` for the
  installers) is Nu's, not Mu's. The splash screens (`splash_screen.png`,
  `splash_fail.png`) and the Mode button (`modes.png`) are drawn from it by
  `utils/make_artwork.py`, replacing Mu's logo artwork.

## Mu's design archive

`docs/icon_brief`, `docs/logo_design` and `docs/swag` hold Mu's original
design material: the brief for Mu's icon set (with screenshots of Mu at the
time), the logo and splash-screen sources, and the contributors' t-shirt
avatars. Nu doesn't use them; they're kept as part of Mu's history, under
Mu's copyright status.
