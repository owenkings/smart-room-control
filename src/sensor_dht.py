"""
DHT22 温湿度传感器模块

基于已验证的 test_dht11.py 脚本重写，使用 adafruit_dht 库。
每次读取后调用 dht.exit() 释放内核资源，后台线程捕获所有
RuntimeError 保证永不崩溃。
"""

import logging
import threading
import time
from typing import Optional

import adafruit_dht
import board

from config import DHT22_PIN, DHT22_INTERVAL

logger = logging.getLogger(__name__)

# 映射 BCM 引脚号到 board 对象
_BOARD_PINS = {
    4: board.D4,
    17: board.D17,
    18: board.D18,
    22: board.D22,
    23: board.D23,
    24: board.D24,
    25: board.D25,
    27: board.D27,
}


class TemperatureSensor:
    """DHT22 温湿度传感器，adafruit_dht 库"""

    def __init__(self, pin: int = DHT22_PIN, interval: float = DHT22_INTERVAL):
        """初始化传感器

        Args:
            pin: BCM GPIO 引脚号，默认 17
            interval: 采样间隔（秒），默认 6.0
        """
        self._pin = pin
        self._board_pin = _BOARD_PINS.get(pin, board.D17)
        self._interval = interval

        # 最近一次有效读数
        self._temperature: Optional[float] = None
        self._humidity: Optional[float] = None
        self._last_read_time: Optional[float] = None
        self._read_error: Optional[str] = None

        # 线程控制
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def read_once(self) -> tuple:
        """单次读取温湿度

        创建 DHT22 实例，读取后立即调用 dht.exit() 释放资源。

        Returns:
            (temperature, humidity) 元组，失败时返回 (None, None)
        """
        dht = adafruit_dht.DHT22(self._board_pin, use_pulseio=False)
        temp = None
        hum = None
        try:
            temp = dht.temperature
            hum = dht.humidity
        except RuntimeError as e:
            logger.warning("DHT22 读取失败: %s", e)
        except OverflowError as e:
            logger.warning("DHT22 读取溢出: %s", e)
        except Exception as e:
            logger.error("DHT22 未知错误: %s", e)
        finally:
            dht.exit()

        return (temp, hum)

    def _worker(self) -> None:
        """后台采样线程主循环

        捕获所有 RuntimeError，永不崩溃。成功读取时更新缓存值，
        失败时保留上次有效读数。
        """
        while self._running:
            temp, hum = self.read_once()

            with self._lock:
                if temp is not None and hum is not None:
                    self._temperature = temp
                    self._humidity = hum
                    self._last_read_time = time.time()
                    self._read_error = None
                    logger.debug(
                        "DHT22: 温度=%.1f°C 湿度=%.1f%%", temp, hum
                    )
                else:
                    self._read_error = "读取失败，保留上次有效值"
                    logger.debug("DHT22: 读取失败，保留上次有效值")

            time.sleep(self._interval)

    def start(self) -> None:
        """启动后台采样线程"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._worker, name="DHT22-Worker", daemon=True
        )
        self._thread.start()
        logger.info("DHT22 后台采样已启动 (间隔 %.1fs)", self._interval)

    def stop(self) -> None:
        """停止后台采样线程"""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=self._interval + 2)
            self._thread = None
        logger.info("DHT22 后台采样已停止")

    def get_status(self) -> dict:
        """返回最新温湿度数据

        即使最近一次读取失败，仍返回上次成功的有效值。

        Returns:
            dict: {
                "temperature": float | None,
                "humidity": float | None,
                "last_read_time": float | None,
                "error": str | None,
                "running": bool
            }
        """
        with self._lock:
            return {
                "temperature": self._temperature,
                "humidity": self._humidity,
                "last_read_time": self._last_read_time,
                "error": self._read_error,
                "running": self._running,
            }
