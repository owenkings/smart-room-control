"""
舵机开关模块 - 用机械臂物理按压墙壁灯开关
非侵入式改造，不改动教室原有电路

硬件连接:
  舵机信号线 -> GPIO18 (支持硬件PWM)
  舵机电源   -> 5V
  舵机地线   -> GND

安装方式:
  用支架将舵机固定在墙壁开关旁，推杆对准开关按钮
"""

import time
import logging
import config
from gpio_compat import GPIO, HAS_GPIO
import user_settings

logger = logging.getLogger(__name__)


class ServoSwitch:
    """舵机灯光开关控制器"""

    def __init__(self):
        self.is_on = False
        self.pwm = None
        self.gpio_available = HAS_GPIO
        self.current_angle = self._clamp_angle(config.SERVO_ANGLE_NEUTRAL)
        self.angle_on = self._clamp_angle(config.SERVO_ANGLE_ON)
        self.angle_off = self._clamp_angle(config.SERVO_ANGLE_OFF)
        self.angle_neutral = self._clamp_angle(config.SERVO_ANGLE_NEUTRAL)
        self.action_duration = max(0.1, float(config.SERVO_ACTION_DURATION))
        self._load_settings()

        if self.gpio_available:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(config.SERVO_PIN_LIGHT, GPIO.OUT)
                self.pwm = GPIO.PWM(config.SERVO_PIN_LIGHT, config.SERVO_PWM_FREQ)
                self.pwm.start(0)
                # 归位到中立位置
                self._set_angle(self.angle_neutral)
                logger.info("舵机灯光开关初始化完成")
            except Exception as e:
                self.gpio_available = False
                self.pwm = None
                logger.warning(f"舵机GPIO初始化失败，切换到模拟模式: {e}")

        if not self.gpio_available:
            logger.info("舵机开关模拟模式已启动")

    def _clamp_angle(self, angle):
        """SG90 为 0-180 度，统一限制录制/控制范围。"""
        return max(0, min(180, int(round(float(angle)))))

    def _load_settings(self):
        settings = user_settings.load()
        self.angle_on = self._clamp_angle(settings.get("servo_angle_on", self.angle_on))
        self.angle_off = self._clamp_angle(settings.get("servo_angle_off", self.angle_off))
        self.angle_neutral = self._clamp_angle(settings.get("servo_angle_neutral", self.angle_neutral))
        self.action_duration = max(
            0.1,
            float(settings.get("servo_action_duration", self.action_duration))
        )
        self.current_angle = self.angle_neutral

    def _angle_to_duty(self, angle):
        """角度(0-180)转换为占空比(2.5-12.5%)"""
        return 2.5 + (angle / 180.0) * 10.0

    def _set_angle(self, angle):
        """设置舵机角度"""
        angle = self._clamp_angle(angle)
        self.current_angle = angle
        if self.pwm:
            duty = self._angle_to_duty(angle)
            self.pwm.ChangeDutyCycle(duty)
            time.sleep(0.3)
            self.pwm.ChangeDutyCycle(0)  # 停止信号，防止抖动

    def _press_switch(self, angle):
        """按压开关动作: 中立 -> 目标角度 -> 保持 -> 回到中立。"""
        angle = self._clamp_angle(angle)
        if self.gpio_available:
            if self.current_angle != self.angle_neutral:
                self._set_angle(self.angle_neutral)
                time.sleep(0.15)
            self._set_angle(angle)
            time.sleep(self.action_duration)
            self._set_angle(self.angle_neutral)
        else:
            self.current_angle = self.angle_neutral
        logger.debug(
            f"舵机按压动作: 中立{self.angle_neutral}° -> 目标{angle}° -> 中立{self.angle_neutral}°"
        )

    def move_to(self, angle):
        """标定模式: 直接移动到指定角度，不执行开关动作。"""
        angle = self._clamp_angle(angle)
        if self.gpio_available:
            self._set_angle(angle)
        else:
            self.current_angle = angle
        logger.info(f"[舵机标定] 直接移动到 {angle}°")
        return angle

    def move_by(self, delta):
        return self.move_to(self.current_angle + delta)

    def move_to_neutral(self):
        return self.move_to(self.angle_neutral)

    def save_calibration(self, *, angle_on=None, angle_off=None, angle_neutral=None, action_duration=None):
        if angle_on is not None:
            self.angle_on = self._clamp_angle(angle_on)
        if angle_off is not None:
            self.angle_off = self._clamp_angle(angle_off)
        if angle_neutral is not None:
            self.angle_neutral = self._clamp_angle(angle_neutral)
        if action_duration is not None:
            self.action_duration = max(0.1, float(action_duration))

        user_settings.save({
            "servo_angle_on": self.angle_on,
            "servo_angle_off": self.angle_off,
            "servo_angle_neutral": self.angle_neutral,
            "servo_action_duration": round(self.action_duration, 2),
        })
        logger.info(
            f"[舵机标定] 已保存 开={self.angle_on}° 关={self.angle_off}° "
            f"中立={self.angle_neutral}° 保持={self.action_duration:.2f}s"
        )
        return self.get_calibration_status()

    def save_preset(self, preset, angle=None):
        angle = self.current_angle if angle is None else angle
        if preset == "on":
            return self.save_calibration(angle_on=angle)
        if preset == "off":
            return self.save_calibration(angle_off=angle)
        if preset == "neutral":
            result = self.save_calibration(angle_neutral=angle)
            self.move_to_neutral()
            return result
        raise ValueError(f"未知舵机预设: {preset}")

    def get_calibration_status(self):
        return {
            "current_angle": self.current_angle,
            "angle_on": self.angle_on,
            "angle_off": self.angle_off,
            "angle_neutral": self.angle_neutral,
            "action_duration": round(self.action_duration, 2),
            "min_angle": 0,
            "max_angle": 180,
            "has_gpio": self.gpio_available,
        }

    def turn_on(self, force=False):
        """开灯"""
        if self.is_on and not force:
            return
        self._press_switch(self.angle_on)
        self.is_on = True
        logger.info("[舵机] 灯光 -> 开启")

    def turn_off(self, force=False):
        """关灯"""
        if not self.is_on and not force:
            return
        self._press_switch(self.angle_off)
        self.is_on = False
        logger.info("[舵机] 灯光 -> 关闭")

    def set(self, on, force=False):
        if on:
            self.turn_on(force=force)
        else:
            self.turn_off(force=force)

    def get_state(self):
        return self.is_on

    def cleanup(self):
        if self.pwm:
            try:
                self.pwm.stop()
            except Exception as e:
                logger.debug(f"舵机PWM停止时忽略异常: {e}")
            finally:
                self.pwm = None
