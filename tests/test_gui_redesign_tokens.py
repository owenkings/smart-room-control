"""
静态验证：GUI 重设计颜色 token 和接口不变性
对应 design.md §9.2 中的 Property 1-6
Validates: Requirements 21.1–21.20
"""
import re
import pathlib

ROOT = pathlib.Path(__file__).parent.parent
GUI_PY = ROOT / "gui_app.py"
HTML = ROOT / "templates" / "index.html"

# ── Property 1: 颜色 Token 规格一致性 ──────────────────────────────
EXPECTED_PYTHON_TOKENS = {
    'BG_PAGE':       '#f6f7f9',
    'BG_CARD':       '#ffffff',
    'BG_SUBTLE':     '#f2f4f7',
    'BORDER':        '#e5e7eb',
    'BORDER_STRONG': '#d0d5dd',
    'TEXT_MAIN':     '#111827',
    'TEXT_MUTED':    '#667085',
    'TEXT_SUBTLE':   '#98a2b3',
    'ACCENT':        '#3f596d',
    'ACCENT_HOVER':  '#334a5c',
    'SUCCESS':       '#2e7d32',
    'DANGER':        '#c62828',
    'WARNING':       '#b7791f',
}
EXPECTED_CSS_TOKENS = {
    '--bg-page':       '#f6f7f9',
    '--bg-card':       '#ffffff',
    '--bg-subtle':     '#f2f4f7',
    '--border':        '#e5e7eb',
    '--border-strong': '#d0d5dd',
    '--text-main':     '#111827',
    '--text-muted':    '#667085',
    '--text-subtle':   '#98a2b3',
    '--accent':        '#3f596d',
    '--accent-hover':  '#334a5c',
    '--success':       '#2e7d32',
    '--danger':        '#c62828',
    '--warning':       '#b7791f',
}


def test_python_color_tokens():
    """Property 1: Python 颜色常量值符合规格"""
    src = GUI_PY.read_text(encoding='utf-8')
    for name, expected in EXPECTED_PYTHON_TOKENS.items():
        pattern = rf'{name}\s*=\s*["\']({re.escape(expected)})["\']'
        assert re.search(pattern, src, re.IGNORECASE), \
            f"Python 常量 {name} 应为 {expected}"


def test_css_color_tokens():
    """Property 1: CSS 变量值符合规格"""
    src = HTML.read_text(encoding='utf-8')
    for name, expected in EXPECTED_CSS_TOKENS.items():
        pattern = rf'{re.escape(name)}\s*:\s*({re.escape(expected)})'
        assert re.search(pattern, src, re.IGNORECASE), \
            f"CSS 变量 {name} 应为 {expected}"


# ── Property 2: JS 函数名不变性 ────────────────────────────────────
REQUIRED_JS_FUNCTIONS = [
    'setMode', 'servoAction', 'servoMove', 'servoNudge', 'servoCalibrate',
    'saveOffsets', 'saveConditions', 'saveThreshold', 'useCurrent',
    'saveTimeFallback', 'saveACThresholds', 'irLearn', 'loadIR',
    'irSend', 'irDel', 'switchModel', 'fetchStatus', 'connectSocket',
    'applyInterval',
]


def test_js_function_names_preserved():
    """Property 2: 关键 JS 函数名在改造后仍然存在"""
    src = HTML.read_text(encoding='utf-8')
    for fn in REQUIRED_JS_FUNCTIONS:
        assert f'function {fn}' in src or f'{fn}(' in src, \
            f"JS 函数 {fn} 不应被删除或重命名"


# ── Property 3: DOM ID 不变性 ──────────────────────────────────────
REQUIRED_DOM_IDS = [
    'personCount', 'temperature', 'humidity', 'lux', 'streamFps', 'inferMs',
    'videoImg', 'wsDot', 'wsLabel', 'btnAuto', 'btnManual', 'modelBadge',
    'servoAngle', 'servoSlider', 'clock', 'irCmdList', 'irStatus',
    'irNameInput', 'modelSelect', 'msgModel', 'msgCond', 'msgThreshold',
    'msgAC', 'intervalLabel', 'intervalSlider', 'videoStatus',
]


def test_dom_ids_preserved():
    """Property 3: 关键 DOM ID 在改造后仍然存在"""
    src = HTML.read_text(encoding='utf-8')
    for dom_id in REQUIRED_DOM_IDS:
        assert f'id="{dom_id}"' in src or f"id='{dom_id}'" in src, \
            f"DOM ID {dom_id} 不应被删除或重命名"


# ── Property 4: 旧蓝色不再作为大面积背景色 ─────────────────────────
OLD_BLUES = ['#2979ff', '#2979FF', '#4A90D9', '#4a90d9']


def test_old_blue_not_used_as_background():
    """Property 4: 旧主色调不再出现在 background 定义中"""
    for path, src in [(GUI_PY, GUI_PY.read_text(encoding='utf-8')),
                      (HTML,   HTML.read_text(encoding='utf-8'))]:
        for blue in OLD_BLUES:
            # 允许出现在注释中，但不允许出现在 background-color 或 --accent 定义中
            bg_pattern = rf'background(?:-color)?\s*[=:]\s*["\']?{re.escape(blue)}'
            accent_def = rf'--accent\s*:\s*{re.escape(blue)}'
            assert not re.search(bg_pattern, src, re.IGNORECASE), \
                f"{path.name}: 旧蓝色 {blue} 不应用于 background"
            assert not re.search(accent_def, src, re.IGNORECASE), \
                f"{path.name}: 旧蓝色 {blue} 不应定义为 --accent"


# ── Property 5: 视频 transform scale 已移除 ────────────────────────
def test_video_transform_scale_removed():
    """Property 5: index.html 中不应包含 transform: scale(1.5)"""
    src = HTML.read_text(encoding='utf-8')
    assert 'scale(1.5)' not in src, \
        "视频 transform: scale(1.5) 应已移除"


# ── Property 6: 日志面板使用浅色背景 ──────────────────────────────
def test_log_panel_light_background():
    """Property 6: QTextEdit 不应使用深色背景 #1e2430"""
    src = GUI_PY.read_text(encoding='utf-8')
    assert '#1e2430' not in src, \
        "日志面板深色背景 #1e2430 应已替换为浅色"


# ── Property 7: 本地 GUI 控件箭头可见性 ────────────────────────────
def test_qt_spinbox_and_combobox_arrows_are_drawn():
    """Property 7: SpinBox/ComboBox 箭头应使用真实透明图片，而不是仅设置 color"""
    src = GUI_PY.read_text(encoding='utf-8')
    for asset in ['ui_arrow_up.png', 'ui_arrow_down.png', 'ui_combo_down.png']:
        assert (ROOT / 'assets' / asset).exists(), f"缺少箭头资源 {asset}"
    assert 'QSpinBox::up-arrow' in src
    assert 'QSpinBox::down-arrow' in src
    assert 'QComboBox::down-arrow' in src
    assert 'image: url("{ARROW_UP_ICON}")' in src
    assert 'image: url("{ARROW_DOWN_ICON}")' in src
    assert 'image: url("{COMBO_DOWN_ICON}")' in src


# ── Property 8: 红外学习帮助悬停提示 ───────────────────────────────
def test_ir_help_button_shows_tooltip_on_hover():
    """Property 8: 红外学习问号按钮应主动显示步骤提示并垂直居中"""
    src = GUI_PY.read_text(encoding='utf-8')
    assert 'class HelpButton(QPushButton)' in src
    assert 'QToolTip.showText' in src
    assert '如何学习红外信号' in src
    assert 'Qt.AlignmentFlag.AlignVCenter' in src


# ── Property 9: SpinBox 内嵌式步进按钮布局 ─────────────────────────
def test_spinbox_stepper_is_embedded_inside_input():
    """Property 9: SpinBox 上下箭头应内嵌在输入框内且高度相加不外溢"""
    src = GUI_PY.read_text(encoding='utf-8')
    assert 'min-height: 34px;' in src
    assert 'padding: 0 28px 0 8px;' in src
    assert src.count('height: 17px;') >= 2
    assert 'border-bottom: 1px solid {BORDER};' in src
    assert 'margin: 0;' in src


# ── Property 10: 左侧监控卡片可读性 ───────────────────────────────
def test_env_and_perf_cards_use_larger_single_column_rows():
    """Property 10: 环境传感器改为四行展示，性能监控字号放大"""
    src = GUI_PY.read_text(encoding='utf-8')
    assert 'grid.addWidget(_lbl("湿度:", TEXT_DIM, size=14), 1, 0)' in src
    assert 'grid.addWidget(_lbl("光照:", TEXT_DIM, size=14), 2, 0)' in src
    assert 'grid.addWidget(_lbl("灯光:", TEXT_DIM, size=14), 3, 0)' in src
    assert 'self.lbl_fps = _lbl("— fps", TEXT_DARK, bold=True, mono=True, size=15)' in src
    assert 'font-size:15px' in src
