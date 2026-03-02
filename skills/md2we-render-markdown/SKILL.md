---
name: md2we-render-markdown
version: "1.0.0"
description: Render Markdown into WeChat-ready HTML with MD2WE themes, code highlighting, font size, and background options. Use when the user asks to convert Markdown to styled HTML, preview theme output, or generate WeChat-compatible article HTML from a file or draft.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
user-invocable: true
triggers:
  - "/md2we-render"
  - "render markdown with md2we"
  - "convert markdown to wechat html"
  - "用 md2we 渲染 markdown"
  - "生成微信公众号 html"
  - "生成微信排版 html"
---

# md2we-render-markdown

Use MD2WE's online `/api/convert` endpoint to render Markdown into styled HTML.

## When To Use

Use this skill when the user wants to:

- Convert a Markdown file into WeChat-compatible HTML
- Compare MD2WE theme variants
- Render with a specific code theme, font size, or background
- Save rendered HTML to disk for later publishing

## Service Check

Default base URL:

```bash
export MD2WE_BASE_URL="${MD2WE_BASE_URL:-https://md2we.com}"
```

Before rendering, verify the service:

```bash
curl -sS "${MD2WE_BASE_URL}/api/health"
```

If the service is unavailable and the current repo is MD2WE, start it from the repo root:

```bash
python3 app.py
```

Then point the base URL to the local service and retry `/api/health`:

```bash
export MD2WE_BASE_URL="http://127.0.0.1:5566"
curl -sS "${MD2WE_BASE_URL}/api/health"
```

## API Call Pattern

Basic render:

```bash
curl -sS "${MD2WE_BASE_URL}/api/convert" \
  -H "Content-Type: application/json" \
  -d @<(jq -Rs '{
    markdown: .,
    theme: "default",
    code_theme: "github",
    font_size: "medium",
    background: "warm"
  }' article.md)
```

Choose render options:

```bash
curl -sS "${MD2WE_BASE_URL}/api/convert" \
  -H "Content-Type: application/json" \
  -d @<(jq -Rs '{
    markdown: .,
    theme: "tech",
    code_theme: "monokai",
    font_size: "large",
    background: "warm"
  }' article.md)
```

Render from stdin:

```bash
cat article.md | jq -Rs '{
  markdown: .,
  theme: "default",
  code_theme: "github",
  font_size: "medium",
  background: "warm"
}' | curl -sS "${MD2WE_BASE_URL}/api/convert" \
  -H "Content-Type: application/json" \
  -d @-
```

Write the returned `html` field to a file:

```bash
response=$(curl -sS "${MD2WE_BASE_URL}/api/convert" \
  -H "Content-Type: application/json" \
  -d @<(jq -Rs '{
    markdown: .,
    theme: "default",
    code_theme: "github",
    font_size: "medium",
    background: "warm"
  }' article.md))

echo "$response" | jq -e '.success == true' >/dev/null || {
  echo "$response" | jq .
  exit 1
}

echo "$response" | jq -r '.html' > article.html
```

## Supported Values

```text
theme: default|sport|chinese|cyberpunk|ocean|forest|sunset|lavender|coffee|minimalist|tech|retro|government|finance
code_theme: github|monokai|dracula|atom-one-dark|atom-one-light|vs|xcode|stackoverflow-light
font_size: small|medium|large
background: warm|grid|none
```

## Result Handling

- Read the `html` field from the JSON response.
- If the user asked for a file, write only the `html` field to disk.
- If the user asked for a quick preview only, inspect the JSON response and summarize the chosen settings.
- If rendering fails, surface the server error directly. Do not guess at broken HTML.
