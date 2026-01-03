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


# 未来可添加更多平台实现:
# @register_platform("douyin", ["douyin.com", "iesdouyin.com"])
# class DouyinClient(PlatformAPIClient): ...

# @register_platform("tiktok", ["tiktok.com", "vm.tiktok.com"])
# class TikTokClient(PlatformAPIClient): ...

# @register_platform("youtube", ["youtube.com", "youtu.be"])
# class YouTubeClient(PlatformAPIClient): ...

# @register_platform("twitter", ["twitter.com", "x.com"])
# class TwitterClient(PlatformAPIClient): ...
