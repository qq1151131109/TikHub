#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TikHub 多平台下载器 - 统一命令行入口

支持的平台:
- Instagram (instagram.com)
- 小红书 (xiaohongshu.com, xhslink.com)
- 更多平台开发中...

用法:
  # 自动检测平台
  python tikhub_downloader.py --url "https://www.instagram.com/natgeo/"

  # 批量下载（从文件）
  python tikhub_downloader.py --accounts-file data/accounts.txt

  # 只下载图片
  python tikhub_downloader.py --url "..." --images-only

  # 只下载视频
  python tikhub_downloader.py --url "..." --videos-only

  # 指定媒体类型
  python tikhub_downloader.py --url "..." --media-types image,video
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from downloader import (
    MediaType,
    MediaDownloader,
    detect_platform,
    get_platform_client,
    PLATFORM_REGISTRY,
)

# 加载 .env 文件
load_dotenv()


def load_accounts_from_file(file_path: Path) -> List[Dict[str, Any]]:
    """
    从文件加载账号列表

    支持格式:
    1. JSON 数组: [{"url": "..."}, ...]
    2. JSON 对象（分类）: {"category1": [...], ...}
    3. 纯文本: 每行一个 URL
    """
    if not file_path.exists():
        raise FileNotFoundError(f"账号文件不存在: {file_path}")

    content = file_path.read_text(encoding="utf-8").strip()

    try:
        data = json.loads(content)

        if isinstance(data, list):
            accounts = []
            for item in data:
                if isinstance(item, dict):
                    accounts.append(item)
                elif isinstance(item, str):
                    accounts.append({"url": item})
            return accounts

        elif isinstance(data, dict):
            accounts = []
            for category, items in data.items():
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            item["category"] = category
                            accounts.append(item)
                        elif isinstance(item, str):
                            accounts.append({"url": item, "category": category})
            return accounts

    except json.JSONDecodeError:
        # 纯文本格式
        accounts = []
        for line in content.split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                accounts.append({"url": line})
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


def get_api_key(config: Dict[str, Any]) -> str:
    """获取 API 密钥"""
    api_key = (
        os.getenv("TIKHUB_API_KEY") or
        os.getenv("HENGHENGMAO_API_KEY") or
        config.get("tikhub", {}).get("api_key", "") or
        config.get("henghengmao", {}).get("api_key", "")
    )

    if not api_key:
        raise ValueError(
            "缺少 TikHub API 密钥。请设置环境变量:\n"
            "  export TIKHUB_API_KEY='your_api_key'\n"
            "或在 config/config.json 中配置"
        )

    return api_key


def get_backup_api_keys(config: Dict[str, Any]) -> List[str]:
    """获取备用 API 密钥列表"""
    backup_keys = []

    # 从环境变量加载
    backup_key = os.getenv("TIKHUB_API_KEY_BACKUP")
    if backup_key:
        backup_keys.append(backup_key)

    # 支持多个备用 Key: TIKHUB_API_KEY_BACKUP_1, TIKHUB_API_KEY_BACKUP_2, ...
    for i in range(1, 10):
        key = os.getenv(f"TIKHUB_API_KEY_BACKUP_{i}")
        if key:
            backup_keys.append(key)

    # 从配置文件加载
    config_backup_keys = config.get("tikhub", {}).get("backup_api_keys", [])
    if isinstance(config_backup_keys, list):
        backup_keys.extend(config_backup_keys)

    return backup_keys


def parse_media_types(args) -> List[MediaType]:
    """解析媒体类型参数"""
    # 快捷选项优先
    if args.images_only:
        return [MediaType.IMAGE]
    if args.videos_only:
        return [MediaType.VIDEO]
    if args.audio_only:
        return [MediaType.AUDIO]

    # 自定义类型
    if args.media_types:
        return MediaType.parse_list(args.media_types)

    # 默认：图片和视频
    return [MediaType.IMAGE, MediaType.VIDEO]


async def download_account(
    api_key: str,
    url: str,
    output_dir: Path,
    media_types: List[MediaType],
    max_posts: Optional[int] = None,
    max_items: Optional[int] = None,
    concurrent: int = 10,
    skip_existing: bool = True,
    backup_api_keys: List[str] = None
) -> Dict[str, Any]:
    """下载单个账号的内容"""
    # 检测平台
    platform = detect_platform(url)
    if not platform:
        return {
            "url": url,
            "success": False,
            "error": "无法识别的平台 URL"
        }

    # 获取平台客户端
    client_cls = get_platform_client(platform)
    if not client_cls:
        return {
            "url": url,
            "success": False,
            "error": f"平台 {platform} 暂不支持"
        }

    print(f"\n{'='*60}")
    print(f"📥 平台: {platform.upper()}")
    print(f"🔗 URL: {url}")
    print(f"📦 媒体类型: {', '.join(t.value for t in media_types)}")

    async with client_cls(api_key, backup_api_keys=backup_api_keys) as api:
        # 获取帖子（对于短链接，这会解析并缓存用户信息）
        posts = await api.get_user_posts(url, max_posts)

        # 提取用户名（在获取帖子后，短链接的用户名可能已被缓存）
        username = api.extract_username_from_url(url) or "unknown"
        print(f"👤 用户: {username}")

        if not posts:
            return {
                "url": url,
                "platform": platform,
                "username": username,
                "success": False,
                "error": "未获取到帖子"
            }

        print(f"📄 获取到 {len(posts)} 个帖子")

        # 提取媒体
        all_items = []
        for post in posts:
            items = api.extract_media_from_post(post, media_types)
            all_items.extend(items)
            if max_items and len(all_items) >= max_items:
                all_items = all_items[:max_items]
                break

        # 统计媒体类型
        type_counts = {}
        for item in all_items:
            t = item.media_type.value
            type_counts[t] = type_counts.get(t, 0) + 1

        print(f"🎬 提取到 {len(all_items)} 个媒体: {type_counts}")

        if not all_items:
            return {
                "url": url,
                "platform": platform,
                "username": username,
                "success": True,
                "total": 0,
                "downloaded": 0
            }

        # 下载
        async with MediaDownloader(
            output_dir,
            max_concurrent=concurrent,
            skip_existing=skip_existing
        ) as downloader:
            results = await downloader.download_batch(
                platform=platform,
                username=username,
                items=all_items,
                progress_desc=f"下载 {username}"
            )

            success_count = sum(1 for s, _ in results if s)
            print(f"✅ 完成: {success_count}/{len(all_items)}")

            return {
                "url": url,
                "platform": platform,
                "username": username,
                "success": True,
                "total": len(all_items),
                "downloaded": success_count,
                "failed": len(all_items) - success_count,
                "stats": downloader.stats.copy()
            }


async def main_async(args):
    """异步主函数"""
    # 加载配置
    config = load_config(Path(args.config))

    # 获取 API 密钥
    try:
        api_key = get_api_key(config)
    except ValueError as e:
        print(f"❌ {e}")
        return 1

    # 获取备用 API 密钥
    backup_api_keys = get_backup_api_keys(config)
    if backup_api_keys:
        print(f"🔑 已加载 {len(backup_api_keys)} 个备用 API Key")

    # 准备账号列表
    accounts = []

    if args.url:
        accounts = [{"url": args.url}]
    elif args.accounts_file:
        accounts = load_accounts_from_file(Path(args.accounts_file))
    else:
        print("❌ 请指定 --url 或 --accounts-file")
        return 1

    if not accounts:
        print("❌ 未找到有效账号")
        return 1

    # 解析媒体类型
    media_types = parse_media_types(args)

    print(f"📋 准备下载 {len(accounts)} 个账号")
    print(f"📁 输出目录: {args.output_dir}")
    print(f"📦 媒体类型: {', '.join(t.value for t in media_types)}")

    # 显示支持的平台
    print(f"🌐 支持平台: {', '.join(PLATFORM_REGISTRY.keys())}")

    if not args.yes:
        response = input("\n是否继续？(y/N): ").strip().lower()
        if response != "y":
            print("已取消")
            return 0

    output_dir = Path(args.output_dir)

    # 处理每个账号
    results = []
    for account in accounts:
        url = account.get("url", "")
        if not url:
            continue

        result = await download_account(
            api_key=api_key,
            url=url,
            output_dir=output_dir,
            media_types=media_types,
            max_posts=args.max_posts,
            max_items=args.max_items,
            concurrent=args.concurrent,
            skip_existing=not args.no_skip_existing,
            backup_api_keys=backup_api_keys
        )
        results.append(result)

    # 输出总结
    print(f"\n{'='*60}")
    print("📊 下载总结:")
    print(f"{'='*60}")

    total_items = sum(r.get("total", 0) for r in results)
    total_downloaded = sum(r.get("downloaded", 0) for r in results)
    total_failed = sum(r.get("failed", 0) for r in results)

    for result in results:
        if result.get("success"):
            platform = result.get("platform", "?")
            username = result.get("username", "?")
            downloaded = result.get("downloaded", 0)
            total = result.get("total", 0)
            print(f"✅ [{platform}] {username}: {downloaded}/{total}")
        else:
            error = result.get("error", "未知错误")
            print(f"❌ {result.get('url', '?')}: {error}")

    print(f"\n总计: {total_downloaded}/{total_items} 个文件成功下载")
    if total_failed > 0:
        print(f"失败: {total_failed} 个")

    return 0


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="TikHub 多平台下载器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 下载 Instagram 账号
  python tikhub_downloader.py --url "https://www.instagram.com/natgeo/"

  # 下载小红书账号
  python tikhub_downloader.py --url "https://www.xiaohongshu.com/user/profile/xxx"

  # 批量下载
  python tikhub_downloader.py --accounts-file data/accounts.txt

  # 只下载图片
  python tikhub_downloader.py --url "..." --images-only

  # 只下载视频
  python tikhub_downloader.py --url "..." --videos-only

  # 指定媒体类型
  python tikhub_downloader.py --url "..." --media-types image,video

支持的平台:
  - Instagram (instagram.com)
  - 小红书 (xiaohongshu.com, xhslink.com)
  - 更多平台开发中...

环境变量:
  TIKHUB_API_KEY - TikHub API 密钥
        """
    )

    # 输入选项
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "--url",
        help="单个账号 URL（自动检测平台）"
    )
    input_group.add_argument(
        "--accounts-file",
        help="账号列表文件（支持 JSON 或纯文本）"
    )

    # 输出选项
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

    # 媒体类型选项
    media_group = parser.add_argument_group("媒体类型")
    media_group.add_argument(
        "--media-types",
        help="媒体类型，逗号分隔 (image,video,audio)"
    )
    media_group.add_argument(
        "--images-only",
        action="store_true",
        help="只下载图片"
    )
    media_group.add_argument(
        "--videos-only",
        action="store_true",
        help="只下载视频"
    )
    media_group.add_argument(
        "--audio-only",
        action="store_true",
        help="只下载音频"
    )

    # 下载选项
    download_group = parser.add_argument_group("下载选项")
    download_group.add_argument(
        "--max-posts",
        type=int,
        help="每个账号最多下载的帖子数"
    )
    download_group.add_argument(
        "--max-items",
        type=int,
        help="每个账号最多下载的媒体数"
    )
    download_group.add_argument(
        "--concurrent",
        type=int,
        default=10,
        help="并发下载数（默认: 10）"
    )
    download_group.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="不跳过已存在的文件"
    )

    # 其他选项
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="跳过确认提示"
    )

    args = parser.parse_args()
    exit_code = asyncio.run(main_async(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
