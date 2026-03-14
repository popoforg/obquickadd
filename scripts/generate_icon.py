#!/usr/bin/env python3
"""Generate macOS app icon assets for Obsidian QuickAdd."""

from __future__ import annotations

import subprocess
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPen


ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "assets"
BASE_PNG = ASSETS_DIR / "app_icon_1024.png"
ICONSET_DIR = ASSETS_DIR / "obquickadd.iconset"
ICNS_PATH = ASSETS_DIR / "obquickadd.icns"


def draw_icon(size: int = 1024) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    unit = size / 64.0

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#1f2933"))
    painter.drawRoundedRect(
        QRectF(4 * unit, 4 * unit, 56 * unit, 56 * unit),
        14 * unit,
        14 * unit,
    )

    shard = [
        QPointF(23 * unit, 12 * unit),
        QPointF(39 * unit, 14 * unit),
        QPointF(46 * unit, 26 * unit),
        QPointF(41 * unit, 44 * unit),
        QPointF(24 * unit, 50 * unit),
        QPointF(16 * unit, 38 * unit),
        QPointF(18 * unit, 22 * unit),
    ]
    painter.setBrush(QColor("#7c3aed"))
    painter.drawPolygon(shard)

    painter.setBrush(QColor("#111827"))
    painter.setPen(QPen(QColor("#9f7aea"), 1.2 * unit))
    painter.drawLine(QPointF(27 * unit, 17 * unit), QPointF(33 * unit, 23 * unit))
    painter.drawLine(QPointF(33 * unit, 23 * unit), QPointF(30 * unit, 33 * unit))
    painter.drawLine(QPointF(30 * unit, 33 * unit), QPointF(36 * unit, 40 * unit))

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#22c55e"))
    painter.drawEllipse(QRectF(36 * unit, 36 * unit, 20 * unit, 20 * unit))

    plus_pen = QPen(QColor("white"), 2.4 * unit)
    plus_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(plus_pen)
    painter.drawLine(QPointF(46 * unit, 41 * unit), QPointF(46 * unit, 51 * unit))
    painter.drawLine(QPointF(41 * unit, 46 * unit), QPointF(51 * unit, 46 * unit))

    painter.end()
    return image


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def build_iconset(base_png: Path, iconset_dir: Path) -> None:
    if iconset_dir.exists():
        for file in iconset_dir.glob("*.png"):
            file.unlink()
    else:
        iconset_dir.mkdir(parents=True, exist_ok=True)

    mapping = {
        "icon_16x16.png": 16,
        "icon_16x16@2x.png": 32,
        "icon_32x32.png": 32,
        "icon_32x32@2x.png": 64,
        "icon_128x128.png": 128,
        "icon_128x128@2x.png": 256,
        "icon_256x256.png": 256,
        "icon_256x256@2x.png": 512,
        "icon_512x512.png": 512,
        "icon_512x512@2x.png": 1024,
    }
    for name, size in mapping.items():
        out = iconset_dir / name
        run(["sips", "-z", str(size), str(size), str(base_png), "--out", str(out)])


def main() -> int:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    image = draw_icon(1024)
    if not image.save(str(BASE_PNG)):
        raise RuntimeError(f"Failed to write {BASE_PNG}")

    build_iconset(BASE_PNG, ICONSET_DIR)
    iconutil_result = subprocess.run(
        ["iconutil", "-c", "icns", str(ICONSET_DIR), "-o", str(ICNS_PATH)],
        check=False,
        capture_output=True,
        text=True,
    )
    if iconutil_result.returncode != 0 and not ICNS_PATH.exists():
        raise RuntimeError(
            f"iconutil failed and no existing icns available: {iconutil_result.stderr or iconutil_result.stdout}"
        )
    if iconutil_result.returncode != 0:
        print("iconutil failed, reusing existing icns file.")
    print(f"Generated icon: {ICNS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
