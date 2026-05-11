"""
用户配置持久化
将用户在 GUI/Web 界面修改的偏好保存到 user_settings.json，
下次启动时自动加载，覆盖 config.py 的默认值。

保存的配置项:
  yolo_model          上次使用的模型
  detection_interval  检测间隔
  control_mode        AUTO / MANUAL
  servo_angle_on      舵机开灯角度
  servo_angle_off     舵机关灯角度
  servo_angle_neutral 舵机中立角度
  servo_action_duration 舵机按压保持时长
"""

import json
import os
import logging

logger = logging.getLogger(__name__)

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "user_settings.json")

_DEFAULTS = {
    "yolo_model": "yolov8n.pt",
    "detection_interval": 2.0,
    "control_mode": "AUTO",
    "servo_angle_on": 60,
    "servo_angle_off": 120,
    "servo_angle_neutral": 90,
    "servo_action_duration": 0.5,
}


def load() -> dict:
    """加载用户配置，文件不存在时返回默认值"""
    if not os.path.exists(SETTINGS_FILE):
        return dict(_DEFAULTS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 合并默认值（新增字段向后兼容）
        merged = dict(_DEFAULTS)
        merged.update(data)
        return merged
    except Exception as e:
        logger.warning(f"读取用户配置失败，使用默认值: {e}")
        return dict(_DEFAULTS)


def save(settings: dict):
    """保存用户配置"""
    try:
        current = load()
        current.update(settings)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
        logger.debug(f"用户配置已保存: {settings}")
    except Exception as e:
        logger.warning(f"保存用户配置失败: {e}")


def get(key: str, fallback=None):
    return load().get(key, fallback)
