#!/usr/bin/env python3
"""PyQt6 quick add tool for today's Obsidian daily note."""

from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
import re
import time
import os
from ctypes import c_void_p
from datetime import date, datetime
from pathlib import Path
from typing import Any

from PyQt6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QEvent,
    QObject,
    QPointF,
    QPropertyAnimation,
    QParallelAnimationGroup,
    QRect,
    QRectF,
    QSize,
    QSequentialAnimationGroup,
    QTimer,
    Qt,
    QSettings,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QAction,
    QColor,
    QCursor,
    QFont,
    QIcon,
    QKeyEvent,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QShortcut,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
)
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizeGrip,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from pynput import keyboard
except Exception:  # pragma: no cover - optional dependency at runtime
    keyboard = None

if sys.platform == "darwin":
    try:
        import objc
        from AppKit import (
            NSApp,
            NSButton,
            NSColor,
            NSFont,
            NSImage,
            NSViewMinXMargin,
            NSLayoutAttributeRight,
            NSTitlebarAccessoryViewController,
            NSView,
            NSWindowCloseButton,
            NSWindowMiniaturizeButton,
            NSWindowZoomButton,
        )
        from Foundation import NSMakeRect, NSObject
    except Exception:  # pragma: no cover - optional dependency at runtime
        objc = None
else:  # pragma: no cover - platform split
    objc = None

APP_TITLE = "Obsidian QuickAdd"
COMMAND_TEMPLATE = "obsidian daily:append content=__CONTENT__"
SETTINGS_ORG = "ObsidianQuickAdd"
SETTINGS_APP = "QuickAdd"
SETTINGS_HOTKEY_KEY = "hotkey/show_window"
SETTINGS_TASK_HOTKEY_KEY = "hotkey/task_toggle"
SETTINGS_SEND_HOTKEY_KEY = "hotkey/send_content"
SETTINGS_PREFIX_TITLE_KEY = "markdown/prefix_title"
DEFAULT_HOTKEY_QT = "Meta+Shift+O" if sys.platform == "darwin" else "Ctrl+Alt+O"
DEFAULT_HOTKEY_TOKEN = "<cmd>+<shift>+o" if sys.platform == "darwin" else "<ctrl>+<alt>+o"
DEFAULT_TASK_HOTKEY_QT = "Ctrl+L" if sys.platform == "darwin" else "Ctrl+L"
DEFAULT_SEND_HOTKEY_QT = "Ctrl+Return" if sys.platform == "darwin" else "Ctrl+Return"
TASK_UNCHECKED_VISUAL = "⬜️ "
TASK_CHECKED_VISUAL = "✅ "
TASK_UNCHECKED_PREFIXES = ("☐ ", "☐\ufe0e ", "⬜ ", "⬜️ ")
TASK_CHECKED_PREFIXES = ("☑ ", "☑\ufe0e ", "☑️ ", "✅ ")
TASK_MARKDOWN_PREFIXES = ("- [ ] ", "- [x] ", "- [X] ")
MACOS_ACTIVATION_POLICY_ACCESSORY = 1
PATH_FALLBACK_DIRS = [
    "/opt/homebrew/bin",
    "/usr/local/bin",
    str(Path.home() / ".local" / "bin"),
    str(Path.home() / "bin"),
    "/usr/bin",
    "/bin",
    "/usr/sbin",
    "/sbin",
]


def _merge_path_lists(*paths: str) -> str:
    merged: list[str] = []
    for path_value in paths:
        for item in path_value.split(":"):
            item = item.strip()
            if not item:
                continue
            if item not in merged:
                merged.append(item)
    return ":".join(merged)


def build_runtime_path() -> str:
    current_path = os.environ.get("PATH", "")
    fallback_path = ":".join(PATH_FALLBACK_DIRS)

    shell_path = ""
    shell_program = os.environ.get("SHELL") or "/bin/zsh"
    try:
        result = subprocess.run(
            [shell_program, "-lc", "printf %s \"$PATH\""],
            check=False,
            capture_output=True,
            text=True,
            timeout=1.8,
        )
        if result.returncode == 0:
            shell_path = result.stdout.strip()
    except Exception:
        shell_path = ""

    return _merge_path_lists(current_path, fallback_path, shell_path)


def build_app_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#1f2933"))
    painter.drawRoundedRect(4, 4, 56, 56, 14, 14)

    shard = [
        QPointF(23, 12),
        QPointF(39, 14),
        QPointF(46, 26),
        QPointF(41, 44),
        QPointF(24, 50),
        QPointF(16, 38),
        QPointF(18, 22),
    ]
    painter.setBrush(QColor("#7c3aed"))
    painter.drawPolygon(shard)

    painter.setBrush(QColor("#111827"))
    painter.setPen(QPen(QColor("#9f7aea"), 1.2))
    painter.drawLine(QPointF(27, 17), QPointF(33, 23))
    painter.drawLine(QPointF(33, 23), QPointF(30, 33))
    painter.drawLine(QPointF(30, 33), QPointF(36, 40))

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#22c55e"))
    painter.drawEllipse(QRectF(36, 36, 20, 20))

    plus_pen = QPen(QColor("white"), 2.4)
    plus_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(plus_pen)
    painter.drawLine(46, 41, 46, 51)
    painter.drawLine(41, 46, 51, 46)
    painter.end()
    return QIcon(pixmap)


def build_pin_icon(color: QColor) -> QIcon:
    pixmap = QPixmap(18, 18)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.translate(9, 9)
    painter.rotate(-34)
    painter.translate(-9, -9)

    fill_pen = QPen(color, 1.2)
    fill_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    fill_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(fill_pen)
    painter.setBrush(color)

    # Angled pushpin head/body.
    painter.drawRoundedRect(QRectF(3.4, 4.2, 8.4, 3.2), 1.4, 1.4)
    painter.drawRoundedRect(QRectF(7.3, 6.9, 1.6, 5.5), 0.7, 0.7)

    needle_pen = QPen(color, 1.5)
    needle_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(needle_pen)
    painter.drawLine(8, 12, 8, 16)

    painter.end()
    return QIcon(pixmap)


def build_close_icon(color: QColor) -> QIcon:
    pixmap = QPixmap(18, 18)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(color, 2.6)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.drawLine(4, 4, 14, 14)
    painter.drawLine(14, 4, 4, 14)
    painter.end()
    return QIcon(pixmap)


def build_send_icon(color: QColor) -> QIcon:
    pixmap = QPixmap(18, 18)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(color, 1.6)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    # Right-pointing paper-plane outline.
    points = [
        QPointF(15.5, 9.0),
        QPointF(2.6, 3.8),
        QPointF(7.0, 9.0),
        QPointF(2.6, 14.2),
        QPointF(15.5, 9.0),
    ]
    for i in range(len(points) - 1):
        painter.drawLine(points[i], points[i + 1])
    painter.drawLine(QPointF(7.0, 9.0), QPointF(11.2, 9.0))
    painter.end()
    return QIcon(pixmap)


def hotkey_label(sequence: QKeySequence) -> str:
    text = sequence.toString(QKeySequence.SequenceFormat.NativeText).strip()
    return text if text else DEFAULT_HOTKEY_QT


def parse_shortcut_text(text: str) -> QKeySequence:
    normalized = text.strip()
    if not normalized:
        return QKeySequence()

    # On macOS Qt maps Command to Ctrl in key sequence strings.
    normalized = re.sub(r"(?i)\bcmd\b", "Ctrl", normalized)
    normalized = re.sub(r"(?i)\bcommand\b", "Ctrl", normalized)
    normalized = re.sub(r"(?i)\bctrl\b", "Ctrl", normalized)
    normalized = re.sub(r"(?i)\bcontrol\b", "Ctrl", normalized)
    normalized = re.sub(r"(?i)\boption\b", "Alt", normalized)
    normalized = re.sub(r"(?i)\benter\b", "Return", normalized)
    return QKeySequence(normalized)


class ShortcutCaptureEdit(QLineEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sequence = QKeySequence()
        self.setReadOnly(True)

    def set_key_sequence(self, sequence: QKeySequence) -> None:
        self._sequence = sequence
        self.setText(sequence.toString(QKeySequence.SequenceFormat.NativeText))

    def key_sequence(self) -> QKeySequence:
        return self._sequence

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key in (Qt.Key.Key_Tab.value, Qt.Key.Key_Backtab.value):
            super().keyPressEvent(event)
            return

        if key in (Qt.Key.Key_Backspace.value, Qt.Key.Key_Delete.value):
            self.set_key_sequence(QKeySequence())
            event.accept()
            return

        modifier_only_keys = {
            Qt.Key.Key_Control.value,
            Qt.Key.Key_Meta.value,
            Qt.Key.Key_Shift.value,
            Qt.Key.Key_Alt.value,
            Qt.Key.Key_AltGr.value,
            Qt.Key.Key_CapsLock.value,
        }
        if key in modifier_only_keys:
            event.accept()
            return

        modifiers = event.modifiers().value
        sequence = QKeySequence(modifiers | key)
        if not sequence.isEmpty():
            self.set_key_sequence(sequence)
        event.accept()


def key_sequence_to_pynput_token(sequence: QKeySequence) -> str | None:
    if sequence.count() == 0:
        return None

    combo = sequence[0]
    try:
        key = combo.key()
        modifiers = combo.keyboardModifiers()
    except Exception:
        return None

    parts: list[str] = []
    if sys.platform == "darwin":
        # On macOS Qt swaps the semantic names:
        # ControlModifier maps to Command (⌘), MetaModifier maps to Control (⌃).
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            parts.append("<cmd>")
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            parts.append("<ctrl>")
    else:
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            parts.append("<ctrl>")
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            parts.append("<cmd>")
    if modifiers & Qt.KeyboardModifier.AltModifier:
        parts.append("<alt>")
    if modifiers & Qt.KeyboardModifier.ShiftModifier:
        parts.append("<shift>")

    key_token: str | None = None
    if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
        key_token = chr(ord("a") + int(key - Qt.Key.Key_A))
    elif Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
        key_token = chr(ord("0") + int(key - Qt.Key.Key_0))
    elif Qt.Key.Key_F1 <= key <= Qt.Key.Key_F35:
        key_token = f"f{int(key - Qt.Key.Key_F1) + 1}"
    else:
        special_map: dict[Qt.Key, str] = {
            Qt.Key.Key_Space: "space",
            Qt.Key.Key_Tab: "tab",
            Qt.Key.Key_Return: "enter",
            Qt.Key.Key_Enter: "enter",
            Qt.Key.Key_Escape: "esc",
            Qt.Key.Key_Up: "up",
            Qt.Key.Key_Down: "down",
            Qt.Key.Key_Left: "left",
            Qt.Key.Key_Right: "right",
            Qt.Key.Key_Home: "home",
            Qt.Key.Key_End: "end",
            Qt.Key.Key_PageUp: "page_up",
            Qt.Key.Key_PageDown: "page_down",
            Qt.Key.Key_Backspace: "backspace",
            Qt.Key.Key_Delete: "delete",
            Qt.Key.Key_Insert: "insert",
            Qt.Key.Key_Comma: ",",
            Qt.Key.Key_Period: ".",
            Qt.Key.Key_Slash: "/",
            Qt.Key.Key_Semicolon: ";",
            Qt.Key.Key_Apostrophe: "'",
            Qt.Key.Key_BracketLeft: "[",
            Qt.Key.Key_BracketRight: "]",
            Qt.Key.Key_Backslash: "\\",
            Qt.Key.Key_Minus: "-",
            Qt.Key.Key_Equal: "=",
            Qt.Key.Key_QuoteLeft: "`",
        }
        key_token = special_map.get(key)

    if key_token is None:
        return None
    return "+".join(parts + [key_token])


class GlobalHotkeyBridge(QObject):
    activated = pyqtSignal()


class GlobalHotkeyManager:
    def __init__(self, bridge: GlobalHotkeyBridge, hotkey_token: str = DEFAULT_HOTKEY_TOKEN) -> None:
        self.bridge = bridge
        self.listener = None
        self.hotkey_token = hotkey_token
        self._required_modifiers: set[str] = set()
        self._required_key: str | None = None
        self._pressed_modifiers: set[str] = set()
        self._pressed_keys: set[str] = set()
        self._hotkey_active = False

    def _parse_hotkey_token(self, token: str) -> tuple[set[str], str | None]:
        parts = [part.strip().lower() for part in token.split("+") if part.strip()]
        modifiers: set[str] = set()
        key: str | None = None
        for part in parts:
            normalized = part[1:-1] if part.startswith("<") and part.endswith(">") else part
            if normalized in {"cmd", "ctrl", "alt", "shift"}:
                modifiers.add(normalized)
            else:
                key = normalized
        return modifiers, key

    def _normalize_pynput_key(self, key_obj) -> tuple[str | None, bool]:
        if keyboard is None:
            return None, False

        def _key_attr(name: str):
            return getattr(keyboard.Key, name, None)

        modifier_map = {}
        for key_name, normalized in (
            ("cmd", "cmd"),
            ("cmd_l", "cmd"),
            ("cmd_r", "cmd"),
            ("ctrl", "ctrl"),
            ("ctrl_l", "ctrl"),
            ("ctrl_r", "ctrl"),
            ("alt", "alt"),
            ("alt_l", "alt"),
            ("alt_r", "alt"),
            ("alt_gr", "alt"),
            ("shift", "shift"),
            ("shift_l", "shift"),
            ("shift_r", "shift"),
        ):
            key_const = _key_attr(key_name)
            if key_const is not None:
                modifier_map[key_const] = normalized
        if key_obj in modifier_map:
            return modifier_map[key_obj], True

        key_map = {}
        for key_name, normalized in (
            ("enter", "enter"),
            ("space", "space"),
            ("tab", "tab"),
            ("esc", "esc"),
            ("up", "up"),
            ("down", "down"),
            ("left", "left"),
            ("right", "right"),
            ("home", "home"),
            ("end", "end"),
            ("page_up", "page_up"),
            ("page_down", "page_down"),
            ("backspace", "backspace"),
            ("delete", "delete"),
            ("insert", "insert"),
        ):
            key_const = _key_attr(key_name)
            if key_const is not None:
                key_map[key_const] = normalized
        if key_obj in key_map:
            return key_map[key_obj], False

        if isinstance(key_obj, keyboard.KeyCode) and key_obj.char:
            return key_obj.char.lower(), False
        return None, False

    def _hotkey_matches(self) -> bool:
        if self._required_key is None:
            return False
        if not self._required_modifiers.issubset(self._pressed_modifiers):
            return False
        return self._required_key in self._pressed_keys

    def _on_press(self, key_obj) -> None:
        normalized, is_modifier = self._normalize_pynput_key(key_obj)
        if normalized is None:
            return
        if is_modifier:
            self._pressed_modifiers.add(normalized)
        else:
            self._pressed_keys.add(normalized)

        if self._hotkey_matches() and not self._hotkey_active:
            self._hotkey_active = True
            self.bridge.activated.emit()

    def _on_release(self, key_obj) -> None:
        normalized, is_modifier = self._normalize_pynput_key(key_obj)
        if normalized is None:
            return
        if is_modifier:
            self._pressed_modifiers.discard(normalized)
        else:
            self._pressed_keys.discard(normalized)
        self._hotkey_active = self._hotkey_matches()

    def start(self) -> bool:
        if keyboard is None:
            return False

        self._required_modifiers, self._required_key = self._parse_hotkey_token(self.hotkey_token)
        if self._required_key is None:
            return False
        self._pressed_modifiers.clear()
        self._pressed_keys.clear()
        self._hotkey_active = False

        try:
            self.listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
            self.listener.daemon = True
            self.listener.start()
            return True
        except Exception:
            self.listener = None
            return False

    def stop(self) -> None:
        if self.listener is not None:
            try:
                self.listener.stop()
            except Exception:
                pass
            self.listener = None

    def set_hotkey(self, hotkey_token: str) -> bool:
        try:
            self.hotkey_token = hotkey_token
            required_modifiers, required_key = self._parse_hotkey_token(hotkey_token)
            if required_key is None:
                return False
            self._required_modifiers = required_modifiers
            self._required_key = required_key
            self._pressed_modifiers.clear()
            self._pressed_keys.clear()
            self._hotkey_active = False
            # If listener isn't running yet, start it now.
            if self.listener is None:
                return self.start()
            return True
        except Exception:
            return False


if objc is not None:
    class MacTitlebarActions(NSObject):
        def initWithOwner_(self, owner: Any):
            self = objc.super(MacTitlebarActions, self).init()
            if self is None:
                return None
            self.owner = owner
            return self

        def onPin_(self, _sender) -> None:
            self.owner._toggle_pin_from_native_titlebar()

        def onHide_(self, _sender) -> None:
            self.owner.hide()


class ContentTextEdit(QTextEdit):
    submit_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._line_spacing_percent = 150
        self._apply_default_line_spacing()

    def _apply_default_line_spacing(self) -> None:
        cursor = QTextCursor(self.document())
        cursor.select(QTextCursor.SelectionType.Document)
        block_fmt = QTextBlockFormat()
        block_fmt.setLineHeight(
            self._line_spacing_percent,
            QTextBlockFormat.LineHeightTypes.ProportionalHeight.value,
        )
        cursor.mergeBlockFormat(block_fmt)

    def _apply_line_spacing_to_current_block(self) -> None:
        cursor = self.textCursor()
        block = cursor.block()
        if not block.isValid():
            return
        block_cursor = QTextCursor(block)
        block_fmt = QTextBlockFormat(block_cursor.blockFormat())
        block_fmt.setLineHeight(
            self._line_spacing_percent,
            QTextBlockFormat.LineHeightTypes.ProportionalHeight.value,
        )
        block_cursor.setBlockFormat(block_fmt)

    def _continuation_prefix_for_line(self, line_text: str) -> str | None:
        task_match = re.match(r"^(\s*)(?:☐(?:\ufe0e)?|⬜(?:\ufe0f)?|☑(?:[\ufe0e\ufe0f])?|✅)\s+", line_text)
        if task_match:
            return f"{task_match.group(1)}{TASK_UNCHECKED_VISUAL}"

        markdown_task_match = re.match(r"^(\s*)- \[[ xX]\]\s+", line_text)
        if markdown_task_match:
            return f"{markdown_task_match.group(1)}{TASK_UNCHECKED_VISUAL}"

        list_match = re.match(r"^(\s*)(?:•|-|\*|\+)\s+", line_text)
        if list_match:
            return f"{list_match.group(1)}• "
        return None

    def _apply_enter_continuation(self) -> None:
        cursor = self.textCursor()
        current_block = cursor.block()
        previous_block = current_block.previous()
        if not previous_block.isValid():
            return

        prefix = self._continuation_prefix_for_line(previous_block.text())
        if not prefix:
            return

        current_text = current_block.text()
        if current_text.startswith(prefix):
            return

        original_offset = cursor.position() - current_block.position()
        block_cursor = QTextCursor(current_block)
        block_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        block_cursor.insertText(prefix)
        inserted_units = block_cursor.position() - current_block.position()
        cursor.setPosition(current_block.position() + inserted_units + original_offset)
        self.setTextCursor(cursor)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        is_newline = event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        before_cursor = self.textCursor()
        before_pos = before_cursor.position()
        before_block_num = before_cursor.blockNumber()
        super().keyPressEvent(event)
        if is_newline:
            after_cursor = self.textCursor()
            if after_cursor.position() == before_pos and after_cursor.blockNumber() == before_block_num:
                # Fallback when default QTextEdit newline handling does not advance on empty lines.
                after_cursor.insertBlock()
                self.setTextCursor(after_cursor)
            self._apply_enter_continuation()
            # Defer one event-loop tick so default newline insertion completes first.
            QTimer.singleShot(0, self._apply_line_spacing_to_current_block)
        else:
            self._apply_line_spacing_to_current_block()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._toggle_task_checkbox(event):
            event.accept()
            return
        super().mousePressEvent(event)

    def _toggle_task_checkbox(self, event: QMouseEvent) -> bool:
        pos = event.position().toPoint()
        cursor = self.cursorForPosition(pos)
        block = cursor.block()
        text = block.text()
        is_markdown_task = text.startswith("- [ ] ") or text.startswith("- [x] ") or text.startswith("- [X] ")
        is_unicode_task = text.startswith(TASK_UNCHECKED_PREFIXES + TASK_CHECKED_PREFIXES)
        if not (is_markdown_task or is_unicode_task):
            return False

        block_start_rect = self.cursorRect(QTextCursor(block))
        if pos.x() > block_start_rect.x() + 52:
            return False

        marker_cursor = QTextCursor(block)
        marker_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        if is_markdown_task:
            marker_cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 6)
            marker_cursor.insertText("- [ ] " if text.startswith("- [x] ") or text.startswith("- [X] ") else "- [x] ")
        else:
            task_prefix = next(
                (prefix for prefix in (TASK_UNCHECKED_PREFIXES + TASK_CHECKED_PREFIXES) if text.startswith(prefix)),
                None,
            )
            if task_prefix is None:
                return False
            toggled_prefix = TASK_CHECKED_VISUAL if task_prefix in TASK_UNCHECKED_PREFIXES else TASK_UNCHECKED_VISUAL
            updated_line = f"{toggled_prefix}{text[len(task_prefix):]}"
            line_cursor = QTextCursor(block)
            line_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            line_cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
            line_cursor.insertText(updated_line)
        self._apply_line_spacing_to_current_block()
        return True


class TitleBar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._drag_offset: tuple[int, int] | None = None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            window = self.window()
            window_pos = window.frameGeometry().topLeft()
            global_pos = event.globalPosition().toPoint()
            self._drag_offset = (global_pos.x() - window_pos.x(), global_pos.y() - window_pos.y())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            global_pos = event.globalPosition().toPoint()
            offset_x, offset_y = self._drag_offset
            self.window().move(global_pos.x() - offset_x, global_pos.y() - offset_y)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class QuickAddWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self._is_pinned = False
        self._suspend_auto_hide = False
        self._suspend_auto_hide_for_emoji = False
        self._settings_dialog_open = False
        self._show_shortcut_cooldown_until = 0.0
        self._markdown_prefix_title = ""
        self._last_position: tuple[int, int] | None = None
        self._base_window_flags = Qt.WindowType.Window
        self._native_controls_ready = False
        self._native_titlebar_actions: Any = None
        self._native_accessory: Any = None
        self._native_pin_button: Any = None
        self._native_window_ref: Any = None
        self.setWindowTitle(APP_TITLE)
        self.setObjectName("quickAddRoot")
        self.resize(440, 280)
        self.setMinimumSize(360, 220)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._apply_window_flags()
        self.setStyleSheet(
            """
            QWidget#quickAddRoot {
                background: #f6f8f7;
                border: none;
            }
            QWidget#panel {
                background: transparent;
                border: none;
            }
            QWidget#titleBar {
                background: transparent;
                border: 0;
                border-bottom: 1px solid #d9dfdc;
            }
            QLabel#titleLabel {
                color: #183623;
                font-size: 22px;
                font-weight: 600;
            }
            QPushButton#pinButton, QPushButton#closeButton {
                background: transparent;
                border: none;
                border-radius: 8px;
                font-weight: 600;
                padding: 0;
                margin: 0;
            }
            QPushButton#pinButton:hover, QPushButton#closeButton:hover {
                background: #dce5e0;
            }
            QPushButton#pinButton {
                min-width: 24px;
                max-width: 24px;
                min-height: 24px;
                max-height: 24px;
            }
            QPushButton#pinButton:checked {
                color: #1f8b3a;
            }
            QPushButton#closeButton {
                min-width: 24px;
                max-width: 24px;
                min-height: 24px;
                max-height: 24px;
            }
            QTextEdit#contentText {
                background: transparent;
                border: none;
                border-radius: 0;
                font-size: 15px;
                padding: 12px;
            }
            QPushButton#sendButton {
                background: #1f5f2e;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
                padding: 3px 10px;
            }
            QPushButton#sendButton:hover {
                background: #174824;
            }
            QPushButton#sendButton:disabled {
                background: #b8bfbb;
                color: #f3f5f4;
            }
            QPushButton#formatButton {
                background: transparent;
                color: #4f5d56;
                border: none;
                border-radius: 7px;
                font-size: 12px;
                font-weight: 600;
                padding: 0 6px;
            }
            QPushButton#formatButton:hover {
                background: #e9eeeb;
            }
            QWidget#actionBar {
                background: transparent;
                border: 0;
                border-top: 1px solid #d9dfdc;
            }
            QLabel#successToast {
                background: rgba(31, 95, 46, 238);
                color: white;
                border: 1px solid rgba(20, 66, 32, 240);
                border-radius: 16px;
                font-size: 13px;
                font-weight: 600;
                padding: 6px 14px;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.panel = QWidget(self)
        self.panel.setObjectName("panel")
        layout.addWidget(self.panel)

        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        self.title_bar = TitleBar(self.panel)
        self.title_bar.setObjectName("titleBar")
        self.title_bar.setFixedHeight(38)
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(10, 5, 10, 5)
        title_layout.setSpacing(6)

        self.title_label = QLabel(APP_TITLE, self.title_bar)
        self.title_label.setObjectName("titleLabel")
        title_layout.addWidget(self.title_label)
        title_layout.addStretch(1)

        self.pin_icon_off = build_pin_icon(QColor("#98a19d"))
        self.pin_icon_on = build_pin_icon(QColor("#1f8b3a"))
        self.close_icon = build_close_icon(QColor("#6f7b75"))
        self.send_icon = build_send_icon(QColor("white"))
        self.pin_button = QPushButton("置顶", self.title_bar)
        self.pin_button.setObjectName("pinButton")
        self.pin_button.setCheckable(True)
        self.pin_button.setChecked(False)
        self.pin_button.setText("")
        self.pin_button.setIcon(self.pin_icon_off)
        self.pin_button.setIconSize(QSize(13, 13))
        self.pin_button.setToolTip("置顶窗口")
        self.pin_button.setFixedSize(24, 24)
        self.pin_button.toggled.connect(self._toggle_pin)
        title_layout.addWidget(self.pin_button)

        self.close_button = QPushButton("", self.title_bar)
        self.close_button.setObjectName("closeButton")
        self.close_button.setIcon(self.close_icon)
        self.close_button.setIconSize(QSize(16, 16))
        self.close_button.setToolTip("隐藏窗口")
        self.close_button.setFixedSize(24, 24)
        self.close_button.clicked.connect(self.hide)
        title_layout.addWidget(self.close_button)

        panel_layout.addWidget(self.title_bar)
        if sys.platform == "darwin":
            self.title_bar.hide()
            self.title_bar.setFixedHeight(0)

        self.content_text = ContentTextEdit(self.panel)
        self.content_text.setObjectName("contentText")
        self.content_text.setPlaceholderText("现在的想法是...")
        self.content_text.textChanged.connect(self._update_send_button_state)
        panel_layout.addWidget(self.content_text, 1)

        self.action_bar = QWidget(self.panel)
        self.action_bar.setObjectName("actionBar")
        self.action_bar.setFixedHeight(44)
        action_layout = QHBoxLayout(self.action_bar)
        action_layout.setContentsMargins(10, 6, 10, 6)
        action_layout.setSpacing(8)

        self.emoji_button = self._build_format_button("☺︎", "打开 Emoji 选择器", self._open_emoji_picker)
        action_layout.addWidget(self.emoji_button)

        self.h_button = self._build_format_button("H", "标题", self._format_heading)
        action_layout.addWidget(self.h_button)
        self.bold_button = self._build_format_button("B", "加粗", self._format_bold)
        action_layout.addWidget(self.bold_button)
        self.italic_button = self._build_format_button("I", "斜体", self._format_italic)
        action_layout.addWidget(self.italic_button)
        self.code_button = self._build_format_button("</>", "行内代码", self._format_code)
        action_layout.addWidget(self.code_button)
        self.list_button = self._build_format_button("•", "无序列表", self._format_list)
        action_layout.addWidget(self.list_button)
        self.task_button = self._build_format_button("☑︎", "任务列表", self._format_task)
        task_font = self.task_button.font()
        task_font.setPointSize(max(task_font.pointSize() + 3, 15))
        self.task_button.setFont(task_font)
        action_layout.addWidget(self.task_button)
        self.quote_button = self._build_format_button("❝", "引用", self._format_quote)
        action_layout.addWidget(self.quote_button)

        action_layout.addStretch(1)

        self.send_button = QPushButton("", self.action_bar)
        self.send_button.setObjectName("sendButton")
        self.send_button.setFixedSize(64, 28)
        self.send_button.setIcon(self.send_icon)
        self.send_button.setIconSize(QSize(14, 14))
        self.send_button.clicked.connect(self.send_content)
        action_layout.addWidget(self.send_button)

        self.size_grip = QSizeGrip(self.action_bar)
        self.size_grip.setToolTip("拖拽调整窗口大小")
        action_layout.addWidget(self.size_grip, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)

        panel_layout.addWidget(self.action_bar)
        self._update_send_button_state()

        self.local_shortcut = QShortcut(QKeySequence(DEFAULT_HOTKEY_QT), self)
        self.local_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.local_shortcut.activated.connect(self.handle_show_shortcut)

        self.task_shortcut = QShortcut(QKeySequence(DEFAULT_TASK_HOTKEY_QT), self)
        self.task_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.task_shortcut.activated.connect(self._format_task)

        self.send_shortcut = QShortcut(QKeySequence(DEFAULT_SEND_HOTKEY_QT), self)
        self.send_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.send_shortcut.activated.connect(self.send_content)

        self.success_tip = QLabel("发送成功", self)
        self.success_tip.setObjectName("successToast")
        self.success_tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.success_tip.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.success_tip.hide()

        self.success_tip_opacity = QGraphicsOpacityEffect(self.success_tip)
        self.success_tip_opacity.setOpacity(0.0)
        self.success_tip.setGraphicsEffect(self.success_tip_opacity)
        self.success_tip_animation: QSequentialAnimationGroup | None = None

    def set_show_window_shortcut(self, sequence: QKeySequence) -> None:
        if sequence.isEmpty():
            return
        self.local_shortcut.setKey(sequence)

    def show_window_shortcut(self) -> QKeySequence:
        return self.local_shortcut.key()

    def set_task_shortcut(self, sequence: QKeySequence) -> None:
        if sequence.isEmpty():
            return
        self.task_shortcut.setKey(sequence)

    def task_shortcut_sequence(self) -> QKeySequence:
        return self.task_shortcut.key()

    def set_send_shortcut(self, sequence: QKeySequence) -> None:
        if sequence.isEmpty():
            return
        self.send_shortcut.setKey(sequence)

    def send_shortcut_sequence(self) -> QKeySequence:
        return self.send_shortcut.key()

    def set_markdown_prefix_title(self, title: str) -> None:
        self._markdown_prefix_title = title.strip()

    def markdown_prefix_title(self) -> str:
        return self._markdown_prefix_title

    def set_settings_dialog_open(self, opened: bool) -> None:
        self._settings_dialog_open = opened

    def set_shortcuts_enabled(self, enabled: bool) -> None:
        self.local_shortcut.setEnabled(enabled)
        self.task_shortcut.setEnabled(enabled)
        self.send_shortcut.setEnabled(enabled)

    def handle_show_shortcut(self) -> None:
        now = time.monotonic()
        if now < self._show_shortcut_cooldown_until:
            return
        self._show_shortcut_cooldown_until = now + 0.28

        if self._settings_dialog_open:
            self.show_window()
            return
        if self.isVisible():
            self.hide()
        else:
            self.show_window()

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.Type.WindowActivate and self._suspend_auto_hide_for_emoji:
            self._suspend_auto_hide_for_emoji = False
        if (
            event.type() == QEvent.Type.WindowDeactivate
            and self.isVisible()
            and not self._is_pinned
            and not self._suspend_auto_hide
            and not self._suspend_auto_hide_for_emoji
        ):
            QTimer.singleShot(0, self.hide)
        return super().event(event)

    def moveEvent(self, event) -> None:
        pos = self.pos()
        self._last_position = (pos.x(), pos.y())
        super().moveEvent(event)

    def _move_to_center(self) -> None:
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen is not None:
            geometry = screen.availableGeometry()
            x = geometry.x() + (geometry.width() - self.width()) // 2
            y = geometry.y() + (geometry.height() - self.height()) // 2
            self.move(x, y)

    def show_window(self) -> None:
        # Avoid immediate auto-hide when opened from global shortcut.
        self._suspend_auto_hide = True
        if self._last_position is None:
            self._move_to_center()
        else:
            self.move(*self._last_position)

        self.show()
        self._setup_native_titlebar_controls()
        if sys.platform == "darwin":
            QTimer.singleShot(0, self._hide_native_traffic_lights)
            QTimer.singleShot(0, self._setup_native_titlebar_controls)
            QTimer.singleShot(80, self._hide_native_traffic_lights)
            QTimer.singleShot(80, self._setup_native_titlebar_controls)
            QTimer.singleShot(180, self._hide_native_traffic_lights)
            QTimer.singleShot(180, self._setup_native_titlebar_controls)
        self.raise_()
        self.activateWindow()
        self.content_text.setFocus()
        QTimer.singleShot(350, self._resume_auto_hide)

    def show_centered(self) -> None:
        self.show_window()

    def _apply_window_flags(self) -> None:
        flags = self._base_window_flags
        if self._is_pinned:
            flags |= Qt.WindowType.WindowStaysOnTopHint

        if self.windowHandle() is not None:
            self._suspend_auto_hide = True
            self.windowHandle().setFlag(Qt.WindowType.WindowStaysOnTopHint, self._is_pinned)
            self._hide_native_traffic_lights()
            QTimer.singleShot(0, self._setup_native_titlebar_controls)
            QTimer.singleShot(80, self._hide_native_traffic_lights)
            QTimer.singleShot(150, self._setup_native_titlebar_controls)
            if self.isVisible():
                self.raise_()
                self.activateWindow()
            QTimer.singleShot(120, self._resume_auto_hide)
            return

        self.setWindowFlags(flags)

    def _resume_auto_hide(self) -> None:
        self._suspend_auto_hide = False

    def _get_native_window(self):
        # Prefer resolving NSWindow from this Qt window's native handle.
        try:
            native_view = objc.objc_object(c_void_p=int(self.winId()))
            if native_view is not None:
                ns_window = native_view.window()
                if ns_window is not None:
                    return ns_window
        except Exception:
            pass

        app = NSApp() if NSApp is not None else None
        ns_window = app.keyWindow() if app is not None else None
        if ns_window is None and app is not None:
            windows = app.windows()
            if windows:
                ns_window = windows[0]
        return ns_window

    def _hide_native_traffic_lights(self, ns_window=None) -> None:
        if sys.platform != "darwin" or objc is None:
            return
        if ns_window is None:
            ns_window = self._get_native_window()
        if ns_window is None:
            return
        for button_type in (NSWindowCloseButton, NSWindowMiniaturizeButton, NSWindowZoomButton):
            button = ns_window.standardWindowButton_(button_type)
            if button is not None:
                button.setHidden_(True)

    def _setup_native_titlebar_controls(self) -> None:
        if sys.platform != "darwin" or objc is None:
            return

        ns_window = self._get_native_window()
        if ns_window is None:
            return

        self._hide_native_traffic_lights(ns_window)
        if self._native_controls_ready and self._native_window_ref is ns_window:
            self._update_native_pin_state()
            return

        self._native_controls_ready = False
        self._native_accessory = None
        self._native_pin_button = None
        self._native_window_ref = ns_window

        self._native_titlebar_actions = MacTitlebarActions.alloc().initWithOwner_(self)

        button_size = 24
        button_gap = 2
        right_padding = 4
        pin_x = 6
        container_width = button_size * 2 + button_gap + right_padding

        pin_button = NSButton.alloc().initWithFrame_(NSMakeRect(pin_x, 0, button_size, button_size))
        pin_button.setBordered_(False)
        pin_button.setTarget_(self._native_titlebar_actions)
        pin_button.setAction_("onPin:")

        close_x = button_size + button_gap - 2
        close_button = NSButton.alloc().initWithFrame_(NSMakeRect(close_x, 0, button_size, button_size))
        close_button.setBordered_(False)
        close_button.setTarget_(self._native_titlebar_actions)
        close_button.setAction_("onHide:")

        pin_image = NSImage.imageWithSystemSymbolName_accessibilityDescription_("pin.fill", None)
        if pin_image is not None:
            pin_button.setImage_(pin_image)
        else:
            pin_button.setTitle_("📌")

        close_button.setTitle_("✕")
        if NSFont is not None:
            close_button.setFont_(NSFont.boldSystemFontOfSize_(16))

        if hasattr(pin_button, "setContentTintColor_"):
            pin_button.setContentTintColor_(NSColor.systemGrayColor())
        if hasattr(close_button, "setContentTintColor_"):
            close_button.setContentTintColor_(NSColor.systemGrayColor())

        container = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, container_width, button_size))
        container.addSubview_(pin_button)
        container.addSubview_(close_button)

        attached = False
        try:
            accessory = NSTitlebarAccessoryViewController.alloc().init()
            accessory.setLayoutAttribute_(NSLayoutAttributeRight)
            accessory.setView_(container)
            ns_window.addTitlebarAccessoryViewController_(accessory)
            self._native_accessory = accessory
            attached = True
        except Exception:
            close_std = ns_window.standardWindowButton_(NSWindowCloseButton)
            titlebar_view = close_std.superview() if close_std is not None else None
            if titlebar_view is not None:
                frame = titlebar_view.frame()
                y = max(0, (frame.size.height - button_size) / 2)
                container.setFrame_(NSMakeRect(frame.size.width - container_width - 4, y, container_width, button_size))
                container.setAutoresizingMask_(NSViewMinXMargin)
                titlebar_view.addSubview_(container)
                self._native_accessory = container
                attached = True

        if not attached:
            return

        self._native_pin_button = pin_button
        self._native_controls_ready = True
        self._update_native_pin_state()

    def _update_native_pin_state(self) -> None:
        if self._native_pin_button is None or objc is None:
            return
        if hasattr(self._native_pin_button, "setContentTintColor_"):
            color = NSColor.systemGreenColor() if self._is_pinned else NSColor.systemGrayColor()
            self._native_pin_button.setContentTintColor_(color)

    def _toggle_pin_from_native_titlebar(self) -> None:
        self._is_pinned = not self._is_pinned
        self.pin_button.blockSignals(True)
        self.pin_button.setChecked(self._is_pinned)
        self.pin_button.blockSignals(False)
        self.pin_button.setIcon(self.pin_icon_on if self._is_pinned else self.pin_icon_off)
        self._apply_window_flags()
        self._update_native_pin_state()

    def _build_command(self, content: str) -> list[str]:
        if "__CONTENT__" not in COMMAND_TEMPLATE:
            raise ValueError("Invalid command template: missing __CONTENT__")

        template = COMMAND_TEMPLATE.replace("__TODAY__", date.today().isoformat())
        args = shlex.split(template)
        return [arg.replace("__CONTENT__", content) for arg in args]

    def _normalize_markdown_output(self, text: str) -> str:
        # QTextEdit.toMarkdown() may escape markdown control chars (e.g. \- \[x\]).
        return re.sub(r"\\([\\`*_{}\[\]()#+\-.!>])", r"\1", text)

    def _visual_tasks_to_markdown(self, text: str) -> str:
        text = re.sub(r"(?m)^(\s*)(?:☐(?:\ufe0e)?|⬜(?:\ufe0f)?)\s+", r"\1- [ ] ", text)
        text = re.sub(r"(?m)^(\s*)(?:☑(?:[\ufe0e\ufe0f])?|✅)\s+", r"\1- [x] ", text)
        text = re.sub(r"(?m)^(\s*)•\s+", r"\1- ", text)
        return text

    def _update_send_button_state(self) -> None:
        content = self.content_text.toPlainText().strip()
        self.send_button.setEnabled(bool(content))

    def _build_format_button(self, label: str, tip: str, callback) -> QPushButton:
        button = QPushButton(label, self.action_bar)
        button.setObjectName("formatButton")
        button.setFixedSize(30, 28)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setToolTip(tip)
        button.clicked.connect(callback)
        return button

    def _apply_inline_format(self, fmt: QTextCharFormat) -> None:
        self.content_text.setFocus()
        cursor = self.content_text.textCursor()
        if cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
        self.content_text.mergeCurrentCharFormat(fmt)
        self.content_text.setFocus()

    def _prefix_selection_lines(self, prefix: str) -> None:
        self.content_text.setFocus()
        cursor = self.content_text.textCursor()
        had_selection = cursor.hasSelection()
        if not had_selection:
            block = cursor.block()
            block_text = block.text()
            if block_text.startswith(prefix):
                return
            original_offset = cursor.position() - block.position()
            block_cursor = QTextCursor(block)
            block_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            block_cursor.insertText(prefix)
            # Keep caret after inserted prefix on the same line.
            inserted_units = block_cursor.position() - block.position()
            cursor.setPosition(block.position() + inserted_units + original_offset)
            self.content_text.setTextCursor(cursor)
            return

        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        start_cursor = QTextCursor(self.content_text.document())
        start_cursor.setPosition(start)
        start_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)

        end_cursor = QTextCursor(self.content_text.document())
        end_cursor.setPosition(end)
        end_cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
        end_limit = end_cursor.position()

        start_cursor.beginEditBlock()
        while True:
            block = start_cursor.block()
            text = block.text()
            if not text.startswith(prefix):
                block_cursor = QTextCursor(block)
                block_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                block_cursor.insertText(prefix)

            block_end = block.position() + block.length() - 1
            if block_end >= end_limit:
                break
            if not start_cursor.movePosition(QTextCursor.MoveOperation.NextBlock):
                break
        start_cursor.endEditBlock()

    def _format_heading(self) -> None:
        self.content_text.setFocus()
        cursor = self.content_text.textCursor()
        if cursor.hasSelection():
            start = cursor.selectionStart()
            end = cursor.selectionEnd()
        else:
            start = cursor.position()
            end = cursor.position()

        iter_cursor = QTextCursor(self.content_text.document())
        iter_cursor.setPosition(start)
        iter_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)

        while True:
            block_cursor = QTextCursor(iter_cursor.block())
            block_fmt = QTextBlockFormat(block_cursor.blockFormat())
            current_level = block_fmt.headingLevel()
            target_level = 0 if current_level > 0 else 1
            block_fmt.setHeadingLevel(target_level)
            block_cursor.setBlockFormat(block_fmt)

            # Keep heading visually distinct in editor while preserving markdown heading semantics.
            block_cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            char_fmt = QTextCharFormat()
            if target_level > 0:
                char_fmt.setFontWeight(QFont.Weight.Bold)
                char_fmt.setFontPointSize(20)
            else:
                char_fmt.setFontWeight(QFont.Weight.Normal)
                char_fmt.setFontPointSize(0)
            block_cursor.mergeCharFormat(char_fmt)

            block_end = iter_cursor.block().position() + iter_cursor.block().length() - 1
            if block_end >= end:
                break
            if not iter_cursor.movePosition(QTextCursor.MoveOperation.NextBlock):
                break

    def _format_bold(self) -> None:
        cursor = self.content_text.textCursor()
        current = cursor.charFormat().fontWeight()
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Weight.Normal if current > QFont.Weight.Normal else QFont.Weight.Bold)
        self._apply_inline_format(fmt)

    def _format_italic(self) -> None:
        cursor = self.content_text.textCursor()
        fmt = QTextCharFormat()
        fmt.setFontItalic(not cursor.charFormat().fontItalic())
        self._apply_inline_format(fmt)

    def _format_code(self) -> None:
        self.content_text.setFocus()
        cursor = self.content_text.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
            if not cursor.hasSelection():
                cursor.insertText("code")
                cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor, 4)
                self.content_text.setTextCursor(cursor)
        current_families = cursor.charFormat().fontFamilies() or []
        is_code = any("Menlo" in family or "Monaco" in family or "Courier" in family for family in current_families)
        fmt = QTextCharFormat()
        if is_code:
            fmt.setFontFamilies([])
            fmt.clearBackground()
        else:
            fmt.setFontFamilies(["Menlo", "Monaco", "Courier New", "monospace"])
            fmt.setBackground(QColor("#e9efec"))
        self._apply_inline_format(fmt)

    def _format_list(self) -> None:
        self._prefix_selection_lines("• ")

    def _format_task(self) -> None:
        self.content_text.setFocus()
        cursor = self.content_text.textCursor()
        block = cursor.block()
        if not block.isValid():
            return

        text = block.text()
        all_prefixes = TASK_UNCHECKED_PREFIXES + TASK_CHECKED_PREFIXES + TASK_MARKDOWN_PREFIXES
        existing_prefix = next((prefix for prefix in all_prefixes if text.startswith(prefix)), None)
        updated_line = text[len(existing_prefix):] if existing_prefix else f"{TASK_UNCHECKED_VISUAL}{text}"

        line_cursor = QTextCursor(block)
        line_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        line_cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
        line_cursor.insertText(updated_line)
        self.content_text.setTextCursor(line_cursor)
        self.content_text._apply_line_spacing_to_current_block()

    def _format_quote(self) -> None:
        self.content_text.setFocus()
        cursor = self.content_text.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
        cursor.beginEditBlock()
        block_fmt = QTextBlockFormat(cursor.blockFormat())
        block_fmt.setLeftMargin(18)
        block_fmt.setTopMargin(2)
        block_fmt.setBottomMargin(2)
        block_fmt.setBackground(QColor("#eef3f0"))
        cursor.setBlockFormat(block_fmt)
        char_fmt = QTextCharFormat()
        char_fmt.setForeground(QColor("#4f5d56"))
        char_fmt.setFontItalic(True)
        cursor.mergeCharFormat(char_fmt)
        cursor.endEditBlock()
        self.content_text.setTextCursor(cursor)

    def _toggle_pin(self, checked: bool) -> None:
        self._is_pinned = checked
        self.pin_button.setIcon(self.pin_icon_on if checked else self.pin_icon_off)
        self._apply_window_flags()
        self._update_native_pin_state()

    def _open_emoji_picker(self) -> None:
        self._suspend_auto_hide_for_emoji = True
        QTimer.singleShot(15000, self._release_emoji_auto_hide_guard)
        self.show_window()
        self.content_text.setFocus()
        if sys.platform == "darwin" and objc is not None:
            try:
                app = NSApp() if NSApp is not None else None
                if app is not None:
                    app.orderFrontCharacterPalette_(None)
                    return
            except Exception:
                pass
            try:
                subprocess.run(
                    [
                        "osascript",
                        "-e",
                        'tell application "System Events" to keystroke " " using {command down, control down}',
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
            except Exception:
                pass

    def _release_emoji_auto_hide_guard(self) -> None:
        self._suspend_auto_hide_for_emoji = False

    def _success_tip_rect(self, y: int) -> QRect:
        self.success_tip.adjustSize()
        width = max(self.success_tip.sizeHint().width() + 24, 96)
        height = max(self.success_tip.sizeHint().height() + 10, 34)
        x = (self.width() - width) // 2
        return QRect(x, y, width, height)

    def _show_success_tip(self) -> None:
        visible_y = 14
        start_rect = self._success_tip_rect(-48)
        visible_rect = self._success_tip_rect(visible_y)
        end_rect = self._success_tip_rect(visible_y - 16)

        if self.success_tip_animation is not None:
            if self.success_tip_animation.state() != QAbstractAnimation.State.Stopped:
                self.success_tip_animation.stop()
            self.success_tip_animation.deleteLater()

        self.success_tip.setGeometry(start_rect)
        self.success_tip_opacity.setOpacity(0.0)
        self.success_tip.show()
        self.success_tip.raise_()

        enter_move = QPropertyAnimation(self.success_tip, b"geometry", self)
        enter_move.setDuration(260)
        enter_move.setStartValue(start_rect)
        enter_move.setEndValue(visible_rect)
        enter_move.setEasingCurve(QEasingCurve.Type.OutCubic)

        enter_opacity = QPropertyAnimation(self.success_tip_opacity, b"opacity", self)
        enter_opacity.setDuration(260)
        enter_opacity.setStartValue(0.0)
        enter_opacity.setEndValue(1.0)

        enter_group = QParallelAnimationGroup(self)
        enter_group.addAnimation(enter_move)
        enter_group.addAnimation(enter_opacity)

        exit_move = QPropertyAnimation(self.success_tip, b"geometry", self)
        exit_move.setDuration(280)
        exit_move.setStartValue(visible_rect)
        exit_move.setEndValue(end_rect)
        exit_move.setEasingCurve(QEasingCurve.Type.InCubic)

        exit_opacity = QPropertyAnimation(self.success_tip_opacity, b"opacity", self)
        exit_opacity.setDuration(280)
        exit_opacity.setStartValue(1.0)
        exit_opacity.setEndValue(0.0)

        exit_group = QParallelAnimationGroup(self)
        exit_group.addAnimation(exit_move)
        exit_group.addAnimation(exit_opacity)

        sequence = QSequentialAnimationGroup(self)
        sequence.addAnimation(enter_group)
        sequence.addPause(1000)
        sequence.addAnimation(exit_group)
        sequence.finished.connect(self.success_tip.hide)

        self.success_tip_animation = sequence
        self.success_tip_animation.start()

    def send_content(self) -> None:
        content = self.content_text.toMarkdown().strip()
        content = self._normalize_markdown_output(content)
        content = self._visual_tasks_to_markdown(content)
        if not content:
            content = self.content_text.toPlainText().strip()
            content = self._visual_tasks_to_markdown(content)
        if not content:
            QMessageBox.warning(self, "提示", "请先输入内容")
            return

        if self._markdown_prefix_title:
            current_time = datetime.now().strftime("%H:%M:%S")
            content = f"## {self._markdown_prefix_title} {current_time}\n\n{content}"

        try:
            args = self._build_command(content)
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"命令模板解析失败: {exc}")
            return

        exec_env = os.environ.copy()
        exec_env["PATH"] = build_runtime_path()

        try:
            result = subprocess.run(
                args,
                check=False,
                capture_output=True,
                text=True,
                timeout=20,
                env=exec_env,
            )
        except FileNotFoundError:
            available = []
            for name in ("obsidian", "obsidiancli", "obsidian-cli"):
                path = shutil.which(name, path=exec_env.get("PATH", ""))
                if path:
                    available.append(f"{name} -> {path}")
            found = "\n".join(available) if available else "(none)"
            QMessageBox.critical(
                self,
                "命令不存在",
                (
                    f"找不到命令: {args[0]}\n\n"
                    f"可用相关命令:\n{found}\n\n"
                    f"当前 PATH:\n{exec_env.get('PATH', '')}\n\n"
                    f"期望模板:\n{COMMAND_TEMPLATE}"
                ),
            )
            return
        except subprocess.TimeoutExpired:
            QMessageBox.critical(self, "超时", "命令执行超时 (20s)")
            return
        except OSError as exc:
            QMessageBox.critical(self, "执行错误", str(exc))
            return

        if result.returncode != 0:
            details = (result.stderr or result.stdout or "(no output)").strip()
            QMessageBox.critical(self, "发送失败", f"Exit code: {result.returncode}\n\n{details}")
            return

        self.content_text.clear()
        self._show_success_tip()


class ShortcutSettingsDialog(QDialog):
    def __init__(
        self,
        show_sequence: QKeySequence,
        task_sequence: QKeySequence,
        send_sequence: QKeySequence,
        prefix_title: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("快捷键设置")
        self.setModal(True)
        self.resize(460, 250)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.show_sequence_edit = ShortcutCaptureEdit(self)
        self.show_sequence_edit.setPlaceholderText("例如: Cmd+Shift+O")
        self.show_sequence_edit.set_key_sequence(show_sequence)
        form.addRow("显示窗口快捷键", self.show_sequence_edit)

        self.task_sequence_edit = ShortcutCaptureEdit(self)
        self.task_sequence_edit.setPlaceholderText("例如: Cmd+L")
        self.task_sequence_edit.set_key_sequence(task_sequence)
        form.addRow("任务列表快捷键", self.task_sequence_edit)

        self.send_sequence_edit = ShortcutCaptureEdit(self)
        self.send_sequence_edit.setPlaceholderText("例如: Cmd+Enter")
        self.send_sequence_edit.set_key_sequence(send_sequence)
        form.addRow("发送快捷键", self.send_sequence_edit)

        self.prefix_title_edit = QLineEdit(self)
        self.prefix_title_edit.setPlaceholderText("例如: 随想")
        self.prefix_title_edit.setText(prefix_title)
        form.addRow("Markdown前缀标题", self.prefix_title_edit)
        layout.addLayout(form)

        hint_label = QLabel("示例: Cmd+Shift+O / Cmd+L / Cmd+Enter；前缀为空则不拼接标题", self)
        hint_label.setStyleSheet("color: #6b746f; font-size: 12px;")
        layout.addWidget(hint_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        restore_button = buttons.addButton("恢复默认", QDialogButtonBox.ButtonRole.ResetRole)
        restore_button.clicked.connect(self._restore_defaults)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _restore_defaults(self) -> None:
        self.show_sequence_edit.set_key_sequence(QKeySequence(DEFAULT_HOTKEY_QT))
        self.task_sequence_edit.set_key_sequence(QKeySequence(DEFAULT_TASK_HOTKEY_QT))
        self.send_sequence_edit.set_key_sequence(QKeySequence(DEFAULT_SEND_HOTKEY_QT))
        self.prefix_title_edit.clear()

    def selected_values(self) -> tuple[QKeySequence, QKeySequence, QKeySequence, str]:
        return (
            self.show_sequence_edit.key_sequence(),
            self.task_sequence_edit.key_sequence(),
            self.send_sequence_edit.key_sequence(),
            self.prefix_title_edit.text().strip(),
        )


class TrayController(QObject):
    def __init__(
        self,
        app: QApplication,
        window: QuickAddWindow,
        icon: QIcon,
        hotkey_manager: GlobalHotkeyManager,
        settings: QSettings,
    ) -> None:
        super().__init__()
        self.app = app
        self.window = window
        self.hotkey_manager = hotkey_manager
        self.settings = settings
        self.tray = QSystemTrayIcon(icon, self.app)
        self._current_hotkey_label = hotkey_label(self.window.show_window_shortcut())
        self.tray.setToolTip(f"{APP_TITLE} ({self._current_hotkey_label})")

        self.menu = QMenu()
        show_action = QAction("显示窗口", self.menu)
        show_action.triggered.connect(self.window.show_window)
        self.menu.addAction(show_action)

        hide_action = QAction("隐藏窗口", self.menu)
        hide_action.triggered.connect(self.window.hide)
        self.menu.addAction(hide_action)

        settings_action = QAction("设置", self.menu)
        settings_action.triggered.connect(self._open_settings)
        self.menu.addAction(settings_action)

        self.menu.addSeparator()

        quit_action = QAction("退出", self.menu)
        quit_action.triggered.connect(self.app.quit)
        self.menu.addAction(quit_action)

        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _toggle_window(self) -> None:
        if self.window.isVisible():
            self.window.hide()
        else:
            self.window.show_window()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self._toggle_window()
            return
        if reason == QSystemTrayIcon.ActivationReason.Context:
            self.menu.popup(QCursor.pos())

    def notify_hotkey_fallback(self) -> None:
        self.tray.showMessage(
            APP_TITLE,
            f"未检测到 pynput，全局快捷键不可用。\n当前可用: {self._current_hotkey_label} (应用激活时)",
            QSystemTrayIcon.MessageIcon.Information,
            3500,
        )

    def _open_settings(self) -> None:
        self.window._suspend_auto_hide = True
        self.window.set_settings_dialog_open(True)
        self.window.set_shortcuts_enabled(False)
        self.window.show_window()
        old_hotkey_token = self.hotkey_manager.hotkey_token
        dialog = ShortcutSettingsDialog(
            self.window.show_window_shortcut(),
            self.window.task_shortcut_sequence(),
            self.window.send_shortcut_sequence(),
            self.window.markdown_prefix_title(),
            self.window,
        )
        old_show_sequence = self.window.show_window_shortcut()
        try:
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

            show_sequence, task_sequence, send_sequence, prefix_title = dialog.selected_values()
            if show_sequence.isEmpty() or task_sequence.isEmpty() or send_sequence.isEmpty():
                QMessageBox.warning(self.window, "设置失败", "快捷键不能为空")
                return

            hotkey_token = key_sequence_to_pynput_token(show_sequence)
            if hotkey_token is None:
                QMessageBox.warning(
                    self.window,
                    "设置失败",
                    "显示窗口快捷键暂不支持，请使用字母/数字或常见按键组合",
                )
                return

            self.window.set_show_window_shortcut(show_sequence)
            self.window.set_task_shortcut(task_sequence)
            self.window.set_send_shortcut(send_sequence)
            self.window.set_markdown_prefix_title(prefix_title)

            self._current_hotkey_label = hotkey_label(show_sequence)
            self.tray.setToolTip(f"{APP_TITLE} ({self._current_hotkey_label})")
            self.settings.setValue(
                SETTINGS_HOTKEY_KEY,
                show_sequence.toString(QKeySequence.SequenceFormat.PortableText),
            )
            self.settings.setValue(
                SETTINGS_TASK_HOTKEY_KEY,
                task_sequence.toString(QKeySequence.SequenceFormat.PortableText),
            )
            self.settings.setValue(
                SETTINGS_SEND_HOTKEY_KEY,
                send_sequence.toString(QKeySequence.SequenceFormat.PortableText),
            )
            self.settings.setValue(SETTINGS_PREFIX_TITLE_KEY, prefix_title)

            show_changed = show_sequence.toString(QKeySequence.SequenceFormat.PortableText) != old_show_sequence.toString(
                QKeySequence.SequenceFormat.PortableText
            )
            if show_changed:
                if keyboard is None:
                    self.hotkey_manager.hotkey_token = hotkey_token
                    self.notify_hotkey_fallback()
                else:
                    if not self.hotkey_manager.set_hotkey(hotkey_token):
                        self.hotkey_manager.set_hotkey(old_hotkey_token)
                        QMessageBox.warning(
                            self.window,
                            "全局快捷键设置失败",
                            "新快捷键注册失败，已恢复旧快捷键。",
                        )
        except Exception as exc:
            QMessageBox.critical(
                self.window,
                "设置失败",
                f"保存设置时发生异常:\n{exc}",
            )
        finally:
            self.window.set_settings_dialog_open(False)
            self.window.set_shortcuts_enabled(True)
            QTimer.singleShot(150, self.window._resume_auto_hide)


def main() -> int:
    os.environ["PATH"] = build_runtime_path()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    if sys.platform == "darwin" and objc is not None:
        try:
            ns_app = NSApp() if NSApp is not None else None
            if ns_app is not None and hasattr(ns_app, "setActivationPolicy_"):
                ns_app.setActivationPolicy_(MACOS_ACTIVATION_POLICY_ACCESSORY)
        except Exception:
            pass

    icon = build_app_icon()
    app.setWindowIcon(icon)

    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    saved_show_shortcut = settings.value(SETTINGS_HOTKEY_KEY, DEFAULT_HOTKEY_QT, str)
    current_show_shortcut = QKeySequence(saved_show_shortcut)
    if current_show_shortcut.isEmpty():
        current_show_shortcut = QKeySequence(DEFAULT_HOTKEY_QT)

    saved_task_shortcut = settings.value(SETTINGS_TASK_HOTKEY_KEY, DEFAULT_TASK_HOTKEY_QT, str)
    current_task_shortcut = QKeySequence(saved_task_shortcut)
    if current_task_shortcut.isEmpty():
        current_task_shortcut = QKeySequence(DEFAULT_TASK_HOTKEY_QT)

    saved_send_shortcut = settings.value(SETTINGS_SEND_HOTKEY_KEY, DEFAULT_SEND_HOTKEY_QT, str)
    current_send_shortcut = QKeySequence(saved_send_shortcut)
    if current_send_shortcut.isEmpty():
        current_send_shortcut = QKeySequence(DEFAULT_SEND_HOTKEY_QT)

    saved_prefix_title = settings.value(SETTINGS_PREFIX_TITLE_KEY, "", str)
    current_prefix_title = saved_prefix_title.strip() if isinstance(saved_prefix_title, str) else ""

    window = QuickAddWindow()
    window.set_show_window_shortcut(current_show_shortcut)
    window.set_task_shortcut(current_task_shortcut)
    window.set_send_shortcut(current_send_shortcut)
    window.set_markdown_prefix_title(current_prefix_title)

    hotkey_bridge = GlobalHotkeyBridge()
    hotkey_bridge.activated.connect(window.handle_show_shortcut)

    hotkey_token = key_sequence_to_pynput_token(current_show_shortcut) or DEFAULT_HOTKEY_TOKEN
    hotkey_manager = GlobalHotkeyManager(hotkey_bridge, hotkey_token)
    tray = TrayController(app, window, icon, hotkey_manager, settings)
    hotkey_ready = hotkey_manager.start()
    if not hotkey_ready:
        QTimer.singleShot(600, tray.notify_hotkey_fallback)

    window.show_window()

    exit_code = app.exec()
    hotkey_manager.stop()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
