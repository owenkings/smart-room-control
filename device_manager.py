"""
设备管理器 - 统一管理所有执行器
  灯光: 舵机按压开关 + 光敏电阻反馈闭环
  空调: 红外发射模拟遥控器
  电源: 继电器控制
"""

import time
import logging
import threading
from servo_switch import ServoSwitch
from ir_controller import IRController
from relay_controller import RelayController
from light_sensor import LightFeedbackSensor
import config

logger = logging.getLogger(__name__)


class DeviceManager:
    """统一设备管理器"""

    def __init__(self):
        self.servo = ServoSwitch()
        self.ir = IRController()
        self.relay = RelayController()
        self._device_lock = threading.RLock()

        # 灯光反馈传感器(闭环控制)
        if config.LIGHT_FEEDBACK_ENABLED:
            self.light_feedback = LightFeedbackSensor()
        else:
            self.light_feedback = None

        self.state = {"light": False, "ac": False, "power": False}
        self.ac_mode = "off"
        logger.info("设备管理器初始化完成")

    def set_light(self, on, force=False):
        """控制灯光 - 带反馈闭环
        舵机按压后读取光敏电阻确认灯是否真的开/关，不符则重试
        """
        with self._device_lock:
            previous_state = self.state["light"]
            if not force and previous_state == on:
                return True

            for attempt in range(config.LIGHT_RETRY_MAX + 1):
                retry_force = force or attempt > 0
                self.servo.set(on, force=retry_force)

                # 若启用反馈，等待光敏判断
                if self.light_feedback:
                    time.sleep(0.5)  # 等灯稳定
                    actual = self.light_feedback.read_stable(samples=5, interval=0.12)
                    self.state["light"] = actual
                    if actual == on:
                        logger.info(f"[闭环] 灯光状态已确认: {'开' if on else '关'}")
                        return True
                    else:
                        logger.warning(
                            f"[闭环] 灯光状态不符(期望={'开' if on else '关'}, "
                            f"实际={'开' if actual else '关'}), "
                            f"重试 {attempt + 1}/{config.LIGHT_RETRY_MAX}"
                        )
                else:
                    self.state["light"] = on
                    return True

            if self.light_feedback:
                self.state["light"] = self.light_feedback.read_stable(samples=5, interval=0.08)
            else:
                self.state["light"] = previous_state
            logger.error("[闭环] 灯光控制失败，已达最大重试次数")
            return False

    def set_ac(self, on, mode="cooling"):
        with self._device_lock:
            if on and self.ac_mode == mode:
                return
            if not on and not self.state["ac"]:
                return
            self.ir.set_ac(on, mode)
            self.state["ac"] = on
            self.ac_mode = mode if on else "off"

    def set_power(self, on):
        with self._device_lock:
            if self.state["power"] == on:
                return
            self.relay.set(on)
            self.state["power"] = on

    def set(self, device, on, **kwargs):
        if device == "light":
            self.set_light(on, kwargs.get("force", False))
        elif device == "ac":
            self.set_ac(on, kwargs.get("mode", "cooling"))
        elif device == "power":
            self.set_power(on)
        else:
            logger.error(f"未知设备: {device}")

    def move_servo_to(self, angle):
        return self.servo.move_to(angle)

    def nudge_servo(self, delta):
        return self.servo.move_by(delta)

    def save_servo_preset(self, preset, angle=None):
        return self.servo.save_preset(preset, angle)

    def save_servo_config(self, angle_on=None, angle_off=None, angle_neutral=None, action_duration=None):
        return self.servo.save_calibration(
            angle_on=angle_on,
            angle_off=angle_off,
            angle_neutral=angle_neutral,
            action_duration=action_duration,
        )

    def get_servo_status(self):
        return self.servo.get_calibration_status()

    def all_off(self):
        self.set_light(False)
        self.set_ac(False)
        self.set_power(False)

    def get_status(self):
        with self._device_lock:
            status = {
                "light": self.state["light"],
                "ac": self.state["ac"],
                "power": self.state["power"],
                "ac_mode": self.ac_mode,
                "servo_calibration": self.servo.get_calibration_status(),
            }
            if self.light_feedback:
                try:
                    status["light_actual"] = self.light_feedback.read()
                except Exception as e:
                    logger.debug(f"读取光敏反馈失败，返回缓存状态: {e}")
                    status["light_actual"] = self.state["light"]
            return status

    def learn_ir_code(self, name):
        return self.ir.learn_code(name)

    def cleanup(self):
        if self.light_feedback:
            self.light_feedback.cleanup()
        self.servo.cleanup()
        self.ir.cleanup()
        self.relay.cleanup()
        logger.info("所有设备资源已清理")
