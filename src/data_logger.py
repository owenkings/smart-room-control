"""
数据日志记录器 — 轻量 CSV 事件日志

将控制事件以 (timestamp, event, payload_json) 三列追加到
logs/control_history.csv，供实验报告分析和 Web/GUI 历史查看。

公共接口:
    log_event(event, payload)  — 追加一行
    tail(n)                    — 返回最近 n 条记录
"""

from __future__ import annotations

import csv
import json
import logging
from collections import deque
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import LOGS_DIR

logger = logging.getLogger(__name__)

# CSV 文件路径
_CSV_PATH: Path = LOGS_DIR / "control_history.csv"

# CSV 列头
_HEADERS = ("timestamp", "event", "payload_json")


def _ensure_csv() -> None:
    """确保 logs 目录和 CSV 文件（含表头）存在。"""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    if not _CSV_PATH.exists():
        with open(_CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(_HEADERS)


def log_event(event: str, payload: dict | None = None) -> None:
    """追加一条事件记录到 CSV。

    Args:
        event: 事件名称，如 "servo_press_on", "mode_change", "ir_send" 等。
        payload: 任意可 JSON 序列化的字典，记录事件上下文。
                 为 None 时存储为空 JSON 对象 "{}"。
    """
    _ensure_csv()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload_json = json.dumps(payload if payload is not None else {}, ensure_ascii=False)
    try:
        with open(_CSV_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow((timestamp, event, payload_json))
    except OSError as e:
        logger.warning("CSV 日志写入失败: %s", e)


def tail(n: int = 10) -> list[dict[str, str]]:
    """返回最近 n 条日志记录。

    每条记录为字典: {"timestamp": ..., "event": ..., "payload_json": ...}
    如果文件不存在或为空，返回空列表。

    Args:
        n: 返回的最大行数，默认 10。
    """
    if not _CSV_PATH.exists():
        return []

    try:
        with open(_CSV_PATH, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header is None:
                return []

            # 使用 deque 高效保留最后 n 行
            recent: deque[list[str]] = deque(maxlen=max(n, 0))
            for row in reader:
                recent.append(row)

        # 将行映射为字典，使用 _HEADERS 作为键
        results: list[dict[str, str]] = []
        for row in recent:
            entry: dict[str, str] = {}
            for i, key in enumerate(_HEADERS):
                entry[key] = row[i] if i < len(row) else ""
            results.append(entry)
        return results
    except (OSError, csv.Error) as e:
        logger.warning("读取 CSV 日志失败: %s", e)
        return []
