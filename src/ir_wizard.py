"""
红外空调引导式录制向导 (IR Wizard)

提供固定12步命令序列的引导式录制流程，降低用户操作门槛。
每一步显示中文指令描述需要按哪个遥控器按钮，支持跳过和重试。
完成时批量保存到 data/ir_commands.json。
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class WizardStep:
    """向导步骤定义"""
    command_name: str
    instruction_zh: str
    recorded: bool = False
    skipped: bool = False


class IRWizard:
    """
    红外空调引导式录制向导。

    固定12步命令序列，引导用户逐步录制空调遥控器的各个命令。
    支持跳过、重试，完成时批量保存所有已录制命令。
    """

    def __init__(self, ir_controller) -> None:
        """
        初始化向导。

        Args:
            ir_controller: IRController 实例，用于录制红外信号
        """
        self._ir_controller = ir_controller
        self._current_step: int = 0
        self._started: bool = False
        self._steps: list[WizardStep] = self._build_steps()

    @staticmethod
    def _build_steps() -> list[WizardStep]:
        """构建固定12步命令序列"""
        return [
            WizardStep(
                command_name="ac_on",
                instruction_zh="请按遥控器上的【开机】按钮"
            ),
            WizardStep(
                command_name="ac_off",
                instruction_zh="请按遥控器上的【关机】按钮"
            ),
            WizardStep(
                command_name="ac_cool",
                instruction_zh="请按遥控器上的【制冷模式】按钮"
            ),
            WizardStep(
                command_name="ac_heat",
                instruction_zh="请按遥控器上的【制热模式】按钮"
            ),
            WizardStep(
                command_name="ac_auto",
                instruction_zh="请按遥控器上的【自动模式】按钮"
            ),
            WizardStep(
                command_name="ac_fan_low",
                instruction_zh="请按遥控器上的【风速低】按钮"
            ),
            WizardStep(
                command_name="ac_fan_mid",
                instruction_zh="请按遥控器上的【风速中】按钮"
            ),
            WizardStep(
                command_name="ac_fan_high",
                instruction_zh="请按遥控器上的【风速高】按钮"
            ),
            WizardStep(
                command_name="ac_temp_up",
                instruction_zh="请按遥控器上的【温度升高(+)】按钮"
            ),
            WizardStep(
                command_name="ac_temp_down",
                instruction_zh="请按遥控器上的【温度降低(-)】按钮"
            ),
            WizardStep(
                command_name="ac_swing",
                instruction_zh="请按遥控器上的【摆风开关】按钮"
            ),
            WizardStep(
                command_name="ac_sleep",
                instruction_zh="请按遥控器上的【睡眠模式】按钮"
            ),
        ]

    @property
    def current_step(self) -> int:
        """当前步骤索引 (0-based)"""
        return self._current_step

    @property
    def total_steps(self) -> int:
        """总步骤数"""
        return len(self._steps)

    @property
    def current_instruction(self) -> str:
        """当前步骤的中文指令"""
        if self._current_step >= len(self._steps):
            return "所有步骤已完成"
        return self._steps[self._current_step].instruction_zh

    @property
    def is_complete(self) -> bool:
        """是否所有步骤都已处理（录制或跳过）"""
        return all(s.recorded or s.skipped for s in self._steps)

    @property
    def recorded_count(self) -> int:
        """已成功录制的步骤数"""
        return sum(1 for s in self._steps if s.recorded)

    @property
    def skipped_count(self) -> int:
        """已跳过的步骤数"""
        return sum(1 for s in self._steps if s.skipped)

    def start(self) -> dict:
        """
        开始向导，返回第一步信息。

        Returns:
            包含向导状态和第一步指令的字典
        """
        self._started = True
        self._current_step = 0
        # 重置所有步骤状态
        self._steps = self._build_steps()

        logger.info("IR录制向导已启动")
        return {
            "success": True,
            "message": "向导已启动",
            "current_step": self._current_step + 1,
            "total_steps": self.total_steps,
            "command_name": self._steps[0].command_name,
            "instruction": self._steps[0].instruction_zh,
        }

    def record_current(self, timeout: float = 10.0) -> dict:
        """
        录制当前步骤的红外信号。

        成功录制后自动前进到下一个未处理的步骤。

        Args:
            timeout: 等待红外信号的超时时间（秒）

        Returns:
            录制结果字典
        """
        if not self._started:
            return {"success": False, "error": "向导未启动，请先调用 start()"}

        if self._current_step >= len(self._steps):
            return {"success": False, "error": "所有步骤已完成"}

        step = self._steps[self._current_step]
        logger.info(f"录制步骤 {self._current_step + 1}/{self.total_steps}: {step.command_name}")

        # 使用 IRController 的 start_learning 方法录制
        result = self._ir_controller.start_learning(step.command_name, timeout=timeout)

        if result.get("success"):
            step.recorded = True
            step.skipped = False
            logger.info(f"步骤 {self._current_step + 1} 录制成功: {step.command_name}")

            # 自动前进到下一步
            self._advance_to_next()

            return {
                "success": True,
                "message": f"录制成功: {step.command_name}",
                "command_name": step.command_name,
                "is_complete": self.is_complete,
                "current_step": self._current_step + 1 if self._current_step < len(self._steps) else self.total_steps,
                "total_steps": self.total_steps,
                "next_instruction": self.current_instruction,
            }
        else:
            error_msg = result.get("error", "未知错误")
            logger.warning(f"步骤 {self._current_step + 1} 录制失败: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "command_name": step.command_name,
                "current_step": self._current_step + 1,
                "total_steps": self.total_steps,
                "instruction": step.instruction_zh,
            }

    def skip_current(self) -> dict:
        """
        跳过当前步骤，前进到下一步。

        Returns:
            跳过结果字典
        """
        if not self._started:
            return {"success": False, "error": "向导未启动，请先调用 start()"}

        if self._current_step >= len(self._steps):
            return {"success": False, "error": "所有步骤已完成"}

        step = self._steps[self._current_step]
        step.skipped = True
        step.recorded = False
        logger.info(f"步骤 {self._current_step + 1} 已跳过: {step.command_name}")

        # 前进到下一步
        self._advance_to_next()

        return {
            "success": True,
            "message": f"已跳过: {step.command_name}",
            "command_name": step.command_name,
            "is_complete": self.is_complete,
            "current_step": self._current_step + 1 if self._current_step < len(self._steps) else self.total_steps,
            "total_steps": self.total_steps,
            "next_instruction": self.current_instruction,
        }

    def retry_current(self) -> dict:
        """
        重试当前步骤（重置当前步骤状态，准备重新录制）。

        Returns:
            重试准备信息字典
        """
        if not self._started:
            return {"success": False, "error": "向导未启动，请先调用 start()"}

        if self._current_step >= len(self._steps):
            return {"success": False, "error": "所有步骤已完成"}

        step = self._steps[self._current_step]
        step.recorded = False
        step.skipped = False
        logger.info(f"步骤 {self._current_step + 1} 准备重试: {step.command_name}")

        return {
            "success": True,
            "message": f"请重新录制: {step.command_name}",
            "command_name": step.command_name,
            "current_step": self._current_step + 1,
            "total_steps": self.total_steps,
            "instruction": step.instruction_zh,
        }

    def finish(self) -> dict:
        """
        完成向导，批量保存所有已录制命令到 data/ir_commands.json。

        Returns:
            完成结果字典，包含录制和跳过的统计信息
        """
        if not self._started:
            return {"success": False, "error": "向导未启动，请先调用 start()"}

        # 批量保存：IRController 在 start_learning 成功时已将命令存入内存，
        # 这里调用 save_commands() 确保所有命令持久化到文件
        self._ir_controller.save_commands()

        recorded_names = [s.command_name for s in self._steps if s.recorded]
        skipped_names = [s.command_name for s in self._steps if s.skipped]

        logger.info(
            f"IR录制向导完成: 已录制 {len(recorded_names)} 个, "
            f"已跳过 {len(skipped_names)} 个"
        )

        self._started = False

        return {
            "success": True,
            "message": "向导已完成，命令已保存",
            "recorded_count": len(recorded_names),
            "skipped_count": len(skipped_names),
            "recorded_commands": recorded_names,
            "skipped_commands": skipped_names,
        }

    def get_status(self) -> dict:
        """
        返回向导完整状态。

        Returns:
            包含所有步骤状态的字典
        """
        steps_status = []
        for i, step in enumerate(self._steps):
            steps_status.append({
                "step": i + 1,
                "command_name": step.command_name,
                "instruction": step.instruction_zh,
                "recorded": step.recorded,
                "skipped": step.skipped,
            })

        return {
            "started": self._started,
            "current_step": self._current_step + 1 if self._current_step < len(self._steps) else self.total_steps,
            "total_steps": self.total_steps,
            "is_complete": self.is_complete,
            "recorded_count": self.recorded_count,
            "skipped_count": self.skipped_count,
            "steps": steps_status,
        }

    def _advance_to_next(self) -> None:
        """前进到下一个未处理的步骤"""
        self._current_step += 1
        # 如果已经超过最后一步，不再前进
        if self._current_step >= len(self._steps):
            return
