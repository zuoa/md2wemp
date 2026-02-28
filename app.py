"""
MD2WEMP - Markdown转微信公众号HTML工具
支持丰富的主题和API调用
"""

from flask import Flask, render_template, request, jsonify, abort, url_for
from flask_cors import CORS
import markdown
from markdown.extensions.tables import TableExtension
from markdown.extensions.fenced_code import FencedCodeExtension
from markdown.extensions.toc import TocExtension
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import HtmlFormatter
from pygments.styles import get_style_by_name
import re
import json
import io
import base64
import urllib.parse
import urllib.request
import ssl
import os
import uuid
from pathlib import Path
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError

try:
    import qrcode
    from qrcode.image.svg import SvgPathImage
    QR_CODE_AVAILABLE = True
except ImportError:
    qrcode = None
    SvgPathImage = None
    QR_CODE_AVAILABLE = False

app = Flask(__name__)
CORS(app)
SHARE_STORAGE_DIR = Path(app.root_path) / "data" / "shares"

# 主题配置 - 丰富的个性化设置
THEMES = {
    "default": {
        "name": "默认主题",
        "colors": ["#3f3f3f", "#1e88e5", "#43a047"],
        "description": "简洁优雅，适合通用场景",
        "styles": {
            "bg_color": "#ffffff",
            "blockquote_bg": "#f8f9fa",
            "code_bg": "#f5f5f5",
            "border_radius": "6px",
            "shadow": "0 2px 8px rgba(0,0,0,0.06)",
            "h1_style": "bottom_border",  # 下边框样式
            "h2_style": "left_border",    # 左边框样式
            "h3_style": "plain"           # 纯文字
        }
    },
    "sport": {
        "name": "运动风",
        "colors": ["#4CAF50", "#2196F3", "#FF9800"],
        "description": "活力四射，动感十足",
        "styles": {
            "bg_color": "#fafafa",
            "blockquote_bg": "#e8f5e9",
            "code_bg": "#fff3e0",
            "border_radius": "12px",
            "shadow": "0 4px 12px rgba(76,175,80,0.15)",
            "h1_style": "background",     # 背景色样式
            "h2_style": "background",     # 背景色样式
            "h3_style": "left_border"
        }
    },
    "chinese": {
        "name": "中国风",
        "colors": ["#C62828", "#212121", "#B71C1C"],
        "description": "传统典雅，国风韵味",
        "styles": {
            "bg_color": "#fffdf7",
            "blockquote_bg": "#fff8e1",
            "code_bg": "#fff8e1",
            "border_radius": "0px",
            "shadow": "none",
            "h1_style": "double_bottom",  # 双线下边框
            "h2_style": "double_left",    # 双线左边框
            "h3_style": "bottom_border"
        }
    },
    "cyberpunk": {
        "name": "赛博朋克",
        "colors": ["#E91E63", "#9C27B0", "#00BCD4"],
        "description": "未来科技，霓虹闪烁",
        "styles": {
            "bg_color": "#1a1a2e",
            "blockquote_bg": "#16213e",
            "code_bg": "#0f0f23",
            "border_radius": "8px",
            "shadow": "0 0 20px rgba(233,30,99,0.3)",
            "h1_style": "neon",           # 霓虹样式
            "h2_style": "gradient_bg",    # 渐变背景
            "h3_style": "left_border",
            "text_color": "#e0e0e0",      # 浅色文字
            "secondary_text": "#a0a0a0"   # 次要文字颜色
        }
    },
    "ocean": {
        "name": "海洋风",
        "colors": ["#0077B6", "#00B4D8", "#90E0EF"],
        "description": "清新淡雅，如沐海风",
        "styles": {
            "bg_color": "#f0f9ff",
            "blockquote_bg": "#e0f7fa",
            "code_bg": "#e0f7fa",
            "border_radius": "16px",
            "shadow": "0 4px 16px rgba(0,119,182,0.1)",
            "h1_style": "wave_bottom",    # 波浪下边框
            "h2_style": "left_border",
            "h3_style": "dotted_bottom"   # 点线下边框
        }
    },
    "forest": {
        "name": "森林风",
        "colors": ["#2E7D32", "#558B2F", "#8BC34A"],
        "description": "自然清新，绿意盎然",
        "styles": {
            "bg_color": "#f1f8e9",
            "blockquote_bg": "#dcedc8",
            "code_bg": "#dcedc8",
            "border_radius": "10px",
            "shadow": "0 3px 10px rgba(46,125,50,0.12)",
            "h1_style": "leaf_deco",      # 叶子装饰
            "h2_style": "thick_left",     # 粗左边框
            "h3_style": "bottom_border"
        }
    },
    "sunset": {
        "name": "日落风",
        "colors": ["#FF5722", "#FF9800", "#FFC107"],
        "description": "温暖浪漫，夕阳余晖",
        "styles": {
            "bg_color": "#fff8f0",
            "blockquote_bg": "#fff3e0",
            "code_bg": "#fff3e0",
            "border_radius": "12px",
            "shadow": "0 4px 14px rgba(255,87,34,0.12)",
            "h1_style": "gradient_bottom", # 渐变下边框
            "h2_style": "gradient_bg",    # 渐变背景
            "h3_style": "left_border"
        }
    },
    "lavender": {
        "name": "薰衣草",
        "colors": ["#7B1FA2", "#9C27B0", "#CE93D8"],
        "description": "浪漫优雅，紫韵飘香",
        "styles": {
            "bg_color": "#faf5ff",
            "blockquote_bg": "#f3e5f5",
            "code_bg": "#f3e5f5",
            "border_radius": "14px",
            "shadow": "0 4px 16px rgba(123,31,162,0.1)",
            "h1_style": "ribbon",         # 缎带样式
            "h2_style": "left_border",
            "h3_style": "dashed_bottom"   # 虚线下边框
        }
    },
    "coffee": {
        "name": "咖啡风",
        "colors": ["#5D4037", "#795548", "#A1887F"],
        "description": "沉稳内敛，醇香浓郁",
        "styles": {
            "bg_color": "#faf6f3",
            "blockquote_bg": "#efebe9",
            "code_bg": "#efebe9",
            "border_radius": "8px",
            "shadow": "0 3px 10px rgba(93,64,55,0.1)",
            "h1_style": "bottom_border",
            "h2_style": "thick_left",     # 粗左边框
            "h3_style": "plain"
        }
    },
    "minimalist": {
        "name": "极简风",
        "colors": ["#212121", "#757575", "#9E9E9E"],
        "description": "极简主义，返璞归真",
        "styles": {
            "bg_color": "#ffffff",
            "blockquote_bg": "#fafafa",
            "code_bg": "#fafafa",
            "border_radius": "0px",
            "shadow": "none",
            "h1_style": "thin_bottom",    # 细线下边框
            "h2_style": "thin_left",      # 细线左边框
            "h3_style": "plain"
        }
    },
    "tech": {
        "name": "科技风",
        "colors": ["#0D47A1", "#1976D2", "#64B5F6"],
        "description": "专业严谨，科技感强",
        "styles": {
            "bg_color": "#f5f7fa",
            "blockquote_bg": "#e3f2fd",
            "code_bg": "#263238",
            "border_radius": "6px",
            "shadow": "0 2px 8px rgba(13,71,161,0.1)",
            "h1_style": "background",     # 背景色
            "h2_style": "left_bottom",    # 左+下边框
            "h3_style": "bottom_border"
        }
    },
    "retro": {
        "name": "复古风",
        "colors": ["#8D6E63", "#A1887F", "#BCAAA4"],
        "description": "怀旧复古，时光倒流",
        "styles": {
            "bg_color": "#faf5f0",
            "blockquote_bg": "#efe0d6",
            "code_bg": "#efe0d6",
            "border_radius": "4px",
            "shadow": "0 2px 6px rgba(141,110,99,0.15)",
            "h1_style": "double_bottom",  # 双线下边框
            "h2_style": "double_bottom",  # 双线下边框
            "h3_style": "dotted_bottom"   # 点线下边框
        }
    },
    "government": {
        "name": "政务风",
        "colors": ["#B71C1C", "#D32F2F", "#FFD700"],
        "description": "庄重典雅，权威正式",
        "styles": {
            "bg_color": "#FFFEF5",
            "blockquote_bg": "#FFF8E1",
            "code_bg": "#FFFDE7",
            "border_radius": "2px",
            "shadow": "0 2px 8px rgba(183,28,28,0.1)",
            "h1_style": "government",     # 政务风格标题
            "h2_style": "government_h2",  # 政务风格副标题
            "h3_style": "bottom_border"
        }
    },
    "finance": {
        "name": "金融风",
        "colors": ["#0D47A1", "#1565C0", "#C9A227"],
        "description": "专业可信，稳健高端",
        "styles": {
            "bg_color": "#FAFBFC",
            "blockquote_bg": "#E3F2FD",
            "code_bg": "#ECEFF1",
            "border_radius": "4px",
            "shadow": "0 2px 10px rgba(13,71,161,0.08)",
            "h1_style": "finance",        # 金融风格标题
            "h2_style": "finance_h2",     # 金融风格副标题
            "h3_style": "left_border"
        }
    }
}

# 代码高亮主题 - 映射到 Pygments 样式
CODE_THEMES = {
    "github": {"name": "GitHub", "style": "default", "bg": "#f6f8fa", "text_color": "#24292e"},
    "monokai": {"name": "Monokai", "style": "monokai", "bg": "#272822", "text_color": "#f8f8f2"},
    "dracula": {"name": "Dracula", "style": "dracula", "bg": "#282a36", "text_color": "#f8f8f2"},
    "atom-one-dark": {"name": "Atom One Dark", "style": "one-dark", "bg": "#282c34", "text_color": "#abb2bf"},
    "atom-one-light": {"name": "Atom One Light", "style": "default", "bg": "#fafafa", "text_color": "#383a42"},
    "vs": {"name": "Visual Studio", "style": "vs", "bg": "#ffffff", "text_color": "#393939"},
    "xcode": {"name": "Xcode", "style": "xcode", "bg": "#ffffff", "text_color": "#000000"},
    "stackoverflow-light": {"name": "StackOverflow Light", "style": "default", "bg": "#f6f8fa", "text_color": "#24292e"}
}

# 字体大小配置
FONT_SIZES = {
    "small": {"base": "14px", "name": "小号字体(14px)", "desc": "信息密度高，适合精细阅读"},
    "medium": {"base": "15px", "name": "中号字体(15px)", "desc": "日常阅读，平衡视觉"},
    "large": {"base": "16px", "name": "大号字体(16px)", "desc": "舒适阅读，视觉友好"}
}

# 背景配置
BACKGROUNDS = {
    "warm": {"name": "温暖米色", "color": "#FDF6E3", "desc": "经典微信风格"},
    "grid": {"name": "方格白底", "color": "#FFFFFF", "desc": "简约方格纹理"},
    "none": {"name": "无背景", "color": "transparent", "desc": "透明背景"}
}


def find_first_heading(md_text):
    """提取 Markdown 中的第一个标题。"""
    match = re.search(r'^\s{0,3}#\s+(.+?)\s*$', md_text, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return ""


def extract_plain_text_from_markdown(md_text):
    """提取适合统计和 AI 分析的纯文本内容。"""
    text = re.sub(r'```[\s\S]*?```', ' ', md_text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'\1 ', text)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 ', text)
    text = re.sub(r'^\s{0,3}#{1,6}\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s{0,3}>\s?', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'[>*_~|-]+', ' ', text)
    text = re.sub(r'\n{2,}', '\n', text)
    return text.strip()


def build_article_context(md_text, limit=2200):
    """为 AI 生成紧凑的文章上下文。"""
    title = find_first_heading(md_text) or "未命名文章"
    plain_text = extract_plain_text_from_markdown(md_text)
    excerpt = plain_text[:limit]
    return {
        "title": title,
        "plain_text": plain_text,
        "excerpt": excerpt
    }


def sanitize_ai_config(ai_config=None):
    """归一化 AI 配置，允许文本和图片分别覆盖环境变量。"""
    ai_config = ai_config or {}
    text_config = ai_config.get("text") or {}
    image_config = ai_config.get("image") or {}
    return {
        "text": {
            "api_key": (text_config.get("api_key") or os.getenv("OPENAI_API_KEY", "")).strip(),
            "base_url": (text_config.get("base_url") or os.getenv("OPENAI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai")).strip().rstrip("/"),
            "model": (text_config.get("model") or os.getenv("OPENAI_TEXT_MODEL", "gemini-2.5-flash")).strip()
        },
        "image": {
            "api_key": (image_config.get("api_key") or os.getenv("OPENAI_API_KEY", "")).strip(),
            "base_url": (image_config.get("base_url") or os.getenv("OPENAI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai")).strip().rstrip("/"),
            "model": (image_config.get("model") or os.getenv("OPENAI_IMAGE_TOOL_MODEL", "imagen-4.0-generate-001")).strip()
        }
    }


def has_ai_capability(ai_config=None, capability="any"):
    """判断当前是否有可用的 AI 配置。"""
    config = sanitize_ai_config(ai_config)
    if capability == "text":
        return bool(config["text"]["api_key"])
    if capability == "image":
        return bool(config["image"]["api_key"])
    return bool(config["text"]["api_key"] or config["image"]["api_key"])


def normalize_render_options(theme="default", code_theme="github", font_size="medium", background="warm"):
    """校验并规范化渲染参数。"""
    return (
        theme if theme in THEMES else "default",
        code_theme if code_theme in CODE_THEMES else "github",
        font_size if font_size in FONT_SIZES else "medium",
        background if background in BACKGROUNDS else "warm"
    )


def build_theme_cards():
    """为主题卡片补充前景色。"""
    themed_cards = {}
    for key, theme in THEMES.items():
        theme_copy = dict(theme)
        bg_color = theme["styles"].get("bg_color", "#ffffff")
        bg_hex = bg_color.lstrip("#")
        r, g, b = int(bg_hex[0:2], 16), int(bg_hex[2:4], 16), int(bg_hex[4:6], 16)
        is_dark = (r * 0.299 + g * 0.587 + b * 0.114) < 128
        theme_copy["card_text_color"] = theme["styles"].get("text_color", "#ffffff") if is_dark else "#1f2937"
        themed_cards[key] = theme_copy
    return themed_cards


def ensure_share_storage_dir():
    """确保分享内容目录存在。"""
    SHARE_STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def get_share_file_path(share_id):
    """返回分享文件路径。"""
    safe_id = re.sub(r"[^a-f0-9]", "", (share_id or "").lower())[:32]
    if not safe_id:
        return None
    return SHARE_STORAGE_DIR / f"{safe_id}.json"


def load_share_payload(share_id):
    """读取分享数据。"""
    share_path = get_share_file_path(share_id)
    if not share_path or not share_path.exists():
        return None

    with share_path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def format_share_timestamp(iso_text):
    """格式化分享时间。"""
    if not iso_text:
        return ""

    try:
        dt = datetime.fromisoformat(iso_text.replace("Z", "+00:00"))
    except ValueError:
        return ""

    if dt.tzinfo:
        dt = dt.astimezone()
    return dt.strftime("%Y-%m-%d %H:%M")


def create_share_qr_svg(url):
    """生成分享链接对应的二维码 SVG。"""
    if not QR_CODE_AVAILABLE or not url:
        return ""

    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2
    )
    qr.add_data(url)
    qr.make(fit=True)

    image = qr.make_image(
        image_factory=SvgPathImage,
        fill_color="#08111f",
        back_color="#ffffff"
    )
    buffer = io.BytesIO()
    image.save(buffer)
    return buffer.getvalue().decode("utf-8")


def build_share_payload(md_text, theme, code_theme, font_size, background, share_id, share_url):
    """构建分享内容。"""
    title = find_first_heading(md_text) or "未命名文章"
    plain_text = extract_plain_text_from_markdown(md_text)
    excerpt = plain_text[:160].strip()
    html = process_markdown(md_text, theme, code_theme, font_size, background)
    created_at = datetime.now(timezone.utc).isoformat()

    return {
        "id": share_id,
        "title": title,
        "excerpt": excerpt,
        "markdown": md_text,
        "html": html,
        "share_url": share_url,
        "created_at": created_at,
        "settings": {
            "theme": theme,
            "code_theme": code_theme,
            "font_size": font_size,
            "background": background
        }
    }


def openai_api_request(path, payload, timeout=60, ai_config=None, capability="text"):
    """调用 OpenAI API。"""
    config = sanitize_ai_config(ai_config)
    target_config = config["text"] if capability == "text" else config["image"]
    api_key = target_config["api_key"]
    if not api_key:
        raise RuntimeError("未配置 OPENAI_API_KEY，AI 功能不可用")

    url = f"{target_config['base_url']}{path}"
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        message = body
        try:
            error_data = json.loads(body)
            message = error_data.get("error", {}).get("message") or body
        except json.JSONDecodeError:
            pass
        raise RuntimeError(f"OpenAI 请求失败: {message}") from exc
    except URLError as exc:
        raise RuntimeError(f"OpenAI 网络请求失败: {exc.reason}") from exc


def extract_chat_completion_text(response_data):
    """从 Chat Completions 响应中提取文本。"""
    choices = response_data.get("choices", [])
    if not choices:
        return ""

    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text_value = item.get("text") or item.get("content", "")
                if text_value:
                    parts.append(text_value)
        return "\n".join(parts).strip()

    return ""


def call_openai_text(system_prompt, user_prompt, max_output_tokens=500, ai_config=None):
    """调用 OpenAI-compatible Chat Completions API 生成文本。"""
    config = sanitize_ai_config(ai_config)
    payload = {
        "model": config["text"]["model"],
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        "max_tokens": max_output_tokens
    }
    response_data = openai_api_request("/chat/completions", payload, timeout=60, ai_config=config, capability="text")
    text = extract_chat_completion_text(response_data)
    if not text:
        raise RuntimeError("AI 没有返回可解析的文本结果")
    return text


def generate_ai_title_suggestions(md_text, ai_config=None):
    """基于文章内容生成标题建议。"""
    context = build_article_context(md_text)
    system_prompt = (
        "你是一名中文内容编辑。请根据文章内容生成标题建议。"
        "标题必须准确、克制、适合公众号文章，避免夸张标题党。"
        "直接返回 5 行标题，每行一个，不要编号，不要解释。"
    )
    user_prompt = (
        f"文章标题（如有）: {context['title']}\n\n"
        f"文章正文摘要:\n{context['excerpt']}"
    )
    text = call_openai_text(system_prompt, user_prompt, max_output_tokens=220, ai_config=ai_config)
    suggestions = []
    for line in text.splitlines():
        cleaned = re.sub(r'^\s*[-*\d.、)\]]+\s*', '', line).strip().strip('"\'' )
        if cleaned:
            suggestions.append(cleaned)
    deduped = []
    seen = set()
    for item in suggestions:
        if item not in seen:
            deduped.append(item)
            seen.add(item)
    return deduped[:5]


def generate_ai_summary(md_text, ai_config=None):
    """生成文章摘要。"""
    context = build_article_context(md_text)
    system_prompt = (
        "你是一名中文编辑。请输出一段适合作为文章摘要的内容。"
        "要求 90 到 140 个中文字符，信息密度高，语气自然，不要使用项目符号，不要以“本文”开头。"
    )
    user_prompt = (
        f"文章标题: {context['title']}\n\n"
        f"文章正文:\n{context['excerpt']}"
    )
    return call_openai_text(system_prompt, user_prompt, max_output_tokens=180, ai_config=ai_config).replace("\n", " ").strip()


def extract_generated_image(response_data):
    """从 Images API 响应中提取图片。"""
    for item in response_data.get("data", []):
        image_base64 = item.get("b64_json")
        if image_base64:
            return image_base64, item.get("revised_prompt", "")
    raise RuntimeError("AI 没有返回可解析的图片结果")


def generate_ai_image(md_text, focus_prompt="", ai_config=None):
    """为文章生成配图。"""
    context = build_article_context(md_text, limit=2600)
    config = sanitize_ai_config(ai_config)
    prompt_parts = [
        "请为一篇中文文章生成一张横版头图插画。",
        "风格要求：现代 editorial illustration，干净、有层次、适合知识型文章。",
        "输出要求：16:9 横图，不包含任何文字、Logo、水印、边框、按钮或界面元素。",
        f"文章标题：{context['title']}",
        f"文章核心内容：{context['excerpt']}"
    ]
    if focus_prompt:
        prompt_parts.append(f"额外侧重点：{focus_prompt.strip()}")

    payload = {
        "model": config["image"]["model"],
        "prompt": "\n".join(prompt_parts),
        "size": "1536x1024",
        "response_format": "b64_json",
        "n": 1
    }
    response_data = openai_api_request("/images/generations", payload, timeout=180, ai_config=config, capability="image")
    image_base64, revised_prompt = extract_generated_image(response_data)
    return {
        "image_data_url": f"data:image/png;base64,{image_base64}",
        "revised_prompt": revised_prompt
    }


def highlight_code(code, language, style_name):
    """使用 Pygments 高亮代码"""
    try:
        lexer = get_lexer_by_name(language, stripall=True)
    except:
        try:
            lexer = guess_lexer(code)
        except:
            lexer = get_lexer_by_name('text', stripall=True)

    try:
        style = get_style_by_name(style_name)
    except:
        style = get_style_by_name('default')

    formatter = HtmlFormatter(
        style=style,
        nowrap=True,
        noclasses=True,
        prestyles='margin:0;padding:0;background:transparent;'
    )

    return highlight(code, lexer, formatter)


def render_latex_to_base64(latex_code, theme_config=None):
    """将 LaTeX 公式渲染为 base64 编码的图片（使用在线服务）"""
    try:
        # 获取主题背景色和文字颜色
        bg_color = 'FFFFFF'
        text_color = '000000'
        if theme_config and 'styles' in theme_config:
            bg = theme_config['styles'].get('bg_color', '#ffffff')
            txt = theme_config['styles'].get('text_color', '#333333')
            bg_color = bg.lstrip('#')
            text_color = txt.lstrip('#')

        # 判断是否为深色背景
        # 计算背景亮度
        r, g, b = int(bg_color[0:2], 16), int(bg_color[2:4], 16), int(bg_color[4:6], 16)
        is_dark = (r * 0.299 + g * 0.587 + b * 0.114) < 128

        # 使用 CodeCogs 在线 LaTeX 渲染服务
        # 对于深色背景，使用白色文字
        if is_dark:
            latex_code = f"\\color{{white}}{{{latex_code}}}"

        encoded_latex = urllib.parse.quote(latex_code)
        url = f"https://latex.codecogs.com/png.latex?\\dpi{{150}}{encoded_latex}"

        # 获取图片
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            img_data = response.read()

        img_base64 = base64.b64encode(img_data).decode('utf-8')
        return f'data:image/png;base64,{img_base64}'
    except Exception as e:
        # 如果在线服务失败，尝试使用 matplotlib 本地渲染（简单公式）
        try:
            return render_latex_local(latex_code, theme_config)
        except:
            return None


def render_latex_local(latex_code, theme_config=None):
    """使用 matplotlib 本地渲染简单的 LaTeX 公式"""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import rcParams

    rcParams['mathtext.fontset'] = 'cm'
    rcParams['font.family'] = 'serif'

    bg_color = '#ffffff'
    text_color = '#333333'
    if theme_config and 'styles' in theme_config:
        bg_color = theme_config['styles'].get('bg_color', '#ffffff')
        text_color = theme_config['styles'].get('text_color', '#333333')

    fig, ax = plt.subplots(figsize=(10, 0.8))
    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(bg_color)
    ax.axis('off')

    ax.text(0.5, 0.5, f'${latex_code}$',
            transform=ax.transAxes,
            fontsize=16,
            ha='center',
            va='center',
            color=text_color)

    fig.tight_layout(pad=0.5)

    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', dpi=150,
                facecolor=bg_color, edgecolor='none',
                bbox_inches='tight', pad_inches=0.1)
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
    plt.close(fig)

    return f'data:image/png;base64,{img_base64}'


def process_math_formulas(md_text, theme_config=None):
    """处理 Markdown 中的数学公式"""

    # 处理块级公式 $$...$$
    def replace_block_math(match):
        latex = match.group(1).strip()
        img_src = render_latex_to_base64(latex, theme_config)
        if img_src:
            return f'\n<img src="{img_src}" style="display: block; margin: 16px auto; max-width: 100%;" alt="math">\n'
        return f'<div style="text-align: center; margin: 16px 0; padding: 12px; background: #f5f5f5; border-radius: 4px;"><code>{latex}</code></div>'

    md_text = re.sub(r'\$\$(.+?)\$\$', replace_block_math, md_text, flags=re.DOTALL)

    # 处理行内/块级公式 $...$（支持多行）
    def replace_inline_math(match):
        latex = match.group(1).strip()
        img_src = render_latex_to_base64(latex, theme_config)
        if img_src:
            # 判断是否为多行公式（包含换行符）
            if '\n' in latex:
                return f'\n<img src="{img_src}" style="display: block; margin: 16px auto; max-width: 100%;" alt="math">\n'
            return f'<img src="{img_src}" style="display: inline-block; vertical-align: middle; margin: 0 2px; max-height: 1.5em;" alt="math">'
        return f'<code style="background: #f5f5f5; padding: 2px 4px; border-radius: 2px;">{latex}</code>'

    # 匹配单个 $ 的公式，支持多行内容
    # 使用更精确的模式：$ 开头，$ 结尾，中间可以包含任何字符（包括换行）
    md_text = re.sub(r'(?<!\$)\$(?!\$)([\s\S]+?)(?<!\$)\$(?!\$)', replace_inline_math, md_text)

    return md_text



def process_markdown(md_text, theme="default", code_theme="github", font_size="medium", background="warm"):
    """处理Markdown文本，生成微信兼容的HTML"""

    # 获取主题配置
    theme_config = THEMES.get(theme, THEMES["default"])
    font_config = FONT_SIZES.get(font_size, FONT_SIZES["medium"])
    bg_config = BACKGROUNDS.get(background, BACKGROUNDS["warm"])
    code_theme_config = CODE_THEMES.get(code_theme, CODE_THEMES["github"])

    # 处理数学公式（在代码块处理之前）
    md_text = process_math_formulas(md_text, theme_config)

    # 提取并临时替换横屏滑动幻灯片（在代码块处理之前）
    sliders = []

    def save_slider(match):
        placeholder = f'SLIDERPLACEHOLDER{len(sliders)}ENDPLACEHOLDER'
        sliders.append(match.group(1))
        return placeholder

    slider_pattern = r'<(!.+?)>'
    md_text = re.sub(slider_pattern, save_slider, md_text, flags=re.DOTALL)

    # 提取并临时替换代码块
    code_blocks = []
    mermaid_blocks = []

    def save_code_block(match):
        lang = (match.group(1) or '').strip()
        code = match.group(2)
        if lang.lower() == 'mermaid':
            placeholder = f'MERMAIDPLACEHOLDER{len(mermaid_blocks)}ENDPLACEHOLDER'
            mermaid_blocks.append(code.strip())
            return placeholder

        placeholder = f'CODEBLOCKPLACEHOLDER{len(code_blocks)}ENDPLACEHOLDER'
        code_blocks.append((lang, code))
        return placeholder

    # 匹配 fenced code blocks - 更宽松的匹配
    pattern = r'```(\w*)\s*\n(.*?)\n```'
    md_text_processed = re.sub(pattern, save_code_block, md_text, flags=re.DOTALL)

    # 解析 Markdown（不含代码块）
    md = markdown.Markdown(extensions=[
        'tables',
        'nl2br',
        'sane_lists'
    ])
    html_content = md.convert(md_text_processed)

    # 恢复并高亮代码块
    for i, (lang, code) in enumerate(code_blocks):
        placeholder = f'CODEBLOCKPLACEHOLDER{i}ENDPLACEHOLDER'
        if lang:
            highlighted = highlight_code(code, lang, code_theme_config["style"])
        else:
            highlighted = highlight_code(code, 'text', code_theme_config["style"])

        # 包装为 pre/code 结构
        code_html = f'<pre class="code-block" data-lang="{lang}"><code>{highlighted}</code></pre>'

        # 尝试多种替换方式
        html_content = html_content.replace(f'<p>{placeholder}</p>', code_html)
        html_content = html_content.replace(placeholder, code_html)

    # 恢复 Mermaid 图表占位，交由前端渲染为 SVG
    mermaid_bg = theme_config['styles'].get('blockquote_bg', '#f8f9fa')
    mermaid_text = theme_config['styles'].get('secondary_text', '#666666')
    mermaid_border = theme_config['colors'][1]
    mermaid_radius = theme_config['styles'].get('border_radius', '8px')
    mermaid_border_rgba = mermaid_border if mermaid_border.startswith('rgba') else f"rgba({int(mermaid_border[1:3], 16)}, {int(mermaid_border[3:5], 16)}, {int(mermaid_border[5:7], 16)}, 0.22)"

    for i, code in enumerate(mermaid_blocks):
        placeholder = f'MERMAIDPLACEHOLDER{i}ENDPLACEHOLDER'
        encoded = base64.b64encode(code.encode('utf-8')).decode('utf-8')
        mermaid_html = (
            f'<div class="md2-mermaid" data-mermaid="{encoded}" '
            f'style="margin: 18px 0; padding: 16px; border: 1px dashed {mermaid_border_rgba}; '
            f'border-radius: {mermaid_radius}; background: {mermaid_bg}; overflow-x: auto;">'
            f'<div class="md2-mermaid-status" style="font-size: 12px; color: {mermaid_text};">'
            'Mermaid 图表渲染中...</div></div>'
        )
        html_content = html_content.replace(f'<p>{placeholder}</p>', mermaid_html)
        html_content = html_content.replace(placeholder, mermaid_html)

    # 恢复横屏滑动幻灯片（在代码块之后，generate_styled_html 之前）
    for i, slider_content in enumerate(sliders):
        placeholder = f'SLIDERPLACEHOLDER{i}ENDPLACEHOLDER'
        # 解析幻灯片中的图片
        img_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
        images = re.findall(img_pattern, slider_content)

        if images:
            # 获取主题边框圆角
            border_radius = theme_config['styles'].get('border_radius', '6px')

            # 生成横屏滑动幻灯片 HTML - 每张图片 16:9 宽高比，拉伸填充，每张占满容器宽度
            images_html = []
            for alt, url in images:
                # 每张图片占满容器宽度，固定 16:9 宽高比，object-fit: fill 拉伸图片
                # 使用 data-slider-img 标记避免被后续样式处理覆盖
                img_html = f'<div style="flex: 0 0 100%; scroll-snap-align: start;"><img data-slider-img="true" src="{url}" alt="{alt}" style="display: block; width: 100%; aspect-ratio: 16/9; object-fit: fill; border-radius: {border_radius}; margin: 0;"></div>'
                images_html.append(img_html)

            slider_html = f'<section style="width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; margin: 16px 0; scroll-snap-type: x mandatory; border-radius: {border_radius};"><div style="display: flex;">{"".join(images_html)}</div></section>'

            html_content = html_content.replace(f'<p>{placeholder}</p>', slider_html)
            html_content = html_content.replace(placeholder, slider_html)

    # 生成内联样式的HTML
    styled_html = generate_styled_html(
        html_content,
        theme_config,
        code_theme_config,
        font_config,
        bg_config
    )

    return styled_html


def generate_styled_html(content, theme_config, code_theme, font_config, bg_config):
    """生成带内联样式的HTML，确保微信兼容"""

    primary_color = theme_config["colors"][0]
    secondary_color = theme_config["colors"][1]
    accent_color = theme_config["colors"][2]
    base_font = font_config["base"]

    # 获取主题样式配置
    styles = theme_config.get("styles", {
        "bg_color": "#ffffff",
        "blockquote_bg": "#f8f8f8",
        "code_bg": "#f5f5f5",
        "border_radius": "6px",
        "shadow": "0 2px 8px rgba(0,0,0,0.06)",
        "h1_style": "bottom_border",
        "h2_style": "left_border",
        "h3_style": "plain"
    })

    bg_color = styles["bg_color"]
    blockquote_bg = styles["blockquote_bg"]
    code_bg = styles["code_bg"]
    border_radius = styles["border_radius"]
    shadow = styles["shadow"]
    h1_style_type = styles.get("h1_style", "bottom_border")
    h2_style_type = styles.get("h2_style", "left_border")
    h3_style_type = styles.get("h3_style", "plain")
    text_color = styles.get("text_color", "#333")
    secondary_text_color = styles.get("secondary_text", "#666")

    # 标题样式生成函数 - 精细化设计，符合各主题特质
    def get_h1_style(style_type, color1, color2, color3, radius, bg_color):
        """生成h1样式 - 更精致的设计"""
        base = "margin: 28px 0 18px; font-size: 1.75em; font-weight: 700; letter-spacing: 0.5px;"

        styles = {
            # Default - 简洁优雅
            "bottom_border": f"{base} padding-bottom: 12px; border-bottom: 2px solid {color1}; color: {color1}; position: relative;",
            # Chinese - 传统典雅，印章风格
            "double_bottom": f"{base} padding: 14px 20px; border: 2px solid {color1}; border-bottom: 4px double {color1}; color: {color1}; text-align: center; background: linear-gradient(to bottom, transparent 0%, rgba({_hex_to_rgb(color1)}, 0.03) 100%);",
            # Sport - 活力动感
            "background": f"{base} padding: 14px 20px; background: linear-gradient(135deg, {color1}, {color2}); color: #fff; border-radius: {radius}; box-shadow: 0 4px 15px rgba({_hex_to_rgb(color1)}, 0.3);",
            # Cyberpunk - 霓虹未来
            "neon": f"{base} padding: 14px 20px; color: {color1}; text-shadow: 0 0 10px {color1}, 0 0 30px {color1}, 0 0 50px {color2}; border: 1px solid {color1}; border-radius: {radius}; background: rgba({_hex_to_rgb(color1)}, 0.05); box-shadow: inset 0 0 20px rgba({_hex_to_rgb(color1)}, 0.1), 0 0 30px rgba({_hex_to_rgb(color1)}, 0.2);",
            # Sunset - 温暖渐变
            "gradient_bottom": f"{base} padding-bottom: 12px; background: linear-gradient(90deg, {color1}, {color2}, {color3}) left bottom / 100% 3px no-repeat; color: {color1};",
            # Lavender - 优雅缎带
            "ribbon": f"{base} padding: 12px 24px; background: linear-gradient(135deg, {color1}, {color2}); color: #fff; border-radius: 0 {radius} {radius} 0; box-shadow: 4px 4px 0 {color3}; margin-left: -4px;",
            # Ocean - 波浪清新
            "wave_bottom": f"{base} padding-bottom: 12px; color: {color1}; background: linear-gradient(90deg, {color1} 0%, {color2} 50%, transparent 50%) left bottom / 8px 3px repeat-x; background-position: 0 100%;",
            # Forest - 自然有机
            "leaf_deco": f"{base} padding: 10px 0 10px 20px; border-left: 4px solid {color1}; color: {color1}; background: linear-gradient(90deg, rgba({_hex_to_rgb(color1)}, 0.08) 0%, transparent 100%); border-radius: 0 {radius} {radius} 0;",
            # Minimalist - 极简主义
            "thin_bottom": f"{base} padding-bottom: 10px; color: {color1}; font-weight: 400; border-bottom: 1px solid rgba({_hex_to_rgb(color1)}, 0.2);",
            # Tech - 专业科技
            "left_bottom": f"{base} padding: 12px 16px; border-left: 4px solid {color1}; border-bottom: 1px solid {color1}; color: {color1}; background: linear-gradient(90deg, rgba({_hex_to_rgb(color1)}, 0.05) 0%, transparent 100%);",
            # Government - 政务风格
            "government": f"{base} padding: 14px 20px; color: {color1}; text-align: center; border-bottom: 3px solid {color3}; background: linear-gradient(to bottom, rgba({_hex_to_rgb(color3)}, 0.08) 0%, transparent 100%); font-weight: 700; letter-spacing: 2px;",
            # Finance - 金融风格
            "finance": f"{base} padding: 14px 0; color: {color1}; border-bottom: 3px double {color3}; position: relative;",
        }
        return styles.get(style_type, styles["bottom_border"])

    def get_h2_style(style_type, color1, color2, color3, radius, bg_color):
        """生成h2样式 - 更精致的设计"""
        base = "margin: 22px 0 14px; font-size: 1.4em; font-weight: 600; letter-spacing: 0.3px;"

        styles = {
            # Default - 左边框强调
            "left_border": f"{base} padding-left: 14px; border-left: 3px solid {color2}; color: {color1};",
            # Chinese - 双线左边框
            "double_left": f"{base} padding-left: 16px; border-left: 4px double {color1}; color: {color1}; background: linear-gradient(90deg, rgba({_hex_to_rgb(color1)}, 0.05) 0%, transparent 30%);",
            # Sport - 圆角背景
            "background": f"{base} padding: 10px 16px; background: {color2}; color: #fff; border-radius: {radius}; display: inline-block;",
            # Cyberpunk - 渐变背景
            "gradient_bg": f"{base} padding: 10px 18px; background: linear-gradient(90deg, {color2}, {color3}); color: #fff; border-radius: {radius}; box-shadow: 0 0 15px rgba({_hex_to_rgb(color2)}, 0.3);",
            # Forest - 粗左边框带渐变
            "thick_left": f"{base} padding: 8px 0 8px 18px; border-left: 5px solid {color2}; color: {color1}; background: linear-gradient(90deg, rgba({_hex_to_rgb(color2)}, 0.1) 0%, transparent 50%);",
            # Sunset - 渐变背景
            "gradient_bottom": f"{base} padding: 10px 16px; background: linear-gradient(90deg, {color2}, {color3}); color: #fff; border-radius: {radius};",
            # Minimalist - 细线左边框
            "thin_left": f"{base} padding-left: 12px; border-left: 2px solid {color2}; color: {color1}; font-weight: 400;",
            # Tech - 左+下边框
            "left_bottom": f"{base} padding: 8px 12px; border-left: 3px solid {color2}; border-bottom: 1px solid {color2}; color: {color1};",
            # Retro - 双线下边框
            "double_bottom": f"{base} padding-bottom: 8px; border-bottom: 3px double {color2}; color: {color1};",
            # Government - 政务副标题
            "government_h2": f"{base} padding-left: 16px; border-left: 4px solid {color1}; color: {color1}; background: linear-gradient(90deg, rgba({_hex_to_rgb(color3)}, 0.1) 0%, transparent 50%);",
            # Finance - 金融副标题
            "finance_h2": f"{base} padding: 8px 16px; background: linear-gradient(90deg, {color1} 0%, {color2} 100%); color: #fff; border-radius: {radius}; display: inline-block; box-shadow: 0 2px 8px rgba({_hex_to_rgb(color1)}, 0.2);",
        }
        return styles.get(style_type, styles["left_border"])

    def get_h3_style(style_type, color1, color2, color3, radius, bg_color):
        """生成h3样式 - 更精致的设计"""
        base = "margin: 18px 0 10px; font-size: 1.15em; font-weight: 600; letter-spacing: 0.2px;"

        styles = {
            # Default - 纯文字
            "plain": f"{base} color: {color1};",
            # Chinese/Default - 下边框
            "bottom_border": f"{base} padding-bottom: 6px; border-bottom: 2px solid {color3}; color: {color1};",
            # Cyberpunk/Sport - 左边框
            "left_border": f"{base} padding-left: 10px; border-left: 3px solid {color3}; color: {color1};",
            # Ocean - 点线下边框
            "dotted_bottom": f"{base} padding-bottom: 6px; border-bottom: 2px dotted {color3}; color: {color1};",
            # Lavender - 虚线下边框
            "dashed_bottom": f"{base} padding-bottom: 6px; border-bottom: 2px dashed {color3}; color: {color1};",
        }
        return styles.get(style_type, styles["plain"])

    def _hex_to_rgb(hex_color):
        """将十六进制颜色转换为RGB值字符串"""
        hex_color = hex_color.lstrip('#')
        return f"{int(hex_color[0:2], 16)}, {int(hex_color[2:4], 16)}, {int(hex_color[4:6], 16)}"

    # 生成标题样式
    h1_style = get_h1_style(h1_style_type, primary_color, secondary_color, accent_color, border_radius, bg_color)
    h2_style = get_h2_style(h2_style_type, primary_color, secondary_color, accent_color, border_radius, bg_color)
    h3_style = get_h3_style(h3_style_type, primary_color, secondary_color, accent_color, border_radius, bg_color)

    # 获取导出背景颜色（如果用户选择了非透明背景，则使用用户选择的背景）
    export_bg_color = bg_config.get("color", "transparent")
    # 如果背景是透明的，使用主题的背景色
    final_bg_color = export_bg_color if export_bg_color != "transparent" else bg_color

    # 微信支持的样式模板
    wrapper_style = f"""
        background-color: {final_bg_color};
        padding: 20px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
        font-size: {base_font};
        color: {text_color};
        line-height: 1.8;
        word-wrap: break-word;
        border-radius: {border_radius};
        box-shadow: {shadow};
    """

    p_style = f"""
        margin: 12px 0;
        text-align: justify;
        color: {text_color};
    """

    blockquote_style = f"""
        margin: 15px 0;
        padding: 10px 15px;
        border-left: 4px solid {accent_color};
        background-color: {blockquote_bg};
        color: {secondary_text_color};
        border-radius: {border_radius};
    """

    # 行内代码样式 - 根据背景亮度调整文字颜色
    code_bg_rgb = _hex_to_rgb(code_bg.lstrip('#') if code_bg.startswith('#') else code_bg)
    if ',' in code_bg_rgb:
        cbr, cbg, cbb = int(code_bg_rgb.split(',')[0].strip()), int(code_bg_rgb.split(',')[1].strip()), int(code_bg_rgb.split(',')[2].strip())
        is_code_bg_dark = (cbr * 0.299 + cbg * 0.587 + cbb * 0.114) < 128
    else:
        is_code_bg_dark = False

    inline_code_text_color = "#ffffff" if is_code_bg_dark else primary_color

    code_inline_style = f"""
        padding: 2px 6px;
        background-color: {code_bg};
        border-radius: 3px;
        font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
        font-size: 0.9em;
        color: {inline_code_text_color};
    """

    # 使用代码高亮主题的背景色和文字颜色
    code_bg_color = code_theme.get("bg", "#282c34")
    code_text_color = code_theme.get("text_color", "#abb2bf")

    code_block_style = f"""
        margin: 15px 0;
        padding: 15px;
        background-color: {code_bg_color};
        border-radius: {border_radius};
        overflow-x: auto;
        font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
        font-size: 0.85em;
        line-height: 1.6;
        color: {code_text_color};
    """

    # 代码块内 code 的样式（透明背景，使用主题文字颜色）
    code_in_block_style = f"background: transparent; padding: 0; color: inherit;"

    # 表格样式 - 根据主题风格定制
    # 使用 secondary_color 作为边框颜色，accent_color 作为条纹背景
    table_border_color = secondary_color
    table_stripe_color = f"rgba({_hex_to_rgb(accent_color)}, 0.08)"
    table_hover_color = f"rgba({_hex_to_rgb(primary_color)}, 0.05)"

    # 判断是否为深色主题（用于调整表格样式）
    bg_rgb = _hex_to_rgb(bg_color)
    r, g, b = int(bg_rgb.split(',')[0].strip()), int(bg_rgb.split(',')[1].strip()), int(bg_rgb.split(',')[2].strip())
    is_dark_theme = (r * 0.299 + g * 0.587 + b * 0.114) < 128

    # 深色主题使用不同的边框和条纹颜色
    table_bg_color = "transparent"
    td_bg_color = "transparent"
    td_bg_even = table_stripe_color

    if is_dark_theme:
        table_border_color = f"rgba(255, 255, 255, 0.2)"
        table_stripe_color = f"rgba(255, 255, 255, 0.05)"
        table_bg_color = bg_color  # 表格使用主题背景色
        td_bg_color = bg_color     # 单元格也使用主题背景色
        td_bg_even = f"rgba(255, 255, 255, 0.08)"  # 条纹行稍亮

    table_style = f"""
        width: 100%;
        margin: 15px 0;
        border-collapse: collapse;
        border: 1px solid {table_border_color};
        border-radius: {border_radius};
        overflow: hidden;
        box-shadow: {shadow};
        background-color: {table_bg_color};
    """

    # 表头样式 - 根据主题风格定制，使用更鲜艳的主题色
    # 判断主色调亮度，决定表头文字颜色
    primary_rgb = _hex_to_rgb(primary_color)
    pr, pg, pb = int(primary_rgb.split(',')[0].strip()), int(primary_rgb.split(',')[1].strip()), int(primary_rgb.split(',')[2].strip())
    is_primary_dark = (pr * 0.299 + pg * 0.587 + pb * 0.114) < 128

    # 根据主题特性选择表头样式 - 优先使用 secondary_color（更鲜艳）
    h1_style_type = styles.get("h1_style", "bottom_border")

    # 表头样式映射 - 使用鲜艳的主题色
    if h1_style_type in ["neon", "gradient_bg"]:
        # 霓虹/渐变风格主题 - 使用渐变背景
        th_bg = f"linear-gradient(135deg, {primary_color}, {secondary_color})"
        th_text_color = "#ffffff"
    elif h1_style_type in ["double_bottom", "double_left"]:
        # 传统风格主题 - 使用主色调（红色等）
        th_bg = primary_color
        th_text_color = "#ffffff"
    elif h1_style_type in ["thin_bottom", "thin_left"]:
        # 极简风格主题 - 使用浅色背景+深色文字
        th_bg = f"rgba({_hex_to_rgb(secondary_color)}, 0.15)"
        th_text_color = secondary_color
    elif h1_style_type in ["leaf_deco", "wave_bottom"]:
        # 自然/清新风格 - 使用鲜艳的绿色/蓝色
        th_bg = primary_color
        th_text_color = "#ffffff"
    elif h1_style_type in ["ribbon"]:
        # 缎带风格 - 使用渐变
        th_bg = f"linear-gradient(135deg, {primary_color}, {secondary_color})"
        th_text_color = "#ffffff"
    elif h1_style_type in ["background"]:
        # 背景风格 - 使用渐变
        th_bg = f"linear-gradient(135deg, {primary_color}, {secondary_color})"
        th_text_color = "#ffffff"
    elif h1_style_type in ["gradient_bottom"]:
        # 渐变下边框风格 - 使用橙色渐变
        th_bg = f"linear-gradient(135deg, {primary_color}, {secondary_color})"
        th_text_color = "#ffffff"
    elif h1_style_type in ["left_bottom"]:
        # 科技风格 - 使用蓝色
        th_bg = secondary_color
        th_text_color = "#ffffff"
    elif h1_style_type in ["government"]:
        # 政务风格 - 红色+金色点缀
        th_bg = primary_color
        th_text_color = "#ffffff"
    elif h1_style_type in ["finance"]:
        # 金融风格 - 深蓝+金色
        th_bg = f"linear-gradient(135deg, {primary_color}, {secondary_color})"
        th_text_color = "#ffffff"
    else:
        # 默认 - 使用 secondary_color（蓝色等鲜艳色）
        th_bg = secondary_color
        th_text_color = "#ffffff"

    # 深色主题特殊处理
    if is_dark_theme:
        th_bg = f"linear-gradient(135deg, {primary_color}, {secondary_color})"
        th_text_color = "#ffffff"

    th_style = f"""
        padding: 12px 14px;
        background: {th_bg};
        color: {th_text_color};
        font-weight: bold;
        text-align: left;
        border: 1px solid {secondary_color};
    """

    # 奇数行 td 样式
    td_style = f"""
        padding: 10px 14px;
        border: 1px solid {table_border_color};
        color: {text_color};
        background-color: {td_bg_color};
    """

    # 偶数行 td 样式（条纹效果）
    td_style_even = f"""
        padding: 10px 14px;
        border: 1px solid {table_border_color};
        color: {text_color};
        background-color: {td_bg_even};
    """

    list_style = f"""
        margin: 10px 0;
        padding-left: 25px;
        color: {text_color};
    """

    li_style = f"""
        margin: 5px 0;
        color: {text_color};
    """

    hr_style = f"""
        margin: 20px 0;
        border: none;
        height: 2px;
        background: linear-gradient(to right, {primary_color}, {secondary_color});
        border-radius: 2px;
    """

    img_style = f"""
        max-width: 100%;
        height: auto;
        display: block;
        margin: 15px auto;
        border-radius: {border_radius};
    """

    # 应用样式到内容
    styled_content = content

    # 先处理代码块内的 code 标签，用临时标记替换
    styled_content = re.sub(
        r'<pre class="code-block" data-lang="([^"]*)"><code>',
        r'<pre class="code-block" data-lang="\1" data-code-inner="true"><code-inner>',
        styled_content
    )

    # 处理表格 - 为每一行添加交替样式
    def style_table_rows(match):
        table_content = match.group(1)
        # 找到所有行
        rows = re.findall(r'<tr>(.*?)</tr>', table_content, re.DOTALL)
        styled_rows = []
        for idx, row in enumerate(rows):
            # 检查是否为表头行（包含 th）
            if '<th' in row:
                # 表头行 - 处理带或不带 style 属性的 th
                def replace_th(m):
                    existing_style = m.group(1) or ''
                    # 合并样式，保留原有的 text-align
                    merged_style = th_style.rstrip()
                    if 'text-align' in existing_style:
                        align_match = re.search(r'text-align:\s*[^;]+', existing_style)
                        if align_match:
                            merged_style = align_match.group(0) + '; ' + merged_style
                    return f'<th style="{merged_style}">'
                styled_row = re.sub(r'<th(?:\s+style=\"([^\"]*)\")?>', replace_th, row)
                styled_rows.append(f'<tr>{styled_row}</tr>')
            else:
                # 数据行 - 交替背景，处理带或不带 style 属性的 td
                current_td_style = td_style if idx % 2 == 1 else td_style_even
                def replace_td(m):
                    existing_style = m.group(1) or ''
                    merged_style = current_td_style.rstrip()
                    if 'text-align' in existing_style:
                        align_match = re.search(r'text-align:\s*[^;]+', existing_style)
                        if align_match:
                            merged_style = align_match.group(0) + '; ' + merged_style
                    return f'<td style="{merged_style}">'
                styled_row = re.sub(r'<td(?:\s+style=\"([^\"]*)\")?>', replace_td, row)
                styled_rows.append(f'<tr>{styled_row}</tr>')
        return f'<table style="{table_style}">{"".join(styled_rows)}</table>'

    # 替换表格（先处理表格，避免与其他样式冲突）
    styled_content = re.sub(r'<table>(.*?)</table>', style_table_rows, styled_content, flags=re.DOTALL)

    # 应用其他样式（排除表格相关，因为上面已处理）
    replacements = [
        (r'<h1>', f'<h1 style="{h1_style}">'),
        (r'</h1>', '</h1>'),
        (r'<h2>', f'<h2 style="{h2_style}">'),
        (r'</h2>', '</h2>'),
        (r'<h3>', f'<h3 style="{h3_style}">'),
        (r'</h3>', '</h3>'),
        (r'<h4>', f'<h4 style="{h3_style}">'),
        (r'<h5>', f'<h5 style="{h3_style}">'),
        (r'<h6>', f'<h6 style="{h3_style}">'),
        (r'<p>', f'<p style="{p_style}">'),
        (r'<blockquote>', f'<blockquote style="{blockquote_style}">'),
        (r'<code>', f'<code style="{code_inline_style}">'),
        (r'<ul>', f'<ul style="{list_style}">'),
        (r'<ol>', f'<ol style="{list_style}">'),
        (r'<li>', f'<li style="{li_style}">'),
        (r'<hr\s*/?>', f'<hr style="{hr_style}">'),
        # 只匹配没有 data-slider-img 属性的图片，避免覆盖幻灯片图片样式
        (r'<img(?![^>]*data-slider-img)', f'<img style="{img_style}"'),
    ]

    for pattern, replacement in replacements:
        styled_content = re.sub(pattern, replacement, styled_content)

    # 恢复代码块并应用正确的样式
    styled_content = re.sub(
        r'<pre class="code-block" data-lang="([^"]*)" data-code-inner="true"><code-inner>',
        f'<pre class="code-block" data-lang="\\1" style="{code_block_style}"><code style="{code_in_block_style}">',
        styled_content
    )

    # 包装完整HTML
    full_html = f'''
<section style="{wrapper_style}">
{styled_content}
</section>
'''

    return full_html.strip()


@app.route('/')
def index():
    """首页"""
    return render_template('index.html',
                          themes=build_theme_cards(),
                          code_themes=CODE_THEMES,
                          font_sizes=FONT_SIZES,
                          backgrounds=BACKGROUNDS,
                          ai_enabled=has_ai_capability(),
                          qr_enabled=QR_CODE_AVAILABLE,
                          ai_defaults={
                              'text': {
                                  'base_url': os.getenv("OPENAI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai"),
                                  'model': os.getenv("OPENAI_TEXT_MODEL", "gemini-2.5-flash")
                              },
                              'image': {
                                  'base_url': os.getenv("OPENAI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai"),
                                  'model': os.getenv("OPENAI_IMAGE_TOOL_MODEL", "imagen-4.0-generate-001")
                              }
                          })


@app.route('/share/<share_id>')
def share_article(share_id):
    """分享页。"""
    payload = load_share_payload(share_id)
    if not payload:
        abort(404, description="分享内容不存在或已失效")

    settings = payload.get("settings") or {}
    theme, code_theme, font_size, background = normalize_render_options(
        settings.get("theme", "default"),
        settings.get("code_theme", "github"),
        settings.get("font_size", "medium"),
        settings.get("background", "warm")
    )

    markdown_text = payload.get("markdown", "")
    article_html = payload.get("html") or process_markdown(
        markdown_text,
        theme,
        code_theme,
        font_size,
        background
    )
    title = payload.get("title") or find_first_heading(markdown_text) or "未命名文章"
    excerpt = payload.get("excerpt") or extract_plain_text_from_markdown(markdown_text)[:160]

    return render_template(
        "share.html",
        title=title,
        excerpt=excerpt,
        article_html=article_html,
        share_url=payload.get("share_url") or request.url,
        theme_name=THEMES[theme]["name"],
        created_at_label=format_share_timestamp(payload.get("created_at")),
        code_theme_name=CODE_THEMES[code_theme]["name"]
    )


@app.route('/api/convert', methods=['POST'])
def api_convert():
    """API接口：转换Markdown为HTML"""
    try:
        data = request.get_json()

        if not data or 'markdown' not in data:
            return jsonify({
                'success': False,
                'error': '请提供markdown内容'
            }), 400

        md_text = data['markdown']
        theme, code_theme, font_size, background = normalize_render_options(
            data.get('theme', 'default'),
            data.get('code_theme', 'github'),
            data.get('font_size', 'medium'),
            data.get('background', 'warm')
        )

        html = process_markdown(md_text, theme, code_theme, font_size, background)

        return jsonify({
            'success': True,
            'html': html,
            'theme': THEMES[theme],
            'font_size': FONT_SIZES[font_size],
            'background': BACKGROUNDS[background]
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/share', methods=['POST'])
def api_share():
    """创建分享页面。"""
    try:
        data = request.get_json() or {}
        md_text = data.get("markdown", "")
        if not md_text.strip():
            return jsonify({
                "success": False,
                "error": "请先输入文章内容"
            }), 400

        theme, code_theme, font_size, background = normalize_render_options(
            data.get("theme", "default"),
            data.get("code_theme", "github"),
            data.get("font_size", "medium"),
            data.get("background", "warm")
        )

        ensure_share_storage_dir()
        share_id = uuid.uuid4().hex[:12]
        share_url = url_for("share_article", share_id=share_id, _external=True)
        payload = build_share_payload(
            md_text,
            theme,
            code_theme,
            font_size,
            background,
            share_id,
            share_url
        )

        share_path = get_share_file_path(share_id)
        with share_path.open("w", encoding="utf-8") as fp:
            json.dump(payload, fp, ensure_ascii=False, indent=2)

        return jsonify({
            "success": True,
            "share_id": share_id,
            "share_url": share_url,
            "title": payload["title"],
            "created_at_label": format_share_timestamp(payload["created_at"]),
            "qr_svg": create_share_qr_svg(share_url)
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/ai/title-suggestions', methods=['POST'])
def api_ai_title_suggestions():
    """AI 标题建议。"""
    try:
        data = request.get_json() or {}
        md_text = data.get('markdown', '')
        ai_config = data.get('ai_config') or {}
        if not md_text.strip():
            return jsonify({'success': False, 'error': '请先输入文章内容'}), 400

        suggestions = generate_ai_title_suggestions(md_text, ai_config=ai_config)
        if not suggestions:
            return jsonify({'success': False, 'error': '未生成可用标题'}), 500

        return jsonify({
            'success': True,
            'suggestions': suggestions
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/ai/summary', methods=['POST'])
def api_ai_summary():
    """AI 文章摘要。"""
    try:
        data = request.get_json() or {}
        md_text = data.get('markdown', '')
        ai_config = data.get('ai_config') or {}
        if not md_text.strip():
            return jsonify({'success': False, 'error': '请先输入文章内容'}), 400

        summary = generate_ai_summary(md_text, ai_config=ai_config)
        return jsonify({
            'success': True,
            'summary': summary
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/ai/generate-image', methods=['POST'])
def api_ai_generate_image():
    """AI 文章配图。"""
    try:
        data = request.get_json() or {}
        md_text = data.get('markdown', '')
        focus_prompt = data.get('focus_prompt', '')
        ai_config = data.get('ai_config') or {}
        if not md_text.strip():
            return jsonify({'success': False, 'error': '请先输入文章内容'}), 400

        result = generate_ai_image(md_text, focus_prompt, ai_config=ai_config)
        return jsonify({
            'success': True,
            'image_data_url': result['image_data_url'],
            'revised_prompt': result.get('revised_prompt', '')
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/themes', methods=['GET'])
def api_themes():
    """API接口：获取所有主题"""
    return jsonify({
        'themes': THEMES,
        'code_themes': CODE_THEMES,
        'font_sizes': FONT_SIZES,
        'backgrounds': BACKGROUNDS,
        'qr_enabled': QR_CODE_AVAILABLE,
        'ai_enabled': has_ai_capability(),
        'ai_defaults': {
            'text': {
                'base_url': os.getenv("OPENAI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai"),
                'model': os.getenv("OPENAI_TEXT_MODEL", "gemini-2.5-flash")
            },
            'image': {
                'base_url': os.getenv("OPENAI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai"),
                'model': os.getenv("OPENAI_IMAGE_TOOL_MODEL", "imagen-4.0-generate-001")
            }
        }
    })


@app.route('/api/health', methods=['GET'])
def api_health():
    """健康检查接口"""
    return jsonify({
        'status': 'ok',
        'service': 'md2wemp',
        'version': '1.0.0'
    })


if __name__ == '__main__':
    app.run(debug=True, port=5566)
