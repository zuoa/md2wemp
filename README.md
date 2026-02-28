# MD2HTML - Markdown 转微信公众号工具

一个面向微信公众号排版的 Markdown 编辑器，支持丰富主题、Mermaid 图表、AI 创作助手、文章分享页和公众号草稿推送。

## 功能特点

- 12 种排版主题和 8 种代码高亮方案
- Mermaid 图表渲染
- AI 标题建议、摘要生成、文章配图
- 长图导出、复制 HTML、下载 HTML
- 一键生成分享页和二维码
- 一键推送到微信公众号草稿箱
- 浏览器本地自动保存

## 项目结构

```text
.
├── app.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── static/
├── templates/
├── scripts/
├── data/shares/     # 分享页持久化数据
└── instance/        # AI 加密私钥等运行时文件
```

## 本地开发

### 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

### 启动服务

```bash
python3 app.py
```

访问 `http://localhost:5566`。

### 健康检查

```bash
curl http://localhost:5566/api/health
```

## Docker 部署

### 方式一：使用 Docker Compose

首次启动前建议先准备持久化目录：

```bash
mkdir -p data/shares instance
```

先拉取线上镜像，再启动：

```bash
docker compose pull
docker compose up -d
```

查看日志：

```bash
docker compose logs -f
```

停止服务：

```bash
docker compose down
```

服务默认监听：

```text
http://localhost:5566
```

## GitHub Actions

仓库现在包含一套可直接启用的 GitHub Actions 工作流：[.github/workflows/ci.yml](/Users/yujian/Code/py/md2html/.github/workflows/ci.yml)。

触发条件：

- `push`
- `pull_request`
- 手动触发 `workflow_dispatch`

工作流会执行两类检查：

- 安装依赖并执行 Python 语法检查
- 构建 Docker 镜像

这套 CI 默认不依赖服务端 `OPENAI_API_KEY`。

### 自动发布镜像

同一个工作流也会自动把镜像发布到 GitHub Container Registry (`ghcr.io`)。

发布条件：

- push 到默认分支时，发布 `latest`、`edge`、分支名和 `sha-*` 标签
- push tag 时，发布 `latest`、对应的 tag 名和 `sha-*` 标签
- pull request 不发布镜像

镜像地址格式：

```text
ghcr.io/<owner>/<repo>
```

当前发布包名是：

```text
ghcr.io/zuoa/md2wemp
```

拉取示例：

```bash
docker pull ghcr.io/zuoa/md2wemp:latest
```

注意：

- 该 workflow 使用 GitHub 自带的 `GITHUB_TOKEN` 推送 GHCR，一般不需要额外配置 Docker 凭证
- 如果仓库是私有仓库，生成的镜像包通常也会是私有的；需要公开时可在 GitHub Packages 页面调整可见性

### 方式二：直接使用 Docker

直接拉取线上镜像：

```bash
docker pull ghcr.io/zuoa/md2wemp:latest
```

启动容器：

```bash
docker run -d \
  --name md2html \
  -p 5566:5566 \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/instance:/app/instance" \
  -e SITE_URL=https://md2we.com \
  -e DEFAULT_OG_IMAGE_URL=https://md2we.com/static/og-cover.png \
  ghcr.io/zuoa/md2wemp:latest
```

### 可选：本地构建镜像

如果你要基于当前工作区代码自行构建，而不是使用 GHCR 上的正式镜像：

```bash
docker build -t md2html:local .
```

## 环境变量

默认情况下，不需要在服务端配置任何 AI 环境变量。直接在页面里的“创作助手 > AI 配置”填写即可，配置只保存在当前浏览器本地。

### 可选：服务端默认 AI 配置

```bash
OPENAI_API_KEY=your_key_here
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
OPENAI_TEXT_MODEL=gemini-2.5-flash
OPENAI_IMAGE_TOOL_MODEL=gemini-2.5-flash-image
```

只有在你希望“容器启动后默认就带一套 AI 配置”时，才需要设置这些环境变量。

也可以在网页中的“创作助手 > AI 配置”里填写：

- `Base URL`
- `文本模型`
- `图片模型`
- `API Key`

页面填写的配置优先于服务端环境变量，并且只保存在当前浏览器本地。

### 可选：SEO 相关配置

```bash
SITE_URL=https://md2we.com
DEFAULT_OG_IMAGE_URL=https://md2we.com/static/og-cover.png
SITE_NAME=MD2WE
SITE_DESCRIPTION=MD2WE 是一个面向微信公众号排版的 Markdown 编辑器
```

说明：

- `SITE_URL` 用于生成稳定的 `canonical`、`robots.txt` 和 `sitemap.xml`
- `DEFAULT_OG_IMAGE_URL` 用于首页和分享页的社交分享卡片图片
- 如果不配置 `SITE_URL`，服务端会退回当前请求域名

### AI 配置加密私钥

为了避免浏览器把 AI `API Key` 明文传给服务端，后端会在首次启动时自动生成一份 RSA 私钥，并默认保存到：

```bash
instance/ai_config_private_key.pem
```

也可以显式通过环境变量提供：

```bash
export AI_CONFIG_PRIVATE_KEY_PEM='-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n'
```

如果需要提前生成一份可复制的环境变量值，可以执行：

```bash
python3 scripts/generate_ai_crypto_key.py
```

说明：

- 后端启动时优先读取 `AI_CONFIG_PRIVATE_KEY_PEM`
- 如果未配置环境变量，会自动读取或创建 `instance/ai_config_private_key.pem`
- 前端会拿到对应公钥，并用它加密 AI 配置
- 后端再使用私钥解密后发起真实 AI 请求
- 该加密只保护浏览器到服务端这一跳，不会加密浏览器本地 `localStorage`

### 可选：Docker Compose 环境变量写法

如果你确实想给服务端预置默认 AI 配置，可以在项目根目录放一个 `.env` 文件，再执行 `docker compose pull && docker compose up -d`：

```bash
OPENAI_API_KEY=your_key_here
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
OPENAI_TEXT_MODEL=gemini-2.5-flash
OPENAI_IMAGE_TOOL_MODEL=gemini-2.5-flash-image
AI_CONFIG_PRIVATE_KEY_PEM=
```

## 持久化目录

- `data/shares/`：保存分享页 JSON 数据
- `instance/`：保存 AI 加密私钥等运行时文件

如果使用 `docker-compose.yml`，这两个目录会自动挂载到容器内：

- `./data -> /app/data`
- `./instance -> /app/instance`

## SEO 支持

项目现在默认包含以下 SEO 基础能力：

- 首页和分享页的 `title`、`description`、`canonical`
- Open Graph 和 Twitter Card 元信息
- `WebApplication` / `Article` 结构化数据
- `robots.txt`
- `sitemap.xml`

相关入口：

- `/robots.txt`
- `/sitemap.xml`

## 公众号草稿推送

在预览区点击“推公众号”即可打开推送面板：

- `AppKey / AppSecret`、作者、原文链接会保存在浏览器 `localStorage`
- 可手动上传一张封面图，推送时优先使用
- 标题默认取 Markdown 第一条 `# H1`
- 摘要默认取正文前 120 个字符，可手动改写
- 如果已配置 AI，可以在推送弹层里生成标题建议、摘要或封面
- 系统会自动上传正文中的图片到微信素材域名
- 系统会自动将正文第一张图片作为封面图上传
- 如果没上传封面且正文没有图片，后端会自动生成一张默认封面

注意：

- 自动封面依赖 Pillow，已包含在依赖中
- 如果微信接口返回 IP 白名单、权限或素材错误，页面会直接显示原始错误信息

## API 接口

### `POST /api/convert`

请求体：

```json
{
  "markdown": "# Hello World\n\nThis is a test.",
  "theme": "default",
  "code_theme": "github",
  "font_size": "medium",
  "background": "warm"
}
```

响应：

```json
{
  "success": true,
  "html": "<section>...</section>",
  "theme": { "name": "默认主题", "colors": [] },
  "font_size": { "base": "15px", "name": "中号字体(15px)" },
  "background": { "name": "温暖米色", "color": "#FDF6E3" }
}
```

### `GET /api/themes`

返回所有可用主题、代码高亮、字号、背景配置，以及当前是否启用 AI。

### `GET /api/health`

返回服务健康状态，适合容器探针和反向代理检查。

### `POST /api/share`

根据当前 Markdown 内容生成一个公开分享页。

### `POST /api/wechat/draft`

请求体：

```json
{
  "markdown": "# 一篇文章\n\n正文内容",
  "theme": "default",
  "code_theme": "github",
  "font_size": "medium",
  "background": "warm",
  "wechat_config": {
    "app_key": "wx1234567890abcdef",
    "app_secret": "your_app_secret"
  },
  "meta": {
    "title": "文章标题",
    "digest": "文章摘要",
    "author": "作者名",
    "content_source_url": "https://example.com/article",
    "cover_image": "data:image/png;base64,..."
  }
}
```

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

## 参数说明

### `theme`

| 值 | 名称 | 描述 |
|---|---|---|
| default | 默认主题 | 简洁优雅，适合通用场景 |
| sport | 运动风 | 活力四射，动感十足 |
| chinese | 中国风 | 传统典雅，国风韵味 |
| cyberpunk | 赛博朋克 | 未来科技，霓虹闪烁 |
| ocean | 海洋风 | 清新淡雅，如沐海风 |
| forest | 森林风 | 自然清新，绿意盎然 |
| sunset | 日落风 | 温暖浪漫，夕阳余晖 |
| lavender | 薰衣草 | 浪漫优雅，紫韵飘香 |
| coffee | 咖啡风 | 沉稳内敛，醇香浓郁 |
| minimalist | 极简风 | 极简主义，返璞归真 |
| tech | 科技风 | 专业严谨，科技感强 |
| retro | 复古风 | 怀旧复古，时光倒流 |

### `code_theme`

- `github`
- `monokai`
- `dracula`
- `atom-one-dark`
- `atom-one-light`
- `vs`
- `xcode`
- `stackoverflow-light`

### `font_size`

| 值 | 基础字号 | 描述 |
|---|---|---|
| small | 14px | 信息密度高，适合精细阅读 |
| medium | 15px | 日常阅读，平衡视觉 |
| large | 16px | 舒适阅读，视觉友好 |

### `background`

| 值 | 名称 | 描述 |
|---|---|---|
| warm | 温暖米色 | 经典微信风格 |
| grid | 方格白底 | 简约方格纹理 |
| none | 无背景 | 透明背景 |

## 键盘快捷键

- `Ctrl/Cmd + S`：复制 HTML
- `Ctrl/Cmd + ,`：打开设置
- `Esc`：关闭设置面板

## 技术栈

- 后端：Flask
- 前端：原生 HTML / CSS / JavaScript
- Markdown 解析：Python-Markdown
- 代码高亮：Pygments
- 图表渲染：Mermaid
- 长图导出：html2canvas
- 生产部署：Gunicorn + Docker Compose

## License

MIT
