"""
UserSettings 模块单元测试

验证:
- _DEFAULTS 包含所有必需的配置字段
- _deep_merge 正确处理嵌套字典合并
- _load_all 向后兼容旧配置文件
- 配置文件损坏时回退到默认值
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.user_settings import _DEFAULTS, _deep_merge, _load_all, SETTINGS_FILE


class TestDefaults:
    """验证 _DEFAULTS 包含所有必需字段"""

    def test_servo_calibration_structure(self):
        cal = _DEFAULTS["servo_calibration"]
        assert "neutral_angle" in cal
        assert "on_offset" in cal
        assert "off_offset" in cal
        assert cal["neutral_angle"] == 90
        assert cal["on_offset"] == -30
        assert cal["off_offset"] == 30

    def test_dark_threshold(self):
        assert _DEFAULTS["dark_threshold"] == 150.0

    def test_light_conditions_structure(self):
        lc = _DEFAULTS["light_conditions"]
        assert "time_enabled" in lc
        assert "light_enabled" in lc
        assert "presence_enabled" in lc
        assert lc["time_enabled"] is True
        assert lc["light_enabled"] is True
        assert lc["presence_enabled"] is True

    def test_fallback_daytime_structure(self):
        fb = _DEFAULTS["fallback_daytime"]
        assert "start" in fb
        assert "end" in fb
        assert fb["start"] == "06:00"
        assert fb["end"] == "18:00"

    def test_ac_thresholds_structure(self):
        ac = _DEFAULTS["ac_thresholds"]
        assert "cooling" in ac
        assert "heating" in ac
        assert ac["cooling"] == 28.0
        assert ac["heating"] == 18.0

    def test_legacy_fields_preserved(self):
        assert _DEFAULTS["yolo_model"] == "yolov8n.pt"
        assert _DEFAULTS["detection_interval"] == 2.0
        assert _DEFAULTS["control_mode"] == "AUTO"


class TestDeepMerge:
    """验证 _deep_merge 递归合并逻辑"""

    def test_empty_overrides(self):
        result = _deep_merge(_DEFAULTS, {})
        assert result == _DEFAULTS

    def test_shallow_override(self):
        result = _deep_merge(_DEFAULTS, {"dark_threshold": 200.0})
        assert result["dark_threshold"] == 200.0
        # 其他字段保持默认
        assert result["yolo_model"] == "yolov8n.pt"

    def test_nested_partial_override(self):
        """旧配置只有部分嵌套字段时，新增字段应获得默认值"""
        old_data = {"servo_calibration": {"neutral_angle": 85}}
        result = _deep_merge(_DEFAULTS, old_data)
        # 用户设置的值保留
        assert result["servo_calibration"]["neutral_angle"] == 85
        # 新增字段获得默认值
        assert result["servo_calibration"]["on_offset"] == -30
        assert result["servo_calibration"]["off_offset"] == 30

    def test_nested_full_override(self):
        """完整覆盖嵌套字典"""
        overrides = {
            "ac_thresholds": {"cooling": 26.0, "heating": 20.0}
        }
        result = _deep_merge(_DEFAULTS, overrides)
        assert result["ac_thresholds"]["cooling"] == 26.0
        assert result["ac_thresholds"]["heating"] == 20.0

    def test_extra_keys_preserved(self):
        """用户配置中的额外键应保留"""
        overrides = {"custom_key": "custom_value"}
        result = _deep_merge(_DEFAULTS, overrides)
        assert result["custom_key"] == "custom_value"

    def test_old_servo_format_backward_compat(self):
        """旧格式 servo_calibration 应被新默认值补全"""
        old_data = {
            "servo_calibration": {
                "angle_on": 60,
                "angle_off": 120,
                "angle_neutral": 90,
                "action_duration": 0.5,
            }
        }
        result = _deep_merge(_DEFAULTS, old_data)
        # 旧字段保留
        assert result["servo_calibration"]["angle_on"] == 60
        # 新字段获得默认值
        assert result["servo_calibration"]["neutral_angle"] == 90
        assert result["servo_calibration"]["on_offset"] == -30
        assert result["servo_calibration"]["off_offset"] == 30


class TestLoadAll:
    """验证 _load_all 的向后兼容性"""

    def test_missing_file_returns_defaults(self, tmp_path):
        """配置文件不存在时返回默认值"""
        fake_path = tmp_path / "nonexistent.json"
        with patch("src.user_settings.SETTINGS_FILE", fake_path):
            result = _load_all()
        assert result["servo_calibration"]["neutral_angle"] == 90
        assert result["dark_threshold"] == 150.0
        assert result["light_conditions"]["time_enabled"] is True

    def test_corrupt_json_returns_defaults(self, tmp_path):
        """损坏的 JSON 文件应回退到默认值"""
        corrupt_file = tmp_path / "user_settings.json"
        corrupt_file.write_text("{ invalid json !!!", encoding="utf-8")
        with patch("src.user_settings.SETTINGS_FILE", corrupt_file):
            result = _load_all()
        assert result == _deep_merge(_DEFAULTS, {})

    def test_old_config_gets_new_defaults(self, tmp_path):
        """旧配置文件（缺少新字段）加载后应包含新字段的默认值"""
        old_config = {
            "yolo_model": "yolov8m.pt",
            "detection_interval": 3.0,
            "control_mode": "MANUAL",
            "servo_calibration": {
                "angle_on": 60,
                "angle_off": 120,
                "angle_neutral": 90,
                "action_duration": 0.5,
            },
        }
        config_file = tmp_path / "user_settings.json"
        config_file.write_text(json.dumps(old_config), encoding="utf-8")
        with patch("src.user_settings.SETTINGS_FILE", config_file):
            result = _load_all()

        # 旧值保留
        assert result["yolo_model"] == "yolov8m.pt"
        assert result["control_mode"] == "MANUAL"
        # 新字段获得默认值
        assert result["dark_threshold"] == 150.0
        assert result["light_conditions"]["time_enabled"] is True
        assert result["fallback_daytime"]["start"] == "06:00"
        assert result["ac_thresholds"]["cooling"] == 28.0
        # 旧 servo 字段保留，新字段补全
        assert result["servo_calibration"]["angle_on"] == 60
        assert result["servo_calibration"]["neutral_angle"] == 90

    def test_complete_config_loads_correctly(self, tmp_path):
        """完整配置文件正确加载"""
        full_config = {
            "yolo_model": "yolov8n.pt",
            "detection_interval": 2.0,
            "control_mode": "AUTO",
            "servo_calibration": {
                "neutral_angle": 85,
                "on_offset": -25,
                "off_offset": 35,
            },
            "dark_threshold": 200.0,
            "light_conditions": {
                "time_enabled": False,
                "light_enabled": True,
                "presence_enabled": False,
            },
            "fallback_daytime": {
                "start": "07:00",
                "end": "19:00",
            },
            "ac_thresholds": {
                "cooling": 26.0,
                "heating": 20.0,
            },
        }
        config_file = tmp_path / "user_settings.json"
        config_file.write_text(json.dumps(full_config), encoding="utf-8")
        with patch("src.user_settings.SETTINGS_FILE", config_file):
            result = _load_all()

        assert result["servo_calibration"]["neutral_angle"] == 85
        assert result["dark_threshold"] == 200.0
        assert result["light_conditions"]["time_enabled"] is False
        assert result["fallback_daytime"]["start"] == "07:00"
        assert result["ac_thresholds"]["cooling"] == 26.0
