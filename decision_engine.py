"""
决策引擎 - 核心控制逻辑
  1. 通过PresenceFilter滤波防止单帧误触发
  2. 结合光照传感器: 有人+光暗 才开灯(节能)
  3. 支持AUTO/MANUAL两种模式，MANUAL模式下自动决策暂停
  4. 决策过程同步写入CSV数据日志
"""

import time
import threading
import logging
import config
from presence_filter import PresenceFilter
from data_logger import DataLogger

logger = logging.getLogger(__name__)


class DecisionEngine:
    """决策引擎"""

    def __init__(self, detector, devices, sensor, light_sensor=None):
        self.detector = detector
        self.devices = devices
        self.sensor = sensor
        self.light_sensor = light_sensor  # BH1750环境光

        self.running = False
        self._thread = None
        self.last_person_seen_time = time.time()
        self.log_history = []

        # 防抖滤波器
        self.presence_filter = PresenceFilter(
            on_threshold=config.PRESENCE_ON_THRESHOLD,
            off_threshold=config.PRESENCE_OFF_THRESHOLD,
        )

        # 控制模式
        self.mode = config.DEFAULT_MODE  # "AUTO" | "MANUAL"

        # 数据日志
        self.data_logger = DataLogger() if config.ENABLE_CSV_LOG else None
        self.last_csv_sample_time = 0

    def set_mode(self, mode):
        """切换自动/手动模式"""
        if mode not in ("AUTO", "MANUAL"):
            return False
        self.mode = mode
        self._log_action(f"切换到{'自动' if mode == 'AUTO' else '手动'}模式")
        return True

    def _log_action(self, action):
        entry = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "action": action
        }
        self.log_history.append(entry)
        if len(self.log_history) > 200:
            self.log_history = self.log_history[-100:]
        logger.info(f"[决策] {action}")

    def _should_turn_on_light(self):
        """判断是否应开灯: 考虑环境亮度"""
        if not config.LIGHT_USE_AMBIENT or self.light_sensor is None:
            return True  # 未启用光照判断，直接开
        return self.light_sensor.is_dark()

    def _handle_presence(self, has_person, person_count):
        now = time.time()
        status = self.devices.get_status()

        if has_person:
            self.last_person_seen_time = now

            # 开灯判断: 有人 + 光照不足
            if not status["light"] and self._should_turn_on_light():
                self.devices.set_light(True)
                lux_info = ""
                if self.light_sensor:
                    lux_info = f"(环境亮度{self.light_sensor.get_status()['lux']}lux)"
                self._log_action(f"检测到{person_count}人 → 舵机开灯 {lux_info}")

            # 通电
            if not status["power"]:
                self.devices.set_power(True)
                self._log_action("继电器通电")
        else:
            elapsed = now - self.last_person_seen_time
            if elapsed >= config.NO_PERSON_TIMEOUT:
                if status["light"]:
                    self.devices.set_light(False)
                    self._log_action(f"无人超过{config.NO_PERSON_TIMEOUT}秒 → 舵机关灯")

                if status["ac"]:
                    self.devices.set_ac(False)
                    self._log_action("红外关闭空调")

                if status["power"]:
                    self.devices.set_power(False)
                    self._log_action("继电器断电")

    def _handle_temperature(self, has_person, temp):
        if not has_person:
            return

        status = self.devices.get_status()
        ac_mode = status["ac_mode"]

        if temp > config.AC_TEMP_HIGH and ac_mode != "cooling":
            self.devices.set_ac(True, "cooling")
            self._log_action(f"室温{temp}°C > {config.AC_TEMP_HIGH}°C → 红外开启制冷")
        elif temp < config.AC_TEMP_LOW and ac_mode != "heating":
            self.devices.set_ac(True, "heating")
            self._log_action(f"室温{temp}°C < {config.AC_TEMP_LOW}°C → 红外开启制热")
        elif ac_mode == "cooling" and temp <= config.AC_TEMP_COMFORT_MAX:
            self.devices.set_ac(False)
            self._log_action(f"室温{temp}°C 已舒适 → 红外关闭制冷")
        elif ac_mode == "heating" and temp >= config.AC_TEMP_COMFORT_MIN:
            self.devices.set_ac(False)
            self._log_action(f"室温{temp}°C 已舒适 → 红外关闭制热")

    def _take_snapshot(self):
        """采集系统快照用于CSV记录"""
        det = self.detector.get_status()
        sen = self.sensor.get_status()
        dev = self.devices.get_status()
        light = self.light_sensor.get_status() if self.light_sensor else {"lux": 0}

        return {
            "person_count": det["person_count"],
            "has_person": self.presence_filter.has_person,
            "temperature": sen["temperature"],
            "humidity": sen["humidity"],
            "lux": light.get("lux", 0),
            "light_on": dev["light"],
            "ac_on": dev["ac"],
            "ac_mode": dev["ac_mode"],
            "power_on": dev["power"],
            "mode": self.mode,
        }

    def decision_loop(self):
        self.running = True
        logger.info(f"决策引擎已启动 [模式: {self.mode}]")

        while self.running:
            try:
                det_status = self.detector.get_status()
                temp_status = self.sensor.get_status()

                raw_has_person = det_status["has_person"]
                person_count = det_status["person_count"]
                temp = temp_status["temperature"]

                # 通过滤波器得到稳定的"有人"状态
                stable_has_person = self.presence_filter.update(raw_has_person)

                # 仅AUTO模式下自动决策
                if self.mode == "AUTO":
                    self._handle_presence(stable_has_person, person_count)
                    self._handle_temperature(stable_has_person, temp)

                # 定期写入CSV
                now = time.time()
                if self.data_logger and now - self.last_csv_sample_time >= config.CSV_SAMPLE_INTERVAL:
                    snapshot = self._take_snapshot()
                    self.data_logger.log(snapshot)
                    self.last_csv_sample_time = now
            except Exception as e:
                if self.running:
                    logger.exception(f"决策线程异常: {e}")
                break

            time.sleep(1)

    def start(self):
        self._thread = threading.Thread(target=self.decision_loop, daemon=True)
        self._thread.start()
        return self._thread

    def stop(self, join_timeout=3.0):
        self.running = False
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=join_timeout)

    def get_full_status(self):
        status = {
            "detector": self.detector.get_status(),
            "sensor": self.sensor.get_status(),
            "devices": self.devices.get_status(),
            "mode": self.mode,
            "filter": self.presence_filter.get_debug_info(),
            "recent_logs": self.log_history[-20:],
        }
        if self.light_sensor:
            status["light_ambient"] = self.light_sensor.get_status()
        return status
