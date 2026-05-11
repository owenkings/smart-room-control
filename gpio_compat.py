"""
GPIO 兼容层
树莓派5 使用新的 RP1 芯片，RPi.GPIO 有已知兼容问题。
优先尝试 rpi-lgpio（官方推荐的 Pi5 兼容层），失败再尝试 RPi.GPIO。

使用方式（替代直接 import RPi.GPIO）:
    from gpio_compat import GPIO, HAS_GPIO
"""

import logging
import config

logger = logging.getLogger(__name__)

GPIO = None
HAS_GPIO = False

if not config.SIMULATE_GPIO:
    # 优先尝试 rpi-lgpio（树莓派5推荐）
    try:
        import RPi.GPIO as GPIO
        HAS_GPIO = True
        logger.debug("GPIO 后端: RPi.GPIO (via rpi-lgpio 或原生)")
    except (ImportError, RuntimeError) as e:
        logger.warning(f"RPi.GPIO 不可用: {e}")
        logger.warning("请安装: pip install rpi-lgpio")
        GPIO = None
        HAS_GPIO = False
