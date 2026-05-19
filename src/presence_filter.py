"""
人员在场滤波器 — 滑动窗口去抖

通过可配置的进入/退出迟滞时间，将原始人员计数平滑为稳定的
在场布尔值，避免因检测抖动导致灯光/空调频繁开关。

逻辑:
  - 当前状态为"无人"时，需要连续 enter_duration 秒检测到人员才切换为"有人"
  - 当前状态为"有人"时，需要连续 exit_duration 秒未检测到人员才切换为"无人"

无外部依赖（不引用任何已删除模块）。
"""

from collections import deque


class PresenceFilter:
    """滑动窗口人员在场去抖器"""

    def __init__(self, enter_duration: float = 2.0, exit_duration: float = 10.0):
        """
        初始化滤波器。

        Args:
            enter_duration: 从"无人"切换到"有人"所需的连续检测时长（秒）。
                            在此时间窗口内持续检测到人员才确认在场。
            exit_duration:  从"有人"切换到"无人"所需的连续无人时长（秒）。
                            在此时间窗口内持续未检测到人员才确认离场。
        """
        if enter_duration <= 0:
            raise ValueError("enter_duration must be positive")
        if exit_duration <= 0:
            raise ValueError("exit_duration must be positive")

        self._enter_duration = enter_duration
        self._exit_duration = exit_duration

        # 滑动窗口：存储 (timestamp, person_count) 观测记录
        self._window: deque[tuple[float, int]] = deque()

        # 当前平滑后的在场状态
        self._present: bool = False

    @property
    def is_present(self) -> bool:
        """当前平滑后的在场状态。"""
        return self._present

    @property
    def enter_duration(self) -> float:
        """进入迟滞时长（秒）。"""
        return self._enter_duration

    @property
    def exit_duration(self) -> float:
        """退出迟滞时长（秒）。"""
        return self._exit_duration

    def _prune_window(self, ts: float) -> None:
        """移除超出最大窗口范围的旧观测。"""
        max_window = max(self._enter_duration, self._exit_duration)
        cutoff = ts - max_window
        while self._window and self._window[0][0] < cutoff:
            self._window.popleft()

    def update(self, person_count: int, ts: float) -> bool:
        """
        输入一次新的人员计数观测，返回平滑后的在场布尔值。

        Args:
            person_count: 当前帧检测到的人员数量（>= 0）。
            ts: 观测时间戳（秒，单调递增，如 time.time()）。

        Returns:
            True 表示判定为"有人在场"，False 表示"无人"。
        """
        # 记录观测
        self._window.append((ts, person_count))

        # 清理过期数据
        self._prune_window(ts)

        if not self._present:
            # 当前状态：无人 → 检查是否应切换为有人
            # 条件：在最近 enter_duration 内，所有观测都检测到人员
            self._present = self._check_enter(ts)
        else:
            # 当前状态：有人 → 检查是否应切换为无人
            # 条件：在最近 exit_duration 内，所有观测都未检测到人员
            if self._check_exit(ts):
                self._present = False

        return self._present

    def _check_enter(self, ts: float) -> bool:
        """
        检查是否满足进入条件：
        在最近 enter_duration 时间窗口内，所有观测的 person_count > 0，
        且窗口内的时间跨度 >= enter_duration。
        """
        cutoff = ts - self._enter_duration
        # 收集窗口内的观测
        relevant = [(t, c) for t, c in self._window if t >= cutoff]

        if not relevant:
            return False

        # 窗口内必须有足够的时间跨度
        earliest = relevant[0][0]
        if ts - earliest < self._enter_duration:
            return False

        # 窗口内所有观测都必须检测到人员
        return all(count > 0 for _, count in relevant)

    def _check_exit(self, ts: float) -> bool:
        """
        检查是否满足退出条件：
        在最近 exit_duration 时间窗口内，所有观测的 person_count == 0，
        且窗口内的时间跨度 >= exit_duration。
        """
        cutoff = ts - self._exit_duration
        # 收集窗口内的观测
        relevant = [(t, c) for t, c in self._window if t >= cutoff]

        if not relevant:
            return False

        # 窗口内必须有足够的时间跨度
        earliest = relevant[0][0]
        if ts - earliest < self._exit_duration:
            return False

        # 窗口内所有观测都必须为零人
        return all(count == 0 for _, count in relevant)

    def reset(self) -> None:
        """重置滤波器状态。"""
        self._window.clear()
        self._present = False
