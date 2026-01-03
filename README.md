# TikHub 多平台下载器

基于 TikHub API 的社交媒体内容批量下载工具，支持多平台、多账号的图片和视频下载。

## 支持平台

| 平台 | 图片 | 视频 | 短链接 |
|------|------|------|--------|
| Instagram | ✅ | ✅ | - |
| 小红书 | ✅ | ✅ | ✅ (xhslink.com) |

## 功能特点

- ✅ **多平台支持** - Instagram、小红书，更多平台开发中
- ✅ **自动平台识别** - 根据 URL 自动检测平台类型
- ✅ **批量下载** - 支持多账号批量下载
- ✅ **媒体类型过滤** - 可选择只下载图片或视频
- ✅ **并发下载** - 高速并发，可配置并发数
- ✅ **智能去重** - 基于 MD5 哈希自动跳过重复内容
- ✅ **增量下载** - 自动跳过已存在文件
- ✅ **API Key 自动切换** - 主 Key 额度耗尽时自动切换备用 Key
- ✅ **进度条显示** - 实时查看下载状态
- ✅ **错误重试** - 自动重试失败请求

## 快速开始

### 1. 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置 API 凭据

```bash
# 主 API Key（必需）
export TIKHUB_API_KEY="your_api_key"

# 备用 API Key（可选，主 Key 额度耗尽时自动切换）
export TIKHUB_API_KEY_BACKUP="your_backup_key"
```

> 获取 API Key: https://tikhub.io

### 3. 开始下载

```bash
# 下载单个账号（自动识别平台）
python tikhub_downloader.py --url "https://www.instagram.com/natgeo/"
python tikhub_downloader.py --url "https://www.xiaohongshu.com/user/profile/xxx"

# 只下载图片
python tikhub_downloader.py --url "..." --images-only

# 只下载视频
python tikhub_downloader.py --url "..." --videos-only

# 批量下载（从文件）
python tikhub_downloader.py --accounts-file data/accounts.txt -y

# 限制下载数量
python tikhub_downloader.py --url "..." --max-posts 50 --max-items 100
```

## 命令行参数

```
必选参数（二选一）:
  --url URL                  下载单个账号/页面
  --accounts-file FILE       批量下载多个账号

媒体类型（可选，默认下载图片和视频）:
  --images-only              只下载图片
  --videos-only              只下载视频
  --audio-only               只下载音频
  --media-types TYPES        自定义类型，逗号分隔（image,video,audio）

下载控制:
  --max-posts N              每个账号最多获取的帖子数
  --max-items N              每个账号最多下载的媒体数
  --concurrent N             并发下载数（默认: 10）
  --no-skip-existing         不跳过已存在的文件

其他:
  --output-dir DIR           输出目录（默认: output）
  --config FILE              配置文件路径
  --yes, -y                  跳过确认提示
```

## 账号列表格式

支持多种格式的账号列表文件：

**纯文本格式 (.txt)**
```text
https://www.instagram.com/natgeo/
https://www.instagram.com/nasa/
https://www.xiaohongshu.com/user/profile/xxx
https://xhslink.com/xxx
```

**JSON 数组格式 (.json)**
```json
[
  {"url": "https://www.instagram.com/natgeo/"},
  {"url": "https://www.xiaohongshu.com/user/profile/xxx"}
]
```

**分类 JSON 格式**
```json
{
  "摄影": [
    {"url": "https://www.instagram.com/natgeo/"}
  ],
  "科技": [
    "https://www.instagram.com/nasa/"
  ]
}
```

## 输出目录结构

```
output/
├── instagram/
│   └── natgeo/
│       ├── post_id_00.jpg
│       ├── post_id_01.jpg
│       └── ...
└── xiaohongshu/
    └── username/
        ├── note_id_00.jpg
        ├── note_id_01.mp4
        └── ...
```

## API Key 自动切换

当主 API Key 额度耗尽（HTTP 402）时，程序会自动切换到备用 Key 继续下载：

```bash
# 设置多个备用 Key
export TIKHUB_API_KEY="main_key"
export TIKHUB_API_KEY_BACKUP="backup_key_1"
export TIKHUB_API_KEY_BACKUP_1="backup_key_2"
export TIKHUB_API_KEY_BACKUP_2="backup_key_3"
```

或在配置文件中设置：

```json
{
  "tikhub": {
    "api_key": "main_key",
    "backup_api_keys": ["backup_key_1", "backup_key_2"]
  }
}
```

## 使用示例

### 示例 1: 下载 Instagram 账号的所有图片

```bash
python tikhub_downloader.py \
  --url "https://www.instagram.com/natgeo/" \
  --images-only \
  -y
```

### 示例 2: 下载小红书用户的最新 50 条笔记

```bash
python tikhub_downloader.py \
  --url "https://www.xiaohongshu.com/user/profile/xxx" \
  --max-posts 50 \
  -y
```

### 示例 3: 批量下载多个平台账号

```bash
# 创建账号列表
cat > accounts.txt << EOF
https://www.instagram.com/natgeo/
https://www.instagram.com/nasa/
https://xhslink.com/xxx
EOF

# 批量下载
python tikhub_downloader.py \
  --accounts-file accounts.txt \
  --images-only \
  --concurrent 20 \
  -y
```

### 示例 4: 高并发下载大量内容

```bash
python tikhub_downloader.py \
  --accounts-file data/accounts.txt \
  --concurrent 30 \
  --max-items 1000 \
  -y
```

## 项目结构

```
.
├── tikhub_downloader.py      # 主程序入口
├── downloader/               # 核心模块
│   ├── __init__.py          # 包导出
│   ├── core.py              # 抽象基类、下载器、平台注册
│   └── platforms.py         # 平台实现（Instagram、小红书）
├── requirements.txt          # Python 依赖
├── config/
│   └── config.example.json  # 配置文件示例
├── data/
│   └── accounts.example.json # 账号列表示例
└── output/                   # 下载输出目录
```

## 添加新平台

项目采用模块化架构，添加新平台只需在 `downloader/platforms.py` 中实现：

```python
@register_platform("douyin", ["douyin.com", "iesdouyin.com"])
class DouyinClient(PlatformAPIClient):
    def extract_username_from_url(self, url: str) -> Optional[str]:
        # 实现 URL 解析
        pass

    async def get_user_posts(self, profile_url: str, max_posts: Optional[int] = None) -> List[Dict]:
        # 实现帖子获取
        pass

    def extract_media_from_post(self, post: Dict, media_types: List[MediaType] = None) -> List[MediaItem]:
        # 实现媒体提取
        pass
```

## 常见问题

### Q: 如何获取 TikHub API Key？

A: 访问 https://tikhub.io 注册账号并获取 API Key。

### Q: API 调用费用是多少？

A: TikHub API 按请求计费，约 $0.001/请求。下载媒体文件本身不收费（直接从 CDN 下载）。

### Q: 遇到 HTTP 402 错误怎么办？

A: HTTP 402 表示 API 额度耗尽。可以：
1. 充值当前 API Key
2. 配置备用 API Key 自动切换

### Q: 下载速度慢怎么办？

A: 可以通过 `--concurrent` 参数增加并发数：

```bash
python tikhub_downloader.py --url "..." --concurrent 30
```

### Q: 如何只下载新内容？

A: 程序默认会跳过已存在的文件，直接重新运行即可增量下载。

## 旧版兼容

旧版 Instagram 专用下载器仍可使用：

```bash
python download_instagram_images.py --account-url "https://www.instagram.com/natgeo/"
```

但推荐使用新的统一入口 `tikhub_downloader.py`。

## 许可证

本项目仅供个人学习和研究使用。请遵守各平台的服务条款和 TikHub API 的使用协议。

---

**注意**: 请合理使用本工具，尊重内容创作者的版权，不要用于商业目的或大规模爬取。
