# ClipKeep 2.251208 - Enhanced Version with Smooth Animation & Thread Safety
import sys
import sqlite3
import json
import traceback
import re
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
import os
import hashlib
import shutil

# 确保配置目录存在
config_dir = Path.home() / ".clipkeep"
config_dir.mkdir(exist_ok=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config_dir / "clipkeep.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

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
    QShortcut, QWheelEvent, QDesktopServices, QPalette, QColor, QCursor, QDrag
)
from PyQt6.QtCore import (
    Qt, QTimer, QByteArray, QBuffer, QSize, QUrl,
    QThreadPool, QRunnable, QObject, pyqtSignal, pyqtSlot,
    QPoint, QRect, QPropertyAnimation, QEasingCurve, QMimeData,
    QSortFilterProxyModel, QRegularExpression
)
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

def resource_path(relative_path):
    """PyInstaller safe resource loading"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# -----------------------
# Constants
# -----------------------
APP_NAME = "ClipKeep"
APP_VERSION = "2.251208"
SINGLE_INSTANCE_KEY = "ClipKeep_Single_Instance_Server"

ROLE_TYPE = Qt.ItemDataRole.UserRole
ROLE_RECORD_ID = Qt.ItemDataRole.UserRole + 1
ROLE_TIMESTAMP = Qt.ItemDataRole.UserRole + 2
ROLE_FORMAT = Qt.ItemDataRole.UserRole + 3
ROLE_CONTENT_HASH = Qt.ItemDataRole.UserRole + 4

MAX_IMAGE_AREA_PIXELS = 4 * 1024 * 1024
SAVE_DEBOUNCE_MS = 700
RESIZE_DEBOUNCE_MS = 150
DEFAULT_MAX_HISTORY = 100
THUMBNAIL_SIZE = 64

# Edge hide settings
EDGE_HIDE_THRESHOLD = 5
EDGE_SHOW_WIDTH = 3
EDGE_DETECT_AREA = 30  # 增加检测区域
ANIMATION_DURATION = 250
EDGE_HIDE_DELAY_MS = 1500  # 贴边后等待1.5秒再隐藏
EDGE_SHOW_DELAY_MS = 300   # 光标靠近后等待0.3秒再显示
EDGE_SNAP_DISTANCE = 30

# Temp cleanup settings
TEMP_CLEANUP_DAYS = 1
MIN_FREE_SPACE_MB = 50

# -----------------------
# Multi-Language Support
# -----------------------
TRANSLATIONS = {
    "zh_CN": {
        "window_title": "ClipKeep",
        "items": "历史",
        "settings": "设置",
        "clear": "清空",
        "search_placeholder": "🔍 搜索剪切板... (Ctrl+F)",
        "content_preview": "内容预览...",
        "zoom_hint": "💡 Ctrl+鼠标滚轮 缩放 | Ctrl+0 重置",
        "ready": "Ready",
        "settings_title": "设置",
        "always_on_top": "窗口置顶 (Always on Top)",
        "theme": "主题 (Theme):",
        "theme_system": "跟随系统 (默认)",
        "theme_light": "亮色模式 (Light)",
        "theme_dark": "暗色模式 (Dark)",
        "language": "语言 (Language):",
        "language_zh": "简体中文",
        "language_en": "English",
        "max_history": "最大历史记录数:",
        "advanced_features": "高级功能 & 格式",
        "save_original": "保存图片原图 (不压缩)",
        "save_original_tip": "开启后将忽略4MP限制,保存完整图片。可能会占用更多空间。",
        "enable_rich_text": "支持富文本 (HTML)",
        "enable_file_paths": "支持文件路径复制",
        "edge_hide": "贴边自动隐藏",
        "save": "保存",
        "cancel": "取消",
        "settings_saved": "设置已保存",
        "show_window": "显示主窗口",
        "exit_app": "退出 ClipKeep",
        "minimized_to_tray": "应用已最小化到托盘",
        "confirm_clear": "确认清空",
        "confirm_clear_msg": "确定要删除所有记录吗?此操作不可恢复。",
        "history_cleared": "历史已清空",
        "deleted": "已删除",
        "copied_text": "✓ 已复制文本",
        "copied_html": "✓ 已复制富文本",
        "copied_file": "✓ 已复制文件路径",
        "copied_image": "✓ 已复制图片",
        "auto_saved": "已自动保存更改",
        "rich_text_prefix": "(富文本) ",
        "file_list": "📂 文件列表",
        "image": "🖼️ 图片",
        "context_open": "📂 打开文件",
        "context_delete": "🗑️ 删除",
        "open_failed": "打开失败",
        "file_not_found": "文件不存在或无法访问",
        "already_running": "程序已在运行",
        "already_running_msg": "ClipKeep 已经在运行中，请检查系统托盘。",
        "self_check_failed": "自检失败",
        "db_check_failed": "数据库检查失败，程序可能无法正常工作",
        "temp_check_failed": "临时目录不可写或磁盘空间不足",
        "tray_check_failed": "系统托盘不可用",
        "self_check_passed": "✓ 自检通过"
    },
    "en_US": {
        "window_title": "ClipKeep",
        "items": "History",
        "settings": "Settings",
        "clear": "Clear",
        "search_placeholder": "🔍 Search clipboard... (Ctrl+F)",
        "content_preview": "Content preview...",
        "zoom_hint": "💡 Ctrl+Scroll to Zoom | Ctrl+0 Reset",
        "ready": "Ready",
        "settings_title": "Settings",
        "always_on_top": "Always on Top",
        "theme": "Theme:",
        "theme_system": "Follow System (Default)",
        "theme_light": "Light Mode",
        "theme_dark": "Dark Mode",
        "language": "Language:",
        "language_zh": "简体中文",
        "language_en": "English",
        "max_history": "Max History Records:",
        "advanced_features": "Advanced Features & Formats",
        "save_original": "Save Original Images (No Compression)",
        "save_original_tip": "Will ignore 4MP limit and save full images. May use more storage.",
        "enable_rich_text": "Enable Rich Text (HTML)",
        "enable_file_paths": "Enable File Path Copying",
        "edge_hide": "Auto-hide at Screen Edge",
        "save": "Save",
        "cancel": "Cancel",
        "settings_saved": "Settings Saved",
        "show_window": "Show Main Window",
        "exit_app": "Exit ClipKeep",
        "minimized_to_tray": "Minimized to system tray",
        "confirm_clear": "Confirm Clear",
        "confirm_clear_msg": "Are you sure you want to delete all records? This cannot be undone.",
        "history_cleared": "History Cleared",
        "deleted": "Deleted",
        "copied_text": "✓ Text Copied",
        "copied_html": "✓ Rich Text Copied",
        "copied_file": "✓ File Path Copied",
        "copied_image": "✓ Image Copied",
        "auto_saved": "Changes Auto-saved",
        "rich_text_prefix": "(HTML) ",
        "file_list": "📂 File List",
        "image": "🖼️ Image",
        "context_open": "📂 Open File",
        "context_delete": "🗑️ Delete",
        "open_failed": "Open Failed",
        "file_not_found": "File not found or inaccessible",
        "already_running": "Already Running",
        "already_running_msg": "ClipKeep is already running. Please check the system tray.",
        "self_check_failed": "Self-check Failed",
        "db_check_failed": "Database check failed, app may not work properly",
        "temp_check_failed": "Temp directory not writable or low disk space",
        "tray_check_failed": "System tray unavailable",
        "self_check_passed": "✓ Self-check Passed"
    }
}

def tr(key: str, lang: str = "zh_CN") -> str:
    """Translation helper"""
    return TRANSLATIONS.get(lang, TRANSLATIONS["zh_CN"]).get(key, key)

# WinUI 3.0 Stylesheet
WINUI_STYLESHEET = """
QMainWindow {
    background-color: #f3f3f3;
}
QWidget {
    font-family: 'Microsoft YaHei', 'Arial', sans-serif;
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

DARK_STYLESHEET = """
QMainWindow {
    background-color: #1f1f1f;
}
QWidget {
    font-family: 'Microsoft YaHei', 'Arial', sans-serif;
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
    background-color: #005090;
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
                 fmt: str = "plain", content_hash: str = ""):
        self.id = record_id
        self.type = record_type
        self.content = content
        self.timestamp = timestamp
        self.thumbnail = thumbnail
        self.format = fmt
        self.content_hash = content_hash


class ClipboardDatabase:
    """Synchronous Database Manager."""
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = None
        self._init_database()

    def _init_database(self):
        try:
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
                    height INTEGER,
                    content_hash TEXT
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON records(timestamp DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_hash ON records(content_hash)
            """)
            self.conn.commit()
        except Exception as e:
            logging.error(f"Database init error: {e}", exc_info=True)
            raise

    def test_write(self) -> bool:
        """Test database write capability"""
        conn = None
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("INSERT INTO records (type, content, timestamp, format) VALUES (?, ?, ?, ?)",
                          ("text", "_test_", datetime.now().timestamp(), "plain"))
            test_id = cursor.lastrowid
            conn.commit()
            cursor.execute("DELETE FROM records WHERE id = ?", (test_id,))
            conn.commit()
            return True
        except Exception as e:
            logging.error(f"Database test write error: {e}", exc_info=True)
            return False
        finally:
            if conn:
                conn.close()

    def add_text_record(self, text: str, record_format: str = "plain") -> int:
        try:
            content_hash = hashlib.md5(text.encode()).hexdigest()
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO records (type, content, timestamp, format, content_hash)
                VALUES (?, ?, ?, ?, ?)
            """, ("text", text, datetime.now().timestamp(), record_format, content_hash))
            self.conn.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"Add text record error: {e}")
            return 0

    def add_image_record(self, image_data: bytes, thumbnail: bytes, fmt: str, 
                        width: int, height: int, content_hash: str) -> int:
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO records (type, content_blob, timestamp, thumbnail, format, width, height, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "image",
                image_data,
                datetime.now().timestamp(),
                thumbnail,
                fmt,
                width,
                height,
                content_hash
            ))
            self.conn.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"Add image record error: {e}")
            return 0

    def check_duplicate_hash(self, content_hash: str) -> bool:
        """Check if content hash exists in recent records"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT id FROM records 
                WHERE content_hash = ? 
                ORDER BY timestamp DESC LIMIT 1
            """, (content_hash,))
            return cursor.fetchone() is not None
        except:
            return False

    def update_text_content(self, record_id: int, new_text: str):
        try:
            cursor = self.conn.cursor()
            cursor.execute("UPDATE records SET content = ? WHERE id = ?", (new_text, record_id))
            self.conn.commit()
        except Exception as e:
            print(f"Update text error: {e}")

    def delete_record(self, record_id: int):
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM records WHERE id = ?", (record_id,))
            self.conn.commit()
        except Exception as e:
            print(f"Delete record error: {e}")

    def clear_all(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM records")
            self.conn.commit()
        except Exception as e:
            print(f"Clear all error: {e}")

    def get_count(self) -> int:
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM records")
            return cursor.fetchone()[0]
        except:
            return 0

    def trim_to_limit(self, max_count: int):
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                DELETE FROM records WHERE id NOT IN (
                    SELECT id FROM records ORDER BY timestamp DESC LIMIT ?
                )
            """, (max_count,))
            self.conn.commit()
        except Exception as e:
            print(f"Trim error: {e}")

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
    """Generic worker for database operations"""
    def __init__(self, db_path: Path, mode: str, **kwargs):
        super().__init__()
        self.db_path = db_path
        self.mode = mode
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            output = None

            if self.mode == "load_all":
                limit = self.kwargs.get("limit", 100)
                cursor.execute("""
                    SELECT id, type, content, content_blob, timestamp, thumbnail, format, content_hash
                    FROM records ORDER BY timestamp DESC LIMIT ?
                """, (limit,))
                rows = cursor.fetchall()
                records = []
                for row in rows:
                    rec_id, rec_type, txt, blob, ts, thumb, fmt, c_hash = row
                    content = txt if rec_type == "text" else None
                    records.append(ClipboardRecord(rec_id, rec_type, content, ts, thumb, fmt, c_hash or ""))
                output = records

            elif self.mode == "get_detail":
                rec_id = self.kwargs.get("record_id")
                cursor.execute("""
                    SELECT id, type, content, content_blob, timestamp, thumbnail, format, content_hash
                    FROM records WHERE id = ?
                """, (rec_id,))
                row = cursor.fetchone()
                if row:
                    rec_id, rec_type, txt, blob, ts, thumb, fmt, c_hash = row
                    if rec_type == "text":
                        content = txt
                    else:
                        image = QImage()
                        image.loadFromData(blob)
                        content = image
                    output = ClipboardRecord(rec_id, rec_type, content, ts, thumb, fmt, c_hash or "")

            conn.close()
            self.signals.result.emit(output)
        except Exception as e:
            print(f"DBWorker error: {e}")
            traceback.print_exc()
            self.signals.error.emit(sys.exc_info())
        finally:
            self.signals.finished.emit()

class ImageProcessWorker(QRunnable):
    """Worker for processing and saving images"""
    def __init__(self, image: QImage, db_path: Path, max_area: int, save_original: bool):
        super().__init__()
        self.image = image
        self.db_path = db_path
        self.max_area = max_area
        self.save_original = save_original
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            persist_image = self.image
            
            # Resize if needed
            if not self.save_original:
                area = self.image.width() * self.image.height()
                if area > self.max_area:
                    scale_factor = (self.max_area / area) ** 0.5
                    new_width = int(self.image.width() * scale_factor)
                    new_height = int(self.image.height() * scale_factor)
                    persist_image = self.image.scaled(
                        new_width, new_height,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )

            # Generate thumbnail
            thumb = persist_image.scaled(
                THUMBNAIL_SIZE, THUMBNAIL_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            thumb_array = QByteArray()
            thumb_buffer = QBuffer(thumb_array)
            thumb_buffer.open(QBuffer.OpenModeFlag.WriteOnly)
            thumb.save(thumb_buffer, "PNG")
            thumb_buffer.close()

            # Save full image
            has_alpha = persist_image.hasAlphaChannel()
            fmt = "PNG" if has_alpha else "JPEG"
            
            img_array = QByteArray()
            img_buffer = QBuffer(img_array)
            img_buffer.open(QBuffer.OpenModeFlag.WriteOnly)
            quality = -1 if fmt == "PNG" else 90
            persist_image.save(img_buffer, fmt, quality)
            img_buffer.close()

            # Calculate hash
            content_hash = hashlib.md5(img_array.data()).hexdigest()

            # Save to database
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO records (type, content_blob, timestamp, thumbnail, format, width, height, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "image",
                img_array.data(),
                datetime.now().timestamp(),
                thumb_array.data(),
                fmt,
                persist_image.width(),
                persist_image.height(),
                content_hash
            ))
            conn.commit()
            record_id = cursor.lastrowid
            conn.close()

            # Clean up
            del persist_image
            del thumb
            del img_array
            del thumb_array
            
            self.signals.result.emit(content_hash)
        except Exception as e:
            print(f"Image process error: {e}")
            traceback.print_exc()
            self.signals.error.emit(sys.exc_info())
        finally:
            self.signals.finished.emit()

class SelfCheckWorker(QRunnable):
    """Worker for self-check on startup"""
    def __init__(self, db_path: Path, temp_dir: Path):
        super().__init__()
        self.db_path = db_path
        self.temp_dir = temp_dir
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            result = {
                "db_ok": False,
                "temp_ok": False,
                "space_ok": False,
                "tray_ok": False
            }

            # Check database
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cursor.execute("INSERT INTO records (type, content, timestamp, format) VALUES (?, ?, ?, ?)",
                              ("text", "_test_", datetime.now().timestamp(), "plain"))
                test_id = cursor.lastrowid
                conn.commit()
                cursor.execute("DELETE FROM records WHERE id = ?", (test_id,))
                conn.commit()
                conn.close()
                result["db_ok"] = True
            except:
                pass

            # Check temp directory
            try:
                test_file = self.temp_dir / "_test_write"
                test_file.write_text("test")
                test_file.unlink()
                result["temp_ok"] = True
            except:
                pass

            # Check disk space
            try:
                stat = shutil.disk_usage(self.temp_dir)
                free_mb = stat.free / (1024 * 1024)
                result["space_ok"] = free_mb > MIN_FREE_SPACE_MB
            except:
                pass

            # Check system tray
            result["tray_ok"] = QSystemTrayIcon.isSystemTrayAvailable()

            self.signals.result.emit(result)
        except Exception as e:
            print(f"Self-check error: {e}")
            self.signals.error.emit(sys.exc_info())
        finally:
            self.signals.finished.emit()

# -----------------------
# Temp File Manager
# -----------------------
class TempFileManager:
    """Manage temporary files with auto-cleanup"""
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.session_dir = None
        self.init_session()

    def init_session(self):
        """Create session directory"""
        try:
            self.base_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            pid = os.getpid()
            self.session_dir = self.base_dir / f"session_{timestamp}_{pid}"
            self.session_dir.mkdir(exist_ok=True)
        except Exception as e:
            print(f"Init session error: {e}")

    def cleanup_old_files(self):
        """Remove old temp files"""
        try:
            if not self.base_dir.exists():
                return
            
            cutoff_time = datetime.now() - timedelta(days=TEMP_CLEANUP_DAYS)
            
            for item in self.base_dir.iterdir():
                if item.is_dir() and item.name.startswith("session_"):
                    try:
                        # Check modification time
                        mtime = datetime.fromtimestamp(item.stat().st_mtime)
                        if mtime < cutoff_time:
                            shutil.rmtree(item, ignore_errors=True)
                    except (PermissionError, OSError):
                        # 文件被占用时跳过
                        continue
        except Exception as e:
            logging.warning(f"Cleanup temp files warning: {e}")

    def get_temp_file(self, record_id: int, fmt: str) -> Path:
        """Get temp file path for a record"""
        if not self.session_dir:
            self.init_session()
        return self.session_dir / f"image_{record_id}.{fmt.lower()}"

# -----------------------
# Custom Widgets
# -----------------------
class DraggableListWidget(QListWidget):
    """支持拖拽内容的列表控件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_app = None
    
    def startDrag(self, supportedActions):
        """开始拖拽操作"""
        try:
            item = self.currentItem()
            if not item or not self.parent_app:
                return
            
            # 获取当前记录
            record_id = item.data(ROLE_RECORD_ID)
            rec_type = item.data(ROLE_TYPE)
            rec_format = item.data(ROLE_FORMAT)
            
            # 异步加载详细内容
            worker = DBWorker(self.parent_app.db_path, "get_detail", record_id=record_id)
            worker.signals.result.connect(lambda record: self._perform_drag(record, supportedActions))
            self.parent_app.threadpool.start(worker)
            
        except Exception as e:
            logging.error(f"Start drag error: {e}", exc_info=True)
    
    def _perform_drag(self, record, supportedActions):
        """执行拖拽"""
        try:
            if not record:
                return
            
            mime_data = QMimeData()
            
            if record.type == "text":
                if record.format == "html":
                    # 富文本：同时设置HTML和纯文本
                    mime_data.setHtml(record.content)
                    if hasattr(self.parent_app, 'strip_html_tags'):
                        plain_text = self.parent_app.strip_html_tags(record.content)
                        mime_data.setText(plain_text)
                    else:
                        mime_data.setText(record.content)
                elif record.format == "file":
                    # 文件路径
                    urls = []
                    for p in record.content.split('\n'):
                        if p.strip():
                            urls.append(QUrl.fromLocalFile(p.strip()))
                    mime_data.setUrls(urls)
                    mime_data.setText(record.content)
                else:
                    # 纯文本
                    mime_data.setText(record.content)
            
            elif record.type == "image":
                # 图片
                mime_data.setImageData(record.content)
            
            # 创建拖拽对象
            drag = QDrag(self)
            drag.setMimeData(mime_data)
            
            # 设置拖拽图标（缩略图）
            current_item = self.currentItem()
            if current_item:
                icon = current_item.icon()
                if not icon.isNull():
                    pixmap = icon.pixmap(64, 64)
                    drag.setPixmap(pixmap)
            
            # 执行拖拽
            drag.exec(supportedActions)
            
        except Exception as e:
            logging.error(f"Perform drag error: {e}", exc_info=True)

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
    """Settings Dialog"""
    def __init__(self, settings: dict, current_lang: str, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.current_lang = current_lang
        self.setWindowTitle(tr("settings_title", current_lang))
        self.setFixedWidth(400)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # General
        self.check_top = QCheckBox(tr("always_on_top", current_lang))
        self.check_top.setChecked(settings.get("window_always_on_top", False))
        form.addRow(self.check_top)

        # Theme
        self.combo_theme = QComboBox()
        self.combo_theme.addItem(tr("theme_system", current_lang), "system")
        self.combo_theme.addItem(tr("theme_light", current_lang), "light")
        self.combo_theme.addItem(tr("theme_dark", current_lang), "dark")
        current_theme = settings.get("app_theme", "system")
        idx = 0
        for i in range(self.combo_theme.count()):
            if self.combo_theme.itemData(i) == current_theme:
                idx = i
                break
        self.combo_theme.setCurrentIndex(idx)
        form.addRow(tr("theme", current_lang), self.combo_theme)

        # Language
        self.combo_lang = QComboBox()
        self.combo_lang.addItem(tr("language_zh", current_lang), "zh_CN")
        self.combo_lang.addItem(tr("language_en", current_lang), "en_US")
        lang_idx = 0 if current_lang == "zh_CN" else 1
        self.combo_lang.setCurrentIndex(lang_idx)
        form.addRow(tr("language", current_lang), self.combo_lang)

        # History Limit
        self.spin_history = QSpinBox()
        self.spin_history.setRange(10, 1000)
        self.spin_history.setSingleStep(10)
        self.spin_history.setValue(settings.get("max_history", DEFAULT_MAX_HISTORY))
        form.addRow(tr("max_history", current_lang), self.spin_history)

        layout.addLayout(form)

        # Advanced
        grp_formats = QGroupBox(tr("advanced_features", current_lang))
        fmt_layout = QVBoxLayout()

        self.check_save_orig = QCheckBox(tr("save_original", current_lang))
        self.check_save_orig.setToolTip(tr("save_original_tip", current_lang))
        self.check_save_orig.setChecked(settings.get("save_original_image", False))
        fmt_layout.addWidget(self.check_save_orig)

        self.check_rich_text = QCheckBox(tr("enable_rich_text", current_lang))
        self.check_rich_text.setChecked(settings.get("enable_rich_text", True))
        fmt_layout.addWidget(self.check_rich_text)

        self.check_files = QCheckBox(tr("enable_file_paths", current_lang))
        self.check_files.setChecked(settings.get("enable_file_paths", True))
        fmt_layout.addWidget(self.check_files)

        self.check_edge_hide = QCheckBox(tr("edge_hide", current_lang))
        self.check_edge_hide.setChecked(settings.get("edge_hide_enabled", False))
        fmt_layout.addWidget(self.check_edge_hide)

        grp_formats.setLayout(fmt_layout)
        layout.addWidget(grp_formats)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_save = QPushButton(tr("save", current_lang))
        btn_save.clicked.connect(self.accept)
        btn_save.setStyleSheet("background-color: #0078D4; color: white; border: none;")

        btn_cancel = QPushButton(tr("cancel", current_lang))
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
            "app_theme": self.combo_theme.currentData() or "system",
            "language": self.combo_lang.currentData() or "zh_CN",
            "edge_hide_enabled": self.check_edge_hide.isChecked()
        }

# -----------------------
# Main Application
# -----------------------
class ClipKeepApp(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Load icon safely
        try:
            self.setWindowIcon(QIcon(resource_path("clipkeep.ico")))
        except:
            pass

        # Core Setup
        self.current_lang = "zh_CN"
        self.setWindowTitle(f"{tr('window_title', self.current_lang)} {APP_VERSION}")
        
        # Configuration
        self.config_dir = Path.home() / ".clipkeep"
        self.config_dir.mkdir(exist_ok=True)
        self.db_path = self.config_dir / "clipboard.db"
        self.settings_file = self.config_dir / "settings.json"
        self.temp_dir = self.config_dir / "temp"

        self.settings = self.load_settings()
        self.current_lang = self.settings.get("language", "zh_CN")
        self.max_history = self.settings.get("max_history", DEFAULT_MAX_HISTORY)

        # Load window geometry from settings
        saved_geometry = self.settings.get("window_geometry")
        if saved_geometry:
            self.setGeometry(
                saved_geometry.get("x", 100),
                saved_geometry.get("y", 100),
                saved_geometry.get("width", 550),
                saved_geometry.get("height", 700)
            )
        else:
            # Default to minimum size on first launch
            self.resize(400, 500)
        
        self.setMinimumSize(400, 500)

        # Temp file manager
        self.temp_manager = TempFileManager(self.temp_dir)
        self.temp_manager.cleanup_old_files()

        # Database & Threading
        self.db = ClipboardDatabase(self.db_path)
        self.threadpool = QThreadPool()

        # State
        self.is_internal_copy = False
        self.force_quit = False
        self.current_record: Optional[ClipboardRecord] = None
        self.last_clipboard_hash = ""
        self.tray_message_shown = False  # 托盘提示是否已显示过

        # Edge Hide State
        self.is_hidden = False
        self.original_geometry = None
        self.hide_animation = None
        self.at_edge_time = None  # 记录到达边缘的时间
        self.hide_pending = False  # 是否有待执行的隐藏
        self.show_pending = False  # 是否有待执行的显示
        
        self.edge_hide_timer = QTimer()
        self.edge_hide_timer.timeout.connect(self.check_edge_hide)
        
        self.edge_hide_delay_timer = QTimer()
        self.edge_hide_delay_timer.setSingleShot(True)
        self.edge_hide_delay_timer.timeout.connect(self.execute_hide)
        
        self.edge_show_delay_timer = QTimer()
        self.edge_show_delay_timer.setSingleShot(True)
        self.edge_show_delay_timer.timeout.connect(self.execute_show)

        # Timers
        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._do_save_pending)
        self._pending_save_id = None
        self._pending_save_text = None

        # UI Initialization
        self.init_ui()
        self.setup_tray()
        self.setup_shortcuts()
        self.apply_settings()

        # Run self-check
        self.run_self_check()

        # Start monitoring
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.on_clipboard_change)

    # -----------------------
    # Self-Check
    # -----------------------
    def run_self_check(self):
        """Run startup self-check"""
        worker = SelfCheckWorker(self.db_path, self.temp_dir)
        worker.signals.result.connect(self.on_self_check_complete)
        self.threadpool.start(worker)

    def on_self_check_complete(self, result: dict):
        """Handle self-check results"""
        errors = []
        
        if not result.get("db_ok"):
            errors.append(tr("db_check_failed", self.current_lang))
        
        if not result.get("temp_ok") or not result.get("space_ok"):
            errors.append(tr("temp_check_failed", self.current_lang))
        
        if not result.get("tray_ok"):
            errors.append(tr("tray_check_failed", self.current_lang))

        if errors:
            QMessageBox.warning(
                self,
                tr("self_check_failed", self.current_lang),
                "\n".join(errors)
            )
        else:
            self.statusBar().showMessage(tr("self_check_passed", self.current_lang), 3000)
            self.refresh_history_async()

    # -----------------------
    # Single Instance
    # -----------------------
    @staticmethod
    def create_single_instance_server() -> Optional[QLocalServer]:
        """Create server for single instance"""
        # Try to connect first
        socket = QLocalSocket()
        socket.connectToServer(SINGLE_INSTANCE_KEY)
        if socket.waitForConnected(500):
            socket.close()
            return None  # Already running

        # Create server
        server = QLocalServer()
        QLocalServer.removeServer(SINGLE_INSTANCE_KEY)
        if not server.listen(SINGLE_INSTANCE_KEY):
            return None
        return server

    # -----------------------
    # Edge Hide with Animation
    # -----------------------
    def check_edge_hide(self):
        """Check if window should hide/show at screen edge"""
        if not self.settings.get("edge_hide_enabled", False):
            return
        
        if not self.isVisible() or self.isMinimized():
            return

        # 如果正在播放动画，不做任何检查
        if self.hide_animation and self.hide_animation.state() == QPropertyAnimation.State.Running:
            return

        screen = QApplication.primaryScreen().geometry()
        win_geo = self.geometry()
        cursor_pos = QCursor.pos()

        # 检查窗口是否在边缘
        at_left_edge = win_geo.x() <= EDGE_HIDE_THRESHOLD
        at_right_edge = win_geo.x() + win_geo.width() >= screen.width() - EDGE_HIDE_THRESHOLD
        at_top_edge = win_geo.y() <= EDGE_HIDE_THRESHOLD
        at_edge = at_left_edge or at_right_edge or at_top_edge

        # 检查是否应该吸附到边缘
        if not at_edge and not self.is_hidden:
            near_left = 0 < win_geo.x() <= EDGE_SNAP_DISTANCE
            near_right = screen.width() - EDGE_SNAP_DISTANCE <= win_geo.x() + win_geo.width() < screen.width()
            near_top = 0 < win_geo.y() <= EDGE_SNAP_DISTANCE
            
            if near_left or near_right or near_top:
                # 执行吸附
                snap_geo = QRect(win_geo)
                if near_left:
                    snap_geo.moveLeft(0)
                elif near_right:
                    snap_geo.moveLeft(screen.width() - win_geo.width())
                elif near_top:
                    snap_geo.moveTop(0)
                
                # 平滑吸附动画
                if not self.hide_animation:
                    self.hide_animation = QPropertyAnimation(self, b"geometry")
                    self.hide_animation.setDuration(150)
                    self.hide_animation.setStartValue(win_geo)
                    self.hide_animation.setEndValue(snap_geo)
                    self.hide_animation.setEasingCurve(QEasingCurve.Type.OutQuad)
                    self.hide_animation.finished.connect(lambda: setattr(self, 'hide_animation', None))
                    self.hide_animation.start()
                return

        if not self.is_hidden:
            # 窗口未隐藏状态
            if at_edge:
                # 窗口在边缘
                cursor_in_window = win_geo.contains(cursor_pos)
                
                if cursor_in_window:
                    # 光标在窗口内，取消任何待执行的隐藏
                    self.at_edge_time = None
                    self.hide_pending = False
                    self.edge_hide_delay_timer.stop()
                else:
                    # 光标不在窗口内，开始计时准备隐藏
                    if not self.hide_pending:
                        self.hide_pending = True
                        self.edge_hide_delay_timer.start(EDGE_HIDE_DELAY_MS)
            else:
                # 窗口不在边缘，取消隐藏
                self.at_edge_time = None
                self.hide_pending = False
                self.edge_hide_delay_timer.stop()
        else:
            # 窗口已隐藏状态
            # 检查光标是否靠近隐藏区域
            cursor_near = False
            
            if at_left_edge and cursor_pos.x() <= EDGE_DETECT_AREA:
                cursor_near = True
            elif at_right_edge and cursor_pos.x() >= screen.width() - EDGE_DETECT_AREA:
                cursor_near = True
            elif at_top_edge and cursor_pos.y() <= EDGE_DETECT_AREA:
                cursor_near = True
            
            if cursor_near:
                # 光标靠近，准备显示
                if not self.show_pending:
                    self.show_pending = True
                    self.edge_show_delay_timer.start(EDGE_SHOW_DELAY_MS)
            else:
                # 光标远离，取消显示
                self.show_pending = False
                self.edge_show_delay_timer.stop()

    def execute_hide(self):
        """执行隐藏动画"""
        self.hide_pending = False
        
        # 再次检查光标位置，确保光标确实不在窗口内
        cursor_pos = QCursor.pos()
        if self.geometry().contains(cursor_pos):
            return  # 光标回到窗口内，取消隐藏
        
        self.hide_to_edge_animated()

    def execute_show(self):
        """执行显示动画"""
        self.show_pending = False
        self.show_from_edge_animated()

    def hide_to_edge_animated(self):
        """Hide window to edge with smooth animation"""
        if self.is_hidden or self.hide_animation:
            return

        self.original_geometry = self.geometry()
        screen = QApplication.primaryScreen().geometry()
        geo = self.geometry()

        target_geo = QRect(geo)
        
        if geo.x() <= EDGE_HIDE_THRESHOLD:
            target_geo.moveLeft(-geo.width() + EDGE_SHOW_WIDTH)
        elif geo.x() + geo.width() >= screen.width() - EDGE_HIDE_THRESHOLD:
            target_geo.moveLeft(screen.width() - EDGE_SHOW_WIDTH)
        elif geo.y() <= EDGE_HIDE_THRESHOLD:
            target_geo.moveTop(-geo.height() + EDGE_SHOW_WIDTH)

        self.hide_animation = QPropertyAnimation(self, b"geometry")
        self.hide_animation.setDuration(ANIMATION_DURATION)
        self.hide_animation.setStartValue(geo)
        self.hide_animation.setEndValue(target_geo)
        self.hide_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.hide_animation.finished.connect(self.on_hide_finished)
        self.hide_animation.start()

    def on_hide_finished(self):
        """Called when hide animation finishes"""
        self.is_hidden = True
        self.hide_animation = None

    def show_from_edge_animated(self):
        """Show window from edge with smooth animation"""
        if not self.is_hidden or not self.original_geometry or self.hide_animation:
            return

        current_geo = self.geometry()
        
        self.hide_animation = QPropertyAnimation(self, b"geometry")
        self.hide_animation.setDuration(ANIMATION_DURATION)
        self.hide_animation.setStartValue(current_geo)
        self.hide_animation.setEndValue(self.original_geometry)
        self.hide_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.hide_animation.finished.connect(self.on_show_finished)
        self.hide_animation.start()

    def on_show_finished(self):
        """Called when show animation finishes"""
        self.is_hidden = False
        self.hide_animation = None
        # 显示完成后，重置状态，允许再次隐藏
        self.at_edge_time = None
        self.hide_pending = False

    # -----------------------
    # Settings Management
    # -----------------------
    def load_settings(self) -> dict:
        defaults = {
            "max_history": DEFAULT_MAX_HISTORY,
            "window_always_on_top": False,
            "save_original_image": False,
            "enable_rich_text": True,
            "enable_file_paths": True,
            "app_theme": "system",
            "language": "zh_CN",
            "edge_hide_enabled": False
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
            # 只在窗口可见且未隐藏时保存几何信息
            if self.isVisible() and not self.is_hidden:
                geo = self.geometry()
                screen = QApplication.primaryScreen().geometry()
                
                # 检查窗口是否在屏幕内
                window_in_screen = (
                    geo.x() >= 0 and 
                    geo.y() >= 0 and
                    geo.x() + geo.width() <= screen.width() and
                    geo.y() + geo.height() <= screen.height()
                )
                
                # 只有窗口完全在屏幕内才保存
                if window_in_screen:
                    self.settings["window_geometry"] = {
                        "x": geo.x(),
                        "y": geo.y(),
                        "width": geo.width(),
                        "height": geo.height()
                    }
                    logging.info(f"Saved window geometry: {geo.x()}, {geo.y()}, {geo.width()}x{geo.height()}")
                else:
                    logging.warning("Window outside screen bounds, not saving geometry")
            else:
                logging.info("Window hidden or invisible, not saving geometry")
            
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Error saving settings: {e}", exc_info=True)

    def is_system_dark(self) -> bool:
        """Detect system dark mode"""
        try:
            pal = QApplication.palette()
            bg = pal.color(QPalette.ColorRole.Window)
            r, g, b = bg.red(), bg.green(), bg.blue()
            luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
            return luminance < 128
        except:
            return False

    def get_current_stylesheet(self, theme: str) -> str:
        """Return stylesheet based on theme"""
        if theme == "light":
            return WINUI_STYLESHEET
        elif theme == "dark":
            return DARK_STYLESHEET
        else:
            return DARK_STYLESHEET if self.is_system_dark() else WINUI_STYLESHEET

    def apply_settings(self):
        # Window flags
        if self.settings.get("window_always_on_top", False):
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        else:
            self.setWindowFlags((self.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint) | Qt.WindowType.Tool)
        
        self.max_history = self.settings.get("max_history", DEFAULT_MAX_HISTORY)

        # Apply theme
        theme = self.settings.get("app_theme", "system")
        stylesheet = self.get_current_stylesheet(theme)
        self.setStyleSheet(stylesheet)

        # Widget styles
        if stylesheet is DARK_STYLESHEET:
            self.image_viewer.setStyleSheet("background-color: #1e1e1e; border: 1px dashed #333; border-radius: 6px;")
            self.zoom_hint.setStyleSheet("color: #999; font-size: 11px; margin-top: 4px;")
            self.count_label.setStyleSheet("color: #cfcfcf; font-weight: bold;")
        else:
            self.image_viewer.setStyleSheet("background-color: #fafafa; border: 1px dashed #ccc; border-radius: 6px;")
            self.zoom_hint.setStyleSheet("color: #999; font-size: 11px; margin-top: 4px;")
            self.count_label.setStyleSheet("color: #666; font-weight: bold;")

        # Start/stop edge hide timer
        if self.settings.get("edge_hide_enabled", False):
            self.edge_hide_timer.start(100)
        else:
            self.edge_hide_timer.stop()
            self.edge_hide_delay_timer.stop()
            self.edge_show_delay_timer.stop()
            if self.is_hidden and self.original_geometry:
                self.setGeometry(self.original_geometry)
                self.is_hidden = False
                self.hide_pending = False
                self.show_pending = False

        self.show()

    def update_ui_language(self):
        """Update all UI text"""
        self.setWindowTitle(f"{tr('window_title', self.current_lang)} {APP_VERSION}")
        self.btn_settings.setToolTip(tr("settings", self.current_lang))
        self.btn_clear.setText(tr("clear", self.current_lang))
        self.search_box.setPlaceholderText(tr("search_placeholder", self.current_lang))
        self.text_editor.setPlaceholderText(tr("content_preview", self.current_lang))
        self.zoom_hint.setText(tr("zoom_hint", self.current_lang))
        self.update_count_label()
        self.statusBar().showMessage(tr("ready", self.current_lang))

    def open_settings_dialog(self):
        dlg = SettingsDialog(self.settings, self.current_lang, self)
        if dlg.exec():
            new_settings = dlg.get_data()
            old_lang = self.current_lang
            self.settings.update(new_settings)
            self.current_lang = self.settings.get("language", "zh_CN")
            self.save_settings_to_file()
            
            if old_lang != self.current_lang:
                self.update_ui_language()
            
            self.apply_settings()
            self.db.trim_to_limit(self.max_history)
            self.refresh_history_async()
            self.statusBar().showMessage(tr("settings_saved", self.current_lang), 2000)

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

        self.count_label = QLabel(f"0 {tr('items', self.current_lang)}")
        self.count_label.setStyleSheet("color: #666; font-weight: bold;")
        top_bar.addWidget(self.count_label)

        top_bar.addStretch()

        self.btn_settings = QPushButton("⚙️")
        self.btn_settings.setToolTip(tr("settings", self.current_lang))
        self.btn_settings.setFixedSize(42, 32)  # 加宽按钮
        self.btn_settings.clicked.connect(self.open_settings_dialog)
        top_bar.addWidget(self.btn_settings)

        self.btn_clear = QPushButton(tr("clear", self.current_lang))
        self.btn_clear.clicked.connect(self.clear_history)
        self.btn_clear.setStyleSheet("background-color: #e81123; color: white; border: none;")
        top_bar.addWidget(self.btn_clear)

        main_layout.addLayout(top_bar)

        # Search
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(tr("search_placeholder", self.current_lang))
        self.search_box.textChanged.connect(self.filter_history)
        main_layout.addWidget(self.search_box)

        # Splitter
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(8)

        # History List
        self.history_list = DraggableListWidget()  # 使用自定义列表控件
        self.history_list.parent_app = self  # 设置父应用引用
        self.history_list.currentItemChanged.connect(self.on_item_selected)
        self.history_list.itemClicked.connect(self.on_item_clicked)
        self.history_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.history_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self.show_context_menu)
        self.history_list.setDragEnabled(True)
        self.history_list.setDefaultDropAction(Qt.DropAction.CopyAction)
        splitter.addWidget(self.history_list)

        # Detail View
        self.detail_container = QWidget()
        detail_layout = QVBoxLayout(self.detail_container)
        detail_layout.setContentsMargins(0, 0, 0, 0)

        self.text_editor = QTextEdit()
        self.text_editor.setPlaceholderText(tr("content_preview", self.current_lang))
        self.text_editor.textChanged.connect(self.on_text_edited)
        self.text_editor.hide()

        self.image_viewer = ZoomableImageLabel()
        self.image_viewer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_viewer.setStyleSheet("background-color: #fafafa; border: 1px dashed #ccc; border-radius: 6px;")
        self.image_viewer.setMinimumHeight(150)
        self.image_viewer.hide()

        self.zoom_hint = QLabel(tr("zoom_hint", self.current_lang))
        self.zoom_hint.setStyleSheet("color: #999; font-size: 11px; margin-top: 4px;")
        self.zoom_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_hint.hide()

        detail_layout.addWidget(self.text_editor)
        detail_layout.addWidget(self.image_viewer)
        detail_layout.addWidget(self.zoom_hint)

        splitter.addWidget(self.detail_container)
        splitter.setSizes([350, 250])

        main_layout.addWidget(splitter)
        self.statusBar().showMessage(tr("ready", self.current_lang))

    def setup_tray(self):
        """Setup system tray"""
        self.tray_icon = QSystemTrayIcon(self)

        if Path(resource_path("clipkeep_tray.png")).exists():
            tray_icon = QIcon(resource_path("clipkeep_tray.png"))
        else:
            tray_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)

        self.tray_icon.setIcon(tray_icon)

        tray_menu = QMenu()
        show_action = QAction(tr("show_window", self.current_lang), self)
        show_action.triggered.connect(self.showNormal)
        tray_menu.addAction(show_action)

        settings_action = QAction(tr("settings", self.current_lang), self)
        settings_action.triggered.connect(self.open_settings_dialog)
        tray_menu.addAction(settings_action)

        tray_menu.addSeparator()

        quit_action = QAction(tr("exit_app", self.current_lang), self)
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
        """Minimize to tray"""
        if self.force_quit:
            event.accept()
        else:
            event.ignore()
            self.hide()
            self.tray_icon.showMessage(
                APP_NAME,
                tr("minimized_to_tray", self.current_lang),
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )

    def quit_application(self):
        """Exit application"""
        # Save window geometry before quit
        self.save_settings_to_file()
        self.force_quit = True
        QApplication.quit()

    def setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+F"), self, self.search_box.setFocus)
        QShortcut(QKeySequence.StandardKey.Delete, self, self.delete_selected)
        QShortcut(QKeySequence("Escape"), self, self.clear_search)
        QShortcut(QKeySequence("Ctrl+Shift+Del"), self, self.clear_history)
        QShortcut(QKeySequence("Ctrl+0"), self, lambda: self.image_viewer.reset_zoom())

    # -----------------------
    # Data Loading
    # -----------------------
    def refresh_history_async(self):
        """Load history list"""
        worker = DBWorker(self.db_path, "load_all", limit=self.max_history)
        worker.signals.result.connect(self.on_history_loaded)
        self.threadpool.start(worker)

    def strip_html_tags(self, html: str) -> str:
        """Remove HTML tags"""
        try:
            html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r'<[^>]+>', '', html)
            html = html.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
            html = re.sub(r'\s+', ' ', html).strip()
            return html
        except:
            return html[:100]

    def on_history_loaded(self, records: List[ClipboardRecord]):
        self.history_list.clear()

        for rec in records:
            if rec.type == "text":
                if rec.format == "file":
                    line_count = rec.content.count('\n') + 1
                    first_file = rec.content.split('\n')[0] if rec.content else ""
                    file_name = Path(first_file).name if first_file else "..."
                    display_text = f"{tr('file_list', self.current_lang)} ({line_count}): {file_name}"
                    icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
                elif rec.format == "html":
                    plain_text = self.strip_html_tags(rec.content)
                    preview = plain_text[:80].replace("\n", " ")
                    display_text = tr("rich_text_prefix", self.current_lang) + preview
                    icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
                else:
                    display_text = rec.content[:80].replace("\n", " ")
                    icon = QIcon()

                item = QListWidgetItem(display_text)
                item.setData(ROLE_TYPE, "text")

            elif rec.type == "image":
                pix = QPixmap()
                if rec.thumbnail:
                    pix.loadFromData(rec.thumbnail)
                icon = QIcon(pix)
                item = QListWidgetItem(tr("image", self.current_lang))
                item.setData(ROLE_TYPE, "image")

            item.setData(ROLE_RECORD_ID, rec.id)
            item.setData(ROLE_TIMESTAMP, rec.timestamp)
            item.setData(ROLE_FORMAT, rec.format)
            item.setData(ROLE_CONTENT_HASH, rec.content_hash)
            item.setIcon(icon)
            
            # 设置拖拽数据
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsDragEnabled)

            self.history_list.addItem(item)

        self.update_count_label()

    def on_item_selected(self, current, previous):
        """Load detail when item selected"""
        if not current:
            self.clear_detail_view()
            return

        record_id = current.data(ROLE_RECORD_ID)

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
    # Clipboard Operations
    # -----------------------
    def on_item_clicked(self, item):
        """Single click to copy"""
        self.copy_selected_to_system()

    def on_item_double_clicked(self, item):
        """Double click to open"""
        if not self.current_record:
            return

        if self.current_record.type == "text" and self.current_record.format == "file":
            self.open_file_path()
        elif self.current_record.type == "image":
            self.open_temp_image()

    def on_clipboard_change(self):
        if self.is_internal_copy:
            self.is_internal_copy = False
            return

        mime_data = self.clipboard.mimeData()
        
        # Priority 1: Images
        if mime_data.hasImage():
            image = self.clipboard.image()
            if not image.isNull():
                byte_array = QByteArray()
                buffer = QBuffer(byte_array)
                buffer.open(QBuffer.OpenModeFlag.WriteOnly)
                image.save(buffer, "PNG")
                buffer.close()
                current_hash = hashlib.md5(byte_array.data()).hexdigest()
                
                if current_hash != self.last_clipboard_hash and not self.db.check_duplicate_hash(current_hash):
                    self.last_clipboard_hash = current_hash
                    self.add_image_record_async(image)
                return

        # Priority 2: Files
        if self.settings.get("enable_file_paths") and mime_data.hasUrls():
            urls = mime_data.urls()
            local_files = [u.toLocalFile() for u in urls if u.isLocalFile()]
            if local_files:
                content = "\n".join(local_files)
                current_hash = hashlib.md5(content.encode()).hexdigest()
                
                if current_hash != self.last_clipboard_hash and not self.db.check_duplicate_hash(current_hash):
                    self.last_clipboard_hash = current_hash
                    self.add_text_record(content, "file")
                return

        # Priority 3: HTML
        if self.settings.get("enable_rich_text") and mime_data.hasHtml():
            html_content = mime_data.html()
            if len(html_content) > 20:
                current_hash = hashlib.md5(html_content.encode()).hexdigest()
                
                if current_hash != self.last_clipboard_hash and not self.db.check_duplicate_hash(current_hash):
                    self.last_clipboard_hash = current_hash
                    self.add_text_record(html_content, "html")
                return

        # Priority 4: Text
        if mime_data.hasText():
            text = self.clipboard.text().strip()
            if text:
                current_hash = hashlib.md5(text.encode()).hexdigest()
                
                if current_hash != self.last_clipboard_hash and not self.db.check_duplicate_hash(current_hash):
                    self.last_clipboard_hash = current_hash
                    self.add_text_record(text, "plain")

    def add_text_record(self, text: str, fmt: str):
        try:
            self.db.add_text_record(text, fmt)
            self.db.trim_to_limit(self.max_history)
            self.refresh_history_async()
            # 新内容添加后，滚动到顶部
            QTimer.singleShot(100, lambda: self.history_list.scrollToTop())
        except Exception as e:
            print(f"Add text error: {e}")

    def add_image_record_async(self, image: QImage):
        """Add image using worker thread"""
        try:
            worker = ImageProcessWorker(
                image,
                self.db_path,
                MAX_IMAGE_AREA_PIXELS,
                self.settings.get("save_original_image", False)
            )
            worker.signals.result.connect(self.on_image_saved)
            worker.signals.finished.connect(lambda: self.db.trim_to_limit(self.max_history))
            self.threadpool.start(worker)
        except Exception as e:
            print(f"Add image error: {e}")

    def on_image_saved(self, content_hash: str):
        """Called when image is saved"""
        self.refresh_history_async()
        # 新内容添加后，滚动到顶部
        QTimer.singleShot(100, lambda: self.history_list.scrollToTop())

    def copy_selected_to_system(self):
        if not self.current_record:
            return

        try:
            self.is_internal_copy = True
            
            if self.current_record.type == "text":
                if self.current_record.format == "html":
                    # 创建新的 MimeData 对象
                    mime_data = QMimeData()
                    mime_data.setHtml(self.current_record.content)
                    # 同时设置纯文本作为后备
                    plain_text = self.strip_html_tags(self.current_record.content)
                    mime_data.setText(plain_text)
                    self.clipboard.setMimeData(mime_data)
                    self.statusBar().showMessage(tr("copied_html", self.current_lang), 2000)
                elif self.current_record.format == "file":
                    urls = []
                    paths = self.current_record.content.split('\n')
                    for p in paths:
                        if p.strip():
                            urls.append(QUrl.fromLocalFile(p.strip()))

                    mime_data = QMimeData()
                    mime_data.setUrls(urls)
                    mime_data.setText(self.current_record.content)
                    self.clipboard.setMimeData(mime_data)
                    self.statusBar().showMessage(tr("copied_file", self.current_lang), 2000)
                else:
                    self.clipboard.setText(self.current_record.content)
                    self.statusBar().showMessage(tr("copied_text", self.current_lang), 2000)

            elif self.current_record.type == "image":
                self.clipboard.setImage(self.current_record.content)
                self.statusBar().showMessage(tr("copied_image", self.current_lang), 2000)
        except Exception as e:
            logging.error(f"Copy error: {e}", exc_info=True)
            QMessageBox.critical(self, "Copy Error", f"Failed to copy: {str(e)}")
            self.statusBar().showMessage(f"Copy failed: {str(e)}", 3000)

    def open_file_path(self):
        """Open file with default application"""
        try:
            if not self.current_record or self.current_record.format != "file":
                return

            paths = self.current_record.content.split('\n')
            for path_str in paths:
                path_str = path_str.strip()
                if not path_str:
                    continue
                
                file_path = Path(path_str)
                if file_path.exists():
                    QDesktopServices.openUrl(QUrl.fromLocalFile(str(file_path)))
                else:
                    QMessageBox.warning(
                        self,
                        tr("open_failed", self.current_lang),
                        f"{tr('file_not_found', self.current_lang)}: {path_str}"
                    )
                break  # Only open first file
        except Exception as e:
            logging.error(f"Open file error: {e}", exc_info=True)
            QMessageBox.critical(self, tr("open_failed", self.current_lang), str(e))

    def open_temp_image(self):
        """Open image in default viewer"""
        try:
            if not self.current_record or self.current_record.type != "image":
                return
            
            if not isinstance(self.current_record.content, QImage):
                return

            fmt = self.current_record.format.lower()
            temp_file = self.temp_manager.get_temp_file(self.current_record.id, fmt)
            
            # Save and release
            success = self.current_record.content.save(str(temp_file), self.current_record.format)
            
            if success:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(temp_file)))
            else:
                QMessageBox.warning(self, tr("open_failed", self.current_lang), "Failed to save temp image")
                
        except Exception as e:
            logging.error(f"Open image error: {e}", exc_info=True)
            QMessageBox.critical(self, tr("open_failed", self.current_lang), str(e))

    def delete_selected(self):
        item = self.history_list.currentItem()
        if not item:
            return

        try:
            row = self.history_list.row(item)
            record_id = item.data(ROLE_RECORD_ID)

            self.db.delete_record(record_id)
            self.history_list.takeItem(row)
            self.clear_detail_view()
            self.update_count_label()
            self.statusBar().showMessage(tr("deleted", self.current_lang), 1500)
        except Exception as e:
            print(f"Delete error: {e}")

    def clear_history(self):
        if self.db.get_count() == 0:
            return

        reply = QMessageBox.question(
            self, tr("confirm_clear", self.current_lang),
            tr("confirm_clear_msg", self.current_lang),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.db.clear_all()
                self.history_list.clear()
                self.clear_detail_view()
                self.update_count_label()
                self.statusBar().showMessage(tr("history_cleared", self.current_lang), 2000)
            except Exception as e:
                print(f"Clear error: {e}")

    # -----------------------
    # UI Helpers
    # -----------------------
    def update_count_label(self):
        count = self.history_list.count()
        self.count_label.setText(f"{tr('items', self.current_lang)}: {count} / {self.max_history}")

    def filter_history(self, text):
        """Filter history list using case-insensitive search"""
        search_text = text.lower()
        for i in range(self.history_list.count()):
            item = self.history_list.item(i)
            item_text = item.text().lower()
            # 搜索项目文本
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
        
        rec_type = item.data(ROLE_TYPE)
        rec_format = item.data(ROLE_FORMAT)
        if (rec_type == "text" and rec_format == "file") or rec_type == "image":
            menu.addAction(tr("context_open", self.current_lang), 
                         lambda: self.on_item_double_clicked(item))
        
        menu.addAction(tr("context_delete", self.current_lang), self.delete_selected)

        ts = item.data(ROLE_TIMESTAMP)
        time_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        info_action = QAction(f"⏰ {time_str}", self)
        info_action.setEnabled(False)
        menu.addSeparator()
        menu.addAction(info_action)

        menu.exec(self.history_list.mapToGlobal(pos))

    def on_text_edited(self):
        """Save text with debounce"""
        if not self.current_record or self.current_record.type != "text":
            return

        try:
            if self.current_record.format == "html":
                new_text = self.text_editor.toHtml()
            else:
                new_text = self.text_editor.toPlainText()

            self._pending_save_id = self.current_record.id
            self._pending_save_text = new_text
            self._save_timer.start(SAVE_DEBOUNCE_MS)
        except Exception as e:
            print(f"Text edit error: {e}")

    def _do_save_pending(self):
        if self._pending_save_id and self._pending_save_text is not None:
            try:
                self.db.update_text_content(self._pending_save_id, self._pending_save_text)
                self._pending_save_id = None
                self._pending_save_text = None
                self.statusBar().showMessage(tr("auto_saved", self.current_lang), 1000)
            except Exception as e:
                print(f"Save error: {e}")

if __name__ == "__main__":
    try:
        logging.info("=" * 50)
        logging.info("ClipKeep Starting...")
        logging.info(f"Python version: {sys.version}")
        logging.info(f"Working directory: {os.getcwd()}")
        
        # Single instance check
        logging.info("Creating QApplication...")
        app = QApplication(sys.argv)
        
        # 启用字体抗锯齿和渲染优化
        app.setFont(app.font())  # 使用系统默认字体
        
        # 设置字体渲染策略（改善文字显示）
        from PyQt6.QtGui import QFont
        font = app.font()
        font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        app.setFont(font)
        
        logging.info("Checking single instance...")
        server = ClipKeepApp.create_single_instance_server()
        if server is None:
            logging.warning("Another instance is already running")
            QMessageBox.warning(
                None,
                tr("already_running", "zh_CN"),
                tr("already_running_msg", "zh_CN")
            )
            sys.exit(0)

        logging.info("Setting application style...")
        app.setStyle("Fusion")
        app.setQuitOnLastWindowClosed(False)

        logging.info("Loading application icon...")
        try:
            app_icon = QIcon(resource_path("clipkeep.ico"))
            if not app_icon.isNull():
                logging.info("Icon loaded successfully")
        except Exception as icon_error:
            logging.warning(f"Failed to load custom icon: {icon_error}")
            app_icon = app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        app.setWindowIcon(app_icon)

        logging.info("Creating main window...")
        window = ClipKeepApp()
        
        logging.info("Showing main window...")
        window.show()
        
        logging.info("ClipKeep started successfully!")
        logging.info("=" * 50)
        
        sys.exit(app.exec())
        
    except Exception as e:
        error_msg = f"Critical startup error: {e}\n{traceback.format_exc()}"
        logging.critical(error_msg)
        
        # 尝试显示错误对话框
        try:
            if 'app' in locals():
                QMessageBox.critical(
                    None, 
                    "ClipKeep Startup Error", 
                    f"Failed to start ClipKeep:\n\n{str(e)}\n\nCheck log file at:\n{config_dir / 'clipkeep.log'}"
                )
        except:
            pass
        
        # 打印到控制台
        print("\n" + "="*50)
        print("CRITICAL ERROR:")
        print(error_msg)
        print("="*50 + "\n")
        
        sys.exit(1)
