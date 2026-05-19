"""
智能教室/实验室网络化测控系统 - 统一配置

只保留硬件已验证的引脚与采样参数，以及标准目录路径。
不包含任何继电器（relay）相关常量。

参考来源（已验证可用的测试脚本）：
  - test_dht11.py  → DHT22_PIN, DHT22_INTERVAL
  - test_bh1750.py → BH1750_BUS, BH1750_ADDR, BH1750_MODE, BH1750_INTERVAL
  - test_ir.py     → IR_RECV_PIN, IR_SEND_PIN
  - test_servo.py  → SERVO_PIN, SERVO_MIN_ANGLE, SERVO_MAX_ANGLE,
                     SERVO_MIN_PULSE, SERVO_MAX_PULSE
"""

from pathlib import Path

# ============ 项目目录 ============
# 所有路径都基于 config.py 所在目录（仓库根目录）派生，保证可移植
PROJECT_ROOT: Path = Path(__file__).resolve().parent
DATA_DIR: Path = PROJECT_ROOT / "data"
LOGS_DIR: Path = PROJECT_ROOT / "logs"
ASSETS_DIR: Path = PROJECT_ROOT / "assets"
WEIGHTS_DIR: Path = PROJECT_ROOT / "weights"

# ============ DHT22 温湿度传感器 ============
# adafruit_dht.DHT22(board.D17, use_pulseio=False)
DHT22_PIN: int = 17           # BCM GPIO17 (Pin 11)
DHT22_INTERVAL: float = 6.0   # 采样间隔 6 秒（DHT22 最小 2 秒，留余量）

# ============ BH1750 光照传感器 ============
# smbus2.SMBus(1) → I2C-1 (Pin 3 SDA / Pin 5 SCL)
BH1750_BUS: int = 1           # I2C 总线号
BH1750_ADDR: int = 0x23       # I2C 地址（ADDR 接 GND）
BH1750_MODE: int = 0x10       # 连续高分辨率模式 1 lx
BH1750_INTERVAL: float = 2.0  # 采样间隔 2 秒

# ============ 红外收发 ============
# lgpio chip 0
IR_RECV_PIN: int = 4          # BCM GPIO4  (Pin 7)  红外接收模块 OUT
IR_SEND_PIN: int = 18         # BCM GPIO18 (Pin 12) 红外发射模块 DAT

# ============ 舵机（灯光开关） ============
# gpiozero.AngularServo + LGPIOFactory
SERVO_PIN: int = 23           # BCM GPIO23 (Pin 16) 舵机信号线
SERVO_MIN_ANGLE: int = 0
SERVO_MAX_ANGLE: int = 180
SERVO_MIN_PULSE: float = 0.0005   # 0.5 ms
SERVO_MAX_PULSE: float = 0.0025   # 2.5 ms

# ============ 摄像头 & YOLO 人员检测 ============
CAMERA_SOURCE: int = 0            # 摄像头设备号（0 = 默认）
CAMERA_WIDTH: int = 640
CAMERA_HEIGHT: int = 480
CAMERA_TARGET_FPS: int = 30
DETECTION_INTERVAL: float = 2.0   # YOLO 推理间隔（秒）
YOLO_MODEL: str = "yolov8n.pt"    # 默认模型（相对于 WEIGHTS_DIR）
YOLO_CONFIDENCE: float = 0.5      # 检测置信度阈值
PERSON_CLASS_ID: int = 0          # COCO person class
STREAM_JPEG_QUALITY: int = 70     # 推流 JPEG 压缩质量
