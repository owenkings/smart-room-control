"""
BH1750 光照传感器模块

通过 I2C 总线读取 BH1750 数字光照传感器，返回 lux 值。
后台线程按 BH1750_INTERVAL 周期轮询，通信失败时记录警告并返回上次有效值。

参考: tests/test_bh1750.py (已验证可用)
硬件: I2C-1, 地址 0x23, 连续高分辨率模式 0x10
"""

import time
import threading
import logging

import config
from src import user_settings

logger = logging.getLogger(__name__)

# 默认光照不足阈值 (lux)，低于此值认为需要开灯
_DEFAULT_DARK_THRESHOLD: float = 150.0


class LightSensor:
    """BH1750 光照传感器，I2C 通信，后台线程轮询。"""

    def __init__(
        self,
        bus: int = config.BH1750_BUS,
        address: int = config.BH1750_ADDR,
        mode: int = config.BH1750_MODE,
        interval: float = config.BH1750_INTERVAL,
    ):
        self._bus_number = bus
        self._address = address
        self._mode = mode
        self._interval = interval

        self._lux: float = 0.0
        self._dark_threshold: float = self._load_threshold()
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._smbus = None

    # ------------------------------------------------------------------
    # 阈值管理
    # ------------------------------------------------------------------

    def _load_threshold(self) -> float:
        """从 UserSettings 加载 dark_threshold，缺失或无效时回退默认值。"""
        try:
            value = user_settings.get("dark_threshold")
            if value is None:
                return _DEFAULT_DARK_THRESHOLD
            threshold = float(value)
            if threshold <= 0:
                logger.warning(
                    "dark_threshold 值无效 (%.2f)，使用默认值 %.1f lux",
                    threshold,
                    _DEFAULT_DARK_THRESHOLD,
                )
                return _DEFAULT_DARK_THRESHOLD
            return threshold
        except (TypeError, ValueError) as e:
            logger.warning(
                "加载 dark_threshold 失败: %s，使用默认值 %.1f lux",
                e,
                _DEFAULT_DARK_THRESHOLD,
            )
            return _DEFAULT_DARK_THRESHOLD

    def set_threshold(self, value: float) -> None:
        """运行时修改光照不足阈值。

        Args:
            value: 新的阈值 (lux)，必须为正数。

        Raises:
            ValueError: 如果 value 不是正数。
        """
        threshold = float(value)
        if threshold <= 0:
            raise ValueError(f"dark_threshold 必须为正数，收到: {value}")
        with self._lock:
            self._dark_threshold = threshold
        logger.info("光照阈值已更新为 %.1f lux", threshold)

    @property
    def dark_threshold(self) -> float:
        """当前光照不足阈值 (lux)。"""
        with self._lock:
            return self._dark_threshold

    # ------------------------------------------------------------------
    # 静态转换方法
    # ------------------------------------------------------------------

    @staticmethod
    def raw_to_lux(high_byte: int, low_byte: int) -> float:
        """将 BH1750 原始 2 字节数据转换为 lux 值。

        公式: (high_byte << 8 | low_byte) / 1.2
        """
        raw = (high_byte << 8) | low_byte
        return raw / 1.2

    # ------------------------------------------------------------------
    # 公共读取接口
    # ------------------------------------------------------------------

    def read_lux(self) -> float:
        """返回最近一次成功读取的光照值 (lux)。"""
        with self._lock:
            return self._lux

    def is_dark(self) -> bool:
        """判断当前光照是否不足（低于 dark_threshold）。"""
        with self._lock:
            return self._lux < self._dark_threshold

    def get_status(self) -> dict:
        """返回当前光照状态字典。"""
        with self._lock:
            return {
                "lux": round(self._lux, 1),
                "is_dark": self._lux < self._dark_threshold,
                "dark_threshold": self._dark_threshold,
            }

    # ------------------------------------------------------------------
    # 后台线程控制
    # ------------------------------------------------------------------

    def start(self) -> None:
        """启动后台轮询线程。"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("BH1750 光照传感器后台线程已启动")

    def stop(self) -> None:
        """停止后台轮询线程并关闭 I2C 总线。"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=self._interval + 1)
        self._close_bus()
        logger.info("BH1750 光照传感器已停止")

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------

    def _open_bus(self) -> None:
        """延迟打开 I2C 总线（在线程内调用，避免跨线程问题）。"""
        if self._smbus is None:
            try:
                import smbus2
                self._smbus = smbus2.SMBus(self._bus_number)
                logger.info(
                    f"I2C 总线 {self._bus_number} 已打开, "
                    f"BH1750 地址 0x{self._address:02X}"
                )
            except (OSError, ImportError) as e:
                logger.warning(f"无法打开 I2C 总线: {e}")
                self._smbus = None

    def _close_bus(self) -> None:
        """关闭 I2C 总线。"""
        if self._smbus is not None:
            try:
                self._smbus.close()
            except Exception:
                pass
            self._smbus = None

    def _read_sensor(self) -> None:
        """执行一次 I2C 读取并更新 lux 值。

        通信失败时记录警告，保留上次有效值。
        """
        if self._smbus is None:
            self._open_bus()
            if self._smbus is None:
                return

        try:
            data = self._smbus.read_i2c_block_data(
                self._address, self._mode, 2
            )
            lux = self.raw_to_lux(data[0], data[1])
            with self._lock:
                self._lux = lux
        except OSError as e:
            logger.warning(f"BH1750 读取失败: {e}, 保留上次值 {self._lux:.1f} lux")

    def _poll_loop(self) -> None:
        """后台轮询循环。"""
        self._open_bus()
        while self._running:
            self._read_sensor()
            time.sleep(self._interval)
