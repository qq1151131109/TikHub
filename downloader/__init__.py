# -*- coding: utf-8 -*-
"""
TikHub 多平台下载器核心模块

支持平台：
- Instagram
- 小红书 (Xiaohongshu)
- 抖音 (Douyin)
- TikTok
- YouTube
- Twitter
- Bilibili
- 更多...
"""

from .core import (
    MediaType,
    MediaItem,
    PlatformAPIClient,
    MediaDownloader,
    get_platform_client,
    detect_platform,
    PLATFORM_REGISTRY,
)

from .platforms import (
    InstagramClient,
    XiaohongshuClient,
)

__all__ = [
    # Core
    "MediaType",
    "MediaItem",
    "PlatformAPIClient",
    "MediaDownloader",
    "get_platform_client",
    "detect_platform",
    "PLATFORM_REGISTRY",
    # Platforms
    "InstagramClient",
    "XiaohongshuClient",
]

__version__ = "2.0.0"
