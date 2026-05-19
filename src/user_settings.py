"""
用户配置持久化模块 (src/user_settings.py)

将用户在 GUI/Web 界面修改的偏好保存到 data/user_settings.json，
下次启动时自动加载。使用原子写入（tmp + os.replace）确保写入安全。

配置项:
  yolo_model          YOLO 模型文件名
  detection_interval  检测间隔（秒）
  control_mode        控制模式 (AUTO / MANUAL)
  servo_calibration   舵机校准数据 (neutral_angle, on_offset, off_offset)
  dark_threshold      光照不足阈值 (lux)
  light_conditions    灯光控制条件启用标志 (time_enabled, light_enabled, presence_enabled)
  fallback_daytime    回退白天时间范围 (start, end)
  ac_thresholds       空调温度阈值 (cooling, heating)
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from config import DATA_DIR

logger = logging.getLogger(__name__)

# 配置文件路径
SETTINGS_FILE: Path = DATA_DIR / "user_settings.json"

# 默认值
_DEFAULTS: dict[str, Any] = {
    "yolo_model": "yolov8n.pt",
    "detection_interval": 2.0,
    "control_mode": "AUTO",
    "servo_calibration": {
        "neutral_angle": 90,
        "on_offset": -30,
        "off_offset": 30,
    },
    "dark_threshold": 150.0,
    "light_conditions": {
        "time_enabled": True,
        "light_enabled": True,
        "presence_enabled": True,
    },
    "fallback_daytime": {
        "start": "06:00",
        "end": "18:00",
    },
    "ac_thresholds": {
        "cooling": 28.0,
        "heating": 18.0,
    },
}


def _deep_merge(defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """递归合并配置字典，确保嵌套字段向后兼容。

    对于嵌套 dict，将 defaults 中的键作为基础，用 overrides 中的对应值覆盖；
    对于非 dict 值，直接使用 overrides 中的值。
    """
    merged = dict(defaults)
    for key, value in overrides.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_all() -> dict[str, Any]:
    """加载完整配置，文件不存在或损坏时返回默认值副本。

    使用深度合并确保新增的嵌套字段在旧配置文件中也能获得默认值。
    """
    if not SETTINGS_FILE.exists():
        return _deep_merge(_DEFAULTS, {})
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 深度合并默认值，保证新增字段向后兼容
        return _deep_merge(_DEFAULTS, data)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("读取用户配置失败，使用默认值: %s", e)
        return _deep_merge(_DEFAULTS, {})


def _save_all(data: dict[str, Any]) -> None:
    """原子写入配置文件：先写临时文件，再 os.replace 覆盖目标。"""
    # 确保 data 目录存在
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)

    # 在同目录下创建临时文件，保证同一文件系统（os.replace 要求）
    fd, tmp_path = tempfile.mkstemp(
        suffix=".tmp",
        prefix="user_settings_",
        dir=str(SETTINGS_FILE.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # 原子替换
        os.replace(tmp_path, str(SETTINGS_FILE))
        logger.debug("用户配置已保存")
    except OSError as e:
        logger.warning("保存用户配置失败: %s", e)
        # 清理临时文件
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def get(key: str, default: Any = None) -> Any:
    """获取单个配置项，不存在时返回 *default*。"""
    data = _load_all()
    return data.get(key, default)


def set(key: str, value: Any) -> None:  # noqa: A001 — shadow built-in 'set' intentionally
    """设置单个配置项并原子写入磁盘。"""
    data = _load_all()
    data[key] = value
    _save_all(data)
