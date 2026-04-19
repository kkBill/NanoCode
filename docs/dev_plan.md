### 04.18 周六
- [ ] API KEY 整改，归一  | ~  completed
- [ ] 日志整改，print -> logger | ~  completed
- [ ] workdir 整改，调整为 ~/.nanocode/，统一各个模块的路径 | ~  completed
- [ ] 更新 Python 依赖，换成 uv | ~  completed
- [ ] tool call schema统一
- [ ] tool call 注册逻辑
- [ ] tool call - task 重构

----
- typing库的用法：typing 是 Python 的标准库，为动态类型的 Python 增加了静态类型注解的能力。它的核心作用是让代码的自文档性更强、IDE 自动补全更准、并在运行前通过类型检查器（如mypy、pyright）捕获类型错误。

  以下是实现 Tool System 时会用到的关键特性：

  ---
  1. 基础类型注解

  def greet(name: str) -> str:
      return f"Hello, {name}"

  name: str 声明参数类型，-> str 声明返回类型。运行时不强制，但 IDE 和类型检查器会据此分析。

  ---
  2. Union / | —— 多类型

  一个值可能是多种类型之一：

  from typing import Union

  # 旧写法
  def parse(data: Union[str, bytes]) -> dict: ...

  # Python 3.10+ 新写法（推荐）
  def parse(data: str | bytes) -> dict: ...

  在方案中大量使用，如 content: str | list[dict]、PermissionDecision = PermissionAllowDecision | PermissionAskDecision | PermissionDenyDecision。

  ---
  3. Optional —— 可能为 None

  from typing import Optional

  # 旧写法
  def find(name: str) -> Optional[Tool]: ...

  # Python 3.10+ 新写法（推荐）
  def find(name: str) -> Tool | None: ...

  Tool | None 明确表示"返回一个 Tool，或者找不到返回 None"。

  ---
  4. Generic / TypeVar —— 泛型

  让类/函数支持"参数化类型"，类似 TypeScript 的 <Input, Output>：

  from typing import Generic, TypeVar

  InputT = TypeVar("InputT", bound=BaseModel)  # InputT 必须是 BaseModel 的子类
  OutputT = TypeVar("OutputT")                 # OutputT 可以是任意类型

  class ToolResult(Generic[OutputT]):
      data: OutputT  # 泛型字段：具体类型在实例化时确定

  # 使用
  text_result: ToolResult[str] = ToolResult(data="hello")
  image_result: ToolResult[ImageOutput] = ToolResult(data=ImageOutput(...))

  bound=BaseModel 约束了类型参数必须是某个基类的子类。

  ---
  5. Callable —— 函数类型

  描述"接受什么参数、返回什么"的函数签名：

  from typing import Callable, Awaitable

  # 同步函数：无参数，返回 dict
  GetAppState = Callable[[], dict]

  # 异步函数：一个参数，返回 PermissionDecision
  CanUseToolFn = Callable[[InputT, ToolUseContext], Awaitable[PermissionDecision]]

  # 回调函数：接收 ToolProgress，返回 None
  ToolCallProgress = Callable[[ToolProgress], None]

  ---
  6. Literal —— 字面量类型

  限制值必须是几个固定的字面量之一：

  from typing import Literal

  PermissionMode = Literal["default", "acceptEdits", "bypassPermissions", "dontAsk", "plan"]

  def set_mode(mode: PermissionMode) -> None: ...

  set_mode("default")   # ✓
  set_mode("plan")      # ✓
  set_mode("admin")     # ✗ 类型检查器报错

  ---
  7. Protocol —— 结构化子类型（鸭子类型）

  不通过继承，而是通过"实现了哪些方法"来判断类型：

  from typing import Protocol

  class Tool(Protocol):
      name: str
      async def call(self, args: dict) -> ToolResult: ...

  # 任何实现了 name 和 call() 的类，都被视为 Tool，无需显式继承
  class FileReadTool:
      name = "FileRead"
      async def call(self, args: dict) -> ToolResult: ...

  这在方案中用于定义 Tool 接口，让 build_tool 返回的对象天然满足该协议。

  ---
  8. Any —— 任意类型

  当类型无法确定或需要动态性时使用：

  from typing import Any

  def log(data: Any) -> None: ...

  应谨慎使用，过多 Any 会失去类型检查的意义。

  ---
  9. list[Tool] 等内置泛型（Python 3.9+）

  # Python 3.9+ 可以直接用内置类型作为泛型
  tools: list[Tool]
  mapping: dict[str, int]
  pairs: tuple[str, int, bool]

  # 旧写法（3.8 及以下）
  from typing import List, Dict, Tuple
  tools: List[Tool]

  方案中统一使用 list[Tool]、dict[str, Any] 等新写法。

  ---
  10. TypeAlias —— 类型别名

  from typing import TypeAlias

  # 给一个复杂类型起别名
  PermissionDecision: TypeAlias = (
      PermissionAllowDecision | PermissionAskDecision | PermissionDenyDecision
  )

  提升可读性，尤其在联合类型复杂时。

  ---
  一句话总结

  typing 让 Python 在保持动态运行时灵活性的同时，获得了静态类型系统的工程化能力。Tool System 方案中大量使用 Generic + TypeVar 实现泛型工具接口、Protocol
  定义鸭子类型、Literal 约束固定值、Callable 描述回调签名、| 表达联合类型——这些都是现代 Python 类型编程的核心工具。

- pydantic库的用法：pydantic 是 Python 生态中最流行的数据验证与序列化库。它的核心哲学是：用类型注解声明数据结构，让 pydantic 自动完成校验、转换和序列化。在 Tool System方案中，它负责所有输入输出类型的定义和运行时校验。在 Tool System 中，ToolUseContext 等内部结构可用 dataclasses，但所有与模型交互的输入输出类型（FileReadInput、FileReadOutput、Message）都用 BaseModel，因为它们是系统边界，需要严格的校验和序列化。


  1. 核心：BaseModel

  from pydantic import BaseModel

  class FileReadInput(BaseModel):
      file_path: str
      offset: int | None = None
      limit: int | None = None

  一旦继承 BaseModel，这个类就获得了自动校验能力：

  # ✓ 合法输入
  valid = FileReadInput(file_path="/tmp/test.py", offset=1)

  # ✗ 类型不匹配 —— 运行时抛出 ValidationError
  invalid = FileReadInput(file_path=123, offset="abc")

  ---
  2. Field：字段描述与约束

  from pydantic import BaseModel, Field

  class FileReadInput(BaseModel):
      file_path: str = Field(description="The absolute path to the file to read")
      offset: int | None = Field(
          default=None,
          description="The line number to start reading from",
          ge=0,  # 必须 >= 0
      )
      limit: int | None = Field(
          default=None,
          description="The number of lines to read",
          gt=0,  # 必须 > 0
      )

  Field() 用于提供：
  - 默认值（default=None）
  - 描述信息（description，在 JSON Schema 中可见）
  - 数值约束（ge, gt, le, lt, min_length, max_length 等）
  - 是否必填（默认不设置 default 即为必填）

  这在 Tool System 中非常关键——工具的 input_schema 最终会被转换为 JSON Schema 发送给 LLM，description 就是模型的"使用说明书"。

  ---
  3. 数据解析：model_validate

  从字典/JSON 创建模型实例：

  raw = {"file_path": "/tmp/test.py", "offset": 10}

  # 解析字典
  input_obj = FileReadInput.model_validate(raw)

  # 解析 JSON 字符串
  json_str = '{"file_path": "/tmp/test.py"}'
  input_obj = FileReadInput.model_validate_json(json_str)

  自动类型转换（在合理范围内）：
  # offset 传入字符串 "10"，pydantic 会自动转为整数 10
  input_obj = FileReadInput.model_validate({"file_path": "/tmp/a.py", "offset": "10"})
  print(input_obj.offset)  # 10 (int)

  这正是 executor.py 中处理模型返回的 tool_use.input 的方式：
  parsed_input = tool.input_schema.model_validate(tool_use.input)

  ---
  4. 序列化：model_dump

  将模型实例转回字典或 JSON：

  input_obj = FileReadInput(file_path="/tmp/test.py", offset=10)

  # 转字典
  print(input_obj.model_dump())
  # {'file_path': '/tmp/test.py', 'offset': 10, 'limit': None}

  # 转 JSON 字符串
  print(input_obj.model_dump_json())
  # '{"file_path":"/tmp/test.py","offset":10,"limit":null}'

  # 排除 None 字段
  print(input_obj.model_dump(exclude_none=True))
  # {'file_path': '/tmp/test.py', 'offset': 10}

  ---
  5. Union / Literal 与 Pydantic

  Pydantic 完美支持 typing 的高级类型：

  from typing import Literal
  from pydantic import BaseModel

  class TextOutput(BaseModel):
      type: Literal["text"] = "text"
      content: str

  class ImageOutput(BaseModel):
      type: Literal["image"] = "image"
      base64: str

  class ToolResult(BaseModel):
      # 根据 type 字段的值自动路由到正确模型
      output: TextOutput | ImageOutput

  # 自动识别为 TextOutput
  result = ToolResult(output={"type": "text", "content": "hello"})

  # 自动识别为 ImageOutput
  result = ToolResult(output={"type": "image", "base64": "iVBORw0..."})

  在方案中 FileReadOutput = FileReadOutputText | FileReadOutputImage 就是这种模式。

  ---
  6. 自定义校验器：@field_validator

  当内置约束不够时，可写自定义校验逻辑：

  from pydantic import BaseModel, field_validator

  class FileReadInput(BaseModel):
      file_path: str
      pages: str | None = None

      @field_validator("pages")
      @classmethod
      def validate_pages(cls, v: str | None) -> str | None:
          if v is None:
              return v
          # 校验 PDF 页码格式，如 "1-5", "3"
          import re
          if not re.match(r"^\d+(-\d+)?$", v):
              raise ValueError(f'Invalid pages format: "{v}"')
          return v

  # ✗ 抛出 ValidationError
  FileReadInput(file_path="/tmp/a.pdf", pages="abc")

