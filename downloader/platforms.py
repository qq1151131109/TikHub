# -*- coding: utf-8 -*-
"""
平台实现模块

包含各个平台的 API 客户端实现:
- Instagram
- 小红书 (Xiaohongshu)
- 更多平台将陆续添加...
"""

import re
from typing import Any, Dict, List, Optional

import aiohttp

from .core import (
    MediaItem,
    MediaType,
    PlatformAPIClient,
    register_platform,
)


@register_platform("instagram", [
    "instagram.com",
    "instagr.am",
    "www.instagram.com"
])
class InstagramClient(PlatformAPIClient):
    """
    Instagram 平台客户端

    使用 TikHub API 获取 Instagram 数据
    """

    def extract_username_from_url(self, url: str) -> Optional[str]:
        """从 Instagram URL 提取用户名"""
        try:
            url = self.clean_url(url)
            # https://www.instagram.com/username/ 或 /username/reels/
            path = url.split("//", 1)[-1]
            path = path.split("/", 1)[-1]  # 去掉域名
            parts = [p for p in path.split("/") if p]
            if parts and parts[0] not in ["p", "reel", "stories", "explore"]:
                return parts[0]
        except Exception:
            pass
        return None

    async def get_user_posts(
        self,
        profile_url: str,
        max_posts: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """获取用户帖子列表"""
        username = self.extract_username_from_url(profile_url)
        if not username:
            print(f"❌ 无法从 URL 提取用户名: {profile_url}")
            return []

        try:
            # 1. 获取用户 ID
            user_info = await self._make_request(
                "/api/v1/instagram/v1/fetch_user_info_by_username",
                params={"username": username}
            )

            if not user_info:
                print(f"❌ 无法获取用户信息: {username}")
                return []

            # TikHub API v1 格式
            user_id = (user_info.get("data", {})
                      .get("data", {})
                      .get("user", {})
                      .get("id"))
            if not user_id:
                print(f"❌ 用户 ID 不存在: {username}")
                return []

            # 2. 分页获取帖子
            all_posts = []
            max_id = None
            has_more = True

            while has_more:
                params = {
                    "user_id": user_id,
                    "count": 12
                }
                if max_id:
                    params["max_id"] = max_id

                posts_data = await self._make_request(
                    "/api/v1/instagram/v1/fetch_user_posts",
                    params=params
                )

                if not posts_data:
                    break

                items = posts_data.get("data", {}).get("items", [])
                for item in items:
                    all_posts.append(item)
                    max_id = item.get("id")

                has_more = posts_data.get("data", {}).get("more_available", False)

                if max_posts and len(all_posts) >= max_posts:
                    all_posts = all_posts[:max_posts]
                    break

                if not has_more or not items:
                    break

            return all_posts

        except Exception as e:
            print(f"❌ 获取帖子失败: {e}")
            return []

    def extract_media_from_post(
        self,
        post: Dict[str, Any],
        media_types: List[MediaType] = None
    ) -> List[MediaItem]:
        """从帖子提取媒体"""
        if media_types is None:
            media_types = [MediaType.IMAGE, MediaType.VIDEO]

        items = []
        post_id = post.get("code") or post.get("id") or "unknown"

        def get_best_image_url(item: Dict) -> Optional[str]:
            """获取最佳图片 URL"""
            candidates = item.get("image_versions2", {}).get("candidates", [])
            if candidates:
                best = max(candidates, key=lambda c: c.get("width", 0) * c.get("height", 0))
                return best.get("url")
            return None

        def get_best_video_url(item: Dict) -> Optional[Dict]:
            """获取最佳视频 URL 和信息"""
            video_versions = item.get("video_versions", [])
            if video_versions:
                best = max(video_versions, key=lambda v: v.get("width", 0) * v.get("height", 0))
                return {
                    "url": best.get("url"),
                    "width": best.get("width", 0),
                    "height": best.get("height", 0)
                }
            return None

        # 处理轮播帖子
        carousel_media = post.get("carousel_media", [])
        if carousel_media:
            for idx, media in enumerate(carousel_media):
                media_type_code = media.get("media_type", 0)

                # 图片 (media_type == 1)
                if media_type_code == 1 and MediaType.IMAGE in media_types:
                    url = get_best_image_url(media)
                    if url:
                        items.append(MediaItem(
                            url=url,
                            media_type=MediaType.IMAGE,
                            post_id=post_id,
                            index=idx
                        ))

                # 视频 (media_type == 2)
                elif media_type_code == 2 and MediaType.VIDEO in media_types:
                    video_info = get_best_video_url(media)
                    if video_info and video_info.get("url"):
                        items.append(MediaItem(
                            url=video_info["url"],
                            media_type=MediaType.VIDEO,
                            post_id=post_id,
                            index=idx,
                            width=video_info.get("width", 0),
                            height=video_info.get("height", 0),
                            duration=media.get("video_duration", 0)
                        ))
        else:
            # 单个媒体帖子
            media_type_code = post.get("media_type", 0)

            if media_type_code == 1 and MediaType.IMAGE in media_types:
                url = get_best_image_url(post)
                if url:
                    items.append(MediaItem(
                        url=url,
                        media_type=MediaType.IMAGE,
                        post_id=post_id,
                        index=0
                    ))

            elif media_type_code == 2 and MediaType.VIDEO in media_types:
                video_info = get_best_video_url(post)
                if video_info and video_info.get("url"):
                    items.append(MediaItem(
                        url=video_info["url"],
                        media_type=MediaType.VIDEO,
                        post_id=post_id,
                        index=0,
                        width=video_info.get("width", 0),
                        height=video_info.get("height", 0),
                        duration=post.get("video_duration", 0)
                    ))

        return items


@register_platform("xiaohongshu", [
    "xiaohongshu.com",
    "xhslink.com",
    "www.xiaohongshu.com"
])
class XiaohongshuClient(PlatformAPIClient):
    """
    小红书平台客户端

    使用 TikHub API 获取小红书数据

    支持两种链接类型:
    1. 用户主页: xiaohongshu.com/user/profile/xxx -> 下载用户所有笔记
    2. 笔记分享: xhslink.com/m/xxx -> 只下载该条笔记
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cached_username = None  # 缓存从 API 获取的用户名

    def extract_username_from_url(self, url: str) -> Optional[str]:
        """从小红书 URL 提取用户 ID"""
        # 如果有缓存的用户名，直接返回
        if self._cached_username:
            return self._cached_username

        try:
            # 格式: https://www.xiaohongshu.com/user/profile/xxx
            if "/user/profile/" in url:
                match = re.search(r'/user/profile/([a-zA-Z0-9]+)', url)
                if match:
                    return match.group(1)

            # 短链接返回 None，需要通过 API 解析后设置 _cached_username
            if "xhslink.com" in url:
                return None

        except Exception:
            pass
        return None

    def _is_short_link(self, url: str) -> bool:
        """判断是否是短链接"""
        return "xhslink.com" in url

    async def _resolve_short_link(self, short_url: str) -> Optional[str]:
        """
        解析短链接，返回完整 URL

        短链接可能重定向到:
        - 用户主页: /user/profile/xxx
        - 单条笔记: /explore/xxx 或 /discovery/item/xxx
        """
        try:
            # 使用 aiohttp 跟随重定向
            if self.session:
                async with self.session.get(short_url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    final_url = str(resp.url)
                    print(f"  📍 短链接解析: {final_url[:60]}...")
                    return final_url
        except Exception as e:
            print(f"  ⚠️  短链接解析失败: {e}")

        return None

    def _extract_user_id_from_url(self, url: str) -> Optional[str]:
        """从完整 URL 提取用户 ID"""
        # /user/profile/xxx
        match = re.search(r'/user/profile/([a-zA-Z0-9]+)', url)
        if match:
            return match.group(1)
        return None

    def _extract_note_id_from_url(self, url: str) -> Optional[str]:
        """从完整 URL 提取笔记 ID"""
        # /explore/xxx 或 /discovery/item/xxx
        patterns = [
            r'/explore/([a-zA-Z0-9]+)',
            r'/discovery/item/([a-zA-Z0-9]+)',
            r'/note/([a-zA-Z0-9]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def _is_user_profile_url(self, url: str) -> bool:
        """判断是否是用户主页 URL"""
        return "/user/profile/" in url

    async def _fetch_note_by_id(self, note_id: str) -> Optional[Dict[str, Any]]:
        """通过笔记 ID 获取笔记详情"""
        endpoints = [
            "/api/v1/xiaohongshu/web/get_note_info",
            "/api/v1/xiaohongshu/app/get_note_info",
        ]

        for endpoint in endpoints:
            try:
                data = await self._make_request(
                    endpoint,
                    params={"note_id": note_id}
                )
                if data and data.get("data"):
                    return data.get("data")
            except Exception:
                continue

        return None

    async def get_user_posts(
        self,
        profile_url: str,
        max_posts: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """获取笔记列表（用户主页或单条笔记）"""

        resolved_url = profile_url
        user_id = None

        # 如果是短链接，先解析
        if self._is_short_link(profile_url):
            resolved_url = await self._resolve_short_link(profile_url)
            if not resolved_url:
                print(f"❌ 无法解析短链接: {profile_url}")
                return []

        # 检查解析后的 URL 类型
        if self._is_user_profile_url(resolved_url):
            # 用户主页 - 获取用户所有笔记
            user_id = self._extract_user_id_from_url(resolved_url)
            if user_id:
                self._cached_username = user_id  # 缓存用户 ID 作为用户名
        else:
            # 可能是笔记链接
            note_id = self._extract_note_id_from_url(resolved_url)
            if note_id:
                note_data = await self._fetch_note_by_id(note_id)
                if note_data:
                    note_info = note_data.get("note_info") or note_data.get("note") or note_data
                    user_info = note_info.get("user", {})
                    self._cached_username = user_info.get("nickname") or user_info.get("user_id") or "xhs_user"
                    return [note_info]

            # 如果还是无法识别，尝试从 URL 提取用户 ID
            user_id = self._extract_user_id_from_url(resolved_url) or self.extract_username_from_url(resolved_url)

        if not user_id:
            print(f"❌ 无法获取用户 ID: {profile_url}")
            return []

        # 获取用户笔记列表
        try:
            all_posts = []
            cursor = ""
            has_more = True
            use_app_endpoint = True  # 优先使用 app 端点（更稳定）

            while has_more:
                posts_data = None

                if use_app_endpoint:
                    # 使用 app 端点
                    posts_data = await self._make_request(
                        "/api/v1/xiaohongshu/app/get_user_notes",
                        params={"user_id": user_id, "cursor": cursor} if cursor else {"user_id": user_id}
                    )

                if not posts_data:
                    # 尝试 web 端点
                    posts_data = await self._make_request(
                        "/api/v1/xiaohongshu/web/get_user_notes",
                        params={"user_id": user_id, "lastCursor": cursor} if cursor else {"user_id": user_id}
                    )

                if not posts_data:
                    break

                # 处理嵌套的数据结构
                # 可能是 data.notes 或 data.data.notes
                data = posts_data.get("data", {})
                if isinstance(data.get("data"), dict):
                    # 嵌套结构: data.data.notes
                    data = data.get("data", {})

                notes = data.get("notes", [])

                for note in notes:
                    all_posts.append(note)
                    # 从第一个笔记中提取用户名（如果尚未缓存）
                    if not self._cached_username or self._cached_username == user_id:
                        user_info = note.get("user", {})
                        nickname = user_info.get("nickname") or user_info.get("nick_name")
                        if nickname:
                            self._cached_username = nickname

                cursor = data.get("cursor", "") or data.get("lastCursor", "")
                has_more = data.get("has_more", False)

                if max_posts and len(all_posts) >= max_posts:
                    all_posts = all_posts[:max_posts]
                    break

                if not has_more or not notes:
                    break

            return all_posts

        except Exception as e:
            print(f"❌ 获取笔记失败: {e}")
            return []

    def extract_media_from_post(
        self,
        post: Dict[str, Any],
        media_types: List[MediaType] = None
    ) -> List[MediaItem]:
        """从笔记提取媒体"""
        if media_types is None:
            media_types = [MediaType.IMAGE, MediaType.VIDEO]

        items = []
        note_id = post.get("note_id") or post.get("id") or post.get("note_info", {}).get("note_id") or "unknown"
        note_type = post.get("type") or post.get("note_type", "normal")

        # 标准化类型
        if note_type in ["normal", "image", "1"]:
            note_type = "image"
        elif note_type in ["video", "2"]:
            note_type = "video"

        # 图片笔记
        if note_type == "image" and MediaType.IMAGE in media_types:
            # 尝试多种图片列表格式
            image_list = (
                post.get("image_list") or
                post.get("images_list") or
                post.get("note_info", {}).get("image_list") or
                []
            )
            for idx, img in enumerate(image_list):
                # 优先使用原图
                url = None
                # 格式1: info_list[].url
                info_list = img.get("info_list", [])
                if info_list:
                    # 选择最大尺寸
                    best_info = max(info_list, key=lambda x: x.get("width", 0) * x.get("height", 0), default={})
                    url = best_info.get("url")

                # 格式2: 直接 url 字段
                if not url:
                    url = (img.get("url_size_large") or
                           img.get("url_default") or
                           img.get("url"))

                if url:
                    items.append(MediaItem(
                        url=url,
                        media_type=MediaType.IMAGE,
                        post_id=note_id,
                        index=idx,
                        width=img.get("width", 0),
                        height=img.get("height", 0)
                    ))

        # 视频笔记
        if note_type == "video" and MediaType.VIDEO in media_types:
            video_info = (
                post.get("video") or
                post.get("video_info") or
                post.get("note_info", {}).get("video") or
                {}
            )
            if video_info:
                # 尝试多种视频 URL 格式
                url = None

                # 格式1: media.stream.h264[]
                media = video_info.get("media", {})
                stream = media.get("stream", {})
                h264_list = stream.get("h264", [])
                if h264_list:
                    # 选择最高质量
                    best = max(h264_list, key=lambda x: x.get("width", 0) * x.get("height", 0), default={})
                    url = best.get("master_url") or best.get("backup_urls", [None])[0]

                # 格式2: 直接 URL 字段
                if not url:
                    url = (video_info.get("url") or
                           video_info.get("h264_720p", {}).get("url") or
                           video_info.get("h264_480p", {}).get("url") or
                           video_info.get("h264_360p", {}).get("url"))

                if url:
                    items.append(MediaItem(
                        url=url,
                        media_type=MediaType.VIDEO,
                        post_id=note_id,
                        index=0,
                        duration=video_info.get("duration", 0) / 1000 if video_info.get("duration", 0) > 1000 else video_info.get("duration", 0)
                    ))

        return items

    def clean_url(self, url: str) -> str:
        """清理小红书 URL"""
        return url.strip()


@register_platform("douyin", [
    "douyin.com",
    "www.douyin.com",
    "v.douyin.com",
    "iesdouyin.com"
])
class DouyinClient(PlatformAPIClient):
    """
    抖音平台客户端

    使用 TikHub API 获取抖音数据
    支持:
    - 用户主页: douyin.com/user/xxx
    - 分享链接: v.douyin.com/xxx
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cached_username = None
        self._cached_sec_user_id = None

    def extract_username_from_url(self, url: str) -> Optional[str]:
        """从抖音 URL 提取用户标识"""
        if self._cached_username:
            return self._cached_username

        try:
            url = self.clean_url(url)

            # 格式1: https://www.douyin.com/user/MS4wLjABxxx
            match = re.search(r'/user/([A-Za-z0-9_-]+)', url)
            if match:
                return match.group(1)

            # 格式2: 抖音号 unique_id
            match = re.search(r'unique_id=([^&]+)', url)
            if match:
                return match.group(1)

        except Exception:
            pass
        return None

    async def _resolve_short_link(self, short_url: str) -> Optional[str]:
        """解析抖音短链接"""
        try:
            if self.session:
                async with self.session.get(short_url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    final_url = str(resp.url)
                    print(f"  📍 短链接解析: {final_url[:60]}...")
                    return final_url
        except Exception as e:
            print(f"  ⚠️  短链接解析失败: {e}")
        return None

    async def _get_sec_user_id(self, identifier: str) -> Optional[str]:
        """获取用户的 sec_user_id"""
        # 如果已经是 sec_user_id 格式
        if identifier.startswith("MS4wLjA"):
            return identifier

        # 通过 unique_id (抖音号) 获取
        data = await self._make_request(
            "/api/v1/douyin/web/fetch_user_info_by_unique_id",
            params={"unique_id": identifier}
        )
        if data:
            user_info = data.get("data", {}).get("user", {})
            return user_info.get("sec_uid")

        return None

    async def get_user_posts(
        self,
        profile_url: str,
        max_posts: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """获取用户作品列表"""
        resolved_url = profile_url

        # 处理短链接
        if "v.douyin.com" in profile_url or "iesdouyin.com" in profile_url:
            resolved_url = await self._resolve_short_link(profile_url)
            if not resolved_url:
                print(f"❌ 无法解析短链接: {profile_url}")
                return []

        # 提取用户标识
        user_id = self.extract_username_from_url(resolved_url)
        if not user_id:
            print(f"❌ 无法从 URL 提取用户 ID: {profile_url}")
            return []

        try:
            # 获取 sec_user_id
            sec_user_id = await self._get_sec_user_id(user_id)
            if not sec_user_id:
                # 尝试直接使用
                sec_user_id = user_id

            self._cached_sec_user_id = sec_user_id

            # 获取用户信息
            user_info_data = await self._make_request(
                "/api/v1/douyin/web/fetch_user_info_by_sec_user_id",
                params={"sec_user_id": sec_user_id}
            )
            if user_info_data:
                user = user_info_data.get("data", {}).get("user", {})
                self._cached_username = user.get("nickname") or user.get("unique_id") or user_id

            print(f"👤 用户: {self._cached_username}")

            # 分页获取作品
            all_posts = []
            max_cursor = 0
            has_more = True

            while has_more:
                posts_data = await self._make_request(
                    "/api/v1/douyin/web/fetch_user_post",
                    params={
                        "sec_user_id": sec_user_id,
                        "max_cursor": max_cursor,
                        "count": 20
                    }
                )

                if not posts_data:
                    break

                data = posts_data.get("data", {})
                aweme_list = data.get("aweme_list", [])

                for aweme in aweme_list:
                    all_posts.append(aweme)

                max_cursor = data.get("max_cursor", 0)
                has_more = data.get("has_more", False)

                if max_posts and len(all_posts) >= max_posts:
                    all_posts = all_posts[:max_posts]
                    break

                if not has_more or not aweme_list:
                    break

            return all_posts

        except Exception as e:
            print(f"❌ 获取作品失败: {e}")
            return []

    def extract_media_from_post(
        self,
        post: Dict[str, Any],
        media_types: List[MediaType] = None
    ) -> List[MediaItem]:
        """从抖音作品提取媒体"""
        if media_types is None:
            media_types = [MediaType.IMAGE, MediaType.VIDEO]

        items = []
        aweme_id = post.get("aweme_id") or post.get("id") or "unknown"
        aweme_type = post.get("aweme_type", 0)

        # 图集 (aweme_type == 2 或 68)
        if aweme_type in [2, 68] and MediaType.IMAGE in media_types:
            images = post.get("images", [])
            for idx, img in enumerate(images):
                url_list = img.get("url_list", [])
                if url_list:
                    url = url_list[0]  # 使用第一个 URL
                    items.append(MediaItem(
                        url=url,
                        media_type=MediaType.IMAGE,
                        post_id=aweme_id,
                        index=idx,
                        width=img.get("width", 0),
                        height=img.get("height", 0)
                    ))

        # 视频 (aweme_type == 0 或其他)
        if aweme_type not in [2, 68] and MediaType.VIDEO in media_types:
            video = post.get("video", {})
            play_addr = video.get("play_addr", {})
            url_list = play_addr.get("url_list", [])

            if url_list:
                # 优先使用无水印地址
                url = url_list[0]
                # 尝试获取无水印版本
                bit_rate = video.get("bit_rate", [])
                if bit_rate:
                    best = max(bit_rate, key=lambda x: x.get("bit_rate", 0))
                    play_addr = best.get("play_addr", {})
                    if play_addr.get("url_list"):
                        url = play_addr["url_list"][0]

                items.append(MediaItem(
                    url=url,
                    media_type=MediaType.VIDEO,
                    post_id=aweme_id,
                    index=0,
                    width=video.get("width", 0),
                    height=video.get("height", 0),
                    duration=video.get("duration", 0) / 1000
                ))

        return items


@register_platform("tiktok", [
    "tiktok.com",
    "www.tiktok.com",
    "vm.tiktok.com",
    "vt.tiktok.com"
])
class TikTokClient(PlatformAPIClient):
    """
    TikTok 平台客户端

    使用 TikHub API 获取 TikTok 数据
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cached_username = None
        self._cached_sec_uid = None

    def extract_username_from_url(self, url: str) -> Optional[str]:
        """从 TikTok URL 提取用户名"""
        if self._cached_username:
            return self._cached_username

        try:
            url = self.clean_url(url)

            # 格式1: https://www.tiktok.com/@username
            match = re.search(r'tiktok\.com/@([^/?]+)', url)
            if match:
                return match.group(1)

        except Exception:
            pass
        return None

    async def _resolve_short_link(self, short_url: str) -> Optional[str]:
        """解析 TikTok 短链接"""
        try:
            if self.session:
                async with self.session.get(short_url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    final_url = str(resp.url)
                    print(f"  📍 短链接解析: {final_url[:60]}...")
                    return final_url
        except Exception as e:
            print(f"  ⚠️  短链接解析失败: {e}")
        return None

    async def get_user_posts(
        self,
        profile_url: str,
        max_posts: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """获取用户作品列表"""
        resolved_url = profile_url

        # 处理短链接
        if "vm.tiktok.com" in profile_url or "vt.tiktok.com" in profile_url:
            resolved_url = await self._resolve_short_link(profile_url)
            if not resolved_url:
                print(f"❌ 无法解析短链接: {profile_url}")
                return []

        # 提取用户名
        username = self.extract_username_from_url(resolved_url)
        if not username:
            print(f"❌ 无法从 URL 提取用户名: {profile_url}")
            return []

        try:
            # 获取用户信息 - 尝试多个端点
            user_info_data = None
            sec_uid = None

            # 尝试不同的 API 端点格式
            endpoints = [
                "/api/v1/tiktok/web/fetch_user_profile",
                "/api/v1/tiktok/app/v3/fetch_user_profile",
            ]

            for endpoint in endpoints:
                user_info_data = await self._make_request(
                    endpoint,
                    params={"uniqueId": username}
                )
                if user_info_data:
                    break

            if not user_info_data:
                print(f"❌ 无法获取用户信息: {username}")
                return []

            # 解析用户信息
            data = user_info_data.get("data", {})
            user_info = data.get("userInfo", data)
            user = user_info.get("user", data.get("user", {}))
            sec_uid = user.get("secUid") or user.get("sec_uid")
            self._cached_username = user.get("nickname") or user.get("uniqueId") or username
            self._cached_sec_uid = sec_uid

            print(f"👤 用户: {self._cached_username}")

            if not sec_uid:
                print(f"❌ 无法获取 sec_uid: {username}")
                return []

            # 分页获取作品
            all_posts = []
            cursor = "0"
            has_more = True

            while has_more:
                # 尝试不同的帖子列表端点
                posts_data = await self._make_request(
                    "/api/v1/tiktok/web/fetch_user_post",
                    params={
                        "secUid": sec_uid,
                        "cursor": cursor,
                        "count": 30
                    }
                )

                if not posts_data:
                    posts_data = await self._make_request(
                        "/api/v1/tiktok/app/v3/fetch_user_post",
                        params={
                            "sec_user_id": sec_uid,
                            "max_cursor": int(cursor) if cursor.isdigit() else 0,
                            "count": 30
                        }
                    )

                if not posts_data:
                    break

                data = posts_data.get("data", {})
                item_list = data.get("itemList", data.get("aweme_list", []))

                for item in item_list:
                    all_posts.append(item)

                cursor = str(data.get("cursor", data.get("max_cursor", "0")))
                has_more = data.get("hasMore", data.get("has_more", False))

                if max_posts and len(all_posts) >= max_posts:
                    all_posts = all_posts[:max_posts]
                    break

                if not has_more or not item_list:
                    break

            return all_posts

        except Exception as e:
            print(f"❌ 获取作品失败: {e}")
            return []

    def extract_media_from_post(
        self,
        post: Dict[str, Any],
        media_types: List[MediaType] = None
    ) -> List[MediaItem]:
        """从 TikTok 作品提取媒体"""
        if media_types is None:
            media_types = [MediaType.IMAGE, MediaType.VIDEO]

        items = []
        video_id = post.get("id") or "unknown"

        # 图集模式
        image_post = post.get("imagePost", {})
        if image_post and MediaType.IMAGE in media_types:
            images = image_post.get("images", [])
            for idx, img in enumerate(images):
                url_list = img.get("imageURL", {}).get("urlList", [])
                if url_list:
                    items.append(MediaItem(
                        url=url_list[0],
                        media_type=MediaType.IMAGE,
                        post_id=video_id,
                        index=idx,
                        width=img.get("imageWidth", 0),
                        height=img.get("imageHeight", 0)
                    ))

        # 视频模式
        video = post.get("video", {})
        if video and not image_post and MediaType.VIDEO in media_types:
            # 尝试获取无水印地址
            play_addr = video.get("playAddr")
            download_addr = video.get("downloadAddr")
            url = download_addr or play_addr

            if url:
                items.append(MediaItem(
                    url=url,
                    media_type=MediaType.VIDEO,
                    post_id=video_id,
                    index=0,
                    width=video.get("width", 0),
                    height=video.get("height", 0),
                    duration=video.get("duration", 0)
                ))

        return items


@register_platform("youtube", [
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
    "m.youtube.com"
])
class YouTubeClient(PlatformAPIClient):
    """
    YouTube 平台客户端

    使用 TikHub API 获取 YouTube 数据

    注意: YouTube 主要是视频平台，图片下载功能有限
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cached_username = None
        self._cached_channel_id = None

    def extract_username_from_url(self, url: str) -> Optional[str]:
        """从 YouTube URL 提取频道标识"""
        if self._cached_username:
            return self._cached_username

        try:
            url = self.clean_url(url)

            # 格式1: youtube.com/channel/UCxxx
            match = re.search(r'youtube\.com/channel/([^/?]+)', url)
            if match:
                return match.group(1)

            # 格式2: youtube.com/@username
            match = re.search(r'youtube\.com/@([^/?]+)', url)
            if match:
                return match.group(1)

            # 格式3: youtube.com/c/channelname
            match = re.search(r'youtube\.com/c/([^/?]+)', url)
            if match:
                return match.group(1)

            # 格式4: youtube.com/user/username
            match = re.search(r'youtube\.com/user/([^/?]+)', url)
            if match:
                return match.group(1)

        except Exception:
            pass
        return None

    async def _get_channel_id(self, identifier: str) -> Optional[str]:
        """获取频道 ID"""
        # 如果已经是频道 ID 格式
        if identifier.startswith("UC"):
            return identifier

        # 通过用户名获取频道 ID
        data = await self._make_request(
            "/api/v1/youtube/web/fetch_channel_id",
            params={"channel_url": f"https://www.youtube.com/@{identifier}"}
        )
        if data:
            return data.get("data", {}).get("channel_id")

        return None

    async def get_user_posts(
        self,
        profile_url: str,
        max_posts: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """获取频道视频列表"""
        identifier = self.extract_username_from_url(profile_url)
        if not identifier:
            print(f"❌ 无法从 URL 提取频道标识: {profile_url}")
            return []

        try:
            # 获取频道 ID
            channel_id = await self._get_channel_id(identifier)
            if not channel_id:
                channel_id = identifier

            self._cached_channel_id = channel_id

            # 获取频道信息
            channel_info = await self._make_request(
                "/api/v1/youtube/web/fetch_channel_info",
                params={"channel_id": channel_id}
            )
            if channel_info:
                self._cached_username = channel_info.get("data", {}).get("title") or identifier

            print(f"👤 频道: {self._cached_username}")

            # 获取频道视频
            all_posts = []
            continuation = None
            has_more = True

            while has_more:
                params = {"channel_id": channel_id}
                if continuation:
                    params["continuation"] = continuation

                videos_data = await self._make_request(
                    "/api/v1/youtube/web/fetch_channel_videos_v2",
                    params=params
                )

                if not videos_data:
                    break

                data = videos_data.get("data", {})
                videos = data.get("videos", [])

                for video in videos:
                    all_posts.append(video)

                continuation = data.get("continuation")
                has_more = bool(continuation)

                if max_posts and len(all_posts) >= max_posts:
                    all_posts = all_posts[:max_posts]
                    break

                if not videos:
                    break

            return all_posts

        except Exception as e:
            print(f"❌ 获取视频失败: {e}")
            return []

    def extract_media_from_post(
        self,
        post: Dict[str, Any],
        media_types: List[MediaType] = None
    ) -> List[MediaItem]:
        """从 YouTube 视频提取媒体"""
        if media_types is None:
            media_types = [MediaType.IMAGE, MediaType.VIDEO]

        items = []
        video_id = post.get("videoId") or post.get("id") or "unknown"

        # YouTube 缩略图作为图片
        if MediaType.IMAGE in media_types:
            thumbnails = post.get("thumbnail", {}).get("thumbnails", [])
            if not thumbnails:
                # 尝试其他格式
                thumbnails = post.get("thumbnails", [])

            if thumbnails:
                # 选择最高分辨率
                best = max(thumbnails, key=lambda x: x.get("width", 0) * x.get("height", 0))
                url = best.get("url")
                if url:
                    items.append(MediaItem(
                        url=url,
                        media_type=MediaType.IMAGE,
                        post_id=video_id,
                        index=0,
                        width=best.get("width", 0),
                        height=best.get("height", 0)
                    ))

        # 注意: YouTube 视频下载需要额外处理，这里返回视频信息用于后续处理
        # TikHub API 可能提供直接下载链接
        if MediaType.VIDEO in media_types:
            # 尝试获取视频流 URL
            url = post.get("video_url") or post.get("streamUrl")
            if url:
                duration_text = post.get("lengthText", "0:00")
                items.append(MediaItem(
                    url=url,
                    media_type=MediaType.VIDEO,
                    post_id=video_id,
                    index=0,
                    extra={"title": post.get("title", "")}
                ))

        return items


@register_platform("twitter", [
    "twitter.com",
    "www.twitter.com",
    "x.com",
    "www.x.com"
])
class TwitterClient(PlatformAPIClient):
    """
    Twitter/X 平台客户端

    使用 TikHub API 获取 Twitter 数据
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cached_username = None
        self._cached_user_id = None

    def extract_username_from_url(self, url: str) -> Optional[str]:
        """从 Twitter URL 提取用户名"""
        if self._cached_username:
            return self._cached_username

        try:
            url = self.clean_url(url)

            # 格式: twitter.com/username 或 x.com/username
            match = re.search(r'(?:twitter\.com|x\.com)/([^/?]+)', url)
            if match:
                username = match.group(1)
                # 排除非用户页面
                if username not in ["home", "explore", "search", "notifications", "messages", "settings", "i"]:
                    return username

        except Exception:
            pass
        return None

    async def get_user_posts(
        self,
        profile_url: str,
        max_posts: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """获取用户推文列表"""
        username = self.extract_username_from_url(profile_url)
        if not username:
            print(f"❌ 无法从 URL 提取用户名: {profile_url}")
            return []

        try:
            # 获取用户信息
            user_info_data = await self._make_request(
                "/api/v1/twitter/web/fetch_user_profile",
                params={"screen_name": username}
            )

            if not user_info_data:
                print(f"❌ 无法获取用户信息: {username}")
                return []

            user = user_info_data.get("data", {}).get("user", {})
            rest_id = user.get("rest_id")
            self._cached_username = user.get("legacy", {}).get("name") or username
            self._cached_user_id = rest_id

            print(f"👤 用户: {self._cached_username}")

            if not rest_id:
                print(f"❌ 无法获取用户 ID: {username}")
                return []

            # 获取用户媒体推文（只包含图片/视频的推文）
            all_posts = []
            cursor = None
            has_more = True

            while has_more:
                params = {"screen_name": username}
                if cursor:
                    params["cursor"] = cursor

                # 使用媒体接口获取包含媒体的推文
                posts_data = await self._make_request(
                    "/api/v1/twitter/web/fetch_user_media",
                    params=params
                )

                if not posts_data:
                    break

                data = posts_data.get("data", {})
                tweets = data.get("tweets", [])

                for tweet in tweets:
                    all_posts.append(tweet)

                cursor = data.get("cursor")
                has_more = bool(cursor) and bool(tweets)

                if max_posts and len(all_posts) >= max_posts:
                    all_posts = all_posts[:max_posts]
                    break

                if not tweets:
                    break

            return all_posts

        except Exception as e:
            print(f"❌ 获取推文失败: {e}")
            return []

    def extract_media_from_post(
        self,
        post: Dict[str, Any],
        media_types: List[MediaType] = None
    ) -> List[MediaItem]:
        """从推文提取媒体"""
        if media_types is None:
            media_types = [MediaType.IMAGE, MediaType.VIDEO]

        items = []
        tweet_id = post.get("rest_id") or post.get("id") or "unknown"

        # 获取媒体列表
        legacy = post.get("legacy", {})
        extended_entities = legacy.get("extended_entities", {})
        media_list = extended_entities.get("media", [])

        for idx, media in enumerate(media_list):
            media_type_str = media.get("type", "")

            # 图片
            if media_type_str == "photo" and MediaType.IMAGE in media_types:
                url = media.get("media_url_https") or media.get("media_url")
                if url:
                    # 获取最大尺寸
                    url = url + "?format=jpg&name=large"
                    sizes = media.get("sizes", {})
                    large = sizes.get("large", {})
                    items.append(MediaItem(
                        url=url,
                        media_type=MediaType.IMAGE,
                        post_id=tweet_id,
                        index=idx,
                        width=large.get("w", 0),
                        height=large.get("h", 0)
                    ))

            # 视频/GIF
            elif media_type_str in ["video", "animated_gif"] and MediaType.VIDEO in media_types:
                video_info = media.get("video_info", {})
                variants = video_info.get("variants", [])

                # 选择最高码率的 mp4
                mp4_variants = [v for v in variants if v.get("content_type") == "video/mp4"]
                if mp4_variants:
                    best = max(mp4_variants, key=lambda x: x.get("bitrate", 0))
                    url = best.get("url")
                    if url:
                        duration_ms = video_info.get("duration_millis", 0)
                        items.append(MediaItem(
                            url=url,
                            media_type=MediaType.VIDEO,
                            post_id=tweet_id,
                            index=idx,
                            duration=duration_ms / 1000
                        ))

        return items


@register_platform("bilibili", [
    "bilibili.com",
    "www.bilibili.com",
    "b23.tv",
    "space.bilibili.com"
])
class BilibiliClient(PlatformAPIClient):
    """
    Bilibili 平台客户端

    使用 TikHub API 获取 Bilibili 数据

    支持:
    - 用户空间: space.bilibili.com/xxx
    - 短链接: b23.tv/xxx
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cached_username = None
        self._cached_mid = None

    def extract_username_from_url(self, url: str) -> Optional[str]:
        """从 Bilibili URL 提取用户 ID"""
        if self._cached_username:
            return self._cached_username

        try:
            url = self.clean_url(url)

            # 格式1: space.bilibili.com/xxx
            match = re.search(r'space\.bilibili\.com/(\d+)', url)
            if match:
                return match.group(1)

            # 格式2: bilibili.com/space/xxx
            match = re.search(r'bilibili\.com/space/(\d+)', url)
            if match:
                return match.group(1)

        except Exception:
            pass
        return None

    async def _resolve_short_link(self, short_url: str) -> Optional[str]:
        """解析 B 站短链接"""
        try:
            if self.session:
                async with self.session.get(short_url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    final_url = str(resp.url)
                    print(f"  📍 短链接解析: {final_url[:60]}...")
                    return final_url
        except Exception as e:
            print(f"  ⚠️  短链接解析失败: {e}")
        return None

    async def get_user_posts(
        self,
        profile_url: str,
        max_posts: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """获取用户视频列表"""
        resolved_url = profile_url

        # 处理短链接
        if "b23.tv" in profile_url:
            resolved_url = await self._resolve_short_link(profile_url)
            if not resolved_url:
                print(f"❌ 无法解析短链接: {profile_url}")
                return []

        # 提取用户 ID
        mid = self.extract_username_from_url(resolved_url)
        if not mid:
            print(f"❌ 无法从 URL 提取用户 ID: {profile_url}")
            return []

        try:
            self._cached_mid = mid

            # 获取用户信息
            user_info_data = await self._make_request(
                "/api/v1/bilibili/web/fetch_user_info",
                params={"mid": mid}
            )
            if user_info_data:
                user = user_info_data.get("data", {})
                self._cached_username = user.get("name") or mid

            print(f"👤 用户: {self._cached_username}")

            # 分页获取视频
            all_posts = []
            page = 1
            has_more = True

            while has_more:
                posts_data = await self._make_request(
                    "/api/v1/bilibili/web/fetch_user_post",
                    params={
                        "mid": mid,
                        "pn": page,
                        "ps": 30
                    }
                )

                if not posts_data:
                    break

                data = posts_data.get("data", {})
                vlist = data.get("list", {}).get("vlist", [])

                for video in vlist:
                    all_posts.append(video)

                page += 1
                total = data.get("page", {}).get("count", 0)
                has_more = len(all_posts) < total

                if max_posts and len(all_posts) >= max_posts:
                    all_posts = all_posts[:max_posts]
                    break

                if not vlist:
                    break

            return all_posts

        except Exception as e:
            print(f"❌ 获取视频失败: {e}")
            return []

    def extract_media_from_post(
        self,
        post: Dict[str, Any],
        media_types: List[MediaType] = None
    ) -> List[MediaItem]:
        """从 B 站视频提取媒体"""
        if media_types is None:
            media_types = [MediaType.IMAGE, MediaType.VIDEO]

        items = []
        bvid = post.get("bvid") or "unknown"
        aid = post.get("aid")

        # 视频封面作为图片
        if MediaType.IMAGE in media_types:
            pic = post.get("pic")
            if pic:
                # 确保是完整 URL
                if pic.startswith("//"):
                    pic = "https:" + pic
                items.append(MediaItem(
                    url=pic,
                    media_type=MediaType.IMAGE,
                    post_id=bvid,
                    index=0,
                    extra={"title": post.get("title", "")}
                ))

        # 注意: B 站视频下载需要额外获取播放地址
        # 这里我们标记视频信息，实际下载时需要调用获取播放地址的 API
        if MediaType.VIDEO in media_types:
            # B 站需要单独获取视频流地址
            # 返回视频封面 URL 作为占位，实际下载时需要额外处理
            duration = post.get("length", "0:00")
            # 解析时长
            if isinstance(duration, str) and ":" in duration:
                parts = duration.split(":")
                if len(parts) == 2:
                    duration_sec = int(parts[0]) * 60 + int(parts[1])
                else:
                    duration_sec = 0
            else:
                duration_sec = int(duration) if duration else 0

            # 存储视频信息用于后续处理
            items.append(MediaItem(
                url=f"https://www.bilibili.com/video/{bvid}",  # 视频页面 URL
                media_type=MediaType.VIDEO,
                post_id=bvid,
                index=0,
                duration=duration_sec,
                extra={
                    "title": post.get("title", ""),
                    "aid": aid,
                    "bvid": bvid,
                    "need_fetch_playurl": True  # 标记需要额外获取播放地址
                }
            ))

        return items
