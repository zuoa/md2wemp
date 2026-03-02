---
name: md2we-ai-assistant
version: "1.0.0"
description: Generate title suggestions, summaries, and cover images through MD2WE AI endpoints. Use when the user asks for AI-assisted article titling, concise Chinese summaries, or a share-cover illustration derived from Markdown content.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
user-invocable: true
triggers:
  - "/md2we-ai"
  - "generate md2we ai title"
  - "generate md2we ai summary"
  - "generate md2we ai image"
  - "用 md2we 生成标题"
  - "用 md2we 生成摘要"
  - "用 md2we 生成配图"
  - "生成公众号标题摘要封面"
---

# md2we-ai-assistant

Use MD2WE online AI endpoints for title suggestions, summary generation, and image generation.

## When To Use

Use this skill when the user wants to:

- Generate five Chinese title options from an article draft
- Generate a concise Chinese summary for share cards or WeChat digest text
- Generate a 16:9 editorial illustration for the article

## AI Config

Requests can pass `ai_config` explicitly, or rely on server-side defaults.

Supported environment variables:

```bash
OPENAI_API_KEY=...
OPENAI_BASE_URL=...
OPENAI_TEXT_MODEL=...
OPENAI_IMAGE_TOOL_MODEL=...
```

Server-side defaults only support `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_TEXT_MODEL`, and `OPENAI_IMAGE_TOOL_MODEL`.

If text and image generation need different credentials or base URLs, pass them explicitly inside `ai_config` in the request body. Do not rely on `OPENAI_IMAGE_API_KEY` or `OPENAI_IMAGE_BASE_URL` as server-side defaults.

## Service Check

```bash
export MD2WE_BASE_URL="${MD2WE_BASE_URL:-https://md2we.com}"
curl -sS "${MD2WE_BASE_URL}/api/health"
```

## API Call Pattern

Title suggestions:

```bash
curl -sS "${MD2WE_BASE_URL}/api/ai/title-suggestions" \
  -H "Content-Type: application/json" \
  -d @<(jq -Rs '{
    markdown: .,
    focus_prompt: "更像媒体标题"
  }' article.md)
```

Summary:

```bash
curl -sS "${MD2WE_BASE_URL}/api/ai/summary" \
  -H "Content-Type: application/json" \
  -d @<(jq -Rs '{
    markdown: .,
    focus_prompt: "突出结论"
  }' article.md)
```

Image generation:

```bash
curl -sS "${MD2WE_BASE_URL}/api/ai/generate-image" \
  -H "Content-Type: application/json" \
  -d @<(jq -Rs '{
    markdown: .,
    focus_prompt: "科技感、克制、媒体头图"
  }' article.md)
```

Pass explicit AI config when needed:

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
      focus_prompt: "突出结论",
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

## Result Handling

- `title` returns `suggestions`
- `summary` returns `summary`
- `image` returns `image_url` and `revised_prompt`

If the server reports missing AI credentials, surface that directly and stop. Do not invent fallback output.
