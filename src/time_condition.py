"""
时间条件提供者模块 (src/time_condition.py)

基于日出日落时间判断当前是否为"需要照明的时段"。
通过 Sunrise-Sunset API 获取本地日出日落时间，每日调用一次并缓存结果。
API 不可达时使用用户配置的回退时间范围（默认 06:00-18:00）。

默认坐标为西安（34.26°N, 108.94°E）。
"""

from __future__ import annotations

import logging
from datetime import datetime, time, date
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Sunrise-Sunset API 端点（免费，无需 API Key）
_API_URL = "https://api.sunrise-sunset.org/json"

# 默认坐标：西安
_DEFAULT_LATITUDE = 34.26
_DEFAULT_LONGITUDE = 108.94

# 默认回退白天时间范围
_DEFAULT_FALLBACK_START = "06:00"
_DEFAULT_FALLBACK_END = "18:00"

# API 请求超时（秒）
_API_TIMEOUT = 10


def _parse_time_str(time_str: str) -> time:
    """解析 HH:MM 格式的时间字符串为 time 对象。"""
    parts = time_str.strip().split(":")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0
    return time(hour=hour, minute=minute)


class TimeConditionProvider:
    """日出日落时间条件提供者。

    判断当前是否为需要照明的时段（日出前或日落后）。
    每日从 Sunrise-Sunset API 获取一次日出日落时间并缓存。
    API 不可达时使用用户配置的回退时间范围。
    """

    def __init__(
        self,
        fallback_start: str = _DEFAULT_FALLBACK_START,
        fallback_end: str = _DEFAULT_FALLBACK_END,
        latitude: float = _DEFAULT_LATITUDE,
        longitude: float = _DEFAULT_LONGITUDE,
    ) -> None:
        """初始化时间条件提供者。

        Args:
            fallback_start: 回退白天开始时间（HH:MM），默认 "06:00"
            fallback_end: 回退白天结束时间（HH:MM），默认 "18:00"
            latitude: 纬度，默认西安 34.26
            longitude: 经度，默认西安 108.94
        """
        self._latitude = latitude
        self._longitude = longitude
        self._fallback_start = _parse_time_str(fallback_start)
        self._fallback_end = _parse_time_str(fallback_end)

        # 缓存的日出日落时间
        self._sunrise: Optional[time] = None
        self._sunset: Optional[time] = None
        self._cached_date: Optional[date] = None

    @property
    def sunrise(self) -> time:
        """当前缓存的日出时间。未缓存时返回回退开始时间。"""
        return self._sunrise if self._sunrise is not None else self._fallback_start

    @property
    def sunset(self) -> time:
        """当前缓存的日落时间。未缓存时返回回退结束时间。"""
        return self._sunset if self._sunset is not None else self._fallback_end

    def is_dark_period(self, now: Optional[datetime] = None) -> bool:
        """判断当前是否为需要照明的时段。

        当前时间在日出前或日落后时返回 True（需要照明）。
        当前时间在日出到日落之间时返回 False（自然光充足）。

        Args:
            now: 当前时间，默认使用系统当前时间。

        Returns:
            True 表示需要照明（天黑），False 表示自然光充足（天亮）。
        """
        if now is None:
            now = datetime.now()

        # 每日刷新一次日出日落时间
        today = now.date()
        if self._cached_date != today:
            self.refresh_sun_times(today)

        current_time = now.time()
        sunrise = self.sunrise
        sunset = self.sunset

        # 在日出到日落之间为白天（不需要照明）
        # 日出前或日落后为夜间（需要照明）
        if sunrise <= sunset:
            # 正常情况：日出在日落之前
            return current_time < sunrise or current_time >= sunset
        else:
            # 极端情况：日出在日落之后（极地等特殊情况）
            # 白天范围为 sunset ~ sunrise（跨午夜）
            return sunset <= current_time < sunrise

    def refresh_sun_times(self, target_date: Optional[date] = None) -> bool:
        """从 Sunrise-Sunset API 刷新日出日落时间。

        每日调用一次，结果缓存到当天结束。
        API 不可达时使用回退时间范围。

        Args:
            target_date: 目标日期，默认使用今天。

        Returns:
            True 表示成功从 API 获取，False 表示使用回退值。
        """
        if target_date is None:
            target_date = date.today()

        try:
            params = {
                "lat": self._latitude,
                "lng": self._longitude,
                "date": target_date.isoformat(),
                "formatted": 0,  # 使用 ISO 8601 格式
            }
            response = requests.get(_API_URL, params=params, timeout=_API_TIMEOUT)
            response.raise_for_status()

            data = response.json()
            if data.get("status") != "OK":
                raise ValueError(f"API 返回非 OK 状态: {data.get('status')}")

            results = data["results"]
            # API 返回 UTC 时间，格式如 "2024-01-15T06:30:00+00:00"
            sunrise_str = results["sunrise"]
            sunset_str = results["sunset"]

            # 解析 ISO 格式时间并转换为本地时间
            sunrise_dt = datetime.fromisoformat(sunrise_str).astimezone()
            sunset_dt = datetime.fromisoformat(sunset_str).astimezone()

            self._sunrise = sunrise_dt.time()
            self._sunset = sunset_dt.time()
            self._cached_date = target_date

            logger.info(
                "日出日落时间已更新: 日出 %s, 日落 %s",
                self._sunrise.strftime("%H:%M"),
                self._sunset.strftime("%H:%M"),
            )
            return True

        except (requests.RequestException, ValueError, KeyError, TypeError) as e:
            logger.warning("获取日出日落时间失败，使用回退值: %s", e)
            # 使用回退时间
            self._sunrise = self._fallback_start
            self._sunset = self._fallback_end
            self._cached_date = target_date
            return False

    def set_fallback(self, start: str, end: str) -> None:
        """更新回退白天时间范围。

        Args:
            start: 白天开始时间（HH:MM）
            end: 白天结束时间（HH:MM）
        """
        self._fallback_start = _parse_time_str(start)
        self._fallback_end = _parse_time_str(end)
        logger.debug("回退时间范围已更新: %s - %s", start, end)

    def set_coordinates(self, latitude: float, longitude: float) -> None:
        """更新坐标位置。

        Args:
            latitude: 纬度
            longitude: 经度
        """
        self._latitude = latitude
        self._longitude = longitude
        # 坐标变更后清除缓存，下次调用时重新获取
        self._cached_date = None
        logger.debug("坐标已更新: %.4f°N, %.4f°E", latitude, longitude)
