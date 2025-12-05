#!/bin/bash
# Instagram 图片下载器 - 快速设置脚本

set -e

echo "🚀 Instagram 图片下载器 - 快速设置"
echo "======================================"

# 检查 Python 版本
echo ""
echo "📌 检查 Python 版本..."
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 python3，请先安装 Python 3.8+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "✅ Python 版本: $PYTHON_VERSION"

# 创建虚拟环境
echo ""
echo "📦 创建虚拟环境..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "✅ 虚拟环境已创建"
else
    echo "⚠️  虚拟环境已存在，跳过"
fi

# 激活虚拟环境
echo ""
echo "🔧 激活虚拟环境..."
source .venv/bin/activate

# 安装依赖
echo ""
echo "📥 安装依赖..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "✅ 依赖安装完成"

# 创建配置文件
echo ""
echo "⚙️  创建配置文件..."

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "✅ .env 文件已创建，请编辑填入你的 API 凭据"
else
    echo "⚠️  .env 文件已存在，跳过"
fi

if [ ! -f "config/config.json" ]; then
    cp config/config.example.json config/config.json
    echo "✅ config.json 文件已创建"
else
    echo "⚠️  config.json 文件已存在，跳过"
fi

# 创建账号列表
echo ""
echo "📋 创建账号列表..."

if [ ! -f "data/accounts.json" ]; then
    cp data/accounts.example.json data/accounts.json
    echo "✅ accounts.json 文件已创建，请编辑添加你要下载的账号"
else
    echo "⚠️  accounts.json 文件已存在，跳过"
fi

# 创建输出目录
echo ""
echo "📁 创建输出目录..."
mkdir -p output
echo "✅ 输出目录已创建"

# 完成
echo ""
echo "======================================"
echo "✅ 设置完成！"
echo ""
echo "📝 接下来的步骤："
echo "1. 编辑 .env 文件，填入你的 HengHengMao API 凭据："
echo "   export HENGHENGMAO_USER_ID='your_user_id'"
echo "   export HENGHENGMAO_SECRET_KEY='your_secret_key'"
echo ""
echo "2. 编辑 data/accounts.json 文件，添加要下载的账号"
echo ""
echo "3. 加载环境变量："
echo "   source .env"
echo ""
echo "4. 开始下载："
echo "   python download_instagram_images.py --accounts-file data/accounts.json"
echo ""
echo "💡 提示: 使用 'python download_instagram_images.py --help' 查看更多选项"
echo "======================================"
