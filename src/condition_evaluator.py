"""
多条件评估器 — 灯光控制条件组合判定

实现 AND 逻辑的多条件评估：
  - 所有启用条件都满足 → True（应开灯）
  - 任一启用条件不满足 → False（应关灯）
  - 无启用条件         → None（不执行动作）

支持三种条件：时间条件、光照条件、人员在场条件。
每种条件可独立启用/禁用，由用户通过 UserSettings 配置。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ConditionConfig:
    """条件启用配置

    Attributes:
        time_enabled: 是否启用时间条件（日出日落判定）
        light_enabled: 是否启用光照条件（传感器阈值判定）
        presence_enabled: 是否启用人员在场条件（YOLO检测判定）
    """

    time_enabled: bool = True
    light_enabled: bool = True
    presence_enabled: bool = True


class MultiConditionEvaluator:
    """多条件 AND 逻辑评估器

    根据启用的条件和各条件的满足状态，返回综合判定结果。
    评估器本身无状态，纯函数式设计便于测试。
    """

    def __init__(self, config: ConditionConfig) -> None:
        """初始化评估器。

        Args:
            config: 条件启用配置
        """
        self._config = config

    @property
    def config(self) -> ConditionConfig:
        """当前条件配置。"""
        return self._config

    def evaluate(
        self,
        time_met: bool,
        light_met: bool,
        presence_met: bool,
    ) -> bool | None:
        """评估所有启用条件的 AND 结果。

        仅考虑已启用的条件。未启用的条件不参与判定。

        Args:
            time_met: 时间条件是否满足（当前为需要照明时段）
            light_met: 光照条件是否满足（光照低于阈值）
            presence_met: 人员在场条件是否满足（有人在场）

        Returns:
            True: 所有启用条件都满足（应开灯）
            False: 至少一个启用条件不满足（应关灯）
            None: 没有启用任何条件（不执行动作）
        """
        # 收集所有启用条件的满足状态
        enabled_results: list[bool] = []

        if self._config.time_enabled:
            enabled_results.append(time_met)
        if self._config.light_enabled:
            enabled_results.append(light_met)
        if self._config.presence_enabled:
            enabled_results.append(presence_met)

        # 无启用条件 → 不执行动作
        if not enabled_results:
            return None

        # AND 逻辑：所有启用条件都满足才返回 True
        return all(enabled_results)

    def update_config(self, config: ConditionConfig) -> None:
        """更新条件启用配置。

        Args:
            config: 新的条件启用配置
        """
        self._config = config
