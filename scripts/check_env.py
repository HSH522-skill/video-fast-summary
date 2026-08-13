#!/usr/bin/env python3
"""秒懂 - 一键配置 + 环境检测
检测: python check_env.py         — 10秒出结果
向导: python check_env.py --wizard — 手把手引导
一键: python check_env.py --setup  — 自动安装+配置，一条命令全搞定
"""

import sys
import shutil
import subprocess
import os
import platform
import argparse


# ── 工具函数 ──────────────────────────────────────────

def _ok(msg):
    print(f"  ✅ {msg}")

def _fail(msg, help_text=""):
    print(f"  ❌ {msg}")
    if help_text:
        print(f"     → {help_text}")

def _info(msg):
    print(f"  ℹ️  {msg}")

def _warn(msg):
    print(f"  ⚠️  {msg}")

def _section(title):
    print(f"\n{'─' * 50}")
    print(f"  {title}")
    print(f"{'─' * 50}")

def _wait_enter():
    try:
        input("\n   👉 完成后按 Enter 继续...")
    except (EOFError, KeyboardInterrupt):
        print("\n")


# ── 检测函数 ──────────────────────────────────────────

def check_python():
    v = sys.version_info
    if v.major >= 3 and v.minor >= 8:
        _ok(f"Python {v.major}.{v.minor}.{v.micro}")
        return True
    _fail(f"Python {v.major}.{v.minor}.{v.micro}（需要 3.8+）")
    return False


def check_ffmpeg():
    path = shutil.which("ffmpeg")
    if path:
        try:
            result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
            version_line = result.stdout.split("\n")[0] if result.stdout else "已安装"
            _ok(f"FFmpeg 已就绪 — {version_line}")
            return True
        except Exception:
            _ok(f"FFmpeg 已安装（{path}）")
            return True
    return False


def check_api_key():
    key = os.getenv("DASHSCOPE_API_KEY")
    if key:
        masked = key[:8] + "****" + key[-4:] if len(key) > 12 else "****"
        _ok(f"API Key 已配置 — {masked}")
        return True
    return False


def check_pip_deps():
    deps = {
        "yt-dlp": "yt_dlp",
        "requests": "requests",
        "dashscope": "dashscope",
        "Pillow": "PIL",
        "openai": "openai",
    }
    missing = []
    for name, import_name in deps.items():
        try:
            __import__(import_name)
            _ok(name)
        except ImportError:
            _warn(f"{name} — 未安装")
            missing.append(name)
    return missing


def check_whisper():
    try:
        __import__("whisper")
        _ok("whisper（备用转写引擎）")
        return True
    except ImportError:
        _info("whisper 未安装（可选，不影响主功能）")
        return False


# ── 自动安装 ──────────────────────────────────────────

def install_ffmpeg():
    """自动安装 FFmpeg，根据操作系统选择最佳方式"""
    system = platform.system()

    if system == "Darwin":
        if shutil.which("brew"):
            _info("正在通过 Homebrew 安装 FFmpeg...")
            try:
                subprocess.check_call(["brew", "install", "ffmpeg"], timeout=600)
                _ok("FFmpeg 安装完成")
                return True
            except Exception as e:
                _warn(f"自动安装失败: {e}")
                return False
        else:
            _warn("未检测到 Homebrew，请先安装 Homebrew 或手动安装 FFmpeg")
            return False

    elif system == "Linux":
        if shutil.which("apt"):
            _info("正在通过 apt 安装 FFmpeg（可能需要 sudo 密码）...")
            try:
                subprocess.check_call(["sudo", "apt", "install", "-y", "ffmpeg"], timeout=600)
                _ok("FFmpeg 安装完成")
                return True
            except Exception as e:
                _warn(f"apt 安装失败: {e}")
                return False
        elif shutil.which("yum"):
            _info("正在通过 yum 安装 FFmpeg...")
            try:
                subprocess.check_call(["sudo", "yum", "install", "-y", "ffmpeg"], timeout=600)
                _ok("FFmpeg 安装完成")
                return True
            except Exception:
                try:
                    subprocess.check_call(["sudo", "yum", "install", "-y", "epel-release"], timeout=120)
                    subprocess.check_call(["sudo", "yum", "install", "-y", "ffmpeg"], timeout=600)
                    _ok("FFmpeg 安装完成")
                    return True
                except Exception as e:
                    _warn(f"yum 安装失败: {e}")
                    return False
        elif shutil.which("dnf"):
            _info("正在通过 dnf 安装 FFmpeg...")
            try:
                subprocess.check_call(["sudo", "dnf", "install", "-y", "ffmpeg-free"], timeout=600)
                _ok("FFmpeg 安装完成")
                return True
            except Exception as e:
                _warn(f"dnf 安装失败: {e}")
                return False
        else:
            _warn("未检测到包管理器，请手动安装: https://ffmpeg.org/download.html")
            return False

    elif system == "Windows":
        if shutil.which("winget"):
            _info("正在通过 winget 安装 FFmpeg...")
            try:
                subprocess.check_call(
                    ["winget", "install", "--id", "Gyan.FFmpeg", "--silent", "--accept-package-agreements"],
                    timeout=600
                )
                _info("FFmpeg 安装完成，请重新打开终端使其生效")
                return True
            except Exception as e:
                _warn(f"winget 安装失败: {e}")
        elif shutil.which("choco"):
            _info("正在通过 Chocolatey 安装 FFmpeg...")
            try:
                subprocess.check_call(["choco", "install", "ffmpeg", "-y"], timeout=600)
                _ok("FFmpeg 安装完成")
                return True
            except Exception as e:
                _warn(f"Chocolatey 安装失败: {e}")
        elif shutil.which("scoop"):
            _info("正在通过 Scoop 安装 FFmpeg...")
            try:
                subprocess.check_call(["scoop", "install", "ffmpeg"], timeout=600)
                _ok("FFmpeg 安装完成")
                return True
            except Exception as e:
                _warn(f"Scoop 安装失败: {e}")

        _warn("未检测到 winget/choco/scoop，请手动安装: https://ffmpeg.org/download.html")
        return False

    return False


def install_pip_deps(missing):
    if not missing:
        return True
    _info(f"正在安装: {', '.join(missing)}...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet"] + missing,
            timeout=300
        )
        _ok("依赖安装完成")
        return True
    except Exception as e:
        _fail(f"自动安装失败: {e}")
        _info(f"请手动执行: pip install {' '.join(missing)}")
        return False


def get_api_key_help():
    return (
        "获取 API Key（免费，2 分钟）：\n"
        "  1. 打开 https://dashscope.console.aliyun.com/\n"
        "  2. 注册/登录阿里云账号\n"
        "  3. 左侧菜单 → 模型服务 → API Key 管理 → 创建 API Key\n"
        "  4. 复制 Key 后在终端执行：\n"
        "     macOS/Linux: export DASHSCOPE_API_KEY=sk-你的key\n"
        "     Windows CMD:  set DASHSCOPE_API_KEY=sk-你的key\n"
        "     Windows PowerShell: $env:DASHSCOPE_API_KEY=\"sk-你的key\"\n"
        "  💰 新用户有免费额度，日常使用完全够用"
    )


# ── 一键配置（--setup） ──────────────────────────────

def setup():
    print()
    print("=" * 56)
    print("   ⚡ 秒懂 — 一键配置")
    print("=" * 56)
    print()
    print("   自动安装 FFmpeg、Python 依赖，然后引导配置 API Key。")
    print("   中间可能需要输入密码（安装系统软件），别担心。")
    print()

    _section("Step 1/4: 检查 Python")
    if not check_python():
        _fail("请先升级 Python 到 3.8+: https://www.python.org/downloads/")
        return False

    _section("Step 2/4: 安装 FFmpeg（自动）")
    if check_ffmpeg():
        _info("已安装，跳过")
    else:
        print()
        _info("检测到 FFmpeg 未安装，正在自动安装...")
        if install_ffmpeg():
            if check_ffmpeg():
                _ok("FFmpeg 安装成功！")
            else:
                _warn("FFmpeg 已安装但可能需要重启终端才能生效")
        else:
            _warn("FFmpeg 自动安装失败，但不影响 SkillHub 对话模式使用")

    _section("Step 3/4: 安装 Python 依赖（自动）")
    missing = check_pip_deps()
    if missing:
        print()
        install_pip_deps(missing)
    else:
        _info("已全部安装，跳过")
    check_whisper()

    _section("Step 4/4: 配置 API Key（手动）")
    if check_api_key():
        _info("已配置，跳过")
    else:
        print()
        print(get_api_key_help())
        print()
        _wait_enter()
        if not check_api_key():
            _warn("API Key 仍未检测到")
            _info("SkillHub 对话模式无需配置，不受影响")

    print()
    print("=" * 56)
    _section("最终检查")
    ffmpeg_ok = check_ffmpeg()
    api_ok = check_api_key()
    print()
    if ffmpeg_ok and api_ok:
        print("   🎉 全部就绪！")
        print()
        print("   python scripts/video_summarizer.py --url \"视频链接\"")
        print()
        print("   或者直接在 SkillHub 对话中说「帮我总结这个视频」")
    else:
        if not ffmpeg_ok:
            print("   ⚠️ FFmpeg 未配好，SkillHub 对话模式不受影响")
        if not api_ok:
            print("   ⚠️ API Key 未配好，SkillHub 对话模式不受影响")
        print()
        print("   本地可运行: python scripts/video_summarizer.py --url \"视频链接\"")
        print("   （部分功能可能受限，建议完成配置后再试）")
    print("=" * 56)
    return True


# ── 交互式向导（--wizard） ──────────────────────────

def wizard():
    print()
    print("=" * 56)
    print("   ⚡ 秒懂 — 交互式配置向导")
    print("=" * 56)
    print()
    print("   这个向导会一步步帮你把本地环境配好。")
    print("   全程跟着提示走就行，不用懂技术。")
    print("   想全自动安装？用: python check_env.py --setup")
    print()

    all_pass = True

    _section("Step 1/4: 检查 Python")
    if not check_python():
        _fail("请先升级 Python 到 3.8+: https://www.python.org/downloads/")
        return False

    _section("Step 2/4: 安装 FFmpeg（视频处理工具）")
    if check_ffmpeg():
        pass
    else:
        system = platform.system()
        if system == "Windows":
            print("\n   Windows 安装 FFmpeg：")
            print("   1. 打开 https://ffmpeg.org/download.html")
            print("   2. 下载 Windows 版本（选 ffmpeg-release-full）")
            print("   3. 解压到 C:\\ffmpeg")
            print("   4. 把 C:\\ffmpeg\\bin 加入系统 PATH")
            print("   5. 重新打开终端")
        elif system == "Darwin":
            print("\n   macOS 安装 FFmpeg：brew install ffmpeg")
        else:
            print("\n   Linux 安装 FFmpeg：sudo apt install ffmpeg")
        print()
        _wait_enter()
        if not check_ffmpeg():
            _warn("FFmpeg 仍未检测到，SkillHub 对话模式不受影响")
            all_pass = False

    _section("Step 3/4: 配置 API Key")
    if check_api_key():
        pass
    else:
        print()
        print(get_api_key_help())
        print()
        _wait_enter()
        if not check_api_key():
            _warn("API Key 仍未检测到，SkillHub 对话模式不受影响")
            all_pass = False

    _section("Step 4/4: 安装 Python 依赖")
    missing = check_pip_deps()
    if missing:
        print()
        _info("这些包是运行必需的，现在就帮你装好")
        install_pip_deps(missing)
    check_whisper()

    print()
    print("=" * 56)
    ffmpeg_ok = check_ffmpeg()
    api_ok = check_api_key()
    if ffmpeg_ok and api_ok:
        print()
        print("   🎉 全部就绪！")
        print("   python scripts/video_summarizer.py --url \"视频链接\"")
    else:
        print()
        if not ffmpeg_ok:
            print("   ⚠️ FFmpeg 未配好，SkillHub 对话模式不受影响")
        if not api_ok:
            print("   ⚠️ API Key 未配好，SkillHub 对话模式不受影响")
    print("=" * 56)
    return True


# ── 快速检测（默认） ──────────────────────────────

def quick_check():
    print("=" * 50)
    print("  ⚡ 秒懂 — 环境检测")
    print("=" * 50)
    print()

    results = {
        "Python 3.8+": check_python(),
        "FFmpeg": check_ffmpeg(),
        "API Key": check_api_key(),
    }

    print()
    print("--- 依赖检测 ---")
    missing = check_pip_deps()
    results["pip 依赖"] = len(missing) == 0
    results["Whisper(可选)"] = check_whisper()

    print()
    print("=" * 50)
    failed = [k for k, v in results.items() if not v and k != "Whisper(可选)"]
    if not failed:
        print("🎉 全部就绪！")
        print()
        print("   python scripts/video_summarizer.py --url \"视频链接\"")
    else:
        print(f"⚠️ 还有 {len(failed)} 项需要配置：{', '.join(failed)}")
        print()
        print("   一键搞定: python scripts/check_env.py --setup")
        print("   手把手:   python scripts/check_env.py --wizard")
    print("=" * 50)


# ── 入口 ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="秒懂 环境检测与配置")
    parser.add_argument("--wizard", action="store_true", help="交互式配置向导")
    parser.add_argument("--setup", action="store_true", help="一键自动安装+配置")
    args = parser.parse_args()

    if args.setup:
        setup()
    elif args.wizard:
        wizard()
    else:
        quick_check()


if __name__ == "__main__":
    main()