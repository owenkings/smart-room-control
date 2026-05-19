"""
舵机控制模块 — 基于 gpiozero.AngularServo + LGPIOFactory

使用 SG90 舵机通过 GPIO23 控制灯光开关。
校准数据使用偏移量模式（neutral_angle + on_offset/off_offset），
从 UserSettings (data/user_settings.json) 加载。

动作序列: neutral → clamp(neutral + offset, 0, 180) → pause 1.5s → neutral

参考: tests/test_servo.py (已验证可用)
"""

import logging
import time

from gpiozero import AngularServo, Device
from gpiozero.pins.lgpio import LGPIOFactory

import config
from src import user_settings

logger = logging.getLogger(__name__)

# 固定停顿时间（秒），硬编码不可配置
_PRESS_PAUSE = 1.5


class ServoController:
    """基于 gpiozero.AngularServo + LGPIOFactory 的舵机控制器。

    使用偏移量模式计算目标角度:
      开灯目标 = clamp(neutral_angle + on_offset, 0, 180)
      关灯目标 = clamp(neutral_angle + off_offset, 0, 180)

    执行流程: neutral → target → pause 1.5s → neutral
    """

    def __init__(
        self,
        pin: int = config.SERVO_PIN,
    ):
        """初始化舵机硬件并从 UserSettings 加载校准数据。

        Args:
            pin: BCM GPIO 引脚号，默认从 config.SERVO_PIN 读取。
        """
        # 设置 lgpio 引脚工厂（Pi 5 必须）
        Device.pin_factory = LGPIOFactory()

        self._servo = AngularServo(
            pin,
            min_angle=config.SERVO_MIN_ANGLE,
            max_angle=config.SERVO_MAX_ANGLE,
            min_pulse_width=config.SERVO_MIN_PULSE,
            max_pulse_width=config.SERVO_MAX_PULSE,
        )

        self._calibration: dict = self.load_calibration()
        self._current_angle: int | None = None

        logger.info(
            "ServoController 初始化完成 — GPIO%d, 校准: %s",
            pin,
            self._calibration,
        )

    # ------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------

    def move_to(self, angle: int) -> None:
        """移动舵机到指定角度，自动钳位到 [0, 180]。

        Args:
            angle: 目标角度（任意整数值，会被钳位到 [0, 180]）。
        """
        angle = max(config.SERVO_MIN_ANGLE, min(config.SERVO_MAX_ANGLE, angle))
        self._servo.angle = angle
        self._current_angle = angle
        logger.debug("舵机移动到 %d°", angle)

    def press_on(self) -> None:
        """执行"开灯"动作序列。

        序列: neutral → clamp(neutral + on_offset, 0, 180) → pause 1.5s → neutral
        """
        neutral = self._calibration["neutral_angle"]
        on_offset = self._calibration["on_offset"]
        target = max(0, min(180, neutral + on_offset))

        self.move_to(neutral)
        self.move_to(target)
        time.sleep(_PRESS_PAUSE)
        self.move_to(neutral)
        logger.info(
            "press_on 完成 (neutral=%d → target=%d → pause %.1fs → neutral=%d)",
            neutral, target, _PRESS_PAUSE, neutral,
        )

    def press_off(self) -> None:
        """执行"关灯"动作序列。

        序列: neutral → clamp(neutral + off_offset, 0, 180) → pause 1.5s → neutral
        """
        neutral = self._calibration["neutral_angle"]
        off_offset = self._calibration["off_offset"]
        target = max(0, min(180, neutral + off_offset))

        self.move_to(neutral)
        self.move_to(target)
        time.sleep(_PRESS_PAUSE)
        self.move_to(neutral)
        logger.info(
            "press_off 完成 (neutral=%d → target=%d → pause %.1fs → neutral=%d)",
            neutral, target, _PRESS_PAUSE, neutral,
        )

    def set_neutral(self, angle: int) -> None:
        """设置中位角度并立即移动到该位置（视觉确认）。

        Args:
            angle: 新的中位角度 [0, 180]。
        """
        angle = max(0, min(180, angle))
        self._calibration["neutral_angle"] = angle
        self.move_to(angle)
        self.save_calibration()
        logger.info("中位角度已设置为 %d° 并移动到位", angle)

    def set_on_offset(self, offset: int) -> None:
        """设置开灯偏移并执行测试动作（neutral → target → neutral）。

        Args:
            offset: 开灯偏移量（度），通常为负值。
        """
        self._calibration["on_offset"] = offset
        # 执行测试动作以供视觉确认
        neutral = self._calibration["neutral_angle"]
        target = max(0, min(180, neutral + offset))
        self.move_to(neutral)
        self.move_to(target)
        time.sleep(_PRESS_PAUSE)
        self.move_to(neutral)
        self.save_calibration()
        logger.info("开灯偏移已设置为 %d°，测试动作完成", offset)

    def set_off_offset(self, offset: int) -> None:
        """设置关灯偏移并执行测试动作（neutral → target → neutral）。

        Args:
            offset: 关灯偏移量（度），通常为正值。
        """
        self._calibration["off_offset"] = offset
        # 执行测试动作以供视觉确认
        neutral = self._calibration["neutral_angle"]
        target = max(0, min(180, neutral + offset))
        self.move_to(neutral)
        self.move_to(target)
        time.sleep(_PRESS_PAUSE)
        self.move_to(neutral)
        self.save_calibration()
        logger.info("关灯偏移已设置为 %d°，测试动作完成", offset)

    def get_calibration(self) -> dict:
        """返回当前校准数据。

        Returns:
            包含 neutral_angle, on_offset, off_offset 的字典。
        """
        return dict(self._calibration)

    def save_calibration(self) -> None:
        """将当前校准数据保存到 UserSettings。"""
        user_settings.set("servo_calibration", self._calibration)
        logger.info("校准数据已保存到 UserSettings")

    def load_calibration(self) -> dict:
        """从 UserSettings 加载校准数据；不存在则使用默认值。

        Returns:
            包含 neutral_angle, on_offset, off_offset 的字典。
        """
        calibration = user_settings.get("servo_calibration")
        if calibration and isinstance(calibration, dict):
            # 确保所有必需键都存在
            defaults = {"neutral_angle": 90, "on_offset": -30, "off_offset": 30}
            for key, default_val in defaults.items():
                calibration.setdefault(key, default_val)
            logger.info("已从 UserSettings 加载校准数据: %s", calibration)
            return calibration
        # 使用默认值
        default_calibration = {"neutral_angle": 90, "on_offset": -30, "off_offset": 30}
        logger.info("使用默认校准数据: %s", default_calibration)
        return default_calibration

    def get_status(self) -> dict:
        """返回当前舵机状态和校准信息。

        Returns:
            包含 current_angle 和校准参数的字典。
        """
        return {
            "current_angle": self._current_angle,
            **self._calibration,
        }

    def cleanup(self) -> None:
        """释放 GPIO 资源。"""
        try:
            self._servo.detach()
        except Exception as e:
            logger.warning("舵机 detach 异常: %s", e)
        logger.info("ServoController 资源已释放")
