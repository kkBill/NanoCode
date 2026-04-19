# NanoCode Agent 测试与验证体系建设计划

## Context

NanoCode Agent 目前支持 14 种工具（bash、file IO、sub-agent、task、background task、cron、memory 等），核心交互逻辑位于 `nanocode/agent.py` 的 `agent_loop()` 中。当前项目**完全没有测试基础设施**（`tests/` 目录仅有一个 `.gitkeep`），验证任何功能（尤其是涉及多轮 tool_calls 的复杂场景）都依赖开发者与 Agent 进行多轮真实对话，再人工观察日志判断行为是否符合预期。这种验证方式效率极低、不可复现、无法回归，严重拖慢开发迭代。

本计划旨在引入一套业界验证过的分层测试体系，将复杂场景的验证从"人工对话+读日志"转变为"自动场景定义+一键执行+断言报告"。

---

## 业界常见解决办法调研总结

通过对 Braintrust、Anthropic、DeepEval、Promptfoo 等主流框架和工程实践的调研，业界针对 LLM Agent 的测试验证已形成以下共识：

| 方法 | 说明 | 适用场景 |
|------|------|---------|
| **分层测试** | 组件级（单个 tool）→ 集成级（agent_loop）→ 端到端场景（多轮交互） | 所有 Agent 项目的基础 |
| **Mock LLM + 预设轨迹** | 用 Mock 客户端替代真实 LLM，按预设序列返回 tool_calls / content，精确控制测试路径 | 验证 agent_loop 的分支逻辑、多轮工具调用顺序 |
| **场景定义文件** | 用 YAML/JSON 定义"用户输入 + 期望 LLM 响应序列 + 断言条件" | 将复杂人工对话场景转化为可复现的自动化测试用例 |
| **执行追踪（Tracing）** | 保存完整 message history（含 tool_calls 和 reasoning_content） | 事后分析、故障定位、轨迹回放做回归对比 |
| **确定性断言 + LLM-as-Judge** | 对 tool 参数、调用顺序用代码断言；对开放式回复质量用 LLM 评分 | 兼顾精确性和灵活性 |
| **回归测试套件** | 将场景测试集成到 CI，每次代码变更自动运行全量场景 | 防止重构引入行为退化 |

**关键洞察**：对于以"工具调用"为核心的 Agent（如 NanoCode），最有效的突破点是 **Mock LLM + 场景定义**——它直接消除了"多轮真实对话"的瓶颈，让复杂交互路径可以在毫秒级完成验证。

---

## 参考来源（References）

### 1. 分层测试与评估框架总览

- **Braintrust — AI Agent Evaluation: A Practical Framework for Testing Multi-Step Agents**
  <br>提出了多支柱评估模型（LLM / Memory / Tools / Environment）和三种评估模式（静态分析、动态测试、Judge-based）。是本文"分层测试"和"Swiss Cheese"验证方法的主要参考。
  <br>https://www.braintrust.dev/articles/ai-agent-evaluation-framework

- **Anthropic — Demystifying Evals for AI Agents**
  <br>Anthropic 官方工程博客，强调评估 Agent 需要同时关注最终输出质量和中间执行轨迹（trajectory），建议使用自动化 evals + 生产监控 + A/B 测试 + 人工校准的组合。是"确定性断言 + LLM-as-Judge"双轨策略的主要来源。
  <br>https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents

- **Databricks — What is AI Agent Evaluation?**
  <br>系统介绍了 Agent 评估的四个阶段（组件级 → 集成级 → 控制场景 → 生产监控），并强调 tracing 是定位工具调用失败和检索层问题的关键基础设施。
  <br>https://www.databricks.com/blog/what-is-agent-evaluation

- **Maxim AI — Exploring Effective Testing Frameworks for AI Agents in Real-World Scenarios**
  <br>对比了当前主流测试框架在真实场景下的适用性，提出测试用例应覆盖 happy-path、edge cases、adversarial cases、off-topic cases 四类。
  <br>https://www.getmaxim.ai/articles/exploring-effective-testing-frameworks-for-ai-agents-in-real-world-scenarios/

### 2. 学术评估框架与指标设计

- **An Assessment Framework for Evaluating Agentic AI Systems (arXiv:2512.12791)**
  <br>2025 年 12 月的学术综述，提出 Agent 系统评估的四大支柱（LLM、Memory、Tools、Environment）和静态/动态/Judge-based 三种评估模式。是"分层测试"方法论的理论支撑。
  <br>https://arxiv.org/html/2512.12791v1

- **ToolSafe: Enhancing Tool Invocation Safety of LLM-based Agents via Proactive Step-level Guardrail and Feedback (arXiv:2601.10156)**
  <br>专注于 LLM Agent 的工具调用安全性验证，提出 step-level guardrail 机制，对本文"工具参数正确性"和"权限拒绝场景"的测试设计有参考价值。
  <br>https://arxiv.org/abs/2601.10156

- **Evaluating Implicit Regulatory Compliance in LLM Tool Invocation via Logic-Guided Synthesis (arXiv:2601.08196)**
  <br>通过逻辑引导合成方法评估 LLM 工具调用的合规性，为复杂场景下工具调用序列的验证提供了形式化思路。
  <br>https://arxiv.org/html/2601.08196v1

- **Sequential Agent Validation Framework**
  <br>提出顺序化 Agent 验证流水线（实验设计 → 执行控制 → 标准生成 → 裁决生成），与本文"场景定义文件 + 场景运行器"的思路高度一致。
  <br>https://www.emergentmind.com/topics/sequential-agent-validation-framework

### 3. 开源工具对比与回归测试实践

- **Promptfoo 官方文档 — Introduction**
  <br>CLI-first 的 LLM 测试框架，核心能力包括多模型回归测试、缓存、并发执行、red-teaming 扫描。支持暴露 tool call metadata 供验证。
  <br>https://www.promptfoo.dev/docs/intro/

- **DeepEval 官方文档 — Alternatives Compared**
  <br>Python-native 的 pytest 风格评估框架，提供 50+ 内置指标（含 `ToolUseMetric`、任务完成度、步骤效率评分），原生支持 Agent 和工具调用验证。与 pytest 直接集成，适合 Python 项目 CI。
  <br>https://docs.confident-ai.com/blog/deepeval-alternatives-compared
  <br>https://deepeval.com/blog/deepeval-alternatives-compared

- **RAGAS vs DeepEval vs Promptfoo — LLM Evaluation Framework Comparison**
  <br>三个主流开源框架的横向对比，明确 DeepEval 在"Agent 专用指标"和"Python 原生"方面的优势，Promptfoo 在"CLI 回归测试"和"red-teaming"方面的优势。
  <br>https://aicoolies.com/comparisons/ragas-vs-deepeval-vs-promptfoo

- **DeepEval vs Promptfoo — Pytest-Style LLM Testing vs CLI-First Evaluation Framework**
  <br>更详细的对比分析，指出 DeepEval 适合"multi-step agent tool use"的深度验证，Promptfoo 适合"rapid multi-model prompt comparison"。是本文"阶段 5 评估框架对接"建议选用 DeepEval 的主要依据。
  <br>https://aicoolies.com/comparisons/deepeval-vs-promptfoo

- **Top 5 AI Agent Eval Tools After Promptfoo's Exit**
  <br>2025-2026 年社区讨论，总结 Promptfoo 被收购后的替代方案，再次确认 DeepEval、Braintrust、Arize Phoenix 作为独立开源/企业方案的可行性。
  <br>https://dev.to/nebulagg/top-5-ai-agent-eval-tools-after-promptfoos-exit-576i

### 4. 自动化测试与持续集成

- **mabl — AI Agent Frameworks for End-to-End Test Automation**
  <br>探讨 AI Agent 在端到端测试自动化中的应用趋势，包括自适应执行、自愈测试（self-healing）和上下文感知断言。
  <br>https://www.mabl.com/blog/ai-agent-frameworks-end-to-end-test-automation

- **PractiTest — AI Agent Testing: Automate, Analyze and Optimize QA**
  <br>从 QA 工程角度总结 AI Agent 测试的最佳实践，强调测试用例生成、失败分析自动化和持续监控。
  <br>https://www.practitest.com/resource-center/blog/ai-agent-testing-automate-analyze-optimize/

---

## 推荐方案：分阶段建设测试体系

### 阶段 1：测试基础设施 + 工具单元测试

**目标**：让每个工具的 `execute()` 方法都有独立、快速的单元测试。

**关键动作**：
1. 在 `pyproject.toml` 中添加 `pytest` 测试依赖。
2. 创建 `tests/conftest.py`，配置共享 fixture（如临时工作目录、mock 环境变量）。
3. 为每个 tool 编写单元测试：
   - `Bash`：验证正常命令执行、超时处理、`rm -rf /` 等危险命令拦截。
   - `ReadFile` / `WriteFile`：验证路径限制在 `WORK_DIR` 内、编码处理。
   - `SubAgent`：mock `OpenAIClient`，验证子代理循环最多 5 轮、正确排除 `sub_agent` 工具。
   - `CreateTask` / `UpdateTask` 等：验证 task 状态流转和依赖关系。
   - `CreateCron` / `DeleteCron`：验证 cron 表达式解析和调度器状态变更。

**复用现有代码**：所有 tool 都继承自 `nanocode/tools/base.py` 的 `Tool` 基类，可以利用其统一接口批量测试 `name()` / `description()` / `schema()` 的合规性。

---

### 阶段 2：Agent Loop 集成测试（核心突破）

**目标**：验证 `agent_loop()` 的核心分支逻辑和多轮交互行为，**不依赖真实 LLM**。

**关键动作**：
1. **创建 `MockOpenAIClient`**（`tests/mocks.py`）：
   - 继承或模拟 `OpenAIClient` 的 `chat()` 方法。
   - 支持按队列顺序返回预设的 `ChatCompletion` 响应（模拟 `finish_reason=tool_calls`、`length`、`stop`、`error` 等）。
   - 支持断言实际传入的 `messages` 和 `tools` 是否符合预期（验证 context compaction、background results 注入等）。
2. **编写 `agent_loop` 集成测试**：
   - **单轮 tool_call**：验证 LLM 返回 `tool_calls` → 执行工具 → 结果追加到 messages → 再次调用 LLM。
   - **多轮 tool_call 链**：模拟"读文件 → 分析内容 → 写文件"的三轮交互，验证消息历史正确累积。
   - **`length` 续写**：模拟 `finish_reason=length` 两次后 `stop`，验证续写计数器和提示注入。
   - **背景任务结果注入**：模拟后台任务完成，验证其结果自动插入 messages。
   - **Cron 通知注入**：模拟 cron 触发，验证通知插入 messages。
   - **异常处理**：模拟 LLM 返回空 response、未知 finish_reason，验证不崩溃。
3. **通过依赖注入或 monkeypatch** 将 `agent_loop` 中的 `OpenAIClient` 替换为 `MockOpenAIClient`。

**关键文件**：
- `nanocode/agent.py`（被测主体）
- `nanocode/llm/openai_client.py`（Mock 目标）

---

### 阶段 3：场景化端到端测试（解决核心痛点）

**目标**：让开发者可以用**声明式场景文件**定义复杂测试用例，一键运行并生成报告，彻底替代"人工多轮对话+看日志"。

**关键动作**：
1. **定义场景文件格式**（YAML，存于 `tests/scenarios/`）：
   ```yaml
   name: "文件读写链式场景"
   description: "验证 Agent 能先读文件、再基于内容写新文件"
   input: "请读取 workspace/old.txt，将其内容转为大写后写入 workspace/new.txt"
   mock_llm_sequence:
     - role: assistant
       finish_reason: tool_calls
       tool_calls:
         - name: read_file
           arguments: '{"file_path": "workspace/old.txt"}'
     - role: assistant
       finish_reason: tool_calls
       tool_calls:
         - name: write_file
           arguments: '{"file_path": "workspace/new.txt", "content": "HELLO"}'
     - role: assistant
       finish_reason: stop
       content: "已完成文件转换。"
   assertions:
     - type: tool_called
       tool: read_file
       args: {"file_path": "workspace/old.txt"}
     - type: tool_called
       tool: write_file
       args: {"file_path": "workspace/new.txt", "content": "HELLO"}
     - type: final_content_contains
       value: "已完成"
     - type: file_exists
       path: "workspace/new.txt"
       content: "HELLO"
   ```
2. **编写场景运行器**（`tests/scenario_runner.py`）：
   - 加载 YAML 场景。
   - 初始化临时工作目录和 Mock LLM Client。
   - 执行 `agent_loop([{"role": "user", "content": input}])`。
   - 按 `assertions` 列表逐一验证，收集通过/失败结果。
   - 输出结构化报告（含失败原因和实际调用序列）。
3. **预置高价值场景**：
   - `sub_agent_spawn.yml`：验证主 Agent 调用 `sub_agent`，子 Agent 内部再调用 `read_file`。
   - `task_lifecycle.yml`：验证创建 task → 更新状态 → 查询 task 的完整流程。
   - `background_task.yml`：验证 `run_background_task` + `check_background_task` 的组合。
   - `cron_scheduler.yml`：验证 `create_cron` 后调度器正确注册。
   - `context_compaction.yml`：注入超长 messages，验证 context_manager 正确压缩。
   - `permission_denied.yml`：模拟权限拒绝（待权限系统重构后激活），验证 Agent 能调整策略。

**预期效果**：新增一个复杂场景的验证成本从"10分钟多轮对话+读日志"降低到"写30行 YAML + 运行2秒"。

---

### 阶段 4：回归测试与轨迹回放

**目标**：捕获真实运行轨迹，用于后续回归对比；将场景测试接入持续集成。

**关键动作**：
1. **可选的轨迹保存模式**：在 `agent_loop` 中增加环境变量开关（如 `NANOCODE_TRACE_DIR`），将完整 `messages` 历史（含 reasoning_content、tool_calls、tool results）保存为 JSONL 文件。
2. **轨迹回放工具**（`tests/trace_replayer.py`）：
   - 读取保存的轨迹文件。
   - 提取其中的 LLM 响应序列，构造 MockOpenAIClient。
   - 重放交互，对比新的输出是否与历史一致（或预期内的变化）。
3. **接入 CI**：
   - 在 `pyproject.toml` 中配置 `pytest` 的测试入口。
   - 添加 GitHub Actions / GitLab CI 工作流（如项目后续使用），在 PR 时自动运行 `pytest tests/` 和场景测试。
4. **性能基准**：记录关键场景的运行耗时（尤其是 context compaction 前后），防止性能回归。

---

### 阶段 5：评估框架对接（长期可选）

**目标**：对开放式、难以用确定性断言评估的场景，引入 LLM-as-Judge。

**关键动作**：
1. 调研并引入 **DeepEval**（Python 原生，支持 `ToolUseMetric`、`TaskCompletionMetric`，与 pytest 集成）。
2. 对需要"判断回答质量"的场景，使用 DeepEval 的指标替代部分硬编码断言。
3. 保持核心场景测试不依赖外部 LLM（低成本、高稳定性），仅对质量评估场景启用 LLM-as-Judge。

---

## 与现有开发计划的衔接

当前 `docs/dev_plan.md` 列出的正在进行的工作：
- `tool call schema 统一` → 完成后，可以用统一的方法批量验证所有 tool 的 schema 合规性（单元测试中遍历 `registry`）。
- `tool call 注册逻辑` → 完成后，Mock 场景可以更方便地注入/替换工具。
- `tool call - task 重构` → 重构后应立即补充 task 相关的场景测试，防止再次退化。

**建议**：在 schema 统一和注册逻辑重构**完成后**，立即启动本计划的阶段 1 和阶段 2（因为此时工具接口稳定，测试编写成本最低）。

---

## 验证方式

1. **工具单元测试**：`pytest tests/tools/ -v` 应全部通过。
2. **Agent Loop 集成测试**：`pytest tests/test_agent_loop.py -v` 应覆盖 `finish_reason` 的所有分支。
3. **场景测试**：`pytest tests/scenarios/ -v` 或 `python -m tests.scenario_runner` 应运行所有 YAML 场景并生成报告。
4. **端到端验证**：手动运行一个包含 sub-agent + task + background task 的复杂场景 YAML，确认运行时间 < 5 秒且断言全部通过。
5. **回归验证**：修改 `agent_loop` 某处逻辑后重新运行场景测试，确认失败用例能精准定位行为变化。

---

## 关键文件清单

| 文件/目录 | 说明 |
|-----------|------|
| `pyproject.toml` | 添加 pytest 依赖和测试配置 |
| `tests/conftest.py` | pytest 共享 fixture |
| `tests/mocks.py` | `MockOpenAIClient` 等 Mock 实现 |
| `tests/tools/test_*.py` | 各 tool 的单元测试 |
| `tests/test_agent_loop.py` | Agent Loop 集成测试 |
| `tests/scenario_runner.py` | 场景 YAML 解析与运行器 |
| `tests/scenarios/*.yml` | 声明式端到端测试场景 |
| `tests/trace_replayer.py` | 轨迹回放工具 |
| `nanocode/agent.py` | 被测主体（需支持依赖注入或 monkeypatch） |
| `nanocode/llm/openai_client.py` | Mock 目标 |
| `nanocode/tools/base.py` | Tool 基类（批量 schema 验证） |
