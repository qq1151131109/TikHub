# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Instagram 图片批量下载器 (Instagram Image Batch Downloader) - A Python tool for downloading images from Instagram accounts using the HengHengMao API. The tool supports concurrent downloads, content deduplication, and incremental downloading.

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

3. Configure API credentials (choose one method):
   - **Environment variables (recommended)**:
     ```bash
     export HENGHENGMAO_USER_ID="your_user_id"
     export HENGHENGMAO_SECRET_KEY="your_secret_key"
     ```
   - **Config file**:
     ```bash
     cp config/config.example.json config/config.json
     # Edit config/config.json with your credentials
     ```

4. Prepare account list:
```bash
cp data/accounts.example.json data/accounts.json
# Edit data/accounts.json to add accounts to download
```

## Common Commands

### Running the Downloader

```bash
# Download from multiple accounts (from file)
python download_instagram_images.py --accounts-file data/accounts.json

# Download from a single account
python download_instagram_images.py --account-url "https://www.instagram.com/username/"

# Limit posts per account
python download_instagram_images.py --accounts-file data/accounts.json --max-posts 50

# Skip confirmation prompt
python download_instagram_images.py --accounts-file data/accounts.json -y

# Adjust concurrent downloads
python download_instagram_images.py --accounts-file data/accounts.json --concurrent 20

# Re-download existing files (no skip)
python download_instagram_images.py --accounts-file data/accounts.json --no-skip-existing
```

### Testing Individual Components

Since this is a single-script project without a test suite, test changes by:
1. Using `--account-url` with a single test account
2. Using `--max-posts 5` to limit the scope
3. Using a separate `--output-dir` to avoid affecting production downloads

Example:
```bash
python download_instagram_images.py --account-url "https://www.instagram.com/natgeo/" --max-posts 5 --output-dir test_output
```

## Architecture

### Core Components

The application is structured around three main classes in `download_instagram_images.py`:

1. **HenghengMaoAPI** (lines 38-168)
   - Handles all Instagram API interactions via HengHengMao API
   - Uses `aiohttp` for async HTTP requests
   - Has built-in rate limiting with `asyncio.Semaphore(5)` for API calls
   - Key methods:
     - `get_profile_posts()`: Fetches posts from an Instagram profile
     - `extract_images_from_post()`: Extracts image URLs from various post formats (single images, carousels, reels)

2. **ImageDownloader** (lines 170-256)
   - Manages concurrent image downloads
   - Implements content-based deduplication using MD5 hashes
   - Controls download concurrency with `asyncio.Semaphore` (default: 10)
   - Key features:
     - Tracks downloaded content via `downloaded_hashes` to avoid duplicate content
     - Generates organized output paths: `output/{username}/{post_id}_{index}.{ext}`
     - Supports skipping existing files for incremental downloads

3. **Account List Loading** (lines 272-329)
   - `load_accounts_from_file()`: Supports three account list formats:
     - JSON array: `[{"username": "...", "url": "..."}, ...]`
     - Categorized JSON: `{"category1": [...], "category2": [...]}`
     - Plain text: One URL or username per line

### Async Architecture

The application uses Python's `asyncio` for concurrent operations:
- API requests are limited to 5 concurrent calls
- Image downloads support configurable concurrency (default: 10, adjustable via `--concurrent`)
- Uses `asyncio.as_completed()` for processing downloads as they finish
- Context managers (`async with`) ensure proper resource cleanup

### Data Flow

1. Load accounts from file or single URL
2. For each account:
   - Fetch all posts via API (respecting `--max-posts` limit)
   - Extract image URLs from each post (handles multiple post types)
   - Queue all images for download
3. Download images concurrently:
   - Check if file exists (skip if `--no-skip-existing` not set)
   - Download image content
   - Check MD5 hash for content deduplication
   - Save to `output/{username}/{post_id}_{index}.{ext}`
4. Display summary statistics

### Configuration Priority

Credentials are loaded with this priority:
1. Environment variables (`HENGHENGMAO_USER_ID`, `HENGHENGMAO_SECRET_KEY`)
2. Config file (`config/config.json`)

### Post Type Handling

The `extract_images_from_post()` method handles multiple Instagram post formats:
- Direct `images` array (most common from HengHengMao API)
- `carousel_media` for multi-image posts (checks `media_type == 1` for images)
- Single image posts (`image_url` or `display_url`)
- Fallback to `thumbnail_url` if no other images found

## File Structure

```
.
├── download_instagram_images.py  # Main application (592 lines)
├── requirements.txt              # Python dependencies (aiohttp, aiofiles, tqdm)
├── config/
│   ├── config.json              # User config (git-ignored)
│   └── config.example.json      # Config template
└── data/
    ├── accounts.json            # Account list (git-ignored)
    ├── accounts.example.json    # Simple JSON array format
    ├── accounts_categorized.example.json  # Categorized format
    └── accounts_simple.example.txt        # Plain text format
```

## Important Notes

### API Rate Limiting
- HengHengMao API calls are limited to 5 concurrent requests (hardcoded in `HenghengMaoAPI.__init__`)
- If you encounter rate limiting issues, this limit is in line 46

### Content Deduplication
- The tool uses MD5 hashing to detect duplicate image content across different posts
- This prevents downloading the same image multiple times even if it appears in multiple posts
- Hashes are stored in memory during execution (not persisted between runs)

### Credential Security
- Never commit `config/config.json` or `.env` files with real credentials
- These files are in `.gitignore` for protection
- Always use environment variables in production/shared environments

### Output Organization
- Images are organized by username: `output/{username}/`
- Filename format: `{post_id}_{index:02d}.{ext}`
- The index allows multiple images from the same post to coexist
