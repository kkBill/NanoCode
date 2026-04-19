# Message 类型重构计划

## Context

当前代码中，LLM 消息是纯 Python `dict`，在 6+ 个文件中被硬编码创建（`__main__.py`、`agent.py`、`context.py`、`subagent.py` 等）。这导致：
- 无类型安全：字段拼写错误只能在运行时由 OpenAI API 报错才发现
- 无 IDE 补全：无法享受静态分析和自动补全
- 不一致：自定义字段（如 `tool_name`、`reasoning_content`）是 ad-hoc 添加的
- 维护困难：消息结构变化时需要全局搜索替换

## Goal

使用 **Pydantic v2** 定义类型安全的 Message 类体系，统一所有消息创建和消费的路径，同时保持与 OpenAI SDK 的兼容性。

## Design

### 1. 新建 `nanocode/message.py`

定义 Message 类体系：

```python
class Message(BaseModel):
    role: str
    content: str
    def to_dict(self) -> dict[str, Any]: ...  # OpenAI API 格式（过滤自定义字段）
    @classmethod
    def from_dict(cls, data: dict) -> Message: ...  # 工厂方法，根据 role 分发

class SystemMessage(Message):
    role: Literal["system"] = "system"

class UserMessage(Message):
    role: Literal["user"] = "user"

class AssistantMessage(Message):
    role: Literal["assistant"] = "assistant"
    tool_calls: list[ToolCall] = Field(default_factory=list)
    reasoning_content: str = ""  # Kimi 自定义字段，to_dict() 中过滤

class ToolMessage(Message):
    role: Literal["tool"] = "tool"
    tool_call_id: str
    tool_name: str = ""  # 内部自定义字段，to_dict() 中过滤

class ToolCall(BaseModel): ...
class ToolCallFunction(BaseModel): ...
```

关键设计决策：
- `to_dict()`：生成 OpenAI SDK 兼容格式，**过滤掉** `tool_name` 和 `reasoning_content`
- `model_dump()`：保留所有字段，供 `debug_print_messages()` 使用
- `Message.from_dict(data)`：根据 `role` 字段分发到正确子类，用于兼容现有 dict 数据

### 2. 修改 `nanocode/llm/openai_client.py`

`chat()` 方法接收 `list[Message]`，内部在调用 OpenAI SDK 前通过 `to_dict()` 转换为 `list[dict]`：

```python
def chat(self, model: str, messages: list[Message], ...) -> ChatCompletion:
    dict_messages = [msg.to_dict() for msg in messages]
    return self.client.chat.completions.create(model=model, messages=dict_messages, ...)
```

### 3. 修改 `nanocode/__main__.py`

- 用 `SystemMessage(content=system_prompt)` 替代 `{"role": "system", ...}`
- 用 `UserMessage(content=query)` 替代 `{"role": "user", ...}`
- `history` 类型标注为 `list[Message]`

### 4. 修改 `nanocode/agent.py`

**所有 dict 构造替换为 Message 对象：**
- 背景/cron 结果注入 → `UserMessage` + `AssistantMessage`
- length 续写 → `AssistantMessage` + `UserMessage`
- tool call 助手消息 → `AssistantMessage`（含 `tool_calls` 和 `reasoning_content`）
- tool 执行结果 → `ToolMessage`（含 `tool_call_id` 和 `tool_name`）

**修复现有 bug：** `context_manager.compact()` 返回新列表，但 `agent_loop` 中 `messages` 被重新绑定后，`__main__.py` 的 `history` 仍指向旧列表，导致 compaction 后的消息在下一次循环中丢失。

修复方式：让 `compact_tool_calls()` 和 `compact()` **就地修改**传入的列表（`messages[:] = ...`），保留外部引用同步。

### 5. 修改 `nanocode/core/context.py`

- 函数签名改为接收 `list[Message]`，返回 `None`（就地修改）
- 用 `isinstance(msg, ToolMessage)` 替代 `msg.get("role") == "tool"`
- compaction 构造的新消息使用 Message 子类

### 6. 修改 `nanocode/tools/subagent.py`

- 所有 dict 构造替换为 Message 对象
- **重要**：当前代码直接调用 `client.chat.completions.create()`（OpenAI SDK 原生 API），需改为调用封装后的 `client.chat()` 方法
- 响应中的 `message.tool_calls` 解析为 `ToolCall` / `ToolCallFunction` 对象

### 7. 修改 `nanocode/utils.py`

`debug_print_messages()` 改为接收 `list[Message]`，使用 `model_dump()` 序列化（保留 `tool_name` 和 `reasoning_content` 用于调试）。

## Critical Files

| 文件 | 操作 | 说明 |
|------|------|------|
| `nanocode/message.py` | 新建 | Message 类体系定义 |
| `nanocode/llm/openai_client.py` | 修改 | chat() 接收 list[Message]，内部转 dict |
| `nanocode/__main__.py` | 修改 | 创建 SystemMessage/UserMessage |
| `nanocode/agent.py` | 修改 | 核心循环，所有消息构造 |
| `nanocode/core/context.py` | 修改 | compaction 逻辑，就地修改列表 |
| `nanocode/tools/subagent.py` | 修改 | 子 agent 循环 |
| `nanocode/utils.py` | 修改 | debug 函数适配 |

## Verification

1. **类型检查**：运行 `python -m py_compile nanocode/message.py` 确认无语法错误
2. **静态分析**：运行 `mypy nanocode/`（如有配置）确认类型注解一致
3. **功能测试**：启动 agent，执行一轮包含 tool call 的对话，确认：
   - 正常对话输出
   - tool call 正常执行并返回结果
   - 续写（length finish reason）场景正常工作
   - subagent 工具正常工作
   - debug 日志中消息序列化正常

-----
```
  修改文件

  ┌──────────────────────┬────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │         文件         │                                                改动                                                │
  ├──────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ llm/openai_client.py │ chat() 接收 list[Message]，内部通过 to_dict() 转 dict 后发给 OpenAI SDK                            │
  ├──────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ __main__.py          │ history 初始化为 list[Message]，使用 SystemMessage / UserMessage                                   │
  ├──────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ agent.py             │ 所有 dict 构造替换为 Message 对象；handle_tool_calls 构造 AssistantMessage（含 tool_calls +        │
  │                      │ reasoning_content）和 ToolMessage                                                                  │
  ├──────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ core/context.py      │ compact_tool_calls() 和 compact() 改为就地修改 messages[:] = ...，修复了之前 history 引用丢失的    │
  │                      │ bug；使用 isinstance(msg, ToolMessage) 替代 msg.get("role")                                        │
  ├──────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ tools/subagent.py    │ 所有 dict 构造替换为 Message 对象；将直接调用 client.chat.completions.create() 改为调用封装后的    │
  │                      │ client.chat()                                                                                      │
  ├──────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ utils.py             │ debug_print_messages() 通过 model_dump() 序列化 Message 对象（保留 tool_name / reasoning_content   │
  │                      │ 用于调试）                                                                                         │
  └──────────────────────┴────────────────────────────────────────────────────────────────────────────────────────────────────┘

  关键设计

  - to_dict() — 生成 OpenAI SDK 兼容格式，过滤掉自定义字段 tool_name 和 reasoning_content
  - model_dump() — 保留全部字段，供调试使用
  - Message.from_dict(data) — 工厂方法，根据 role 分发到正确子类
```