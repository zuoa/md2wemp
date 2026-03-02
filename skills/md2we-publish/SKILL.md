---
name: md2we-publish
version: "1.0.0"
description: One-click MD2WE workflow that generates a title, summary, cover image, validates render output, and pushes a Markdown article to a WeChat Official Account draft. Use when the user wants to publish a Markdown article to 微信公众号草稿箱 in one pass with MD2WE.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
user-invocable: true
triggers:
  - "/md2we-publish"
  - "md2we publish"
  - "publish md2we draft"
  - "一键发布公众号草稿"
  - "生成标题摘要封面并推送草稿"
---

# md2we-publish

Use `https://md2we.com` APIs to complete the full publishing flow in one pass:

1. Generate title suggestions
2. Pick the best title automatically
3. Generate a digest
4. Generate a cover image
5. Render the article HTML
6. Push the article to WeChat Official Account drafts

## When To Use

Use this skill when the user wants one command-level workflow instead of calling multiple MD2WE skills separately.

## Required Inputs

- A Markdown article, usually a local `.md` file
- `WECHAT_APP_KEY`
- `WECHAT_APP_SECRET`

Optional:

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_TEXT_MODEL`
- `OPENAI_IMAGE_TOOL_MODEL`
- `WECHAT_AUTHOR`
- `WECHAT_SOURCE_URL`

## Service Base URL

```bash
export MD2WE_BASE_URL="${MD2WE_BASE_URL:-https://md2we.com}"
curl -sS "${MD2WE_BASE_URL}/api/health"
```

## Default Policy

Unless the user says otherwise, follow this policy:

- Use the first returned title suggestion as the final title
- Use the generated summary as the WeChat digest
- Use the generated image URL as `meta.cover_image`
- Render with `theme=default`, `code_theme=github`, `font_size=medium`, `background=warm`
- Publish with `show_cover_pic=1`, `need_open_comment=1`, `only_fans_can_comment=0`
- Do not rewrite the Markdown file unless the user explicitly asks for file edits

## Workflow

### Step 1: Generate title suggestions

```bash
curl -sS "${MD2WE_BASE_URL}/api/ai/title-suggestions" \
  -H "Content-Type: application/json" \
  -d @<(jq -Rs '{
    markdown: .,
    focus_prompt: "适合微信公众号传播，准确，不标题党"
  }' article.md)
```

Read `.suggestions[0]` as the final title.

### Step 2: Generate summary

```bash
curl -sS "${MD2WE_BASE_URL}/api/ai/summary" \
  -H "Content-Type: application/json" \
  -d @<(jq -Rs '{
    markdown: .,
    focus_prompt: "适合作为微信公众号摘要，信息密度高"
  }' article.md)
```

Read `.summary` as the final digest.

### Step 3: Generate cover image

```bash
curl -sS "${MD2WE_BASE_URL}/api/ai/generate-image" \
  -H "Content-Type: application/json" \
  -d @<(jq -Rs '{
    markdown: .,
    focus_prompt: "适合微信公众号头图，克制，现代 editorial illustration"
  }' article.md)
```

Read `.image_url` as the final cover image URL.

### Step 4: Render HTML

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

This step validates that the article can be rendered successfully before draft publishing.

### Step 5: Push draft

```bash
jq -Rs \
  --arg app_key "$WECHAT_APP_KEY" \
  --arg app_secret "$WECHAT_APP_SECRET" \
  --arg title "$FINAL_TITLE" \
  --arg digest "$FINAL_DIGEST" \
  --arg author "${WECHAT_AUTHOR:-}" \
  --arg content_source_url "${WECHAT_SOURCE_URL:-}" \
  --arg cover_image "$FINAL_COVER_URL" \
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

## Agent Execution Rules

When this skill is triggered, the agent should execute the workflow in this order:

1. Health check
2. Title generation
3. Summary generation
4. Cover generation
5. HTML render validation
6. Draft publishing

If any step fails, stop immediately and report that step's API error. Do not silently skip failed steps.

## Output To User

After success, report:

- Final title
- Final digest
- Cover image URL
- Draft `media_id`
- Uploaded image count

## Optional AI Config

If the server-side AI config is not available, pass explicit `ai_config`:

```bash
curl -sS "${MD2WE_BASE_URL}/api/ai/summary" \
  -H "Content-Type: application/json" \
  -d @<(jq -Rs \
    --arg api_key "$OPENAI_API_KEY" \
    --arg base_url "${OPENAI_BASE_URL:-https://generativelanguage.googleapis.com/v1beta/openai}" \
    --arg text_model "${OPENAI_TEXT_MODEL:-gemini-2.5-flash}" \
    --arg image_model "${OPENAI_IMAGE_TOOL_MODEL:-gemini-2.5-flash-image}" \
    '{
      markdown: .,
      focus_prompt: "适合作为微信公众号摘要，信息密度高",
      ai_config: {
        text: {
          api_key: $api_key,
          base_url: $base_url,
          model: $text_model
        },
        image: {
          api_key: $api_key,
          base_url: $base_url,
          model: $image_model
        }
      }
    }' article.md)
```

Apply the same `ai_config` pattern to title and image generation when needed.
