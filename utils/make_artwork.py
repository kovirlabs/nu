"""
Draw Nu's start-up artwork from the app icon (mu/resources/images/icon.png).

Writes, into mu/resources/images/:

* splash_screen.png: the splash shown while Nu starts;
* splash_fail.png: the splash shown if starting fails (the bottom half is
  left blank for the error text);
* modes.png: the toolbar's Mode button (Nu's logo in the yellow ring).

Run it from the repository root after changing icon.png:

    QT_QPA_PLATFORM=offscreen python utils/make_artwork.py
"""

import os
import sys

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QGuiApplication,
    QImage,
    QPainter,
    QPen,
)

IMAGES = os.path.join("mu", "resources", "images")
FONTS = os.path.join("mu", "resources", "fonts")
TITLE = "Nu: a Python editor"
URL = "github.com/kovirlabs/nu"
RING = QColor("#ffcc33")  # The toolbar buttons' yellow ring.


def font(family, size, bold=False):
    f = QFont(family)
    f.setPixelSize(size)
    f.setBold(bold)
    return f


def blank(width, height):
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor("white"))
    return image


def draw_heading(painter, width, family):
    painter.setPen(QColor("black"))
    painter.setFont(font(family, 46, bold=True))
    painter.drawText(QRectF(0, 25, width, 70), Qt.AlignmentFlag.AlignCenter, TITLE)
    painter.setFont(font(family, 22))
    painter.drawText(QRectF(0, 95, width, 35), Qt.AlignmentFlag.AlignCenter, URL)


def draw_icon(painter, icon, centre_x, top, size, grey=False):
    scaled = icon.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    if grey:
        scaled = scaled.convertToFormat(QImage.Format.Format_Grayscale8)
    painter.drawImage(QPointF(centre_x - scaled.width() / 2, top), scaled)


def splash(icon, family):
    width, height = 800, 600
    image = blank(width, height)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    draw_heading(painter, width, family)
    draw_icon(painter, icon, width / 2, 145, 300)
    painter.setFont(font(family, 24))
    painter.drawText(
        QRectF(0, 455, width, 40),
        Qt.AlignmentFlag.AlignCenter,
        "Starting... (this can take a minute the first time)",
    )
    painter.end()
    return image


def splash_fail(icon, family):
    width, height = 800, 523
    image = blank(width, height)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    draw_heading(painter, width, family)
    draw_icon(painter, icon, width / 2, 140, 150, grey=True)
    painter.setPen(QPen(QColor("#808080"), 1))
    painter.drawLine(0, 307, width, 307)
    painter.end()
    return image


def mode_button(icon):
    size = 256
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    ring = size * 0.075
    painter.setPen(QPen(RING, ring))
    painter.setBrush(QColor("white"))
    painter.drawEllipse(QRectF(ring / 2, ring / 2, size - ring, size - ring))
    draw_icon(painter, icon, size / 2, size * 0.2, int(size * 0.6))
    painter.end()
    return image


def main():
    app = QGuiApplication(sys.argv)  # Fonts and drawing need an application.
    print("Drawing with Qt's {} platform.".format(app.platformName()))
    family = "Source Code Pro"
    font_id = QFontDatabase.addApplicationFont(
        os.path.join(FONTS, "SourceCodePro-Regular.otf")
    )
    QFontDatabase.addApplicationFont(os.path.join(FONTS, "SourceCodePro-Bold.otf"))
    if font_id >= 0:
        family = QFontDatabase.applicationFontFamilies(font_id)[0]
    icon = QImage(os.path.join(IMAGES, "icon.png"))
    if icon.isNull():
        sys.exit("Run this from the repository root (no icon.png found).")
    for name, image in (
        ("splash_screen.png", splash(icon, family)),
        ("splash_fail.png", splash_fail(icon, family)),
        ("modes.png", mode_button(icon)),
    ):
        path = os.path.join(IMAGES, name)
        image.save(path)
        print("Wrote", path)


if __name__ == "__main__":
    main()
