<div>
    <a href="https://v2.nonebot.dev/store">
    <img src="https://raw.githubusercontent.com/fllesser/nonebot-plugin-template/refs/heads/resource/.docs/NoneBotPlugin.svg" width="310" alt="logo"></a>

## ✨ 消息存储 ✨

[![LICENSE](https://img.shields.io/github/license/WhyPilotXia/nonebot_plugin_message_storage.svg)](./LICENSE)[![pypi](https://img.shields.io/pypi/v/nonebot-plugin-message-storage.svg)](https://pypi.python.org/pypi/nonebot-plugin-message-storage)[![python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org)[![NoneBot](https://img.shields.io/badge/NoneBot-2.x-green.svg)](https://github.com/nonebot/nonebot2)

## 📖 介绍

一个用于记录 QQ 群聊与私聊消息的 NoneBot2 插件，支持消息检索、常见 notice 事件入库，并可选启用 AI 图片识别，将图片消息总结为可搜索文本。

功能特色：

- **消息存储**：记录群聊与私聊消息，私聊使用 `group_id=-1` 存入同一张消息表。
- **事件记录**：支持戳一戳、加群、退群/被踢、群撤回、私聊撤回等事件写入消息表。
- **消息检索**：使用 `/查消息` 在当前会话或指定群中搜索历史消息。
- **AI 识图**：遇到图片消息时可缓存图片并批量识别，识别成功后把原图片 CQ 码回写为 `[image:{summary:"",tip:""}]`。
- **上下文感知**：识图时会带上图片前后方的聊天上下文，已识别图片会使用数据库中的总结版本。
- **批量缓存**：待识别图片写入 `pending_images.json`，累计 5 张、等待 30 分钟或收到命令时提交。
- **本地缓存**：使用 `nonebot-plugin-localstore` 管理缓存目录，成功或失败后自动清理图片缓存。

## 💿 安装

### 使用 nb-cli 安装

在 nonebot2 项目的根目录下打开命令行，输入以下指令：

```bash
nb plugin install nonebot-plugin-message-storage
```

### 使用包管理器安装

在 nonebot2 项目的插件目录下，打开命令行，根据你使用的包管理器输入相应命令。

#### pdm

```bash
pdm add nonebot-plugin-message-storage
```

#### poetry

```bash
poetry add nonebot-plugin-message-storage
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
| `IMAGE_CONTEXT_BEFORE_CHARS` | 否 | `100` | 每张图片前方上下文的目标字数。 |
| `IMAGE_CONTEXT_AFTER_CHARS` | 否 | `100` | 每张图片后方上下文的目标字数。 |

### AI 识图配置

| 配置项 | 必填 | 默认值 | 说明 |
|:--:|:--:|:--:|:--|
| `AI_API_KEY` | 否 | (空字符串) | AI 接口密钥。为空时不启用 AI 识图，只保存原始消息内容。 |
| `AI_BASE_URL` | 否 | `https://api.exesim.com/v1` | OpenAI 兼容接口地址。 |
| `AI_MODEL` | 否 | `gemini-3.5-flash` | 用于识图总结的模型名称。 |

**配置示例：**

```env
AI_API_KEY="sk-xxxxxxxxxxxxxxxx"
AI_BASE_URL="https://api.exesim.com/v1"
AI_MODEL="gemini-3.5-flash"
IMAGE_BATCH_SIZE=5
IMAGE_FLUSH_SECONDS=1800
IMAGE_CONTEXT_BEFORE_CHARS=100
IMAGE_CONTEXT_AFTER_CHARS=100
```

> 未配置 `AI_API_KEY` 时，插件启动会输出 info提示跳过识图逻辑；图片消息仍会按原始 CQ 码存入数据库。

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
- 待识别图片累计达到 `IMAGE_BATCH_SIZE`，且这些图片都已积攒到 `IMAGE_CONTEXT_AFTER_CHARS` 的后文时自动提交。
- 如果达到批量数量时又出现了新图片，新图片会继续等待自己的后文，不会被提前并入上一批。
- 最早一张待识别图片等待超过 `IMAGE_FLUSH_SECONDS` 时自动提交。
- 用户发送 `/识别` 或 `/立即识别` 时会立即提交对应待识别图片，不等待后文继续积累。
- 超级用户发送 `/立即识别 全部` 时提交全局待识别图片。

### 识图上下文规则

- 每张图片会分别向前、向后读取上下文，默认目标字数分别是 `IMAGE_CONTEXT_BEFORE_CHARS=100` 和 `IMAGE_CONTEXT_AFTER_CHARS=100`。
- 图片后的发言会保留给这张图片作为后文上下文，直到批量提交、超时提交或命令立即提交。
- 从当前图片消息前后持续取整条消息，没有固定条数限制。
- 上下文窗口会按真实聊天顺序合并去重，多张图片上下文重叠时不会重复塞给 AI。
- 单条消息不会截断；如果加入某条消息会让单侧上下文超过 600 字，则不加入该条。
- 如果上下文中已有 AI 图片总结，会使用数据库内的总结版本。

## 📦 数据与缓存

插件使用 `nonebot-plugin-localstore` 管理本地数据目录：

- `pending_images.json`：待识别图片任务账本。
- `image_cache/`：待识别图片缓存目录。

图片识别成功或失败后，任务会从 `pending_images.json` 中移除，对应缓存图片也会删除。

## 🧐 图片示例


/识别 效果

<img width="655" height="564" alt="image" src="https://github.com/user-attachments/assets/67a5d86f-ca2e-4f50-9fd7-394b2646abc3" />

<img width="578" height="458" alt="image" src="https://github.com/user-attachments/assets/48c6b4a5-9fb8-4a19-99ba-291c246e877f" />

<img width="575" height="441" alt="image" src="https://github.com/user-attachments/assets/e1c4a564-8819-480d-8e86-7abd1d9979a4" />


<img width="572" height="582" alt="image" src="https://github.com/user-attachments/assets/5e201601-e8ac-4565-a37f-bf397ae92f27" />


<img width="598" height="539" alt="image" src="https://github.com/user-attachments/assets/0d4fa7ac-3902-4ce4-835f-701d742a12bf" />

<img width="570" height="951" alt="image" src="https://github.com/user-attachments/assets/d68afd8b-30e8-4ab5-8a99-14caf5d1335f" />

<img width="613" height="471" alt="image" src="https://github.com/user-attachments/assets/88a96bc3-b4a9-4455-959d-262a6689ef7f" />

<img width="526" height="458" alt="image" src="https://github.com/user-attachments/assets/484458f3-4e34-4cd8-89cb-285d8dab5f7c" />



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



## 更新内容

1.1.0：

```text
现在已经全部跑通了。需要做一个小优化：图片发完后，以及等待攒满batchsize张时，这期间群友会发言。每张图后面允许100字内容，逻辑与每张图前面类似（图后发言仍然缓存在那张图上下文）。这样可以更好的表达上下文。逻辑改为满足batchsize张且后面字数达到指定值（前后预期字数都设为配置项，默认前100，后100），提交（后面字数达到指定值期间可能会有新图，此时该新图应该未满足后预期字数，则作为下一批pending任务）。若为/识别或/立即识别。马上提交，也就是不等后面的100字。但是对于比如之前的未识别图可能后面已经积攒了上下文，不要删除。依然构造完整去重上下文。

已完成这次“图后上下文 + batch 等待”的优化。
改动要点：
新增配置项：IMAGE_CONTEXT_BEFORE_CHARS，默认 100
IMAGE_CONTEXT_AFTER_CHARS，默认 100

每张待识别图片现在会取：图前上下文，默认目标 100 字
图后上下文，默认目标 100 字

batch 自动提交逻辑改为：pending 中达到 IMAGE_BATCH_SIZE
且被提交的那些图片都已经积攒到足够图后上下文
新来的图片如果还没攒够后文，会留在下一批

/识别、/立即识别、超时提交仍然立即提交，不等待后文继续积累。
timeline 构造仍然会合并去重所有前后上下文，按真实聊天顺序给 AI。
图片 CQ 码在普通文本上下文里会被剔除，避免未选中的新图以原始 CQ 码污染 prompt。
```

1.0.0:

```
加一个命令：/识别。命令只在带有回复消息时有效（checker）此时去读回复的消息（参考：if event.reply:
        state["abstract"] = str(event.reply.message)
        return）或者查数据库已存消息ID
若其中无图片，回复"回复的消息似乎不包含图片哦"，如果有，如果已经提交过识别存入，
先贴表情（    try:
        await bot.call_api('set_msg_emoji_like', group_id=event.group_id, message_id=event.message_id, emoji_id='320', 
                       set=True)
    except Exception as e:
        logger.opt(exception=e).warning("贴表情失败")）
返回数据库中那条消息（即识别后结果）
如果没有，
先贴表情（314）自动执行/立即识别，然后返回数据库中那条消息（即识别后结果）

已加 /识别 命令。
实现行为：
只在“回复消息”时触发，非回复不会响应。
优先从 event.reply 读取回复消息；没有的话读 reply 消息段并 bot.get_msg；再兜底用数据库里的 raw CQ 解析。
根据回复消息的 message_id 查数据库。
如果数据库中没有这条消息：返回 没有在数据库中找到回复的消息。
如果没有图片：返回 回复的消息似乎不包含图片哦
如果图片已经识别完成，也就是数据库里已经是 [image:{summary:"",tip:""}]：群聊里给命令消息贴 emoji_id=320
返回数据库中那条消息的 raw_message

如果还有未识别的 CQ 图片：群聊里给命令消息贴 emoji_id=314
立即为回复消息补建 pending 图片任务
执行当前会话范围的识别
返回数据库中更新后的那条消息
```

