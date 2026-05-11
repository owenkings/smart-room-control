# -*- coding: utf-8 -*-
"""
智能教室测控系统 - 本地 GUI 版本（PyQt6）

修复清单:
  1. PersonDetector.person_count AttributeError — __init__ 缺少初始化
  2. 中文乱码 — 显式设置 UTF-8 + 微软雅黑字体
  3. 布局不均 — 改用 QSplitter 自适应分割
  4. 模型切换 — 下拉框存储 (显示名, 文件名) 分离，currentIndex 取文件名
  5. 窗口图标 — 加载 assets/app_icon.ico

运行: python gui_app.py
依赖: pip install PyQt6
"""

# ── 编码声明（防止 Windows 控制台乱码）──────────────────────────────
import sys
import os
import io

# Windows 下强制 stdout/stderr 使用 UTF-8
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import time
import queue as _queue
import signal
import logging
import numpy as np

import user_settings  # 用户配置持久化

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QComboBox, QSlider, QTextEdit, QSizePolicy,
    QSplitter, QStatusBar, QScrollArea, QFrame, QLineEdit,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QImage, QPixmap, QFont, QColor, QIcon, QFontDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("gui")

# ── 颜色常量 ─────────────────────────────────────────────────────────
DARK_BG  = "#1a1a2e"
CARD_BG  = "#16213e"
BORDER   = "#0f3460"
GREEN    = "#4ecca3"
RED      = "#e94560"
AMBER    = "#f0a500"
BLUE     = "#4a9eff"
TEXT     = "#eeeeee"
DIM      = "#888888"

# ── 全局样式表 ────────────────────────────────────────────────────────
STYLE = f"""
* {{
    font-family: "Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Micro Hei",
                 "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC",
                 "Segoe UI", sans-serif;
    font-size: 12px;
    color: {TEXT};
}}
QMainWindow, QWidget, QScrollArea, QScrollArea > QWidget > QWidget {{
    background-color: {DARK_BG};
}}
QGroupBox {{
    background-color: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 10px;
    padding: 10px 8px 8px 8px;
    font-weight: bold;
    color: {RED};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    background-color: {CARD_BG};
}}
QPushButton {{
    background-color: {BORDER};
    color: {TEXT};
    border: 1px solid #1a4080;
    border-radius: 6px;
    padding: 4px 10px;
    min-height: 24px;
}}
QPushButton:hover  {{ background-color: #1e4d99; border-color: {BLUE}; }}
QPushButton:pressed {{ background-color: {GREEN}; color: {DARK_BG}; }}
QPushButton[role="on"] {{
    background-color: {GREEN}; color: {DARK_BG}; font-weight: bold;
    border-color: {GREEN};
}}
QPushButton[role="on"]:hover {{ background-color: #3ab88a; }}
QPushButton[role="off"] {{
    background-color: {RED}; color: white; font-weight: bold;
    border-color: {RED};
}}
QPushButton[role="off"]:hover {{ background-color: #c73550; }}
QPushButton[role="mode_active"] {{
    background-color: {GREEN}; color: {DARK_BG}; font-weight: bold;
}}
QPushButton[role="mode_manual_active"] {{
    background-color: {AMBER}; color: {DARK_BG}; font-weight: bold;
}}
QSlider::groove:horizontal {{
    height: 4px; background: {BORDER}; border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {GREEN}; width: 14px; height: 14px;
    margin: -5px 0; border-radius: 7px;
}}
QSlider::sub-page:horizontal {{ background: {GREEN}; border-radius: 2px; }}
QTextEdit {{
    background-color: {DARK_BG};
    color: {DIM};
    border: 1px solid {BORDER};
    border-radius: 6px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 11px;
    padding: 4px;
}}
QComboBox {{
    background-color: {BORDER};
    color: {TEXT};
    border: 1px solid #1a4080;
    border-radius: 6px;
    padding: 4px 8px;
    min-height: 24px;
}}
QComboBox:hover {{ border-color: {BLUE}; }}
QComboBox QAbstractItemView {{
    background-color: {CARD_BG};
    color: {TEXT};
    border: 1px solid {BORDER};
    selection-background-color: {BORDER};
}}
QComboBox::drop-down {{ border: none; width: 20px; }}
QScrollBar:vertical {{
    background: {DARK_BG}; width: 6px; border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER}; border-radius: 3px; min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QStatusBar {{
    background-color: {CARD_BG};
    color: {DIM};
    font-size: 11px;
    border-top: 1px solid {BORDER};
}}
QSplitter::handle {{ background-color: {BORDER}; }}
QSplitter::handle:horizontal {{ width: 2px; }}
QSplitter::handle:vertical {{ height: 2px; }}
"""


# ══════════════════════════════════════════════════════════════════════
#  模型列表（显示名 → 文件名，分离存储）
# ══════════════════════════════════════════════════════════════════════
MODEL_ENTRIES = [
    # (显示文本,  文件名,  是否为分组标题)
    ("-- YOLOv8  经典稳定 ----------------", "",           True),
    ("v8n   Nano    3.2M   最快 速度优先",       "yolov8n.pt", False),
    ("v8s   Small  11.2M   快   均衡",         "yolov8s.pt", False),
    ("v8m   Medium 25.9M   均衡",              "yolov8m.pt", False),
    ("v8l   Large  43.7M   精准",              "yolov8l.pt", False),
    ("v8x   XLarge 68.2M   最精准 精度优先",     "yolov8x.pt", False),
    ("-- YOLO11  精度更高 ----------------", "",           True),
    ("v11n  Nano    2.6M   最快",              "yolo11n.pt", False),
    ("v11s  Small   9.4M   快",               "yolo11s.pt", False),
    ("v11m  Medium 20.1M   均衡",             "yolo11m.pt", False),
    ("v11l  Large  25.3M   精准",             "yolo11l.pt", False),
    ("v11x  XLarge 56.9M   最精准",           "yolo11x.pt", False),
    ("-- YOLO26  最新一代 ----------------", "",           True),
    ("v26n  Nano    2.4M   最快",              "yolo26n.pt", False),
    ("v26s  Small   9.5M   快",               "yolo26s.pt", False),
    ("v26m  Medium 20.4M   均衡",             "yolo26m.pt", False),
    ("v26l  Large  24.8M   精准",             "yolo26l.pt", False),
    ("v26x  XLarge 55.7M   最精准",           "yolo26x.pt", False),
]


# ══════════════════════════════════════════════════════════════════════
#  后台线程
# ══════════════════════════════════════════════════════════════════════

class CaptureThread(QThread):
    """全速读取最新帧，通过信号发给主线程渲染，不阻塞 UI"""
    frame_ready = pyqtSignal(np.ndarray)

    def __init__(self, detector):
        super().__init__()
        self.detector = detector
        self._running = True

    def run(self):
        interval = 1.0 / 30   # 目标 30fps
        logger.info("GUI 采集线程已启动")
        while self._running:
            t0 = time.perf_counter()
            # 永远取最新原始帧 + 叠加检测框，不受推理延迟影响
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
                self.status_ready.emit(self.engine.get_full_status())
            except Exception as e:
                logger.debug(f"状态获取失败: {e}")
            self.msleep(1000)

    def stop(self):
        self._running = False
        self.wait(2000)


# ══════════════════════════════════════════════════════════════════════
#  辅助函数
# ══════════════════════════════════════════════════════════════════════

def _lbl(text, color=TEXT, bold=False, size=13, mono=False):
    """快速创建样式化 QLabel"""
    w = QLabel(text)
    w.setStyleSheet(
        f"color:{color};"
        f"font-size:{size}px;"
        f"{'font-weight:bold;' if bold else ''}"
        f"{'font-family:Consolas,monospace;' if mono else ''}"
    )
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

    def __init__(self, engine, detector):
        super().__init__()
        self.engine   = engine
        self.detector = detector

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
        self._apply_saved_settings()   # 恢复上次配置
        self._start_threads()

    # ── 布局构建 ──────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(0)

        # 主分割器：大屏左右分栏，小屏上下分栏，避免树莓派小屏挤压乱排。
        orientation = Qt.Orientation.Vertical if self.compact_ui else Qt.Orientation.Horizontal
        splitter = QSplitter(orientation)
        splitter.setHandleWidth(4)

        # ── 左侧 ──
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0 if self.compact_ui else 4, 0)
        left_layout.setSpacing(8)

        # 视频+日志 垂直分割
        v_splitter = QSplitter(Qt.Orientation.Vertical)
        v_splitter.addWidget(self._build_video_card())
        v_splitter.addWidget(self._build_log_card())
        v_splitter.setStretchFactor(0, 4)
        v_splitter.setStretchFactor(1, 1)
        left_layout.addWidget(v_splitter)

        # ── 右侧（可滚动的控制面板）──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0 if self.compact_ui else 4, 4 if self.compact_ui else 0, 0, 0)
        right_layout.setSpacing(8)
        right_layout.addWidget(self._build_detection_card())
        right_layout.addWidget(self._build_env_card())
        right_layout.addWidget(self._build_device_card())
        right_layout.addWidget(self._build_model_card())
        right_layout.addStretch()
        scroll.setWidget(right_widget)

        splitter.addWidget(left_widget)
        splitter.addWidget(scroll)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        if self.compact_ui:
            total_height = self.height() if self.height() > 0 else 700
            splitter.setSizes([int(total_height * 0.58), int(total_height * 0.42)])
        else:
            total_width = self.width() if self.width() > 0 else 1200
            splitter.setSizes([int(total_width * 0.62), int(total_width * 0.38)])

        root.addWidget(splitter)

        # 状态栏
        sb = QStatusBar()
        self.setStatusBar(sb)
        self.lbl_status = QLabel("系统初始化中…")
        self.lbl_status.setStyleSheet(f"color:{DIM};font-size:11px;")
        sb.addWidget(self.lbl_status)

    # ── 视频卡片 ──────────────────────────────────────────────────────

    def _build_video_card(self):
        box = QGroupBox("实时监控画面")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(6, 14, 6, 6)
        layout.setSpacing(6)

        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Ignored 防止每帧撑大 label 触发布局重算（流畅度关键）
        self.video_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.video_label.setStyleSheet(
            f"background:{DARK_BG};border-radius:6px;border:1px solid {BORDER};")
        self.video_label.setMinimumHeight(320)
        layout.addWidget(self.video_label, stretch=1)

        # 性能行
        perf = QHBoxLayout()
        perf.setSpacing(16)
        self.lbl_fps     = _lbl("采集: — fps", DIM, size=11, mono=True)
        self.lbl_infer   = _lbl("推理: — ms",  DIM, size=11, mono=True)
        self.lbl_backend = _lbl("后端: —",      DIM, size=11)
        for w in (self.lbl_fps, self.lbl_infer, self.lbl_backend):
            perf.addWidget(w)
        perf.addStretch()
        layout.addLayout(perf)
        return box

    # ── 日志卡片 ──────────────────────────────────────────────────────

    def _build_log_card(self):
        box = QGroupBox("操作日志")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(6, 14, 6, 6)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        return box

    # ── 人员检测卡片 ──────────────────────────────────────────────────

    def _build_detection_card(self):
        box = QGroupBox("人员检测")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 16, 10, 10)
        layout.setSpacing(8)

        # 大数字
        self.lbl_count = QLabel("0")
        self.lbl_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_count.setFont(QFont("Consolas", 42, QFont.Weight.Bold))
        self.lbl_count.setStyleSheet(f"color:{RED};")
        layout.addWidget(self.lbl_count)

        # 状态行
        row1 = QHBoxLayout()
        row1.addWidget(_lbl("原始检测:", DIM))
        self.lbl_raw = _lbl("—", TEXT, bold=True)
        row1.addWidget(self.lbl_raw)
        row1.addStretch()
        row1.addWidget(_lbl("稳定状态:", DIM))
        self.lbl_stable = _lbl("—", TEXT, bold=True)
        row1.addWidget(self.lbl_stable)
        layout.addLayout(row1)

        layout.addWidget(_sep())

        # 检测间隔
        row2 = QHBoxLayout()
        row2.addWidget(_lbl("检测间隔:", DIM))
        self.lbl_interval = _lbl("2.0 s", GREEN, bold=True, mono=True)
        row2.addWidget(self.lbl_interval)
        row2.addStretch()
        layout.addLayout(row2)

        self.slider_interval = QSlider(Qt.Orientation.Horizontal)
        self.slider_interval.setRange(5, 200)   # 0.5s ~ 20s，步长0.1s
        self.slider_interval.setValue(20)
        self.slider_interval.valueChanged.connect(
            lambda v: self.lbl_interval.setText(f"{v/10:.1f} s"))
        self.slider_interval.sliderReleased.connect(self._on_interval_released)
        layout.addWidget(self.slider_interval)

        hint = _lbl("建议间隔 = 推理耗时 × 1.5", DIM, size=10)
        self.lbl_suggest = _lbl("", AMBER, size=10, mono=True)
        row3 = QHBoxLayout()
        row3.addWidget(hint)
        row3.addWidget(self.lbl_suggest)
        row3.addStretch()
        layout.addLayout(row3)

        layout.addWidget(_sep())

        # 模式切换
        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        self.btn_auto   = QPushButton("自动模式")
        self.btn_manual = QPushButton("手动模式")
        self.btn_auto.clicked.connect(lambda: self._set_mode("AUTO"))
        self.btn_manual.clicked.connect(lambda: self._set_mode("MANUAL"))
        mode_row.addWidget(self.btn_auto)
        mode_row.addWidget(self.btn_manual)
        layout.addLayout(mode_row)

        return box

    # ── 环境传感器卡片 ────────────────────────────────────────────────

    def _build_env_card(self):
        box = QGroupBox("环境传感器")
        grid = QGridLayout(box)
        grid.setContentsMargins(10, 16, 10, 10)
        grid.setSpacing(8)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        grid.addWidget(_lbl("温度:", DIM), 0, 0)
        self.lbl_temp = _lbl("—°C", TEXT, bold=True, mono=True)
        grid.addWidget(self.lbl_temp, 0, 1)

        grid.addWidget(_lbl("湿度:", DIM), 0, 2)
        self.lbl_humi = _lbl("—%", TEXT, bold=True, mono=True)
        grid.addWidget(self.lbl_humi, 0, 3)

        grid.addWidget(_lbl("光照:", DIM), 1, 0)
        self.lbl_lux = _lbl("— lux", TEXT, bold=True, mono=True)
        grid.addWidget(self.lbl_lux, 1, 1)

        grid.addWidget(_lbl("空调模式:", DIM), 1, 2)
        self.lbl_ac_mode = _lbl("—", TEXT, bold=True)
        grid.addWidget(self.lbl_ac_mode, 1, 3)

        return box

    # ── 设备控制卡片 ──────────────────────────────────────────────────

    def _build_device_card(self):
        box = QGroupBox("设备控制")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 16, 10, 10)
        layout.setSpacing(8)

        # 灯光
        row_light = QHBoxLayout()
        row_light.addWidget(_lbl("灯光 (舵机):", DIM))
        self.lbl_light = _lbl("关闭", RED, bold=True)
        row_light.addWidget(self.lbl_light)
        row_light.addStretch()
        b_on  = _btn("开灯", "on",  60)
        b_off = _btn("关灯", "off", 60)
        b_on.clicked.connect(lambda: self._control("light", True))
        b_off.clicked.connect(lambda: self._control("light", False))
        row_light.addWidget(b_on)
        row_light.addWidget(b_off)
        layout.addLayout(row_light)

        servo_box = QGroupBox("舵机标定 / 录制")
        servo_layout = QVBoxLayout(servo_box)
        servo_layout.setContentsMargins(8, 12, 8, 8)
        servo_layout.setSpacing(6)

        row_servo_info = QHBoxLayout()
        row_servo_info.addWidget(_lbl("当前角度:", DIM, size=11))
        self.lbl_servo_angle = _lbl("90°", GREEN, bold=True, mono=True, size=11)
        row_servo_info.addWidget(self.lbl_servo_angle)
        row_servo_info.addStretch()
        self.lbl_servo_saved = _lbl("开灯按压60° / 关灯按压120° / 中立回位90°", DIM, size=10, mono=True)
        row_servo_info.addWidget(self.lbl_servo_saved)
        servo_layout.addLayout(row_servo_info)

        self.slider_servo = QSlider(Qt.Orientation.Horizontal)
        self.slider_servo.setRange(0, 180)
        self.slider_servo.setValue(90)
        self.slider_servo.valueChanged.connect(
            lambda v: self.lbl_servo_angle.setText(f"{v}°"))
        self.slider_servo.sliderReleased.connect(self._servo_move_slider)
        servo_layout.addWidget(self.slider_servo)

        row_servo_nudge = QHBoxLayout()
        for text, delta in (("-5°", -5), ("-1°", -1), ("+1°", 1), ("+5°", 5)):
            btn = _btn(text, width=56)
            btn.clicked.connect(lambda _, d=delta: self._servo_nudge(d))
            row_servo_nudge.addWidget(btn)
        row_servo_nudge.addStretch()
        btn_center = _btn("回中立", width=70)
        btn_center.clicked.connect(self._servo_move_neutral)
        row_servo_nudge.addWidget(btn_center)
        servo_layout.addLayout(row_servo_nudge)

        row_servo_save = QHBoxLayout()
        btn_save_on = _btn("记为开灯按压角", "on", 110)
        btn_save_off = _btn("记为关灯按压角", "off", 110)
        btn_save_neutral = _btn("记为中立回位角", width=118)
        btn_save_on.clicked.connect(lambda: self._servo_save_preset("on"))
        btn_save_off.clicked.connect(lambda: self._servo_save_preset("off"))
        btn_save_neutral.clicked.connect(lambda: self._servo_save_preset("neutral"))
        row_servo_save.addWidget(btn_save_on)
        row_servo_save.addWidget(btn_save_off)
        row_servo_save.addWidget(btn_save_neutral)
        servo_layout.addLayout(row_servo_save)

        row_servo_duration = QHBoxLayout()
        row_servo_duration.addWidget(_lbl("保持时长(s):", DIM, size=11))
        self.edit_servo_duration = QLineEdit("0.5")
        self.edit_servo_duration.setFixedWidth(72)
        self.edit_servo_duration.setStyleSheet(
            f"background:{BORDER};color:{TEXT};border:1px solid #1a4080;"
            f"border-radius:6px;padding:4px 8px;min-height:24px;")
        row_servo_duration.addWidget(self.edit_servo_duration)
        btn_save_duration = _btn("保存时长", width=78)
        btn_save_duration.clicked.connect(self._servo_save_duration)
        row_servo_duration.addWidget(btn_save_duration)
        row_servo_duration.addStretch()
        servo_layout.addLayout(row_servo_duration)

        layout.addWidget(servo_box)
        layout.addWidget(_sep())

        # 电源
        row_power = QHBoxLayout()
        row_power.addWidget(_lbl("电源 (继电器):", DIM))
        self.lbl_power = _lbl("关闭", RED, bold=True)
        row_power.addWidget(self.lbl_power)
        row_power.addStretch()
        b_on2  = _btn("通电", "on",  60)
        b_off2 = _btn("断电", "off", 60)
        b_on2.clicked.connect(lambda: self._control("power", True))
        b_off2.clicked.connect(lambda: self._control("power", False))
        row_power.addWidget(b_on2)
        row_power.addWidget(b_off2)
        layout.addLayout(row_power)

        layout.addWidget(_sep())

        # 空调
        row_ac = QHBoxLayout()
        row_ac.addWidget(_lbl("空调 (红外):", DIM))
        self.lbl_ac = _lbl("关闭", RED, bold=True)
        row_ac.addWidget(self.lbl_ac)
        row_ac.addStretch()
        b_cool = _btn("制冷", "on",  52)
        b_heat = _btn("制热", "on",  52)
        b_aoff = _btn("关闭", "off", 52)
        b_cool.clicked.connect(lambda: self._control_ac(True, "cooling"))
        b_heat.clicked.connect(lambda: self._control_ac(True, "heating"))
        b_aoff.clicked.connect(lambda: self._control_ac(False))
        row_ac.addWidget(b_cool)
        row_ac.addWidget(b_heat)
        row_ac.addWidget(b_aoff)
        layout.addLayout(row_ac)

        return box

    # ── 模型切换卡片 ──────────────────────────────────────────────────

    def _build_model_card(self):
        box = QGroupBox("模型切换")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 16, 10, 10)
        layout.setSpacing(8)

        # 下拉框：显示名与文件名分离
        self.combo_model = QComboBox()
        self.combo_model.setMaxVisibleItems(20)
        for label, fname, is_header in MODEL_ENTRIES:
            self.combo_model.addItem(label, userData=fname)  # userData 存文件名
        # 分组标题行：禁用 + 橙色
        model_obj = self.combo_model.model()
        for i, (_, fname, is_header) in enumerate(MODEL_ENTRIES):
            if is_header:
                item = model_obj.item(i)
                item.setEnabled(False)
                item.setForeground(QColor(AMBER))
        # 默认选中 yolov8n
        self.combo_model.setCurrentIndex(1)
        layout.addWidget(self.combo_model)

        # 自定义路径输入提示
        hint = _lbl("或直接输入本地 .pt 文件路径:", DIM, size=11)
        layout.addWidget(hint)

        from PyQt6.QtWidgets import QLineEdit
        self.edit_custom = QLineEdit()
        self.edit_custom.setPlaceholderText("例: C:/models/best.pt")
        self.edit_custom.setStyleSheet(
            f"background:{BORDER};color:{TEXT};border:1px solid #1a4080;"
            f"border-radius:6px;padding:4px 8px;min-height:26px;")
        layout.addWidget(self.edit_custom)

        btn_switch = QPushButton("切换模型")
        btn_switch.setStyleSheet(
            f"background:{BLUE};color:white;font-weight:bold;"
            f"border-radius:6px;padding:6px;")
        btn_switch.clicked.connect(self._switch_model)
        layout.addWidget(btn_switch)

        self.lbl_model_cur = _lbl("当前: yolov8n.pt", DIM, size=11)
        self.lbl_model_msg = _lbl("", GREEN, size=11)
        layout.addWidget(self.lbl_model_cur)
        layout.addWidget(self.lbl_model_msg)

        return box

    # ── 恢复上次配置 ──────────────────────────────────────────────────

    def _apply_saved_settings(self):
        """从 user_settings.json 恢复上次的配置"""
        s = user_settings.load()

        # 恢复模型选择
        saved_model = s.get("yolo_model", "yolov8n.pt")
        # 在下拉框中找到对应条目
        for i, (_, fname, _) in enumerate(MODEL_ENTRIES):
            if fname == saved_model:
                self.combo_model.setCurrentIndex(i)
                break
        self.lbl_model_cur.setText(f"当前: {saved_model}")

        # 恢复检测间隔
        interval = s.get("detection_interval", 2.0)
        self.slider_interval.setValue(int(interval * 10))
        self.lbl_interval.setText(f"{interval:.1f} s")

        # 恢复控制模式
        mode = s.get("control_mode", "AUTO")
        self.engine.set_mode(mode)

    # ── 后台线程 ──────────────────────────────────────────────────────

    def _start_threads(self):
        self.cap_thread = CaptureThread(self.detector)
        self.cap_thread.frame_ready.connect(self._on_frame)
        self.cap_thread.start()

        self.stat_thread = StatusThread(self.engine)
        self.stat_thread.status_ready.connect(self._on_status)
        self.stat_thread.start()

    # ── 槽：帧渲染（主线程，直接操作 QLabel）────────────────────────

    def _on_frame(self, frame: np.ndarray):
        """
        BGR numpy array → QPixmap，Format_BGR888 直接映射内存，
        无需 cvtColor，FastTransformation 省去平滑插值开销。
        """
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
        det  = s.get("detector", {})
        sen  = s.get("sensor", {})
        dev  = s.get("devices", {})
        flt  = s.get("filter", {})
        lamb = s.get("light_ambient", {})
        logs = s.get("recent_logs", [])
        mode = s.get("mode", "AUTO")

        # ── 人员检测 ──
        count = det.get("person_count", 0)
        self.lbl_count.setText(str(count))
        self.lbl_count.setStyleSheet(
            f"color:{GREEN if count > 0 else RED};"
            f"font-size:42px;font-weight:bold;")

        raw = det.get("has_person", False)
        self.lbl_raw.setText("检测到" if raw else "未检测")
        self.lbl_raw.setStyleSheet(
            f"color:{GREEN if raw else DIM};font-weight:bold;")

        stable = flt.get("stable_state", False)
        self.lbl_stable.setText("有人" if stable else "无人")
        self.lbl_stable.setStyleSheet(
            f"color:{GREEN if stable else RED};font-weight:bold;")

        # ── 性能 ──
        fps = det.get("stream_fps", 0)
        self.lbl_fps.setText(f"采集: {fps} fps")

        infer_ms = det.get("infer_ms", 0)
        ic = GREEN if infer_ms < 200 else (AMBER if infer_ms < 500 else RED)
        self.lbl_infer.setText(f"推理: {infer_ms} ms")
        self.lbl_infer.setStyleSheet(f"color:{ic};font-size:11px;font-family:Consolas,monospace;")

        self.lbl_backend.setText(f"后端: {det.get('camera_backend','—')}")

        if infer_ms > 0:
            suggest = infer_ms * 1.5 / 1000
            self.lbl_suggest.setText(f"建议 ≥ {suggest:.1f}s")

        # ── 模型 ──
        model_name = det.get("model_name", "—")
        loading    = det.get("model_loading", False)
        self.lbl_model_cur.setText(
            "加载中…" if loading else f"当前: {model_name}")
        self.lbl_model_cur.setStyleSheet(
            f"color:{AMBER};font-size:11px;" if loading
            else f"color:{DIM};font-size:11px;")

        # ── 环境 ──
        self.lbl_temp.setText(f"{sen.get('temperature','—')}°C")
        self.lbl_humi.setText(f"{sen.get('humidity','—')}%")
        lux = lamb.get("lux", "—") if lamb else "—"
        self.lbl_lux.setText(f"{lux} lux")

        ac_map = {"off": "关闭", "cooling": "制冷", "heating": "制热"}
        ac_mode_str = ac_map.get(dev.get("ac_mode", "off"), "—")
        self.lbl_ac_mode.setText(ac_mode_str)
        self.lbl_ac_mode.setStyleSheet(
            f"color:{GREEN if dev.get('ac') else DIM};font-weight:bold;")

        # ── 设备 ──
        self._dev_lbl(self.lbl_light, dev.get("light", False), "开启", "关闭")
        self._dev_lbl(self.lbl_power, dev.get("power", False), "开启", "关闭")
        self._dev_lbl(self.lbl_ac,    dev.get("ac",    False), ac_mode_str, "关闭")

        servo = dev.get("servo_calibration", {})
        if servo:
            current_angle = int(servo.get("current_angle", 90))
            if not self.slider_servo.isSliderDown():
                self.slider_servo.setValue(current_angle)
            self.lbl_servo_angle.setText(f"{current_angle}°")
            self.lbl_servo_saved.setText(
                f"开灯按压{servo.get('angle_on', 60)}° / "
                f"关灯按压{servo.get('angle_off', 120)}° / "
                f"中立回位{servo.get('angle_neutral', 90)}°"
            )
            self.edit_servo_duration.setText(str(servo.get("action_duration", 0.5)))

        # ── 模式按钮高亮 ──
        self.btn_auto.setProperty(
            "role", "mode_active" if mode == "AUTO" else "normal")
        self.btn_manual.setProperty(
            "role", "mode_manual_active" if mode == "MANUAL" else "normal")
        for b in (self.btn_auto, self.btn_manual):
            b.style().unpolish(b)
            b.style().polish(b)

        # ── 日志 ──
        if logs:
            self.log_text.clear()
            for entry in reversed(logs[-40:]):
                self.log_text.append(
                    f'<span style="color:{GREEN}">{entry["time"]}</span>'
                    f'&nbsp;&nbsp;{entry["action"]}')

        # ── 状态栏 ──
        self.lbl_status.setText(
            f"人数: {count}  |  温度: {sen.get('temperature','—')}°C  |  "
            f"模式: {mode}  |  {det.get('camera_backend','—')}")

    def _dev_lbl(self, lbl: QLabel, on: bool, on_text: str, off_text: str):
        lbl.setText(on_text if on else off_text)
        lbl.setStyleSheet(
            f"color:{GREEN};font-weight:bold;" if on
            else f"color:{RED};font-weight:bold;")

    # ── 控制槽 ────────────────────────────────────────────────────────

    def _on_interval_released(self):
        s = self.slider_interval.value() / 10.0
        self.detector.set_detection_interval(s)
        self.engine._log_action(f"检测间隔调整为 {s}s")
        user_settings.save({"detection_interval": s})

    def _set_mode(self, mode: str):
        self.engine.set_mode(mode)
        user_settings.save({"control_mode": mode})

    def _control(self, device: str, on: bool):
        if device == "light":
            self.engine.devices.set(device, on, force=True)
        else:
            self.engine.devices.set(device, on)
        self.engine._log_action(
            f"[手动] {'开启' if on else '关闭'} {device}")

    def _control_ac(self, on: bool, mode: str = "cooling"):
        self.engine.devices.set_ac(on, mode)
        self.engine._log_action(
            f"[手动] 空调 {'开启-' + mode if on else '关闭'}")

    def _servo_move_slider(self):
        angle = self.slider_servo.value()
        actual = self.engine.devices.move_servo_to(angle)
        self.slider_servo.setValue(actual)
        self.engine._log_action(f"[标定] 舵机移动到 {actual}°")

    def _servo_nudge(self, delta: int):
        actual = self.engine.devices.nudge_servo(delta)
        self.slider_servo.setValue(actual)
        self.engine._log_action(f"[标定] 舵机微调 {delta:+d}° -> {actual}°")

    def _servo_move_neutral(self):
        actual = self.engine.devices.move_servo_to(self.engine.devices.get_servo_status()["angle_neutral"])
        self.slider_servo.setValue(actual)
        self.engine._log_action(f"[标定] 舵机回到中立 {actual}°")

    def _servo_save_preset(self, preset: str):
        status = self.engine.devices.save_servo_preset(preset, self.slider_servo.value())
        self.slider_servo.setValue(status["current_angle"])
        preset_map = {"on": "开灯按压角", "off": "关灯按压角", "neutral": "中立回位角"}
        self.engine._log_action(f"[标定] 已记录舵机{preset_map.get(preset, preset)}")

    def _servo_save_duration(self):
        try:
            duration = float(self.edit_servo_duration.text().strip())
        except ValueError:
            self.lbl_status.setText("舵机保持时长必须是数字")
            return
        status = self.engine.devices.save_servo_config(action_duration=duration)
        self.edit_servo_duration.setText(str(status["action_duration"]))
        self.engine._log_action(f"[标定] 已保存舵机保持时长 {status['action_duration']:.2f}s")

    def _switch_model(self):
        # 优先取自定义路径输入框
        custom = self.edit_custom.text().strip()
        if custom:
            model_path = custom
        else:
            # 从下拉框 userData 取文件名（与显示文本分离）
            model_path = self.combo_model.currentData()

        if not model_path:
            self.lbl_model_msg.setText("请选择模型或输入路径")
            self.lbl_model_msg.setStyleSheet(f"color:{RED};font-size:11px;")
            return

        result = self.detector.switch_model(model_path)
        if result["ok"]:
            self.lbl_model_msg.setText(f"正在加载 {model_path}…")
            self.lbl_model_msg.setStyleSheet(f"color:{AMBER};font-size:11px;")
            self.engine._log_action(f"切换模型: {model_path}")
            self.edit_custom.clear()
            user_settings.save({"yolo_model": model_path})
        else:
            self.lbl_model_msg.setText(f"失败: {result.get('error','')}")
            self.lbl_model_msg.setStyleSheet(f"color:{RED};font-size:11px;")

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

    # 优先使用树莓派常见中文字体；缺字时 Qt 会继续走系统 fallback。
    font = QFont()
    available = QFontDatabase.families()
    for family in ("Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Micro Hei",
                   "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC"):
        if family in available:
            font.setFamily(family)
            break
    font.setPointSize(9 if sys.platform.startswith("linux") else 10)
    app.setFont(font)
    app.setStyleSheet(STYLE)

    logger.info("=" * 55)
    logger.info("  智能教室测控系统 — 本地 GUI 版本")
    logger.info("=" * 55)

    try:
        from detector import PersonDetector
        from device_manager import DeviceManager
        from sensor import TemperatureSensor
        from light_sensor import LightSensor
        from decision_engine import DecisionEngine
        from data_logger import setup_file_logging
        import config
    except ImportError as e:
        print(f"模块导入失败: {e}")
        sys.exit(1)

    if config.ENABLE_FILE_LOG:
        setup_file_logging()

    # 加载用户配置，覆盖 config.py 默认值
    saved = user_settings.load()
    config.YOLO_MODEL = saved.get("yolo_model", config.YOLO_MODEL)
    config.DETECTION_INTERVAL = saved.get("detection_interval", config.DETECTION_INTERVAL)

    logger.info("初始化系统模块…")
    detector = PersonDetector()
    devices  = DeviceManager()
    sensor   = TemperatureSensor()
    light    = LightSensor()
    engine   = DecisionEngine(detector, devices, sensor, light)

    detector.start()
    sensor.start()
    light.start()
    engine.start()

    def shutdown():
        logger.info("正在关闭系统…")
        detector.stop()
        sensor.stop()
        light.stop()
        engine.stop()
        devices.all_off()
        devices.cleanup()
        logger.info("系统已安全关闭")

    window = MainWindow(engine, detector)
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
