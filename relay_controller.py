"""
继电器控制模块(精简版) - 仅用于电源通断控制
灯光改用舵机按压开关，空调改用红外遥控
"""

import logging
import config
from gpio_compat import GPIO, HAS_GPIO

logger = logging.getLogger(__name__)


class RelayController:
    """继电器控制器 - 电源通断"""

    def __init__(self):
        self.is_on = False
        self.gpio_available = HAS_GPIO

        if self.gpio_available:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)
                GPIO.setup(config.RELAY_PIN_POWER, GPIO.OUT)
                self._write(False)
                logger.info("电源继电器初始化完成")
            except Exception as e:
                self.gpio_available = False
                logger.warning(f"电源继电器GPIO初始化失败，切换到模拟模式: {e}")
        else:
            logger.info("电源继电器模拟模式已启动")

    def _write(self, on):
        if self.gpio_available:
            if config.RELAY_ACTIVE_LOW:
                GPIO.output(config.RELAY_PIN_POWER, GPIO.LOW if on else GPIO.HIGH)
            else:
                GPIO.output(config.RELAY_PIN_POWER, GPIO.HIGH if on else GPIO.LOW)

    def turn_on(self):
        if self.is_on:
            return
        self._write(True)
        self.is_on = True
        logger.info("[继电器] 电源 -> 开启")

    def turn_off(self):
        if not self.is_on:
            return
        self._write(False)
        self.is_on = False
        logger.info("[继电器] 电源 -> 关闭")

    def set(self, on):
        if on:
            self.turn_on()
        else:
            self.turn_off()

    def get_state(self):
        return self.is_on

    def cleanup(self):
        self.gpio_available = False
