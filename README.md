# nonebot-plugin-smart-message-storage

支持群聊/私聊消息归档、搜索和 AI 图片理解总结的 NoneBot2 插件。

## 功能

- 记录群聊和私聊消息，私聊使用 `group_id=-1` 存入同一张消息表。
- 支持 `/查消息` 搜索历史消息。
- 记录戳一戳、加群、退群、撤回等 notice 事件。
- 支持 AI 识图，将图片 CQ 码回写为 `[image:{summary:"",tip:""}]`，方便后续搜索。
- 识图时会携带图片前后的聊天上下文。
- 待识别图片会先写入 `pending_images.json`，达到批量数量、超时或收到命令时提交。
- 使用 SQLAlchemy 异步引擎和 `aiosqlite` 访问 SQLite，避免在 NoneBot 异步事件循环里直接阻塞数据库 IO。

## 安装

```bash
nb plugin install nonebot-plugin-smart-message-storage
```

也可以使用包管理器安装：

```bash
pdm add nonebot-plugin-smart-message-storage
```

或：

```bash
poetry add nonebot-plugin-smart-message-storage
```

然后在 NoneBot 项目的 `pyproject.toml` 中启用插件：

```toml
[tool.nonebot]
plugins = ["nonebot_plugin_smart_message_storage"]
```

## 配置

在 NoneBot 项目的 `.env` 或 `.env.prod` 中配置。所有配置项都使用 `MESSAGE_` 前缀，避免和其他插件冲突。

### 基础配置

| 配置项 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `MESSAGE_DB_URL` | 否 | `sqlite:///qq_messages.db` | SQLAlchemy 数据库连接地址。默认数据库仍在 bot.py 同目录的 `qq_messages.db`。 |
| `MESSAGE_IMAGE_BATCH_SIZE` | 否 | `5` | 待识别图片累计达到该数量后自动提交 AI。 |
| `MESSAGE_IMAGE_FLUSH_SECONDS` | 否 | `1800` | 待识别图片最久等待时间，单位秒。 |
| `MESSAGE_IMAGE_CONTEXT_BEFORE_CHARS` | 否 | `100` | 每张图片前方上下文的目标字数。 |
| `MESSAGE_IMAGE_CONTEXT_AFTER_CHARS` | 否 | `100` | 每张图片后方上下文的目标字数。 |

### AI 识图配置

| 配置项 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `MESSAGE_AI_API_KEY` | 否 | 空字符串 | AI 接口密钥。为空时不启用 AI 识图，只保存原始消息内容。 |
| `MESSAGE_AI_BASE_URL` | 否 | `https://api.exesim.com/v1` | OpenAI 兼容接口地址。 |
| `MESSAGE_AI_MODEL` | 否 | `gemini-3.5-flash` | 用于识图总结的模型名称。 |

### 配置示例

```env
MESSAGE_AI_API_KEY="sk-xxxxxxxxxxxxxxxx"
MESSAGE_AI_BASE_URL="https://api.exesim.com/v1"
MESSAGE_AI_MODEL="gemini-3.5-flash"
MESSAGE_IMAGE_BATCH_SIZE=5
MESSAGE_IMAGE_FLUSH_SECONDS=1800
MESSAGE_IMAGE_CONTEXT_BEFORE_CHARS=100
MESSAGE_IMAGE_CONTEXT_AFTER_CHARS=100
# MESSAGE_DB_URL="sqlite:///qq_messages.db"
```

未配置 `MESSAGE_AI_API_KEY` 时，插件会跳过 AI 识图逻辑；图片消息仍会按原始 CQ 码存入数据库。

## 旧配置迁移

旧版本使用了没有前缀的配置名。升级后请按下表修改 `.env` 或 `.env.prod`：

| 旧配置 | 新配置 |
| --- | --- |
| `AI_API_KEY` | `MESSAGE_AI_API_KEY` |
| `AI_BASE_URL` | `MESSAGE_AI_BASE_URL` |
| `AI_MODEL` | `MESSAGE_AI_MODEL` |
| `DB_URL` | `MESSAGE_DB_URL` |
| `IMAGE_BATCH_SIZE` | `MESSAGE_IMAGE_BATCH_SIZE` |
| `IMAGE_FLUSH_SECONDS` | `MESSAGE_IMAGE_FLUSH_SECONDS` |
| `IMAGE_CONTEXT_BEFORE_CHARS` | `MESSAGE_IMAGE_CONTEXT_BEFORE_CHARS` |
| `IMAGE_CONTEXT_AFTER_CHARS` | `MESSAGE_IMAGE_CONTEXT_AFTER_CHARS` |

数据库位置不需要改。默认值仍是：

```env
MESSAGE_DB_URL="sqlite:///qq_messages.db"
```

插件内部会把 SQLite URL 转为 `sqlite+aiosqlite:///qq_messages.db` 来使用异步驱动，但连接的是同一个 `qq_messages.db` 文件，不会迁移、不清空、不改变位置。

## 命令

| 命令 | 权限 | 说明 |
| --- | --- | --- |
| `/查消息 <关键词>` | 所有人 | 在当前群聊或当前私聊中搜索消息。 |
| `/查消息 <群号> <关键词>` | 所有人 | 搜索指定群号中的消息。 |
| `/识别` | 所有人 | 回复一条图片消息使用。已识别则返回数据库中的总结，未识别则立即提交识别。 |
| `/立即识别` | 所有人 | 提交当前群聊或当前私聊中的待识别图片。 |
| `/立即识别 全部` | 超级用户 | 提交所有会话中的待识别图片。 |

## 存储说明

- 群聊消息按真实 `group_id` 存储。
- 私聊消息也写入 `group_messages` 表，其中 `group_id=-1`，使用 `user_id` 区分私聊会话。
- 图片未识别或识别失败时，数据库中保留原始 CQ 码。
- 图片识别成功后，会回写当前消息的 `raw_message`，将图片段替换为：

```text
[image:{summary:"图片总结",tip:"不确定性提示"}]
```

## AI 识图触发规则

- 收到图片消息后，先下载并压缩到本地缓存，再写入 `pending_images.json`。
- 待识别图片累计达到 `MESSAGE_IMAGE_BATCH_SIZE`，且这些图片都已经积攒到 `MESSAGE_IMAGE_CONTEXT_AFTER_CHARS` 的后文时自动提交。
- 如果达到批量数量时又出现新图片，新图片会继续等待自己的后文，不会被提前并入上一批。
- 最早一张待识别图片等待超过 `MESSAGE_IMAGE_FLUSH_SECONDS` 时自动提交。
- 用户发送 `/识别` 或 `/立即识别` 时会立即提交对应待识别图片，不等待后文继续积累。
- 超级用户发送 `/立即识别 全部` 时提交全局待识别图片。

## 识图上下文规则

- 每张图片会分别向前、向后读取上下文，默认目标字数分别是 `MESSAGE_IMAGE_CONTEXT_BEFORE_CHARS=100` 和 `MESSAGE_IMAGE_CONTEXT_AFTER_CHARS=100`。
- 图片后的发言会保留给这张图片作为后文上下文，直到批量提交、超时提交或命令立即提交。
- 上下文窗口会按真实聊天顺序合并去重，多张图片上下文重叠时不会重复塞给 AI。
- 单条消息不会截断；如果加入某条消息会让单侧上下文超过 600 字，则不加入该条。
- 如果上下文中已有 AI 图片总结，会使用数据库内的总结版本。

## 数据与缓存

插件使用 `nonebot-plugin-localstore` 管理图片识别相关缓存：

- `pending_images.json`：待识别图片任务账本。
- `image_cache/`：待识别图片缓存目录。

图片识别成功或失败后，任务会从 `pending_images.json` 中移除，对应缓存图片也会删除。

消息数据库默认不放在 localstore，而是放在 bot.py 同目录：

```text
qq_messages.db
```

如需自定义数据库位置，可以配置 `MESSAGE_DB_URL`。

## 兼容性

- Python 3.10+
- NoneBot2 2.3.0+
- OneBot v11 适配器
- SQLAlchemy 2.x
- aiosqlite
- nonebot-plugin-localstore

## License

本项目遵循仓库中的 LICENSE 文件。
