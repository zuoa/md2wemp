# MD2WE

将 Markdown 转成适合微信公众号发布的排版内容。

MD2WE 是一个面向微信公众号场景的 Markdown 编辑器，提供实时预览、主题排版、 Mermaid 图表、AI 创作辅助、分享页生成和公众号草稿推送。

## Highlights

- Markdown 实时编辑与预览
- 12 种排版主题和 8 种代码高亮方案
- Mermaid 图表渲染
- AI 标题建议、摘要生成和文章配图
- 复制 HTML、下载 HTML、长图导出
- 公开分享页、二维码和独立图片 URL
- 一键推送到微信公众号草稿箱
- 浏览器本地自动保存

## Quick Start

### Local

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 app.py
```

Open `http://localhost:5566`

健康检查：

```bash
curl http://localhost:5566/api/health
```

### Docker Compose

默认使用 Docker named volume 持久化 `/app/data` 和 `/app/instance`：

```bash
docker compose pull
docker compose up -d
```

### Docker

```bash
docker pull ghcr.io/zuoa/md2we:latest

docker run -d \
  --name md2we \
  -p 5566:5566 \
  -v md2we-data:/app/data \
  -v md2we-instance:/app/instance \
  -e SITE_URL=https://md2we.com \
  -e DEFAULT_OG_IMAGE_URL=https://md2we.com/static/og-cover.png \
  ghcr.io/zuoa/md2we:latest
```

如果你需要将分享数据直接映射到宿主机目录：

```bash
mkdir -p data/shares
chmod 0777 data data/shares
```

否则容器内非 root 用户可能无法写入 `/app/data/shares`。

## Configuration

默认情况下，不需要在服务端配置 AI 环境变量。可以直接在页面里填写，本地配置优先于服务端环境变量。

### AI

```bash
OPENAI_API_KEY=your_key_here
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
OPENAI_TEXT_MODEL=gemini-2.5-flash
OPENAI_IMAGE_TOOL_MODEL=gemini-2.5-flash-image
```

### Site

```bash
SITE_URL=https://md2we.com
DEFAULT_OG_IMAGE_URL=https://md2we.com/static/og-cover.png
SITE_NAME=MD2WE
SITE_DESCRIPTION=MD2WE 是一个面向微信公众号排版的 Markdown 编辑器
SHARE_STORAGE_DIR=/app/data/shares
```

- `SITE_URL` 用于生成分享页、二维码、`canonical`、`robots.txt`、`sitemap.xml` 和 AI 配图 URL
- `SHARE_STORAGE_DIR` 用于显式指定分享页 JSON 和 AI 配图的存储目录

### AI Config Private Key

后端会自动生成 RSA 私钥，默认保存在：

```bash
instance/ai_config_private_key.pem
```

也可以显式提供：

```bash
export AI_CONFIG_PRIVATE_KEY_PEM='-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n'
```

生成环境变量值：

```bash
python3 scripts/generate_ai_crypto_key.py
```

## Core Workflows

### Share Pages

- `POST /api/share` 生成公开分享页
- 分享页内容保存在 `data/shares/*.json`
- AI 配图保存在 `data/shares/images/`
- 分享页底部显示当前链接二维码和 `Powered by MD2WE`

### WeChat Draft Publishing

- 支持保存 `AppKey / AppSecret`、作者、原文链接到浏览器本地
- 标题默认取 Markdown 第一条 `# H1`
- 摘要默认取正文前 120 个字符
- 支持 AI 标题、摘要和封面生成
- 自动上传正文图片和封面图到微信素材域名

### SEO

- 首页和分享页的 `title`、`description`、`canonical`
- Open Graph 和 Twitter Card
- `WebApplication` / `Article` 结构化数据
- `/robots.txt`
- `/sitemap.xml`

## API

### `POST /api/convert`

```json
{
  "markdown": "# Hello World\n\nThis is a test.",
  "theme": "default",
  "code_theme": "github",
  "font_size": "medium",
  "background": "warm"
}
```

### `POST /api/share`

根据当前 Markdown 内容生成公开分享页。

### `POST /api/wechat/draft`

将文章推送到微信公众号草稿箱。

### `POST /api/ai/title-suggestions`

```json
{
  "markdown": "# 一篇文章\n\n正文内容"
}
```

### `POST /api/ai/summary`

```json
{
  "markdown": "# 一篇文章\n\n正文内容"
}
```

### `POST /api/ai/generate-image`

```json
{
  "markdown": "# 一篇文章\n\n正文内容",
  "focus_prompt": "科技感、极简插画"
}
```

响应示例：

```json
{
  "success": true,
  "image_url": "https://md2we.com/share/images/ai-20260228183000-ab12cd34ef.png",
  "revised_prompt": "已根据文章内容调整画面重点"
}
```

## Project Structure

```text
.
├── app.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── static/
├── templates/
├── scripts/
├── data/shares/     # 分享页 JSON 与 AI 配图文件
└── instance/        # AI 加密私钥等运行时文件
```

## Development

- `Ctrl/Cmd + S`: 复制 HTML
- `Ctrl/Cmd + ,`: 打开设置
- `Esc`: 关闭设置面板

技术栈：

- Flask
- 原生 HTML / CSS / JavaScript
- Python-Markdown
- Pygments
- Mermaid
- html2canvas
- Gunicorn
- Docker Compose

CI workflow: [`.github/workflows/ci.yml`](.github/workflows/ci.yml)  
Container image: `ghcr.io/zuoa/md2we`

## License

MIT
