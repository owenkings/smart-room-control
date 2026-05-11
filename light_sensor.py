"""
光照传感器模块 - 两种方案
  1. BH1750 (I2C, 高精度, 用于决策)
  2. 光敏电阻模块 (数字IO, 快速响应, 用于灯光状态反馈)

用途:
  决策: 环境亮度不足才开灯(节能)
  反馈: 判断灯光实际是否开启(舵机按压后是否真的亮了)
"""

import time
import random
import threading
import logging
import config
from gpio_compat import GPIO, HAS_GPIO

logger = logging.getLogger(__name__)

# BH1750库
try:
    if not config.SIMULATE_GPIO and config.ENABLE_BH1750:
        import smbus2
        HAS_BH1750 = True
    else:
        HAS_BH1750 = False
except ImportError:
    HAS_BH1750 = False


class LightSensor:
    """光照传感器 - 决策用(BH1750或模拟)"""

    BH1750_ADDR = 0x23
    ONE_TIME_HIGH_RES_MODE = 0x20

    def __init__(self):
        self.lux = 300.0  # 环境亮度(lux), 300lux约等于办公室正常照明
        self.running = False
        self._thread = None
        self.lock = threading.Lock()
        self.bus = None
        self.photo_available = False

        if HAS_BH1750:
            try:
                self.bus = smbus2.SMBus(1)
                logger.info("BH1750光照传感器初始化完成")
            except Exception as e:
                logger.warning(f"BH1750初始化失败: {e}, 切换到模拟模式")
                self.bus = None
        elif HAS_GPIO:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(config.LIGHT_FEEDBACK_PIN, GPIO.IN)
                self.photo_available = True
                logger.info(f"环境光改用光敏电阻数字量(GPIO{config.LIGHT_FEEDBACK_PIN})")
            except Exception as e:
                logger.warning(f"光敏电阻环境光初始化失败: {e}, 切换到模拟模式")
        else:
            logger.info("光照传感器模拟模式")

    def _read_real(self):
        try:
            data = self.bus.read_i2c_block_data(
                self.BH1750_ADDR, self.ONE_TIME_HIGH_RES_MODE, 2
            )
            raw = (data[0] << 8) | data[1]
            lux = raw / 1.2
            with self.lock:
                self.lux = lux
        except Exception as e:
            logger.debug(f"BH1750读取失败: {e}")

    def _read_simulated(self):
        # 模拟教室亮度波动(200-500lux)
        with self.lock:
            self.lux += random.uniform(-20, 20)
            self.lux = max(50.0, min(800.0, self.lux))

    def _read_photo_digital(self):
        """光敏电阻数字量转换为粗略lux，仅用于开灯决策"""
        try:
            raw = GPIO.input(config.LIGHT_FEEDBACK_PIN)
            is_bright = (raw == GPIO.LOW) if config.LIGHT_FEEDBACK_ACTIVE_LOW else (raw == GPIO.HIGH)
            with self.lock:
                # 数字量无法给出真实lux，这里仅映射到两个典型区间
                self.lux = 500.0 if is_bright else 80.0
        except Exception as e:
            self.photo_available = False
            logger.debug(f"环境光数字量读取失败，切换到模拟模式: {e}")

    def read_loop(self):
        self.running = True
        while self.running:
            if self.bus:
                self._read_real()
            elif self.photo_available:
                self._read_photo_digital()
            else:
                self._read_simulated()
            time.sleep(config.LIGHT_READ_INTERVAL)

    def start(self):
        self._thread = threading.Thread(target=self.read_loop, daemon=True)
        self._thread.start()
        logger.info("光照传感器读取线程已启动")
        return self._thread

    def stop(self, join_timeout=2.0):
        self.running = False
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=join_timeout)

    def is_dark(self):
        """是否光照不足，需要开灯"""
        with self.lock:
            return self.lux < config.LIGHT_DARK_THRESHOLD

    def is_bright(self):
        """是否光照充足"""
        with self.lock:
            return self.lux > config.LIGHT_BRIGHT_THRESHOLD

    def get_status(self):
        with self.lock:
            return {
                "lux": round(self.lux, 1),
                "is_dark": self.lux < config.LIGHT_DARK_THRESHOLD,
                "is_bright": self.lux > config.LIGHT_BRIGHT_THRESHOLD,
            }


class LightFeedbackSensor:
    """光敏电阻模块 - 灯光实际状态反馈
    只读数字引脚(亮/暗)，速度快，用于判断灯是否真的被打开
    """

    def __init__(self):
        self.is_bright = False
        self.gpio_available = HAS_GPIO

        if self.gpio_available:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(config.LIGHT_FEEDBACK_PIN, GPIO.IN)
                logger.info("光敏电阻反馈传感器初始化完成")
            except Exception as e:
                self.gpio_available = False
                logger.warning(f"光敏反馈传感器初始化失败，切换到缓存模式: {e}")
        else:
            logger.info("光敏反馈传感器模拟模式")

    def read(self):
        """读取当前是否亮(True=亮)"""
        if self.gpio_available:
            try:
                # 光敏电阻模块通常是: 亮=LOW, 暗=HIGH (具体看模块, 可通过config调整)
                raw = GPIO.input(config.LIGHT_FEEDBACK_PIN)
                self.is_bright = (raw == GPIO.LOW) if config.LIGHT_FEEDBACK_ACTIVE_LOW else (raw == GPIO.HIGH)
            except Exception as e:
                self.gpio_available = False
                logger.debug(f"光敏反馈读取失败，返回最后缓存值: {e}")
        return self.is_bright

    def read_stable(self, samples=5, interval=0.1):
        """多次采样后取多数票，减少灯刚切换时的抖动误判。"""
        bright_count = 0
        for _ in range(max(1, samples)):
            if self.read():
                bright_count += 1
            time.sleep(interval)
        return bright_count >= (samples // 2 + 1)

    def get_status(self):
        return {"actual_light_on": self.read()}

    def cleanup(self):
        self.gpio_available = False
