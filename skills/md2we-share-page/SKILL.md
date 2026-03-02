---
name: md2we-share-page
version: "1.0.0"
description: Create MD2WE share pages and upload article images. Use when the user asks to generate a public article link, create a QR-ready share page, upload an image and insert Markdown, or prepare hosted assets for a WeChat article.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
user-invocable: true
triggers:
  - "/md2we-share"
  - "create md2we share page"
  - "generate share link with md2we"
  - "upload image with md2we"
  - "生成 md2we 分享页"
  - "生成分享链接和二维码"
  - "上传图片并生成 markdown"
---

# md2we-share-page

Use MD2WE's online share and image upload APIs.

## When To Use

Use this skill when the user wants to:

- Generate a public share page from Markdown
- Get a share URL and QR-ready payload
- Upload a local image into MD2WE storage
- Turn a local image into Markdown syntax

## Service Check

```bash
export MD2WE_BASE_URL="${MD2WE_BASE_URL:-https://md2we.com}"
curl -sS "${MD2WE_BASE_URL}/api/health"
```

If needed, start the local MD2WE server from the repo root:

```bash
python3 app.py
```

Then point the base URL to the local service and retry `/api/health`:

```bash
export MD2WE_BASE_URL="http://127.0.0.1:5566"
curl -sS "${MD2WE_BASE_URL}/api/health"
```

## API Call Pattern

Create a share page:

```bash
curl -sS "${MD2WE_BASE_URL}/api/share" \
  -H "Content-Type: application/json" \
  -d @<(jq -Rs '{
    markdown: .,
    theme: "default",
    code_theme: "github",
    font_size: "medium",
    background: "warm"
  }' article.md)
```

Upload an image and get Markdown:

```bash
curl -sS "${MD2WE_BASE_URL}/api/upload/image" \
  -F "image=@./cover.png"
```

## Notes

- Each `share` call creates a new share page.
- Uploaded images must be JPG, PNG, WebP, or GIF, and under 10 MB.
- Read `share_url`, `share_id`, `qr_svg`, `image_url`, and `markdown` from the JSON result.
- If the user wants the Markdown inserted into a file, update the target file after the upload succeeds.
