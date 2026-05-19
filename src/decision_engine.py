"""
决策引擎 — 智能教室测控系统核心协调器

组合所有传感器、执行器和辅助模块，根据多条件评估结果（时间+光照+人员在场）
自动控制灯光（舵机），并根据温度和人员在场状态自动控制空调（红外）。

灯光控制逻辑:
  - 使用 MultiConditionEvaluator 进行 AND 逻辑评估
  - 所有启用条件满足 → 开灯（如灯当前关闭）
  - 任一启用条件不满足 → 关灯（如灯当前开启）
  - 无启用条件 → 不执行灯光动作

空调控制逻辑:
  - 使用 ACController 状态机进行温度评估
  - 仅在状态转换时发送IR命令
  - 人员离场时调用 force_off() 强制关闭

模式:
  AUTO   — 自动控制灯光和空调
  MANUAL — 仅采集数据，不自动执行任何动作

无继电器(relay)引用。
"""

from __future__ import annotations

import logging
import threading
import time
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class Mode(str, Enum):
    """控制模式枚举"""
    AUTO = "AUTO"
    MANUAL = "MANUAL"


# 决策循环默认间隔（秒）
_DECISION_INTERVAL: float = 2.0


class DecisionEngine:
    """智能教室决策引擎

    组合以下子组件:
      - TemperatureSensor      (src/sensor_dht.py)
      - LightSensor            (src/sensor_light.py)
      - Detector               (src/detector.py)
      - PresenceFilter         (src/presence_filter.py)
      - ServoController        (src/servo.py)
      - IRController           (src/ir_controller.py)
      - DataLogger             (src/data_logger.py)  — 模块级函数
      - UserSettings           (src/user_settings.py) — 模块级函数
      - MultiConditionEvaluator (src/condition_evaluator.py)
      - TimeConditionProvider  (src/time_condition.py)
      - ACController           (src/ac_controller.py)
    """

    def __init__(
        self,
        temperature_sensor=None,
        light_sensor=None,
        detector=None,
        presence_filter=None,
        servo=None,
        ir_controller=None,
        data_logger=None,
        user_settings=None,
        condition_evaluator=None,
        time_condition=None,
        ac_controller=None,
        decision_interval: float = _DECISION_INTERVAL,
    ):
        """初始化决策引擎。

        所有组件参数均可选，传入 None 时使用默认实例化。
        支持注入 stub/mock 用于测试。

        Args:
            temperature_sensor: TemperatureSensor 实例或兼容对象
            light_sensor: LightSensor 实例或兼容对象
            detector: Detector/PersonDetector 实例或兼容对象
            presence_filter: PresenceFilter 实例或兼容对象
            servo: ServoController 实例或兼容对象
            ir_controller: IRController 实例或兼容对象
            data_logger: 具有 log_event(event, payload) 的模块/对象
            user_settings: 具有 get(key, default) / set(key, value) 的模块/对象
            condition_evaluator: MultiConditionEvaluator 实例或兼容对象
            time_condition: TimeConditionProvider 实例或兼容对象
            ac_controller: ACController 实例或兼容对象
            decision_interval: 决策循环间隔（秒）
        """
        # 延迟导入，仅在未注入时使用
        self.temperature_sensor = temperature_sensor or self._create_temperature_sensor()
        self.light_sensor = light_sensor or self._create_light_sensor()
        self.detector = detector or self._create_detector()
        self.presence_filter = presence_filter or self._create_presence_filter()
        self.servo = servo or self._create_servo()
        self.ir_controller = ir_controller or self._create_ir_controller()
        self.data_logger = data_logger or self._create_data_logger()
        self.user_settings = user_settings or self._create_user_settings()

        # 新增组件：多条件评估器、时间条件、空调控制器
        self.condition_evaluator = condition_evaluator or self._create_condition_evaluator()
        self.time_condition = time_condition or self._create_time_condition()
        self.ac_controller = ac_controller or self._create_ac_controller()

        # 控制模式
        self._mode: Mode = Mode(
            self.user_settings.get("control_mode", Mode.AUTO.value)
        )

        # 决策循环
        self._decision_interval = decision_interval
        self._running = False
        self._thread: threading.Thread | None = None

        # 内部状态跟踪
        self._light_on = False       # 灯光当前是否已开
        self._prev_present = False   # 上一次循环的人员在场状态（用于检测离场事件）

        logger.info("DecisionEngine 初始化完成, 模式=%s", self._mode.value)

    # ------------------------------------------------------------------
    # 默认组件工厂（延迟导入避免循环依赖）
    # ------------------------------------------------------------------

    @staticmethod
    def _create_temperature_sensor():
        from src.sensor_dht import TemperatureSensor
        return TemperatureSensor()

    @staticmethod
    def _create_light_sensor():
        from src.sensor_light import LightSensor
        return LightSensor()

    @staticmethod
    def _create_detector():
        from src.detector import Detector
        return Detector()

    @staticmethod
    def _create_presence_filter():
        from src.presence_filter import PresenceFilter
        return PresenceFilter()

    @staticmethod
    def _create_servo():
        from src.servo import ServoController
        return ServoController()

    @staticmethod
    def _create_ir_controller():
        from src.ir_controller import IRController
        return IRController()

    @staticmethod
    def _create_data_logger():
        from src import data_logger
        return data_logger

    @staticmethod
    def _create_user_settings():
        from src import user_settings
        return user_settings

    def _create_condition_evaluator(self):
        """创建多条件评估器，从 UserSettings 加载条件配置。"""
        from src.condition_evaluator import MultiConditionEvaluator, ConditionConfig

        # 从 UserSettings 加载条件启用配置
        conditions_cfg = self.user_settings.get("light_conditions", {})
        config = ConditionConfig(
            time_enabled=conditions_cfg.get("time_enabled", True),
            light_enabled=conditions_cfg.get("light_enabled", True),
            presence_enabled=conditions_cfg.get("presence_enabled", True),
        )
        return MultiConditionEvaluator(config)

    def _create_time_condition(self):
        """创建时间条件提供者，从 UserSettings 加载回退时间。"""
        from src.time_condition import TimeConditionProvider

        # 从 UserSettings 加载回退白天时间范围
        fallback_cfg = self.user_settings.get("fallback_daytime", {})
        fallback_start = fallback_cfg.get("start", "06:00")
        fallback_end = fallback_cfg.get("end", "18:00")

        return TimeConditionProvider(
            fallback_start=fallback_start,
            fallback_end=fallback_end,
        )

    def _create_ac_controller(self):
        """创建空调控制器，从 UserSettings 加载温度阈值。"""
        from src.ac_controller import ACController

        # 从 UserSettings 加载空调温度阈值
        ac_cfg = self.user_settings.get("ac_thresholds", {})
        cooling_threshold = ac_cfg.get("cooling", 28.0)
        heating_threshold = ac_cfg.get("heating", 18.0)

        return ACController(
            ir_controller=self.ir_controller,
            cooling_threshold=cooling_threshold,
            heating_threshold=heating_threshold,
        )

    # ------------------------------------------------------------------
    # 启动 / 停止
    # ------------------------------------------------------------------

    def start(self) -> None:
        """启动所有传感器、检测器和决策循环。"""
        if self._running:
            return

        logger.info("DecisionEngine 启动中...")

        # 启动传感器
        self.temperature_sensor.start()
        self.light_sensor.start()

        # 启动人员检测器
        self.detector.start()

        # 启动决策循环
        self._running = True
        self._thread = threading.Thread(
            target=self._decision_loop, name="DecisionLoop", daemon=True
        )
        self._thread.start()

        self.data_logger.log_event("engine_start", {"mode": self._mode.value})
        logger.info("DecisionEngine 已启动")

    def stop(self) -> None:
        """停止决策循环（不释放硬件资源，用 cleanup() 完全释放）。"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=self._decision_interval + 2)
            self._thread = None
        logger.info("DecisionEngine 决策循环已停止")

    def cleanup(self) -> None:
        """停止所有组件并释放硬件资源。"""
        logger.info("DecisionEngine cleanup 开始...")
        self.stop()

        # 停止传感器
        try:
            self.temperature_sensor.stop()
        except Exception as e:
            logger.warning("温湿度传感器停止异常: %s", e)

        try:
            self.light_sensor.stop()
        except Exception as e:
            logger.warning("光照传感器停止异常: %s", e)

        # 停止检测器
        try:
            self.detector.stop()
        except Exception as e:
            logger.warning("检测器停止异常: %s", e)

        # 释放执行器
        try:
            self.servo.cleanup()
        except Exception as e:
            logger.warning("舵机清理异常: %s", e)

        try:
            self.ir_controller.cleanup()
        except Exception as e:
            logger.warning("红外控制器清理异常: %s", e)

        self.data_logger.log_event("engine_cleanup", {})
        logger.info("DecisionEngine cleanup 完成")

    # ------------------------------------------------------------------
    # 模式控制
    # ------------------------------------------------------------------

    @property
    def mode(self) -> str:
        """当前控制模式字符串。"""
        return self._mode.value

    def set_mode(self, mode: str) -> str:
        """切换控制模式。

        Args:
            mode: "AUTO" 或 "MANUAL"

        Returns:
            切换后的模式字符串

        Raises:
            ValueError: 无效的模式值
        """
        try:
            new_mode = Mode(mode.upper())
        except ValueError:
            raise ValueError(
                f"无效模式: {mode!r}, 可选: 'AUTO', 'MANUAL'"
            )

        old_mode = self._mode
        self._mode = new_mode

        # 持久化
        self.user_settings.set("control_mode", new_mode.value)
        self.data_logger.log_event(
            "mode_change", {"from": old_mode.value, "to": new_mode.value}
        )
        logger.info("模式切换: %s → %s", old_mode.value, new_mode.value)
        return new_mode.value

    # ------------------------------------------------------------------
    # 状态查询
    # ------------------------------------------------------------------

    def get_state(self) -> dict[str, Any]:
        """返回系统当前状态，供 Web/GUI 消费。

        Returns:
            dict: {
                mode, presence, light_on, ac_state,
                temperature, humidity, lux,
                servo, ir_commands, detector,
                condition_config, time_condition
            }
        """
        # 温湿度
        dht_status = self.temperature_sensor.get_status()
        # 光照
        light_status = self.light_sensor.get_status()
        # 舵机
        servo_status = self.servo.get_status()
        # 红外命令列表
        ir_commands = self.ir_controller.list_commands()
        # 检测器
        detector_status = self.detector.get_status()

        return {
            "mode": self._mode.value,
            "presence": self.presence_filter.is_present,
            "light_on": self._light_on,
            "ac_state": self.ac_controller.current_state.value,
            "temperature": dht_status.get("temperature"),
            "humidity": dht_status.get("humidity"),
            "lux": light_status.get("lux", 0.0),
            "servo": servo_status,
            "ir_commands": ir_commands,
            "detector": detector_status,
            "condition_config": {
                "time_enabled": self.condition_evaluator.config.time_enabled,
                "light_enabled": self.condition_evaluator.config.light_enabled,
                "presence_enabled": self.condition_evaluator.config.presence_enabled,
            },
            "time_condition": {
                "sunrise": str(self.time_condition.sunrise),
                "sunset": str(self.time_condition.sunset),
            },
        }

    # ------------------------------------------------------------------
    # 决策循环
    # ------------------------------------------------------------------

    def _decision_loop(self) -> None:
        """后台决策循环：周期性检查传感器状态并执行自动控制。"""
        logger.info("决策循环已启动 (间隔 %.1fs)", self._decision_interval)

        while self._running:
            try:
                self._tick()
            except Exception as e:
                logger.error("决策循环异常: %s", e, exc_info=True)

            time.sleep(self._decision_interval)

    def _tick(self) -> None:
        """单次决策逻辑。

        使用多条件评估器替代原有简单逻辑：
        1. 更新人员在场状态
        2. 检测人员离场事件 → 强制关闭空调
        3. 在 AUTO 模式下：
           a. 获取三个条件状态（时间、光照、人员在场）
           b. 使用 MultiConditionEvaluator 评估灯光决策
           c. 使用 ACController 评估空调决策
        """
        # 1. 更新人员在场状态
        person_count = self.detector.get_person_count()
        ts = time.time()
        self.presence_filter.update(person_count, ts)
        is_present = self.presence_filter.is_present

        # 2. 检测人员离场事件（从有人变为无人）→ 强制关闭空调
        if self._prev_present and not is_present:
            self._on_presence_lost()

        # 更新上一次在场状态
        self._prev_present = is_present

        # 手动模式不执行自动动作
        if self._mode != Mode.AUTO:
            return

        # 3a. 获取三个条件状态
        # 时间条件：当前是否为需要照明的时段
        time_met = self.time_condition.is_dark_period()

        # 光照条件：当前光照是否低于阈值
        light_met = self.light_sensor.is_dark()

        # 人员在场条件
        presence_met = is_present

        # 3b. 使用多条件评估器评估灯光决策
        decision = self.condition_evaluator.evaluate(time_met, light_met, presence_met)

        if decision is True and not self._light_on:
            # 所有启用条件都满足，且灯当前关闭 → 开灯
            self._action_lights_on()
        elif decision is False and self._light_on:
            # 至少一个启用条件不满足，且灯当前开启 → 关灯
            self._action_lights_off()
        # decision is None → 无启用条件，不执行灯光动作

        # 3c. 使用 ACController 评估空调决策（仅在有温度数据时）
        dht_status = self.temperature_sensor.get_status()
        temperature = dht_status.get("temperature")
        if temperature is not None:
            self.ac_controller.evaluate(temperature, is_present)

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------

    def _on_presence_lost(self) -> None:
        """人员离场事件处理：强制关闭空调。"""
        try:
            self.ac_controller.force_off()
            self.data_logger.log_event("ac_force_off", {"trigger": "presence_lost"})
            logger.info("人员离场: 空调已强制关闭")
        except Exception as e:
            logger.error("人员离场关闭空调失败: %s", e)

    # ------------------------------------------------------------------
    # 动作执行
    # ------------------------------------------------------------------

    def _action_lights_on(self) -> None:
        """开灯动作。"""
        try:
            self.servo.press_on()
            self._light_on = True
            self.data_logger.log_event("servo_press_on", {"trigger": "auto"})
            logger.info("AUTO: 开灯")
        except Exception as e:
            logger.error("开灯动作失败: %s", e)

    def _action_lights_off(self) -> None:
        """关灯动作。"""
        try:
            self.servo.press_off()
            self._light_on = False
            self.data_logger.log_event("servo_press_off", {"trigger": "auto"})
            logger.info("AUTO: 关灯")
        except Exception as e:
            logger.error("关灯动作失败: %s", e)
