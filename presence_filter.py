"""
人员检测防抖滤波器
用于避免YOLO单帧误检/漏检导致设备频繁开关

原理:
  - 连续N次检测到人 -> 判定"有人"
  - 连续M次未检测到人 -> 判定"无人"
  - 中间抖动不触发状态翻转
"""

import logging

logger = logging.getLogger(__name__)


class PresenceFilter:
    """状态滤波器 - 滞回判断"""

    def __init__(self, on_threshold=2, off_threshold=5):
        """
        Args:
            on_threshold: 连续检测到人几次才判定"有人"
            off_threshold: 连续未检测到几次才判定"无人"
        """
        self.on_threshold = on_threshold
        self.off_threshold = off_threshold
        self.hit_count = 0
        self.miss_count = 0
        self.has_person = False

    def update(self, detected):
        """更新检测结果
        Args:
            detected: 本次检测是否有人(bool)
        Returns:
            bool: 滤波后的稳定状态
        """
        if detected:
            self.hit_count += 1
            self.miss_count = 0
            if not self.has_person and self.hit_count >= self.on_threshold:
                self.has_person = True
                logger.info(f"[滤波器] 状态翻转: 无人 -> 有人 (连续命中{self.hit_count}次)")
        else:
            self.miss_count += 1
            self.hit_count = 0
            if self.has_person and self.miss_count >= self.off_threshold:
                self.has_person = False
                logger.info(f"[滤波器] 状态翻转: 有人 -> 无人 (连续未检测{self.miss_count}次)")

        return self.has_person

    def get_debug_info(self):
        return {
            "stable_state": self.has_person,
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
        }
