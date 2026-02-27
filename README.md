# MD2HTML - Markdown 转微信公众号工具

一个简洁优雅的 Markdown 转微信公众号 HTML 工具，支持丰富的主题和 API 调用。

## 功能特点

- 🎨 **12种精美主题** - 默认、运动风、中国风、赛博朋克、海洋风、森林风、日落风、薰衣草、咖啡风、极简风、科技风、复古风
- 💻 **8种代码高亮** - GitHub、Monokai、Dracula、Atom One Dark 等
- 📝 **实时预览** - 边写边看，所见即所得
- 📋 **一键复制** - 直接复制到微信公众号编辑器
- 🔌 **API 支持** - 支持通过 API 调用进行批量转换
- 💾 **自动保存** - 内容自动保存到本地存储

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动服务

```bash
python app.py
```

访问 http://localhost:5555 即可使用。

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

返回所有可用的主题、代码高亮、字体大小和背景配置。

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
- `Esc` - 关闭设置面板

## 技术栈

- 后端：Python Flask
- 前端：原生 HTML/CSS/JS
- Markdown 解析：Python-Markdown
- 代码高亮：Highlight.js

## License

MIT
