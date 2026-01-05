# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TikHub 多平台下载器 - A Python tool for downloading images, videos, and audio from multiple social media platforms using the TikHub API. Supports concurrent downloads, content deduplication, incremental downloading, and automatic API key failover.

**Supported Platforms:**
- Instagram (instagram.com, instagr.am)
- 小红书 Xiaohongshu (xiaohongshu.com, xhslink.com)
- 抖音 Douyin (douyin.com, v.douyin.com)
- TikTok (tiktok.com, vm.tiktok.com)
- Twitter/X (twitter.com, x.com)
- YouTube (youtube.com, youtu.be)
- Bilibili (bilibili.com, b23.tv)

## Development Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export TIKHUB_API_KEY="your_api_key"
export TIKHUB_API_KEY_BACKUP="your_backup_key"  # Optional
```

## Common Commands

```bash
# Download from any platform (auto-detect)
python tikhub_downloader.py --url "https://www.instagram.com/natgeo/" -y

# Batch download from file
python tikhub_downloader.py --accounts-file data/accounts.txt -y

# Filter by media type
python tikhub_downloader.py --url "..." --images-only
python tikhub_downloader.py --url "..." --videos-only

# Limit downloads
python tikhub_downloader.py --url "..." --max-posts 50 --max-items 100

# Quick test
python tikhub_downloader.py --url "https://www.instagram.com/natgeo/" --max-posts 2 --max-items 5 --output-dir test_output -y
```

## Architecture

### Core Components (downloader/core.py)

1. **MediaType** - Enum: IMAGE, VIDEO, AUDIO

2. **MediaItem** - Dataclass for downloadable media with URL, type, post_id, dimensions

3. **PlatformAPIClient** (Abstract Base Class)
   - Handles TikHub API auth and requests with multi-URL failover
   - **Automatic API key switching** on HTTP 402 (quota exhausted)
   - Abstract methods to implement:
     - `extract_username_from_url(url)` → username
     - `get_user_posts(url, max_posts)` → posts list
     - `extract_media_from_post(post, media_types)` → MediaItem list

4. **MediaDownloader**
   - Concurrent downloads with semaphore control
   - MD5-based content deduplication
   - Statistics: success, skipped, duplicate, failed

5. **Platform Registration**
   - `@register_platform(name, url_patterns)` decorator
   - `detect_platform(url)` - Auto-detect platform
   - `get_platform_client(platform)` - Get client class

### Platform Implementations (downloader/platforms.py)

| Platform | Client Class | URL Patterns | API Endpoints |
|----------|-------------|--------------|---------------|
| Instagram | InstagramClient | instagram.com, instagr.am | /api/v1/instagram/v1/... |
| Xiaohongshu | XiaohongshuClient | xiaohongshu.com, xhslink.com | /api/v1/xiaohongshu/app/v1/... |
| Douyin | DouyinClient | douyin.com, v.douyin.com | /api/v1/douyin/web/... |
| TikTok | TikTokClient | tiktok.com, vm.tiktok.com | /api/v1/tiktok/web_api/v1/... |
| Twitter | TwitterClient | twitter.com, x.com | /api/v1/twitter/web/... |
| YouTube | YouTubeClient | youtube.com, youtu.be | /api/v1/youtube/web/... |
| Bilibili | BilibiliClient | bilibili.com, b23.tv | /api/v1/bilibili/web/... |

### Adding New Platforms

```python
@register_platform("douyin", ["douyin.com", "iesdouyin.com"])
class DouyinClient(PlatformAPIClient):
    def extract_username_from_url(self, url: str) -> Optional[str]:
        pass

    async def get_user_posts(self, profile_url: str, max_posts: Optional[int] = None) -> List[Dict]:
        pass

    def extract_media_from_post(self, post: Dict, media_types: List[MediaType] = None) -> List[MediaItem]:
        pass
```

### Data Flow

1. CLI args → detect platform from URL
2. Get platform client → fetch posts via TikHub API (paginated)
3. Extract media items → download concurrently with deduplication
4. Output: `output/{platform}/{username}/{post_id}_{index}.{ext}`

## Key Features

### API Key Auto-Switch
When primary key returns HTTP 402 (quota exhausted), automatically switches to backup keys:
```bash
export TIKHUB_API_KEY="main_key"
export TIKHUB_API_KEY_BACKUP="backup_1"
export TIKHUB_API_KEY_BACKUP_1="backup_2"
```

### Rate Limiting
- TikHub API: 5 concurrent requests per client
- Downloads: configurable via `--concurrent` (default: 10)

### Environment Variables
- `TIKHUB_API_KEY` - Primary API key (required)
- `TIKHUB_API_KEY_BACKUP` - Backup key (optional)
- `TIKHUB_API_KEY_BACKUP_N` - Additional backup keys (N=1-9)
- `HENGHENGMAO_API_KEY` - Legacy alias
