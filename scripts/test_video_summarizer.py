#!/usr/bin/env python3
"""video_summarizer 测试套件

覆盖核心模块：字体查找、文本换行、参数解析、多语言、FFmpeg 检查
运行方式：python scripts/test_video_summarizer.py
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from io import StringIO

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import video_summarizer as vs


class TestSupportedLanguages(unittest.TestCase):
    """多语言配置测试"""

    def test_supported_langs_complete(self):
        """多语言配置包含所有必需语种"""
        self.assertIn("zh", vs.SUPPORTED_LANGS)
        self.assertIn("en", vs.SUPPORTED_LANGS)
        self.assertIn("ja", vs.SUPPORTED_LANGS)
        self.assertIn("ko", vs.SUPPORTED_LANGS)
        self.assertEqual(vs.SUPPORTED_LANGS["zh"], "中文")
        self.assertEqual(vs.SUPPORTED_LANGS["en"], "英文")

    def test_all_langs_have_display_name(self):
        """所有语言都有对应的显示名称"""
        for code, name in vs.SUPPORTED_LANGS.items():
            self.assertIsInstance(code, str)
            self.assertIsInstance(name, str)
            self.assertGreater(len(name), 0)


class TestFontDiscovery(unittest.TestCase):
    """字体查找逻辑测试"""

    def test_find_cjk_font_returns_font(self):
        """字体查找应返回一个字体对象"""
        font = vs._find_cjk_font(size=20)
        self.assertIsNotNone(font, "应返回字体对象（可为系统字体或 fallback）")

    def test_find_cjk_font_different_sizes(self):
        """不同尺寸字体查找均正常"""
        for size in [12, 16, 20, 32, 48]:
            font = vs._find_cjk_font(size=size)
            self.assertIsNotNone(font, f"size={size} 应返回字体")

    def test_font_cache_dir(self):
        """字体缓存路径存在"""
        self.assertIn("video_summarizer_fonts", vs._FONT_CACHE_DIR)


class TestTextWrapping(unittest.TestCase):
    """文本换行测试"""

    def setUp(self):
        from PIL import Image, ImageDraw, ImageFont
        self.img = Image.new("RGB", (800, 100), (255, 255, 255))
        self.draw = ImageDraw.Draw(self.img)
        self.font = vs._find_cjk_font(16)

    def test_empty_text(self):
        """空文本返回空列表"""
        result = vs._wrap_text("", 100, self.font, self.draw)
        self.assertEqual(result, [])

    def test_short_text_no_wrap(self):
        """短文本不换行"""
        result = vs._wrap_text("你好", 800, self.font, self.draw)
        self.assertEqual(len(result), 1)

    def test_chinese_text_wrapping(self):
        """中文文本换行"""
        text = "这是一段很长的中文测试文本，用于验证换行逻辑是否正常工作"
        result = vs._wrap_text(text, 100, self.font, self.draw)
        self.assertGreater(len(result), 1, "长文本应产生多行")

    def test_english_text_wrapping(self):
        """英文文本换行"""
        text = "This is a very long English text for testing wrapping logic"
        result = vs._wrap_text(text, 100, self.font, self.draw)
        self.assertGreater(len(result), 1, "长英文应产生多行")

    def test_mixed_text_wrapping(self):
        """中英混排换行"""
        text = "这是一段mixed text中英文混排的测试内容for testing"
        result = vs._wrap_text(text, 200, self.font, self.draw)
        self.assertGreater(len(result), 0, "至少应有一行")

    def test_single_char(self):
        """单字符不换行"""
        result = vs._wrap_text("A", 800, self.font, self.draw)
        self.assertEqual(len(result), 1)


class TestUtils(unittest.TestCase):
    """工具函数测试"""

    def test_check_ffmpeg(self):
        """FFmpeg 检查不抛异常，返回布尔值"""
        try:
            has_ffmpeg = vs.check_ffmpeg(fatal=False)
            self.assertIsInstance(has_ffmpeg, bool)
        except Exception as e:
            self.fail(f"check_ffmpeg 抛异常: {e}")

    def test_format_timestamp(self):
        """时间戳格式化正确"""
        self.assertEqual(vs.format_timestamp(0), "0:00")
        self.assertEqual(vs.format_timestamp(65), "1:05")
        self.assertEqual(vs.format_timestamp(3661), "1:01:01")

    def test_format_timestamp_negative(self):
        """负时间戳处理"""
        result = vs.format_timestamp(-1)
        self.assertIn("0:00", result)

    def test_detect_language(self):
        """语言检测函数可调用"""
        result = vs.detect_language("这是一段中文文本")
        self.assertIsNotNone(result)


class TestSocialCopy(unittest.TestCase):
    """社交文案生成测试"""

    def test_generate_social_copy_empty(self):
        """空摘要生成社交文案应返回空"""
        result = vs.generate_social_copy({}, "wechat", "zh")
        self.assertIsNone(result)

    def test_generate_social_copy_with_summary(self):
        """有摘要时生成社交文案"""
        sample = {"summary": "这是一个测试视频摘要内容"}
        result = vs.generate_social_copy(sample, "wechat", "zh")
        self.assertIsNotNone(result)

    def test_generate_social_copy_all_platforms(self):
        """所有平台都能生成文案"""
        sample = {"summary": "测试摘要", "key_points": ["要点1", "要点2"]}
        for platform in ["wechat", "xiaohongshu", "weibo", "douyin", "auto"]:
            result = vs.generate_social_copy(sample, platform, "zh")
            # auto 模式下可能返回 None 如果无法判断平台
            if platform != "auto":
                self.assertIsNotNone(result, f"平台 {platform} 应生成文案")


class TestDisplayResults(unittest.TestCase):
    """展示结果测试"""

    def test_display_results_no_error(self):
        """展示结果不抛异常"""
        result = {
            "title": "测试视频",
            "summary": "测试摘要",
            "key_points": ["要点1", "要点2"],
        }
        options = {"summary": True, "quotes": False, "score": False, "full_analysis": False}
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            vs.display_results(result, options)
        except Exception as e:
            self.fail(f"display_results 抛异常: {e}")
        finally:
            sys.stdout = old_stdout


class TestParseAnalysisResult(unittest.TestCase):
    """分析结果解析测试"""

    def test_parse_empty_text(self):
        """空文本解析"""
        result = vs.parse_analysis_result("", {"summary": True})
        self.assertIsNotNone(result)

    def test_parse_with_summary(self):
        """含摘要的文本解析"""
        text = "【摘要】\n这是一个测试摘要\n【核心要点】\n- 要点1\n- 要点2"
        result = vs.parse_analysis_result(text, {"summary": True, "quotes": False, "score": False})
        self.assertIsNotNone(result)
        self.assertIn("summary", result)


if __name__ == "__main__":
    print("🧪 视频极速摘要 Pro 测试套件")
    print("=" * 50)
    try:
        from PIL import Image, ImageDraw, ImageFont
        print("✅ Pillow 已安装")
    except ImportError:
        print("⚠️ Pillow 未安装，部分测试将跳过")
    print("=" * 50)
    unittest.main(verbosity=2)