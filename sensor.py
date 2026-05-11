"""
温度传感器模块
支持DHT22传感器和模拟模式
"""

import time
import random
import threading
import logging
import config

logger = logging.getLogger(__name__)

# 尝试导入DHT库
try:
    if not config.SIMULATE_GPIO and config.ENABLE_DHT22:
        import adafruit_dht
        import board
        HAS_DHT = True
    else:
        HAS_DHT = False
except (ImportError, RuntimeError, NotImplementedError) as e:
    HAS_DHT = False
    if not config.SIMULATE_GPIO:
        logger.warning(f"adafruit_dht 不可用: {e}，切换到模拟模式。"
                       "请运行: pip install adafruit-circuitpython-dht && sudo apt install libgpiod2")

if not config.ENABLE_DHT22:
    logger.info("DHT22已在配置中禁用，温湿度将使用模拟数据")


class TemperatureSensor:
    """温度传感器读取器"""

    def __init__(self):
        self.temperature = 25.0
        self.humidity = 50.0
        self.running = False
        self.lock = threading.Lock()
        self.dht_device = None

        if HAS_DHT:
            pin = getattr(board, f"D{config.TEMP_SENSOR_PIN}")
            self.dht_device = adafruit_dht.DHT22(pin)
            logger.info("DHT22传感器初始化完成")
        else:
            logger.info("温度传感器模拟模式已启动")

    def _read_real(self):
        """从真实传感器读取"""
        try:
            self.temperature = self.dht_device.temperature
            self.humidity = self.dht_device.humidity
        except RuntimeError as e:
            logger.warning(f"传感器读取失败: {e}")

    def _read_simulated(self):
        """模拟温度数据(在25°C附近波动)"""
        with self.lock:
            self.temperature += random.uniform(-0.5, 0.5)
            self.temperature = max(15.0, min(35.0, self.temperature))
            self.humidity += random.uniform(-1, 1)
            self.humidity = max(30.0, min(80.0, self.humidity))

    def read_loop(self):
        """持续读取循环"""
        self.running = True
        while self.running:
            if HAS_DHT:
                self._read_real()
            else:
                self._read_simulated()
            time.sleep(config.TEMP_READ_INTERVAL)

    def start(self):
        """启动读取线程"""
        thread = threading.Thread(target=self.read_loop, daemon=True)
        thread.start()
        logger.info("温度传感器读取线程已启动")
        return thread

    def stop(self):
        self.running = False

    def get_status(self):
        with self.lock:
            return {
                "temperature": round(self.temperature, 1),
                "humidity": round(self.humidity, 1)
            }
