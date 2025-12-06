# ClipKeep 2.1 (based on ClipKeep 2.0) - added system/light/dark theme support
import sys
import sqlite3
import json
import traceback
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple
import os

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QListWidget, QListWidgetItem, QTextEdit, QLabel,
    QSplitter, QHBoxLayout, QPushButton, QCheckBox,
    QMessageBox, QLineEdit, QMenu, QSystemTrayIcon,
    QStyle, QDialog, QFormLayout, QSpinBox, QGroupBox,
    QComboBox
)
from PyQt6.QtGui import (
    QIcon, QAction, QPixmap, QImage, QKeySequence,
    QShortcut, QWheelEvent, QDesktopServices, QPalette, QColor
)
from PyQt6.QtCore import (
    Qt, QTimer, QByteArray, QBuffer, QSize, QUrl,
    QThreadPool, QRunnable, QObject, pyqtSignal, pyqtSlot
)

def resource_path(relative_path):
    """PyInstaller 安全加载资源文件（icons/images）"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# -----------------------
# Constants
# -----------------------
APP_NAME = "ClipKeep"
APP_VERSION = "2.1"

ROLE_TYPE = Qt.ItemDataRole.UserRole
ROLE_RECORD_ID = Qt.ItemDataRole.UserRole + 1
ROLE_TIMESTAMP = Qt.ItemDataRole.UserRole + 2
ROLE_FORMAT = Qt.ItemDataRole.UserRole + 3

MAX_IMAGE_AREA_PIXELS = 4 * 1024 * 1024  # 4MP (Default limit)
SAVE_DEBOUNCE_MS = 700
RESIZE_DEBOUNCE_MS = 150
DEFAULT_MAX_HISTORY = 100
THUMBNAIL_SIZE = 64

# WinUI 3.0 Inspired Stylesheet (light)
WINUI_STYLESHEET = """
QMainWindow {
    background-color: #f3f3f3;
}
QWidget {
    font-family: 'Segoe UI', sans-serif;
    font-size: 14px;
    color: #333;
}
QLineEdit {
    background-color: white;
    border: 1px solid #e5e5e5;
    border-radius: 6px;
    padding: 8px;
    selection-background-color: #0078D4;
}
QLineEdit:focus {
    border: 1px solid #0078D4;
    border-bottom: 2px solid #0078D4;
}
QPushButton {
    background-color: white;
    border: 1px solid #e5e5e5;
    border-radius: 6px;
    padding: 6px 12px;
}
QPushButton:hover {
    background-color: #f9f9f9;
    border-color: #d0d0d0;
}
QPushButton:pressed {
    background-color: #f0f0f0;
    color: #666;
}
QListWidget {
    background-color: white;
    border: 1px solid #e5e5e5;
    border-radius: 8px;
    outline: none;
}
QListWidget::item {
    padding: 12px;
    border-bottom: 1px solid #f9f9f9;
    border-radius: 4px;
    margin: 2px 4px;
}
QListWidget::item:selected {
    background-color: #e0eaff;
    color: #000;
    border: none;
}
QListWidget::item:hover:!selected {
    background-color: #f3f3f3;
}
QTextEdit {
    background-color: white;
    border: 1px solid #e5e5e5;
    border-radius: 8px;
    padding: 8px;
}
QLabel#DetailPlaceholder {
    color: #888;
    background-color: white;
    border-radius: 8px;
    border: 1px dashed #ccc;
}
"""

# Dark Stylesheet
DARK_STYLESHEET = """
QMainWindow {
    background-color: #1f1f1f;
}
QWidget {
    font-family: 'Segoe UI', sans-serif;
    font-size: 14px;
    color: #e8e8e8;
}
QLineEdit {
    background-color: #2a2a2a;
    border: 1px solid #3a3a3a;
    border-radius: 6px;
    padding: 8px;
    selection-background-color: #0078D4;
    color: #e8e8e8;
}
QLineEdit:focus {
    border: 1px solid #0078D4;
    border-bottom: 2px solid #0078D4;
}
QPushButton {
    background-color: #2a2a2a;
    border: 1px solid #3a3a3a;
    border-radius: 6px;
    padding: 6px 12px;
    color: #e8e8e8;
}
QPushButton:hover {
    background-color: #333333;
    border-color: #505050;
}
QPushButton:pressed {
    background-color: #2b2b2b;
    color: #ccc;
}
QListWidget {
    background-color: #151515;
    border: 1px solid #2a2a2a;
    border-radius: 8px;
    outline: none;
}
QListWidget::item {
    padding: 12px;
    border-bottom: 1px solid #151515;
    border-radius: 4px;
    margin: 2px 4px;
    color: #e8e8e8;
}
QListWidget::item:selected {
    background-color: #005090; /* adapted WinUI blue for dark */
    color: #ffffff;
    border: none;
}
QListWidget::item:hover:!selected {
    background-color: #232323;
}
QTextEdit {
    background-color: #1e1e1e;
    border: 1px solid #2a2a2a;
    border-radius: 8px;
    padding: 8px;
    color: #e8e8e8;
}
QLabel#DetailPlaceholder {
    color: #999;
    background-color: #1e1e1e;
    border-radius: 8px;
    border: 1px dashed #333;
}
"""

# -----------------------
# Data Model
# -----------------------
class ClipboardRecord:
    """Represents a single clipboard record."""
    def __init__(self, record_id: int, record_type: str, content: any,
                 timestamp: float, thumbnail: Optional[bytes] = None,
                 fmt: str = "plain"):
        self.id = record_id
        self.type = record_type
        self.content = content
        self.timestamp = timestamp
        self.thumbnail = thumbnail
        self.format = fmt  # 'plain', 'html', 'file', 'PNG', 'JPEG'


class ClipboardDatabase:
    """Synchronous Database Manager."""
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = None
        self._init_database()

    def _init_database(self):
        # Allow check_same_thread=False for read operations from workers,
        # but writes should be carefully managed (mainly main thread).
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        cursor = self.conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                content TEXT,
                content_blob BLOB,
                timestamp REAL NOT NULL,
                thumbnail BLOB,
                format TEXT,
                width INTEGER,
                height INTEGER
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON records(timestamp DESC)
        """)
        self.conn.commit()

    def add_text_record(self, text: str, record_format: str = "plain") -> int:
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO records (type, content, timestamp, format)
            VALUES (?, ?, ?, ?)
        """, ("text", text, datetime.now().timestamp(), record_format))
        self.conn.commit()
        return cursor.lastrowid

    def add_image_record(self, image: QImage, thumbnail: bytes, fmt: str) -> int:
        byte_array = QByteArray()
        buffer = QBuffer(byte_array)
        buffer.open(QBuffer.OpenModeFlag.WriteOnly)

        # Save exact blob
        quality = -1 if fmt == "PNG" else 90
        image.save(buffer, fmt, quality)
        buffer.close()

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO records (type, content_blob, timestamp, thumbnail, format, width, height)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            "image",
            byte_array.data(),
            datetime.now().timestamp(),
            thumbnail,
            fmt,
            image.width(),
            image.height()
        ))
        self.conn.commit()
        return cursor.lastrowid

    def update_text_content(self, record_id: int, new_text: str):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE records SET content = ? WHERE id = ?", (new_text, record_id))
        self.conn.commit()

    def delete_record(self, record_id: int):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM records WHERE id = ?", (record_id,))
        self.conn.commit()

    def clear_all(self):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM records")
        self.conn.commit()

    def get_count(self) -> int:
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM records")
        return cursor.fetchone()[0]

    def trim_to_limit(self, max_count: int):
        cursor = self.conn.cursor()
        cursor.execute("""
            DELETE FROM records WHERE id NOT IN (
                SELECT id FROM records ORDER BY timestamp DESC LIMIT ?
            )
        """, (max_count,))
        self.conn.commit()

    def close(self):
        if self.conn:
            self.conn.close()

# -----------------------
# Async Workers
# -----------------------
class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)

class DBWorker(QRunnable):
    """Generic worker for database operations to avoid blocking UI."""
    def __init__(self, db_path: Path, mode: str, **kwargs):
        super().__init__()
        self.db_path = db_path
        self.mode = mode
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            # Create a fresh connection for thread safety
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            output = None

            if self.mode == "load_all":
                limit = self.kwargs.get("limit", 100)
                cursor.execute("""
                    SELECT id, type, content, content_blob, timestamp, thumbnail, format
                    FROM records ORDER BY timestamp DESC LIMIT ?
                """, (limit,))
                rows = cursor.fetchall()
                records = []
                for row in rows:
                    rec_id, rec_type, txt, blob, ts, thumb, fmt = row
                    # For list view, we don't load full image blobs, only thumbs/text
                    content = txt if rec_type == "text" else None
                    records.append(ClipboardRecord(rec_id, rec_type, content, ts, thumb, fmt))
                output = records

            elif self.mode == "get_detail":
                rec_id = self.kwargs.get("record_id")
                cursor.execute("""
                    SELECT id, type, content, content_blob, timestamp, thumbnail, format
                    FROM records WHERE id = ?
                """, (rec_id,))
                row = cursor.fetchone()
                if row:
                    rec_id, rec_type, txt, blob, ts, thumb, fmt = row
                    if rec_type == "text":
                        content = txt
                    else:
                        image = QImage()
                        image.loadFromData(blob)
                        content = image
                    output = ClipboardRecord(rec_id, rec_type, content, ts, thumb, fmt)

            conn.close()
            self.signals.result.emit(output)
        except Exception:
            traceback.print_exc()
            self.signals.error.emit(sys.exc_info())
        finally:
            self.signals.finished.emit()

# -----------------------
# Custom Widgets
# -----------------------
class ZoomableImageLabel(QLabel):
    """Scalable image viewer with mouse wheel support."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.original_image: Optional[QImage] = None
        self.zoom_factor = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 5.0
        self.original_width = 0
        self.original_height = 0

    def set_image(self, image: Optional[QImage]):
        if image is None:
            self.original_image = None
            self.clear()
            return
        self.original_image = image
        self.original_width = image.width()
        self.original_height = image.height()
        self.zoom_factor = 1.0
        self._update_display()

    def _update_display(self):
        if not self.original_image:
            return

        container_size = self.size()
        if container_size.width() <= 0 or container_size.height() <= 0:
            return

        scale_w = container_size.width() / self.original_width
        scale_h = container_size.height() / self.original_height
        fit_scale = min(scale_w, scale_h)
        final_scale = fit_scale * self.zoom_factor

        final_width = int(self.original_width * final_scale)
        final_height = int(self.original_height * final_scale)

        scaled = self.original_image.scaled(
            final_width, final_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.setPixmap(QPixmap.fromImage(scaled))

    def wheelEvent(self, event: QWheelEvent):
        if not self.original_image:
            return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            zoom_step = 0.1
            if delta > 0:
                self.zoom_factor = min(self.max_zoom, self.zoom_factor + zoom_step)
            else:
                self.zoom_factor = max(self.min_zoom, self.zoom_factor - zoom_step)
            self._update_display()
            event.accept()
        else:
            super().wheelEvent(event)

    def reset_zoom(self):
        self.zoom_factor = 1.0
        self._update_display()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.original_image:
            self._update_display()

class SettingsDialog(QDialog):
    """Settings Window using QDialog."""
    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("设置")
        self.setFixedWidth(380)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # General
        self.check_top = QCheckBox("窗口置顶 (Always on Top)")
        self.check_top.setChecked(settings.get("window_always_on_top", False))
        form.addRow(self.check_top)

        # Theme selection
        self.combo_theme = QComboBox()
        # Display labels: follow system / light / dark
        self.combo_theme.addItem("跟随系统 (默认)", "system")
        self.combo_theme.addItem("亮色模式 (Light)", "light")
        self.combo_theme.addItem("暗色模式 (Dark)", "dark")
        current_theme = settings.get("app_theme", "system")
        idx = 0
        for i in range(self.combo_theme.count()):
            if self.combo_theme.itemData(i) == current_theme:
                idx = i
                break
        self.combo_theme.setCurrentIndex(idx)
        form.addRow("主题 (Theme):", self.combo_theme)

        # History Limit
        self.spin_history = QSpinBox()
        self.spin_history.setRange(10, 1000)
        self.spin_history.setSingleStep(10)
        self.spin_history.setValue(settings.get("max_history", DEFAULT_MAX_HISTORY))
        form.addRow("最大历史记录数:", self.spin_history)

        layout.addLayout(form)

        # Formats Group
        grp_formats = QGroupBox("高级功能 & 格式")
        fmt_layout = QVBoxLayout()

        self.check_save_orig = QCheckBox("保存图片原图 (不压缩)")
        self.check_save_orig.setToolTip("开启后将忽略4MP限制，保存完整图片。可能会占用更多空间。")
        self.check_save_orig.setChecked(settings.get("save_original_image", False))
        fmt_layout.addWidget(self.check_save_orig)

        self.check_rich_text = QCheckBox("支持富文本 (HTML)")
        self.check_rich_text.setChecked(settings.get("enable_rich_text", True))
        fmt_layout.addWidget(self.check_rich_text)

        self.check_files = QCheckBox("支持文件路径复制")
        self.check_files.setChecked(settings.get("enable_file_paths", True))
        fmt_layout.addWidget(self.check_files)

        grp_formats.setLayout(fmt_layout)
        layout.addWidget(grp_formats)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("保存")
        btn_save.clicked.connect(self.accept)
        btn_save.setStyleSheet("background-color: #0078D4; color: white; border: none;")

        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

    def get_data(self) -> dict:
        return {
            "window_always_on_top": self.check_top.isChecked(),
            "max_history": self.spin_history.value(),
            "save_original_image": self.check_save_orig.isChecked(),
            "enable_rich_text": self.check_rich_text.isChecked(),
            "enable_file_paths": self.check_files.isChecked(),
            "app_theme": self.combo_theme.currentData() or "system"
        }

# -----------------------
# Main Application
# -----------------------

class ClipKeepApp(QMainWindow):  # <--- FIXED: Added the missing class definition
    def __init__(self):
        super().__init__()
        
        # Load icon safely
        try:
            self.setWindowIcon(QIcon(resource_path("clipkeep.ico")))
        except:
            pass

        # Core Setup
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(550, 700)
        self.setMinimumSize(400, 500)

        # Configuration
        self.config_dir = Path.home() / ".holder"
        self.config_dir.mkdir(exist_ok=True)
        self.db_path = self.config_dir / "clipboard.db"
        self.settings_file = self.config_dir / "settings.json"

        self.settings = self.load_settings()
        self.max_history = self.settings.get("max_history", DEFAULT_MAX_HISTORY)

        # Database & Threading
        self.db = ClipboardDatabase(self.db_path)
        self.threadpool = QThreadPool()

        # State
        self.is_internal_copy = False
        self.force_quit = False  # Controlled exit vs minimize
        self.current_record: Optional[ClipboardRecord] = None

        # Timers
        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._do_save_pending)
        self._pending_save_id = None
        self._pending_save_text = None

        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._on_resize_complete)

        # UI Initialization
        # Default: apply theme-aware stylesheet through apply_settings
        self.init_ui()
        self.setup_tray()
        self.setup_shortcuts()
        self.apply_settings()
        self.refresh_history_async()

        # Clipboard Monitor
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.on_clipboard_change)

    # -----------------------
    # Theme & Settings Management
    # -----------------------
    def load_settings(self) -> dict:
        defaults = {
            "max_history": DEFAULT_MAX_HISTORY,
            "window_always_on_top": False,
            "save_original_image": False,
            "enable_rich_text": True,
            "enable_file_paths": True,
            "app_theme": "system"  # 'system' | 'light' | 'dark'
        }
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    defaults.update(data)
            except Exception as e:
                print(f"Error loading settings: {e}")
        return defaults

    def save_settings_to_file(self):
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def is_system_dark(self) -> bool:
        """
        Heuristic to detect system preference for dark mode using QApplication palette.
        Returns True if the system palette suggests dark theme.
        """
        try:
            pal = QApplication.palette()
            # Get window background color
            bg = pal.color(QPalette.ColorRole.Window)
            # Compute perceived luminance
            r, g, b = bg.red(), bg.green(), bg.blue()
            # Relative luminance approximation
            luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
            return luminance < 128
        except Exception:
            return False

    def get_current_stylesheet(self, theme: str) -> str:
        """
        Return the appropriate stylesheet string based on setting:
         - 'system' -> detect via is_system_dark()
         - 'light' or 'dark' -> force
        """
        if theme == "light":
            return WINUI_STYLESHEET
        elif theme == "dark":
            return DARK_STYLESHEET
        else:
            # system
            return DARK_STYLESHEET if self.is_system_dark() else WINUI_STYLESHEET

    def apply_settings(self):
        # Window on top
        if self.settings.get("window_always_on_top", False):
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)
        self.max_history = self.settings.get("max_history", DEFAULT_MAX_HISTORY)

        # Apply theme stylesheet
        theme = self.settings.get("app_theme", "system")
        stylesheet = self.get_current_stylesheet(theme)
        # Apply to the main window (affects children)
        self.setStyleSheet(stylesheet)

        # Additional per-widget tweaks that cannot be fully controlled via global stylesheet:
        # ZoomableImageLabel background / border adjustments:
        if stylesheet is DARK_STYLESHEET:
            self.image_viewer.setStyleSheet("background-color: #1e1e1e; border: 1px dashed #333; border-radius: 6px;")
            self.zoom_hint.setStyleSheet("color: #999; font-size: 11px; margin-top: 4px;")
            self.count_label.setStyleSheet("color: #cfcfcf; font-weight: bold;")
            # Tray icon font color can't be enforced, but ensure menu actions text color uses system
        else:
            self.image_viewer.setStyleSheet("background-color: #fafafa; border: 1px dashed #ccc; border-radius: 6px;")
            self.zoom_hint.setStyleSheet("color: #999; font-size: 11px; margin-top: 4px;")
            self.count_label.setStyleSheet("color: #666; font-weight: bold;")

        # Ensure flags are applied (window always on top change requires re-show)
        self.show()

    def open_settings_dialog(self):
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec():
            new_settings = dlg.get_data()
            self.settings.update(new_settings)
            self.save_settings_to_file()
            # Immediately apply settings including theme
            self.apply_settings()

            # If history limit reduced, trim DB and reload
            self.db.trim_to_limit(self.max_history)
            self.refresh_history_async()
            self.statusBar().showMessage("设置已保存", 2000)

    # -----------------------
    # UI Setup
    # -----------------------
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)

        # Top Bar
        top_bar = QHBoxLayout()

        self.count_label = QLabel("0 Items")
        self.count_label.setStyleSheet("color: #666; font-weight: bold;")
        top_bar.addWidget(self.count_label)

        top_bar.addStretch()

        btn_style = "QPushButton { font-weight: bold; border-radius: 6px; }"

        self.btn_settings = QPushButton("⚙️")
        self.btn_settings.setToolTip("设置")
        self.btn_settings.setFixedSize(36, 32)
        self.btn_settings.clicked.connect(self.open_settings_dialog)
        top_bar.addWidget(self.btn_settings)

        self.btn_clear = QPushButton("清空")
        self.btn_clear.setToolTip("Ctrl+Shift+Del")
        self.btn_clear.clicked.connect(self.clear_history)
        self.btn_clear.setStyleSheet("background-color: #e81123; color: white; border: none;")
        top_bar.addWidget(self.btn_clear)

        self.btn_copy = QPushButton("复制")
        self.btn_copy.setToolTip("Ctrl+Enter")
        self.btn_copy.clicked.connect(self.copy_selected_to_system)
        self.btn_copy.setStyleSheet("background-color: #0078D4; color: white; border: none;")
        top_bar.addWidget(self.btn_copy)

        main_layout.addLayout(top_bar)

        # Search
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 搜索剪切板... (Ctrl+F)")
        self.search_box.textChanged.connect(self.filter_history)
        main_layout.addWidget(self.search_box)

        # Splitter (List / Detail)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(8)

        # History List
        self.history_list = QListWidget()
        self.history_list.currentItemChanged.connect(self.on_item_selected)
        self.history_list.itemDoubleClicked.connect(self.copy_selected_to_system)
        self.history_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self.show_context_menu)
        splitter.addWidget(self.history_list)

        # Detail View Container
        self.detail_container = QWidget()
        detail_layout = QVBoxLayout(self.detail_container)
        detail_layout.setContentsMargins(0, 0, 0, 0)

        # Different Viewers
        self.text_editor = QTextEdit()
        self.text_editor.setPlaceholderText("内容预览...")
        self.text_editor.textChanged.connect(self.on_text_edited)
        self.text_editor.hide()

        self.image_viewer = ZoomableImageLabel()
        self.image_viewer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_viewer.setStyleSheet("background-color: #fafafa; border: 1px dashed #ccc; border-radius: 6px;")
        self.image_viewer.setMinimumHeight(150)
        self.image_viewer.hide()

        self.zoom_hint = QLabel("💡 Ctrl+Scroll 缩放 | Ctrl+0 重置")
        self.zoom_hint.setStyleSheet("color: #999; font-size: 11px; margin-top: 4px;")
        self.zoom_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_hint.hide()

        detail_layout.addWidget(self.text_editor)
        detail_layout.addWidget(self.image_viewer)
        detail_layout.addWidget(self.zoom_hint)

        splitter.addWidget(self.detail_container)
        splitter.setSizes([350, 250]) # Default ratio

        main_layout.addWidget(splitter)
        self.statusBar().showMessage("Ready")

    def setup_tray(self):
        """Initialize System Tray Icon."""
        self.tray_icon = QSystemTrayIcon(self)

        # Use standard icon or fallback
        # FIXED: use class name or self to ensure context
        if Path(resource_path("clipkeep_tray.png")).exists():
            tray_icon = QIcon(resource_path("clipkeep_tray.png"))
        else:
            tray_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)

        self.tray_icon.setIcon(tray_icon)

        tray_menu = QMenu()

        show_action = QAction("显示主窗口", self)
        show_action.triggered.connect(self.showNormal)
        tray_menu.addAction(show_action)

        settings_action = QAction("设置...", self)
        settings_action.triggered.connect(self.open_settings_dialog)
        tray_menu.addAction(settings_action)

        tray_menu.addSeparator()

        quit_action = QAction("退出 ClipKeep", self)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.showNormal()
                self.activateWindow()

    def closeEvent(self, event):
        """Minimize to tray instead of exiting."""
        if self.force_quit:
            event.accept()
        else:
            event.ignore()
            self.hide()
            self.tray_icon.showMessage(
                "ClipKeep",
                "应用已最小化到托盘",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )

    def quit_application(self):
        """Truly exit the application."""
        self.force_quit = True
        QApplication.quit()

    def setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+F"), self, self.search_box.setFocus)
        QShortcut(QKeySequence.StandardKey.Delete, self, self.delete_selected)
        QShortcut(QKeySequence("Ctrl+Return"), self, self.copy_selected_to_system)
        QShortcut(QKeySequence("Escape"), self, self.clear_search)
        QShortcut(QKeySequence("Ctrl+Shift+Del"), self, self.clear_history)
        QShortcut(QKeySequence("Return"), self.history_list, self.copy_selected_to_system)
        QShortcut(QKeySequence("Ctrl+0"), self, lambda: self.image_viewer.reset_zoom())

    # -----------------------
    # Logic: Loading Data (Async)
    # -----------------------
    def refresh_history_async(self):
        """Load history list via ThreadPool."""
        worker = DBWorker(self.db_path, "load_all", limit=self.max_history)
        worker.signals.result.connect(self.on_history_loaded)
        self.threadpool.start(worker)

    def on_history_loaded(self, records: List[ClipboardRecord]):
        self.history_list.clear()

        for rec in records:
            # Determine display text and icon
            if rec.type == "text":
                if rec.format == "file":
                    # File List
                    line_count = rec.content.count('\n') + 1
                    display_text = f"📂 文件列表 ({line_count} items): " + rec.content.split('\n')[0]
                    icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
                elif rec.format == "html":
                    display_text = "🌐 富文本 (HTML)"
                    icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
                else:
                    # Plain Text
                    display_text = rec.content[:80].replace("\n", " ")
                    icon = QIcon() # Default no icon

                item = QListWidgetItem(display_text)
                item.setData(ROLE_TYPE, "text")

            elif rec.type == "image":
                # Create icon from thumbnail bytes
                pix = QPixmap()
                if rec.thumbnail:
                    pix.loadFromData(rec.thumbnail)
                else:
                    # fallback in case content_blob is present; DBWorker didn't return content_blob for list
                    pix = QPixmap()
                icon = QIcon(pix)
                item = QListWidgetItem(f"🖼️ 图片")
                item.setData(ROLE_TYPE, "image")

            # Common Data
            item.setData(ROLE_RECORD_ID, rec.id)
            item.setData(ROLE_TIMESTAMP, rec.timestamp)
            item.setData(ROLE_FORMAT, rec.format)
            item.setIcon(icon)

            self.history_list.addItem(item)

        self.update_count_label()

    def on_item_selected(self, current, previous):
        """Trigger async load of details."""
        if not current:
            self.clear_detail_view()
            return

        record_id = current.data(ROLE_RECORD_ID)

        # UI Feedback
        self.text_editor.hide()
        self.image_viewer.hide()
        self.zoom_hint.hide()

        worker = DBWorker(self.db_path, "get_detail", record_id=record_id)
        worker.signals.result.connect(self.on_detail_loaded)
        self.threadpool.start(worker)

    def on_detail_loaded(self, record: Optional[ClipboardRecord]):
        if not record:
            return

        self.current_record = record

        if record.type == "text":
            self.text_editor.show()
            self.text_editor.blockSignals(True)
            if record.format == "html":
                self.text_editor.setHtml(record.content)
            else:
                self.text_editor.setPlainText(record.content)
            self.text_editor.blockSignals(False)

        elif record.type == "image":
            self.image_viewer.show()
            self.zoom_hint.show()
            self.image_viewer.set_image(record.content)

    def clear_detail_view(self):
        self.text_editor.hide()
        self.image_viewer.hide()
        self.zoom_hint.hide()
        self.current_record = None

    # -----------------------
    # Logic: Clipboard Capture
    # -----------------------
    def on_clipboard_change(self):
        if self.is_internal_copy:
            self.is_internal_copy = False
            return

        mime_data = self.clipboard.mimeData()

        # Priority 1: File Paths (if enabled)
        if self.settings.get("enable_file_paths") and mime_data.hasUrls():
            urls = mime_data.urls()
            # Filter for local files
            local_files = [u.toLocalFile() for u in urls if u.isLocalFile()]
            if local_files:
                content = "\n".join(local_files)
                self.add_text_record(content, "file")
                return

        # Priority 2: Images
        if mime_data.hasImage():
            image = self.clipboard.image()
            if not image.isNull():
                self.add_image_record(image)
                return

        # Priority 3: HTML (if enabled)
        if self.settings.get("enable_rich_text") and mime_data.hasHtml():
            html_content = mime_data.html()
            # Avoid storing empty html wrappers
            if len(html_content) > 20:
                self.add_text_record(html_content, "html")
                return

        # Priority 4: Plain Text
        if mime_data.hasText():
            text = self.clipboard.text().strip()
            if text:
                # Check duplication logic in DB or simple recently check
                if not self._is_duplicate(text):
                    self.add_text_record(text, "plain")

    def _is_duplicate(self, text: str) -> bool:
        # Check first item in list
        if self.history_list.count() > 0:
            item = self.history_list.item(0)
            if item.data(ROLE_TYPE) == "text":
                # Need to check content. Since list item only has preview,
                # we rely on DB or cache. For simplicity, just check preview text equality
                preview = text[:80].replace("\n", " ")
                if item.text() == preview:
                    return True
        return False

    def add_text_record(self, text: str, fmt: str):
        self.db.add_text_record(text, fmt)
        self.db.trim_to_limit(self.max_history)
        self.refresh_history_async()

    def add_image_record(self, image: QImage):
        # Resize Logic if not "Save Original"
        persist_image = image
        if not self.settings.get("save_original_image"):
            area = image.width() * image.height()
            if area > MAX_IMAGE_AREA_PIXELS:
                scale_factor = (MAX_IMAGE_AREA_PIXELS / area) ** 0.5
                new_width = int(image.width() * scale_factor)
                new_height = int(image.height() * scale_factor)
                persist_image = image.scaled(
                    new_width, new_height,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )

        # Generate Thumbnail
        thumb = persist_image.scaled(
            THUMBNAIL_SIZE, THUMBNAIL_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        byte_array = QByteArray()
        buffer = QBuffer(byte_array)
        buffer.open(QBuffer.OpenModeFlag.WriteOnly)
        thumb.save(buffer, "PNG")
        buffer.close()

        has_alpha = persist_image.hasAlphaChannel()
        fmt = "PNG" if has_alpha else "JPEG"

        self.db.add_image_record(persist_image, byte_array.data(), fmt)
        self.db.trim_to_limit(self.max_history)
        self.refresh_history_async()

    # -----------------------
    # Logic: Copy / Delete
    # -----------------------
    def copy_selected_to_system(self):
        if not self.current_record:
            return

        self.is_internal_copy = True
        # For simplicity using clipboard API directly
        if self.current_record.type == "text":
            if self.current_record.format == "html":
                # Copy both text and html
                mime_data = self.clipboard.mimeData()
                mime_data.setHtml(self.current_record.content)
                # Strip tags for plain text fallback
                doc = QTextEdit()
                doc.setHtml(self.current_record.content)
                mime_data.setText(doc.toPlainText())
                self.clipboard.setMimeData(mime_data)
                self.statusBar().showMessage("✓ 已复制富文本", 2000)
            elif self.current_record.format == "file":
                # Create URLs
                urls = []
                paths = self.current_record.content.split('\n')
                for p in paths:
                    if p.strip():
                        urls.append(QUrl.fromLocalFile(p.strip()))

                mime_data = self.clipboard.mimeData()
                mime_data.setUrls(urls)
                mime_data.setText(self.current_record.content) # Fallback text
                self.clipboard.setMimeData(mime_data)
                self.statusBar().showMessage("✓ 已复制文件路径", 2000)
            else:
                self.clipboard.setText(self.current_record.content)
                self.statusBar().showMessage("✓ 已复制文本", 2000)

        elif self.current_record.type == "image":
            self.clipboard.setImage(self.current_record.content)
            self.statusBar().showMessage("✓ 已复制图片", 2000)

    def delete_selected(self):
        item = self.history_list.currentItem()
        if not item:
            return

        row = self.history_list.row(item)
        record_id = item.data(ROLE_RECORD_ID)

        self.db.delete_record(record_id)
        self.history_list.takeItem(row)
        self.clear_detail_view()
        self.update_count_label()
        self.statusBar().showMessage("已删除", 1500)

    def clear_history(self):
        if self.db.get_count() == 0:
            return

        reply = QMessageBox.question(
            self, "确认清空",
            "确定要删除所有记录吗？此操作不可恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.clear_all()
            self.history_list.clear()
            self.clear_detail_view()
            self.update_count_label()
            self.statusBar().showMessage("历史已清空", 2000)

    # -----------------------
    # Helper / Event Overrides
    # -----------------------
    def update_count_label(self):
        count = self.history_list.count()
        self.count_label.setText(f"历史: {count} / {self.max_history}")

    def filter_history(self, text):
        search_text = text.lower()
        for i in range(self.history_list.count()):
            item = self.history_list.item(i)
            # Search in text or format tag
            item_text = item.text().lower()
            match = search_text in item_text
            item.setHidden(not match)

    def clear_search(self):
        self.search_box.clear()
        self.search_box.clearFocus()

    def show_context_menu(self, pos):
        item = self.history_list.itemAt(pos)
        if not item:
            return

        menu = QMenu(self)
        menu.addAction("📋 复制", self.copy_selected_to_system)
        menu.addAction("🗑️ 删除", self.delete_selected)

        # Info
        ts = item.data(ROLE_TIMESTAMP)
        time_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        info_action = QAction(f"⏰ {time_str}", self)
        info_action.setEnabled(False)
        menu.addSeparator()
        menu.addAction(info_action)

        menu.exec(self.history_list.mapToGlobal(pos))

    def on_text_edited(self):
        """Save text changes with debounce."""
        if not self.current_record or self.current_record.type != "text":
            return

        # We only allow editing plain text or HTML source easily.
        if self.current_record.format == "html":
            new_text = self.text_editor.toHtml()
        else:
            new_text = self.text_editor.toPlainText()

        self._pending_save_id = self.current_record.id
        self._pending_save_text = new_text
        self._save_timer.start(SAVE_DEBOUNCE_MS)

    def _do_save_pending(self):
        if self._pending_save_id and self._pending_save_text is not None:
            self.db.update_text_content(self._pending_save_id, self._pending_save_text)
            self._pending_save_id = None
            self._pending_save_text = None
            self.statusBar().showMessage("已自动保存更改", 1000)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_timer.start(RESIZE_DEBOUNCE_MS)

    def _on_resize_complete(self):
        pass

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    try:
        app_icon = QIcon(resource_path("clipkeep.ico"))
    except Exception:
        app_icon = app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
    app.setWindowIcon(app_icon)

    window = ClipKeepApp()
    window.show()

    sys.exit(app.exec())
