# -*- coding: utf-8 -*-
"""
核心抽象层 - 平台无关的基础类和工具

包含:
- MediaType: 媒体类型枚举
- MediaItem: 媒体项数据类
- PlatformAPIClient: 平台 API 客户端抽象基类
- MediaDownloader: 通用媒体下载器
- 平台注册和检测机制
"""

import asyncio
import hashlib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Type
from urllib.parse import urlparse

import aiofiles
import aiohttp
from tqdm import tqdm


class MediaType(Enum):
    """媒体类型枚举"""
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"

    @classmethod
    def from_string(cls, s: str) -> "MediaType":
        """从字符串转换"""
        mapping = {
            "image": cls.IMAGE,
            "images": cls.IMAGE,
            "video": cls.VIDEO,
            "videos": cls.VIDEO,
            "audio": cls.AUDIO,
        }
        return mapping.get(s.lower(), cls.IMAGE)

    @classmethod
    def parse_list(cls, s: str) -> List["MediaType"]:
        """解析逗号分隔的媒体类型列表"""
        types = []
        for part in s.split(","):
            part = part.strip().lower()
            if part:
                try:
                    types.append(cls.from_string(part))
                except (KeyError, ValueError):
                    pass
        return types if types else [cls.IMAGE, cls.VIDEO, cls.AUDIO]


@dataclass
class MediaItem:
    """媒体项数据类"""
    url: str
    media_type: MediaType
    post_id: str
    index: int = 0
    extension: str = ""
    width: int = 0
    height: int = 0
    duration: float = 0.0  # 视频/音频时长（秒）
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """自动推断扩展名"""
        if not self.extension:
            self.extension = self._infer_extension()

    def _infer_extension(self) -> str:
        """从 URL 推断文件扩展名"""
        parsed = urlparse(self.url)
        path_parts = parsed.path.split(".")
        if len(path_parts) > 1:
            ext = path_parts[-1].split("?")[0].lower()
            # 验证扩展名
            valid_exts = {
                MediaType.IMAGE: ["jpg", "jpeg", "png", "webp", "gif", "heic"],
                MediaType.VIDEO: ["mp4", "mov", "avi", "mkv", "webm", "m3u8"],
                MediaType.AUDIO: ["mp3", "m4a", "aac", "wav", "ogg", "flac"],
            }
            if ext in valid_exts.get(self.media_type, []):
                return ext
        # 默认扩展名
        defaults = {
            MediaType.IMAGE: "jpg",
            MediaType.VIDEO: "mp4",
            MediaType.AUDIO: "mp3",
        }
        return defaults.get(self.media_type, "bin")


# 平台注册表
PLATFORM_REGISTRY: Dict[str, Type["PlatformAPIClient"]] = {}


def register_platform(name: str, url_patterns: List[str] = None):
    """
    平台注册装饰器

    Args:
        name: 平台名称 (如 "instagram", "xiaohongshu")
        url_patterns: URL 匹配模式列表

    Example:
        @register_platform("instagram", ["instagram.com", "instagr.am"])
        class InstagramClient(PlatformAPIClient):
            ...
    """
    def decorator(cls: Type["PlatformAPIClient"]) -> Type["PlatformAPIClient"]:
        cls.PLATFORM_NAME = name
        cls.URL_PATTERNS = url_patterns or []
        PLATFORM_REGISTRY[name] = cls
        return cls
    return decorator


def detect_platform(url: str) -> Optional[str]:
    """
    从 URL 自动检测平台

    Args:
        url: 输入 URL

    Returns:
        平台名称，未识别返回 None
    """
    url_lower = url.lower()

    for name, client_cls in PLATFORM_REGISTRY.items():
        patterns = getattr(client_cls, "URL_PATTERNS", [])
        for pattern in patterns:
            if pattern.lower() in url_lower:
                return name

    return None


def get_platform_client(platform: str) -> Optional[Type["PlatformAPIClient"]]:
    """
    获取平台客户端类

    Args:
        platform: 平台名称

    Returns:
        平台客户端类，未找到返回 None
    """
    return PLATFORM_REGISTRY.get(platform.lower())


class PlatformAPIClient(ABC):
    """
    平台 API 客户端抽象基类

    所有平台实现都需要继承此类并实现抽象方法。
    """

    PLATFORM_NAME: str = ""
    URL_PATTERNS: List[str] = []

    def __init__(
        self,
        api_key: str,
        base_urls: List[str] = None,
        api_semaphore: int = 5,
        backup_api_keys: List[str] = None
    ):
        """
        初始化客户端

        Args:
            api_key: TikHub API 密钥
            base_urls: API 基础 URL 列表（支持故障转移）
            api_semaphore: API 并发限制
            backup_api_keys: 备用 API 密钥列表（当主密钥返回 402 时自动切换）
        """
        self.api_keys = [api_key] + (backup_api_keys or [])
        self.current_key_index = 0
        self.base_urls = base_urls or [
            "https://api.tikhub.dev",
            "https://api.tikhub.io"
        ]
        self.session: Optional[aiohttp.ClientSession] = None
        self._sem = asyncio.Semaphore(api_semaphore)

    @property
    def api_key(self) -> str:
        """获取当前使用的 API 密钥"""
        return self.api_keys[self.current_key_index]

    def _switch_to_backup_key(self) -> bool:
        """
        切换到备用 API 密钥

        Returns:
            是否成功切换（还有可用的备用密钥）
        """
        if self.current_key_index < len(self.api_keys) - 1:
            self.current_key_index += 1
            key_preview = self.api_key[:8] + "..."
            print(f"🔄 切换到备用 API Key: {key_preview}")
            return True
        return False

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=120)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _build_headers(self) -> Dict[str, str]:
        """构建请求头"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        }

    async def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET"
    ) -> Optional[Dict[str, Any]]:
        """
        发起 API 请求，支持多 base URL 故障转移和 API Key 自动切换

        Args:
            endpoint: API 端点路径
            params: 查询参数
            method: HTTP 方法

        Returns:
            响应数据，失败返回 None
        """
        if not self.session:
            raise RuntimeError("Session not initialized. Use 'async with' context manager.")

        # 尝试当前 API Key 和所有备用 Key
        while True:
            headers = self._build_headers()
            needs_key_switch = False

            for base_url in self.base_urls:
                url = f"{base_url.rstrip('/')}{endpoint}"
                try:
                    async with self._sem:
                        if method.upper() == "GET":
                            async with self.session.get(url, headers=headers, params=params) as resp:
                                result, needs_key_switch = await self._handle_response(resp, base_url)
                        elif method.upper() == "POST":
                            async with self.session.post(url, headers=headers, json=params) as resp:
                                result, needs_key_switch = await self._handle_response(resp, base_url)
                        else:
                            result, needs_key_switch = None, False

                        if result is not None:
                            return result

                        # 如果需要切换 API Key，跳出 base_url 循环
                        if needs_key_switch:
                            break

                except asyncio.TimeoutError:
                    print(f"⚠️  请求超时 [{base_url}]")
                    continue
                except aiohttp.ClientError as e:
                    print(f"⚠️  请求异常 [{base_url}]: {e}")
                    continue
                except Exception as e:
                    print(f"⚠️  未知异常 [{base_url}]: {e}")
                    continue

            # 如果需要切换 API Key
            if needs_key_switch:
                if self._switch_to_backup_key():
                    # 成功切换，用新 Key 重试
                    continue
                else:
                    # 没有更多备用 Key
                    print("❌ 所有 API Key 额度已耗尽")
                    return None
            else:
                # 不需要切换 Key，请求结束
                return None

    async def _handle_response(
        self,
        resp: aiohttp.ClientResponse,
        base_url: str
    ) -> Tuple[Optional[Dict[str, Any]], bool]:
        """
        处理 API 响应

        Returns:
            (响应数据, 是否需要切换 API Key)
        """
        if resp.status == 200:
            data = await resp.json()
            # TikHub API 统一格式
            if data.get("code") == 200:
                return data, False
            else:
                msg = data.get("message", "未知错误")
                print(f"⚠️  API 错误: {msg}")
                return None, False
        elif resp.status == 402:
            # 402 Payment Required - 需要切换 API Key
            print(f"⚠️  HTTP {resp.status} [{base_url}]")
            return None, True
        else:
            print(f"⚠️  HTTP {resp.status} [{base_url}]")
            return None, False

    @abstractmethod
    def extract_username_from_url(self, url: str) -> Optional[str]:
        """
        从 URL 提取用户名

        Args:
            url: 平台主页 URL

        Returns:
            用户名，无法提取返回 None
        """
        pass

    @abstractmethod
    async def get_user_posts(
        self,
        profile_url: str,
        max_posts: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        获取用户帖子列表

        Args:
            profile_url: 用户主页 URL
            max_posts: 最大帖子数，None 表示全部

        Returns:
            帖子列表
        """
        pass

    @abstractmethod
    def extract_media_from_post(
        self,
        post: Dict[str, Any],
        media_types: List[MediaType] = None
    ) -> List[MediaItem]:
        """
        从帖子中提取媒体项

        Args:
            post: 帖子数据
            media_types: 要提取的媒体类型，None 表示全部

        Returns:
            媒体项列表
        """
        pass

    def clean_url(self, url: str) -> str:
        """
        清理 URL（移除查询参数等）

        默认实现，子类可覆盖
        """
        if '?' in url:
            url = url.split('?')[0]
        if not url.endswith('/'):
            url += '/'
        return url


class MediaDownloader:
    """
    通用媒体下载器

    支持图片、视频、音频的并发下载，具备:
    - 内容去重（MD5）
    - 增量下载（跳过已存在）
    - 并发控制
    """

    def __init__(
        self,
        output_dir: Path,
        max_concurrent: int = 10,
        skip_existing: bool = True
    ):
        """
        初始化下载器

        Args:
            output_dir: 输出根目录
            max_concurrent: 最大并发数
            skip_existing: 是否跳过已存在文件
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._sem = asyncio.Semaphore(max_concurrent)
        self.skip_existing = skip_existing
        self.session: Optional[aiohttp.ClientSession] = None
        self.downloaded_hashes: Set[str] = set()

        # 统计信息
        self.stats = {
            "total": 0,
            "success": 0,
            "skipped": 0,
            "duplicate": 0,
            "failed": 0
        }

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=300)  # 视频可能较大
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _get_file_hash(self, data: bytes) -> str:
        """计算内容 MD5 哈希"""
        return hashlib.md5(data).hexdigest()

    def _get_output_path(
        self,
        platform: str,
        username: str,
        item: MediaItem
    ) -> Path:
        """
        生成输出文件路径

        格式: output/{platform}/{username}/{post_id}_{index}.{ext}
        """
        # 创建目录结构
        user_dir = self.output_dir / platform / username
        user_dir.mkdir(parents=True, exist_ok=True)

        # 文件名
        filename = f"{item.post_id}_{item.index:02d}.{item.extension}"
        return user_dir / filename

    async def download_item(
        self,
        platform: str,
        username: str,
        item: MediaItem
    ) -> Tuple[bool, str]:
        """
        下载单个媒体项

        Args:
            platform: 平台名称
            username: 用户名
            item: 媒体项

        Returns:
            (成功标志, 消息)
        """
        self.stats["total"] += 1
        output_path = self._get_output_path(platform, username, item)

        # 跳过已存在文件
        if self.skip_existing and output_path.exists():
            self.stats["skipped"] += 1
            return True, f"跳过: {output_path.name}"

        if not self.session:
            self.stats["failed"] += 1
            return False, "Session 未初始化"

        async with self._sem:
            try:
                async with self.session.get(item.url) as resp:
                    resp.raise_for_status()
                    data = await resp.read()

                # 内容去重
                file_hash = self._get_file_hash(data)
                if file_hash in self.downloaded_hashes:
                    self.stats["duplicate"] += 1
                    return True, f"重复: {output_path.name}"

                # 保存文件
                async with aiofiles.open(output_path, "wb") as f:
                    await f.write(data)

                self.downloaded_hashes.add(file_hash)
                self.stats["success"] += 1
                return True, f"✓ {output_path.name}"

            except aiohttp.ClientResponseError as e:
                self.stats["failed"] += 1
                return False, f"✗ HTTP {e.status}: {output_path.name}"
            except asyncio.TimeoutError:
                self.stats["failed"] += 1
                return False, f"✗ 超时: {output_path.name}"
            except Exception as e:
                self.stats["failed"] += 1
                return False, f"✗ {output_path.name}: {str(e)[:50]}"

    async def download_batch(
        self,
        platform: str,
        username: str,
        items: List[MediaItem],
        progress_desc: str = "下载中"
    ) -> List[Tuple[bool, str]]:
        """
        批量下载媒体项

        Args:
            platform: 平台名称
            username: 用户名
            items: 媒体项列表
            progress_desc: 进度条描述

        Returns:
            结果列表 [(成功标志, 消息), ...]
        """
        if not items:
            return []

        tasks = [
            self.download_item(platform, username, item)
            for item in items
        ]

        results = []
        with tqdm(total=len(tasks), desc=progress_desc, leave=False) as pbar:
            for coro in asyncio.as_completed(tasks):
                result = await coro
                results.append(result)
                pbar.update(1)

        return results

    def get_stats_summary(self) -> str:
        """获取统计摘要"""
        return (
            f"总计: {self.stats['total']} | "
            f"成功: {self.stats['success']} | "
            f"跳过: {self.stats['skipped']} | "
            f"重复: {self.stats['duplicate']} | "
            f"失败: {self.stats['failed']}"
        )

    def reset_stats(self):
        """重置统计"""
        for key in self.stats:
            self.stats[key] = 0
