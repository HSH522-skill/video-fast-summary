付费安装与授权说明（示例 — 可放入 README.md 的“付费安装”章节）

付费版本概述
- Video Fast Summary 商业版提供更高并发、更长时长的视频处理、企业级 SLA 与专属支持。
- 购买后将获得 License Key（授权码），用于激活高级功能或访问托管服务 API。

快速开始（本地离线版 + License 校验）
1. 获取软件包
   - 购买后你会收到一个下载链接（或成为组织成员后访问私有 Release）。
2. 安装
   - 解压并进入目录：
     tar -xzf video-fast-summary-v1.0.0.tar.gz
     cd video-fast-summary
   - 安装依赖（示例 Node.js）：
     npm ci
3. 配置 License
   - 从购买邮件或平台获取 LICENSE_KEY。
   - 编辑配置文件 .env（或直接导出环境变量）：
     LICENSE_KEY=你的授权码
     LICENSE_SERVER=https://license.yourdomain.com
   - 启动程序：
     npm start
4. 运行时授权验证
   - 程序启动时会向 LICENSE_SERVER 发送验证请求；验证通过后解锁高级功能。
   - 若长期离线使用，请联系 support@example.com 申请离线授权流程（仅供企业版，并需提供机器指纹）。

SaaS/托管版（推荐）
- 购买订阅后，用户通过 API Key 调用我们的托管服务（不需本地算力）。
- 计费方式：订阅包（月/年）或按分钟/次计费。购买后会自动生成 API Key 并发送到邮箱。

售后与支持
- 试用期���可申请退款（详情见退款政策）。
- 技术支持：support@example.com（或在 Marketplace/购买平台内提交工单）。

安全与隐私提示
- 请勿在公共仓库或公开渠道泄露 LICENSE_KEY。
- 若怀疑授权被盗用，请立即联系我们以重置授权。
