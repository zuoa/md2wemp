---
name: md2we-wechat-draft
version: "1.0.0"
description: Push Markdown articles to a WeChat Official Account draft box through MD2WE. Use when the user asks to publish or prepare a 微信公众号草稿, upload cover content through the MD2WE pipeline, or run the final WeChat draft payload from Markdown.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
user-invocable: true
triggers:
  - "/md2we-wechat-draft"
  - "publish wechat draft with md2we"
  - "push article to wechat draft"
  - "用 md2we 推送公众号草稿"
  - "发布到公众号草稿箱"
  - "推送微信公众号草稿"
---

# md2we-wechat-draft

Use MD2WE's online `/api/wechat/draft` endpoint to submit a draft article.

## When To Use

Use this skill when the user wants to:

- Push a Markdown article to WeChat Official Account drafts
- Override title, digest, author, or source URL before publishing
- Reuse the article's first image or an explicit cover image URL/path
- Control cover display and comment switches in the draft payload

## Service Check

```bash
export MD2WE_BASE_URL="${MD2WE_BASE_URL:-https://md2we.com}"
curl -sS "${MD2WE_BASE_URL}/api/health"
```

If the local service is not running and the repo contains `app.py`, start it first:

```bash
python3 app.py
```

Then point the base URL to the local service and retry `/api/health`:

```bash
export MD2WE_BASE_URL="http://127.0.0.1:5566"
curl -sS "${MD2WE_BASE_URL}/api/health"
```

## API Call Pattern

Minimal draft push:

```bash
jq -Rs --arg app_key "$WECHAT_APP_KEY" --arg app_secret "$WECHAT_APP_SECRET" '{
  markdown: .,
  theme: "default",
  code_theme: "github",
  font_size: "medium",
  background: "warm",
  wechat_config: {
    app_key: $app_key,
    app_secret: $app_secret
  },
  meta: {}
}' article.md | curl -sS "${MD2WE_BASE_URL}/api/wechat/draft" \
  -H "Content-Type: application/json" \
  -d @-
```

With metadata:

```bash
jq -Rs \
  --arg app_key "$WECHAT_APP_KEY" \
  --arg app_secret "$WECHAT_APP_SECRET" \
  --arg title "新的标题" \
  --arg digest "80 字以内的摘要" \
  --arg author "作者名" \
  --arg content_source_url "https://example.com/article" \
  --arg cover_image "./cover.png" \
  '{
    markdown: .,
    theme: "default",
    code_theme: "github",
    font_size: "medium",
    background: "warm",
    wechat_config: {
      app_key: $app_key,
      app_secret: $app_secret
    },
    meta: {
      title: $title,
      digest: $digest,
      author: $author,
      content_source_url: $content_source_url,
      cover_image: $cover_image,
      show_cover_pic: 1,
      need_open_comment: 1,
      only_fans_can_comment: 0
    }
  }' article.md | curl -sS "${MD2WE_BASE_URL}/api/wechat/draft" \
  -H "Content-Type: application/json" \
  -d @-
```

## Payload Fields

```text
theme: default|sport|chinese|cyberpunk|ocean|forest|sunset|lavender|coffee|minimalist|tech|retro|government|finance
code_theme: github|monokai|dracula|atom-one-dark|atom-one-light|vs|xcode|stackoverflow-light
font_size: small|medium|large
background: warm|grid|none
meta.title: optional
meta.digest: optional
meta.author: optional
meta.content_source_url: optional
meta.cover_image: optional, path or URL resolvable by MD2WE
meta.show_cover_pic: 0|1
meta.need_open_comment: 0|1
meta.only_fans_can_comment: 0|1
```

## Safety

- Never write `AppSecret` into files or commit history.
- Prefer environment variables for `WECHAT_APP_KEY` and `WECHAT_APP_SECRET`.
- If the API returns an error, report it exactly. Do not retry with mutated credentials.

## Result Handling

Read from the JSON response:

- `media_id`
- `title`
- `uploaded_image_count`

Report those back to the user after a successful draft push.
