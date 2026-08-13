# video-fast-summary

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![SkillHub](https://img.shields.io/badge/SkillHub-4.8%2F5-brightgreen)](https://skillhub.cn/skill/video-fast-summary)

> AI-powered video summarization tool that extracts titles, summaries, and key points from Bilibili, Douyin, Xiaohongshu, YouTube links or local videos.

## ✨ Features

- **Multi-platform support**: Bilibili, Douyin, Xiaohongshu, YouTube, and local files
- **AI summaries**: Generates a title, a 200-word summary, and 3-5 key points
- **Dual transcription engine**: Tongyi Tingwu (primary) with automatic fallback to Whisper (local)
- **10+ languages**: Chinese, English, Japanese, Korean, French, German, Spanish, Portuguese, Russian, Arabic
- **Rich outputs**: Summaries, quotes, mind maps, social copy, share cards, and subtitles
- **One-command setup**: `check_env.py --setup` auto-installs FFmpeg and all Python dependencies
- **Batch processing**: Process multiple videos at once with `--batch`
- **Competitor analysis**: Compare multiple videos side-by-side
- **No configuration required**: Zero config, ready to use

## 📊 Performance

| Metric | Value |
|--------|-------|
| TRACE Score | 4.8 / 5 |
| Downloads | 814+ on SkillHub |
| Versions | 10+ iterations |
| Languages | 10 |

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/video-fast-summary.git
cd video-fast-summary

# Install dependencies (recommended)
pip install -r requirements.txt
Basic Usage
Summarize a video from a link (Bilibili, Douyin, etc.)

bash
python scripts/video_summarizer.py --url "https://www.bilibili.com/video/BV1GJ411x7xxx" --mode summary
Summarize a local video file

bash
python scripts/video_summarizer.py --file "path/to/video.mp4" --mode summary
Save the summary to a file

bash
python scripts/video_summarizer.py --url "https://www.bilibili.com/video/BV1GJ411x7xxx" --output summary.md
Generate a share card image

bash
python scripts/video_summarizer.py --url "https://www.bilibili.com/video/BV1GJ411x7xxx" --share
Extract quotes and create a mind map

bash
python scripts/video_summarizer.py --url "https://www.bilibili.com/video/BV1GJ411x7xxx" --quotes --mindmap
Batch process multiple videos

bash
python scripts/video_summarizer.py --batch "url1,url2,url3" --mode summary
Environment Setup (Optional)
If you want to use the advanced features (e.g., Tongyi Tingwu), you need to set up your API key. The tool provides an interactive wizard:

bash
python check_env.py --wizard
This will guide you through:

Installing FFmpeg (if missing)

Installing Python dependencies

Configuring your DASHSCOPE_API_KEY

🛠️ Tech Stack
Python 3.8+

Qwen-Plus (Alibaba Cloud) – for summarization and content generation

Paraformer (Tongyi Tingwu) – high-accuracy speech recognition

OpenAI Whisper – local fallback transcription

yt-dlp – video downloading

FFmpeg – audio extraction

Pillow – share card image generation

🤝 Contributing
Contributions are welcome! Please feel free to submit a Pull Request or open an Issue.

Fork the repository

Create your feature branch (git checkout -b feature/amazing-feature)

Commit your changes (git commit -m 'Add some amazing feature')

Push to the branch (git push origin feature/amazing-feature)

Open a Pull Request

💖 Support This Project
GitHub Sponsors – Become a sponsor to support ongoing development

Try it on SkillHub – See it in action

📄 License
This project is licensed under the Apache License 2.0 – see the LICENSE file for details.

🙏 Acknowledgements
Powered by Alibaba Cloud DashScope

Built on the SkillHub platform

Thanks to all users who have downloaded and provided feedback
