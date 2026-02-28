# MD2HTML - Markdown 转微信公众号工具

一个面向微信公众号排版的 Markdown 编辑器，支持丰富主题、Mermaid 图表、AI 创作助手和长图导出。

## 功能特点

- 🎨 **12 种精美主题** - 默认、运动风、中国风、赛博朋克、海洋风、森林风、日落风、薰衣草、咖啡风、极简风、科技风、复古风
- 💻 **8 种代码高亮** - GitHub、Monokai、Dracula、Atom One Dark 等
- 📈 **Mermaid 图表支持** - 直接在 Markdown 中写 `mermaid` 代码块，预览自动渲染为 SVG
- 🤖 **AI 创作助手** - 支持标题建议、文章摘要、文章配图生成
- ⏱️ **增强统计** - 汉字数、英文词数、预计阅读时间、标题数、图片数、行数
- 🖼️ **导出长图** - 将当前预览一键导出为 PNG 长图
- 📋 **一键复制 / 下载 HTML** - 直接复制到微信公众号编辑器或导出 HTML
- 💾 **自动保存** - 内容自动保存到本地存储

## 快速开始

### 安装依赖

```bash
python3 -m pip install -r requirements.txt
```

### 启动服务

```bash
python3 app.py
```

访问 `http://localhost:5566` 即可使用。

### 可选：启用 AI 能力

如果需要标题建议、摘要生成、AI 配图，请配置 OpenAI 环境变量：

```bash
export OPENAI_API_KEY=your_key_here
```

可选覆盖项：

```bash
export OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
export OPENAI_TEXT_MODEL=gemini-2.5-flash
export OPENAI_IMAGE_TOOL_MODEL=imagen-4.0-generate-001
```

也可以直接在网页的“创作助手 > AI 配置”中填写：

- `Base URL`
- `文本模型`
- `图片模型`
- `API Key`

页面配置优先于服务端环境变量，且仅保存在当前浏览器本地。

## API 接口

### 转换接口

**POST** `/api/convert`

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
  "theme": { "name": "默认主题", "colors": [...] },
  "font_size": { "base": "15px", "name": "中号字体(15px)" },
  "background": { "name": "温暖米色", "color": "#FDF6E3" }
}
```

### 获取配置

**GET** `/api/themes`

返回所有可用的主题、代码高亮、字体大小和背景配置，以及当前是否启用 AI。

### AI 标题建议

**POST** `/api/ai/title-suggestions`

请求体：

```json
{
  "markdown": "# 一篇文章\n\n正文内容"
}
```

### AI 摘要

**POST** `/api/ai/summary`

请求体：

```json
{
  "markdown": "# 一篇文章\n\n正文内容"
}
```

### AI 配图

**POST** `/api/ai/generate-image`

请求体：

```json
{
  "markdown": "# 一篇文章\n\n正文内容",
  "focus_prompt": "科技感、极简插画"
}
```

## 参数说明

### theme (主题)

| 值 | 名称 | 描述 |
|---|------|------|
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

### code_theme (代码高亮)

- github
- monokai
- dracula
- atom-one-dark
- atom-one-light
- vs
- xcode
- stackoverflow-light

### font_size (字体大小)

| 值 | 基础字号 | 描述 |
|---|---------|------|
| small | 14px | 信息密度高，适合精细阅读 |
| medium | 15px | 日常阅读，平衡视觉 |
| large | 16px | 舒适阅读，视觉友好 |

### background (背景)

| 值 | 名称 | 描述 |
|---|------|------|
| warm | 温暖米色 | 经典微信风格 |
| grid | 方格白底 | 简约方格纹理 |
| none | 无背景 | 透明背景 |

## 键盘快捷键

- `Ctrl/Cmd + S` - 复制 HTML
- `Ctrl/Cmd + ,` - 打开设置
- `Esc` - 关闭设置面板

## 技术栈

- 后端：Python Flask
- 前端：原生 HTML/CSS/JS
- Markdown 解析：Python-Markdown
- 代码高亮：Pygments
- 图表渲染：Mermaid
- 长图导出：html2canvas

## License

MIT
