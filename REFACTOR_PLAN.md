# Nanobot LangChain 重构计划

## 一、重构推荐总览

| 优先级 | 模块 | 推荐程度 | 收益 |
|--------|------|---------|------|
| 1 | Agent Loop + Sub-agent → LangGraph StateGraph | ⭐⭐⭐⭐⭐ | 声明式图替代400行手动 ReAct 循环 |
| 2 | Tools 层 → LangChain @tool | ⭐⭐⭐⭐ | 代码量减少50%+，类型安全 |
| 3 | Memory → LangGraph Checkpointing | ⭐⭐⭐⭐ | 自动持久化、断点恢复 |
| 4 | Context Builder → ChatPromptTemplate | ⭐⭐⭐ | 可选，当前实现已够好 |
| - | Providers / Channels / Bus / Config | 不推荐 | 保留现有实现 |

---

## 二、测试验证清单

### 重构 Loop 时必须通过的测试

```bash
pytest tests/test_task_cancel.py tests/test_message_tool_suppress.py tests/test_loop_save_turn.py tests/test_loop_consolidation_tokens.py tests/test_restart_command.py tests/test_consolidate_offset.py tests/test_memory_consolidation_types.py tests/test_context_prompt_cache.py tests/test_evaluator.py
```

| 测试文件 | 测试数 | 覆盖内容 |
|----------|--------|---------|
| test_task_cancel.py | 8 | _handle_stop 取消、_dispatch 发布、_processing_lock 串行、SubagentManager |
| test_message_tool_suppress.py | 6 | message tool 抑制回复、on_progress 隐藏 reasoning |
| test_loop_save_turn.py | 3 | _save_turn 跳过 runtime context、图片占位、工具结果截断 |
| test_loop_consolidation_tokens.py | 6 | token 阈值触发整合、user boundary 归档、preflight 在 LLM 前 |
| test_restart_command.py | 3 | /restart 处理、run loop 拦截、/help 包含 restart |
| test_consolidate_offset.py | ~40 | Session last_consolidated、消息切片、/new 归档 |
| test_memory_consolidation_types.py | 14 | MemoryStore.consolidate 各种边界 |
| test_context_prompt_cache.py | 3 | system prompt 稳定性、runtime context 注入 |
| test_evaluator.py | 4 | evaluate_response 通知判断 |

### 重构 Tools 时必须通过的测试

```bash
pytest tests/test_filesystem_tools.py tests/test_tool_validation.py tests/test_web_search_tool.py tests/test_mcp_tool.py tests/test_message_tool.py tests/test_message_tool_suppress.py tests/test_task_cancel.py tests/test_cron_service.py
```

| 测试文件 | 测试数 | 覆盖内容 |
|----------|--------|---------|
| test_filesystem_tools.py | ~18 | ReadFile/EditFile/ListDir 全部行为 |
| test_tool_validation.py | ~30 | validate_params/cast_params/ExecTool 安全 |
| test_web_search_tool.py | 10 | WebSearchTool 多 provider + 回退 |
| test_mcp_tool.py | 10 | MCPToolWrapper + connect_mcp_servers |
| test_message_tool.py | ? | MessageTool 消息发送 |
| test_message_tool_suppress.py | 6 | MessageTool 与 Loop 协作 |
| test_task_cancel.py | 8 | 通过 ToolRegistry.execute 调用工具 |
| test_cron_service.py | 3 | CronService 基础行为 |

---

## 三、Phase 1 Prompt — 用 LangGraph 重构 Agent Loop

```
# 任务：用 LangGraph 重构 nanobot Agent Loop

## 背景
nanobot 是一个轻量级 AI 助手框架，当前在 `nanobot/agent/loop.py` 中手动实现了 ReAct 循环。
我希望用 LangGraph 的 StateGraph 替代手动循环，同时保持与现有系统（MessageBus、Channels、Config）的兼容。

## 当前架构
- `nanobot/agent/loop.py` — AgentLoop 类，核心方法 `_run_agent_loop()`：
  - 循环最多 `max_iterations` 次
  - 每轮：调用 `provider.chat_with_retry()` → 检查 tool_calls → 执行工具 → 追加结果 → 下一轮
  - 支持 on_progress 回调（流式推送思考过程和工具调用状态）
  - 通过 `_processing_lock` 保证串行处理
  - 支持 `/stop` 取消当前任务
- `nanobot/agent/subagent.py` — SubagentManager，spawn 子 agent 执行后台任务
- `nanobot/agent/tools/registry.py` — ToolRegistry，统一注册和执行工具
- `nanobot/providers/base.py` — LLMProvider 抽象基类，返回 LLMResponse(content, tool_calls, ...)
- `nanobot/bus/events.py` — InboundMessage / OutboundMessage
- `nanobot/bus/queue.py` — MessageBus

## 重构要求

### 1. 创建 LangGraph StateGraph
- 定义 `AgentState` TypedDict，包含：messages, tool_calls, iteration_count, should_stop 等
- 创建包含以下节点的图：
  - `call_llm` — 调用 LLM provider
  - `execute_tools` — 执行工具调用
  - `check_completion` — 检查是否完成（无 tool_calls 或达到 max_iterations）
- 使用条件边连接节点

### 2. 保持兼容性
- **不要替换 LLMProvider**：继续使用现有的 `nanobot.providers.base.LLMProvider`，不要引入 LangChain 的 ChatModel
  - 如果需要桥接，创建一个 wrapper 将 `LLMProvider` 适配为 LangChain 的 `BaseChatModel`
  - 或者直接在 LangGraph 节点中调用 `provider.chat_with_retry()`
- **不要替换 ToolRegistry**：在 LangGraph 的工具执行节点中调用现有的 `ToolRegistry.execute()`
- **保留 MessageBus 集成**：`AgentLoop.run()` 仍然从 bus 消费消息并发布结果
- **保留 on_progress 回调**：在图节点中发送进度更新

### 3. Sub-agent 用 LangGraph 子图实现
- 将 `SubagentManager.spawn()` 改为启动一个 LangGraph 子图
- 子图使用精简工具集（与当前行为一致）
- 完成后通过 InboundMessage 通知主 agent

### 4. 保留的功能
- `/stop` 取消支持（通过 `should_stop` state flag + asyncio.Task.cancel()）
- 工具结果截断（`_TOOL_RESULT_MAX_CHARS = 16_000`）
- 内存整合触发（`MemoryConsolidator.maybe_consolidate_by_tokens()`）
- MCP 懒加载连接

### 5. 文件结构建议

nanobot/agent/
├── graph.py          # LangGraph StateGraph 定义
├── state.py          # AgentState 类型定义
├── nodes.py          # 各节点实现（call_llm, execute_tools, etc.）
├── loop.py           # 保留 AgentLoop 作为入口，内部使用 graph
├── subagent.py       # 用子图重构
├── context.py        # 保留不变
├── memory.py         # 保留不变
└── tools/            # 保留不变

## 测试验证
重构完成后，以下测试必须全部通过：

pytest tests/test_task_cancel.py tests/test_message_tool_suppress.py tests/test_loop_save_turn.py tests/test_loop_consolidation_tokens.py tests/test_restart_command.py tests/test_consolidate_offset.py tests/test_memory_consolidation_types.py tests/test_context_prompt_cache.py tests/test_evaluator.py

## 依赖
- 已安装：`langgraph>=1.1.2`（见 pyproject.toml）
- LLM 桥接：优先通过直接调用 `provider.chat_with_retry()` 在节点内实现，避免引入额外依赖

## 参考代码路径
- Agent Loop: nanobot/agent/loop.py（特别关注 `_run_agent_loop()` 方法）
- Sub-agent: nanobot/agent/subagent.py
- Tool Registry: nanobot/agent/tools/registry.py
- Provider Base: nanobot/providers/base.py
- Bus Events: nanobot/bus/events.py
- Session Manager: nanobot/session/manager.py

## 注意事项
- 这是渐进式重构的第一步，后续会重构 Tools 和 Memory
- 不要修改 providers/、channels/、bus/、config/ 目录
- 代码风格：ruff，line-length=100，target Python 3.11+
```

---

## 四、Phase 2 Prompt — 用 LangChain @tool 重构工具层

```
# 任务：用 LangChain @tool 装饰器重构 nanobot 工具层

## 背景
nanobot 的工具层在 `nanobot/agent/tools/` 中，使用自定义的 `Tool` 抽象基类。
每个工具需要手动定义 `name`、`description`、`parameters`（JSON Schema）和 `execute()` 方法。
我希望用 LangChain 的 `@tool` 装饰器简化工具定义，同时保持工具的全部功能。

## 当前架构
- `nanobot/agent/tools/base.py` — Tool 抽象基类：
  - `name`、`description`、`parameters` 属性
  - `execute(**kwargs)` 异步抽象方法
  - `cast_params()` — 根据 JSON Schema 转换参数类型
  - `validate_params()` — 校验参数
  - `to_schema()` — 转为 OpenAI function calling 格式
- `nanobot/agent/tools/registry.py` — ToolRegistry：
  - `register(tool)` / `unregister(name)`
  - `get_definitions()` — 返回所有工具的 OpenAI 格式定义
  - `execute(name, params)` — 执行工具，内部做类型转换和校验

### 现有工具列表
1. **filesystem.py**: ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
   - 继承 `_FsTool`，共享 `_resolve_path()` 和 `allowed_dir` 路径限制
2. **shell.py**: ExecTool
   - deny_patterns 安全规则、超时、输出截断
3. **web.py**: WebSearchTool, WebFetchTool
   - 多搜索 provider、URL 抓取
4. **message.py**: MessageTool
   - 需要运行时 context（channel, chat_id）通过 `set_context()` 注入
5. **spawn.py**: SpawnTool
   - 需要运行时 SubagentManager 引用
6. **cron.py**: CronTool
   - 需要运行时 CronService 引用
7. **mcp.py**: MCPToolWrapper
   - 动态包装 MCP 远程工具

## 重构要求

### 1. 用 LangChain @tool 或 StructuredTool 替代
- 简单工具（无状态）：使用 `@tool` 装饰器 + Pydantic 参数模型
- 有状态工具（需要 context 注入的，如 MessageTool、SpawnTool、CronTool）：
  使用 `StructuredTool` 或带闭包的 `@tool`，通过工厂函数注入依赖
- 文件系统工具：保留路径安全检查（`allowed_dir`），在 Pydantic 模型的 validator 中实现

### 2. 保持功能完整
- 所有工具的具体业务逻辑不变
- shell 的 deny_patterns 安全规则保留
- 文件系统的路径限制保留
- web_search 的多 provider 支持保留
- MCP 动态工具包装保留

### 3. 适配 ToolRegistry
- 重构 ToolRegistry 使其同时支持 LangChain Tool 和旧 Tool
- 或者完全用 LangChain 的工具列表替代 registry
- `get_definitions()` 应返回与 LangChain `convert_to_openai_function()` 兼容的格式

### 4. 文件结构

nanobot/agent/tools/
├── base.py           # 可保留做向后兼容，或标记为 deprecated
├── registry.py       # 重构为支持 LangChain Tool
├── filesystem.py     # 用 @tool + Pydantic 重写
├── shell.py          # 用 @tool + Pydantic 重写
├── web.py            # 用 @tool + Pydantic 重写
├── message.py        # 用 StructuredTool + 工厂函数重写
├── spawn.py          # 用 StructuredTool + 工厂函数重写
├── cron.py           # 用 StructuredTool + 工厂函数重写
└── mcp.py            # 保留动态包装逻辑，适配 LangChain Tool 接口

## 示例：期望的工具定义风格

```python
from langchain_core.tools import tool
from pydantic import BaseModel, Field

class ReadFileInput(BaseModel):
    path: str = Field(description="File path to read")
    offset: int | None = Field(default=None, description="Line offset to start reading from")
    limit: int | None = Field(default=None, description="Maximum number of lines to read")

@tool(args_schema=ReadFileInput)
async def read_file(path: str, offset: int | None = None, limit: int | None = None) -> str:
    """Read the contents of a file."""
    # ... 实现逻辑 ...
```

## 测试验证
重构完成后，以下测试必须全部通过：

pytest tests/test_filesystem_tools.py tests/test_tool_validation.py tests/test_web_search_tool.py tests/test_mcp_tool.py tests/test_message_tool.py tests/test_message_tool_suppress.py tests/test_task_cancel.py tests/test_cron_service.py

## 依赖
- 需要添加：`langchain-core`（@tool 装饰器来自这里）
- 已安装：`langgraph>=1.1.2`、`pydantic>=2.12.0`

## 参考代码路径
- Tool base: nanobot/agent/tools/base.py
- Registry: nanobot/agent/tools/registry.py
- 各工具文件: nanobot/agent/tools/*.py

## 注意事项
- 这是 Phase 2，Phase 1 已用 LangGraph 重构了 Agent Loop
- 确保重构后的工具能被 Phase 1 的 LangGraph 图正确调用
- 不要修改 providers/、channels/、bus/、config/ 目录
- 代码风格：ruff，line-length=100，target Python 3.11+
```

---

## 五、Phase 3 Prompt — 用 LangGraph 重构 Memory

```
# 任务：用 LangGraph Checkpointing + LangChain Memory 重构 nanobot 记忆系统

## 背景
nanobot 的记忆系统在 `nanobot/agent/memory.py` 中，包含：
- `MemoryStore`：持久化存储 MEMORY.md（长期记忆）和 HISTORY.md（历史摘要）
- `MemoryConsolidator`：当上下文窗口超限时，自动将旧消息归档为摘要

我希望用 LangGraph 的 checkpointing 机制和 LangChain 的 memory 抽象来替代。

## 当前架构
- `MemoryStore`:
  - `read_long_term()` / `write_long_term()` — 读写 MEMORY.md
  - `append_history(entry)` — 追加到 HISTORY.md
  - `get_memory_context()` — 返回记忆内容供 system prompt 使用
- `MemoryConsolidator`:
  - `maybe_consolidate_by_tokens()` — token 超限时触发整合
  - `consolidate_messages(messages)` — 将消息段交给 LLM 生成摘要
  - 使用 `_SAVE_MEMORY_TOOL` 让 LLM 通过 function calling 输出结构化摘要
  - 失败降级：多次失败后 `_raw_archive()` 原始写入

## 重构要求

### 1. 使用 LangGraph Checkpointer
- 用 `MemorySaver`（开发/轻量）或 `SqliteSaver`（持久化）替代 Session 的 JSONL 存储
- 每次 agent 循环结束时自动 checkpoint
- 支持通过 `thread_id`（对应现有的 session_key = channel:chat_id）恢复会话

### 2. 保留长期记忆机制
- MEMORY.md 的长期记忆概念保留（LangGraph checkpoint 只管短期对话状态）
- 可以用 LangChain 的 `ConversationSummaryBufferMemory` 替代 `MemoryConsolidator`
  - 当 buffer 超过 `max_token_limit` 时自动生成摘要
  - 摘要持久化到 MEMORY.md 或专用存储
- 或者自定义一个 LangGraph 节点 `consolidate_memory` 在图中作为条件节点

### 3. 保持向后兼容
- 现有 MEMORY.md 和 HISTORY.md 的内容应该能被迁移或继续使用
- ContextBuilder 中引用记忆的方式需要相应调整
- system prompt 中的记忆注入逻辑保留

### 4. AgentState 扩展
在 Phase 1 创建的 `AgentState` 中添加记忆相关字段：

class AgentState(TypedDict):
    messages: list[BaseMessage]
    # ... 现有字段 ...
    long_term_memory: str           # MEMORY.md 内容
    should_consolidate: bool        # 是否需要记忆整合
    consolidation_count: int        # 整合失败计数

## 测试验证
重构完成后，以下测试必须全部通过：

pytest tests/test_memory_consolidation_types.py tests/test_consolidate_offset.py tests/test_loop_consolidation_tokens.py tests/test_context_prompt_cache.py tests/test_loop_save_turn.py

## 依赖
- `langgraph` 已安装
- 可能需要：`langgraph-checkpoint-sqlite`（如果用 SQLite 持久化）

## 参考代码路径
- Memory: nanobot/agent/memory.py
- Context Builder: nanobot/agent/context.py
- Session: nanobot/session/manager.py
- Agent State: nanobot/agent/state.py（Phase 1 创建）

## 注意事项
- 这是 Phase 3，Phase 1 和 Phase 2 已完成
- token 估算函数 `estimate_prompt_tokens_chain()` 在 `nanobot/utils/helpers.py` 中，可继续使用
- 记忆整合使用的 LLM 调用应复用现有的 provider，不要引入新的 LangChain ChatModel
- 代码风格：ruff，line-length=100，target Python 3.11+
```
