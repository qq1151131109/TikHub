# Instagram 图片批量下载器

基于 HengHengMao API 的 Instagram 图片批量下载工具，支持下载多个账号的所有图片。

## 功能特点

- ✅ 批量下载多个 Instagram 账号的所有图片
- ✅ 支持普通帖子和 Reels 的图片
- ✅ 并发下载，速度快
- ✅ 智能去重（基于文件内容）
- ✅ 增量下载，避免重复下载已存在的文件
- ✅ 支持多种账号列表格式（JSON、文本）
- ✅ 进度条显示，实时查看下载状态
- ✅ 自动重试和错误处理

## 快速开始

### 1. 安装依赖

```bash
cd /Users/shenglin/Developer/code/instagram-image-downloader
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置 API 凭据

**方式 1: 使用环境变量（推荐）**

```bash
export HENGHENGMAO_USER_ID="your_user_id"
export HENGHENGMAO_SECRET_KEY="your_secret_key"
```

**方式 2: 使用配置文件**

```bash
cp config/config.example.json config/config.json
# 编辑 config/config.json，填入你的凭据
```

### 3. 准备账号列表

**方式 1: JSON 数组格式**

```bash
cp data/accounts.example.json data/accounts.json
# 编辑 data/accounts.json，添加你要下载的账号
```

**方式 2: 分类格式（推荐）**

```bash
cp data/accounts_categorized.example.json data/accounts.json
# 按类别组织账号
```

**方式 3: 简单文本格式**

```bash
cp data/accounts_simple.example.txt data/accounts.txt
# 每行一个 URL 或用户名
```

### 4. 开始下载

```bash
# 批量下载（从文件）
python download_instagram_images.py --accounts-file data/accounts.json

# 下载单个账号
python download_instagram_images.py --account-url "https://www.instagram.com/natgeo/"

# 限制每个账号下载的帖子数
python download_instagram_images.py --accounts-file data/accounts.json --max-posts 50

# 跳过确认提示
python download_instagram_images.py --accounts-file data/accounts.json -y
```

## 使用说明

### 命令行参数

```
必选参数（二选一）:
  --account-url URL          下载单个账号
  --accounts-file FILE       批量下载多个账号

可选参数:
  --output-dir DIR           输出目录（默认: output）
  --config FILE              配置文件路径（默认: config/config.json）
  --max-posts N              每个账号最多下载的帖子数（默认: 无限制）
  --concurrent N             并发下载数（默认: 10）
  --no-skip-existing         不跳过已存在的文件（重新下载）
  --yes, -y                  跳过确认提示
```

### 账号列表格式

支持三种格式：

**1. JSON 数组格式**
```json
[
  {
    "username": "natgeo",
    "url": "https://www.instagram.com/natgeo/"
  },
  {
    "username": "instagram",
    "url": "https://www.instagram.com/instagram/"
  }
]
```

**2. 分类 JSON 格式**
```json
{
  "摄影": [
    {
      "username": "natgeo",
      "url": "https://www.instagram.com/natgeo/"
    }
  ],
  "科技": [
    "https://www.instagram.com/tech/"
  ]
}
```

**3. 纯文本格式**
```text
https://www.instagram.com/natgeo/
https://www.instagram.com/instagram/
natgeo
instagram
```

### 输出目录结构

```
output/
├── natgeo/
│   ├── post_id_00.jpg
│   ├── post_id_01.jpg
│   └── ...
├── instagram/
│   ├── post_id_00.jpg
│   └── ...
└── ...
```

## 使用示例

### 示例 1: 下载单个账号

```bash
python download_instagram_images.py \
  --account-url "https://www.instagram.com/natgeo/" \
  --output-dir downloads/natgeo \
  -y
```

### 示例 2: 批量下载多个账号

```bash
python download_instagram_images.py \
  --accounts-file data/accounts.json \
  --output-dir downloads \
  --concurrent 15 \
  -y
```

### 示例 3: 限制下载数量

```bash
# 每个账号只下载最新的 30 个帖子
python download_instagram_images.py \
  --accounts-file data/accounts.json \
  --max-posts 30 \
  -y
```

### 示例 4: 重新下载所有文件

```bash
python download_instagram_images.py \
  --account-url "https://www.instagram.com/natgeo/" \
  --no-skip-existing \
  -y
```

## 常见问题

### Q: 如何获取 HengHengMao API 凭据？

A: 请联系 HengHengMao API 服务提供商获取 `user_id` 和 `secret_key`。

### Q: 下载速度慢怎么办？

A: 可以通过 `--concurrent` 参数调整并发数，例如：

```bash
python download_instagram_images.py \
  --accounts-file data/accounts.json \
  --concurrent 20
```

### Q: 如何避免重复下载？

A: 程序默认会跳过已存在的文件。如果想要重新下载，使用 `--no-skip-existing` 参数。

### Q: 支持下载视频吗？

A: 本工具专注于图片下载。如需下载视频，请使用项目中的其他工具。

### Q: 如何处理下载失败的图片？

A: 程序会在最后的总结中显示失败的图片数量。你可以重新运行程序，它会自动跳过已下载的文件。

## 高级功能

### 内容去重

程序会计算每张图片的 MD5 哈希值，自动跳过内容完全相同的图片，即使它们来自不同的帖子。

### 增量下载

默认情况下，程序会跳过已存在的文件。这意味着你可以：
- 中断后继续下载
- 定期运行脚本获取新内容
- 避免浪费时间和带宽

### 并发控制

程序有两级并发控制：
1. API 请求并发（内部限制为 5）
2. 图片下载并发（通过 `--concurrent` 参数控制，默认 10）

## 故障排查

### 错误: "缺少 HengHengMao API 凭据"

确保设置了环境变量或配置文件：

```bash
export HENGHENGMAO_USER_ID="your_user_id"
export HENGHENGMAO_SECRET_KEY="your_secret_key"
```

### 错误: "账号文件不存在"

检查文件路径是否正确：

```bash
ls -la data/accounts.json
```

### 下载的图片质量不佳

Instagram API 返回的图片质量取决于 HengHengMao API 的实现。如果需要更高质量，请联系 API 服务提供商。

## 项目结构

```
instagram-image-downloader/
├── download_instagram_images.py  # 主程序
├── requirements.txt              # Python 依赖
├── README.md                     # 本文档
├── config/
│   └── config.example.json      # 配置文件示例
├── data/
│   ├── accounts.example.json                    # 账号列表示例（JSON 数组）
│   ├── accounts_categorized.example.json        # 账号列表示例（分类）
│   └── accounts_simple.example.txt              # 账号列表示例（纯文本）
└── output/                       # 下载的图片（自动创建）
```

## 许可证

本项目仅供个人学习和研究使用。请遵守 Instagram 的服务条款和 HengHengMao API 的使用协议。

## 技术支持

如有问题或建议，请参考原项目文档或联系开发者。

---

**注意**: 请合理使用本工具，尊重内容创作者的版权，不要用于商业目的或大规模爬取。
