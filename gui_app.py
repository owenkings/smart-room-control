# -*- coding: utf-8 -*-
"""
智能教室测控系统 - 本地 GUI 版本（PyQt6）

亮色主题，QSplitter 自适应布局，CJK 字体支持。
通过 DecisionEngine 统一控制所有硬件模块。

运行: python gui_app.py
依赖: pip install PyQt6
"""

# ── 编码声明（防止 Windows 控制台乱码）──────────────────────────────
import sys
import os
import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import time
import signal
import logging
import numpy as np

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QComboBox, QSlider, QTextEdit, QSizePolicy,
    QSplitter, QStatusBar, QScrollArea, QFrame, QLineEdit,
    QCheckBox, QSpinBox, QDoubleSpinBox, QProgressBar,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QImage, QPixmap, QFont, QIcon, QFontDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("gui")


# ── 亮色主题颜色常量 ─────────────────────────────────────────────────
BG_WHITE = "#ffffff"
BG_LIGHT = "#f5f7fa"
CARD_BG = "#ffffff"
BORDER = "#e0e4e8"
ACCENT = "#2979ff"
ACCENT_HOVER = "#1565c0"
GREEN = "#43a047"
RED = "#e53935"
AMBER = "#f9a825"
TEXT_DARK = "#212121"
TEXT_DIM = "#757575"

# ── 亮色 QSS 样式表 ──────────────────────────────────────────────────
STYLE = f"""
/* ── 全局基础 ── */
* {{
    font-size: 12px;
    color: {TEXT_DARK};
    font-family: "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif;
}}
QMainWindow, QWidget {{
    background-color: {BG_LIGHT};
}}
QScrollArea, QScrollArea > QWidget > QWidget {{
    background-color: {BG_LIGHT};
}}

/* ── GroupBox 卡片 ── */
QGroupBox {{
    background-color: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: 10px;
    margin-top: 14px;
    padding: 14px 10px 10px 10px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 3px 10px;
    background-color: {ACCENT};
    color: white;
    border-radius: 5px;
    font-weight: bold;
    font-size: 12px;
}}

/* ── 按钮 ── */
QPushButton {{
    background-color: {BG_WHITE};
    color: {TEXT_DARK};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 12px;
    min-height: 26px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: #e8f4fd;
    border-color: {ACCENT};
    color: {ACCENT};
}}
QPushButton:pressed {{
    background-color: {ACCENT};
    color: white;
    border-color: {ACCENT};
}}
QPushButton[role="on"] {{
    background-color: {GREEN};
    color: white;
    font-weight: bold;
    border-color: {GREEN};
}}
QPushButton[role="on"]:hover {{ background-color: #2da44e; }}
QPushButton[role="off"] {{
    background-color: {RED};
    color: white;
    font-weight: bold;
    border-color: {RED};
}}
QPushButton[role="off"]:hover {{ background-color: #d32f2f; }}
QPushButton[role="accent"] {{
    background-color: {ACCENT};
    color: white;
    font-weight: bold;
    border-color: {ACCENT};
}}
QPushButton[role="accent"]:hover {{ background-color: {ACCENT_HOVER}; }}
QPushButton[role="mode_active"] {{
    background-color: {ACCENT};
    color: white;
    font-weight: bold;
    border-color: {ACCENT};
}}
QPushButton[role="mode_manual_active"] {{
    background-color: {AMBER};
    color: white;
    font-weight: bold;
    border-color: {AMBER};
}}

/* ── 输入框 ── */
QLineEdit {{
    background-color: {BG_WHITE};
    color: {TEXT_DARK};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 9px;
    min-height: 26px;
    selection-background-color: {ACCENT};
    selection-color: white;
}}
QLineEdit:focus {{
    border: 2px solid {ACCENT};
    padding: 4px 8px;
    background-color: #fafcff;
}}
QLineEdit:hover:!focus {{
    border-color: #b0c8e8;
}}

/* ── SpinBox ── */
QSpinBox, QDoubleSpinBox {{
    background-color: {BG_WHITE};
    color: {TEXT_DARK};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px 6px;
    min-height: 26px;
    selection-background-color: {ACCENT};
}}
QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 2px solid {ACCENT};
    background-color: #fafcff;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 18px;
    border-left: 1px solid {BORDER};
    border-top-right-radius: 5px;
    background: {BG_LIGHT};
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {{
    background: #e8f4fd;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 18px;
    border-left: 1px solid {BORDER};
    border-bottom-right-radius: 5px;
    background: {BG_LIGHT};
}}
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background: #e8f4fd;
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    width: 8px; height: 8px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    width: 8px; height: 8px;
}}

/* ── ComboBox ── */
QComboBox {{
    background-color: {BG_WHITE};
    color: {TEXT_DARK};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 9px;
    min-height: 26px;
}}
QComboBox:hover {{ border-color: #b0c8e8; }}
QComboBox:focus {{ border: 2px solid {ACCENT}; background-color: #fafcff; }}
QComboBox::drop-down {{
    border: none;
    width: 22px;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
    background: {BG_LIGHT};
}}
QComboBox::drop-down:hover {{ background: #e8f4fd; }}
QComboBox QAbstractItemView {{
    background-color: {BG_WHITE};
    color: {TEXT_DARK};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 2px;
    selection-background-color: #e8f4fd;
    selection-color: {ACCENT};
    outline: none;
}}

/* ── CheckBox ── */
QCheckBox {{
    spacing: 8px;
    padding: 3px 6px;
    border-radius: 5px;
    color: {TEXT_DARK};
}}
QCheckBox:hover {{
    background-color: #e8f4fd;
}}
QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border-radius: 4px;
    border: 1.5px solid {BORDER};
    background: {BG_WHITE};
}}
QCheckBox::indicator:hover {{
    border-color: {ACCENT};
}}
QCheckBox::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
    image: url(none);
}}

/* ── Slider ── */
QSlider::groove:horizontal {{
    height: 5px;
    background: {BORDER};
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT};
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
    border: 2px solid white;
}}
QSlider::handle:horizontal:hover {{
    background: {ACCENT_HOVER};
    width: 18px;
    height: 18px;
    margin: -7px 0;
    border-radius: 9px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 3px;
}}

/* ── TextEdit (日志) ── */
QTextEdit {{
    background-color: #1e2430;
    color: #a8c0d6;
    border: 1px solid {BORDER};
    border-radius: 8px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 11px;
    padding: 6px;
    selection-background-color: {ACCENT};
}}

/* ── Label ── */
QLabel {{
    background: transparent;
    border: none;
}}

/* ── ProgressBar ── */
QProgressBar {{
    background-color: {BG_LIGHT};
    border: 1px solid {BORDER};
    border-radius: 5px;
    height: 14px;
    text-align: center;
    font-size: 10px;
    color: {TEXT_DIM};
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {ACCENT}, stop:1 #64b5f6);
    border-radius: 4px;
}}

/* ── ScrollBar ── */
QScrollBar:vertical {{
    background: transparent;
    width: 7px;
    border-radius: 4px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #c8d8e8;
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: #a0b8cc;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

/* ── Splitter ── */
QSplitter::handle {{
    background-color: {BORDER};
    border-radius: 2px;
}}
QSplitter::handle:horizontal {{
    width: 4px;
    margin: 4px 0;
}}
QSplitter::handle:vertical {{
    height: 4px;
    margin: 0 4px;
}}
QSplitter::handle:hover {{
    background-color: {ACCENT};
}}

/* ── StatusBar ── */
QStatusBar {{
    background-color: {BG_WHITE};
    color: {TEXT_DIM};
    font-size: 11px;
    border-top: 1px solid {BORDER};
}}
"""


# ══════════════════════════════════════════════════════════════════════
#  模型列表（显示名 → 文件名，分离存储）
# ══════════════════════════════════════════════════════════════════════
MODEL_ENTRIES = [
    ("-- YOLOv8  经典稳定 ----------------", "", True),
    ("v8n   Nano    3.2M   最快 速度优先", "yolov8n.pt", False),
    ("v8s   Small  11.2M   快   均衡", "yolov8s.pt", False),
    ("v8m   Medium 25.9M   均衡", "yolov8m.pt", False),
    ("v8l   Large  43.7M   精准", "yolov8l.pt", False),
    ("v8x   XLarge 68.2M   最精准 精度优先", "yolov8x.pt", False),
    ("-- YOLO11  精度更高 ----------------", "", True),
    ("v11n  Nano    2.6M   最快", "yolo11n.pt", False),
    ("v11s  Small   9.4M   快", "yolo11s.pt", False),
    ("v11m  Medium 20.1M   均衡", "yolo11m.pt", False),
    ("v11l  Large  25.3M   精准", "yolo11l.pt", False),
    ("v11x  XLarge 56.9M   最精准", "yolo11x.pt", False),
    ("-- YOLO26  最新一代 ----------------", "", True),
    ("v26n  Nano    2.4M   最快", "yolo26n.pt", False),
    ("v26s  Small   9.5M   快", "yolo26s.pt", False),
    ("v26m  Medium 20.4M   均衡", "yolo26m.pt", False),
    ("v26l  Large  24.8M   精准", "yolo26l.pt", False),
    ("v26x  XLarge 55.7M   最精准", "yolo26x.pt", False),
]


# ══════════════════════════════════════════════════════════════════════
#  后台线程
# ══════════════════════════════════════════════════════════════════════

class CaptureThread(QThread):
    """全速读取最新帧，通过信号发给主线程渲染"""
    frame_ready = pyqtSignal(np.ndarray)

    def __init__(self, detector):
        super().__init__()
        self.detector = detector
        self._running = True

    def run(self):
        interval = 1.0 / 30
        while self._running:
            t0 = time.perf_counter()
            frame = self.detector.get_latest_frame()
            if frame is not None:
                self.frame_ready.emit(frame)
            sleep_ms = max(1, int((interval - (time.perf_counter() - t0)) * 1000))
            self.msleep(sleep_ms)

    def stop(self):
        self._running = False
        self.wait(2000)


class StatusThread(QThread):
    """每秒拉取系统状态"""
    status_ready = pyqtSignal(dict)

    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self._running = True

    def run(self):
        while self._running:
            try:
                self.status_ready.emit(self.engine.get_state())
            except Exception as e:
                logger.debug(f"状态获取失败: {e}")
            self.msleep(1000)

    def stop(self):
        self._running = False
        self.wait(2000)


# ══════════════════════════════════════════════════════════════════════
#  辅助函数
# ══════════════════════════════════════════════════════════════════════


class _QtLogHandler(logging.Handler):
    """将 logging 输出路由到 QTextEdit 的自定义 Handler。

    使用信号机制确保线程安全（后台线程的日志也能正确显示）。
    """

    def __init__(self, text_widget: QTextEdit):
        super().__init__()
        self._widget = text_widget
        # 限制最大行数，防止内存无限增长
        self._max_lines = 200

    def emit(self, record):
        try:
            msg = self.format(record)
            # 使用 QTimer.singleShot 确保在主线程中更新 UI
            QTimer.singleShot(0, lambda: self._append(msg))
        except Exception:
            self.handleError(record)

    def _append(self, msg: str):
        """在主线程中追加日志文本"""
        self._widget.append(msg)
        # 自动滚动到底部
        scrollbar = self._widget.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        # 限制行数
        doc = self._widget.document()
        if doc.blockCount() > self._max_lines:
            cursor = self._widget.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.movePosition(
                cursor.MoveOperation.Down, cursor.MoveMode.KeepAnchor,
                doc.blockCount() - self._max_lines
            )
            cursor.removeSelectedText()
            cursor.deleteChar()  # 删除多余换行

def _lbl(text, color=TEXT_DARK, bold=False, size=13, mono=False):
    """快速创建样式化 QLabel — 强制透明背景，避免继承父控件颜色"""
    w = QLabel(text)
    w.setStyleSheet(
        f"color:{color};"
        f"font-size:{size}px;"
        f"background:transparent;"
        f"border:none;"
        f"padding:1px 3px;"
        f"{'font-weight:bold;' if bold else ''}"
        f"{'font-family:Consolas,monospace;' if mono else ''}"
    )
    if not mono:
        w.setWordWrap(True)
    return w


def _sep():
    """水平分割线"""
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"color:{BORDER};")
    return line


def _btn(text, role="normal", width=None):
    b = QPushButton(text)
    b.setProperty("role", role)
    b.style().unpolish(b)
    b.style().polish(b)
    if width:
        b.setFixedWidth(width)
    return b


# ══════════════════════════════════════════════════════════════════════
#  主窗口
# ══════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):

    def __init__(self, engine):
        """
        Args:
            engine: src.decision_engine.DecisionEngine 实例
        """
        super().__init__()
        self.engine = engine

        self.setWindowTitle("智能教室测控系统")
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        self.compact_ui = bool(available and available.width() < 1100)
        if available and available.width() <= 1280:
            self.setMinimumSize(760, 500)
            self.resize(min(1100, available.width()), min(700, available.height()))
        else:
            self.setMinimumSize(1100, 680)
            self.resize(1360, 820)
        self.setStyleSheet(STYLE)

        # 加载图标
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "app_icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._build_ui()
        self._apply_saved_settings()
        self._setup_log_handler()
        self._start_threads()

    # ── 布局构建 ──────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ── 三列布局：信息列 | 视频+日志列 | 控制面板列 ──
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setHandleWidth(4)

        # ── 左侧信息列（人员检测 + 环境传感器 + 性能 + 模型切换，固定宽度，不可滚动）──
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 4, 0)
        info_layout.setSpacing(8)
        info_layout.addWidget(self._build_detection_card())
        info_layout.addWidget(self._build_env_card())
        info_layout.addWidget(self._build_perf_card())
        info_layout.addWidget(self._build_model_card())
        info_layout.addStretch()

        # ── 中间列：视频 + 日志 ──
        mid_widget = QWidget()
        mid_layout = QVBoxLayout(mid_widget)
        mid_layout.setContentsMargins(0, 0, 4, 0)
        mid_layout.setSpacing(8)

        v_splitter = QSplitter(Qt.Orientation.Vertical)
        v_splitter.addWidget(self._build_video_card())
        v_splitter.addWidget(self._build_log_card())
        v_splitter.setStretchFactor(0, 7)
        v_splitter.setStretchFactor(1, 1)
        mid_layout.addWidget(v_splitter)

        # ── 右侧：控制面板（可滚动）──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(260)  # 防止右列被拖得过窄导致文字溢出
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        right_widget = QWidget()
        right_widget.setMinimumWidth(250)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.setSpacing(8)
        right_layout.addWidget(self._build_servo_card())
        right_layout.addWidget(self._build_servo_calibration_card())
        right_layout.addWidget(self._build_light_threshold_card())
        right_layout.addWidget(self._build_conditions_card())
        right_layout.addWidget(self._build_time_fallback_card())
        right_layout.addWidget(self._build_temperature_card())
        right_layout.addWidget(self._build_ir_card())
        right_layout.addWidget(self._build_ir_wizard_card())
        right_layout.addStretch()
        scroll.setWidget(right_widget)

        main_splitter.addWidget(info_widget)
        main_splitter.addWidget(mid_widget)
        main_splitter.addWidget(scroll)

        # 比例：信息列 ~160px | 视频列 ~60% | 控制列 ~30%
        total_width = self.width() if self.width() > 0 else 1360
        main_splitter.setSizes([160, int((total_width - 160) * 0.62), int((total_width - 160) * 0.38)])
        main_splitter.setStretchFactor(0, 0)   # 信息列不随窗口拉伸
        main_splitter.setStretchFactor(1, 3)   # 视频列优先拉伸
        main_splitter.setStretchFactor(2, 2)   # 控制列次之

        root.addWidget(main_splitter)

        # 状态栏
        sb = QStatusBar()
        self.setStatusBar(sb)
        self.lbl_status = QLabel("系统初始化中…")
        self.lbl_status.setStyleSheet(f"color:{TEXT_DIM};font-size:11px;")
        sb.addWidget(self.lbl_status)

    # ── 日志处理器 ────────────────────────────────────────────────────

    def _setup_log_handler(self):
        """将 Python logging 输出路由到 GUI 的操作日志面板"""
        handler = _QtLogHandler(self.log_text)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%H:%M:%S",
        ))
        handler.setLevel(logging.INFO)
        # 添加到根 logger
        logging.getLogger().addHandler(handler)

    # ── 视频卡片 ──────────────────────────────────────────────────────

    def _build_video_card(self):
        box = QGroupBox("📹 实时监控画面")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(6, 14, 6, 6)
        layout.setSpacing(6)

        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.video_label.setStyleSheet(
            f"background:{BG_LIGHT};border-radius:6px;border:1px solid {BORDER};")
        self.video_label.setMinimumHeight(320)
        layout.addWidget(self.video_label, stretch=1)
        return box

    # ── 日志卡片 ──────────────────────────────────────────────────────

    def _build_log_card(self):
        box = QGroupBox("📋 操作日志")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(6, 14, 6, 6)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        return box

    # ── 人员检测卡片 ──────────────────────────────────────────────────

    def _build_detection_card(self):
        box = QGroupBox("👤 人员检测")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 16, 10, 10)
        layout.setSpacing(8)

        # 大数字
        self.lbl_count = QLabel("0")
        self.lbl_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_count.setFont(QFont("Consolas", 42, QFont.Weight.Bold))
        self.lbl_count.setStyleSheet(f"color:{ACCENT};")
        layout.addWidget(self.lbl_count)

        # 状态行
        row1 = QHBoxLayout()
        row1.addWidget(_lbl("在场状态:", TEXT_DIM))
        self.lbl_presence = _lbl("—", TEXT_DARK, bold=True)
        row1.addWidget(self.lbl_presence)
        row1.addStretch()
        layout.addLayout(row1)

        layout.addWidget(_sep())

        # 模式切换
        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        self.btn_auto = QPushButton("自动模式")
        self.btn_manual = QPushButton("手动模式")
        self.btn_auto.clicked.connect(lambda: self._set_mode("AUTO"))
        self.btn_manual.clicked.connect(lambda: self._set_mode("MANUAL"))
        mode_row.addWidget(self.btn_auto)
        mode_row.addWidget(self.btn_manual)
        layout.addLayout(mode_row)

        return box

    # ── 环境传感器卡片 ────────────────────────────────────────────────

    def _build_env_card(self):
        box = QGroupBox("🌡️ 环境传感器")
        grid = QGridLayout(box)
        grid.setContentsMargins(10, 16, 10, 10)
        grid.setSpacing(8)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        grid.addWidget(_lbl("温度:", TEXT_DIM), 0, 0)
        self.lbl_temp = _lbl("—°C", TEXT_DARK, bold=True, mono=True)
        grid.addWidget(self.lbl_temp, 0, 1)

        grid.addWidget(_lbl("湿度:", TEXT_DIM), 0, 2)
        self.lbl_humi = _lbl("—%", TEXT_DARK, bold=True, mono=True)
        grid.addWidget(self.lbl_humi, 0, 3)

        grid.addWidget(_lbl("光照:", TEXT_DIM), 1, 0)
        self.lbl_lux = _lbl("— lux", TEXT_DARK, bold=True, mono=True)
        grid.addWidget(self.lbl_lux, 1, 1)

        grid.addWidget(_lbl("灯光:", TEXT_DIM), 1, 2)
        self.lbl_light = _lbl("关闭", RED, bold=True)
        grid.addWidget(self.lbl_light, 1, 3)

        return box

    # ── 性能监控卡片 ──────────────────────────────────────────────────

    def _build_perf_card(self):
        box = QGroupBox("📊 性能监控")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 16, 10, 10)
        layout.setSpacing(6)

        row_fps = QHBoxLayout()
        row_fps.addWidget(_lbl("帧率:", TEXT_DIM, size=11))
        self.lbl_fps = _lbl("— fps", TEXT_DARK, bold=True, mono=True, size=11)
        row_fps.addWidget(self.lbl_fps)
        row_fps.addStretch()
        layout.addLayout(row_fps)

        row_infer = QHBoxLayout()
        row_infer.addWidget(_lbl("推理:", TEXT_DIM, size=11))
        self.lbl_infer = _lbl("— ms", TEXT_DARK, bold=True, mono=True, size=11)
        row_infer.addWidget(self.lbl_infer)
        row_infer.addStretch()
        layout.addLayout(row_infer)

        row_backend = QHBoxLayout()
        row_backend.addWidget(_lbl("后端:", TEXT_DIM, size=11))
        self.lbl_backend = _lbl("—", TEXT_DIM, size=11)
        row_backend.addWidget(self.lbl_backend)
        row_backend.addStretch()
        layout.addLayout(row_backend)

        return box

    # ── 舵机校准卡片 ──────────────────────────────────────────────────

    def _build_servo_card(self):
        box = QGroupBox("⚙️ 舵机控制")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 16, 10, 10)
        layout.setSpacing(8)

        # 灯光控制按钮
        row_light = QHBoxLayout()
        row_light.addWidget(_lbl("灯光控制:", TEXT_DIM))
        b_on = _btn("开灯", "on", 60)
        b_off = _btn("关灯", "off", 60)
        b_on.clicked.connect(lambda: self._servo_press("on"))
        b_off.clicked.connect(lambda: self._servo_press("off"))
        row_light.addStretch()
        row_light.addWidget(b_on)
        row_light.addWidget(b_off)
        layout.addLayout(row_light)

        layout.addWidget(_sep())

        # 当前角度信息
        row_info = QHBoxLayout()
        row_info.addWidget(_lbl("当前角度:", TEXT_DIM, size=11))
        self.lbl_servo_angle = _lbl("90°", ACCENT, bold=True, mono=True, size=11)
        row_info.addWidget(self.lbl_servo_angle)
        row_info.addStretch()
        self.lbl_servo_saved = _lbl(
            "开灯60° / 关灯120° / 中立90°", TEXT_DIM, size=10, mono=True)
        self.lbl_servo_saved.setMinimumWidth(180)
        row_info.addWidget(self.lbl_servo_saved)
        layout.addLayout(row_info)

        # 角度滑块
        self.slider_servo = QSlider(Qt.Orientation.Horizontal)
        self.slider_servo.setRange(0, 180)
        self.slider_servo.setValue(90)
        self.slider_servo.valueChanged.connect(
            lambda v: self.lbl_servo_angle.setText(f"{v}°"))
        self.slider_servo.sliderReleased.connect(self._servo_move_slider)
        layout.addWidget(self.slider_servo)

        # 微调按钮 ±1° ±5°
        row_nudge = QHBoxLayout()
        for text, delta in (("-5°", -5), ("-1°", -1), ("+1°", 1), ("+5°", 5)):
            btn = _btn(text, width=56)
            btn.clicked.connect(lambda _, d=delta: self._servo_nudge(d))
            row_nudge.addWidget(btn)
        row_nudge.addStretch()
        btn_center = _btn("回中立", width=70)
        btn_center.clicked.connect(self._servo_move_neutral)
        row_nudge.addWidget(btn_center)
        layout.addLayout(row_nudge)

        layout.addWidget(_sep())

        # 保存预设按钮
        row_save = QHBoxLayout()
        btn_save_on = _btn("记为开灯角", "accent", 100)
        btn_save_off = _btn("记为关灯角", "accent", 100)
        btn_save_neutral = _btn("记为中立角", "accent", 100)
        btn_save_on.clicked.connect(lambda: self._servo_save_preset("on"))
        btn_save_off.clicked.connect(lambda: self._servo_save_preset("off"))
        btn_save_neutral.clicked.connect(lambda: self._servo_save_preset("neutral"))
        row_save.addWidget(btn_save_on)
        row_save.addWidget(btn_save_off)
        row_save.addWidget(btn_save_neutral)
        layout.addLayout(row_save)

        # 保持时长
        row_duration = QHBoxLayout()
        row_duration.addWidget(_lbl("保持时长(s):", TEXT_DIM, size=11))
        self.edit_servo_duration = QLineEdit("0.5")
        self.edit_servo_duration.setMinimumWidth(60)
        self.edit_servo_duration.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row_duration.addWidget(self.edit_servo_duration)
        btn_save_dur = _btn("保存", width=60)
        btn_save_dur.clicked.connect(self._servo_save_duration)
        row_duration.addWidget(btn_save_dur)
        row_duration.addStretch()
        layout.addLayout(row_duration)

        return box

        return box

    # ── 舵机校准面板（偏移量模式）──────────────────────────────────────

    def _build_servo_calibration_card(self):
        """舵机校准面板：Neutral_Angle, ON_Offset, OFF_Offset 输入 + 测试按钮"""
        box = QGroupBox("⚙️ 舵机偏移量校准")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 16, 10, 10)
        layout.setSpacing(6)

        # 加载当前校准值
        calibration = self.engine.user_settings.get("servo_calibration", {})
        neutral = calibration.get("neutral_angle", 90)
        on_offset = calibration.get("on_offset", -30)
        off_offset = calibration.get("off_offset", 30)

        # Neutral Angle
        row_neutral = QHBoxLayout()
        row_neutral.addWidget(_lbl("中位:", TEXT_DIM, size=11))
        self.spin_neutral = QSpinBox()
        self.spin_neutral.setRange(0, 180)
        self.spin_neutral.setValue(neutral)
        self.spin_neutral.setSuffix("°")
        self.spin_neutral.setMinimumWidth(55)
        self.spin_neutral.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row_neutral.addWidget(self.spin_neutral)
        btn_test_neutral = _btn("测试", "accent", 50)
        btn_test_neutral.clicked.connect(self._calibration_test_neutral)
        row_neutral.addWidget(btn_test_neutral)
        row_neutral.addWidget(_lbl("开灯偏移:", TEXT_DIM, size=11))
        self.spin_on_offset = QSpinBox()
        self.spin_on_offset.setRange(-90, 90)
        self.spin_on_offset.setValue(on_offset)
        self.spin_on_offset.setSuffix("°")
        self.spin_on_offset.setMinimumWidth(55)
        self.spin_on_offset.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row_neutral.addWidget(self.spin_on_offset)
        btn_test_on = _btn("测试", "accent", 50)
        btn_test_on.clicked.connect(self._calibration_test_on)
        row_neutral.addWidget(btn_test_on)
        row_neutral.addStretch()
        layout.addLayout(row_neutral)

        # OFF Offset + Save (same row)
        row_off = QHBoxLayout()
        row_off.addWidget(_lbl("关灯偏移:", TEXT_DIM, size=11))
        self.spin_off_offset = QSpinBox()
        self.spin_off_offset.setRange(-90, 90)
        self.spin_off_offset.setValue(off_offset)
        self.spin_off_offset.setSuffix("°")
        self.spin_off_offset.setMinimumWidth(55)
        self.spin_off_offset.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row_off.addWidget(self.spin_off_offset)
        btn_test_off = _btn("测试", "accent", 50)
        btn_test_off.clicked.connect(self._calibration_test_off)
        row_off.addWidget(btn_test_off)
        btn_save_cal = _btn("保存校准", "accent", 80)
        btn_save_cal.clicked.connect(self._calibration_save)
        row_off.addWidget(btn_save_cal)
        self.lbl_cal_status = _lbl("", TEXT_DIM, size=11)
        row_off.addWidget(self.lbl_cal_status)
        row_off.addStretch()
        layout.addLayout(row_off)

        return box

    # ── 光照阈值配置卡片 ──────────────────────────────────────────────

    def _build_light_threshold_card(self):
        """光照阈值配置：数值输入 + '使用当前读数'按钮"""
        box = QGroupBox("☀️ 光照阈值配置")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 16, 10, 10)
        layout.setSpacing(6)

        # 加载当前阈值
        threshold = self.engine.user_settings.get("dark_threshold", 150.0)

        row_threshold = QHBoxLayout()
        row_threshold.addWidget(_lbl("阈值:", TEXT_DIM, size=11))
        self.spin_dark_threshold = QDoubleSpinBox()
        self.spin_dark_threshold.setRange(0.0, 65535.0)
        self.spin_dark_threshold.setValue(threshold)
        self.spin_dark_threshold.setSuffix(" lux")
        self.spin_dark_threshold.setDecimals(1)
        self.spin_dark_threshold.setMinimumWidth(70)
        self.spin_dark_threshold.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row_threshold.addWidget(self.spin_dark_threshold)
        btn_use_current = _btn("用当前值", "accent", 80)
        btn_use_current.clicked.connect(self._light_use_current)
        row_threshold.addWidget(btn_use_current)
        btn_save_threshold = _btn("保存", "accent", 50)
        btn_save_threshold.clicked.connect(self._light_save_threshold)
        row_threshold.addWidget(btn_save_threshold)
        self.lbl_light_threshold_status = _lbl("", TEXT_DIM, size=11)
        row_threshold.addWidget(self.lbl_light_threshold_status)
        row_threshold.addStretch()
        layout.addLayout(row_threshold)

        return box

    # ── 灯光条件复选框卡片 ────────────────────────────────────────────

    def _build_conditions_card(self):
        """灯光条件复选框：时间/光照/人员在场"""
        box = QGroupBox("💡 灯光控制条件")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 16, 10, 10)
        layout.setSpacing(4)

        # 加载当前条件配置
        conditions = self.engine.user_settings.get("light_conditions", {})

        self.chk_time = QCheckBox("时间条件（日出日落）")
        self.chk_time.setChecked(conditions.get("time_enabled", True))
        layout.addWidget(self.chk_time)

        self.chk_light = QCheckBox("光照条件（低于阈值）")
        self.chk_light.setChecked(conditions.get("light_enabled", True))
        layout.addWidget(self.chk_light)

        row_last = QHBoxLayout()
        self.chk_presence = QCheckBox("人员在场条件")
        self.chk_presence.setChecked(conditions.get("presence_enabled", True))
        row_last.addWidget(self.chk_presence)
        row_last.addStretch()
        btn_save_cond = _btn("保存", "accent", 50)
        btn_save_cond.clicked.connect(self._conditions_save)
        row_last.addWidget(btn_save_cond)
        self.lbl_conditions_status = _lbl("", TEXT_DIM, size=11)
        row_last.addWidget(self.lbl_conditions_status)
        layout.addLayout(row_last)

        return box

    # ── 时间回退配置卡片 ──────────────────────────────────────────────

    def _build_time_fallback_card(self):
        """时间回退配置：白天开始/结束时间输入"""
        box = QGroupBox("🕐 时间回退配置")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 16, 10, 10)
        layout.setSpacing(6)

        # 加载当前配置
        fallback = self.engine.user_settings.get("fallback_daytime", {})

        row = QHBoxLayout()
        row.addWidget(_lbl("白天:", TEXT_DIM, size=11))
        self.edit_fallback_start = QLineEdit(fallback.get("start", "06:00"))
        self.edit_fallback_start.setMinimumWidth(50)
        self.edit_fallback_start.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.edit_fallback_start.setPlaceholderText("HH:MM")
        row.addWidget(self.edit_fallback_start)
        row.addWidget(_lbl("~", TEXT_DIM, size=11))
        self.edit_fallback_end = QLineEdit(fallback.get("end", "18:00"))
        self.edit_fallback_end.setMinimumWidth(50)
        self.edit_fallback_end.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.edit_fallback_end.setPlaceholderText("HH:MM")
        row.addWidget(self.edit_fallback_end)
        btn_save_time = _btn("保存", "accent", 50)
        btn_save_time.clicked.connect(self._time_fallback_save)
        row.addWidget(btn_save_time)
        self.lbl_time_fallback_status = _lbl("", TEXT_DIM, size=11)
        row.addWidget(self.lbl_time_fallback_status)
        row.addStretch()
        layout.addLayout(row)

        layout.addWidget(_lbl("API不可用时使用此回退时间范围", TEXT_DIM, size=10))

        return box

    # ── 温度阈值配置卡片 ──────────────────────────────────────────────

    def _build_temperature_card(self):
        """温度阈值配置：制冷/制热阈值输入"""
        box = QGroupBox("❄️ 温度阈值配置")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 16, 10, 10)
        layout.setSpacing(6)

        # 加载当前配置
        ac_cfg = self.engine.user_settings.get("ac_thresholds", {})

        row = QHBoxLayout()
        row.addWidget(_lbl("制冷 >", TEXT_DIM, size=11))
        self.spin_cooling = QDoubleSpinBox()
        self.spin_cooling.setRange(15.0, 40.0)
        self.spin_cooling.setValue(ac_cfg.get("cooling", 28.0))
        self.spin_cooling.setSuffix("°C")
        self.spin_cooling.setDecimals(1)
        self.spin_cooling.setMinimumWidth(60)
        self.spin_cooling.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row.addWidget(self.spin_cooling)
        row.addWidget(_lbl("制热 <", TEXT_DIM, size=11))
        self.spin_heating = QDoubleSpinBox()
        self.spin_heating.setRange(0.0, 30.0)
        self.spin_heating.setValue(ac_cfg.get("heating", 18.0))
        self.spin_heating.setSuffix("°C")
        self.spin_heating.setDecimals(1)
        self.spin_heating.setMinimumWidth(60)
        self.spin_heating.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row.addWidget(self.spin_heating)
        btn_save_temp = _btn("保存", "accent", 50)
        btn_save_temp.clicked.connect(self._temperature_save)
        row.addWidget(btn_save_temp)
        self.lbl_temp_threshold_status = _lbl("", TEXT_DIM, size=11)
        row.addWidget(self.lbl_temp_threshold_status)
        row.addStretch()
        layout.addLayout(row)

        return box

    # ── IR Wizard 向导卡片 ────────────────────────────────────────────

    def _build_ir_wizard_card(self):
        """IR Wizard 向导界面：步骤显示 + 录制/跳过/重试按钮"""
        box = QGroupBox("📡 红外录制向导")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 16, 10, 10)
        layout.setSpacing(8)

        # 向导状态
        self.lbl_wizard_status = _lbl("向导未启动", TEXT_DIM, size=11)
        layout.addWidget(self.lbl_wizard_status)

        # 进度条
        self.progress_wizard = QProgressBar()
        self.progress_wizard.setRange(0, 12)
        self.progress_wizard.setValue(0)
        self.progress_wizard.setTextVisible(True)
        self.progress_wizard.setFormat("%v / %m 步")
        layout.addWidget(self.progress_wizard)

        # 当前步骤指令
        self.lbl_wizard_instruction = _lbl("", ACCENT, bold=True, size=12)
        self.lbl_wizard_instruction.setMinimumHeight(36)
        layout.addWidget(self.lbl_wizard_instruction)

        layout.addWidget(_sep())

        # 控制按钮
        row_btns = QHBoxLayout()
        self.btn_wizard_start = _btn("开始向导", "accent", 90)
        self.btn_wizard_start.clicked.connect(self._wizard_start)
        row_btns.addWidget(self.btn_wizard_start)

        self.btn_wizard_record = _btn("录制", "on", 70)
        self.btn_wizard_record.clicked.connect(self._wizard_record)
        self.btn_wizard_record.setEnabled(False)
        row_btns.addWidget(self.btn_wizard_record)

        self.btn_wizard_skip = _btn("跳过", width=70)
        self.btn_wizard_skip.clicked.connect(self._wizard_skip)
        self.btn_wizard_skip.setEnabled(False)
        row_btns.addWidget(self.btn_wizard_skip)

        self.btn_wizard_retry = _btn("重试", width=70)
        self.btn_wizard_retry.clicked.connect(self._wizard_retry)
        self.btn_wizard_retry.setEnabled(False)
        row_btns.addWidget(self.btn_wizard_retry)

        row_btns.addStretch()
        layout.addLayout(row_btns)

        # 完成按钮
        row_finish = QHBoxLayout()
        self.btn_wizard_finish = _btn("完成并保存", "accent", 100)
        self.btn_wizard_finish.clicked.connect(self._wizard_finish)
        self.btn_wizard_finish.setEnabled(False)
        row_finish.addWidget(self.btn_wizard_finish)
        self.lbl_wizard_result = _lbl("", TEXT_DIM, size=11)
        row_finish.addWidget(self.lbl_wizard_result)
        row_finish.addStretch()
        layout.addLayout(row_finish)

        return box

    # ── 红外控制卡片 ──────────────────────────────────────────────────

    def _build_ir_card(self):
        box = QGroupBox("📡 红外控制")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 16, 10, 10)
        layout.setSpacing(8)

        # 学习区域
        row_learn = QHBoxLayout()
        row_learn.addWidget(_lbl("命令名称:", TEXT_DIM, size=11))
        self.edit_ir_name = QLineEdit()
        self.edit_ir_name.setPlaceholderText("例: ac_on_cool")
        self.edit_ir_name.setMinimumWidth(80)
        self.edit_ir_name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row_learn.addWidget(self.edit_ir_name)
        btn_learn = _btn("学习", "accent", 60)
        btn_learn.clicked.connect(self._ir_learn)
        row_learn.addWidget(btn_learn)
        row_learn.addStretch()
        layout.addLayout(row_learn)

        self.lbl_ir_status = _lbl("", TEXT_DIM, size=11)
        layout.addWidget(self.lbl_ir_status)

        layout.addWidget(_sep())

        # 命令列表 + 发送/删除
        row_cmd = QHBoxLayout()
        row_cmd.addWidget(_lbl("已学习命令:", TEXT_DIM, size=11))
        self.combo_ir = QComboBox()
        self.combo_ir.setMinimumWidth(140)
        row_cmd.addWidget(self.combo_ir)
        btn_send = _btn("发送", "on", 60)
        btn_send.clicked.connect(self._ir_send)
        row_cmd.addWidget(btn_send)
        btn_del = _btn("删除", "off", 60)
        btn_del.clicked.connect(self._ir_delete)
        row_cmd.addWidget(btn_del)
        row_cmd.addStretch()
        layout.addLayout(row_cmd)

        return box


    # ── 模型切换卡片 ──────────────────────────────────────────────────

    def _build_model_card(self):
        box = QGroupBox("🧠 模型切换")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 16, 10, 10)
        layout.setSpacing(8)

        self.combo_model = QComboBox()
        self.combo_model.setMaxVisibleItems(20)
        from PyQt6.QtGui import QColor as _QColor
        for label, fname, is_header in MODEL_ENTRIES:
            self.combo_model.addItem(label, userData=fname)
        model_obj = self.combo_model.model()
        for i, (_, fname, is_header) in enumerate(MODEL_ENTRIES):
            if is_header:
                item = model_obj.item(i)
                item.setEnabled(False)
                item.setForeground(_QColor(AMBER))
        self.combo_model.setCurrentIndex(1)
        layout.addWidget(self.combo_model)

        hint = _lbl("或直接输入本地 .pt 文件路径:", TEXT_DIM, size=11)
        layout.addWidget(hint)

        self.edit_custom = QLineEdit()
        self.edit_custom.setPlaceholderText("例: C:/models/best.pt")
        layout.addWidget(self.edit_custom)

        btn_switch = _btn("切换模型", "accent")
        btn_switch.clicked.connect(self._switch_model)
        layout.addWidget(btn_switch)

        self.lbl_model_cur = _lbl("当前: yolov8n.pt", TEXT_DIM, size=11)
        self.lbl_model_msg = _lbl("", GREEN, size=11)
        layout.addWidget(self.lbl_model_cur)
        layout.addWidget(self.lbl_model_msg)

        return box

    # ── 恢复上次配置 ──────────────────────────────────────────────────

    def _apply_saved_settings(self):
        """从 user_settings 恢复上次的配置"""
        saved_model = self.engine.user_settings.get("yolo_model", "yolov8n.pt")
        for i, (_, fname, _) in enumerate(MODEL_ENTRIES):
            if fname == saved_model:
                self.combo_model.setCurrentIndex(i)
                break
        self.lbl_model_cur.setText(f"当前: {saved_model}")

        mode = self.engine.user_settings.get("control_mode", "AUTO")
        # Mode is already set in engine init

        # Refresh IR command list
        self._refresh_ir_commands()

    # ── 后台线程 ──────────────────────────────────────────────────────

    def _start_threads(self):
        self.cap_thread = CaptureThread(self.engine.detector)
        self.cap_thread.frame_ready.connect(self._on_frame)
        self.cap_thread.start()

        self.stat_thread = StatusThread(self.engine)
        self.stat_thread.status_ready.connect(self._on_status)
        self.stat_thread.start()

    # ── 槽：帧渲染 ───────────────────────────────────────────────────

    def _on_frame(self, frame: np.ndarray):
        h, w, ch = frame.shape
        img = QImage(frame.data, w, h, ch * w, QImage.Format.Format_BGR888)
        pix = QPixmap.fromImage(img).scaled(
            self.video_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        self.video_label.setPixmap(pix)

    # ── 槽：状态更新 ──────────────────────────────────────────────────

    def _on_status(self, s: dict):
        # 人员检测
        det = s.get("detector", {})
        presence = s.get("presence", False)
        person_count = det.get("person_count", 0) if det else 0

        self.lbl_count.setText(str(person_count))
        self.lbl_count.setStyleSheet(
            f"color:{GREEN if person_count > 0 else RED};"
            f"font-size:42px;font-weight:bold;")

        self.lbl_presence.setText("有人" if presence else "无人")
        self.lbl_presence.setStyleSheet(
            f"color:{GREEN if presence else RED};font-weight:bold;")

        # 性能
        if det:
            fps = det.get("stream_fps", 0)
            self.lbl_fps.setText(f"采集: {fps} fps")
            infer_ms = det.get("infer_ms", 0)
            ic = GREEN if infer_ms < 200 else (AMBER if infer_ms < 500 else RED)
            self.lbl_infer.setText(f"推理: {infer_ms} ms")
            self.lbl_infer.setStyleSheet(
                f"color:{ic};font-size:11px;font-family:Consolas,monospace;")
            self.lbl_backend.setText(f"后端: {det.get('camera_backend', '—')}")

        # 环境
        temp = s.get("temperature")
        humi = s.get("humidity")
        lux = s.get("lux", 0.0)
        self.lbl_temp.setText(f"{temp}°C" if temp is not None else "—°C")
        self.lbl_humi.setText(f"{humi}%" if humi is not None else "—%")
        self.lbl_lux.setText(f"{lux:.0f} lux" if lux else "— lux")

        # 灯光状态
        light_on = s.get("light_on", False)
        self.lbl_light.setText("开启" if light_on else "关闭")
        self.lbl_light.setStyleSheet(
            f"color:{GREEN};font-weight:bold;" if light_on
            else f"color:{RED};font-weight:bold;")

        # 舵机
        servo = s.get("servo", {})
        if servo:
            current_angle = servo.get("current_angle")
            if current_angle is not None and not self.slider_servo.isSliderDown():
                self.slider_servo.setValue(int(current_angle))
            self.lbl_servo_saved.setText(
                f"开灯{servo.get('angle_on', 60)}° / "
                f"关灯{servo.get('angle_off', 120)}° / "
                f"中立{servo.get('angle_neutral', 90)}°"
            )

        # 模式按钮高亮
        mode = s.get("mode", "AUTO")
        self.btn_auto.setProperty(
            "role", "mode_active" if mode == "AUTO" else "normal")
        self.btn_manual.setProperty(
            "role", "mode_manual_active" if mode == "MANUAL" else "normal")
        for b in (self.btn_auto, self.btn_manual):
            b.style().unpolish(b)
            b.style().polish(b)

        # 模型
        if det:
            model_name = det.get("model_name", "—")
            self.lbl_model_cur.setText(f"当前: {model_name}")

        # 状态栏
        ac_state = s.get("ac_state", "off")
        self.lbl_status.setText(
            f"人数: {person_count}  |  "
            f"温度: {temp if temp is not None else '—'}°C  |  "
            f"空调: {ac_state}  |  "
            f"模式: {mode}")


    # ── 控制槽 ────────────────────────────────────────────────────────

    def _set_mode(self, mode: str):
        self.engine.set_mode(mode)

    def _servo_press(self, action: str):
        """执行舵机开灯/关灯动作"""
        try:
            if action == "on":
                self.engine.servo.press_on()
            else:
                self.engine.servo.press_off()
            logger.info(f"[手动] 舵机 press_{action}")
        except Exception as e:
            logger.error(f"舵机动作失败: {e}")

    def _servo_move_slider(self):
        angle = self.slider_servo.value()
        try:
            self.engine.servo.move_to(angle)
            self.lbl_servo_angle.setText(f"{angle}°")
            logger.info(f"[标定] 舵机移动到 {angle}°")
        except Exception as e:
            logger.error(f"舵机移动失败: {e}")

    def _servo_nudge(self, delta: int):
        current = self.slider_servo.value()
        target = max(0, min(180, current + delta))
        self.slider_servo.setValue(target)
        try:
            self.engine.servo.move_to(target)
            logger.info(f"[标定] 舵机微调 {delta:+d}° -> {target}°")
        except Exception as e:
            logger.error(f"舵机微调失败: {e}")

    def _servo_move_neutral(self):
        status = self.engine.servo.get_status()
        neutral = status.get("angle_neutral", 90)
        self.slider_servo.setValue(neutral)
        try:
            self.engine.servo.move_to(neutral)
            logger.info(f"[标定] 舵机回到中立 {neutral}°")
        except Exception as e:
            logger.error(f"舵机回中立失败: {e}")

    def _servo_save_preset(self, preset: str):
        angle = self.slider_servo.value()
        try:
            self.engine.servo.calibrate(preset, angle)
            self.engine.servo.save_calibration()
            preset_map = {"on": "开灯角", "off": "关灯角", "neutral": "中立角"}
            logger.info(f"[标定] 已记录舵机{preset_map.get(preset, preset)} = {angle}°")
        except Exception as e:
            logger.error(f"保存预设失败: {e}")

    def _servo_save_duration(self):
        try:
            duration = float(self.edit_servo_duration.text().strip())
        except ValueError:
            self.lbl_status.setText("保持时长必须是数字")
            return
        # Update calibration duration directly
        self.engine.servo._calibration["action_duration"] = duration
        self.engine.servo.save_calibration()
        logger.info(f"[标定] 已保存舵机保持时长 {duration:.2f}s")

    # ── 舵机偏移量校准槽 ──────────────────────────────────────────────

    def _calibration_test_neutral(self):
        """测试中位角度：立即移动到该位置"""
        angle = self.spin_neutral.value()
        try:
            self.engine.servo.set_neutral(angle)
            self.lbl_cal_status.setText(f"中位角度已设为 {angle}°")
            self.lbl_cal_status.setStyleSheet(f"color:{GREEN};font-size:11px;")
            logger.info(f"[校准] 中位角度测试: {angle}°")
        except Exception as e:
            self.lbl_cal_status.setText(f"测试失败: {e}")
            self.lbl_cal_status.setStyleSheet(f"color:{RED};font-size:11px;")

    def _calibration_test_on(self):
        """测试开灯偏移：执行 neutral → target → neutral 动作"""
        offset = self.spin_on_offset.value()
        try:
            self.engine.servo.set_on_offset(offset)
            self.lbl_cal_status.setText(f"开灯偏移已设为 {offset}°，测试完成")
            self.lbl_cal_status.setStyleSheet(f"color:{GREEN};font-size:11px;")
            logger.info(f"[校准] 开灯偏移测试: {offset}°")
        except Exception as e:
            self.lbl_cal_status.setText(f"测试失败: {e}")
            self.lbl_cal_status.setStyleSheet(f"color:{RED};font-size:11px;")

    def _calibration_test_off(self):
        """测试关灯偏移：执行 neutral → target → neutral 动作"""
        offset = self.spin_off_offset.value()
        try:
            self.engine.servo.set_off_offset(offset)
            self.lbl_cal_status.setText(f"关灯偏移已设为 {offset}°，测试完成")
            self.lbl_cal_status.setStyleSheet(f"color:{GREEN};font-size:11px;")
            logger.info(f"[校准] 关灯偏移测试: {offset}°")
        except Exception as e:
            self.lbl_cal_status.setText(f"测试失败: {e}")
            self.lbl_cal_status.setStyleSheet(f"color:{RED};font-size:11px;")

    def _calibration_save(self):
        """保存校准数据到 UserSettings"""
        calibration = {
            "neutral_angle": self.spin_neutral.value(),
            "on_offset": self.spin_on_offset.value(),
            "off_offset": self.spin_off_offset.value(),
        }
        self.engine.user_settings.set("servo_calibration", calibration)
        # 更新引擎中的舵机校准
        self.engine.servo._calibration.update(calibration)
        self.lbl_cal_status.setText("校准数据已保存")
        self.lbl_cal_status.setStyleSheet(f"color:{GREEN};font-size:11px;")
        logger.info(f"[校准] 已保存: {calibration}")

    # ── 光照阈值槽 ────────────────────────────────────────────────────

    def _light_use_current(self):
        """使用当前光照读数作为阈值"""
        try:
            status = self.engine.light_sensor.get_status()
            lux = status.get("lux", 0.0)
            if lux is not None and lux > 0:
                self.spin_dark_threshold.setValue(lux)
                self.lbl_light_threshold_status.setText(f"已读取当前值: {lux:.1f} lux")
                self.lbl_light_threshold_status.setStyleSheet(f"color:{GREEN};font-size:11px;")
            else:
                self.lbl_light_threshold_status.setText("当前无有效光照读数")
                self.lbl_light_threshold_status.setStyleSheet(f"color:{AMBER};font-size:11px;")
        except Exception as e:
            self.lbl_light_threshold_status.setText(f"读取失败: {e}")
            self.lbl_light_threshold_status.setStyleSheet(f"color:{RED};font-size:11px;")

    def _light_save_threshold(self):
        """保存光照阈值到 UserSettings"""
        threshold = self.spin_dark_threshold.value()
        self.engine.user_settings.set("dark_threshold", threshold)
        # 更新光照传感器的阈值
        try:
            self.engine.light_sensor.set_threshold(threshold)
        except AttributeError:
            pass  # 旧版本可能没有 set_threshold 方法
        self.lbl_light_threshold_status.setText(f"已保存: {threshold:.1f} lux")
        self.lbl_light_threshold_status.setStyleSheet(f"color:{GREEN};font-size:11px;")
        logger.info(f"[配置] 光照阈值已保存: {threshold:.1f} lux")

    # ── 灯光条件槽 ────────────────────────────────────────────────────

    def _conditions_save(self):
        """保存灯光条件配置到 UserSettings"""
        conditions = {
            "time_enabled": self.chk_time.isChecked(),
            "light_enabled": self.chk_light.isChecked(),
            "presence_enabled": self.chk_presence.isChecked(),
        }
        self.engine.user_settings.set("light_conditions", conditions)
        # 更新条件评估器配置
        try:
            from src.condition_evaluator import ConditionConfig
            new_config = ConditionConfig(
                time_enabled=conditions["time_enabled"],
                light_enabled=conditions["light_enabled"],
                presence_enabled=conditions["presence_enabled"],
            )
            self.engine.condition_evaluator.update_config(new_config)
        except Exception as e:
            logger.warning(f"更新条件评估器失败: {e}")
        self.lbl_conditions_status.setText("条件配置已保存")
        self.lbl_conditions_status.setStyleSheet(f"color:{GREEN};font-size:11px;")
        logger.info(f"[配置] 灯光条件已保存: {conditions}")

    # ── 时间回退配置槽 ────────────────────────────────────────────────

    def _time_fallback_save(self):
        """保存时间回退配置到 UserSettings"""
        start = self.edit_fallback_start.text().strip()
        end = self.edit_fallback_end.text().strip()

        # 简单格式验证
        import re
        time_pattern = re.compile(r"^\d{2}:\d{2}$")
        if not time_pattern.match(start) or not time_pattern.match(end):
            self.lbl_time_fallback_status.setText("格式错误，请使用 HH:MM")
            self.lbl_time_fallback_status.setStyleSheet(f"color:{RED};font-size:11px;")
            return

        fallback = {"start": start, "end": end}
        self.engine.user_settings.set("fallback_daytime", fallback)
        # 更新时间条件提供者
        try:
            self.engine.time_condition._fallback_start = start
            self.engine.time_condition._fallback_end = end
        except AttributeError:
            pass
        self.lbl_time_fallback_status.setText("时间配置已保存")
        self.lbl_time_fallback_status.setStyleSheet(f"color:{GREEN};font-size:11px;")
        logger.info(f"[配置] 时间回退已保存: {fallback}")

    # ── 温度阈值槽 ────────────────────────────────────────────────────

    def _temperature_save(self):
        """保存温度阈值到 UserSettings"""
        cooling = self.spin_cooling.value()
        heating = self.spin_heating.value()

        if heating >= cooling:
            self.lbl_temp_threshold_status.setText("制热阈值必须低于制冷阈值")
            self.lbl_temp_threshold_status.setStyleSheet(f"color:{RED};font-size:11px;")
            return

        thresholds = {"cooling": cooling, "heating": heating}
        self.engine.user_settings.set("ac_thresholds", thresholds)
        # 更新空调控制器阈值
        try:
            self.engine.ac_controller._cooling_threshold = cooling
            self.engine.ac_controller._heating_threshold = heating
        except AttributeError:
            pass
        self.lbl_temp_threshold_status.setText(f"已保存: 制冷>{cooling}°C, 制热<{heating}°C")
        self.lbl_temp_threshold_status.setStyleSheet(f"color:{GREEN};font-size:11px;")
        logger.info(f"[配置] 温度阈值已保存: {thresholds}")

    # ── IR Wizard 向导槽 ──────────────────────────────────────────────

    def _wizard_start(self):
        """启动IR录制向导"""
        try:
            from src.ir_wizard import IRWizard
            # 创建向导实例（如果引擎没有的话）
            if not hasattr(self.engine, '_ir_wizard') or self.engine._ir_wizard is None:
                self.engine._ir_wizard = IRWizard(self.engine.ir_controller)
            result = self.engine._ir_wizard.start()
            if result.get("success"):
                self._wizard_update_ui(result)
                self.btn_wizard_start.setEnabled(False)
                self.btn_wizard_record.setEnabled(True)
                self.btn_wizard_skip.setEnabled(True)
                self.btn_wizard_retry.setEnabled(True)
                self.btn_wizard_finish.setEnabled(False)
                self.lbl_wizard_status.setText("向导已启动")
                self.lbl_wizard_status.setStyleSheet(f"color:{GREEN};font-size:11px;")
                logger.info("[IR Wizard] 向导已启动")
            else:
                self.lbl_wizard_status.setText(f"启动失败: {result.get('error', '')}")
                self.lbl_wizard_status.setStyleSheet(f"color:{RED};font-size:11px;")
        except Exception as e:
            self.lbl_wizard_status.setText(f"启动失败: {e}")
            self.lbl_wizard_status.setStyleSheet(f"color:{RED};font-size:11px;")

    def _wizard_record(self):
        """录制当前步骤"""
        if not hasattr(self.engine, '_ir_wizard') or self.engine._ir_wizard is None:
            return
        self.lbl_wizard_status.setText("录制中… 请对准红外接收器按下遥控器按键")
        self.lbl_wizard_status.setStyleSheet(f"color:{AMBER};font-size:11px;")
        QApplication.processEvents()

        result = self.engine._ir_wizard.record_current(timeout=10.0)
        if result.get("success"):
            self.lbl_wizard_status.setText(f"录制成功: {result.get('command_name', '')}")
            self.lbl_wizard_status.setStyleSheet(f"color:{GREEN};font-size:11px;")
            self._wizard_update_ui(result)
        else:
            self.lbl_wizard_status.setText(f"录制失败: {result.get('error', '超时')}")
            self.lbl_wizard_status.setStyleSheet(f"color:{RED};font-size:11px;")
        self._wizard_check_complete()

    def _wizard_skip(self):
        """跳过当前步骤"""
        if not hasattr(self.engine, '_ir_wizard') or self.engine._ir_wizard is None:
            return
        result = self.engine._ir_wizard.skip_current()
        if result.get("success"):
            self.lbl_wizard_status.setText(f"已跳过: {result.get('command_name', '')}")
            self.lbl_wizard_status.setStyleSheet(f"color:{AMBER};font-size:11px;")
            self._wizard_update_ui(result)
        self._wizard_check_complete()

    def _wizard_retry(self):
        """重试当前步骤"""
        if not hasattr(self.engine, '_ir_wizard') or self.engine._ir_wizard is None:
            return
        result = self.engine._ir_wizard.retry_current()
        if result.get("success"):
            self.lbl_wizard_status.setText(f"请重新录制: {result.get('command_name', '')}")
            self.lbl_wizard_status.setStyleSheet(f"color:{ACCENT};font-size:11px;")
            self.lbl_wizard_instruction.setText(result.get("instruction", ""))

    def _wizard_finish(self):
        """完成向导并保存"""
        if not hasattr(self.engine, '_ir_wizard') or self.engine._ir_wizard is None:
            return
        result = self.engine._ir_wizard.finish()
        if result.get("success"):
            recorded = result.get("recorded_count", 0)
            skipped = result.get("skipped_count", 0)
            self.lbl_wizard_result.setText(
                f"完成! 录制 {recorded} 个, 跳过 {skipped} 个")
            self.lbl_wizard_result.setStyleSheet(f"color:{GREEN};font-size:11px;")
            self.lbl_wizard_status.setText("向导已完成")
            self.lbl_wizard_status.setStyleSheet(f"color:{GREEN};font-size:11px;")
            # 重置按钮状态
            self.btn_wizard_start.setEnabled(True)
            self.btn_wizard_record.setEnabled(False)
            self.btn_wizard_skip.setEnabled(False)
            self.btn_wizard_retry.setEnabled(False)
            self.btn_wizard_finish.setEnabled(False)
            self.lbl_wizard_instruction.setText("")
            # 刷新IR命令列表
            self._refresh_ir_commands()
            logger.info(f"[IR Wizard] 完成: 录制{recorded}个, 跳过{skipped}个")

    def _wizard_update_ui(self, result: dict):
        """更新向导UI状态"""
        step = result.get("current_step", 1)
        total = result.get("total_steps", 12)
        instruction = result.get("instruction") or result.get("next_instruction", "")
        self.progress_wizard.setValue(step - 1)
        self.lbl_wizard_instruction.setText(instruction)

    def _wizard_check_complete(self):
        """检查向导是否完成"""
        if not hasattr(self.engine, '_ir_wizard') or self.engine._ir_wizard is None:
            return
        if self.engine._ir_wizard.is_complete:
            self.btn_wizard_record.setEnabled(False)
            self.btn_wizard_skip.setEnabled(False)
            self.btn_wizard_retry.setEnabled(False)
            self.btn_wizard_finish.setEnabled(True)
            self.progress_wizard.setValue(12)
            self.lbl_wizard_instruction.setText("所有步骤已完成，请点击「完成并保存」")

    # ── 红外控制槽 ────────────────────────────────────────────────────

    def _refresh_ir_commands(self):
        """刷新红外命令下拉列表"""
        self.combo_ir.clear()
        commands = self.engine.ir_controller.list_commands()
        for cmd in commands:
            self.combo_ir.addItem(cmd)

    def _ir_learn(self):
        """开始红外学习"""
        name = self.edit_ir_name.text().strip()
        if not name:
            self.lbl_ir_status.setText("请输入命令名称")
            self.lbl_ir_status.setStyleSheet(f"color:{RED};font-size:11px;")
            return

        self.lbl_ir_status.setText("学习中… 请对准红外接收器按下遥控器按键")
        self.lbl_ir_status.setStyleSheet(f"color:{AMBER};font-size:11px;")
        QApplication.processEvents()

        result = self.engine.ir_controller.start_learning(name, timeout=10.0)
        if result.get("success"):
            self.lbl_ir_status.setText(
                f"学习成功: {name} (addr={result['address']}, cmd={result['command']})")
            self.lbl_ir_status.setStyleSheet(f"color:{GREEN};font-size:11px;")
            self.edit_ir_name.clear()
            self._refresh_ir_commands()
        else:
            self.lbl_ir_status.setText(f"学习失败: {result.get('error', '未知错误')}")
            self.lbl_ir_status.setStyleSheet(f"color:{RED};font-size:11px;")

    def _ir_send(self):
        """发送红外命令"""
        cmd = self.combo_ir.currentText()
        if not cmd:
            self.lbl_ir_status.setText("请选择要发送的命令")
            self.lbl_ir_status.setStyleSheet(f"color:{RED};font-size:11px;")
            return

        ok = self.engine.ir_controller.send_command(cmd)
        if ok:
            self.lbl_ir_status.setText(f"已发送: {cmd}")
            self.lbl_ir_status.setStyleSheet(f"color:{GREEN};font-size:11px;")
        else:
            self.lbl_ir_status.setText(f"发送失败: {cmd}")
            self.lbl_ir_status.setStyleSheet(f"color:{RED};font-size:11px;")

    def _ir_delete(self):
        """删除红外命令"""
        cmd = self.combo_ir.currentText()
        if not cmd:
            return
        ok = self.engine.ir_controller.delete_command(cmd)
        if ok:
            self.lbl_ir_status.setText(f"已删除: {cmd}")
            self.lbl_ir_status.setStyleSheet(f"color:{GREEN};font-size:11px;")
            self._refresh_ir_commands()
        else:
            self.lbl_ir_status.setText(f"删除失败: {cmd}")
            self.lbl_ir_status.setStyleSheet(f"color:{RED};font-size:11px;")

    # ── 模型切换 ──────────────────────────────────────────────────────

    def _switch_model(self):
        custom = self.edit_custom.text().strip()
        if custom:
            model_path = custom
        else:
            model_path = self.combo_model.currentData()

        if not model_path:
            self.lbl_model_msg.setText("请选择模型或输入路径")
            self.lbl_model_msg.setStyleSheet(f"color:{RED};font-size:11px;")
            return

        # 检查本地是否存在模型文件
        import os
        weights_dir = os.path.join(os.path.dirname(__file__), "weights")
        local_path = os.path.join(weights_dir, model_path) if not os.path.isabs(model_path) else model_path

        if not os.path.exists(local_path) and not os.path.isabs(model_path):
            self.lbl_model_msg.setText(f"本地无此模型，首次使用将自动下载: {model_path}")
            self.lbl_model_msg.setStyleSheet(f"color:{AMBER};font-size:11px;")
            logger.info("[模型] 本地未找到 %s，ultralytics 将自动下载", model_path)
        else:
            self.lbl_model_msg.setText(f"正在切换: {model_path}…")
            self.lbl_model_msg.setStyleSheet(f"color:{AMBER};font-size:11px;")

        QApplication.processEvents()

        try:
            result = self.engine.detector.switch_model(model_path)
            if result.get("ok"):
                self.lbl_model_msg.setText(f"✓ 已切换: {model_path}")
                self.lbl_model_msg.setStyleSheet(f"color:{GREEN};font-size:11px;")
                self.edit_custom.clear()
                self.engine.user_settings.set("yolo_model", model_path)
                self.lbl_model_cur.setText(f"当前: {model_path}")
                logger.info("[模型] 切换成功: %s", model_path)
            else:
                err = result.get('error', '未知错误')
                self.lbl_model_msg.setText(f"✗ 失败: {err}")
                self.lbl_model_msg.setStyleSheet(f"color:{RED};font-size:11px;")
                logger.error("[模型] 切换失败: %s", err)
        except Exception as e:
            self.lbl_model_msg.setText(f"✗ 切换失败: {e}")
            self.lbl_model_msg.setStyleSheet(f"color:{RED};font-size:11px;")
            logger.error("[模型] 切换异常: %s", e)

    # ── 关闭 ──────────────────────────────────────────────────────────

    def closeEvent(self, event):
        logger.info("GUI 窗口关闭，停止线程…")
        self.cap_thread.stop()
        self.stat_thread.stop()
        event.accept()


# ══════════════════════════════════════════════════════════════════════
#  入口
# ══════════════════════════════════════════════════════════════════════

def main():
    # Windows 高 DPI 支持
    if sys.platform == "win32":
        try:
            from PyQt6.QtCore import Qt as _Qt
            QApplication.setHighDpiScaleFactorRoundingPolicy(
                _Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("智能教室测控系统")

    # 设置 CJK 字体：Windows 用 Microsoft YaHei，Linux 用 Noto Sans CJK SC
    font = QFont()
    available_fonts = QFontDatabase.families()
    if sys.platform == "win32":
        preferred = ["Microsoft YaHei", "Microsoft YaHei UI"]
    else:
        preferred = ["Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Micro Hei"]

    for family in preferred:
        if family in available_fonts:
            font.setFamily(family)
            break
    else:
        # Fallback: try any CJK-capable font
        for family in ("Microsoft YaHei", "Noto Sans CJK SC", "PingFang SC",
                       "SimHei", "WenQuanYi Micro Hei"):
            if family in available_fonts:
                font.setFamily(family)
                break

    font.setPointSize(9 if sys.platform.startswith("linux") else 10)
    app.setFont(font)
    app.setStyleSheet(STYLE)

    # 加载图标
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "app_icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    logger.info("=" * 55)
    logger.info("  智能教室测控系统 — 本地 GUI 版本 (亮色主题)")
    logger.info("=" * 55)

    # 导入新的 src 包模块
    try:
        from src.decision_engine import DecisionEngine
    except ImportError as e:
        print(f"模块导入失败: {e}")
        print("请确保 src/ 目录下的模块已正确安装")
        sys.exit(1)

    # 平台检测：PC 模式使用 Stub 组件，避免硬件依赖
    def _detect_platform() -> str:
        try:
            import lgpio  # noqa: F401
            return "pi"
        except ImportError:
            pass
        try:
            import gpiozero  # noqa: F401
            return "pi"
        except ImportError:
            pass
        return "pc"

    platform = _detect_platform()
    logger.info("运行平台: %s", "树莓派" if platform == "pi" else "PC 模拟")

    if platform == "pi":
        from src.sensor_dht import TemperatureSensor
        from src.sensor_light import LightSensor
        from src.servo import ServoController
        from src.ir_controller import IRController
        from src.detector import Detector

        temperature_sensor = TemperatureSensor()
        light_sensor = LightSensor()
        servo = ServoController()
        ir_controller = IRController()
        detector = Detector()
    else:
        # PC 模式 Stub 类（与 main.py 一致）
        import random as _rnd

        class _StubTemp:
            def start(self): pass
            def stop(self): pass
            def read_once(self): return (round(_rnd.uniform(22, 26), 1), round(_rnd.uniform(40, 60), 1))
            def get_status(self):
                t, h = self.read_once()
                return {"temperature": t, "humidity": h}

        class _StubLight:
            def __init__(self): self._lux = 300.0; self._threshold = 150.0
            def start(self): pass
            def stop(self): pass
            def read_lux(self): self._lux = round(_rnd.uniform(100, 500), 1); return self._lux
            def is_dark(self): return self._lux < self._threshold
            def set_threshold(self, v): self._threshold = float(v)
            @property
            def dark_threshold(self): return self._threshold
            def get_status(self): return {"lux": self.read_lux(), "is_dark": self.is_dark(), "dark_threshold": self._threshold}

        class _StubServo:
            def __init__(self):
                self._angle = 90
                self._calibration = {"neutral_angle": 90, "on_offset": -30, "off_offset": 30}
            def move_to(self, a): self._angle = max(0, min(180, a))
            def press_on(self): logger.info("[Stub] 开灯")
            def press_off(self): logger.info("[Stub] 关灯")
            def calibrate(self, preset, angle):
                if preset == "on": self._calibration["angle_on"] = angle
                elif preset == "off": self._calibration["angle_off"] = angle
                elif preset == "neutral": self._calibration["angle_neutral"] = angle
            def set_neutral(self, a): self._calibration["neutral_angle"] = max(0, min(180, a)); self._angle = self._calibration["neutral_angle"]
            def set_on_offset(self, o): self._calibration["on_offset"] = o
            def set_off_offset(self, o): self._calibration["off_offset"] = o
            def get_status(self): return {"current_angle": self._angle, **self._calibration}
            def save_calibration(self): pass
            def load_calibration(self): return self._calibration.copy()
            def cleanup(self): pass

        class _StubIR:
            def __init__(self): self._cmds = {}
            def start_learning(self, name, timeout=10.0): return {"success": False, "error": "PC模拟模式"}
            def send_command(self, name): return name in self._cmds
            def list_commands(self): return list(self._cmds.keys())
            def delete_command(self, name): return self._cmds.pop(name, None) is not None
            def save_commands(self): pass
            def cleanup(self): pass

        class _StubDetector:
            def __init__(self): self._model_name = "yolov8n.pt"
            def start(self): pass
            def stop(self): pass
            def get_person_count(self): return 0
            def get_latest_frame(self): return None
            def get_status(self): return {"person_count": 0, "running": True, "camera_backend": "stub", "model_name": self._model_name, "stream_fps": 0, "infer_ms": 0}
            def switch_model(self, path):
                logger.info("[模型] 切换到: %s", path)
                self._model_name = path
                return {"ok": True}

        temperature_sensor = _StubTemp()
        light_sensor = _StubLight()
        servo = _StubServo()
        ir_controller = _StubIR()
        detector = _StubDetector()

    logger.info("初始化 DecisionEngine…")
    engine = DecisionEngine(
        temperature_sensor=temperature_sensor,
        light_sensor=light_sensor,
        detector=detector,
        servo=servo,
        ir_controller=ir_controller,
    )
    engine.start()

    def shutdown():
        logger.info("正在关闭系统…")
        engine.cleanup()
        logger.info("系统已安全关闭")

    window = MainWindow(engine)
    window.show()

    # Ctrl+C 支持
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    timer = QTimer()
    timer.start(300)
    timer.timeout.connect(lambda: None)

    code = app.exec()
    shutdown()
    sys.exit(code)


if __name__ == "__main__":
    main()
