"""
温度自动空调控制器模块

基于状态机模式实现温度自动空调控制：
- 温度超过制冷阈值且有人在场 → 发送制冷命令
- 温度低于制热阈值且有人在场 → 发送制热命令
- 人员离场 → 强制关闭空调
- 仅在状态转换时发送IR命令，避免重复发送

Requirements: 9.1, 9.2, 9.3, 9.7, 9.8
"""

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class ACState(Enum):
    """空调运行状态"""
    OFF = "off"
    COOLING = "cooling"
    HEATING = "heating"


# IR 命令名称映射
IR_CMD_COOL = "ac_cool_26"
IR_CMD_HEAT = "ac_heat_24"
IR_CMD_OFF = "ac_power_off"

# 回差值（防止频繁切换）
HYSTERESIS = 2.0


class ACController:
    """
    温度自动空调控制器

    基于状态机模式，根据温度和人员在场状态决定空调运行模式。
    仅在状态转换时发送IR命令，避免重复发送（幂等性）。

    状态转换规则：
    - OFF → COOLING: temp > cooling_threshold AND is_present
    - OFF → HEATING: temp < heating_threshold AND is_present
    - COOLING → OFF: !is_present OR temp <= cooling_threshold - HYSTERESIS
    - HEATING → OFF: !is_present OR temp >= heating_threshold + HYSTERESIS
    - COOLING → HEATING: temp < heating_threshold
    - HEATING → COOLING: temp > cooling_threshold
    """

    def __init__(self, ir_controller, cooling_threshold: float = 28.0,
                 heating_threshold: float = 18.0):
        """
        初始化空调控制器。

        Args:
            ir_controller: IRController 实例，用于发送红外命令
            cooling_threshold: 制冷启动阈值（默认28°C）
            heating_threshold: 制热启动阈值（默认18°C）
        """
        self._ir_controller = ir_controller
        self._cooling_threshold = cooling_threshold
        self._heating_threshold = heating_threshold
        self._state = ACState.OFF

    @property
    def current_state(self) -> ACState:
        """当前空调状态"""
        return self._state

    @property
    def cooling_threshold(self) -> float:
        """制冷启动阈值"""
        return self._cooling_threshold

    @cooling_threshold.setter
    def cooling_threshold(self, value: float) -> None:
        self._cooling_threshold = value

    @property
    def heating_threshold(self) -> float:
        """制热启动阈值"""
        return self._heating_threshold

    @heating_threshold.setter
    def heating_threshold(self, value: float) -> None:
        self._heating_threshold = value

    def evaluate(self, temperature: float, is_present: bool) -> ACState:
        """
        根据温度和人员在场状态评估目标AC状态。
        仅在状态转换时发送IR命令。

        Args:
            temperature: 当前温度读数（°C）
            is_present: 是否有人在场

        Returns:
            评估后的当前AC状态
        """
        target_state = self._determine_target_state(temperature, is_present)

        # 仅在状态转换时发送IR命令
        if target_state != self._state:
            old_state = self._state
            self._state = target_state
            self._send_state_command(target_state)
            logger.info(
                f"AC状态转换: {old_state.value} → {target_state.value} "
                f"(温度={temperature:.1f}°C, 有人={is_present})"
            )

        return self._state

    def force_off(self) -> None:
        """
        强制关闭空调（人员离场时调用）。

        无论当前状态如何，都发送关闭命令并将状态设为OFF。
        """
        if self._state != ACState.OFF:
            old_state = self._state
            self._state = ACState.OFF
            self._send_ir_command(IR_CMD_OFF)
            logger.info(f"AC强制关闭: {old_state.value} → OFF (人员离场)")

    def _determine_target_state(self, temperature: float,
                                is_present: bool) -> ACState:
        """
        根据当前状态、温度和在场状态确定目标状态。

        使用回差（hysteresis）防止在阈值附近频繁切换。
        """
        # 无人在场时，目标状态为OFF
        if not is_present:
            return ACState.OFF

        # 有人在场，根据当前状态和温度判定
        if self._state == ACState.OFF:
            # OFF → COOLING: 温度超过制冷阈值
            if temperature > self._cooling_threshold:
                return ACState.COOLING
            # OFF → HEATING: 温度低于制热阈值
            elif temperature < self._heating_threshold:
                return ACState.HEATING
            # 舒适区，保持OFF
            return ACState.OFF

        elif self._state == ACState.COOLING:
            # COOLING → HEATING: 温度低于制热阈值（极端情况）
            if temperature < self._heating_threshold:
                return ACState.HEATING
            # COOLING → OFF: 温度降到制冷阈值以下（含回差）
            if temperature <= self._cooling_threshold - HYSTERESIS:
                return ACState.OFF
            # 保持制冷
            return ACState.COOLING

        elif self._state == ACState.HEATING:
            # HEATING → COOLING: 温度超过制冷阈值（极端情况）
            if temperature > self._cooling_threshold:
                return ACState.COOLING
            # HEATING → OFF: 温度升到制热阈值以上（含回差）
            if temperature >= self._heating_threshold + HYSTERESIS:
                return ACState.OFF
            # 保持制热
            return ACState.HEATING

        return ACState.OFF

    def _send_state_command(self, state: ACState) -> None:
        """根据目标状态发送对应的IR命令"""
        if state == ACState.COOLING:
            self._send_ir_command(IR_CMD_COOL)
        elif state == ACState.HEATING:
            self._send_ir_command(IR_CMD_HEAT)
        elif state == ACState.OFF:
            self._send_ir_command(IR_CMD_OFF)

    def _send_ir_command(self, command_name: str) -> None:
        """
        发送IR命令，缺少命令时记录警告并跳过。

        Args:
            command_name: IR命令名称（如 "ac_cool_26"）
        """
        if self._ir_controller is None:
            logger.warning(f"IR控制器未初始化，跳过AC命令: {command_name}")
            return

        # 检查命令是否已录制
        available_commands = self._ir_controller.list_commands()
        if command_name not in available_commands:
            logger.warning(
                f"IR命令 '{command_name}' 未录制，跳过AC动作。"
                f"请通过IR Wizard录制该命令。"
            )
            return

        # 发送命令
        success = self._ir_controller.send_command(command_name)
        if success:
            logger.debug(f"AC IR命令已发送: {command_name}")
        else:
            logger.error(f"AC IR命令发送失败: {command_name}")
