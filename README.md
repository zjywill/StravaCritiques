# Strava 活动点评工具包

<p align="center">
  <img src="assets/strava-ai-icon.svg" alt="Strava AI Toolkit Icon" width="140" />
</p>

这是一个基于 AI 智能体的 Strava 活动点评自动化工具包，集成了数据抓取、AI 点评生成和自动回写功能。系统支持批量处理你的 Strava 运动数据，使用 LLM 生成中文运动点评，并自动同步回 Strava 活动描述。

## ✨ 核心功能

- **一体化点评脚本** (`critique.py`) - 整合了活动抓取、点评生成、自动上传的完整工作流
- **智能体架构点评** (`ai_gen_comment.py`) - 基于工具的智能体架构，支持复杂运动数据分析
- **增强活动分析** - 新增游泳活动分析，支持多种运动类型的深度数据解读
- **自动化 OAuth** (`stravalogin.py`) - Selenium 驱动的令牌获取，支持无头模式
- **数据同步工具** (`latest_activity.py`, `post_comment.py`) - 活动数据抓取和点评上传
- **Flask OAuth 演示** (`strava/app.py`) - 完整的 OAuth 授权流程示例
- **可配置提示词** (`prompts/activity_prompt.md`) - 外部化的活动提示词模板，支持自定义风格

## 🏗️ 系统架构

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Strava API    │────│  活动数据抓取     │────│   AI 智能体     │
│                 │    │                  │    │                │
│ • 活动读取      │    │ • 令牌管理       │    │ • 工具调用架构   │
│ • 描述更新      │    │ • 数据持久化     │    │ • 智能分析引擎   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  OAuth 授权流程 │    │    数据存储      │    │   提示词管理    │
│                 │    │                  │    │                │
│ • Selenium 自动  │    │ • JSON 格式     │    │ • 外部化模板    │
│ • Flask 服务     │    │ • 状态跟踪      │    │ • 多运动类型支持 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 📁 项目结构

- `critique.py` - **主要入口**，一键完成抓取、生成、上传全流程
- `ai_gen_comment.py` - AI 智能体点评生成核心逻辑（基于工具架构）
- `latest_activity.py` - Strava 活动数据抓取器
- `post_comment.py` - 点评内容上传到 Strava
- `stravalogin.py` - Selenium OAuth 令牌自动化获取
- `strava/app.py` - Flask OAuth 授权服务器
- `prompts/activity_prompt.md` - 可配置的活动点评提示词模板
- `AGENTS.md` - 开发者指南和代码规范文档
- `CLAUDE.md` - Claude Code 开发环境配置指南

## 🚀 快速开始

### 环境准备

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env                    # 编辑 .env 添加必要的 API 密钥
```

### 必需的环境变量

| 变量名 | 用途 | 默认值 |
|--------|------|--------|
| `ONE_API_KEY` / `OPENAI_API_KEY` | LLM API 密钥 | - |
| `ONE_API_MODEL` | LLM 模型名称 | `gpt-3.5-turbo` |
| `ONE_API_REMOTE` | 自定义 API 端点 | - |
| `STRAVA_CLIENT_ID` | Strava 应用 ID | - |
| `STRAVA_CLIENT_SECRET` | Strava 应用密钥 | - |
| `FLASK_SECRET_KEY` | Flask 会话密钥 | - |
| `LLM_SYSTEM_PROMPT` | 自定义点评指令 | 中文毒舌风格 |

## 📋 使用方法

### 方法一：一键完整流程（推荐）

```bash
# 一键完成：抓取活动 → 生成点评 → 自动上传
python critique.py --per-page 3

# 仅生成点评，不上传
python critique.py --per-page 5 --skip-upload

# 预览模式（不真正上传）
python critique.py --dry-run

# 自定义 LLM 配置
python critique.py --model "gpt-4" --base-url "https://api.openai.com"
```

### 方法二：分步操作

**1. 获取 Strava 访问令牌**

```bash
python stravalogin.py --headless
```

**2. 抓取最新活动**

```bash
python latest_activity.py --per-page 5
```

**3. 生成智能点评**

```bash
python ai_gen_comment.py
```

该脚本会读取 `prompts/activity_prompt.md` 中的提示词模板来生成点评内容，你可以直接编辑该文件以调整点评风格、语气或分析要求。默认采用友好鼓励的风格，根据不同运动类型提供专业建议。

**4. 上传点评到 Strava**

```bash
python post_comment.py --max-count 3
```

## 🎯 高级用法

### 自定义点评风格

系统支持多种自定义点评风格的方式：

```bash
# 方法1：通过环境变量设置自定义系统提示词
export LLM_SYSTEM_PROMPT="你是一个专业的运动教练，给出鼓励性的建议"

# 方法2：在命令行中覆盖提示词
python critique.py --system-prompt "用幽默的风格点评这次运动"

# 方法3：直接编辑提示词模板文件
vim prompts/activity_prompt.md  # 修改后立即生效
```

### 支持的运动类型

系统智能识别多种运动类型并提供针对性分析：
- **骑自行车** - 踏频、心率、功率分析
- **跑步** - 配速、步频、心率区间
- **游泳** - 泳姿、划水频率、技术分析
- **Track Me** - 日常活动、步行、徒步数据分析

### 批量处理管理

```bash
# 控制上传数量，避免触发 API 限制
python critique.py --per-page 10 --max-upload 3

# 重新生成已上传的点评
python critique.py --regenerate-uploaded

# 跳过抓取，使用现有数据
python critique.py --skip-fetch --activities-file my_activities.json
```

## 🔧 开发调试

### Flask OAuth 服务器

```bash
flask --app strava.app --debug run
# 访问 http://localhost:5000/login
```

### 测试和代码检查

```bash
# 运行测试
pytest

# 代码格式化
ruff --fix .
black .
```

## 🤖 AI 智能体架构

系统采用基于工具的智能体架构，提供更强大和灵活的活动分析能力：

- **模块化工具调用** - 将复杂分析任务拆分为独立的工具函数
- **上下文理解** - 智能体能理解不同运动类型的特定数据字段
- **灵活的提示管理** - 通过外部化模板支持快速调整分析风格
- **可扩展架构** - 易于添加新的运动类型和分析维度

## 📊 数据文件说明

- `user_token/` - 存储 OAuth 访问令牌
- `latest_activities.json` - 抓取的活动数据
- `activity_critiques.json` - 生成的点评和上传状态

## 🛡️ 安全注意事项

- **敏感数据保护**：`.env`、`user_token/`、`latest_activities.json` 包含敏感信息，请勿提交到版本控制
- **令牌管理**：定期刷新访问令牌，确保权限正常
- **API 限制**：注意 Strava API 的速率限制，避免频繁调用
- **数据清理**：分享代码时请清理点评数据中的个人信息

## 🤝 贡献指南

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/amazing-feature`
3. 提交更改：`git commit -m 'Add amazing feature'`
4. 推送到分支：`git push origin feature/amazing-feature`
5. 提交 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

---

💡 **提示**：首次使用建议先运行 `python critique.py --dry-run` 预览效果，确认点评风格和内容质量符合预期后再执行实际上传。系统默认采用友好鼓励的风格，适合各种运动水平的用户。
