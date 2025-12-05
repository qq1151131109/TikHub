#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Instagram 图片批量下载器 - 基于 TikHub API

功能特点：
- 批量下载多个 Instagram 账号的所有图片
- 支持普通帖子和 Reels 的图片
- 并发下载提高效率
- 增量模式避免重复下载
- 自动去重和错误重试
- 双 API 服务器支持（中国大陆和国际）

用法：
  python download_instagram_images.py --accounts-file data/accounts.json --output-dir output
  python download_instagram_images.py --account-url "https://www.instagram.com/username/" --max-posts 50

配置：
  在 config/config.json 中配置 TikHub 凭据，或通过环境变量：
  export TIKHUB_API_KEY="your_api_key"
"""

import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

import aiofiles
import aiohttp
from tqdm import tqdm
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


class HenghengMaoAPI:
    """TikHub API 客户端 (替代 HengHengMao API)"""

    def __init__(self, api_key: str, base_url: str = "https://api.tikhub.dev"):
        self.api_key = api_key
        # 支持双 base URL (中国大陆和国际)
        self.base_urls = [
            "https://api.tikhub.dev",     # 中国大陆
            "https://api.tikhub.io"       # 国际
        ]
        # 如果提供了自定义 base_url，将其添加到列表开头
        if base_url and base_url not in self.base_urls:
            self.base_urls.insert(0, base_url)

        self.session: Optional[aiohttp.ClientSession] = None
        self._sem = asyncio.Semaphore(5)  # API 并发限制

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
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        发起 API 请求,支持双 base URL 自动切换

        Args:
            endpoint: API 端点路径
            params: 查询参数

        Returns:
            响应数据,失败返回 None
        """
        if not self.session:
            raise RuntimeError("Session not initialized")

        headers = self._build_headers()

        # 尝试所有 base URL
        for base_url in self.base_urls:
            url = f"{base_url.rstrip('/')}{endpoint}"
            try:
                async with self.session.get(url, headers=headers, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("code") == 200:
                            return data
                        else:
                            print(f"⚠️  API 返回错误: {data.get('message', '未知错误')}")
                    else:
                        print(f"⚠️  请求失败 [{base_url}]: HTTP {resp.status}")
            except Exception as e:
                print(f"⚠️  请求异常 [{base_url}]: {e}")
                continue

        return None

    async def get_profile_posts(
        self,
        profile_url: str,
        max_posts: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        获取账号的所有帖子

        Args:
            profile_url: Instagram 账号主页 URL
            max_posts: 最大获取帖子数，None 表示获取所有

        Returns:
            帖子列表，每个帖子是 TikHub API 返回的原始 node 数据
        """
        if not self.session:
            raise RuntimeError("Session not initialized")

        # 从 URL 提取用户名
        username = extract_username_from_url(profile_url)
        if not username:
            print(f"❌ 无法从 URL 提取用户名: {profile_url}")
            return []

        async with self._sem:
            try:
                # 1. 获取用户 ID
                user_info = await self._make_request(
                    "/api/v1/instagram/web_app/fetch_user_info_by_username",
                    params={"username": username}
                )

                if not user_info:
                    print(f"❌ 无法获取用户信息: {username}")
                    return []

                user_id = user_info.get("data", {}).get("id")
                if not user_id:
                    print(f"❌ 用户 ID 不存在: {username}")
                    return []

                # 2. 获取帖子列表 (分页)
                all_posts = []
                end_cursor = None
                has_next_page = True

                while has_next_page:
                    params = {
                        "user_id": user_id,
                        "count": 12  # 每页获取 12 个帖子
                    }
                    if end_cursor:
                        params["end_cursor"] = end_cursor

                    posts_data = await self._make_request(
                        "/api/v1/instagram/web_app/fetch_user_posts_by_user_id",
                        params=params
                    )

                    if not posts_data:
                        print(f"❌ 获取帖子列表失败: {username}")
                        break

                    # 提取帖子
                    edges = (posts_data.get("data", {})
                            .get("data", {})
                            .get("user", {})
                            .get("edge_owner_to_timeline_media", {})
                            .get("edges", []))

                    for edge in edges:
                        all_posts.append(edge.get("node", {}))

                    # 检查分页
                    page_info = (posts_data.get("data", {})
                                .get("data", {})
                                .get("user", {})
                                .get("edge_owner_to_timeline_media", {})
                                .get("page_info", {}))

                    has_next_page = page_info.get("has_next_page", False)
                    end_cursor = page_info.get("end_cursor")

                    # 如果设置了最大数量限制，检查是否已达到
                    if max_posts is not None and len(all_posts) >= max_posts:
                        all_posts = all_posts[:max_posts]
                        break

                    # 如果没有更多帖子或没有 cursor，退出
                    if not has_next_page or not end_cursor:
                        break

                return all_posts

            except Exception as e:
                print(f"❌ 获取帖子失败: {e}")
                import traceback
                traceback.print_exc()
                return []

    def extract_images_from_post(self, post: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        从帖子中提取所有图片信息

        Args:
            post: TikHub API 返回的帖子节点数据

        Returns:
            [{"url": "...", "post_id": "...", "index": 0}, ...]
        """
        images = []
        post_id = post.get("id") or post.get("shortcode") or "unknown"
        post_type = post.get("__typename", "")

        # 优先使用 display_url (主图片)
        display_url = post.get("display_url")
        if display_url:
            images.append({
                "url": display_url,
                "post_id": post_id,
                "index": 0
            })

        # 如果是轮播帖子 (GraphSidecar)，可能需要额外处理
        # 但从 TikHub API 的响应来看，每个帖子节点已经是展开的单个媒体
        # 所以这里只需要提取 display_url 即可

        # 如果没有 display_url，尝试其他字段
        if not images:
            # 尝试 thumbnail_src (缩略图)
            thumbnail_src = post.get("thumbnail_src")
            if thumbnail_src:
                images.append({
                    "url": thumbnail_src,
                    "post_id": post_id,
                    "index": 0
                })

        return images


class ImageDownloader:
    """图片下载器"""

    def __init__(self, output_dir: Path, max_concurrent: int = 10):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._sem = asyncio.Semaphore(max_concurrent)
        self.session: Optional[aiohttp.ClientSession] = None
        self.downloaded_hashes: Set[str] = set()

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _get_file_hash(self, data: bytes) -> str:
        """计算文件内容的 hash 用于去重"""
        return hashlib.md5(data).hexdigest()

    def _get_output_path(self, username: str, post_id: str, index: int, url: str) -> Path:
        """生成输出文件路径"""
        # 从 URL 提取文件扩展名
        parsed = urlparse(url)
        path_parts = parsed.path.split(".")
        ext = path_parts[-1] if len(path_parts) > 1 else "jpg"
        ext = ext.split("?")[0]  # 移除查询参数

        if ext not in ["jpg", "jpeg", "png", "webp"]:
            ext = "jpg"

        user_dir = self.output_dir / username
        user_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{post_id}_{index:02d}.{ext}"
        return user_dir / filename

    async def download_image(
        self,
        username: str,
        image_info: Dict[str, str],
        skip_existing: bool = True
    ) -> Tuple[bool, str]:
        """
        下载单张图片

        Returns:
            (success, message)
        """
        url = image_info["url"]
        post_id = image_info["post_id"]
        index = image_info["index"]

        output_path = self._get_output_path(username, post_id, index, url)

        # 跳过已存在的文件
        if skip_existing and output_path.exists():
            return True, f"已存在: {output_path.name}"

        if not self.session:
            return False, "Session not initialized"

        async with self._sem:
            try:
                async with self.session.get(url) as resp:
                    resp.raise_for_status()
                    data = await resp.read()

                # 检查是否重复（内容去重）
                file_hash = self._get_file_hash(data)
                if file_hash in self.downloaded_hashes:
                    return True, f"重复内容: {output_path.name}"

                # 保存文件
                async with aiofiles.open(output_path, "wb") as f:
                    await f.write(data)

                self.downloaded_hashes.add(file_hash)
                return True, f"✓ {output_path.name}"

            except Exception as e:
                return False, f"✗ {output_path.name}: {str(e)[:50]}"


def clean_instagram_url(url: str) -> str:
    """清理 Instagram URL，移除查询参数"""
    # 移除 ?igsh= 等查询参数
    if '?' in url:
        url = url.split('?')[0]
    # 确保以 / 结尾
    if not url.endswith('/'):
        url += '/'
    return url


def extract_username_from_url(url: str) -> Optional[str]:
    """从 Instagram URL 提取用户名"""
    try:
        # 先清理 URL
        url = clean_instagram_url(url)
        # https://www.instagram.com/username/ 或 https://www.instagram.com/username/reels/
        path = url.split("//", 1)[-1]
        path = path.split("/", 1)[-1]  # 去掉域名
        parts = [p for p in path.split("/") if p]
        if parts:
            return parts[0]
    except Exception:
        pass
    return None


def load_accounts_from_file(file_path: Path) -> List[Dict[str, Any]]:
    """
    从文件加载账号列表

    支持格式：
    1. JSON 数组: [{"username": "...", "url": "..."}, ...]
    2. JSON 对象（按类别分组）: {"category1": [...], "category2": [...]}
    3. 纯文本: 每行一个 URL 或用户名
    """
    if not file_path.exists():
        raise FileNotFoundError(f"账号文件不存在: {file_path}")

    content = file_path.read_text(encoding="utf-8").strip()

    # 尝试解析 JSON
    try:
        data = json.loads(content)

        if isinstance(data, list):
            # 格式1: JSON 数组
            accounts = []
            for item in data:
                if isinstance(item, dict):
                    # 清理 URL
                    if 'url' in item:
                        item['url'] = clean_instagram_url(item['url'])
                    accounts.append(item)
                elif isinstance(item, str):
                    cleaned_url = clean_instagram_url(item)
                    username = extract_username_from_url(cleaned_url) or item
                    accounts.append({"username": username, "url": cleaned_url})
            return accounts

        elif isinstance(data, dict):
            # 格式2: JSON 对象（按类别）
            accounts = []
            for category, items in data.items():
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            # 清理 URL
                            if 'url' in item:
                                item['url'] = clean_instagram_url(item['url'])
                            item["category"] = category
                            accounts.append(item)
                        elif isinstance(item, str):
                            cleaned_url = clean_instagram_url(item)
                            username = extract_username_from_url(cleaned_url) or item
                            accounts.append({
                                "username": username,
                                "url": cleaned_url,
                                "category": category
                            })
            return accounts

    except json.JSONDecodeError:
        # 格式3: 纯文本
        accounts = []
        for line in content.split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                cleaned_url = clean_instagram_url(line)
                username = extract_username_from_url(cleaned_url) or line
                accounts.append({"username": username, "url": cleaned_url})
        return accounts

    return []


def load_config(config_path: Path) -> Dict[str, Any]:
    """加载配置文件"""
    if config_path.exists():
        try:
            return json.loads(config_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"⚠️  配置文件解析失败: {e}")
    return {}


def get_credentials(config: Dict[str, Any]) -> str:
    """获取 TikHub API 凭据（优先使用环境变量）"""
    # 支持多个环境变量名（向后兼容）
    api_key = (
        os.getenv("TIKHUB_API_KEY") or
        os.getenv("HENGHENGMAO_API_KEY") or
        config.get("tikhub", {}).get("api_key", "") or
        config.get("henghengmao", {}).get("api_key", "")
    )

    if not api_key:
        raise ValueError(
            "缺少 TikHub API 凭据。请设置环境变量：\n"
            "  export TIKHUB_API_KEY='your_api_key'\n"
            "或在 config/config.json 中配置"
        )

    return api_key


async def download_account_images(
    api: HenghengMaoAPI,
    downloader: ImageDownloader,
    account: Dict[str, Any],
    max_posts: Optional[int] = None,
    max_images: Optional[int] = None,
    skip_existing: bool = True
) -> Dict[str, Any]:
    """下载单个账号的所有图片"""
    username = account.get("username", "unknown")
    profile_url = account.get("url", "")

    if not profile_url:
        profile_url = f"https://www.instagram.com/{username}/"

    print(f"\n{'='*60}")
    print(f"📥 正在处理账号: {username}")
    print(f"🔗 URL: {profile_url}")

    # 获取帖子列表
    posts = await api.get_profile_posts(profile_url, max_posts)

    if not posts:
        return {
            "username": username,
            "success": False,
            "message": "未获取到帖子",
            "total_images": 0,
            "downloaded": 0
        }

    print(f"📄 获取到 {len(posts)} 个帖子")

    # 提取所有图片
    all_images = []
    for post in posts:
        images = api.extract_images_from_post(post)
        all_images.extend(images)
        # 如果设置了最大图片数限制，检查是否已达到
        if max_images is not None and len(all_images) >= max_images:
            all_images = all_images[:max_images]
            break

    print(f"🖼️  提取到 {len(all_images)} 张图片")

    if not all_images:
        return {
            "username": username,
            "success": True,
            "message": "无图片可下载",
            "total_images": 0,
            "downloaded": 0
        }

    # 批量下载
    tasks = [
        downloader.download_image(username, img_info, skip_existing)
        for img_info in all_images
    ]

    results = []
    with tqdm(total=len(tasks), desc=f"下载 {username}", leave=False) as pbar:
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
            pbar.update(1)

    # 统计结果
    success_count = sum(1 for success, _ in results if success)

    print(f"✅ 完成: {success_count}/{len(all_images)} 张图片")

    return {
        "username": username,
        "success": True,
        "total_images": len(all_images),
        "downloaded": success_count,
        "failed": len(all_images) - success_count
    }


async def main_async(args):
    """异步主函数"""
    # 加载配置
    config_path = Path(args.config)
    config = load_config(config_path)

    # 获取凭据
    try:
        api_key = get_credentials(config)
    except ValueError as e:
        print(f"❌ {e}")
        return 1

    # 准备账号列表
    accounts = []

    if args.account_url:
        # 单个账号模式
        cleaned_url = clean_instagram_url(args.account_url)
        username = extract_username_from_url(cleaned_url) or "unknown"
        accounts = [{"username": username, "url": cleaned_url}]
    elif args.accounts_file:
        # 批量账号模式
        accounts_file = Path(args.accounts_file)
        accounts = load_accounts_from_file(accounts_file)
    else:
        print("❌ 请指定 --account-url 或 --accounts-file")
        return 1

    if not accounts:
        print("❌ 未找到有效账号")
        return 1

    print(f"📋 准备下载 {len(accounts)} 个账号的图片")
    print(f"📁 输出目录: {args.output_dir}")

    if not args.yes:
        response = input("\n是否继续？(y/N): ").strip().lower()
        if response != "y":
            print("已取消")
            return 0

    # 初始化客户端
    output_dir = Path(args.output_dir)

    # 从配置中获取 base_url (默认使用中国大陆 URL)
    base_url = config.get("tikhub", {}).get("base_url", "https://api.tikhub.dev")

    async with HenghengMaoAPI(api_key, base_url) as api:
        async with ImageDownloader(output_dir, max_concurrent=args.concurrent) as downloader:
            # 逐个处理账号
            results = []
            for account in accounts:
                result = await download_account_images(
                    api=api,
                    downloader=downloader,
                    account=account,
                    max_posts=args.max_posts,
                    max_images=args.max_images,
                    skip_existing=not args.no_skip_existing
                )
                results.append(result)

    # 输出总结
    print(f"\n{'='*60}")
    print("📊 下载总结:")
    print(f"{'='*60}")

    total_images = sum(r["total_images"] for r in results)
    total_downloaded = sum(r["downloaded"] for r in results)
    total_failed = sum(r.get("failed", 0) for r in results)

    for result in results:
        status = "✅" if result["success"] else "❌"
        print(f"{status} {result['username']}: {result['downloaded']}/{result['total_images']} 张图片")

    print(f"\n总计: {total_downloaded}/{total_images} 张图片成功下载")
    if total_failed > 0:
        print(f"失败: {total_failed} 张")

    return 0


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Instagram 图片批量下载器 - 基于 TikHub API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 下载单个账号的所有图片
  python download_instagram_images.py --account-url "https://www.instagram.com/username/"

  # 批量下载多个账号（从文件读取）
  python download_instagram_images.py --accounts-file data/accounts.json

  # 限制每个账号下载的帖子数
  python download_instagram_images.py --accounts-file data/accounts.json --max-posts 50

  # 调整并发数
  python download_instagram_images.py --accounts-file data/accounts.json --concurrent 20

环境变量:
  TIKHUB_API_KEY      - TikHub API 密钥
        """
    )

    parser.add_argument(
        "--account-url",
        help="单个账号的 Instagram URL"
    )

    parser.add_argument(
        "--accounts-file",
        help="账号列表文件（支持 JSON 或纯文本格式）"
    )

    parser.add_argument(
        "--output-dir",
        default="output",
        help="输出目录（默认: output）"
    )

    parser.add_argument(
        "--config",
        default="config/config.json",
        help="配置文件路径（默认: config/config.json）"
    )

    parser.add_argument(
        "--max-posts",
        type=int,
        help="每个账号最多下载的帖子数（默认: 无限制）"
    )

    parser.add_argument(
        "--max-images",
        type=int,
        default=500,
        help="每个账号最多下载的图片数（默认: 500）"
    )

    parser.add_argument(
        "--concurrent",
        type=int,
        default=10,
        help="并发下载数（默认: 10）"
    )

    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="不跳过已存在的文件（重新下载）"
    )

    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="跳过确认提示"
    )

    args = parser.parse_args()

    # 运行异步主函数
    exit_code = asyncio.run(main_async(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
