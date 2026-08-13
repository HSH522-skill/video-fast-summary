import subprocess
import os
import sys
import argparse
import tempfile
import shutil
import json
import time
import re
from datetime import datetime

import requests

from openai import OpenAI
import dashscope
from dashscope.audio.asr import Transcription


# 多语言配置
SUPPORTED_LANGS = {
    "zh": "中文",
    "en": "英文",
    "ja": "日文",
    "ko": "韩文",
    "fr": "法文",
    "de": "德文",
    "es": "西班牙文",
    "pt": "葡萄牙文",
    "ru": "俄文",
    "ar": "阿拉伯文"
}

# 语言检测关键词
LANG_DETECT_KEYWORDS = {
    "zh": ["的", "是", "在", "了", "不", "和", "我们", "他们"],
    "en": ["the", "is", "and", "we", "they", "this", "that", "have"],
    "ja": ["の", "は", "が", "です", "ます", "を", "に", "で"],
    "ko": ["은", "는", "이", "가", "을", "를", "의", "에"],
}


def detect_language(text_sample):
    """自动检测文本语言"""
    scores = {lang: 0 for lang in LANG_DETECT_KEYWORDS}
    words = text_sample.lower().split()
    for lang, keywords in LANG_DETECT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in words or keyword in text_sample:
                scores[lang] += 1
    detected = max(scores, key=scores.get)
    return detected if scores[detected] > 0 else "zh"


def download_audio(url, output_path):
    """使用 yt-dlp 下载视频并提取音频（带自动重试）"""
    print(f"📥 正在下载视频: {url}")
    
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            cmd = [
                "yt-dlp",
                "-x",
                "--audio-format", "mp3",
                "-o", output_path,
                "--no-playlist",
                url
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                print(f"✅ 音频下载完成")
                return True
            else:
                print(f"⚠️ 下载失败 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    
        except subprocess.TimeoutExpired:
            print(f"⚠️ 下载超时 (尝试 {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2
        except Exception as e:
            print(f"⚠️ 下载异常: {str(e)[:50]}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2
    
    print("❌ 下载失败，可能的原因：")
    print("   1. 视频链接无效或已失效 → 请检查链接是否正确")
    print("   2. 视频为私密/付费内容 → 需要登录或购买后才能访问")
    print("   3. 网络不稳定 → 请检查网络连接后重试")
    print("   4. 平台限制 → 部分平台需要更新 yt-dlp: pip install -U yt-dlp")
    return False


def transcribe_audio_with_timestamps(audio_path, model_size="base", source_lang="auto"):
    """
    使用通义听悟 SDK 转写音频，带时间戳。
    注意：音频数据会上传至阿里云 DashScope 服务器进行转写处理。
    敏感场景请使用本地 Whisper 模式（自动 fallback）。
    """
    print(f"🎤 正在转写音频...")

    if not os.path.exists(audio_path):
        print(f"❌ 音频文件不存在")
        return None, None

    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("❌ 未配置 DASHSCOPE_API_KEY 环境变量")
        print("💡 请访问 https://dashscope.console.aliyun.com/ 申请免费 API Key")
        return None, None

    dashscope.api_key = api_key

    # 语言映射到听悟支持的语言代码
    asr_lang_map = {
        "zh": "zh",
        "en": "en",
        "ja": "ja",
        "ko": "ko",
        "auto": "auto"
    }
    asr_lang = asr_lang_map.get(source_lang, "zh") if source_lang != "auto" else "auto"

    try:
        print("📤 正在上传音频文件...")
        upload_url = "https://dashscope.aliyuncs.com/api/v1/uploads"
        headers = {"Authorization": f"Bearer {api_key}"}

        with open(audio_path, "rb") as f:
            files = {"file": ("audio.mp3", f, "audio/mpeg")}
            upload_response = requests.post(upload_url, headers=headers, files=files, timeout=120)

        if upload_response.status_code != 200:
            status_msg = f"状态码 {upload_response.status_code}"
            if upload_response.status_code == 401:
                print(f"⚠️ API Key 无效或已过期 ({status_msg})，切换本地 Whisper...")
                print("💡 请检查 DASHSCOPE_API_KEY 是否正确，或前往 dashscope.console.aliyun.com 重新生成")
            elif upload_response.status_code == 429:
                print(f"⚠️ API 额度已用完或请求过于频繁 ({status_msg})，切换本地 Whisper...")
                print("💡 请稍后重试或检查阿里云账户余额")
            else:
                print(f"⚠️ 文件上传失败 ({status_msg})，切换本地 Whisper...")
            return transcribe_audio_whisper(audio_path, model_size, source_lang), None

        upload_result = upload_response.json()
        file_url = upload_result.get("data", {}).get("url")
        if not file_url:
            print(f"⚠️ 未获取到文件URL，切换 Whisper...")
            return transcribe_audio_whisper(audio_path, model_size, source_lang), None

        print(f"✅ 文件上传成功")
        print("📤 正在提交转写任务...")

        call_kwargs = {
            "model": "paraformer-v1",
            "file_urls": [file_url],
            "enable_punctuation_prediction": True,
            "enable_inverse_text_normalization": True,
            "enable_timestamp": True
        }
        if asr_lang != "auto":
            call_kwargs["language"] = asr_lang

        result = Transcription.call(**call_kwargs)

        if result.status_code == 200:
            if result.output and result.output.get("task_status") == "SUCCEEDED":
                results = result.output.get("results", [])
                if results and len(results) > 0:
                    transcription_url = results[0].get("transcription_url")
                    if transcription_url:
                        resp = requests.get(transcription_url)
                        if resp.status_code == 200:
                            data = resp.json()
                            text = data.get("text", "")
                            timestamps = data.get("timestamps", [])
                            if text:
                                detected_lang = detect_language(text[:500])
                                print(f"✅ 转写完成 (检测语言: {SUPPORTED_LANGS.get(detected_lang, detected_lang)})，共 {len(text)} 字符")
                                return text, timestamps

    except Exception as e:
        print(f"⚠️ 转写异常，切换 Whisper...")

    return transcribe_audio_whisper(audio_path, model_size, source_lang), None


def transcribe_audio_whisper(audio_path, model_size="base", source_lang="auto"):
    """使用 Whisper 转写（无时间戳）"""
    print(f"🎤 正在使用 Whisper 转写 (模型: {model_size})...")

    # 语言映射
    whisper_lang_map = {
        "zh": "Chinese",
        "en": "English",
        "ja": "Japanese",
        "ko": "Korean",
        "fr": "French",
        "de": "German",
        "es": "Spanish",
        "auto": None
    }
    whisper_lang = whisper_lang_map.get(source_lang)

    cmd = [
        "whisper",
        audio_path,
        "--model", model_size,
        "--output_format", "txt",
        "--output_dir", os.path.dirname(audio_path)
    ]
    if whisper_lang:
        cmd.extend(["--language", whisper_lang])

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"❌ Whisper 转写失败")
        return None

    txt_path = audio_path.rsplit(".", 1)[0] + ".txt"
    if os.path.exists(txt_path):
        with open(txt_path, "r", encoding="utf-8") as f:
            text = f.read()
        detected_lang = detect_language(text[:500])
        print(f"✅ Whisper 转写完成 (检测语言: {SUPPORTED_LANGS.get(detected_lang, detected_lang)})，共 {len(text)} 字符")
        return text
    else:
        print(f"❌ 找不到转写结果文件")
        return None


def format_timestamp(seconds):
    """将秒数格式化为 MM:SS"""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"


def get_client():
    """获取 OpenAI 客户端"""
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        return None
    return OpenAI(
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )


def check_output_truncated(result, options, full_text):
    """检查分析结果是否可能被截断"""
    if not result:
        return True
    
    summary = result.get("summary", "")
    quotes = result.get("quotes", [])
    text_len = len(full_text)
    
    # 摘要过短（<50字）且原始文本很长（>2000字），大概率截断
    if len(summary) < 50 and text_len > 2000:
        return True
    
    # 请求了金句但没提取到，且文本够长
    if options.get("quotes") and (not quotes or len(quotes) == 0) and text_len > 1000:
        return True
    
    # 摘要明显偏短（不到文本长度的1%）
    if len(summary) < text_len * 0.005 and text_len > 1000:
        return True
    
    return False


def generate_full_analysis(text, timestamps=None, lang="zh", options=None):
    """调用通义千问 API 生成完整分析"""
    client = get_client()
    if not client:
        print("❌ 无法创建 API 客户端，请检查 DASHSCOPE_API_KEY")
        return None

    text_truncated = text[:8000] if len(text) > 8000 else text
    target_lang = SUPPORTED_LANGS.get(lang, "中文")

    # 构建任务列表
    tasks = []
    tasks.append(f"""
1. 生成基础摘要，JSON格式：
{{"title": "一句话标题(15字内)", "summary": "200字摘要", "key_points": ["要点1", "要点2", "要点3", "要点4", "要点5"]}}
""")

    if options.get("quotes"):
        tasks.append("""
2. 提取3-5条金句（视频中最精彩、最有价值的原话），JSON格式：
{"quotes": [{"text": "金句内容", "time": "出现时间如02:15"}]}
""")

    if options.get("mindmap"):
        tasks.append("""
3. 生成思维导图（Markdown格式），结构清晰，层级分明，用 # 和 - 表示层级
""")

    if options.get("score"):
        tasks.append("""
4. 内容评分（1-5星），JSON格式：
{"scores": {"信息密度": 4, "逻辑清晰": 4, "实用价值": 5, "表达流畅": 4, "创新性": 3}}
""")

    if options.get("translate_to") and options["translate_to"] != lang:
        translate_target = SUPPORTED_LANGS.get(options["translate_to"], "中文")
        tasks.append(f"""
5. 将上述所有内容翻译为{translate_target}，JSON格式：
{{"title": "...", "summary": "...", "key_points": ["...", "..."]}}
""")

    prompt = f"""请分析以下视频转写的文字内容，用 {target_lang} 输出。

转写文本：
{text_truncated}

请完成以下任务：
{"".join(tasks)}

每个任务的结果之间用 "---" 分隔。"""

    try:
        completion = client.chat.completions.create(
            model="qwen-plus",
            messages=[
                {"role": "system", "content": f"你是专业的视频内容分析专家，精通{target_lang}。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        result_text = completion.choices[0].message.content
        return parse_analysis_result(result_text, options)
    except Exception as e:
        print(f"⚠️ API 调用失败: {str(e)[:100]}")
        return None


def generate_competitor_analysis(video_results, lang="zh"):
    """生成竞品对比分析报告"""
    client = get_client()
    if not client:
        print("❌ 无法创建 API 客户端")
        return None

    target_lang = SUPPORTED_LANGS.get(lang, "中文")

    # 构建各视频摘要信息
    video_summaries = []
    for i, vr in enumerate(video_results, 1):
        info = f"视频{i} ({vr.get('url', '未知来源')}):\n"
        info += f"标题: {vr.get('title', '无')}\n"
        info += f"摘要: {vr.get('summary', '无')}\n"
        info += f"核心要点: {', '.join(vr.get('key_points', []))}\n"
        if vr.get('quotes'):
            info += f"金句: {'; '.join([q.get('text', '') for q in vr['quotes']])}\n"
        if vr.get('scores'):
            info += f"评分: {json.dumps(vr['scores'], ensure_ascii=False)}\n"
        video_summaries.append(info)

    combined_info = "\n\n".join(video_summaries)

    prompt = f"""你是一位资深的行业分析师。请对以下多个视频内容进行深度竞品对比分析，用{target_lang}输出。

{combined_info}

请生成一份专业的竞品分析报告，包含以下部分：

## 一、各视频核心观点对比
用表格形式对比各视频的主要观点、切入角度和核心主张。

## 二、差异化分析
分析各视频之间的差异化特点，包括：
- 内容侧重点差异
- 观点立场差异
- 论证方式差异
- 受众定位差异

## 三、共识与分歧
- 各视频的共同观点（共识）
- 各视频的分歧点及各自理由

## 四、优劣势评估
对各视频的内容质量、论证深度、实用价值进行评估排名。

## 五、综合洞察与建议
基于以上分析，给出综合洞察和可操作建议。

请确保分析客观、有深度，用 Markdown 格式输出。"""

    try:
        completion = client.chat.completions.create(
            model="qwen-plus",
            messages=[
                {"role": "system", "content": f"你是资深的行业分析师和内容策略专家，用{target_lang}输出专业分析报告。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"⚠️ 竞品分析生成失败: {str(e)[:100]}")
        return None


def generate_chapters(text, timestamps=None, lang="zh"):
    """AI 章节分段：将长视频转写文本拆分为 3-5 个章节"""
    client = get_client()
    if not client:
        return None

    target_lang = SUPPORTED_LANGS.get(lang, "中文")
    text_truncated = text[:12000] if len(text) > 12000 else text

    prompt = f"""你是专业的视频内容分析师。请将以下视频转写文本按主题拆分为 3-5 个章节，用{target_lang}输出。

转写文本：
{text_truncated}

请输出 JSON 格式：
{{
  "chapters": [
    {{
      "title": "章节标题（10字内）",
      "start_time": "起始时间如 00:00",
      "summary": "本章节 50 字摘要",
      "key_moment": "本章最精彩的一句话"
    }}
  ]
}}

规则：
- 按内容主题自然分段，不要机械按时间切
- 每个章节有明显主题区分
- 章节标题要吸引人
- 时间戳尽量准确"""

    try:
        completion = client.chat.completions.create(
            model="qwen-plus",
            messages=[
                {"role": "system", "content": f"你是专业的视频内容分析师，用{target_lang}输出。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        text = completion.choices[0].message.content
        json_blocks = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
        for jb in json_blocks:
            try:
                data = json.loads(jb)
                if "chapters" in data:
                    return data["chapters"]
            except (json.JSONDecodeError, ValueError):
                pass
        return None
    except Exception as e:
        print(f"⚠️ 章节分段失败: {str(e)[:100]}")
        return None


def generate_social_copy(result, platform="auto", lang="zh"):
    """生成社交媒体文案（小红书/朋友圈/微博）"""
    client = get_client()
    if not client:
        return None

    target_lang = SUPPORTED_LANGS.get(lang, "中文")
    title = result.get("title", "精彩视频")
    summary = result.get("summary", "")
    key_points = result.get("key_points", [])
    quotes = result.get("quotes", [])

    platform_hints = {
        "xiaohongshu": "小红书风格：用 emoji 分隔，加话题标签，口语化，像朋友分享，控制在 300 字以内",
        "pengyouquan": "朋友圈风格：简洁真诚，1-2 句话点出最打动人的地方，加一个 emoji",
        "weibo": "微博风格：可以直接一点，加话题标签，140 字左右",
        "auto": "根据内容自动选择最合适的风格"
    }
    style_hint = platform_hints.get(platform, platform_hints["auto"])

    prompt = f"""你是社交媒体内容专家。请根据以下视频摘要，生成一段{style_hint}的分享文案，用{target_lang}。

视频标题：{title}
视频摘要：{summary}
核心要点：{', '.join(key_points[:5])}
金句：{'; '.join([q.get('text', '') for q in quotes[:3]]) if quotes else '无'}

请输出 JSON：
{{
  "platform": "推荐平台",
  "copy": "文案正文",
  "hashtags": ["标签1", "标签2", "标签3"],
  "title": "吸引人的标题（15字内）"
}}"""

    try:
        completion = client.chat.completions.create(
            model="qwen-plus",
            messages=[
                {"role": "system", "content": "你是社交媒体运营专家，擅长写爆款文案。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        text = completion.choices[0].message.content
        json_blocks = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
        for jb in json_blocks:
            try:
                data = json.loads(jb)
                if "copy" in data:
                    return data
            except (json.JSONDecodeError, ValueError):
                pass
        return None
    except Exception as e:
        print(f"⚠️ 社交文案生成失败: {str(e)[:100]}")
        return None


def parse_analysis_result(text, options):
    """解析 AI 返回的分析结果"""
    result = {}
    sections = text.split("---")
    
    for section in sections:
        section = section.strip()
        if not section:
            continue
        
        # 查找所有 JSON 块（支持嵌套）
        json_blocks = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', section, re.DOTALL)
        for json_str in json_blocks:
            try:
                data = json.loads(json_str)
                if "title" in data and "summary" in data:
                    result["title"] = data.get("title", "")
                    result["summary"] = data.get("summary", "")
                    result["key_points"] = data.get("key_points", [])
                if "quotes" in data:
                    result["quotes"] = data.get("quotes", [])
                if "scores" in data:
                    result["scores"] = data.get("scores", {})
            except (json.JSONDecodeError, ValueError):
                pass

    # 提取思维导图
    if options.get("mindmap"):
        mindmap_match = re.search(r'(#\s+.+(?:\n(?:[-*]|\s+|#).+)*)', text, re.DOTALL)
        if mindmap_match:
            result["mindmap"] = mindmap_match.group(1).strip()

    # 提取章节
    if options.get("chapters"):
        for json_str in re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL):
            try:
                data = json.loads(json_str)
                if "chapters" in data:
                    result["chapters"] = data["chapters"]
                    break
            except (json.JSONDecodeError, ValueError):
                pass

    return result


# 字体缓存目录
_FONT_CACHE_DIR = os.path.join(tempfile.gettempdir(), "video_summarizer_fonts")


def _download_fallback_font():
    """下载开源中文字体作为 fallback，避免分享卡片显示方块"""
    os.makedirs(_FONT_CACHE_DIR, exist_ok=True)
    cached = os.path.join(_FONT_CACHE_DIR, "NotoSansSC-Regular.ttf")
    if os.path.exists(cached):
        return cached

    # 多个备用下载源，按优先级尝试
    font_urls = [
        "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansSC-Regular.otf",
        "https://cdn.jsdelivr.net/gh/notofonts/noto-cjk@main/Sans/OTF/SimplifiedChinese/NotoSansSC-Regular.otf",
        "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/SimplifiedChinese/NotoSansSC-Regular.otf",
    ]
    for url in font_urls:
        try:
            print(f"  🔤 正在下载中文字体（约 8MB）...")
            resp = requests.get(url, timeout=60, stream=True)
            if resp.status_code == 200:
                with open(cached, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                # 验证文件完整性
                if os.path.getsize(cached) > 100000:
                    print(f"  ✅ 字体已缓存到 {cached}")
                    return cached
                else:
                    os.remove(cached)
        except Exception:
            continue
    return None


def _find_cjk_font(size=20):
    """智能查找系统中支持中文的字体，找不到时自动下载"""
    from PIL import ImageFont

    cjk_fonts = [
        # Linux
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
        # macOS
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        # Windows
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
    ]

    # 1. 查找系统字体
    for font_path in cjk_fonts:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                continue

    # 2. 尝试下载 fallback 字体
    fallback = _download_fallback_font()
    if fallback:
        try:
            return ImageFont.truetype(fallback, size)
        except Exception:
            pass

    # 3. 最后退路：DejaVu（不支持中文但不会崩溃）
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
    except Exception:
        return ImageFont.load_default()


def generate_share_card(result, options, output_path=None):
    """生成精美摘要分享卡片图片"""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("⚠️ 未安装 Pillow，跳过分享卡片生成")
        print("💡 请执行: pip install Pillow")
        return None

    # 卡片尺寸
    width, height = 800, 1000
    bg_color = (25, 25, 45)  # 深色背景
    accent_color = (100, 140, 255)  # 蓝紫强调色
    text_color = (255, 255, 255)
    subtitle_color = (180, 190, 210)

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # 智能加载中文字体
    font_title = _find_cjk_font(32)
    font_body = _find_cjk_font(20)
    font_small = _find_cjk_font(16)
    font_emoji = _find_cjk_font(24)

    y = 40

    # 顶部装饰线
    draw.rectangle([40, y, width - 40, y + 4], fill=accent_color)
    y += 30

    # 标题区域
    title = result.get("title", "视频摘要")[:20]
    draw.text((40, y), f"📺 {title}", fill=text_color, font=font_title)
    y += 55

    # 分隔线
    draw.line([40, y, width - 40, y], fill=(60, 60, 80), width=1)
    y += 25

    # 摘要区域
    draw.text((40, y), "📝 核心摘要", fill=accent_color, font=font_body)
    y += 35

    summary = result.get("summary", "")
    if summary:
        # 逐行绘制摘要，支持中文
        lines = _wrap_text(summary, width - 80, font_body, draw)
        for line in lines[:8]:
            draw.text((40, y), line, fill=text_color, font=font_body)
            y += 28
    y += 20

    # 核心要点
    key_points = result.get("key_points", [])
    if key_points:
        draw.line([40, y, width - 40, y], fill=(60, 60, 80), width=1)
        y += 20
        draw.text((40, y), "🎯 核心要点", fill=accent_color, font=font_body)
        y += 35

        for i, point in enumerate(key_points[:5], 1):
            point_text = f"{i}. {point[:40]}"
            draw.text((40, y), point_text, fill=text_color, font=font_body)
            y += 28

    # 金句
    if options.get("quotes") and result.get("quotes"):
        draw.line([40, y, width - 40, y], fill=(60, 60, 80), width=1)
        y += 20
        draw.text((40, y), "💬 金句", fill=accent_color, font=font_body)
        y += 35

        for quote in result["quotes"][:3]:
            q_text = f"「{quote.get('text', '')[:35]}」"
            draw.text((40, y), q_text, fill=subtitle_color, font=font_small)
            y += 24

    # 评分
    if options.get("score") and result.get("scores"):
        draw.line([40, y, width - 40, y], fill=(60, 60, 80), width=1)
        y += 20
        draw.text((40, y), "⭐ 综合评分", fill=accent_color, font=font_body)
        y += 35

        x = 40
        for dim, score in list(result["scores"].items())[:4]:
            try:
                s = int(score)
            except (ValueError, TypeError):
                s = 0
            stars = "★" * s + "☆" * (5 - s)
            draw.text((x, y), f"{dim}: {stars}", fill=text_color, font=font_small)
            y += 24

    # 底部标识
    draw.line([40, height - 60, width - 40, height - 60], fill=accent_color, width=2)
    draw.text((40, height - 45), "视频极速摘要 Pro · 由 AI 生成", fill=subtitle_color, font=font_small)

    # 保存
    if not output_path:
        output_path = f"video_summary_share_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

    img.save(output_path, "PNG")
    print(f"\n🖼️ 分享卡片已生成: {output_path}")
    return output_path


def _wrap_text(text, max_width, font, draw):
    """中文友好的文本换行"""
    lines = []
    current_line = ""
    for char in text:
        test_line = current_line + char
        try:
            bbox = draw.textbbox((0, 0), test_line, font=font)
            w = bbox[2] - bbox[0]
        except Exception:
            w = len(test_line) * 10
        if w > max_width:
            lines.append(current_line)
            current_line = char
        else:
            current_line = test_line
    if current_line:
        lines.append(current_line)
    return lines


def display_results(result, options):
    """展示分析结果"""
    print("\n" + "=" * 50)
    
    if options.get("full_analysis"):
        print("📌 视频深度分析")
    else:
        print("📌 视频摘要结果")
    
    print("=" * 50)
    
    if result.get("title"):
        print(f"\n【标题】\n{result['title']}")
    
    if result.get("summary"):
        print(f"\n【摘要】\n{result['summary']}")
    
    if result.get("key_points"):
        print(f"\n【核心要点】")
        for i, point in enumerate(result["key_points"], 1):
            print(f"  {i}. {point}")
    
    if options.get("quotes") and result.get("quotes"):
        print(f"\n【金句摘录】")
        for quote in result["quotes"]:
            time_str = f" [{quote.get('time', '')}]" if quote.get("time") else ""
            print(f"  💬 \"{quote.get('text', '')}\"{time_str}")
    
    if options.get("score") and result.get("scores"):
        print(f"\n【内容评分】")
        for dimension, score in result["scores"].items():
            try:
                s = int(score)
                stars = "⭐" * s + "☆" * (5 - s)
            except (ValueError, TypeError):
                stars = str(score)
            print(f"  📊 {dimension}: {stars}")
    
    if options.get("mindmap") and result.get("mindmap"):
        print(f"\n【思维导图】")
        print(result["mindmap"])
    
    if options.get("chapters") and result.get("chapters"):
        print(f"\n【📑 章节分段】")
        for i, ch in enumerate(result["chapters"], 1):
            ts = f" [{ch.get('start_time', '')}]" if ch.get("start_time") else ""
            print(f"  {i}. {ch.get('title', '无标题')}{ts}")
            print(f"     {ch.get('summary', '')}")
            if ch.get("key_moment"):
                print(f"     💬 {ch['key_moment']}")
    
    print("\n" + "=" * 50)


def process_single_video(args, url=None, file_path=None):
    """处理单个视频，返回分析结果"""
    temp_dir = tempfile.mkdtemp()
    audio_path = os.path.join(temp_dir, "audio.mp3")
    result = None

    try:
        target_url = url or args.url
        target_file = file_path or args.file

        # 下载/提取音频
        if target_url:
            success = download_audio(target_url, audio_path)
            if not success:
                return None
        elif target_file:
            print(f"📁 正在提取本地视频音频...")
            cmd = [
                "ffmpeg",
                "-i", target_file,
                "-vn",
                "-acodec", "libmp3lame",
                "-y",
                audio_path
            ]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                print(f"❌ 音频提取失败")
                return None
            print(f"✅ 音频提取完成")
        else:
            return None

        # 转写
        text, timestamps = transcribe_audio_with_timestamps(audio_path, args.model, args.source_lang)
        if not text:
            return None

        # 生成分析
        print("\n🤖 正在生成 AI 分析...")
        
        options = {
            "quotes": args.quotes or args.full_analysis,
            "mindmap": args.mindmap or args.full_analysis,
            "timestamps": args.timestamps or args.full_analysis,
            "score": args.score or args.full_analysis,
            "full_analysis": args.full_analysis,
            "chapters": args.chapters or args.full_analysis,
            "share": args.share,
            "export_subtitles": args.export_subtitles,
            "social": args.social,
            "translate_to": args.translate if hasattr(args, 'translate') and args.translate else None
        }
        
        result = generate_full_analysis(text, timestamps, args.lang, options)
        
        # 输出完整性自检：检查结果是否可能被截断
        if result and check_output_truncated(result, options, text):
            print("\n⚠️ 结果看起来不完整，正在自动重试…")
            time.sleep(2)
            result = generate_full_analysis(text, timestamps, args.lang, options)
            if result and check_output_truncated(result, options, text):
                print("💡 视频较长，部分内容可能未完整覆盖，建议用章节分段模式重新处理")
        
        if result:
            result["url"] = target_url or target_file
            display_results(result, options)
            
            # 章节分段（独立于摘要分析，单独调用）
            if options.get("chapters"):
                print("\n📑 正在生成章节分段...")
                chapters = generate_chapters(text, timestamps, args.lang)
                if chapters:
                    result["chapters"] = chapters
                    print(f"✅ 共 {len(chapters)} 个章节：")
                    for i, ch in enumerate(chapters, 1):
                        ts = f" [{ch.get('start_time', '')}]" if ch.get("start_time") else ""
                        print(f"  {i}. {ch.get('title', '')}{ts}")
            
            # 社交文案生成
            if options.get("social"):
                platform = args.social if args.social != True else "auto"
                print(f"\n📱 正在生成社交文案...")
                social = generate_social_copy(result, platform, args.lang)
                if social:
                    print(f"\n{'='*50}")
                    print(f"📱 {social.get('platform', '社交')}分享文案")
                    print(f"{'='*50}")
                    print(f"【标题】{social.get('title', '')}")
                    print(f"【正文】\n{social.get('copy', '')}")
                    if social.get("hashtags"):
                        print(f"【标签】{' '.join(['#' + t for t in social['hashtags']])}")
                    print(f"{'='*50}")
                    result["social"] = social
            
            # 生成分享卡片
            if options.get("share"):
                share_path = args.output.replace(".md", ".png") if args.output else None
                generate_share_card(result, options, share_path)
            
            # 导出字幕
            if options.get("export_subtitles"):
                sub_path = args.output.replace(".md", "_subtitles.txt") if args.output else f"subtitles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                try:
                    with open(sub_path, "w", encoding="utf-8") as sf:
                        sf.write(text)
                    print(f"📄 字幕已导出: {sub_path}")
                except Exception as e:
                    print(f"⚠️ 字幕导出失败: {e}")
            
            if args.output:
                save_results(result, args.output, options)
        
        return result

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def run_competitor_analysis(args):
    """运行竞品分析模式：批量处理多个视频并生成对比报告"""
    urls = [url.strip() for url in args.compare.split(",")]
    
    if len(urls) < 2:
        print("❌ 竞品分析至少需要 2 个视频链接")
        sys.exit(1)
    
    print(f"🔍 竞品分析模式：共 {len(urls)} 个视频")
    print("=" * 50)
    
    video_results = []
    
    for i, url in enumerate(urls, 1):
        print(f"\n{'='*50}")
        print(f"📹 处理竞品视频 [{i}/{len(urls)}]: {url}")
        print(f"{'='*50}")
        
        result = process_single_video(args, url=url)
        if result:
            video_results.append(result)
            print(f"✅ 视频 {i} 分析完成")
        else:
            print(f"⚠️ 视频 {i} 分析失败，跳过")
    
    if len(video_results) < 2:
        print("\n❌ 至少需要成功分析 2 个视频才能进行竞品对比")
        return
    
    # 生成竞品对比分析报告
    print(f"\n📊 正在生成竞品对比分析报告...")
    report = generate_competitor_analysis(video_results, args.lang)
    
    if report:
        print("\n" + "=" * 50)
        print("📊 竞品对比分析报告")
        print("=" * 50)
        print(report)
        print("=" * 50)
        
        # 保存报告
        output_path = args.output or f"competitor_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(f"# 竞品对比分析报告\n")
                f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(f"分析视频数量: {len(video_results)}\n\n")
                f.write("## 视频列表\n")
                for i, vr in enumerate(video_results, 1):
                    f.write(f"{i}. {vr.get('url', '未知')}\n")
                    f.write(f"   - 标题: {vr.get('title', '无')}\n")
                f.write("\n---\n\n")
                f.write(report)
            print(f"\n✅ 竞品分析报告已保存到: {output_path}")
        except Exception as e:
            print(f"⚠️ 保存报告失败: {e}")
    
    return video_results, report


def save_results(result, output_path, options):
    """保存结果到文件"""
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            if result.get("title"):
                f.write(f"# {result['title']}\n\n")
            if result.get("summary"):
                f.write(f"## 摘要\n{result['summary']}\n\n")
            if result.get("key_points"):
                f.write(f"## 核心要点\n")
                for i, point in enumerate(result["key_points"], 1):
                    f.write(f"{i}. {point}\n")
                f.write("\n")
            if options.get("quotes") and result.get("quotes"):
                f.write(f"## 金句摘录\n")
                for quote in result["quotes"]:
                    f.write(f"- \"{quote.get('text', '')}\"\n")
                f.write("\n")
            if options.get("mindmap") and result.get("mindmap"):
                f.write(f"## 思维导图\n{result['mindmap']}\n\n")
            if options.get("score") and result.get("scores"):
                f.write(f"## 内容评分\n")
                for dim, score in result["scores"].items():
                    f.write(f"- {dim}: {score}/5\n")
        print(f"\n✅ 结果已保存到: {output_path}")
    except Exception as e:
        print(f"⚠️ 保存文件失败: {e}")


def auto_install_dependencies():
    """自动检测并安装缺失的 Python 依赖，安装失败时给出清晰指引"""
    required_packages = {
        "yt_dlp": "yt-dlp",
        "openai": "openai",
        "requests": "requests",
        "dashscope": "dashscope",
        "PIL": "Pillow",
    }
    # whisper 单独处理：依赖 PyTorch ~2GB，安装慢且容易失败
    heavy_packages = {
        "whisper": "openai-whisper",
    }
    
    missing = []
    for module, package in required_packages.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)
    
    # 检查 whisper（可选，不是所有场景都需要）
    whisper_missing = False
    for module, package in heavy_packages.items():
        try:
            __import__(module)
        except ImportError:
            whisper_missing = True
    
    if not missing and not whisper_missing:
        return True
    
    if missing:
        print(f"🔧 检测到缺少依赖: {', '.join(missing)}")
    if whisper_missing:
        print(f"🔧 检测到缺少 openai-whisper（备用转写引擎，可选）")
    
    print("📦 正在自动安装...")
    
    # 拼接安装命令，一次 pip 调用装多个轻量包，效率更高
    failed = []
    
    if missing:
        for package in missing:
            success = _pip_install(package, timeout=120)
            if not success:
                failed.append(package)
    
    if whisper_missing:
        # whisper 依赖 PyTorch ~2GB，分两步安装更稳定
        print(f"  ⏳ 安装 openai-whisper（依赖 PyTorch，约 2GB，可能需要 5-10 分钟）...")
        # 先尝试装 PyTorch CPU 版（体积更小，不依赖 CUDA）
        torch_ok = _pip_install("torch", timeout=600)
        if not torch_ok:
            print(f"  🔄 PyTorch 直接安装失败，尝试预装 numpy...")
            _pip_install("numpy", timeout=120)
        # 再装 whisper，禁用缓存加速
        success = _pip_install("openai-whisper", timeout=600)
        if not success:
            print(f"  💡 openai-whisper 安装失败不影响核心功能，通义听悟仍是首选转写引擎")
            print(f"     如需本地转写，请手动执行: pip install torch && pip install openai-whisper")
    
    if failed:
        print(f"\n💡 以下包自动安装失败，请手动安装:")
        print(f"   pip install {' '.join(failed)}")
        return False
    
    print("✅ 核心依赖已就绪\n")
    return True


def _pip_install(package, timeout=120):
    """安装单个 pip 包，带重试和权限处理"""
    base_cmd = [sys.executable, "-m", "pip", "install", package, "--user"]
    
    for attempt in range(2):
        try:
            result = subprocess.run(
                base_cmd,
                capture_output=True, text=True, timeout=timeout
            )
            if result.returncode == 0:
                print(f"  ✅ {package} 安装成功")
                return True
            
            # 权限错误：试试不用 --user
            if "permission" in result.stderr.lower() and "--user" in base_cmd:
                base_cmd.remove("--user")
                continue
            
            # 网络错误：重试
            if attempt == 0 and ("Connection" in result.stderr or "timeout" in result.stderr.lower()):
                print(f"  🔄 网络波动，重试 {package}...")
                time.sleep(2)
                continue
            
            # 其他错误
            err_tail = result.stderr.strip().split("\n")[-1] if result.stderr.strip() else "未知错误"
            print(f"  ⚠️ {package} 安装失败: {err_tail[:100]}")
            return False
            
        except subprocess.TimeoutExpired:
            if attempt == 0:
                print(f"  🔄 {package} 安装超时，重试...")
                continue
            print(f"  ⚠️ {package} 安装超时（>{timeout}秒）")
            return False
        except Exception as e:
            print(f"  ⚠️ {package} 安装异常: {str(e)[:80]}")
            return False
    
    return False


def check_ffmpeg(fatal=True):
    """检查 FFmpeg 是否可用，给出友好提示"""
    if shutil.which("ffmpeg"):
        print("✅ ffmpeg 已就绪")
        return True
    
    print("⚠️ 电脑上还没装 FFmpeg（视频处理工具）")
    print("💡 装一下就行，很简单：")
    print("   Windows: 去 ffmpeg.org 下载，解压后把 bin 目录加入 PATH")
    print("   Mac:     brew install ffmpeg")
    print("   Linux:   sudo apt install ffmpeg")
    
    if fatal:
        print("❌ 请安装 FFmpeg 后重试，或直接在 SkillHub 对话中使用（无需配置）")
        return False
    return True


def main():
    # 环境检查
    print("🔍 正在检查运行环境...")
    
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("⚠️ 还没配置 API Key")
        print("💡 去阿里云 DashScope 免费领一个：https://dashscope.console.aliyun.com/")
        print("   新用户免费，注册后在「API Key 管理」创建 Key，然后执行：")
        print("   export DASHSCOPE_API_KEY=sk-你的key")
        print("")
    
    # 自动安装缺失的 Python 依赖
    if not auto_install_dependencies():
        print("⚠️ 部分依赖安装失败，功能可能受限\n")
    
    # 检查 FFmpeg（非对话模式下必须）
    if not check_ffmpeg(fatal=True):
        sys.exit(1)
    
    print("✅ 环境检查通过\n")
    
    # 参数解析
    parser = argparse.ArgumentParser(description="视频极速摘要 Pro v3.0 - 多语言+竞品分析")
    parser.add_argument("--url", help="视频链接")
    parser.add_argument("--file", help="本地视频文件路径")
    parser.add_argument("--mode", default="summary", choices=["summary", "full"], help="输出模式")
    parser.add_argument("--model", default="base", choices=["tiny", "base", "small", "medium", "large"], help="Whisper模型")
    parser.add_argument("--output", help="输出文件路径")
    parser.add_argument("--lang", default="zh", choices=list(SUPPORTED_LANGS.keys()), help="摘要输出语言")
    parser.add_argument("--source-lang", default="auto", choices=list(SUPPORTED_LANGS.keys()) + ["auto"], help="视频原始语言（默认自动检测）")
    parser.add_argument("--translate", help="翻译摘要到指定语言（代码如 en/ja/ko）")
    parser.add_argument("--batch", help="批量处理，多个URL用逗号分隔")
    
    # 特色功能参数
    parser.add_argument("--quotes", action="store_true", help="提取金句")
    parser.add_argument("--mindmap", action="store_true", help="生成思维导图")
    parser.add_argument("--timestamps", action="store_true", help="显示时间戳")
    parser.add_argument("--score", action="store_true", help="内容评分")
    parser.add_argument("--full-analysis", action="store_true", help="完整分析（包含所有功能）")
    parser.add_argument("--share", action="store_true", help="生成精美分享卡片图片")
    parser.add_argument("--export-subtitles", action="store_true", help="导出纯字幕文本")
    parser.add_argument("--chapters", action="store_true", help="AI章节分段（长视频自动拆分3-5章）")
    parser.add_argument("--social", nargs="?", const="auto", help="生成社交分享文案（可选: xiaohongshu/pengyouquan/weibo）")
    
    # 竞品分析模式
    parser.add_argument("--compare", help="竞品分析模式，多个视频URL用逗号分隔（至少2个）")

    args = parser.parse_args()

    # 竞品分析模式
    if args.compare:
        run_competitor_analysis(args)
        return

    # 批量处理
    if args.batch:
        urls = [url.strip() for url in args.batch.split(",")]
        print(f"📦 批量处理模式：共 {len(urls)} 个视频\n")
        for i, url in enumerate(urls, 1):
            print(f"\n{'='*50}")
            print(f"📹 正在处理第 {i}/{len(urls)} 个视频")
            print(f"{'='*50}")
            process_single_video(args, url=url)
        print(f"\n✅ 批量处理完成！共处理 {len(urls)} 个视频")
        return

    if not args.url and not args.file:
        print("❌ 请提供 --url、--file、--batch 或 --compare 参数")
        print("💡 使用 --help 查看帮助")
        sys.exit(1)

    process_single_video(args)


if __name__ == "__main__":
    main()
