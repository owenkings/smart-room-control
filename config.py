"""
智能教室/实验室网络化测控系统 - 配置文件
"""

import os
import platform


def _default_simulate_gpio():
    """PC 默认模拟，树莓派默认真实硬件；也可用环境变量强制覆盖。"""
    override = os.getenv("SMART_ROOM_SIMULATE_GPIO")
    if override is not None:
        return override.strip().lower() in ("1", "true", "yes", "on", "simulate")

    machine = platform.machine().lower()
    is_raspberry_pi = platform.system() == "Linux" and machine in (
        "aarch64", "arm64", "armv7l", "armv6l"
    )
    return not is_raspberry_pi

# ============ 摄像头配置 ============
CAMERA_SOURCE = 0  # 0=USB摄像头, 或填IP摄像头地址如 "rtsp://192.168.1.100:554/stream"
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_TARGET_FPS = 30        # 目标帧率，摄像头支持的最大帧率

# ============ YOLO模型配置 ============
# PC开发/测试:    yolov8n.pt  (最快，精度低)
# 树莓派5 推荐:   yolov8s.pt 或 yolov11s.pt  (精度/速度平衡)
# 树莓派5 高精度: yolov8m.pt  (慢，但8GB内存够用)
# 模型首次运行会自动下载，之后缓存在本地
YOLO_MODEL = "yolov8n.pt"
YOLO_CONFIDENCE = 0.5
PERSON_CLASS_ID = 0

# ============ 检测与推流配置 ============
DETECTION_INTERVAL = 2.0    # 默认2秒检测一次，可在Web界面实时调整(0.5~30秒)
STREAM_JPEG_QUALITY = 75    # 推流JPEG质量(1-100)
STREAM_WS_FPS = 25          # WebSocket 推流目标帧率（实际受采集帧率限制）

# ============ 人员检测防抖滤波器 ============
PRESENCE_ON_THRESHOLD = 2   # 连续N次检测到人才判定"有人"
PRESENCE_OFF_THRESHOLD = 5  # 连续N次未检测到才判定"无人"

# ============ 舵机配置(灯光开关) ============
SERVO_PIN_LIGHT = 18
SERVO_ANGLE_ON = 60
SERVO_ANGLE_OFF = 120
SERVO_ANGLE_NEUTRAL = 90
SERVO_ACTION_DURATION = 0.5
SERVO_PWM_FREQ = 50

# ============ 光照传感器配置(BH1750) ============
LIGHT_READ_INTERVAL = 3         # 光照读取间隔(秒)
LIGHT_DARK_THRESHOLD = 150      # 低于此值判定为暗(lux)
LIGHT_BRIGHT_THRESHOLD = 400    # 高于此值判定为亮(lux)
ENABLE_BH1750 = False           # 临时禁用BH1750，改用光敏电阻数字量做环境判断

# ============ 光敏电阻反馈传感器 ============
# 注意：你的实际接线是 GPIO17 (Pin 11)，与部署指南图示不同
# 如果你按照硬件接线指南接的是 GPIO23，改回 23 即可
LIGHT_FEEDBACK_PIN = 17         # 光敏电阻模块DO引脚(BCM) — 对应 Pin 11
LIGHT_FEEDBACK_ACTIVE_LOW = True  # 亮=LOW, 暗=HIGH

# ============ 红外遥控配置(空调控制) ============
IR_SEND_PIN = 25
IR_RECV_PIN = 24
IR_PROTOCOL = "NEC"
IR_CODES = {
    "ac_on_cool": None,
    "ac_on_heat": None,
    "ac_off": None,
    "ac_temp_up": None,
    "ac_temp_down": None,
}
IR_CODES_FILE = "ir_codes.json"

# ============ 继电器配置(电源控制) ============
RELAY_PIN_POWER = 27
RELAY_ACTIVE_LOW = True

# ============ 温度传感器配置 ============
TEMP_SENSOR_PIN = 4
TEMP_READ_INTERVAL = 10
ENABLE_DHT22 = False            # 临时禁用DHT22，改为模拟温湿度

# ============ 决策逻辑配置 ============
NO_PERSON_TIMEOUT = 30
AC_TEMP_HIGH = 28.0
AC_TEMP_LOW = 18.0
AC_TEMP_COMFORT_MIN = 22.0
AC_TEMP_COMFORT_MAX = 26.0

# 灯光控制策略
LIGHT_USE_AMBIENT = True        # True=有人且光照不足才开灯, False=有人就开灯
LIGHT_FEEDBACK_ENABLED = True   # 是否启用光敏电阻反馈闭环
LIGHT_RETRY_MAX = 2             # 舵机按压后，若反馈状态不符，最多重试次数

# ============ 控制模式 ============
DEFAULT_MODE = "AUTO"  # AUTO=自动决策, MANUAL=仅手动控制

# ============ 数据日志 ============
ENABLE_FILE_LOG = True
ENABLE_CSV_LOG = True
CSV_SAMPLE_INTERVAL = 10  # 多少秒记录一次快照

# ============ Web服务配置 ============
WEB_HOST = "0.0.0.0"
WEB_PORT = 8080

# ============ 运行模式 ============
# True=PC模拟模式, False=树莓派真实模式
# 覆盖方式:
#   Windows/PC测试:  set SMART_ROOM_SIMULATE_GPIO=1
#   树莓派真实硬件:  export SMART_ROOM_SIMULATE_GPIO=0
SIMULATE_GPIO = _default_simulate_gpio()
