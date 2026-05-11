"""
数据日志记录器
将系统运行数据持久化到文件，便于实验报告分析

输出文件:
  logs/system.log      - 系统运行日志(调试用)
  logs/control_history.csv - 控制历史(Excel可直接打开分析)
"""

import os
import csv
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

LOG_DIR = "logs"


def ensure_log_dir():
    os.makedirs(LOG_DIR, exist_ok=True)


class DataLogger:
    """CSV数据记录器"""

    CSV_HEADERS = [
        "timestamp", "person_count", "has_person", "temperature", "humidity",
        "lux", "light_on", "ac_on", "ac_mode", "power_on", "mode", "action"
    ]

    def __init__(self, csv_name="control_history.csv"):
        ensure_log_dir()
        self.csv_path = os.path.join(LOG_DIR, csv_name)
        self._init_csv()

    def _init_csv(self):
        """如果文件不存在，写入表头"""
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self.CSV_HEADERS)

    def log(self, snapshot, action=""):
        """记录一次系统快照
        Args:
            snapshot: dict 包含所有传感器和设备状态
            action: 本次触发的动作描述
        """
        try:
            row = [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                snapshot.get("person_count", 0),
                snapshot.get("has_person", False),
                snapshot.get("temperature", 0),
                snapshot.get("humidity", 0),
                snapshot.get("lux", 0),
                snapshot.get("light_on", False),
                snapshot.get("ac_on", False),
                snapshot.get("ac_mode", "off"),
                snapshot.get("power_on", False),
                snapshot.get("mode", "AUTO"),
                action,
            ]
            with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(row)
        except Exception as e:
            logger.warning(f"CSV日志写入失败: {e}")


def setup_file_logging():
    """配置文件日志处理器 - 所有logger输出同步到文件"""
    ensure_log_dir()
    log_path = os.path.join(LOG_DIR, "system.log")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))

    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    logger.info(f"文件日志已启用: {log_path}")
