<div align="center">
    <a href="https://v2.nonebot.dev/store">
    <img src="https://raw.githubusercontent.com/fllesser/nonebot-plugin-template/refs/heads/resource/.docs/NoneBotPlugin.svg" width="310" alt="logo"></a>

## ✨ 消息存储 ✨

[![LICENSE](https://img.shields.io/github/license/WhyPilotXia/nonebot_plugin_message_storage.svg)](./LICENSE)
[![pypi](https://img.shields.io/pypi/v/nonebot-plugin-message-storage.svg)](https://pypi.python.org/pypi/nonebot-plugin-message-storage)
[![python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org)
[![NoneBot](https://img.shields.io/badge/NoneBot-2.x-green.svg)](https://github.com/nonebot/nonebot2)

</div>

## 📖 介绍

一个用于记录 QQ 群聊与私聊消息的 NoneBot2 插件，支持消息检索、常见 notice 事件入库，并可选启用 AI 图片识别，将图片消息总结为可搜索文本。

功能特色：

- **消息存储**：记录群聊与私聊消息，私聊使用 `group_id=-1` 存入同一张消息表。
- **事件记录**：支持戳一戳、加群、退群/被踢、群撤回、私聊撤回等事件写入消息表。
- **消息检索**：使用 `/查消息` 在当前会话或指定群中搜索历史消息。
- **AI 识图**：遇到图片消息时可缓存图片并批量识别，识别成功后把原图片 CQ 码回写为 `[image:{summary:"",tip:""}]`。
- **上下文感知**：识图时会带上图片前方的聊天上下文，已识别图片会使用数据库中的总结版本。
- **批量缓存**：待识别图片写入 `pending_images.json`，累计 5 张、等待 30 分钟或收到命令时提交。
- **本地缓存**：使用 `nonebot-plugin-localstore` 管理缓存目录，成功或失败后自动清理图片缓存。

## 💿 安装

### 使用 nb-cli 安装

在 nonebot2 项目的根目录下打开命令行，输入以下指令：

```bash
nb plugin install nonebot_plugin_message_storage
```

### 使用包管理器安装

在 nonebot2 项目的插件目录下，打开命令行，根据你使用的包管理器输入相应命令。

#### pdm

```bash
pdm add nonebot_plugin_message_storage
```

#### poetry

```bash
poetry add nonebot_plugin_message_storage
```

然后打开 nonebot2 项目根目录下的 `pyproject.toml` 文件，在 `[tool.nonebot]` 部分追加写入：

```toml
plugins = ["nonebot_plugin_message_storage"]
```

### 本地插件安装

如果直接使用本仓库源码，可以将 `nonebot_plugin_message_storage` 文件夹放入项目插件目录，并在 `pyproject.toml` 中加载：

```toml
plugins = ["nonebot_plugin_message_storage"]
```

## ⚙️ 配置

在 nonebot2 项目的 `.env` 或 `.env.prod` 文件中添加下表中的配置。

### 基础配置

| 配置项 | 必填 | 默认值 | 说明 |
|:--:|:--:|:--:|:--|
| `DB_URL` | 否 | `sqlite:///qq_messages.db` | SQLAlchemy 数据库连接地址。 |
| `IMAGE_BATCH_SIZE` | 否 | `5` | 待识别图片累计达到该数量后自动提交 AI。 |
| `IMAGE_FLUSH_SECONDS` | 否 | `1800` | 待识别图片最久等待时间，单位秒。 |

### AI 识图配置

| 配置项 | 必填 | 默认值 | 说明 |
|:--:|:--:|:--:|:--|
| `AI_API_KEY` | 否 | 空字符串 | AI 接口密钥。为空时不启用 AI 识图，只保存原始消息内容。 |
| `AI_BASE_URL` | 否 | `https://api.exesim.com/v1` | OpenAI 兼容接口地址。 |
| `AI_MODEL` | 否 | `gemini-3.5-flash` | 用于识图总结的模型名称。 |

**配置示例：**

```env
AI_API_KEY="sk-xxxxxxxxxxxxxxxx"
AI_BASE_URL="https://api.exesim.com/v1"
AI_MODEL="gemini-3.5-flash"
IMAGE_BATCH_SIZE=5
IMAGE_FLUSH_SECONDS=1800
```

> 未配置 `AI_API_KEY` 时，插件启动会输出 info 日志，并跳过识图逻辑；图片消息仍会按原始 CQ 码存入数据库。

## 🎉 使用

### 指令表

| 指令 | 权限 | 说明 |
|:--:|:--:|:--|
| `/查消息 <关键词>` | 所有用户 | 在当前群聊或当前私聊中搜索消息。 |
| `/查消息 <群号> <关键词>` | 所有用户 | 搜索指定群号中的消息。 |
| `/识别` | 所有用户 | 回复一条图片消息使用；已有总结则返回数据库中的总结，未识别则立即提交识别后返回。 |
| `/立即识别` | 所有用户 | 提交当前群聊或当前私聊中的待识别图片。 |
| `/立即识别 全部` | 超级用户 | 提交所有会话中的待识别图片。 |

### 存储说明

- 群聊消息按真实 `group_id` 存储。
- 私聊消息也写入 `group_messages`，其中 `group_id=-1`，使用 `user_id` 区分私聊会话。
- 图片未识别或识别失败时，数据库中保留原始 CQ 码。
- 图片识别成功后，会回写当前消息的 `raw_message`，将图片段替换为：

```text
[image:{summary:"图片总结",tip:"不确定性提示"}]
```

### AI 识图触发规则

- 收到图片消息后，先下载并压缩到本地缓存，再写入 `pending_images.json`。
- 累计待识别图片达到 `IMAGE_BATCH_SIZE` 时自动提交。
- 最早一张待识别图片等待超过 `IMAGE_FLUSH_SECONDS` 时自动提交。
- 用户发送 `/立即识别` 时提交当前会话的待识别图片。
- 超级用户发送 `/立即识别 全部` 时提交全局待识别图片。

### 识图上下文规则

- 每张图片至少尝试读取前一条消息作为上下文。
- 从当前图片消息之前持续向前取整条消息，没有固定条数限制。
- 上下文累计超过约 150 字后停止继续增加。
- 单条消息不会截断；如果加入某条消息会让上下文超过 600 字，则不加入该条。
- 如果上下文中已有 AI 图片总结，会使用数据库内的总结版本。

## 📦 数据与缓存

插件使用 `nonebot-plugin-localstore` 管理本地数据目录：

- `pending_images.json`：待识别图片任务账本。
- `image_cache/`：待识别图片缓存目录。

图片识别成功或失败后，任务会从 `pending_images.json` 中移除，对应缓存图片也会删除。

## 🗂️ 项目结构

```text
nonebot_plugin_message_storage/
├── __init__.py          # 插件入口，声明元数据，初始化数据库，注册启动任务并加载 handlers
├── config.py            # 插件配置模型，读取数据库地址、AI 接口、批量识别数量和超时时间
├── constants.py         # 定义 localstore 数据目录、图片缓存目录和 pending_images.json 路径
├── db.py                # 创建 SQLAlchemy engine/session，并提供 init_db() 初始化表结构
├── models.py            # 定义 GroupMessage 数据模型，对应 group_messages 表
├── prompt.py            # 构造 AI 识图提示词，包含聊天时间线、图片任务和返回格式要求
├── vision.py            # 调用 OpenAI 兼容视觉接口，上传 base64 图片并解析 AI JSON 返回
├── handlers/
│   ├── __init__.py      # 汇总导入所有 handler，完成指令和事件监听注册
│   ├── notices.py       # 监听戳一戳、加群、退群、撤回等 notice 事件并写入消息表
│   ├── recognize.py     # 实现 /立即识别、/立即识别 全部 和回复图片消息使用的 /识别
│   ├── search.py        # 实现 /查消息 指令，将搜索结果渲染为图片回复
│   └── store.py         # 监听群聊/私聊消息，写入数据库，并为图片消息建立待识别任务
└── services/
    ├── __init__.py      # services 子包标记文件
    ├── contacts.py      # 获取用户展示名，优先群名片，再好友备注/昵称，最后陌生人昵称
    ├── context.py       # 为图片识别选择前文消息，并生成消息快照
    ├── images.py        # 下载 OneBot 图片，兼容 URL 与本地路径，并压缩为 JPEG 缓存
    ├── image_tasks.py   # 将消息中的图片转换为 pending 任务，写入缓存图片和任务账本
    ├── message_utils.py # 消息类型判断、图片段提取、CQ 图片正则和图片总结段格式化工具
    └── pending.py       # 管理 pending_images.json，批量识别图片、构造时间线、回写数据库并清理缓存
```

## 🧩 兼容性

- Python `3.10+`
- NoneBot2 2.3.0+
- OneBot v11 适配器
- 依赖 `nonebot-plugin-localstore`

## 📄 License

本项目遵循仓库中的 LICENSE 文件。
