"""
MD2WE - Markdown转微信公众号HTML工具
支持丰富的主题和API调用
"""

from flask import Flask, render_template, request, jsonify, abort, url_for, send_from_directory
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
import logging
import io
import base64
import mimetypes
import html as html_lib
import urllib.parse
import urllib.request
import ssl
import os
import threading
import tempfile
import uuid
import copy
import time
import socket
from pathlib import Path
from datetime import datetime, timezone
from http.client import RemoteDisconnected
from urllib.error import HTTPError, URLError

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    hashes = None
    serialization = None
    padding = None
    rsa = None
    AESGCM = None
    CRYPTOGRAPHY_AVAILABLE = False

try:
    import qrcode
    from qrcode.image.svg import SvgPathImage
    QR_CODE_AVAILABLE = True
except ImportError:
    qrcode = None
    SvgPathImage = None
    QR_CODE_AVAILABLE = False

try:
    from PIL import Image, ImageOps, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    Image = None
    ImageOps = None
    ImageDraw = None
    ImageFont = None
    PIL_AVAILABLE = False

try:
    from google import genai as google_genai
    from google.genai import types as google_genai_types
    GOOGLE_GENAI_AVAILABLE = True
except ImportError:
    google_genai = None
    google_genai_types = None
    GOOGLE_GENAI_AVAILABLE = False

app = Flask(__name__)
CORS(app)
DEFAULT_SHARE_STORAGE_DIR = Path(app.root_path) / "data" / "shares"
AI_CRYPTO_KEY_PATH = Path(app.instance_path) / "ai_config_private_key.pem"
AI_CRYPTO_FALLBACK_KEY_PATH = Path(tempfile.gettempdir()) / "md2we" / "ai_config_private_key.pem"
ILLUSTRATION_JOB_STORAGE_DIR = Path(app.instance_path) / "illustration_jobs"
WECHAT_API_BASE = "https://api.weixin.qq.com/cgi-bin"
WECHAT_INLINE_IMAGE_MAX_BYTES = 1024 * 1024
WECHAT_THUMB_IMAGE_MAX_BYTES = 64 * 1024
AI_CONFIG_CRYPTO_VERSION = "rsa-oaep-aes-gcm-v1"
SITE_NAME = os.getenv("SITE_NAME", "MD2WE")
SITE_DESCRIPTION = os.getenv(
    "SITE_DESCRIPTION",
    "MD2WE 是一个面向微信公众号排版的 Markdown 编辑器，支持主题排版、Mermaid、AI 辅助创作、分享页和公众号草稿推送。"
).strip()
GOOGLE_ANALYTICS_MEASUREMENT_ID = (os.getenv("GA_MEASUREMENT_ID", "") or "").strip()
_ACTIVE_SHARE_STORAGE_DIR = None
UPLOAD_IMAGE_MAX_BYTES = 10 * 1024 * 1024
UPLOAD_IMAGE_ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif"
}
ILLUSTRATION_JOB_TTL_SECONDS = 60 * 60
_ILLUSTRATION_JOBS_LOCK = threading.Lock()
AI_REQUEST_MAX_ATTEMPTS = 3
AI_REQUEST_RETRY_BACKOFF_SECONDS = 2


def configure_app_logging():
    """将应用日志稳定输出到控制台。"""
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
    )
    stream_handler_exists = any(isinstance(handler, logging.StreamHandler) for handler in app.logger.handlers)
    if not stream_handler_exists:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        app.logger.addHandler(stream_handler)
    else:
        for handler in app.logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.setFormatter(formatter)

    app.logger.setLevel(logging.INFO)
    app.logger.propagate = False


configure_app_logging()


def get_utc_timestamp():
    """返回当前 UTC 时间戳。"""
    return time.time()


def get_utc_iso_timestamp():
    """返回当前 UTC ISO 时间。"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ensure_illustration_job_storage_dir():
    """确保一键配图任务目录存在。"""
    ILLUSTRATION_JOB_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    return ILLUSTRATION_JOB_STORAGE_DIR


def get_illustration_job_file_path(job_id):
    """返回任务文件路径。"""
    return ensure_illustration_job_storage_dir() / f"{job_id}.json"


def load_illustration_job_from_path(job_path):
    """从磁盘读取任务数据。"""
    try:
        with job_path.open("r", encoding="utf-8") as fp:
            job = json.load(fp)
    except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError):
        return None

    if not isinstance(job, dict):
        return None
    return job


def persist_illustration_job(job):
    """使用原子替换写入任务状态，供多进程共享读取。"""
    if not isinstance(job, dict):
        raise ValueError("illustration job must be a dict")

    ensure_illustration_job_storage_dir()
    job_id = (job.get("job_id") or "").strip()
    if not job_id:
        raise ValueError("illustration job_id is required")

    job_path = get_illustration_job_file_path(job_id)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(job_path.parent),
        delete=False
    ) as fp:
        json.dump(job, fp, ensure_ascii=False, indent=2)
        temp_path = Path(fp.name)
    os.replace(temp_path, job_path)


def cleanup_illustration_jobs():
    """清理过期的一键配图任务。"""
    now = get_utc_timestamp()
    ensure_illustration_job_storage_dir()

    with _ILLUSTRATION_JOBS_LOCK:
        for job_path in ILLUSTRATION_JOB_STORAGE_DIR.glob("*.json"):
            job = load_illustration_job_from_path(job_path)
            if not job:
                try:
                    job_path.unlink()
                except FileNotFoundError:
                    pass
                except OSError:
                    continue
                continue

            updated_at_ts = float(job.get("updated_at_ts") or 0)
            if now - updated_at_ts > ILLUSTRATION_JOB_TTL_SECONDS:
                try:
                    job_path.unlink()
                except FileNotFoundError:
                    pass
                except OSError:
                    continue


def create_illustration_job(style_key, public_base_url):
    """创建一键配图后台任务。"""
    cleanup_illustration_jobs()
    now_iso = get_utc_iso_timestamp()
    now_ts = get_utc_timestamp()
    job_id = uuid.uuid4().hex
    normalized_style_key, style_config = normalize_article_illustration_style(style_key)
    job = {
        "job_id": job_id,
        "status": "queued",
        "stage": "queued",
        "message": "任务已创建，等待开始。",
        "progress_percent": 0,
        "completed_segments": 0,
        "total_segments": 0,
        "segments": [],
        "markdown": "",
        "style": {
            "key": normalized_style_key,
            "label": style_config["label"]
        },
        "error": "",
        "created_at": now_iso,
        "updated_at": now_iso,
        "updated_at_ts": now_ts,
        "public_base_url": public_base_url
    }
    with _ILLUSTRATION_JOBS_LOCK:
        persist_illustration_job(job)
    return copy.deepcopy(job)


def update_illustration_job(job_id, **changes):
    """更新一键配图任务状态。"""
    cleanup_illustration_jobs()
    with _ILLUSTRATION_JOBS_LOCK:
        job = load_illustration_job_from_path(get_illustration_job_file_path(job_id))
        if not job:
            return None

        for key, value in changes.items():
            if value is not None:
                job[key] = value

        job["updated_at"] = get_utc_iso_timestamp()
        job["updated_at_ts"] = get_utc_timestamp()
        persist_illustration_job(job)
        return copy.deepcopy(job)


def get_illustration_job(job_id):
    """读取一键配图任务。"""
    cleanup_illustration_jobs()
    with _ILLUSTRATION_JOBS_LOCK:
        job = load_illustration_job_from_path(get_illustration_job_file_path(job_id))
        if not job:
            return None
        return copy.deepcopy(job)


def serialize_illustration_job(job):
    """输出前端可消费的任务信息。"""
    if not job:
        return None

    payload = copy.deepcopy(job)
    payload.pop("updated_at_ts", None)
    payload.pop("public_base_url", None)
    return payload


def get_ai_retry_delay(attempt_index):
    """返回 AI 请求重试前的退避秒数。"""
    return AI_REQUEST_RETRY_BACKOFF_SECONDS * max(1, attempt_index)


def is_retryable_http_status(status_code):
    """判断 HTTP 状态码是否适合自动重试。"""
    return status_code in {408, 409, 425, 429, 500, 502, 503, 504}


def is_retryable_ai_exception(exc):
    """判断 AI 请求异常是否适合自动重试。"""
    if isinstance(exc, (URLError, TimeoutError, socket.timeout, ConnectionResetError, ConnectionAbortedError, BrokenPipeError, RemoteDisconnected)):
        return True

    message = str(exc or "").strip().lower()
    retryable_markers = (
        "server disconnected without sending a response",
        "remote end closed connection without response",
        "connection reset by peer",
        "connection aborted",
        "temporarily unavailable",
        "timed out",
        "timeout",
        "eof",
        "502 bad gateway",
        "503 service unavailable",
        "504 gateway timeout"
    )
    return any(marker in message for marker in retryable_markers)


def normalize_ai_exception_message(exc, capability="text", attempts=1):
    """把底层网络错误转换成更清晰的中文消息。"""
    raw_message = str(exc or "").strip()
    if is_retryable_ai_exception(exc):
        capability_label = "图片服务" if capability == "image" else "文本服务"
        return f"AI {capability_label}连接中断，已自动重试 {attempts} 次仍未成功，请稍后重试"
    return raw_message or "AI 请求失败"


class AIConfigCryptoError(ValueError):
    """AI 参数加解密失败。"""


@app.context_processor
def inject_global_template_vars():
    """注入全局模板变量。"""
    return {
        "google_analytics_measurement_id": GOOGLE_ANALYTICS_MEASUREMENT_ID
    }


def normalize_pem_text(raw_value):
    """将环境变量中的 PEM 文本恢复为标准格式。"""
    return (raw_value or "").strip().replace("\\n", "\n")


def summarize_log_text(text, limit=160):
    """压缩日志文本，避免输出整篇正文。"""
    compact_text = re.sub(r"\s+", " ", (text or "").strip())
    if len(compact_text) <= limit:
        return compact_text
    return f"{compact_text[:limit - 1]}…"


@app.before_request
def log_request_started():
    """输出接口请求日志。"""
    if request.path.startswith("/api/"):
        app.logger.info(
            "API request started path=%s method=%s remote=%s",
            request.path,
            request.method,
            request.remote_addr
        )


@app.after_request
def log_request_finished(response):
    """输出接口响应日志。"""
    if request.path.startswith("/api/"):
        app.logger.info(
            "API request finished path=%s method=%s status=%s",
            request.path,
            request.method,
            response.status_code
        )
    return response


def iter_ai_crypto_key_paths():
    """返回 AI 私钥候选路径，优先使用显式配置。"""
    explicit_path = (os.getenv("AI_CONFIG_PRIVATE_KEY_PATH") or "").strip()
    seen_paths = set()

    candidates = []
    if explicit_path:
        candidates.append(Path(explicit_path).expanduser())
    candidates.extend([AI_CRYPTO_KEY_PATH, AI_CRYPTO_FALLBACK_KEY_PATH])

    for candidate in candidates:
        resolved_candidate = candidate.resolve(strict=False)
        if resolved_candidate in seen_paths:
            continue
        seen_paths.add(resolved_candidate)
        yield candidate


def iter_share_storage_dirs():
    """返回分享数据目录候选列表。"""
    explicit_path = (os.getenv("SHARE_STORAGE_DIR") or "").strip()
    seen_paths = set()

    candidates = []
    if explicit_path:
        candidates.append(Path(explicit_path).expanduser())
    candidates.append(DEFAULT_SHARE_STORAGE_DIR)

    for candidate in candidates:
        resolved_candidate = candidate.resolve(strict=False)
        if resolved_candidate in seen_paths:
            continue
        seen_paths.add(resolved_candidate)
        yield candidate


def is_share_storage_dir_writable(directory):
    """检测分享目录是否可写。"""
    probe_path = directory / f".write-test-{uuid.uuid4().hex}"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe_path.write_text("", encoding="utf-8")
        probe_path.unlink()
        return True
    except OSError as exc:
        app.logger.warning("Unable to write share storage dir %s: %s", directory, exc)
        try:
            if probe_path.exists():
                probe_path.unlink()
        except OSError:
            pass
        return False


def get_active_share_storage_dir():
    """返回当前用于写入的分享目录。"""
    global _ACTIVE_SHARE_STORAGE_DIR

    if _ACTIVE_SHARE_STORAGE_DIR is not None:
        return _ACTIVE_SHARE_STORAGE_DIR

    for candidate in iter_share_storage_dirs():
        if not is_share_storage_dir_writable(candidate):
            continue
        _ACTIVE_SHARE_STORAGE_DIR = candidate
        return _ACTIVE_SHARE_STORAGE_DIR

    raise OSError("没有可写的分享目录，请检查 SHARE_STORAGE_DIR 或挂载目录权限")


def iter_share_image_dirs():
    """返回分享图片目录候选列表。"""
    seen_paths = set()

    for share_dir in iter_share_storage_dirs():
        image_dir = share_dir / "images"
        resolved_candidate = image_dir.resolve(strict=False)
        if resolved_candidate in seen_paths:
            continue
        seen_paths.add(resolved_candidate)
        yield image_dir


def get_active_share_image_dir():
    """返回当前用于写入的分享图片目录。"""
    image_dir = get_active_share_storage_dir() / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    return image_dir


def guess_image_extension(mime_type):
    """根据 MIME 类型推断图片扩展名。"""
    mime_type = (mime_type or "").strip().lower()
    if mime_type == "image/jpeg":
        return ".jpg"
    if mime_type == "image/webp":
        return ".webp"
    if mime_type == "image/gif":
        return ".gif"
    return ".png"


def save_generated_image_bytes(image_bytes, mime_type):
    """保存 AI 生成图片并返回文件名。"""
    image_dir = get_active_share_image_dir()
    extension = guess_image_extension(mime_type)
    filename = f"ai-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:10]}{extension}"
    image_path = image_dir / filename
    image_path.write_bytes(image_bytes)
    return filename


def sanitize_markdown_image_alt(raw_name):
    """根据文件名生成适合 Markdown 的 alt 文本。"""
    alt_text = re.sub(r"[-_]+", " ", Path(raw_name or "").stem).strip()
    alt_text = re.sub(r"\s+", " ", alt_text)
    return alt_text[:80] or "图片"


def save_uploaded_image_bytes(image_bytes, mime_type):
    """保存用户上传图片并返回文件名。"""
    image_dir = get_active_share_image_dir()
    extension = guess_image_extension(mime_type)
    filename = f"upload-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:10]}{extension}"
    image_path = image_dir / filename
    image_path.write_bytes(image_bytes)
    return filename


def load_or_create_ai_crypto_private_key():
    """加载或自动生成用于 AI 参数传输加密的私钥。"""
    private_key_pem = normalize_pem_text(os.getenv("AI_CONFIG_PRIVATE_KEY_PEM", ""))
    if private_key_pem:
        return serialization.load_pem_private_key(private_key_pem.encode("utf-8"), password=None)

    for key_path in iter_ai_crypto_key_paths():
        try:
            if key_path.exists():
                return serialization.load_pem_private_key(key_path.read_bytes(), password=None)
        except OSError as exc:
            app.logger.warning("Unable to read AI private key from %s: %s", key_path, exc)

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    for key_path in iter_ai_crypto_key_paths():
        try:
            key_path.parent.mkdir(parents=True, exist_ok=True)
            key_path.write_bytes(pem_bytes)
            try:
                os.chmod(key_path, 0o600)
            except OSError:
                pass
            return private_key
        except OSError as exc:
            app.logger.warning("Unable to persist AI private key to %s: %s", key_path, exc)

    app.logger.warning("Falling back to an in-memory AI private key because no writable storage path is available")
    return private_key


def build_ai_crypto_state():
    """初始化 AI 参数传输加密所需的密钥。"""
    if not CRYPTOGRAPHY_AVAILABLE:
        return {
            "enabled": False,
            "public_key_pem": ""
        }

    private_key = load_or_create_ai_crypto_private_key()

    public_key_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("utf-8")

    return {
        "enabled": True,
        "private_key": private_key,
        "public_key_pem": public_key_pem
    }


AI_CRYPTO_STATE = build_ai_crypto_state()


def get_ai_crypto_public_config():
    """返回前端可用的 AI 参数加密配置。"""
    return {
        "enabled": AI_CRYPTO_STATE["enabled"],
        "version": AI_CONFIG_CRYPTO_VERSION,
        "publicKeyPem": AI_CRYPTO_STATE.get("public_key_pem", "")
    }


def decode_base64_field(encoded_value, field_name):
    """安全解码 Base64 字段。"""
    try:
        return base64.b64decode((encoded_value or "").encode("utf-8"))
    except Exception as exc:
        raise AIConfigCryptoError(f"AI 加密参数字段无效: {field_name}") from exc


def decrypt_ai_config_payload(encrypted_payload):
    """解密前端提交的 AI 配置。"""
    if not encrypted_payload:
        return {}

    if not AI_CRYPTO_STATE["enabled"]:
        raise AIConfigCryptoError("服务端未启用 AI 参数加密，请安装 cryptography 并重启服务")

    version = (encrypted_payload.get("version") or "").strip()
    if version != AI_CONFIG_CRYPTO_VERSION:
        raise AIConfigCryptoError("AI 加密参数版本不匹配")

    encrypted_key = decode_base64_field(encrypted_payload.get("encrypted_key"), "encrypted_key")
    iv = decode_base64_field(encrypted_payload.get("iv"), "iv")
    ciphertext = decode_base64_field(encrypted_payload.get("ciphertext"), "ciphertext")

    try:
        aes_key = AI_CRYPTO_STATE["private_key"].decrypt(
            encrypted_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        plaintext = AESGCM(aes_key).decrypt(iv, ciphertext, None)
        config = json.loads(plaintext.decode("utf-8"))
    except Exception as exc:
        raise AIConfigCryptoError("AI 加密参数解密失败") from exc

    if not isinstance(config, dict):
        raise AIConfigCryptoError("AI 加密参数格式错误")

    return config


def extract_ai_config_from_request(data):
    """从请求体中提取 AI 配置，优先解密密文。"""
    encrypted_payload = data.get("ai_config_encrypted")
    if encrypted_payload is not None:
        if not isinstance(encrypted_payload, dict):
            raise AIConfigCryptoError("AI 加密参数格式错误")
        return decrypt_ai_config_payload(encrypted_payload)

    ai_config = data.get("ai_config") or {}
    if not isinstance(ai_config, dict):
        raise AIConfigCryptoError("AI 配置格式错误")
    return ai_config


def get_ai_request_data():
    """统一读取 AI 接口请求，并处理 AI 配置加解密。"""
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        raise AIConfigCryptoError("请求体必须是 JSON 对象")
    payload = dict(data)
    payload["ai_config"] = extract_ai_config_from_request(payload)
    return payload

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

ARTICLE_ILLUSTRATION_STYLES = {
    "editorial": {
        "label": "Editorial",
        "prompt": "视觉风格：editorial illustration，杂志感，干净构图，层次清楚，信息表达优先。"
    },
    "notion": {
        "label": "Notion",
        "prompt": "视觉风格：Notion 风格知识插画，简洁几何形、柔和留白、信息组织清晰。"
    },
    "blueprint": {
        "label": "Blueprint",
        "prompt": "视觉风格：蓝图式技术插画，结构线框、系统感、专业克制，适合架构和流程。"
    },
    "warm": {
        "label": "Warm",
        "prompt": "视觉风格：温暖叙事插画，色调柔和，人物和场景自然，但避免装饰性过强。"
    },
    "minimal": {
        "label": "Minimal",
        "prompt": "视觉风格：极简概念插画，元素少而准，版面克制，强调核心关系。"
    },
    "watercolor": {
        "label": "Watercolor",
        "prompt": "视觉风格：淡彩水彩插画，轻质感，柔和渐变，适合人文和场景表达。"
    },
    "scientific": {
        "label": "Scientific",
        "prompt": "视觉风格：科学信息图插画，理性、精确、可视化导向，适合原理和对比。"
    }
}

MAX_ARTICLE_ILLUSTRATIONS = 5


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


def get_article_illustration_style_options():
    """返回前端可用的配图风格选项。"""
    return [
        {
            "key": key,
            "label": value["label"]
        }
        for key, value in ARTICLE_ILLUSTRATION_STYLES.items()
    ]


def normalize_article_illustration_style(style_key):
    """规范化一键配图使用的画风。"""
    normalized_key = (style_key or "").strip().lower()
    if normalized_key not in ARTICLE_ILLUSTRATION_STYLES:
        normalized_key = "editorial"
    return normalized_key, ARTICLE_ILLUSTRATION_STYLES[normalized_key]


def parse_markdown_blocks(md_text):
    """按块解析 Markdown，保留每个块在原文中的行范围。"""
    normalized_text = (md_text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized_text.split("\n")
    blocks = []
    block_start = None
    block_lines = []
    in_fence = False
    fence_char = ""
    fence_length = 0

    def close_block(end_line):
        nonlocal block_start, block_lines
        if block_start is None:
            return
        blocks.append({
            "block_index": len(blocks) + 1,
            "start_line": block_start,
            "end_line": end_line,
            "content": "\n".join(block_lines)
        })
        block_start = None
        block_lines = []

    for line_index, line in enumerate(lines):
        stripped = line.strip()
        fence_match = re.match(r"^\s*(```+|~~~+)", line)

        if block_start is None:
            if not stripped:
                continue
            block_start = line_index
            block_lines = [line]
            if fence_match:
                fence_token = fence_match.group(1)
                in_fence = True
                fence_char = fence_token[0]
                fence_length = len(fence_token)
            continue

        if in_fence:
            block_lines.append(line)
            if fence_match:
                fence_token = fence_match.group(1)
                if fence_token[0] == fence_char and len(fence_token) >= fence_length:
                    in_fence = False
            continue

        if not stripped:
            close_block(line_index - 1)
            continue

        block_lines.append(line)
        if fence_match:
            fence_token = fence_match.group(1)
            in_fence = True
            fence_char = fence_token[0]
            fence_length = len(fence_token)

    close_block(len(lines) - 1)
    return blocks


def get_markdown_block_kind(block_text):
    """粗略识别 Markdown 块类型，用于过滤不适合配图的内容。"""
    stripped = (block_text or "").strip()
    if not stripped:
        return "empty"
    if len(stripped.splitlines()) == 1 and re.match(r"^\s{0,3}#{1,6}\s+.+$", stripped):
        return "heading"
    if re.match(r"^\s*(```+|~~~+)", stripped):
        return "fence"
    if re.search(r"!\[[^\]]*\]\([^)]+\)", stripped):
        return "image"
    if re.match(r"^\s*([-*_])(?:\s*\1){2,}\s*$", stripped):
        return "divider"
    if stripped.startswith("|") and "\n" in stripped:
        return "table"
    if re.match(r"^\s*<[^>]+>", stripped):
        return "html"
    return "text"


def summarize_markdown_block(block_text, limit=220):
    """提取块的纯文本摘要，控制提示词长度。"""
    summary = re.sub(r"\s+", " ", extract_plain_text_from_markdown(block_text))
    if len(summary) <= limit:
        return summary
    return f"{summary[:limit - 1].rstrip()}…"


def is_illustratable_markdown_block(block_text):
    """判断一个 Markdown 块是否适合作为一键配图候选。"""
    if get_markdown_block_kind(block_text) in {"heading", "fence", "image", "divider", "table", "html", "empty"}:
        return False
    return len(summarize_markdown_block(block_text, limit=320)) >= 28


def extract_json_payload_from_text(text):
    """从模型返回文本中提取 JSON。"""
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    candidate_positions = [index for index in [cleaned.find("{"), cleaned.find("[")] if index != -1]
    if not candidate_positions:
        raise RuntimeError("AI 未返回可解析的 JSON 结果")

    start_index = min(candidate_positions)
    end_index = max(cleaned.rfind("}"), cleaned.rfind("]"))
    if end_index < start_index:
        raise RuntimeError("AI 返回的 JSON 结构不完整")

    return json.loads(cleaned[start_index:end_index + 1])


def sanitize_article_illustration_alt_text(raw_text, fallback_text=""):
    """清洗图片 alt 文本，避免过长或过虚。"""
    alt_text = normalize_generated_text(raw_text)
    alt_text = alt_text.strip("\"'“”‘’")
    alt_text = re.sub(r"[，,。；;：:]+$", "", alt_text)
    if count_chinese_chars(alt_text) < 2:
        fallback_plain_text = re.sub(r"\s+", "", extract_plain_text_from_markdown(fallback_text))
        alt_text = fallback_plain_text[:14] or "AI 配图"
    return alt_text[:24]


def normalize_article_illustration_plan(raw_plan, candidate_map):
    """验证并清洗模型返回的插图计划。"""
    plan_items = raw_plan
    if isinstance(raw_plan, dict):
        plan_items = raw_plan.get("plan") or raw_plan.get("items") or raw_plan.get("illustrations") or []

    if not isinstance(plan_items, list):
        raise RuntimeError("AI 返回的插图计划格式错误")

    normalized_items = []
    seen_block_indices = set()

    for item in plan_items:
        if not isinstance(item, dict):
            continue

        block_index = item.get("block_index", item.get("index"))
        try:
            block_index = int(block_index)
        except (TypeError, ValueError):
            continue

        if block_index in seen_block_indices or block_index not in candidate_map:
            continue

        prompt_text = normalize_generated_text(
            item.get("prompt") or item.get("description") or item.get("scene") or ""
        )
        if len(prompt_text) < 12:
            continue

        normalized_items.append({
            "block_index": block_index,
            "alt_text": sanitize_article_illustration_alt_text(item.get("alt_text"), candidate_map[block_index]["content"]),
            "prompt": prompt_text
        })
        seen_block_indices.add(block_index)

        if len(normalized_items) >= MAX_ARTICLE_ILLUSTRATIONS:
            break

    if not normalized_items:
        raise RuntimeError("AI 未返回可用的插图计划")

    return normalized_items


def repair_article_illustration_plan(plan_text, candidate_map, ai_config=None):
    """当模型首轮没有返回合法 JSON 时，要求其仅修复结构。"""
    candidate_ids = sorted(candidate_map.keys())
    repair_system_prompt = (
        "你是一名 JSON 修复助手。"
        "你会把一段不规范的插图计划修复为严格合法的 JSON。"
        "只输出 JSON，不要解释，不要 Markdown 代码块。"
        "格式固定为："
        "{\"plan\":[{\"block_index\":3,\"alt_text\":\"简短中文短语\",\"prompt\":\"一段中文生图描述\"}]}"
    )
    repair_user_prompt = (
        f"可用 block_index 只有这些：{candidate_ids}\n"
        f"最多保留 {MAX_ARTICLE_ILLUSTRATIONS} 个。\n"
        "请删除无效项、重复项、空项，并修复成合法 JSON。\n\n"
        "原始输出如下：\n"
        f"{plan_text}"
    )
    repaired_text = call_openai_text(
        repair_system_prompt,
        repair_user_prompt,
        max_output_tokens=2200,
        retry_max_output_tokens=3200,
        ai_config=ai_config
    )
    raw_plan = extract_json_payload_from_text(repaired_text)
    return normalize_article_illustration_plan(raw_plan, candidate_map)


def fallback_article_illustration_plan(candidates, article_context, style_config, ai_config=None):
    """当结构化计划仍失败时，降级为从核心块中挑选并逐块生成描述。"""
    prioritized_candidates = sorted(
        candidates,
        key=lambda item: len(item.get("preview", "")),
        reverse=True
    )[:MAX_ARTICLE_ILLUSTRATIONS]
    plan_items = []

    for candidate in prioritized_candidates:
        system_prompt = (
            "你是一名中文知识文章插画编辑。"
            "请只为当前段落生成一个适合 16:9 插画的中文画面描述。"
            "返回严格 JSON，不要解释："
            "{\"alt_text\":\"简短中文短语\",\"prompt\":\"一段中文生图描述\"}"
        )
        user_prompt = (
            f"文章标题：{article_context['title']}\n"
            f"整篇背景：{article_context['excerpt']}\n"
            f"指定画风：{style_config['label']}。{style_config['prompt']}\n"
            f"当前段落：{candidate['preview']}\n"
            "要求：突出这一段真正需要可视化的核心概念，不要把修辞字面化，不要包含文字或 Logo。"
        )
        description_text = call_openai_text(
            system_prompt,
            user_prompt,
            max_output_tokens=800,
            retry_max_output_tokens=1200,
            ai_config=ai_config
        )
        try:
            description_data = extract_json_payload_from_text(description_text)
        except Exception:
            description_data = {
                "alt_text": candidate["preview"][:12],
                "prompt": normalize_generated_text(description_text)
            }

        prompt_text = normalize_generated_text(description_data.get("prompt") if isinstance(description_data, dict) else "")
        if len(prompt_text) < 12:
            continue

        plan_items.append({
            "block_index": candidate["block_index"],
            "alt_text": sanitize_article_illustration_alt_text(
                description_data.get("alt_text") if isinstance(description_data, dict) else "",
                candidate["content"]
            ),
            "prompt": prompt_text
        })

    if not plan_items:
        raise RuntimeError("AI 未能生成可用的一键配图计划")

    return plan_items


def build_article_illustration_candidates(md_text):
    """提取一键配图可选的正文块。"""
    blocks = parse_markdown_blocks(md_text)
    candidates = []

    for block in blocks:
        if not is_illustratable_markdown_block(block["content"]):
            continue
        candidates.append({
            **block,
            "preview": summarize_markdown_block(block["content"], limit=220)
        })

    return blocks, candidates


def generate_article_illustration_plan(md_text, style_key, ai_config=None):
    """让文本模型只选择核心段落，并为每段生成图片描述。"""
    style_key, style_config = normalize_article_illustration_style(style_key)
    article_context = build_article_context(md_text, limit=2600)
    blocks, candidates = build_article_illustration_candidates(md_text)

    if not candidates:
        raise RuntimeError("正文中没有找到适合自动配图的核心段落")

    app.logger.info(
        "Illustration planning started title=%s style=%s total_blocks=%s candidate_blocks=%s",
        article_context["title"],
        style_key,
        len(blocks),
        len(candidates)
    )

    candidate_map = {candidate["block_index"]: candidate for candidate in candidates}
    candidate_sections = []
    for candidate in candidates[:36]:
        candidate_sections.append(
            f"[候选块 {candidate['block_index']}]\n"
            f"{candidate['preview']}"
        )

    system_prompt = (
        "你是一名中文知识文章的插画策划编辑。"
        f"你只能从候选块中挑选最值得配图的核心段落，数量不得超过 {MAX_ARTICLE_ILLUSTRATIONS} 个，宁缺毋滥。"
        "优先选择需要可视化解释的概念、结构、流程、对比、场景或关键转折。"
        "不要选择寒暄、铺垫、重复论证、纯总结、纯标题、代码、表格、已有图片。"
        "不要把比喻、修辞或口号字面化。"
        "必须只返回 JSON，不要解释，不要 Markdown 代码块。"
        "格式固定为："
        "{\"plan\":[{\"block_index\":3,\"alt_text\":\"简短中文短语\",\"prompt\":\"一段中文生图描述\"}]}"
        "其中 block_index 必须来自候选块编号；alt_text 保持简短准确；prompt 必须适合 16:9 知识型插画，且不能包含文字、Logo、水印、边框或界面按钮。"
    )
    user_prompt = (
        f"文章标题：{article_context['title']}\n\n"
        f"文章整体摘要：\n{article_context['excerpt']}\n\n"
        f"指定画风：{style_config['label']}。{style_config['prompt']}\n\n"
        "请只选真正值得配图的核心段落，整篇不要超过 5 个。\n\n"
        "候选块列表：\n"
        f"{chr(10).join(candidate_sections)}"
    )

    plan_text = call_openai_text(
        system_prompt,
        user_prompt,
        max_output_tokens=2200,
        retry_max_output_tokens=3200,
        ai_config=ai_config
    )
    try:
        raw_plan = extract_json_payload_from_text(plan_text)
        plan_items = normalize_article_illustration_plan(raw_plan, candidate_map)
    except Exception:
        app.logger.warning("Illustration planning returned non-standard JSON, attempting repair")
        try:
            plan_items = repair_article_illustration_plan(plan_text, candidate_map, ai_config=ai_config)
        except Exception:
            app.logger.warning("Illustration plan repair failed, falling back to per-block generation")
            plan_items = fallback_article_illustration_plan(
                candidates,
                article_context,
                style_config,
                ai_config=ai_config
            )

    app.logger.info(
        "Illustration planning finished title=%s selected_blocks=%s block_indexes=%s",
        article_context["title"],
        len(plan_items),
        [item["block_index"] for item in plan_items]
    )

    return {
        "style_key": style_key,
        "style_config": style_config,
        "blocks": blocks,
        "candidate_map": candidate_map,
        "plan_items": plan_items,
        "article_context": article_context
    }


def build_article_block_image_prompt(article_context, block_text, visual_goal, style_config):
    """将段落与画风整理成单张图片生成提示词。"""
    block_summary = summarize_markdown_block(block_text, limit=1200)
    prompt_parts = [
        "请为一篇中文知识文章中的核心段落生成一张横版插画。",
        style_config["prompt"],
        "画面目标：帮助读者理解该段落的核心意思，而不是做装饰性头图。",
        "输出要求：16:9 横图，不包含任何文字、Logo、水印、边框、按钮、聊天气泡或界面截图。",
        f"整篇文章标题：{article_context['title']}",
        f"整篇文章背景：{article_context['excerpt']}",
        f"当前段落内容：{block_summary}",
        f"这一段要表达的画面重点：{visual_goal}"
    ]
    return "\n".join(prompt_parts)


def insert_images_into_markdown_blocks(md_text, blocks, generated_segments):
    """按块尾行把 Markdown 图片语法精确插回原文。"""
    normalized_text = (md_text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized_text.split("\n")
    block_map = {block["block_index"]: block for block in blocks}
    insertions = {}

    for segment in generated_segments:
        block = block_map.get(segment["block_index"])
        if not block:
            continue
        insertions.setdefault(block["end_line"], []).append(
            f"![{segment['alt_text']}]({segment['image_url']})"
        )

    if not insertions:
        return normalized_text

    result_lines = []
    for line_index, line in enumerate(lines):
        result_lines.append(line)
        snippets = insertions.get(line_index) or []
        for snippet in snippets:
            if result_lines and result_lines[-1].strip():
                result_lines.append("")
            result_lines.append(snippet)
            next_line = lines[line_index + 1] if line_index + 1 < len(lines) else None
            if next_line is not None and next_line.strip():
                result_lines.append("")

    return "\n".join(result_lines)


def trim_meta_text(text, limit=160):
    """裁剪适合 SEO 的描述文本。"""
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if len(clean) <= limit:
        return clean
    return f"{clean[:limit - 1].rstrip()}…"


def get_public_base_url():
    """获取对外公开访问的站点根地址。"""
    configured_url = (os.getenv("SITE_URL", "") or "").strip().rstrip("/")
    if configured_url:
        return configured_url
    return request.url_root.rstrip("/")


def build_public_url(endpoint, public_base_url=None, **values):
    """生成面向搜索引擎和分享卡片的绝对地址。"""
    base_url = (public_base_url or get_public_base_url()).rstrip("/")
    return f"{base_url}{url_for(endpoint, _external=False, **values)}"


def get_default_og_image_url():
    """返回默认 Open Graph 图片地址。"""
    return (os.getenv("DEFAULT_OG_IMAGE_URL", "") or "").strip()


def resolve_share_og_image_url(source, page_url="", allow_local_copy=True):
    """将正文首图解析成可用于 OG 的公开地址。"""
    source = (source or "").strip()
    if not source:
        return ""

    if re.match(r"^https?://", source, re.IGNORECASE):
        return source

    if source.startswith("//"):
        public_scheme = urllib.parse.urlparse(get_public_base_url()).scheme or "https"
        return f"{public_scheme}:{source}"

    if source.startswith("data:"):
        if not allow_local_copy:
            return ""
        raw_bytes, mime_type, _ = fetch_binary_resource(source)
        filename = save_uploaded_image_bytes(raw_bytes, mime_type)
        return build_public_url("share_image_file", filename=filename)

    local_path = resolve_local_resource_path(source)
    if local_path:
        if not allow_local_copy:
            return ""
        mime_type = (mimetypes.guess_type(str(local_path))[0] or "application/octet-stream").lower()
        filename = save_uploaded_image_bytes(local_path.read_bytes(), mime_type)
        return build_public_url("share_image_file", filename=filename)

    if source.startswith("/"):
        return f"{get_public_base_url()}{source}"

    base_url = (page_url or get_public_base_url()).rstrip("/") + "/"
    return urllib.parse.urljoin(base_url, source)


def build_share_og_image_url(md_text, html_content, page_url="", allow_local_copy=True):
    """优先从正文首图生成分享卡片图片地址，没有则回退默认封面。"""
    first_image_source = (
        extract_first_markdown_image_source(md_text)
        or extract_first_html_image_source(html_content)
    )
    try:
        resolved_url = resolve_share_og_image_url(
            first_image_source,
            page_url=page_url,
            allow_local_copy=allow_local_copy
        )
    except Exception as exc:
        app.logger.warning("Unable to resolve share og image source=%s error=%s", first_image_source, exc)
        resolved_url = ""
    return resolved_url or get_default_og_image_url()


def normalize_iso_timestamp(iso_text):
    """将时间统一为 ISO 8601 格式。"""
    if not iso_text:
        return ""

    try:
        dt = datetime.fromisoformat(iso_text.replace("Z", "+00:00"))
    except ValueError:
        return ""
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_homepage_structured_data(canonical_url):
    """构建首页结构化数据。"""
    return {
        "@context": "https://schema.org",
        "@type": "WebApplication",
        "name": SITE_NAME,
        "url": canonical_url,
        "description": SITE_DESCRIPTION,
        "applicationCategory": "BusinessApplication",
        "operatingSystem": "Web",
        "inLanguage": "zh-CN",
        "offers": {
            "@type": "Offer",
            "price": "0",
            "priceCurrency": "USD"
        }
    }


def build_share_structured_data(title, description, canonical_url, published_at, image_url=""):
    """构建分享页结构化数据。"""
    structured_data = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": description,
        "mainEntityOfPage": canonical_url,
        "url": canonical_url,
        "inLanguage": "zh-CN",
        "author": {
            "@type": "Organization",
            "name": SITE_NAME
        },
        "publisher": {
            "@type": "Organization",
            "name": SITE_NAME
        }
    }

    if published_at:
        structured_data["datePublished"] = published_at
        structured_data["dateModified"] = published_at

    if image_url:
        structured_data["image"] = image_url

    return structured_data


def iter_share_sitemap_entries():
    """遍历 sitemap 需要输出的分享页。"""
    entries = []
    seen_share_ids = set()

    for share_dir in iter_share_storage_dirs():
        if not share_dir.exists():
            continue

        for share_path in sorted(share_dir.glob("*.json")):
            try:
                payload = json.loads(share_path.read_text("utf-8"))
            except (OSError, ValueError):
                continue

            share_id = (payload.get("id") or share_path.stem or "").strip()
            if not share_id or share_id in seen_share_ids:
                continue

            seen_share_ids.add(share_id)
            entries.append({
                "loc": build_public_url("share_article", share_id=share_id),
                "lastmod": normalize_iso_timestamp(payload.get("created_at"))
            })

    return entries


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
            "model": (image_config.get("model") or os.getenv("OPENAI_IMAGE_TOOL_MODEL", "gemini-2.5-flash-image")).strip()
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
    get_active_share_storage_dir().mkdir(parents=True, exist_ok=True)


def get_share_file_path(share_id):
    """返回分享文件路径。"""
    safe_id = re.sub(r"[^a-f0-9]", "", (share_id or "").lower())[:32]
    if not safe_id:
        return None
    return get_active_share_storage_dir() / f"{safe_id}.json"


def load_share_payload(share_id):
    """读取分享数据。"""
    safe_id = re.sub(r"[^a-f0-9]", "", (share_id or "").lower())[:32]
    if not safe_id:
        return None

    for share_dir in iter_share_storage_dirs():
        share_path = share_dir / f"{safe_id}.json"
        if not share_path.exists():
            continue
        with share_path.open("r", encoding="utf-8") as fp:
            return json.load(fp)

    return None


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
    og_image_url = build_share_og_image_url(md_text, html, page_url=share_url, allow_local_copy=True)

    return {
        "id": share_id,
        "title": title,
        "excerpt": excerpt,
        "markdown": md_text,
        "html": html,
        "og_image_url": og_image_url,
        "share_url": share_url,
        "created_at": created_at,
        "settings": {
            "theme": theme,
            "code_theme": code_theme,
            "font_size": font_size,
            "background": background
        }
    }


def guess_extension_from_mime(mime_type):
    """根据 MIME 类型推断文件扩展名。"""
    if not mime_type:
        return ".jpg"
    guessed = mimetypes.guess_extension(mime_type.split(";")[0].strip().lower())
    if guessed == ".jpe":
        return ".jpg"
    return guessed or ".jpg"


def decode_data_url(data_url):
    """解析 data URL。"""
    match = re.match(r"^data:([^;,]+)?(;base64)?,(.*)$", data_url, re.IGNORECASE | re.DOTALL)
    if not match:
        raise RuntimeError("不支持的 data URL 格式")

    mime_type = (match.group(1) or "application/octet-stream").strip().lower()
    payload = match.group(3) or ""
    if match.group(2):
        raw_bytes = base64.b64decode(payload)
    else:
        raw_bytes = urllib.parse.unquote_to_bytes(payload)

    return raw_bytes, mime_type


def resolve_local_resource_path(source):
    """尝试将资源路径解析为本地文件。"""
    if not source:
        return None

    candidates = []
    source_path = Path(source)
    if source_path.is_absolute():
        candidates.append(source_path)
    else:
        candidates.append(Path.cwd() / source)
        candidates.append(Path(app.root_path) / source)

    if source.startswith("/"):
        candidates.append(Path(app.root_path) / source.lstrip("/"))

    for candidate in candidates:
        try:
            resolved = candidate.expanduser().resolve()
        except OSError:
            continue
        if resolved.exists() and resolved.is_file():
            return resolved

    return None


def fetch_binary_resource(source):
    """获取图片字节内容，支持 data URL、远程 URL 和本地文件。"""
    source = (source or "").strip()
    if not source:
        raise RuntimeError("图片地址为空")

    if source.startswith("data:"):
        raw_bytes, mime_type = decode_data_url(source)
        return raw_bytes, mime_type, f"embedded{guess_extension_from_mime(mime_type)}"

    if re.match(r"^https?://", source, re.IGNORECASE):
        req = urllib.request.Request(source, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=30, context=ssl.create_default_context()) as response:
                raw_bytes = response.read()
                mime_type = (response.headers.get_content_type() or "").strip().lower()
        except HTTPError as exc:
            raise RuntimeError(f"下载远程图片失败：HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError(f"下载远程图片失败：{exc.reason}") from exc

        parsed = urllib.parse.urlparse(source)
        filename = Path(urllib.parse.unquote(parsed.path)).name or f"remote{guess_extension_from_mime(mime_type)}"
        return raw_bytes, mime_type, filename

    local_path = resolve_local_resource_path(source)
    if not local_path:
        raise RuntimeError(f"无法读取图片资源：{source}")

    mime_type = (mimetypes.guess_type(str(local_path))[0] or "application/octet-stream").lower()
    return local_path.read_bytes(), mime_type, local_path.name


def normalize_image_for_wechat(image_bytes, mime_type, filename, max_bytes, purpose_label):
    """将图片压缩到微信公众号更容易接受的范围。"""
    if not image_bytes:
        raise RuntimeError(f"{purpose_label}为空，无法上传")

    mime_type = (mime_type or "").split(";")[0].strip().lower()
    if not PIL_AVAILABLE:
        if mime_type in {"image/jpeg", "image/png"} and len(image_bytes) <= max_bytes:
            return image_bytes, mime_type, filename
        raise RuntimeError(f"{purpose_label}过大或格式不兼容，且当前环境未安装 Pillow 无法压缩")

    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode not in ("RGB", "L"):
                rgba_image = image.convert("RGBA")
                base = Image.new("RGB", image.size, "#ffffff")
                base.paste(rgba_image, mask=rgba_image.getchannel("A"))
                image = base
            elif image.mode == "L":
                image = image.convert("RGB")

            resampling_attr = getattr(Image, "Resampling", Image)
            resample_filter = getattr(resampling_attr, "LANCZOS", Image.LANCZOS)
            max_side_candidates = (1600, 1280, 1080, 960, 840, 720, 640, 560, 480, 360)
            quality_candidates = (88, 82, 76, 70, 64, 58, 52, 46, 40)

            for max_side in max_side_candidates:
                candidate = image.copy()
                candidate.thumbnail((max_side, max_side), resample_filter)
                for quality in quality_candidates:
                    buffer = io.BytesIO()
                    candidate.save(buffer, format="JPEG", quality=quality, optimize=True)
                    optimized = buffer.getvalue()
                    if len(optimized) <= max_bytes:
                        safe_name = f"{Path(filename).stem or 'wechat-image'}.jpg"
                        return optimized, "image/jpeg", safe_name
    except Exception as exc:
        raise RuntimeError(f"{purpose_label}处理失败：{exc}") from exc

    raise RuntimeError(f"{purpose_label}压缩后仍超过限制，请换更小的图片后重试")


def get_cover_font_candidates():
    """返回一组可能存在的中英文字体路径。"""
    return [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf"
    ]


def load_cover_font(size):
    """加载可用字体，找不到时退回 Pillow 默认字体。"""
    if not PIL_AVAILABLE:
        raise RuntimeError("当前环境未安装 Pillow，无法自动生成封面")

    for font_path in get_cover_font_candidates():
        if Path(font_path).exists():
            try:
                return ImageFont.truetype(font_path, size=size)
            except Exception:
                continue
    return ImageFont.load_default()


def wrap_text_for_cover(text, font, max_width, max_lines=3):
    """按像素宽度切分标题，适合封面排版。"""
    if not text:
        return ["未命名文章"]

    lines = []
    current = ""
    for char in text.strip():
        candidate = f"{current}{char}"
        bbox = font.getbbox(candidate)
        width = bbox[2] - bbox[0]
        if current and width > max_width:
            lines.append(current)
            current = char
        else:
            current = candidate

    if current:
        lines.append(current)

    if len(lines) <= max_lines:
        return lines

    clipped = lines[:max_lines]
    last = clipped[-1]
    while last:
        candidate = f"{last}..."
        bbox = font.getbbox(candidate)
        if bbox[2] - bbox[0] <= max_width:
            clipped[-1] = candidate
            return clipped
        last = last[:-1]

    clipped[-1] = "..."
    return clipped


def simplify_title_for_cover(title, max_chars=22):
    """将标题压缩成更适合封面的短标题。"""
    clean = re.sub(r"\s+", " ", (title or "").strip())
    clean = re.sub(r"[|｜丨｜:：,，;；、]+", " ", clean)
    clean = re.sub(r"\s{2,}", " ", clean).strip()
    if not clean:
        return "未命名文章"
    if len(clean) <= max_chars:
        return clean
    return f"{clean[:max_chars].rstrip()}..."


def generate_default_cover_image(title, digest=""):
    """生成可上传到公众号的默认封面图。"""
    if not PIL_AVAILABLE:
        raise RuntimeError("文章没有图片，且当前环境未安装 Pillow，无法自动生成封面")

    width, height = 900, 500
    canvas = Image.new("RGB", (width, height), "#0b1220")
    draw = ImageDraw.Draw(canvas)

    # 简单大气：纯背景 + 大标题。
    for y in range(height):
        ratio = y / max(height - 1, 1)
        r = int(11 + (22 - 11) * ratio)
        g = int(18 + (38 - 18) * ratio)
        b = int(32 + (68 - 32) * ratio)
        draw.line((0, y, width, y), fill=(r, g, b))

    draw.ellipse((-120, -160, 360, 260), fill="#16315f")
    draw.ellipse((width - 320, height - 250, width + 120, height + 120), fill="#10284d")
    draw.rounded_rectangle((72, 72, width - 72, height - 72), radius=32, outline="#2a4571", width=2)

    title_font = load_cover_font(76)
    text_left = 108
    text_width = width - text_left * 2
    concise_title = simplify_title_for_cover(title)
    title_lines = wrap_text_for_cover(concise_title, title_font, text_width, max_lines=2)

    line_heights = []
    for line in title_lines:
        bbox = title_font.getbbox(line)
        line_heights.append((bbox[3] - bbox[1]) + 18)
    total_height = sum(line_heights) - 18 if line_heights else 0
    current_top = int((height - total_height) / 2)

    for index, line in enumerate(title_lines):
        shadow_offset = 3
        draw.text((text_left + shadow_offset, current_top + shadow_offset), line, font=title_font, fill="#09111d")
        draw.text((text_left, current_top), line, font=title_font, fill="#f8fbff")
        current_top += line_heights[index]

    buffer = io.BytesIO()
    canvas.save(buffer, format="JPEG", quality=78, optimize=True)
    image_bytes = buffer.getvalue()
    return image_bytes, "image/jpeg", "auto-cover.jpg"


def build_multipart_body(fields=None, files=None):
    """构造 multipart/form-data 请求体。"""
    boundary = f"----MD2WE{uuid.uuid4().hex}"
    body = bytearray()

    for key, value in (fields or {}).items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
        body.extend(str(value).encode("utf-8"))
        body.extend(b"\r\n")

    for file_item in files or []:
        field_name = file_item["field_name"]
        filename = file_item["filename"]
        content_type = file_item["content_type"]
        content = file_item["content"]
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8")
        )
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        body.extend(content)
        body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    return bytes(body), boundary


def wechat_api_request(url, method="GET", payload=None, headers=None):
    """请求微信公众号接口并解析 JSON。"""
    request_headers = headers.copy() if headers else {}
    data = None
    if payload is not None:
        if isinstance(payload, (dict, list)):
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        else:
            data = payload

    req = urllib.request.Request(url, data=data, headers=request_headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=60, context=ssl.create_default_context()) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"微信接口请求失败：HTTP {exc.code} {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"微信接口网络请求失败：{exc.reason}") from exc

    try:
        response_data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"微信接口返回了无法解析的响应：{raw[:200]}") from exc

    errcode = response_data.get("errcode")
    if errcode not in (None, 0):
        errmsg = response_data.get("errmsg", "未知错误")
        raise RuntimeError(f"微信接口返回错误：errcode={errcode}, errmsg={errmsg}")

    return response_data


def wechat_get_access_token(app_key, app_secret):
    """使用 AppKey/AppSecret 获取公众号 access token。"""
    url = (
        f"{WECHAT_API_BASE}/token?"
        f"grant_type=client_credential&appid={urllib.parse.quote(app_key)}&secret={urllib.parse.quote(app_secret)}"
    )
    response_data = wechat_api_request(url)
    access_token = (response_data.get("access_token") or "").strip()
    if not access_token:
        raise RuntimeError("未获取到微信公众号 access_token")
    return access_token


def wechat_upload_article_image(access_token, image_bytes, filename, mime_type):
    """上传正文图片到微信公众号素材域名。"""
    body, boundary = build_multipart_body(files=[{
        "field_name": "media",
        "filename": filename,
        "content_type": mime_type,
        "content": image_bytes
    }])
    url = f"{WECHAT_API_BASE}/media/uploadimg?access_token={urllib.parse.quote(access_token)}"
    response_data = wechat_api_request(
        url,
        method="POST",
        payload=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    image_url = (response_data.get("url") or "").strip()
    if not image_url:
        raise RuntimeError("微信未返回正文图片地址")
    return image_url


def wechat_upload_thumb_image(access_token, image_bytes, filename, mime_type):
    """上传封面图并返回 thumb_media_id。"""
    body, boundary = build_multipart_body(files=[{
        "field_name": "media",
        "filename": filename,
        "content_type": mime_type,
        "content": image_bytes
    }])
    url = f"{WECHAT_API_BASE}/material/add_material?access_token={urllib.parse.quote(access_token)}&type=thumb"
    response_data = wechat_api_request(
        url,
        method="POST",
        payload=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    thumb_media_id = (response_data.get("media_id") or "").strip()
    if not thumb_media_id:
        raise RuntimeError("微信未返回封面 thumb_media_id")
    return thumb_media_id


def replace_mermaid_blocks_for_wechat(html_content):
    """将前端 Mermaid 占位块替换为源码代码块，避免公众号正文出现“渲染中”。"""
    pattern = re.compile(r'<div class="md2-mermaid" data-mermaid="([^"]+)"[^>]*>.*?</div></div>', re.DOTALL)

    def repl(match):
        try:
            source = base64.b64decode(match.group(1)).decode("utf-8")
        except Exception:
            source = "Mermaid 图表源码解析失败"
        escaped = html_lib.escape(source)
        return (
            '<pre style="margin: 16px 0; padding: 14px 16px; background: #f5f7fa; color: #1f2937; '
            'border-radius: 8px; overflow-x: auto; white-space: pre-wrap; word-break: break-word;">'
            f'<code>{escaped}</code></pre>'
        )

    return pattern.sub(repl, html_content)


def replace_content_images_with_wechat_urls(html_content, access_token):
    """上传正文中的图片到微信并替换为微信地址。"""
    upload_cache = {}
    pattern = re.compile(r'(<img\b[^>]*\bsrc=["\'])([^"\']+)(["\'][^>]*>)', re.IGNORECASE)

    def repl(match):
        source = match.group(2).strip()
        if not source:
            return match.group(0)
        if "mmbiz.qpic.cn" in source or "mmbiz.qlogo.cn" in source:
            return match.group(0)

        if source not in upload_cache:
            raw_bytes, mime_type, filename = fetch_binary_resource(source)
            normalized_bytes, normalized_mime, normalized_name = normalize_image_for_wechat(
                raw_bytes,
                mime_type,
                filename,
                WECHAT_INLINE_IMAGE_MAX_BYTES,
                "正文图片"
            )
            upload_cache[source] = wechat_upload_article_image(
                access_token,
                normalized_bytes,
                normalized_name,
                normalized_mime
            )

        return f"{match.group(1)}{upload_cache[source]}{match.group(3)}"

    replaced_html = pattern.sub(repl, html_content)
    return replaced_html, len(upload_cache)


def extract_first_markdown_image_source(md_text):
    """提取 Markdown 中第一张图片地址。"""
    match = re.search(r'!\[[^\]]*\]\(([^)\s]+(?:\?[^)]*)?)', md_text)
    if match:
        return match.group(1).strip()
    return ""


def extract_first_html_image_source(html_content):
    """提取 HTML 中第一张非公式图片地址。"""
    pattern = re.compile(r'<img\b([^>]*?)\bsrc=["\']([^"\']+)["\']([^>]*)>', re.IGNORECASE)
    for match in pattern.finditer(html_content):
        attrs = f"{match.group(1)} {match.group(3)}".lower()
        if 'alt="math"' in attrs or "alt='math'" in attrs:
            continue
        return match.group(2).strip()
    return ""


def coerce_bool_flag(value, default):
    """将前端传来的布尔值规范成 0/1。"""
    if value is None:
        return default
    if isinstance(value, bool):
        return 1 if value else 0
    return 1 if str(value).strip().lower() in {"1", "true", "yes", "on"} else 0


def prepare_wechat_article_payload(md_text, theme, code_theme, font_size, background, access_token, meta=None):
    """组装公众号草稿文章数据。"""
    meta = meta or {}
    title = (meta.get("title") or find_first_heading(md_text) or "未命名文章").strip()
    digest = (meta.get("digest") or extract_plain_text_from_markdown(md_text)[:120]).strip()
    author = (meta.get("author") or "").strip()
    content_source_url = (meta.get("content_source_url") or "").strip()

    html_content = process_markdown(md_text, theme, code_theme, font_size, background)
    html_content = replace_mermaid_blocks_for_wechat(html_content)
    html_content, uploaded_image_count = replace_content_images_with_wechat_urls(html_content, access_token)

    cover_source = (
        (meta.get("cover_image") or "").strip()
        or extract_first_markdown_image_source(md_text)
        or extract_first_html_image_source(html_content)
    )
    if cover_source:
        raw_cover_bytes, cover_mime_type, cover_filename = fetch_binary_resource(cover_source)
    else:
        raw_cover_bytes, cover_mime_type, cover_filename = generate_default_cover_image(title, digest)

    cover_bytes, cover_upload_mime, cover_upload_name = normalize_image_for_wechat(
        raw_cover_bytes,
        cover_mime_type,
        cover_filename,
        WECHAT_THUMB_IMAGE_MAX_BYTES,
        "封面图片"
    )
    thumb_media_id = wechat_upload_thumb_image(
        access_token,
        cover_bytes,
        cover_upload_name,
        cover_upload_mime
    )

    return {
        "article": {
            "title": title,
            "author": author,
            "digest": digest,
            "content": html_content,
            "thumb_media_id": thumb_media_id,
            "content_source_url": content_source_url,
            "show_cover_pic": coerce_bool_flag(meta.get("show_cover_pic"), 1),
            "need_open_comment": coerce_bool_flag(meta.get("need_open_comment"), 1),
            "only_fans_can_comment": coerce_bool_flag(meta.get("only_fans_can_comment"), 0)
        },
        "uploaded_image_count": uploaded_image_count
    }


def openai_api_request(path, payload, timeout=60, ai_config=None, capability="text"):
    """调用 OpenAI API。"""
    config = sanitize_ai_config(ai_config)
    target_config = config["text"] if capability == "text" else config["image"]
    api_key = target_config["api_key"]
    if not api_key:
        raise RuntimeError("未配置 OPENAI_API_KEY，AI 功能不可用")

    url = f"{target_config['base_url']}{path}"
    app.logger.info(
        "AI request capability=%s path=%s model=%s base_url=%s",
        capability,
        path,
        target_config["model"],
        target_config["base_url"]
    )
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    for attempt in range(1, AI_REQUEST_MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as response:
                response_json = json.loads(response.read().decode("utf-8"))
                app.logger.info(
                    "AI request completed capability=%s path=%s attempt=%s",
                    capability,
                    path,
                    attempt
                )
                return response_json
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            message = body
            try:
                error_data = json.loads(body)
                message = error_data.get("error", {}).get("message") or body
            except json.JSONDecodeError:
                pass

            if attempt < AI_REQUEST_MAX_ATTEMPTS and is_retryable_http_status(exc.code):
                app.logger.warning(
                    "AI request retrying capability=%s path=%s attempt=%s status=%s message=%s",
                    capability,
                    path,
                    attempt,
                    exc.code,
                    summarize_log_text(message, limit=240)
                )
                time.sleep(get_ai_retry_delay(attempt))
                continue

            app.logger.error(
                "AI request failed capability=%s path=%s status=%s message=%s attempts=%s",
                capability,
                path,
                exc.code,
                summarize_log_text(message, limit=240),
                attempt
            )
            raise RuntimeError(f"OpenAI 请求失败: {message}") from exc
        except Exception as exc:
            if attempt < AI_REQUEST_MAX_ATTEMPTS and is_retryable_ai_exception(exc):
                app.logger.warning(
                    "AI network request retrying capability=%s path=%s attempt=%s error=%s",
                    capability,
                    path,
                    attempt,
                    exc
                )
                time.sleep(get_ai_retry_delay(attempt))
                continue

            app.logger.error(
                "AI network request failed capability=%s path=%s attempts=%s error=%s",
                capability,
                path,
                attempt,
                exc
            )
            raise RuntimeError(normalize_ai_exception_message(exc, capability=capability, attempts=attempt)) from exc


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


def is_chat_completion_truncated(response_data):
    """判断 Chat Completions 是否因 token 上限被截断。"""
    choices = response_data.get("choices", [])
    if not choices:
        return False

    finish_reason = str(choices[0].get("finish_reason", "") or "").strip().lower()
    return finish_reason in {"length", "max_tokens"}


def request_openai_text_completion(system_prompt, user_prompt, max_output_tokens=500, ai_config=None):
    """发起一次 OpenAI-compatible Chat Completions 请求。"""
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
    return text, response_data


def call_openai_text(system_prompt, user_prompt, max_output_tokens=500, ai_config=None, retry_max_output_tokens=None):
    """调用 OpenAI-compatible Chat Completions API 生成文本。"""
    text, response_data = request_openai_text_completion(
        system_prompt,
        user_prompt,
        max_output_tokens=max_output_tokens,
        ai_config=ai_config
    )

    if retry_max_output_tokens and retry_max_output_tokens > max_output_tokens and is_chat_completion_truncated(response_data):
        retry_text, _ = request_openai_text_completion(
            system_prompt,
            user_prompt,
            max_output_tokens=retry_max_output_tokens,
            ai_config=ai_config
        )
        return retry_text

    return text


def normalize_generated_text(text):
    """压缩多余空白，保留单段文本。"""
    return re.sub(r"\s+", " ", (text or "")).strip()


def is_complete_chinese_sentence(text):
    """判断文本是否自然收束，而不是停在半句。"""
    stripped = normalize_generated_text(text)
    if not stripped:
        return False
    return bool(re.search(r'[。！？!?…]["”’』」】）》）\']*$', stripped))


def count_chinese_chars(text):
    """统计文本中的中文字符数量。"""
    return len(re.findall(r'[\u4e00-\u9fff]', text or ""))


def extract_title_candidates(text):
    """从模型返回文本中尽量提取标题候选。"""
    raw_text = (text or "").replace("\r", "\n")
    fragments = []
    for block in raw_text.splitlines():
        cleaned_block = block.strip()
        if not cleaned_block:
            continue
        parts = re.split(r'[|｜/／]+', cleaned_block)
        for part in parts:
            candidate = re.sub(r'^\s*[-*\d.、)\]]+\s*', '', part).strip().strip("\"'“”‘’")
            if candidate:
                fragments.append(candidate)
    return fragments


def normalize_title_candidate(text):
    """清洗标题候选，只保留完整中文标题。"""
    candidate = normalize_generated_text(text).strip("\"'“”‘’")
    candidate = re.sub(r'^\s*[-*\d.、)\]]+\s*', '', candidate)
    candidate = candidate.strip(" ,，;；:：")
    chinese_chars = count_chinese_chars(candidate)
    ascii_letters = len(re.findall(r'[A-Za-z]', candidate))
    if not candidate or chinese_chars < 4 or ascii_letters > 0:
        return ""
    return candidate


def finalize_title_suggestions(candidates):
    """去重并裁剪标题候选。"""
    deduped = []
    seen = set()
    for item in candidates:
        normalized = normalize_title_candidate(item)
        if normalized and normalized not in seen:
            deduped.append(normalized)
            seen.add(normalized)
    return deduped[:5]


def rewrite_incomplete_summary(context, current_summary, ai_config=None):
    """当摘要停在半句或明显过短时，重写为完整摘要。"""
    system_prompt = (
        "你是一名中文编辑，正在为社交媒体分享卡片重写摘要。"
        "你会把一段未完成、停在半句或长度不足的摘要，改写成一段完整、顺畅、适合转发预览的中文摘要。"
        "要求输出单段正文，长度控制在 60 到 100 个中文字符，信息密度高，语气自然，有吸引力，但不要夸张失真。"
        "不要使用项目符号，不要加引号，不要解释，结尾必须自然收束，并以中文句号、问号或感叹号结束。"
    )
    user_prompt = (
        f"文章标题: {context['title']}\n\n"
        f"文章正文:\n{context['excerpt']}\n\n"
        f"当前未完成摘要（仅供参考，可能停在半句）:\n{current_summary}"
    )
    return normalize_generated_text(
        call_openai_text(
            system_prompt,
            user_prompt,
            max_output_tokens=1000,
            retry_max_output_tokens=1600,
            ai_config=ai_config
        )
    )


def generate_ai_title_suggestions(md_text, focus_prompt="", ai_config=None):
    """基于文章内容生成标题建议。"""
    context = build_article_context(md_text)
    system_prompt = (
        "你是一名中文内容编辑，正在为社交媒体分享场景撰写中文标题。"
        "请根据文章内容生成更容易吸引用户点开和转发的标题建议。"
        "标题必须准确、鲜明、有传播力，但不能夸张失真或标题党。"
        "必须只输出中文标题，不要夹杂英文单词、英文标点或中英混写。"
        "固定返回 5 行标题，每行一个，不要编号，不要解释，不要输出少于 5 个。"
    )
    user_prompt = (
        f"文章标题（如有）: {context['title']}\n\n"
        f"文章正文摘要:\n{context['excerpt']}"
    )
    if focus_prompt and focus_prompt.strip():
        user_prompt = f"{user_prompt}\n\n额外标题偏向：{focus_prompt.strip()}"
    text = call_openai_text(
        system_prompt,
        user_prompt,
        max_output_tokens=560,
        retry_max_output_tokens=960,
        ai_config=ai_config
    )
    suggestions = finalize_title_suggestions(extract_title_candidates(text))

    if len(suggestions) < 5:
        retry_system_prompt = (
            "你是一名中文新媒体编辑。请严格补齐缺少的中文标题候选。"
            "每个标题都必须是完整中文句子，禁止出现英文单词、缩写、emoji、编号或解释。"
            "标题要适合社交媒体分享，能吸引点击，但不能标题党。"
            f"当前已有标题: {' / '.join(suggestions) if suggestions else '无'}。"
            f"请补充 {5 - len(suggestions)} 个不同的新标题。"
            "固定逐行输出，每行 1 个标题。"
        )
        retry_text = call_openai_text(
            retry_system_prompt,
            user_prompt,
            max_output_tokens=680,
            retry_max_output_tokens=1200,
            ai_config=ai_config
        )
        suggestions = finalize_title_suggestions(suggestions + extract_title_candidates(retry_text))

    if len(suggestions) < 5:
        rewrite_prompt = (
            "请重新输出 5 个完整中文标题。"
            "固定逐行输出，每行 1 个，不要编号，不要解释，不要英文。"
        )
        rewrite_text = call_openai_text(
            system_prompt,
            f"{user_prompt}\n\n补充要求:\n{rewrite_prompt}",
            max_output_tokens=820,
            retry_max_output_tokens=1400,
            ai_config=ai_config
        )
        suggestions = finalize_title_suggestions(suggestions + extract_title_candidates(rewrite_text))

    return suggestions[:5]


def generate_ai_summary(md_text, focus_prompt="", ai_config=None):
    """生成文章摘要。"""
    context = build_article_context(md_text)
    system_prompt = (
        "你是一名中文编辑，正在为社交媒体分享卡片撰写摘要。"
        "请输出一段适合转发预览、能激发继续阅读兴趣的摘要。"
        "要求 60 到 100 个中文字符，信息密度高，语气自然，有吸引力，但不要夸张失真，不要使用项目符号，不要以“本文”开头。"
        "输出必须是完整单段，不能停在半句，结尾必须自然收束，并以中文句号、问号或感叹号结束。"
    )
    user_prompt = (
        f"文章标题: {context['title']}\n\n"
        f"文章正文:\n{context['excerpt']}"
    )
    if focus_prompt and focus_prompt.strip():
        user_prompt = f"{user_prompt}\n\n额外摘要偏向：{focus_prompt.strip()}"
    summary = normalize_generated_text(call_openai_text(
        system_prompt,
        user_prompt,
        max_output_tokens=1000,
        retry_max_output_tokens=1600,
        ai_config=ai_config
    ))

    # if count_chinese_chars(summary) < 60 or count_chinese_chars(summary) > 100 or not is_complete_chinese_sentence(summary):
    #     summary = rewrite_incomplete_summary(context, summary, ai_config=ai_config)
    #
    # if not is_complete_chinese_sentence(summary):
    #     summary = re.sub(r'[，、；：,\s]+$', '', summary).strip()
    #     if summary and summary[-1] not in "。！？":
    #         summary = f"{summary}。"

    return summary


def extract_generated_image(response_data):
    """从 Images API 响应中提取图片。"""
    for item in response_data.get("data", []):
        image_base64 = item.get("b64_json")
        if image_base64:
            return image_base64, item.get("revised_prompt", "")
    raise RuntimeError("AI 没有返回可解析的图片结果")


def is_gemini_native_image_model(model_name):
    """判断图片模型是否应该走 Gemini SDK 原生接口。"""
    model_name = (model_name or "").strip().lower()
    return model_name.startswith("gemini")


def collect_gemini_response_parts(response_data):
    """兼容不同响应结构，提取 Gemini 返回的 parts。"""
    parts = []

    direct_parts = getattr(response_data, "parts", None) or []
    parts.extend(direct_parts)

    for candidate in getattr(response_data, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            parts.append(part)

    return parts


def extract_generated_image_from_gemini_response(response_data):
    """从 Gemini SDK 响应中提取图片与文本。"""
    image_base64 = ""
    mime_type = "image/png"
    text_parts = []

    for part in collect_gemini_response_parts(response_data):
        text_value = getattr(part, "text", None)
        if text_value:
            text_parts.append(str(text_value).strip())

        inline_data = getattr(part, "inline_data", None)
        if not inline_data:
            continue

        mime_type = getattr(inline_data, "mime_type", None) or mime_type
        raw_data = getattr(inline_data, "data", None)
        if isinstance(raw_data, str) and raw_data:
            image_base64 = raw_data.strip()
            break
        if isinstance(raw_data, (bytes, bytearray, memoryview)):
            image_base64 = base64.b64encode(bytes(raw_data)).decode("utf-8")
            break

    if not image_base64:
        raise RuntimeError("Gemini SDK 没有返回可解析的图片结果")

    revised_prompt = "\n".join(item for item in text_parts if item).strip()
    return image_base64, mime_type, revised_prompt


def generate_ai_image_with_gemini_sdk(prompt_text, model_name, api_key):
    """使用 Gemini SDK 原生接口生成图片。"""
    if not GOOGLE_GENAI_AVAILABLE:
        raise RuntimeError("未安装 google-genai，无法使用 Gemini SDK 图片生成")
    if not api_key:
        raise RuntimeError("未配置 Gemini API Key，图片生成不可用")

    client = google_genai.Client(api_key=api_key)
    last_exc = None

    for attempt in range(1, AI_REQUEST_MAX_ATTEMPTS + 1):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt_text,
                config=google_genai_types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=google_genai_types.ImageConfig(
                        aspect_ratio="16:9"
                    )
                )
            )
            return extract_generated_image_from_gemini_response(response)
        except Exception as exc:
            last_exc = exc
            if attempt < AI_REQUEST_MAX_ATTEMPTS and is_retryable_ai_exception(exc):
                app.logger.warning(
                    "Gemini image request retrying model=%s attempt=%s error=%s",
                    model_name,
                    attempt,
                    exc
                )
                time.sleep(get_ai_retry_delay(attempt))
                continue

            app.logger.error(
                "Gemini image request failed model=%s attempts=%s error=%s",
                model_name,
                attempt,
                exc
            )
            raise RuntimeError(normalize_ai_exception_message(exc, capability="image", attempts=attempt)) from exc

    raise RuntimeError(normalize_ai_exception_message(last_exc, capability="image", attempts=AI_REQUEST_MAX_ATTEMPTS))


def generate_ai_image_from_prompt(prompt_text, ai_config=None, public_base_url=None):
    """根据已整理好的提示词生成单张图片。"""
    config = sanitize_ai_config(ai_config)
    image_model = config["image"]["model"]

    if is_gemini_native_image_model(image_model):
        image_base64, mime_type, revised_prompt = generate_ai_image_with_gemini_sdk(
            prompt_text,
            image_model,
            config["image"]["api_key"]
        )
        image_bytes = base64.b64decode(image_base64)
        filename = save_generated_image_bytes(image_bytes, mime_type)
        return {
            "image_url": build_public_url("share_image_file", filename=filename, public_base_url=public_base_url),
            "revised_prompt": revised_prompt
        }

    payload = {
        "model": image_model,
        "prompt": prompt_text,
        "size": "1536x1024",
        "response_format": "b64_json",
        "n": 1
    }
    response_data = openai_api_request("/images/generations", payload, timeout=180, ai_config=config, capability="image")
    image_base64, revised_prompt = extract_generated_image(response_data)
    image_bytes = base64.b64decode(image_base64)
    filename = save_generated_image_bytes(image_bytes, "image/png")
    return {
        "image_url": build_public_url("share_image_file", filename=filename, public_base_url=public_base_url),
        "revised_prompt": revised_prompt
    }


def generate_ai_image(md_text, focus_prompt="", ai_config=None, public_base_url=None):
    """为文章生成配图。"""
    context = build_article_context(md_text, limit=2600)
    prompt_parts = [
        "请为一篇中文文章生成一张横版头图插画。",
        "风格要求：现代 editorial illustration，干净、有层次、适合知识型文章。",
        "输出要求：16:9 横图，不包含任何文字、Logo、水印、边框、按钮或界面元素。",
        f"文章标题：{context['title']}",
        f"文章核心内容：{context['excerpt']}"
    ]
    if focus_prompt:
        prompt_parts.append(f"额外侧重点：{focus_prompt.strip()}")

    return generate_ai_image_from_prompt("\n".join(prompt_parts), ai_config=ai_config, public_base_url=public_base_url)


def illustrate_article_with_ai(md_text, style_key="editorial", ai_config=None, public_base_url=None, progress_callback=None):
    """一键为文章核心段落配图，并将 Markdown 图片语法插回原文。"""
    if not has_ai_capability(ai_config, capability="text") or not has_ai_capability(ai_config, capability="image"):
        raise RuntimeError("一键配图需要同时配置文本模型和图片模型")

    if progress_callback:
        progress_callback(
            stage="planning",
            message="正在分析文章并挑选最值得配图的核心段落。",
            progress_percent=5,
            completed_segments=0,
            total_segments=0
        )

    plan_result = generate_article_illustration_plan(md_text, style_key=style_key, ai_config=ai_config)
    generated_segments = []
    total_segments = len(plan_result["plan_items"])
    app.logger.info(
        "Illustration generation started title=%s style=%s segments=%s",
        plan_result["article_context"]["title"],
        plan_result["style_key"],
        total_segments
    )

    if progress_callback:
        if total_segments:
            progress_callback(
                stage="generating",
                message=f"已锁定 {total_segments} 个核心段落，开始生成第 1 张配图。",
                progress_percent=15,
                completed_segments=0,
                total_segments=total_segments,
                style={
                    "key": plan_result["style_key"],
                    "label": plan_result["style_config"]["label"]
                }
            )
        else:
            progress_callback(
                stage="completed",
                message="这次没有识别到适合自动配图的核心段落。",
                progress_percent=100,
                completed_segments=0,
                total_segments=0,
                style={
                    "key": plan_result["style_key"],
                    "label": plan_result["style_config"]["label"]
                }
            )

    for plan_item in plan_result["plan_items"]:
        current_index = len(generated_segments)
        block = plan_result["candidate_map"][plan_item["block_index"]]
        app.logger.info(
            "Generating illustration block_index=%s alt=%s preview=%s",
            plan_item["block_index"],
            plan_item["alt_text"],
            summarize_log_text(block["content"], limit=120)
        )
        prompt_text = build_article_block_image_prompt(
            plan_result["article_context"],
            block["content"],
            plan_item["prompt"],
            plan_result["style_config"]
        )
        if progress_callback:
            current_number = current_index + 1
            progress_callback(
                stage="generating",
                message=f"正在生成第 {current_number}/{total_segments} 张配图：{plan_item['alt_text']}",
                progress_percent=min(90, 15 + int((current_index / max(total_segments, 1)) * 75)),
                completed_segments=current_index,
                total_segments=total_segments,
                segments=generated_segments,
                current_segment={
                    "block_index": plan_item["block_index"],
                    "alt_text": plan_item["alt_text"],
                    "block_preview": summarize_markdown_block(block["content"], limit=80)
                },
                style={
                    "key": plan_result["style_key"],
                    "label": plan_result["style_config"]["label"]
                }
            )
        image_result = generate_ai_image_from_prompt(
            prompt_text,
            ai_config=ai_config,
            public_base_url=public_base_url
        )
        generated_segments.append({
            "block_index": plan_item["block_index"],
            "alt_text": plan_item["alt_text"],
            "image_url": image_result["image_url"],
            "revised_prompt": image_result.get("revised_prompt", ""),
            "block_preview": summarize_markdown_block(block["content"], limit=80)
        })
        app.logger.info(
            "Illustration generated block_index=%s image_url=%s",
            plan_item["block_index"],
            image_result["image_url"]
        )
        if progress_callback:
            progress_callback(
                stage="generating",
                message=f"已完成 {len(generated_segments)}/{total_segments} 张配图。",
                progress_percent=min(90, 15 + int((len(generated_segments) / max(total_segments, 1)) * 75)),
                completed_segments=len(generated_segments),
                total_segments=total_segments,
                segments=generated_segments,
                style={
                    "key": plan_result["style_key"],
                    "label": plan_result["style_config"]["label"]
                }
            )

    if progress_callback:
        progress_callback(
            stage="writing",
            message="正在把图片 Markdown 插回正文。",
            progress_percent=95,
            completed_segments=len(generated_segments),
            total_segments=total_segments,
            segments=generated_segments,
            style={
                "key": plan_result["style_key"],
                "label": plan_result["style_config"]["label"]
            }
        )

    updated_markdown = insert_images_into_markdown_blocks(
        md_text,
        plan_result["blocks"],
        generated_segments
    )
    app.logger.info(
        "Illustration generation finished title=%s inserted_segments=%s",
        plan_result["article_context"]["title"],
        len(generated_segments)
    )

    return {
        "markdown": updated_markdown,
        "segments": generated_segments,
        "style": {
            "key": plan_result["style_key"],
            "label": plan_result["style_config"]["label"]
        }
    }


def run_article_illustration_job(job_id, md_text, style_key, ai_config, public_base_url):
    """后台执行一键配图任务，并持续刷新进度。"""
    update_illustration_job(
        job_id,
        status="running",
        stage="planning",
        message="任务已启动，正在分析文章结构。",
        progress_percent=3,
        completed_segments=0,
        total_segments=0,
        error=""
    )

    def report_progress(stage, message, progress_percent=None, completed_segments=None, total_segments=None, segments=None, style=None, current_segment=None):
        update_illustration_job(
            job_id,
            status="running",
            stage=stage,
            message=message,
            progress_percent=progress_percent,
            completed_segments=completed_segments,
            total_segments=total_segments,
            segments=copy.deepcopy(segments) if segments is not None else None,
            style=copy.deepcopy(style) if style is not None else None,
            current_segment=copy.deepcopy(current_segment) if current_segment is not None else None
        )

    try:
        with app.app_context():
            with app.test_request_context(base_url=public_base_url):
                result = illustrate_article_with_ai(
                    md_text,
                    style_key=style_key,
                    ai_config=ai_config,
                    public_base_url=public_base_url,
                    progress_callback=report_progress
                )
        update_illustration_job(
            job_id,
            status="succeeded",
            stage="completed",
            message=f"配图完成，已插入 {len(result['segments'])} 张图片。",
            progress_percent=100,
            completed_segments=len(result["segments"]),
            total_segments=len(result["segments"]),
            segments=copy.deepcopy(result["segments"]),
            markdown=result["markdown"],
            style=copy.deepcopy(result["style"]),
            current_segment=None,
            error=""
        )
        app.logger.info(
            "Illustrate article job succeeded job_id=%s inserted_segments=%s",
            job_id,
            len(result["segments"])
        )
    except Exception as exc:
        update_illustration_job(
            job_id,
            status="failed",
            stage="failed",
            message="一键配图失败。",
            error=str(exc),
            current_segment=None
        )
        app.logger.exception("Illustrate article job failed job_id=%s", job_id)


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
    canonical_url = build_public_url("index")
    og_image_url = get_default_og_image_url()
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
                                  'model': os.getenv("OPENAI_IMAGE_TOOL_MODEL", "gemini-2.5-flash-image")
                              }
                          },
                          ai_illustration_styles=get_article_illustration_style_options(),
                          ai_crypto=get_ai_crypto_public_config(),
                          site_name=SITE_NAME,
                          seo_title=f"{SITE_NAME} - Markdown 转微信公众号工具",
                          seo_description=SITE_DESCRIPTION,
                          canonical_url=canonical_url,
                          og_image_url=og_image_url,
                          structured_data=build_homepage_structured_data(canonical_url))


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
    excerpt = trim_meta_text(payload.get("excerpt") or extract_plain_text_from_markdown(markdown_text), 180)
    published_at = normalize_iso_timestamp(payload.get("created_at"))
    canonical_url = build_public_url("share_article", share_id=share_id)
    og_image_url = (
        (payload.get("og_image_url") or "").strip()
        or build_share_og_image_url(markdown_text, article_html, page_url=canonical_url, allow_local_copy=False)
    )
    page_qr_svg = create_share_qr_svg(canonical_url)

    return render_template(
        "share.html",
        title=title,
        excerpt=excerpt,
        article_html=article_html,
        share_url=canonical_url,
        theme_name=THEMES[theme]["name"],
        created_at_label=format_share_timestamp(payload.get("created_at")),
        code_theme_name=CODE_THEMES[code_theme]["name"],
        site_name=SITE_NAME,
        canonical_url=canonical_url,
        page_qr_svg=page_qr_svg,
        published_at=published_at,
        og_image_url=og_image_url,
        structured_data=build_share_structured_data(
            title,
            excerpt or title,
            canonical_url,
            published_at,
            og_image_url
        )
    )


@app.route('/share/images/<path:filename>')
def share_image_file(filename):
    """输出分享页相关的本地图片资源。"""
    safe_name = os.path.basename(filename or "")
    if safe_name != filename or not safe_name:
        abort(404)

    for image_dir in iter_share_image_dirs():
        image_path = image_dir / safe_name
        if image_path.exists() and image_path.is_file():
            return send_from_directory(image_dir, safe_name, conditional=True)

    abort(404)


@app.route('/robots.txt')
def robots_txt():
    """站点 robots 配置。"""
    lines = [
        "User-agent: *",
        "Allow: /",
        f"Sitemap: {build_public_url('sitemap_xml')}"
    ]
    return app.response_class("\n".join(lines) + "\n", mimetype="text/plain")


@app.route('/sitemap.xml')
def sitemap_xml():
    """输出 sitemap.xml。"""
    entries = [{
        "loc": build_public_url("index"),
        "lastmod": ""
    }]
    entries.extend(iter_share_sitemap_entries())

    xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']

    for entry in entries:
        xml_lines.append("  <url>")
        xml_lines.append(f"    <loc>{html_lib.escape(entry['loc'])}</loc>")
        if entry.get("lastmod"):
            xml_lines.append(f"    <lastmod>{html_lib.escape(entry['lastmod'])}</lastmod>")
        xml_lines.append("  </url>")

    xml_lines.append("</urlset>")
    return app.response_class("\n".join(xml_lines) + "\n", mimetype="application/xml")


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


@app.route('/api/upload/image', methods=['POST'])
def api_upload_image():
    """上传图片并返回可公开访问的 Markdown 图片地址。"""
    try:
        upload = request.files.get("image")
        if upload is None:
            return jsonify({
                "success": False,
                "error": "请先选择图片文件"
            }), 400

        mime_type = (upload.mimetype or "").strip().lower()
        if mime_type not in UPLOAD_IMAGE_ALLOWED_MIME_TYPES:
            return jsonify({
                "success": False,
                "error": "仅支持 JPG、PNG、WebP、GIF 图片"
            }), 400

        image_bytes = upload.read()
        if not image_bytes:
            return jsonify({
                "success": False,
                "error": "上传图片为空"
            }), 400

        if len(image_bytes) > UPLOAD_IMAGE_MAX_BYTES:
            return jsonify({
                "success": False,
                "error": "图片不能超过 10MB"
            }), 400

        ensure_share_storage_dir()
        filename = save_uploaded_image_bytes(image_bytes, mime_type)
        image_url = build_public_url("share_image_file", filename=filename)
        alt_text = sanitize_markdown_image_alt(upload.filename)

        return jsonify({
            "success": True,
            "image_url": image_url,
            "markdown": f"![{alt_text}]({image_url})",
            "filename": filename,
            "alt": alt_text
        })
    except Exception as exc:
        return jsonify({
            "success": False,
            "error": str(exc)
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
        share_url = build_public_url("share_article", share_id=share_id)
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


@app.route('/api/wechat/draft', methods=['POST'])
def api_wechat_draft():
    """推送当前文章到公众号草稿箱。"""
    try:
        data = request.get_json() or {}
        md_text = data.get("markdown", "")
        if not md_text.strip():
            return jsonify({
                "success": False,
                "error": "请先输入文章内容"
            }), 400

        wechat_config = data.get("wechat_config") or {}
        app_key = (wechat_config.get("app_key") or "").strip()
        app_secret = (wechat_config.get("app_secret") or "").strip()
        if not app_key or not app_secret:
            return jsonify({
                "success": False,
                "error": "请填写公众号 AppKey 和 AppSecret"
            }), 400

        theme, code_theme, font_size, background = normalize_render_options(
            data.get("theme", "default"),
            data.get("code_theme", "github"),
            data.get("font_size", "medium"),
            data.get("background", "warm")
        )

        access_token = wechat_get_access_token(app_key, app_secret)
        article_payload = prepare_wechat_article_payload(
            md_text,
            theme,
            code_theme,
            font_size,
            background,
            access_token,
            meta=data.get("meta") or {}
        )

        response_data = wechat_api_request(
            f"{WECHAT_API_BASE}/draft/add?access_token={urllib.parse.quote(access_token)}",
            method="POST",
            payload={"articles": [article_payload["article"]]}
        )
        media_id = (response_data.get("media_id") or "").strip()
        if not media_id:
            raise RuntimeError("微信未返回草稿 media_id")

        return jsonify({
            "success": True,
            "title": article_payload["article"]["title"],
            "media_id": media_id,
            "uploaded_image_count": article_payload["uploaded_image_count"]
        })
    except RuntimeError as exc:
        return jsonify({
            "success": False,
            "error": str(exc)
        }), 400
    except Exception as exc:
        return jsonify({
            "success": False,
            "error": str(exc)
        }), 500


@app.route('/api/ai/title-suggestions', methods=['POST'])
def api_ai_title_suggestions():
    """AI 标题建议。"""
    try:
        data = get_ai_request_data()
        md_text = data.get('markdown', '')
        focus_prompt = data.get('focus_prompt', '')
        ai_config = data.get('ai_config') or {}
        if not md_text.strip():
            return jsonify({'success': False, 'error': '请先输入文章内容'}), 400

        suggestions = generate_ai_title_suggestions(md_text, focus_prompt=focus_prompt, ai_config=ai_config)
        if not suggestions:
            return jsonify({'success': False, 'error': '未生成可用标题'}), 500

        return jsonify({
            'success': True,
            'suggestions': suggestions
        })
    except AIConfigCryptoError as exc:
        return jsonify({
            'success': False,
            'error': str(exc)
        }), 400
    except Exception as e:
        app.logger.exception("Title suggestions failed")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/ai/summary', methods=['POST'])
def api_ai_summary():
    """AI 文章摘要。"""
    try:
        data = get_ai_request_data()
        md_text = data.get('markdown', '')
        focus_prompt = data.get('focus_prompt', '')
        ai_config = data.get('ai_config') or {}
        if not md_text.strip():
            return jsonify({'success': False, 'error': '请先输入文章内容'}), 400

        summary = generate_ai_summary(md_text, focus_prompt=focus_prompt, ai_config=ai_config)
        return jsonify({
            'success': True,
            'summary': summary
        })
    except AIConfigCryptoError as exc:
        return jsonify({
            'success': False,
            'error': str(exc)
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/ai/generate-image', methods=['POST'])
def api_ai_generate_image():
    """AI 文章配图。"""
    try:
        data = get_ai_request_data()
        md_text = data.get('markdown', '')
        focus_prompt = data.get('focus_prompt', '')
        ai_config = data.get('ai_config') or {}
        if not md_text.strip():
            return jsonify({'success': False, 'error': '请先输入文章内容'}), 400

        result = generate_ai_image(md_text, focus_prompt, ai_config=ai_config)
        return jsonify({
            'success': True,
            'image_url': result['image_url'],
            'revised_prompt': result.get('revised_prompt', '')
        })
    except AIConfigCryptoError as exc:
        return jsonify({
            'success': False,
            'error': str(exc)
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/ai/illustrate-article', methods=['POST'])
def api_ai_illustrate_article():
    """创建一键为文章核心段落配图的后台任务。"""
    try:
        data = get_ai_request_data()
        md_text = data.get('markdown', '')
        style_key = data.get('style', 'editorial')
        ai_config = data.get('ai_config') or {}
        app.logger.info(
            "Illustrate article API called style=%s markdown_preview=%s",
            style_key,
            summarize_log_text(md_text, limit=180)
        )
        if not md_text.strip():
            return jsonify({'success': False, 'error': '请先输入文章内容'}), 400
        if not has_ai_capability(ai_config, capability='text') or not has_ai_capability(ai_config, capability='image'):
            return jsonify({'success': False, 'error': '一键配图需要同时配置文本模型和图片模型'}), 400

        public_base_url = get_public_base_url()
        job = create_illustration_job(style_key, public_base_url=public_base_url)
        worker = threading.Thread(
            target=run_article_illustration_job,
            args=(job['job_id'], md_text, style_key, ai_config, public_base_url),
            daemon=True
        )
        worker.start()
        app.logger.info(
            "Illustrate article job created style=%s job_id=%s",
            style_key,
            job['job_id']
        )
        return jsonify({
            'success': True,
            'job_id': job['job_id'],
            'job': serialize_illustration_job(job)
        }), 202
    except AIConfigCryptoError as exc:
        return jsonify({
            'success': False,
            'error': str(exc)
        }), 400
    except Exception as e:
        app.logger.exception("Illustrate article failed")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/ai/illustrate-article/<job_id>', methods=['GET'])
def api_ai_illustrate_article_status(job_id):
    """查询一键配图后台任务状态。"""
    job = get_illustration_job(job_id)
    if not job:
        return jsonify({
            'success': False,
            'error': '任务不存在或已过期'
        }), 404

    return jsonify({
        'success': True,
        'job': serialize_illustration_job(job)
    })


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
                'model': os.getenv("OPENAI_IMAGE_TOOL_MODEL", "gemini-2.5-flash-image")
            }
        },
        'ai_illustration_styles': get_article_illustration_style_options()
    })


@app.route('/api/health', methods=['GET'])
def api_health():
    """健康检查接口"""
    return jsonify({
        'status': 'ok',
        'service': 'md2we',
        'version': '1.0.0'
    })


if __name__ == '__main__':
    app.run(debug=True, port=5566)
