# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TikHub 多平台下载器 - A Python tool for downloading images, videos, and audio from multiple social media platforms using the TikHub API. The tool supports concurrent downloads, content deduplication, and incremental downloading.

**支持的平台 (Supported Platforms):**
- Instagram (instagram.com)
- 小红书 Xiaohongshu (xiaohongshu.com, xhslink.com)
- 更多平台开发中... (More platforms coming soon)

## Development Setup

1. Create and activate virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure API credentials:
```bash
export TIKHUB_API_KEY="your_api_key"
```

4. Prepare account list (optional for batch downloads):
```bash
cp data/accounts.example.json data/accounts.json
# Edit data/accounts.json to add accounts to download
```

## Common Commands

### New Multi-Platform Downloader (Recommended)

```bash
# Download from any supported platform (auto-detect)
python tikhub_downloader.py --url "https://www.instagram.com/natgeo/"
python tikhub_downloader.py --url "https://www.xiaohongshu.com/user/profile/xxx"

# Batch download from file
python tikhub_downloader.py --accounts-file data/accounts.txt

# Only download images
python tikhub_downloader.py --url "..." --images-only

# Only download videos
python tikhub_downloader.py --url "..." --videos-only

# Specify media types
python tikhub_downloader.py --url "..." --media-types image,video

# Skip confirmation prompt
python tikhub_downloader.py --url "..." -y

# Limit downloads
python tikhub_downloader.py --url "..." --max-posts 50 --max-items 100
```

### Legacy Instagram-Only Downloader

```bash
# Download from multiple accounts (from file)
python download_instagram_images.py --accounts-file data/accounts.json

# Download from a single account
python download_instagram_images.py --account-url "https://www.instagram.com/username/"
```

### Testing

```bash
# Quick test with limited scope
python tikhub_downloader.py --url "https://www.instagram.com/natgeo/" --max-posts 2 --max-items 5 --output-dir test_output -y
```

## Architecture

### File Structure

```
.
├── tikhub_downloader.py          # New unified CLI entry point
├── download_instagram_images.py   # Legacy Instagram-only downloader
├── downloader/                    # Core package
│   ├── __init__.py               # Package exports
│   ├── core.py                   # Abstract base classes and utilities
│   └── platforms.py              # Platform implementations
├── requirements.txt              # Python dependencies
├── config/
│   └── config.example.json       # Config template
└── data/
    └── accounts.example.json     # Account list examples
```

### Core Components (downloader/core.py)

1. **MediaType** - Enum for media types (IMAGE, VIDEO, AUDIO)

2. **MediaItem** - Dataclass representing a downloadable media item

3. **PlatformAPIClient** (Abstract Base Class)
   - Base class for all platform implementations
   - Handles TikHub API authentication and requests
   - Supports multiple base URLs for failover
   - Key abstract methods:
     - `extract_username_from_url()`: Extract username from platform URL
     - `get_user_posts()`: Fetch user posts with pagination
     - `extract_media_from_post()`: Extract media items from post data

4. **MediaDownloader**
   - Generic downloader for all media types
   - MD5-based content deduplication
   - Concurrent downloads with semaphore control
   - Statistics tracking (success, skipped, duplicate, failed)

5. **Platform Registration**
   - `@register_platform(name, url_patterns)` decorator
   - `detect_platform(url)` - Auto-detect platform from URL
   - `get_platform_client(platform)` - Get client class by name

### Platform Implementations (downloader/platforms.py)

1. **InstagramClient**
   - URL patterns: `instagram.com`, `instagr.am`
   - Supports: Images, Videos
   - API endpoints: `/api/v1/instagram/v1/...`

2. **XiaohongshuClient**
   - URL patterns: `xiaohongshu.com`, `xhslink.com`
   - Supports: Images, Videos
   - API endpoints: `/api/v1/xiaohongshu/app/v1/...`

### Adding New Platforms

To add a new platform, create a new client class in `platforms.py`:

```python
@register_platform("douyin", ["douyin.com", "iesdouyin.com"])
class DouyinClient(PlatformAPIClient):
    def extract_username_from_url(self, url: str) -> Optional[str]:
        # Implementation
        pass

    async def get_user_posts(self, profile_url: str, max_posts: Optional[int] = None) -> List[Dict]:
        # Implementation
        pass

    def extract_media_from_post(self, post: Dict, media_types: List[MediaType] = None) -> List[MediaItem]:
        # Implementation
        pass
```

### Data Flow

1. Parse CLI arguments and detect platform from URL
2. Get appropriate platform client
3. Fetch user posts via TikHub API (with pagination)
4. Extract media items based on requested media types
5. Download media concurrently with deduplication
6. Output organized by: `output/{platform}/{username}/{post_id}_{index}.{ext}`

## Important Notes

### API Rate Limiting
- TikHub API calls are limited to 5 concurrent requests per client
- Download concurrency is configurable (default: 10, via `--concurrent`)

### Content Deduplication
- MD5 hashing prevents downloading duplicate content
- Hashes are stored in memory during execution

### Output Organization
- New format: `output/{platform}/{username}/{post_id}_{index}.{ext}`
- Legacy format: `output/{username}/{post_id}_{index}.{ext}`

### Environment Variables
- `TIKHUB_API_KEY` - TikHub API key (required)
- `HENGHENGMAO_API_KEY` - Legacy alias for TikHub API key

### Credential Security
- Never commit API keys to version control
- Use environment variables in production
