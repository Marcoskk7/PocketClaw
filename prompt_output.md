Project Path: agent

Source Tree:

```txt
agent
├── __init__.py
├── tools
│   ├── __init__.py
│   ├── base.py
│   ├── shell.py
│   ├── spawn.py
│   ├── cron.py
│   ├── filesystem.py
│   ├── message.py
│   ├── mcp.py
│   ├── web.py
│   └── registry.py
├── memory.py
├── subagent.py
├── loop.py
├── skills.py
└── context.py

```

`agent/__init__.py`:

```py
   1 | """Agent core module."""
   2 | 
   3 | from nanobot.agent.context import ContextBuilder
   4 | from nanobot.agent.loop import AgentLoop
   5 | from nanobot.agent.memory import MemoryStore
   6 | from nanobot.agent.skills import SkillsLoader
   7 | 
   8 | __all__ = ["AgentLoop", "ContextBuilder", "MemoryStore", "SkillsLoader"]

```

`agent/tools/__init__.py`:

```py
   1 | """Agent tools module."""
   2 | 
   3 | from nanobot.agent.tools.base import Tool
   4 | from nanobot.agent.tools.registry import ToolRegistry
   5 | 
   6 | __all__ = ["Tool", "ToolRegistry"]

```

`agent/tools/base.py`:

```py
   1 | """Base class for agent tools."""
   2 | 
   3 | from abc import ABC, abstractmethod
   4 | from typing import Any
   5 | 
   6 | 
   7 | class Tool(ABC):
   8 |     """
   9 |     Abstract base class for agent tools.
  10 | 
  11 |     Tools are capabilities that the agent can use to interact with
  12 |     the environment, such as reading files, executing commands, etc.
  13 |     """
  14 | 
  15 |     _TYPE_MAP = {
  16 |         "string": str,
  17 |         "integer": int,
  18 |         "number": (int, float),
  19 |         "boolean": bool,
  20 |         "array": list,
  21 |         "object": dict,
  22 |     }
  23 | 
  24 |     @property
  25 |     @abstractmethod
  26 |     def name(self) -> str:
  27 |         """Tool name used in function calls."""
  28 |         pass
  29 | 
  30 |     @property
  31 |     @abstractmethod
  32 |     def description(self) -> str:
  33 |         """Description of what the tool does."""
  34 |         pass
  35 | 
  36 |     @property
  37 |     @abstractmethod
  38 |     def parameters(self) -> dict[str, Any]:
  39 |         """JSON Schema for tool parameters."""
  40 |         pass
  41 | 
  42 |     @abstractmethod
  43 |     async def execute(self, **kwargs: Any) -> str:
  44 |         """
  45 |         Execute the tool with given parameters.
  46 | 
  47 |         Args:
  48 |             **kwargs: Tool-specific parameters.
  49 | 
  50 |         Returns:
  51 |             String result of the tool execution.
  52 |         """
  53 |         pass
  54 | 
  55 |     def cast_params(self, params: dict[str, Any]) -> dict[str, Any]:
  56 |         """Apply safe schema-driven casts before validation."""
  57 |         schema = self.parameters or {}
  58 |         if schema.get("type", "object") != "object":
  59 |             return params
  60 | 
  61 |         return self._cast_object(params, schema)
  62 | 
  63 |     def _cast_object(self, obj: Any, schema: dict[str, Any]) -> dict[str, Any]:
  64 |         """Cast an object (dict) according to schema."""
  65 |         if not isinstance(obj, dict):
  66 |             return obj
  67 | 
  68 |         props = schema.get("properties", {})
  69 |         result = {}
  70 | 
  71 |         for key, value in obj.items():
  72 |             if key in props:
  73 |                 result[key] = self._cast_value(value, props[key])
  74 |             else:
  75 |                 result[key] = value
  76 | 
  77 |         return result
  78 | 
  79 |     def _cast_value(self, val: Any, schema: dict[str, Any]) -> Any:
  80 |         """Cast a single value according to schema."""
  81 |         target_type = schema.get("type")
  82 | 
  83 |         if target_type == "boolean" and isinstance(val, bool):
  84 |             return val
  85 |         if target_type == "integer" and isinstance(val, int) and not isinstance(val, bool):
  86 |             return val
  87 |         if target_type in self._TYPE_MAP and target_type not in ("boolean", "integer", "array", "object"):
  88 |             expected = self._TYPE_MAP[target_type]
  89 |             if isinstance(val, expected):
  90 |                 return val
  91 | 
  92 |         if target_type == "integer" and isinstance(val, str):
  93 |             try:
  94 |                 return int(val)
  95 |             except ValueError:
  96 |                 return val
  97 | 
  98 |         if target_type == "number" and isinstance(val, str):
  99 |             try:
 100 |                 return float(val)
 101 |             except ValueError:
 102 |                 return val
 103 | 
 104 |         if target_type == "string":
 105 |             return val if val is None else str(val)
 106 | 
 107 |         if target_type == "boolean" and isinstance(val, str):
 108 |             val_lower = val.lower()
 109 |             if val_lower in ("true", "1", "yes"):
 110 |                 return True
 111 |             if val_lower in ("false", "0", "no"):
 112 |                 return False
 113 |             return val
 114 | 
 115 |         if target_type == "array" and isinstance(val, list):
 116 |             item_schema = schema.get("items")
 117 |             return [self._cast_value(item, item_schema) for item in val] if item_schema else val
 118 | 
 119 |         if target_type == "object" and isinstance(val, dict):
 120 |             return self._cast_object(val, schema)
 121 | 
 122 |         return val
 123 | 
 124 |     def validate_params(self, params: dict[str, Any]) -> list[str]:
 125 |         """Validate tool parameters against JSON schema. Returns error list (empty if valid)."""
 126 |         if not isinstance(params, dict):
 127 |             return [f"parameters must be an object, got {type(params).__name__}"]
 128 |         schema = self.parameters or {}
 129 |         if schema.get("type", "object") != "object":
 130 |             raise ValueError(f"Schema must be object type, got {schema.get('type')!r}")
 131 |         return self._validate(params, {**schema, "type": "object"}, "")
 132 | 
 133 |     def _validate(self, val: Any, schema: dict[str, Any], path: str) -> list[str]:
 134 |         t, label = schema.get("type"), path or "parameter"
 135 |         if t == "integer" and (not isinstance(val, int) or isinstance(val, bool)):
 136 |             return [f"{label} should be integer"]
 137 |         if t == "number" and (
 138 |             not isinstance(val, self._TYPE_MAP[t]) or isinstance(val, bool)
 139 |         ):
 140 |             return [f"{label} should be number"]
 141 |         if t in self._TYPE_MAP and t not in ("integer", "number") and not isinstance(val, self._TYPE_MAP[t]):
 142 |             return [f"{label} should be {t}"]
 143 | 
 144 |         errors = []
 145 |         if "enum" in schema and val not in schema["enum"]:
 146 |             errors.append(f"{label} must be one of {schema['enum']}")
 147 |         if t in ("integer", "number"):
 148 |             if "minimum" in schema and val < schema["minimum"]:
 149 |                 errors.append(f"{label} must be >= {schema['minimum']}")
 150 |             if "maximum" in schema and val > schema["maximum"]:
 151 |                 errors.append(f"{label} must be <= {schema['maximum']}")
 152 |         if t == "string":
 153 |             if "minLength" in schema and len(val) < schema["minLength"]:
 154 |                 errors.append(f"{label} must be at least {schema['minLength']} chars")
 155 |             if "maxLength" in schema and len(val) > schema["maxLength"]:
 156 |                 errors.append(f"{label} must be at most {schema['maxLength']} chars")
 157 |         if t == "object":
 158 |             props = schema.get("properties", {})
 159 |             for k in schema.get("required", []):
 160 |                 if k not in val:
 161 |                     errors.append(f"missing required {path + '.' + k if path else k}")
 162 |             for k, v in val.items():
 163 |                 if k in props:
 164 |                     errors.extend(self._validate(v, props[k], path + "." + k if path else k))
 165 |         if t == "array" and "items" in schema:
 166 |             for i, item in enumerate(val):
 167 |                 errors.extend(
 168 |                     self._validate(item, schema["items"], f"{path}[{i}]" if path else f"[{i}]")
 169 |                 )
 170 |         return errors
 171 | 
 172 |     def to_schema(self) -> dict[str, Any]:
 173 |         """Convert tool to OpenAI function schema format."""
 174 |         return {
 175 |             "type": "function",
 176 |             "function": {
 177 |                 "name": self.name,
 178 |                 "description": self.description,
 179 |                 "parameters": self.parameters,
 180 |             },
 181 |         }

```

`agent/tools/shell.py`:

```py
   1 | """Shell execution tool."""
   2 | 
   3 | import asyncio
   4 | import os
   5 | import re
   6 | from pathlib import Path
   7 | from typing import Any
   8 | 
   9 | from nanobot.agent.tools.base import Tool
  10 | 
  11 | 
  12 | class ExecTool(Tool):
  13 |     """Tool to execute shell commands."""
  14 | 
  15 |     def __init__(
  16 |         self,
  17 |         timeout: int = 60,
  18 |         working_dir: str | None = None,
  19 |         deny_patterns: list[str] | None = None,
  20 |         allow_patterns: list[str] | None = None,
  21 |         restrict_to_workspace: bool = False,
  22 |         path_append: str = "",
  23 |     ):
  24 |         self.timeout = timeout
  25 |         self.working_dir = working_dir
  26 |         self.deny_patterns = deny_patterns or [
  27 |             r"\brm\s+-[rf]{1,2}\b",          # rm -r, rm -rf, rm -fr
  28 |             r"\bdel\s+/[fq]\b",              # del /f, del /q
  29 |             r"\brmdir\s+/s\b",               # rmdir /s
  30 |             r"(?:^|[;&|]\s*)format\b",       # format (as standalone command only)
  31 |             r"\b(mkfs|diskpart)\b",          # disk operations
  32 |             r"\bdd\s+if=",                   # dd
  33 |             r">\s*/dev/sd",                  # write to disk
  34 |             r"\b(shutdown|reboot|poweroff)\b",  # system power
  35 |             r":\(\)\s*\{.*\};\s*:",          # fork bomb
  36 |         ]
  37 |         self.allow_patterns = allow_patterns or []
  38 |         self.restrict_to_workspace = restrict_to_workspace
  39 |         self.path_append = path_append
  40 | 
  41 |     @property
  42 |     def name(self) -> str:
  43 |         return "exec"
  44 | 
  45 |     _MAX_TIMEOUT = 600
  46 |     _MAX_OUTPUT = 10_000
  47 | 
  48 |     @property
  49 |     def description(self) -> str:
  50 |         return "Execute a shell command and return its output. Use with caution."
  51 | 
  52 |     @property
  53 |     def parameters(self) -> dict[str, Any]:
  54 |         return {
  55 |             "type": "object",
  56 |             "properties": {
  57 |                 "command": {
  58 |                     "type": "string",
  59 |                     "description": "The shell command to execute",
  60 |                 },
  61 |                 "working_dir": {
  62 |                     "type": "string",
  63 |                     "description": "Optional working directory for the command",
  64 |                 },
  65 |                 "timeout": {
  66 |                     "type": "integer",
  67 |                     "description": (
  68 |                         "Timeout in seconds. Increase for long-running commands "
  69 |                         "like compilation or installation (default 60, max 600)."
  70 |                     ),
  71 |                     "minimum": 1,
  72 |                     "maximum": 600,
  73 |                 },
  74 |             },
  75 |             "required": ["command"],
  76 |         }
  77 | 
  78 |     async def execute(
  79 |         self, command: str, working_dir: str | None = None,
  80 |         timeout: int | None = None, **kwargs: Any,
  81 |     ) -> str:
  82 |         cwd = working_dir or self.working_dir or os.getcwd()
  83 |         guard_error = self._guard_command(command, cwd)
  84 |         if guard_error:
  85 |             return guard_error
  86 | 
  87 |         effective_timeout = min(timeout or self.timeout, self._MAX_TIMEOUT)
  88 | 
  89 |         env = os.environ.copy()
  90 |         if self.path_append:
  91 |             env["PATH"] = env.get("PATH", "") + os.pathsep + self.path_append
  92 | 
  93 |         try:
  94 |             process = await asyncio.create_subprocess_shell(
  95 |                 command,
  96 |                 stdout=asyncio.subprocess.PIPE,
  97 |                 stderr=asyncio.subprocess.PIPE,
  98 |                 cwd=cwd,
  99 |                 env=env,
 100 |             )
 101 | 
 102 |             try:
 103 |                 stdout, stderr = await asyncio.wait_for(
 104 |                     process.communicate(),
 105 |                     timeout=effective_timeout,
 106 |                 )
 107 |             except asyncio.TimeoutError:
 108 |                 process.kill()
 109 |                 try:
 110 |                     await asyncio.wait_for(process.wait(), timeout=5.0)
 111 |                 except asyncio.TimeoutError:
 112 |                     pass
 113 |                 return f"Error: Command timed out after {effective_timeout} seconds"
 114 | 
 115 |             output_parts = []
 116 | 
 117 |             if stdout:
 118 |                 output_parts.append(stdout.decode("utf-8", errors="replace"))
 119 | 
 120 |             if stderr:
 121 |                 stderr_text = stderr.decode("utf-8", errors="replace")
 122 |                 if stderr_text.strip():
 123 |                     output_parts.append(f"STDERR:\n{stderr_text}")
 124 | 
 125 |             output_parts.append(f"\nExit code: {process.returncode}")
 126 | 
 127 |             result = "\n".join(output_parts) if output_parts else "(no output)"
 128 | 
 129 |             # Head + tail truncation to preserve both start and end of output
 130 |             max_len = self._MAX_OUTPUT
 131 |             if len(result) > max_len:
 132 |                 half = max_len // 2
 133 |                 result = (
 134 |                     result[:half]
 135 |                     + f"\n\n... ({len(result) - max_len:,} chars truncated) ...\n\n"
 136 |                     + result[-half:]
 137 |                 )
 138 | 
 139 |             return result
 140 | 
 141 |         except Exception as e:
 142 |             return f"Error executing command: {str(e)}"
 143 | 
 144 |     def _guard_command(self, command: str, cwd: str) -> str | None:
 145 |         """Best-effort safety guard for potentially destructive commands."""
 146 |         cmd = command.strip()
 147 |         lower = cmd.lower()
 148 | 
 149 |         for pattern in self.deny_patterns:
 150 |             if re.search(pattern, lower):
 151 |                 return "Error: Command blocked by safety guard (dangerous pattern detected)"
 152 | 
 153 |         if self.allow_patterns:
 154 |             if not any(re.search(p, lower) for p in self.allow_patterns):
 155 |                 return "Error: Command blocked by safety guard (not in allowlist)"
 156 | 
 157 |         if self.restrict_to_workspace:
 158 |             if "..\\" in cmd or "../" in cmd:
 159 |                 return "Error: Command blocked by safety guard (path traversal detected)"
 160 | 
 161 |             cwd_path = Path(cwd).resolve()
 162 | 
 163 |             for raw in self._extract_absolute_paths(cmd):
 164 |                 try:
 165 |                     expanded = os.path.expandvars(raw.strip())
 166 |                     p = Path(expanded).expanduser().resolve()
 167 |                 except Exception:
 168 |                     continue
 169 |                 if p.is_absolute() and cwd_path not in p.parents and p != cwd_path:
 170 |                     return "Error: Command blocked by safety guard (path outside working dir)"
 171 | 
 172 |         return None
 173 | 
 174 |     @staticmethod
 175 |     def _extract_absolute_paths(command: str) -> list[str]:
 176 |         win_paths = re.findall(r"[A-Za-z]:\\[^\s\"'|><;]+", command)   # Windows: C:\...
 177 |         posix_paths = re.findall(r"(?:^|[\s|>'\"])(/[^\s\"'>;|<]+)", command) # POSIX: /absolute only
 178 |         home_paths = re.findall(r"(?:^|[\s|>'\"])(~[^\s\"'>;|<]*)", command) # POSIX/Windows home shortcut: ~
 179 |         return win_paths + posix_paths + home_paths

```

`agent/tools/spawn.py`:

```py
   1 | """Spawn tool for creating background subagents."""
   2 | 
   3 | from typing import TYPE_CHECKING, Any
   4 | 
   5 | from nanobot.agent.tools.base import Tool
   6 | 
   7 | if TYPE_CHECKING:
   8 |     from nanobot.agent.subagent import SubagentManager
   9 | 
  10 | 
  11 | class SpawnTool(Tool):
  12 |     """Tool to spawn a subagent for background task execution."""
  13 | 
  14 |     def __init__(self, manager: "SubagentManager"):
  15 |         self._manager = manager
  16 |         self._origin_channel = "cli"
  17 |         self._origin_chat_id = "direct"
  18 |         self._session_key = "cli:direct"
  19 | 
  20 |     def set_context(self, channel: str, chat_id: str) -> None:
  21 |         """Set the origin context for subagent announcements."""
  22 |         self._origin_channel = channel
  23 |         self._origin_chat_id = chat_id
  24 |         self._session_key = f"{channel}:{chat_id}"
  25 | 
  26 |     @property
  27 |     def name(self) -> str:
  28 |         return "spawn"
  29 | 
  30 |     @property
  31 |     def description(self) -> str:
  32 |         return (
  33 |             "Spawn a subagent to handle a task in the background. "
  34 |             "Use this for complex or time-consuming tasks that can run independently. "
  35 |             "The subagent will complete the task and report back when done."
  36 |         )
  37 | 
  38 |     @property
  39 |     def parameters(self) -> dict[str, Any]:
  40 |         return {
  41 |             "type": "object",
  42 |             "properties": {
  43 |                 "task": {
  44 |                     "type": "string",
  45 |                     "description": "The task for the subagent to complete",
  46 |                 },
  47 |                 "label": {
  48 |                     "type": "string",
  49 |                     "description": "Optional short label for the task (for display)",
  50 |                 },
  51 |             },
  52 |             "required": ["task"],
  53 |         }
  54 | 
  55 |     async def execute(self, task: str, label: str | None = None, **kwargs: Any) -> str:
  56 |         """Spawn a subagent to execute the given task."""
  57 |         return await self._manager.spawn(
  58 |             task=task,
  59 |             label=label,
  60 |             origin_channel=self._origin_channel,
  61 |             origin_chat_id=self._origin_chat_id,
  62 |             session_key=self._session_key,
  63 |         )

```

`agent/tools/cron.py`:

```py
   1 | """Cron tool for scheduling reminders and tasks."""
   2 | 
   3 | from contextvars import ContextVar
   4 | from typing import Any
   5 | 
   6 | from nanobot.agent.tools.base import Tool
   7 | from nanobot.cron.service import CronService
   8 | from nanobot.cron.types import CronSchedule
   9 | 
  10 | 
  11 | class CronTool(Tool):
  12 |     """Tool to schedule reminders and recurring tasks."""
  13 | 
  14 |     def __init__(self, cron_service: CronService):
  15 |         self._cron = cron_service
  16 |         self._channel = ""
  17 |         self._chat_id = ""
  18 |         self._in_cron_context: ContextVar[bool] = ContextVar("cron_in_context", default=False)
  19 | 
  20 |     def set_context(self, channel: str, chat_id: str) -> None:
  21 |         """Set the current session context for delivery."""
  22 |         self._channel = channel
  23 |         self._chat_id = chat_id
  24 | 
  25 |     def set_cron_context(self, active: bool):
  26 |         """Mark whether the tool is executing inside a cron job callback."""
  27 |         return self._in_cron_context.set(active)
  28 | 
  29 |     def reset_cron_context(self, token) -> None:
  30 |         """Restore previous cron context."""
  31 |         self._in_cron_context.reset(token)
  32 | 
  33 |     @property
  34 |     def name(self) -> str:
  35 |         return "cron"
  36 | 
  37 |     @property
  38 |     def description(self) -> str:
  39 |         return "Schedule reminders and recurring tasks. Actions: add, list, remove."
  40 | 
  41 |     @property
  42 |     def parameters(self) -> dict[str, Any]:
  43 |         return {
  44 |             "type": "object",
  45 |             "properties": {
  46 |                 "action": {
  47 |                     "type": "string",
  48 |                     "enum": ["add", "list", "remove"],
  49 |                     "description": "Action to perform",
  50 |                 },
  51 |                 "message": {"type": "string", "description": "Reminder message (for add)"},
  52 |                 "every_seconds": {
  53 |                     "type": "integer",
  54 |                     "description": "Interval in seconds (for recurring tasks)",
  55 |                 },
  56 |                 "cron_expr": {
  57 |                     "type": "string",
  58 |                     "description": "Cron expression like '0 9 * * *' (for scheduled tasks)",
  59 |                 },
  60 |                 "tz": {
  61 |                     "type": "string",
  62 |                     "description": "IANA timezone for cron expressions (e.g. 'America/Vancouver')",
  63 |                 },
  64 |                 "at": {
  65 |                     "type": "string",
  66 |                     "description": "ISO datetime for one-time execution (e.g. '2026-02-12T10:30:00')",
  67 |                 },
  68 |                 "job_id": {"type": "string", "description": "Job ID (for remove)"},
  69 |             },
  70 |             "required": ["action"],
  71 |         }
  72 | 
  73 |     async def execute(
  74 |         self,
  75 |         action: str,
  76 |         message: str = "",
  77 |         every_seconds: int | None = None,
  78 |         cron_expr: str | None = None,
  79 |         tz: str | None = None,
  80 |         at: str | None = None,
  81 |         job_id: str | None = None,
  82 |         **kwargs: Any,
  83 |     ) -> str:
  84 |         if action == "add":
  85 |             if self._in_cron_context.get():
  86 |                 return "Error: cannot schedule new jobs from within a cron job execution"
  87 |             return self._add_job(message, every_seconds, cron_expr, tz, at)
  88 |         elif action == "list":
  89 |             return self._list_jobs()
  90 |         elif action == "remove":
  91 |             return self._remove_job(job_id)
  92 |         return f"Unknown action: {action}"
  93 | 
  94 |     def _add_job(
  95 |         self,
  96 |         message: str,
  97 |         every_seconds: int | None,
  98 |         cron_expr: str | None,
  99 |         tz: str | None,
 100 |         at: str | None,
 101 |     ) -> str:
 102 |         if not message:
 103 |             return "Error: message is required for add"
 104 |         if not self._channel or not self._chat_id:
 105 |             return "Error: no session context (channel/chat_id)"
 106 |         if tz and not cron_expr:
 107 |             return "Error: tz can only be used with cron_expr"
 108 |         if tz:
 109 |             from zoneinfo import ZoneInfo
 110 | 
 111 |             try:
 112 |                 ZoneInfo(tz)
 113 |             except (KeyError, Exception):
 114 |                 return f"Error: unknown timezone '{tz}'"
 115 | 
 116 |         # Build schedule
 117 |         delete_after = False
 118 |         if every_seconds:
 119 |             schedule = CronSchedule(kind="every", every_ms=every_seconds * 1000)
 120 |         elif cron_expr:
 121 |             schedule = CronSchedule(kind="cron", expr=cron_expr, tz=tz)
 122 |         elif at:
 123 |             from datetime import datetime
 124 | 
 125 |             try:
 126 |                 dt = datetime.fromisoformat(at)
 127 |             except ValueError:
 128 |                 return f"Error: invalid ISO datetime format '{at}'. Expected format: YYYY-MM-DDTHH:MM:SS"
 129 |             at_ms = int(dt.timestamp() * 1000)
 130 |             schedule = CronSchedule(kind="at", at_ms=at_ms)
 131 |             delete_after = True
 132 |         else:
 133 |             return "Error: either every_seconds, cron_expr, or at is required"
 134 | 
 135 |         job = self._cron.add_job(
 136 |             name=message[:30],
 137 |             schedule=schedule,
 138 |             message=message,
 139 |             deliver=True,
 140 |             channel=self._channel,
 141 |             to=self._chat_id,
 142 |             delete_after_run=delete_after,
 143 |         )
 144 |         return f"Created job '{job.name}' (id: {job.id})"
 145 | 
 146 |     def _list_jobs(self) -> str:
 147 |         jobs = self._cron.list_jobs()
 148 |         if not jobs:
 149 |             return "No scheduled jobs."
 150 |         lines = [f"- {j.name} (id: {j.id}, {j.schedule.kind})" for j in jobs]
 151 |         return "Scheduled jobs:\n" + "\n".join(lines)
 152 | 
 153 |     def _remove_job(self, job_id: str | None) -> str:
 154 |         if not job_id:
 155 |             return "Error: job_id is required for remove"
 156 |         if self._cron.remove_job(job_id):
 157 |             return f"Removed job {job_id}"
 158 |         return f"Job {job_id} not found"

```

`agent/tools/filesystem.py`:

```py
   1 | """File system tools: read, write, edit, list."""
   2 | 
   3 | import difflib
   4 | from pathlib import Path
   5 | from typing import Any
   6 | 
   7 | from nanobot.agent.tools.base import Tool
   8 | 
   9 | 
  10 | def _resolve_path(
  11 |     path: str, workspace: Path | None = None, allowed_dir: Path | None = None
  12 | ) -> Path:
  13 |     """Resolve path against workspace (if relative) and enforce directory restriction."""
  14 |     p = Path(path).expanduser()
  15 |     if not p.is_absolute() and workspace:
  16 |         p = workspace / p
  17 |     resolved = p.resolve()
  18 |     if allowed_dir:
  19 |         try:
  20 |             resolved.relative_to(allowed_dir.resolve())
  21 |         except ValueError:
  22 |             raise PermissionError(f"Path {path} is outside allowed directory {allowed_dir}")
  23 |     return resolved
  24 | 
  25 | 
  26 | class _FsTool(Tool):
  27 |     """Shared base for filesystem tools — common init and path resolution."""
  28 | 
  29 |     def __init__(self, workspace: Path | None = None, allowed_dir: Path | None = None):
  30 |         self._workspace = workspace
  31 |         self._allowed_dir = allowed_dir
  32 | 
  33 |     def _resolve(self, path: str) -> Path:
  34 |         return _resolve_path(path, self._workspace, self._allowed_dir)
  35 | 
  36 | 
  37 | # ---------------------------------------------------------------------------
  38 | # read_file
  39 | # ---------------------------------------------------------------------------
  40 | 
  41 | class ReadFileTool(_FsTool):
  42 |     """Read file contents with optional line-based pagination."""
  43 | 
  44 |     _MAX_CHARS = 128_000
  45 |     _DEFAULT_LIMIT = 2000
  46 | 
  47 |     @property
  48 |     def name(self) -> str:
  49 |         return "read_file"
  50 | 
  51 |     @property
  52 |     def description(self) -> str:
  53 |         return (
  54 |             "Read the contents of a file. Returns numbered lines. "
  55 |             "Use offset and limit to paginate through large files."
  56 |         )
  57 | 
  58 |     @property
  59 |     def parameters(self) -> dict[str, Any]:
  60 |         return {
  61 |             "type": "object",
  62 |             "properties": {
  63 |                 "path": {"type": "string", "description": "The file path to read"},
  64 |                 "offset": {
  65 |                     "type": "integer",
  66 |                     "description": "Line number to start reading from (1-indexed, default 1)",
  67 |                     "minimum": 1,
  68 |                 },
  69 |                 "limit": {
  70 |                     "type": "integer",
  71 |                     "description": "Maximum number of lines to read (default 2000)",
  72 |                     "minimum": 1,
  73 |                 },
  74 |             },
  75 |             "required": ["path"],
  76 |         }
  77 | 
  78 |     async def execute(self, path: str, offset: int = 1, limit: int | None = None, **kwargs: Any) -> str:
  79 |         try:
  80 |             fp = self._resolve(path)
  81 |             if not fp.exists():
  82 |                 return f"Error: File not found: {path}"
  83 |             if not fp.is_file():
  84 |                 return f"Error: Not a file: {path}"
  85 | 
  86 |             all_lines = fp.read_text(encoding="utf-8").splitlines()
  87 |             total = len(all_lines)
  88 | 
  89 |             if offset < 1:
  90 |                 offset = 1
  91 |             if total == 0:
  92 |                 return f"(Empty file: {path})"
  93 |             if offset > total:
  94 |                 return f"Error: offset {offset} is beyond end of file ({total} lines)"
  95 | 
  96 |             start = offset - 1
  97 |             end = min(start + (limit or self._DEFAULT_LIMIT), total)
  98 |             numbered = [f"{start + i + 1}| {line}" for i, line in enumerate(all_lines[start:end])]
  99 |             result = "\n".join(numbered)
 100 | 
 101 |             if len(result) > self._MAX_CHARS:
 102 |                 trimmed, chars = [], 0
 103 |                 for line in numbered:
 104 |                     chars += len(line) + 1
 105 |                     if chars > self._MAX_CHARS:
 106 |                         break
 107 |                     trimmed.append(line)
 108 |                 end = start + len(trimmed)
 109 |                 result = "\n".join(trimmed)
 110 | 
 111 |             if end < total:
 112 |                 result += f"\n\n(Showing lines {offset}-{end} of {total}. Use offset={end + 1} to continue.)"
 113 |             else:
 114 |                 result += f"\n\n(End of file — {total} lines total)"
 115 |             return result
 116 |         except PermissionError as e:
 117 |             return f"Error: {e}"
 118 |         except Exception as e:
 119 |             return f"Error reading file: {e}"
 120 | 
 121 | 
 122 | # ---------------------------------------------------------------------------
 123 | # write_file
 124 | # ---------------------------------------------------------------------------
 125 | 
 126 | class WriteFileTool(_FsTool):
 127 |     """Write content to a file."""
 128 | 
 129 |     @property
 130 |     def name(self) -> str:
 131 |         return "write_file"
 132 | 
 133 |     @property
 134 |     def description(self) -> str:
 135 |         return "Write content to a file at the given path. Creates parent directories if needed."
 136 | 
 137 |     @property
 138 |     def parameters(self) -> dict[str, Any]:
 139 |         return {
 140 |             "type": "object",
 141 |             "properties": {
 142 |                 "path": {"type": "string", "description": "The file path to write to"},
 143 |                 "content": {"type": "string", "description": "The content to write"},
 144 |             },
 145 |             "required": ["path", "content"],
 146 |         }
 147 | 
 148 |     async def execute(self, path: str, content: str, **kwargs: Any) -> str:
 149 |         try:
 150 |             fp = self._resolve(path)
 151 |             fp.parent.mkdir(parents=True, exist_ok=True)
 152 |             fp.write_text(content, encoding="utf-8")
 153 |             return f"Successfully wrote {len(content)} bytes to {fp}"
 154 |         except PermissionError as e:
 155 |             return f"Error: {e}"
 156 |         except Exception as e:
 157 |             return f"Error writing file: {e}"
 158 | 
 159 | 
 160 | # ---------------------------------------------------------------------------
 161 | # edit_file
 162 | # ---------------------------------------------------------------------------
 163 | 
 164 | def _find_match(content: str, old_text: str) -> tuple[str | None, int]:
 165 |     """Locate old_text in content: exact first, then line-trimmed sliding window.
 166 | 
 167 |     Both inputs should use LF line endings (caller normalises CRLF).
 168 |     Returns (matched_fragment, count) or (None, 0).
 169 |     """
 170 |     if old_text in content:
 171 |         return old_text, content.count(old_text)
 172 | 
 173 |     old_lines = old_text.splitlines()
 174 |     if not old_lines:
 175 |         return None, 0
 176 |     stripped_old = [l.strip() for l in old_lines]
 177 |     content_lines = content.splitlines()
 178 | 
 179 |     candidates = []
 180 |     for i in range(len(content_lines) - len(stripped_old) + 1):
 181 |         window = content_lines[i : i + len(stripped_old)]
 182 |         if [l.strip() for l in window] == stripped_old:
 183 |             candidates.append("\n".join(window))
 184 | 
 185 |     if candidates:
 186 |         return candidates[0], len(candidates)
 187 |     return None, 0
 188 | 
 189 | 
 190 | class EditFileTool(_FsTool):
 191 |     """Edit a file by replacing text with fallback matching."""
 192 | 
 193 |     @property
 194 |     def name(self) -> str:
 195 |         return "edit_file"
 196 | 
 197 |     @property
 198 |     def description(self) -> str:
 199 |         return (
 200 |             "Edit a file by replacing old_text with new_text. "
 201 |             "Supports minor whitespace/line-ending differences. "
 202 |             "Set replace_all=true to replace every occurrence."
 203 |         )
 204 | 
 205 |     @property
 206 |     def parameters(self) -> dict[str, Any]:
 207 |         return {
 208 |             "type": "object",
 209 |             "properties": {
 210 |                 "path": {"type": "string", "description": "The file path to edit"},
 211 |                 "old_text": {"type": "string", "description": "The text to find and replace"},
 212 |                 "new_text": {"type": "string", "description": "The text to replace with"},
 213 |                 "replace_all": {
 214 |                     "type": "boolean",
 215 |                     "description": "Replace all occurrences (default false)",
 216 |                 },
 217 |             },
 218 |             "required": ["path", "old_text", "new_text"],
 219 |         }
 220 | 
 221 |     async def execute(
 222 |         self, path: str, old_text: str, new_text: str,
 223 |         replace_all: bool = False, **kwargs: Any,
 224 |     ) -> str:
 225 |         try:
 226 |             fp = self._resolve(path)
 227 |             if not fp.exists():
 228 |                 return f"Error: File not found: {path}"
 229 | 
 230 |             raw = fp.read_bytes()
 231 |             uses_crlf = b"\r\n" in raw
 232 |             content = raw.decode("utf-8").replace("\r\n", "\n")
 233 |             match, count = _find_match(content, old_text.replace("\r\n", "\n"))
 234 | 
 235 |             if match is None:
 236 |                 return self._not_found_msg(old_text, content, path)
 237 |             if count > 1 and not replace_all:
 238 |                 return (
 239 |                     f"Warning: old_text appears {count} times. "
 240 |                     "Provide more context to make it unique, or set replace_all=true."
 241 |                 )
 242 | 
 243 |             norm_new = new_text.replace("\r\n", "\n")
 244 |             new_content = content.replace(match, norm_new) if replace_all else content.replace(match, norm_new, 1)
 245 |             if uses_crlf:
 246 |                 new_content = new_content.replace("\n", "\r\n")
 247 | 
 248 |             fp.write_bytes(new_content.encode("utf-8"))
 249 |             return f"Successfully edited {fp}"
 250 |         except PermissionError as e:
 251 |             return f"Error: {e}"
 252 |         except Exception as e:
 253 |             return f"Error editing file: {e}"
 254 | 
 255 |     @staticmethod
 256 |     def _not_found_msg(old_text: str, content: str, path: str) -> str:
 257 |         lines = content.splitlines(keepends=True)
 258 |         old_lines = old_text.splitlines(keepends=True)
 259 |         window = len(old_lines)
 260 | 
 261 |         best_ratio, best_start = 0.0, 0
 262 |         for i in range(max(1, len(lines) - window + 1)):
 263 |             ratio = difflib.SequenceMatcher(None, old_lines, lines[i : i + window]).ratio()
 264 |             if ratio > best_ratio:
 265 |                 best_ratio, best_start = ratio, i
 266 | 
 267 |         if best_ratio > 0.5:
 268 |             diff = "\n".join(difflib.unified_diff(
 269 |                 old_lines, lines[best_start : best_start + window],
 270 |                 fromfile="old_text (provided)",
 271 |                 tofile=f"{path} (actual, line {best_start + 1})",
 272 |                 lineterm="",
 273 |             ))
 274 |             return f"Error: old_text not found in {path}.\nBest match ({best_ratio:.0%} similar) at line {best_start + 1}:\n{diff}"
 275 |         return f"Error: old_text not found in {path}. No similar text found. Verify the file content."
 276 | 
 277 | 
 278 | # ---------------------------------------------------------------------------
 279 | # list_dir
 280 | # ---------------------------------------------------------------------------
 281 | 
 282 | class ListDirTool(_FsTool):
 283 |     """List directory contents with optional recursion."""
 284 | 
 285 |     _DEFAULT_MAX = 200
 286 |     _IGNORE_DIRS = {
 287 |         ".git", "node_modules", "__pycache__", ".venv", "venv",
 288 |         "dist", "build", ".tox", ".mypy_cache", ".pytest_cache",
 289 |         ".ruff_cache", ".coverage", "htmlcov",
 290 |     }
 291 | 
 292 |     @property
 293 |     def name(self) -> str:
 294 |         return "list_dir"
 295 | 
 296 |     @property
 297 |     def description(self) -> str:
 298 |         return (
 299 |             "List the contents of a directory. "
 300 |             "Set recursive=true to explore nested structure. "
 301 |             "Common noise directories (.git, node_modules, __pycache__, etc.) are auto-ignored."
 302 |         )
 303 | 
 304 |     @property
 305 |     def parameters(self) -> dict[str, Any]:
 306 |         return {
 307 |             "type": "object",
 308 |             "properties": {
 309 |                 "path": {"type": "string", "description": "The directory path to list"},
 310 |                 "recursive": {
 311 |                     "type": "boolean",
 312 |                     "description": "Recursively list all files (default false)",
 313 |                 },
 314 |                 "max_entries": {
 315 |                     "type": "integer",
 316 |                     "description": "Maximum entries to return (default 200)",
 317 |                     "minimum": 1,
 318 |                 },
 319 |             },
 320 |             "required": ["path"],
 321 |         }
 322 | 
 323 |     async def execute(
 324 |         self, path: str, recursive: bool = False,
 325 |         max_entries: int | None = None, **kwargs: Any,
 326 |     ) -> str:
 327 |         try:
 328 |             dp = self._resolve(path)
 329 |             if not dp.exists():
 330 |                 return f"Error: Directory not found: {path}"
 331 |             if not dp.is_dir():
 332 |                 return f"Error: Not a directory: {path}"
 333 | 
 334 |             cap = max_entries or self._DEFAULT_MAX
 335 |             items: list[str] = []
 336 |             total = 0
 337 | 
 338 |             if recursive:
 339 |                 for item in sorted(dp.rglob("*")):
 340 |                     if any(p in self._IGNORE_DIRS for p in item.parts):
 341 |                         continue
 342 |                     total += 1
 343 |                     if len(items) < cap:
 344 |                         rel = item.relative_to(dp)
 345 |                         items.append(f"{rel}/" if item.is_dir() else str(rel))
 346 |             else:
 347 |                 for item in sorted(dp.iterdir()):
 348 |                     if item.name in self._IGNORE_DIRS:
 349 |                         continue
 350 |                     total += 1
 351 |                     if len(items) < cap:
 352 |                         pfx = "📁 " if item.is_dir() else "📄 "
 353 |                         items.append(f"{pfx}{item.name}")
 354 | 
 355 |             if not items and total == 0:
 356 |                 return f"Directory {path} is empty"
 357 | 
 358 |             result = "\n".join(items)
 359 |             if total > cap:
 360 |                 result += f"\n\n(truncated, showing first {cap} of {total} entries)"
 361 |             return result
 362 |         except PermissionError as e:
 363 |             return f"Error: {e}"
 364 |         except Exception as e:
 365 |             return f"Error listing directory: {e}"

```

`agent/tools/message.py`:

```py
   1 | """Message tool for sending messages to users."""
   2 | 
   3 | from typing import Any, Awaitable, Callable
   4 | 
   5 | from nanobot.agent.tools.base import Tool
   6 | from nanobot.bus.events import OutboundMessage
   7 | 
   8 | 
   9 | class MessageTool(Tool):
  10 |     """Tool to send messages to users on chat channels."""
  11 | 
  12 |     def __init__(
  13 |         self,
  14 |         send_callback: Callable[[OutboundMessage], Awaitable[None]] | None = None,
  15 |         default_channel: str = "",
  16 |         default_chat_id: str = "",
  17 |         default_message_id: str | None = None,
  18 |     ):
  19 |         self._send_callback = send_callback
  20 |         self._default_channel = default_channel
  21 |         self._default_chat_id = default_chat_id
  22 |         self._default_message_id = default_message_id
  23 |         self._sent_in_turn: bool = False
  24 | 
  25 |     def set_context(self, channel: str, chat_id: str, message_id: str | None = None) -> None:
  26 |         """Set the current message context."""
  27 |         self._default_channel = channel
  28 |         self._default_chat_id = chat_id
  29 |         self._default_message_id = message_id
  30 | 
  31 |     def set_send_callback(self, callback: Callable[[OutboundMessage], Awaitable[None]]) -> None:
  32 |         """Set the callback for sending messages."""
  33 |         self._send_callback = callback
  34 | 
  35 |     def start_turn(self) -> None:
  36 |         """Reset per-turn send tracking."""
  37 |         self._sent_in_turn = False
  38 | 
  39 |     @property
  40 |     def name(self) -> str:
  41 |         return "message"
  42 | 
  43 |     @property
  44 |     def description(self) -> str:
  45 |         return "Send a message to the user. Use this when you want to communicate something."
  46 | 
  47 |     @property
  48 |     def parameters(self) -> dict[str, Any]:
  49 |         return {
  50 |             "type": "object",
  51 |             "properties": {
  52 |                 "content": {
  53 |                     "type": "string",
  54 |                     "description": "The message content to send"
  55 |                 },
  56 |                 "channel": {
  57 |                     "type": "string",
  58 |                     "description": "Optional: target channel (telegram, discord, etc.)"
  59 |                 },
  60 |                 "chat_id": {
  61 |                     "type": "string",
  62 |                     "description": "Optional: target chat/user ID"
  63 |                 },
  64 |                 "media": {
  65 |                     "type": "array",
  66 |                     "items": {"type": "string"},
  67 |                     "description": "Optional: list of file paths to attach (images, audio, documents)"
  68 |                 }
  69 |             },
  70 |             "required": ["content"]
  71 |         }
  72 | 
  73 |     async def execute(
  74 |         self,
  75 |         content: str,
  76 |         channel: str | None = None,
  77 |         chat_id: str | None = None,
  78 |         message_id: str | None = None,
  79 |         media: list[str] | None = None,
  80 |         **kwargs: Any
  81 |     ) -> str:
  82 |         channel = channel or self._default_channel
  83 |         chat_id = chat_id or self._default_chat_id
  84 |         message_id = message_id or self._default_message_id
  85 | 
  86 |         if not channel or not chat_id:
  87 |             return "Error: No target channel/chat specified"
  88 | 
  89 |         if not self._send_callback:
  90 |             return "Error: Message sending not configured"
  91 | 
  92 |         msg = OutboundMessage(
  93 |             channel=channel,
  94 |             chat_id=chat_id,
  95 |             content=content,
  96 |             media=media or [],
  97 |             metadata={
  98 |                 "message_id": message_id,
  99 |             },
 100 |         )
 101 | 
 102 |         try:
 103 |             await self._send_callback(msg)
 104 |             if channel == self._default_channel and chat_id == self._default_chat_id:
 105 |                 self._sent_in_turn = True
 106 |             media_info = f" with {len(media)} attachments" if media else ""
 107 |             return f"Message sent to {channel}:{chat_id}{media_info}"
 108 |         except Exception as e:
 109 |             return f"Error sending message: {str(e)}"

```

`agent/tools/mcp.py`:

```py
   1 | """MCP client: connects to MCP servers and wraps their tools as native nanobot tools."""
   2 | 
   3 | import asyncio
   4 | from contextlib import AsyncExitStack
   5 | from typing import Any
   6 | 
   7 | import httpx
   8 | from loguru import logger
   9 | 
  10 | from nanobot.agent.tools.base import Tool
  11 | from nanobot.agent.tools.registry import ToolRegistry
  12 | 
  13 | 
  14 | class MCPToolWrapper(Tool):
  15 |     """Wraps a single MCP server tool as a nanobot Tool."""
  16 | 
  17 |     def __init__(self, session, server_name: str, tool_def, tool_timeout: int = 30):
  18 |         self._session = session
  19 |         self._original_name = tool_def.name
  20 |         self._name = f"mcp_{server_name}_{tool_def.name}"
  21 |         self._description = tool_def.description or tool_def.name
  22 |         self._parameters = tool_def.inputSchema or {"type": "object", "properties": {}}
  23 |         self._tool_timeout = tool_timeout
  24 | 
  25 |     @property
  26 |     def name(self) -> str:
  27 |         return self._name
  28 | 
  29 |     @property
  30 |     def description(self) -> str:
  31 |         return self._description
  32 | 
  33 |     @property
  34 |     def parameters(self) -> dict[str, Any]:
  35 |         return self._parameters
  36 | 
  37 |     async def execute(self, **kwargs: Any) -> str:
  38 |         from mcp import types
  39 | 
  40 |         try:
  41 |             result = await asyncio.wait_for(
  42 |                 self._session.call_tool(self._original_name, arguments=kwargs),
  43 |                 timeout=self._tool_timeout,
  44 |             )
  45 |         except asyncio.TimeoutError:
  46 |             logger.warning("MCP tool '{}' timed out after {}s", self._name, self._tool_timeout)
  47 |             return f"(MCP tool call timed out after {self._tool_timeout}s)"
  48 |         except asyncio.CancelledError:
  49 |             # MCP SDK's anyio cancel scopes can leak CancelledError on timeout/failure.
  50 |             # Re-raise only if our task was externally cancelled (e.g. /stop).
  51 |             task = asyncio.current_task()
  52 |             if task is not None and task.cancelling() > 0:
  53 |                 raise
  54 |             logger.warning("MCP tool '{}' was cancelled by server/SDK", self._name)
  55 |             return "(MCP tool call was cancelled)"
  56 |         except Exception as exc:
  57 |             logger.exception(
  58 |                 "MCP tool '{}' failed: {}: {}",
  59 |                 self._name,
  60 |                 type(exc).__name__,
  61 |                 exc,
  62 |             )
  63 |             return f"(MCP tool call failed: {type(exc).__name__})"
  64 | 
  65 |         parts = []
  66 |         for block in result.content:
  67 |             if isinstance(block, types.TextContent):
  68 |                 parts.append(block.text)
  69 |             else:
  70 |                 parts.append(str(block))
  71 |         return "\n".join(parts) or "(no output)"
  72 | 
  73 | 
  74 | async def connect_mcp_servers(
  75 |     mcp_servers: dict, registry: ToolRegistry, stack: AsyncExitStack
  76 | ) -> None:
  77 |     """Connect to configured MCP servers and register their tools."""
  78 |     from mcp import ClientSession, StdioServerParameters
  79 |     from mcp.client.sse import sse_client
  80 |     from mcp.client.stdio import stdio_client
  81 |     from mcp.client.streamable_http import streamable_http_client
  82 | 
  83 |     for name, cfg in mcp_servers.items():
  84 |         try:
  85 |             transport_type = cfg.type
  86 |             if not transport_type:
  87 |                 if cfg.command:
  88 |                     transport_type = "stdio"
  89 |                 elif cfg.url:
  90 |                     # Convention: URLs ending with /sse use SSE transport; others use streamableHttp
  91 |                     transport_type = (
  92 |                         "sse" if cfg.url.rstrip("/").endswith("/sse") else "streamableHttp"
  93 |                     )
  94 |                 else:
  95 |                     logger.warning("MCP server '{}': no command or url configured, skipping", name)
  96 |                     continue
  97 | 
  98 |             if transport_type == "stdio":
  99 |                 params = StdioServerParameters(
 100 |                     command=cfg.command, args=cfg.args, env=cfg.env or None
 101 |                 )
 102 |                 read, write = await stack.enter_async_context(stdio_client(params))
 103 |             elif transport_type == "sse":
 104 |                 def httpx_client_factory(
 105 |                     headers: dict[str, str] | None = None,
 106 |                     timeout: httpx.Timeout | None = None,
 107 |                     auth: httpx.Auth | None = None,
 108 |                 ) -> httpx.AsyncClient:
 109 |                     merged_headers = {**(cfg.headers or {}), **(headers or {})}
 110 |                     return httpx.AsyncClient(
 111 |                         headers=merged_headers or None,
 112 |                         follow_redirects=True,
 113 |                         timeout=timeout,
 114 |                         auth=auth,
 115 |                     )
 116 | 
 117 |                 read, write = await stack.enter_async_context(
 118 |                     sse_client(cfg.url, httpx_client_factory=httpx_client_factory)
 119 |                 )
 120 |             elif transport_type == "streamableHttp":
 121 |                 # Always provide an explicit httpx client so MCP HTTP transport does not
 122 |                 # inherit httpx's default 5s timeout and preempt the higher-level tool timeout.
 123 |                 http_client = await stack.enter_async_context(
 124 |                     httpx.AsyncClient(
 125 |                         headers=cfg.headers or None,
 126 |                         follow_redirects=True,
 127 |                         timeout=None,
 128 |                     )
 129 |                 )
 130 |                 read, write, _ = await stack.enter_async_context(
 131 |                     streamable_http_client(cfg.url, http_client=http_client)
 132 |                 )
 133 |             else:
 134 |                 logger.warning("MCP server '{}': unknown transport type '{}'", name, transport_type)
 135 |                 continue
 136 | 
 137 |             session = await stack.enter_async_context(ClientSession(read, write))
 138 |             await session.initialize()
 139 | 
 140 |             tools = await session.list_tools()
 141 |             enabled_tools = set(cfg.enabled_tools)
 142 |             allow_all_tools = "*" in enabled_tools
 143 |             registered_count = 0
 144 |             matched_enabled_tools: set[str] = set()
 145 |             available_raw_names = [tool_def.name for tool_def in tools.tools]
 146 |             available_wrapped_names = [f"mcp_{name}_{tool_def.name}" for tool_def in tools.tools]
 147 |             for tool_def in tools.tools:
 148 |                 wrapped_name = f"mcp_{name}_{tool_def.name}"
 149 |                 if (
 150 |                     not allow_all_tools
 151 |                     and tool_def.name not in enabled_tools
 152 |                     and wrapped_name not in enabled_tools
 153 |                 ):
 154 |                     logger.debug(
 155 |                         "MCP: skipping tool '{}' from server '{}' (not in enabledTools)",
 156 |                         wrapped_name,
 157 |                         name,
 158 |                     )
 159 |                     continue
 160 |                 wrapper = MCPToolWrapper(session, name, tool_def, tool_timeout=cfg.tool_timeout)
 161 |                 registry.register(wrapper)
 162 |                 logger.debug("MCP: registered tool '{}' from server '{}'", wrapper.name, name)
 163 |                 registered_count += 1
 164 |                 if enabled_tools:
 165 |                     if tool_def.name in enabled_tools:
 166 |                         matched_enabled_tools.add(tool_def.name)
 167 |                     if wrapped_name in enabled_tools:
 168 |                         matched_enabled_tools.add(wrapped_name)
 169 | 
 170 |             if enabled_tools and not allow_all_tools:
 171 |                 unmatched_enabled_tools = sorted(enabled_tools - matched_enabled_tools)
 172 |                 if unmatched_enabled_tools:
 173 |                     logger.warning(
 174 |                         "MCP server '{}': enabledTools entries not found: {}. Available raw names: {}. "
 175 |                         "Available wrapped names: {}",
 176 |                         name,
 177 |                         ", ".join(unmatched_enabled_tools),
 178 |                         ", ".join(available_raw_names) or "(none)",
 179 |                         ", ".join(available_wrapped_names) or "(none)",
 180 |                     )
 181 | 
 182 |             logger.info("MCP server '{}': connected, {} tools registered", name, registered_count)
 183 |         except Exception as e:
 184 |             logger.error("MCP server '{}': failed to connect: {}", name, e)

```

`agent/tools/web.py`:

```py
   1 | """Web tools: web_search and web_fetch."""
   2 | 
   3 | from __future__ import annotations
   4 | 
   5 | import asyncio
   6 | import html
   7 | import json
   8 | import os
   9 | import re
  10 | from typing import TYPE_CHECKING, Any
  11 | from urllib.parse import urlparse
  12 | 
  13 | import httpx
  14 | from loguru import logger
  15 | 
  16 | from nanobot.agent.tools.base import Tool
  17 | 
  18 | if TYPE_CHECKING:
  19 |     from nanobot.config.schema import WebSearchConfig
  20 | 
  21 | # Shared constants
  22 | USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_2) AppleWebKit/537.36"
  23 | MAX_REDIRECTS = 5  # Limit redirects to prevent DoS attacks
  24 | 
  25 | 
  26 | def _strip_tags(text: str) -> str:
  27 |     """Remove HTML tags and decode entities."""
  28 |     text = re.sub(r'<script[\s\S]*?</script>', '', text, flags=re.I)
  29 |     text = re.sub(r'<style[\s\S]*?</style>', '', text, flags=re.I)
  30 |     text = re.sub(r'<[^>]+>', '', text)
  31 |     return html.unescape(text).strip()
  32 | 
  33 | 
  34 | def _normalize(text: str) -> str:
  35 |     """Normalize whitespace."""
  36 |     text = re.sub(r'[ \t]+', ' ', text)
  37 |     return re.sub(r'\n{3,}', '\n\n', text).strip()
  38 | 
  39 | 
  40 | def _validate_url(url: str) -> tuple[bool, str]:
  41 |     """Validate URL: must be http(s) with valid domain."""
  42 |     try:
  43 |         p = urlparse(url)
  44 |         if p.scheme not in ('http', 'https'):
  45 |             return False, f"Only http/https allowed, got '{p.scheme or 'none'}'"
  46 |         if not p.netloc:
  47 |             return False, "Missing domain"
  48 |         return True, ""
  49 |     except Exception as e:
  50 |         return False, str(e)
  51 | 
  52 | 
  53 | def _format_results(query: str, items: list[dict[str, Any]], n: int) -> str:
  54 |     """Format provider results into shared plaintext output."""
  55 |     if not items:
  56 |         return f"No results for: {query}"
  57 |     lines = [f"Results for: {query}\n"]
  58 |     for i, item in enumerate(items[:n], 1):
  59 |         title = _normalize(_strip_tags(item.get("title", "")))
  60 |         snippet = _normalize(_strip_tags(item.get("content", "")))
  61 |         lines.append(f"{i}. {title}\n   {item.get('url', '')}")
  62 |         if snippet:
  63 |             lines.append(f"   {snippet}")
  64 |     return "\n".join(lines)
  65 | 
  66 | 
  67 | class WebSearchTool(Tool):
  68 |     """Search the web using configured provider."""
  69 | 
  70 |     name = "web_search"
  71 |     description = "Search the web. Returns titles, URLs, and snippets."
  72 |     parameters = {
  73 |         "type": "object",
  74 |         "properties": {
  75 |             "query": {"type": "string", "description": "Search query"},
  76 |             "count": {"type": "integer", "description": "Results (1-10)", "minimum": 1, "maximum": 10},
  77 |         },
  78 |         "required": ["query"],
  79 |     }
  80 | 
  81 |     def __init__(self, config: WebSearchConfig | None = None, proxy: str | None = None):
  82 |         from nanobot.config.schema import WebSearchConfig
  83 | 
  84 |         self.config = config if config is not None else WebSearchConfig()
  85 |         self.proxy = proxy
  86 | 
  87 |     async def execute(self, query: str, count: int | None = None, **kwargs: Any) -> str:
  88 |         provider = self.config.provider.strip().lower() or "brave"
  89 |         n = min(max(count or self.config.max_results, 1), 10)
  90 | 
  91 |         if provider == "duckduckgo":
  92 |             return await self._search_duckduckgo(query, n)
  93 |         elif provider == "tavily":
  94 |             return await self._search_tavily(query, n)
  95 |         elif provider == "searxng":
  96 |             return await self._search_searxng(query, n)
  97 |         elif provider == "jina":
  98 |             return await self._search_jina(query, n)
  99 |         elif provider == "brave":
 100 |             return await self._search_brave(query, n)
 101 |         else:
 102 |             return f"Error: unknown search provider '{provider}'"
 103 | 
 104 |     async def _search_brave(self, query: str, n: int) -> str:
 105 |         api_key = self.config.api_key or os.environ.get("BRAVE_API_KEY", "")
 106 |         if not api_key:
 107 |             logger.warning("BRAVE_API_KEY not set, falling back to DuckDuckGo")
 108 |             return await self._search_duckduckgo(query, n)
 109 |         try:
 110 |             async with httpx.AsyncClient(proxy=self.proxy) as client:
 111 |                 r = await client.get(
 112 |                     "https://api.search.brave.com/res/v1/web/search",
 113 |                     params={"q": query, "count": n},
 114 |                     headers={"Accept": "application/json", "X-Subscription-Token": api_key},
 115 |                     timeout=10.0,
 116 |                 )
 117 |                 r.raise_for_status()
 118 |             items = [
 119 |                 {"title": x.get("title", ""), "url": x.get("url", ""), "content": x.get("description", "")}
 120 |                 for x in r.json().get("web", {}).get("results", [])
 121 |             ]
 122 |             return _format_results(query, items, n)
 123 |         except Exception as e:
 124 |             return f"Error: {e}"
 125 | 
 126 |     async def _search_tavily(self, query: str, n: int) -> str:
 127 |         api_key = self.config.api_key or os.environ.get("TAVILY_API_KEY", "")
 128 |         if not api_key:
 129 |             logger.warning("TAVILY_API_KEY not set, falling back to DuckDuckGo")
 130 |             return await self._search_duckduckgo(query, n)
 131 |         try:
 132 |             async with httpx.AsyncClient(proxy=self.proxy) as client:
 133 |                 r = await client.post(
 134 |                     "https://api.tavily.com/search",
 135 |                     headers={"Authorization": f"Bearer {api_key}"},
 136 |                     json={"query": query, "max_results": n},
 137 |                     timeout=15.0,
 138 |                 )
 139 |                 r.raise_for_status()
 140 |             return _format_results(query, r.json().get("results", []), n)
 141 |         except Exception as e:
 142 |             return f"Error: {e}"
 143 | 
 144 |     async def _search_searxng(self, query: str, n: int) -> str:
 145 |         base_url = (self.config.base_url or os.environ.get("SEARXNG_BASE_URL", "")).strip()
 146 |         if not base_url:
 147 |             logger.warning("SEARXNG_BASE_URL not set, falling back to DuckDuckGo")
 148 |             return await self._search_duckduckgo(query, n)
 149 |         endpoint = f"{base_url.rstrip('/')}/search"
 150 |         is_valid, error_msg = _validate_url(endpoint)
 151 |         if not is_valid:
 152 |             return f"Error: invalid SearXNG URL: {error_msg}"
 153 |         try:
 154 |             async with httpx.AsyncClient(proxy=self.proxy) as client:
 155 |                 r = await client.get(
 156 |                     endpoint,
 157 |                     params={"q": query, "format": "json"},
 158 |                     headers={"User-Agent": USER_AGENT},
 159 |                     timeout=10.0,
 160 |                 )
 161 |                 r.raise_for_status()
 162 |             return _format_results(query, r.json().get("results", []), n)
 163 |         except Exception as e:
 164 |             return f"Error: {e}"
 165 | 
 166 |     async def _search_jina(self, query: str, n: int) -> str:
 167 |         api_key = self.config.api_key or os.environ.get("JINA_API_KEY", "")
 168 |         if not api_key:
 169 |             logger.warning("JINA_API_KEY not set, falling back to DuckDuckGo")
 170 |             return await self._search_duckduckgo(query, n)
 171 |         try:
 172 |             headers = {"Accept": "application/json", "Authorization": f"Bearer {api_key}"}
 173 |             async with httpx.AsyncClient(proxy=self.proxy) as client:
 174 |                 r = await client.get(
 175 |                     f"https://s.jina.ai/",
 176 |                     params={"q": query},
 177 |                     headers=headers,
 178 |                     timeout=15.0,
 179 |                 )
 180 |                 r.raise_for_status()
 181 |             data = r.json().get("data", [])[:n]
 182 |             items = [
 183 |                 {"title": d.get("title", ""), "url": d.get("url", ""), "content": d.get("content", "")[:500]}
 184 |                 for d in data
 185 |             ]
 186 |             return _format_results(query, items, n)
 187 |         except Exception as e:
 188 |             return f"Error: {e}"
 189 | 
 190 |     async def _search_duckduckgo(self, query: str, n: int) -> str:
 191 |         try:
 192 |             from ddgs import DDGS
 193 | 
 194 |             ddgs = DDGS(timeout=10)
 195 |             raw = await asyncio.to_thread(ddgs.text, query, max_results=n)
 196 |             if not raw:
 197 |                 return f"No results for: {query}"
 198 |             items = [
 199 |                 {"title": r.get("title", ""), "url": r.get("href", ""), "content": r.get("body", "")}
 200 |                 for r in raw
 201 |             ]
 202 |             return _format_results(query, items, n)
 203 |         except Exception as e:
 204 |             logger.warning("DuckDuckGo search failed: {}", e)
 205 |             return f"Error: DuckDuckGo search failed ({e})"
 206 | 
 207 | 
 208 | class WebFetchTool(Tool):
 209 |     """Fetch and extract content from a URL."""
 210 | 
 211 |     name = "web_fetch"
 212 |     description = "Fetch URL and extract readable content (HTML → markdown/text)."
 213 |     parameters = {
 214 |         "type": "object",
 215 |         "properties": {
 216 |             "url": {"type": "string", "description": "URL to fetch"},
 217 |             "extractMode": {"type": "string", "enum": ["markdown", "text"], "default": "markdown"},
 218 |             "maxChars": {"type": "integer", "minimum": 100},
 219 |         },
 220 |         "required": ["url"],
 221 |     }
 222 | 
 223 |     def __init__(self, max_chars: int = 50000, proxy: str | None = None):
 224 |         self.max_chars = max_chars
 225 |         self.proxy = proxy
 226 | 
 227 |     async def execute(self, url: str, extractMode: str = "markdown", maxChars: int | None = None, **kwargs: Any) -> str:
 228 |         max_chars = maxChars or self.max_chars
 229 |         is_valid, error_msg = _validate_url(url)
 230 |         if not is_valid:
 231 |             return json.dumps({"error": f"URL validation failed: {error_msg}", "url": url}, ensure_ascii=False)
 232 | 
 233 |         result = await self._fetch_jina(url, max_chars)
 234 |         if result is None:
 235 |             result = await self._fetch_readability(url, extractMode, max_chars)
 236 |         return result
 237 | 
 238 |     async def _fetch_jina(self, url: str, max_chars: int) -> str | None:
 239 |         """Try fetching via Jina Reader API. Returns None on failure."""
 240 |         try:
 241 |             headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
 242 |             jina_key = os.environ.get("JINA_API_KEY", "")
 243 |             if jina_key:
 244 |                 headers["Authorization"] = f"Bearer {jina_key}"
 245 |             async with httpx.AsyncClient(proxy=self.proxy, timeout=20.0) as client:
 246 |                 r = await client.get(f"https://r.jina.ai/{url}", headers=headers)
 247 |                 if r.status_code == 429:
 248 |                     logger.debug("Jina Reader rate limited, falling back to readability")
 249 |                     return None
 250 |                 r.raise_for_status()
 251 | 
 252 |             data = r.json().get("data", {})
 253 |             title = data.get("title", "")
 254 |             text = data.get("content", "")
 255 |             if not text:
 256 |                 return None
 257 | 
 258 |             if title:
 259 |                 text = f"# {title}\n\n{text}"
 260 |             truncated = len(text) > max_chars
 261 |             if truncated:
 262 |                 text = text[:max_chars]
 263 | 
 264 |             return json.dumps({
 265 |                 "url": url, "finalUrl": data.get("url", url), "status": r.status_code,
 266 |                 "extractor": "jina", "truncated": truncated, "length": len(text), "text": text,
 267 |             }, ensure_ascii=False)
 268 |         except Exception as e:
 269 |             logger.debug("Jina Reader failed for {}, falling back to readability: {}", url, e)
 270 |             return None
 271 | 
 272 |     async def _fetch_readability(self, url: str, extract_mode: str, max_chars: int) -> str:
 273 |         """Local fallback using readability-lxml."""
 274 |         from readability import Document
 275 | 
 276 |         try:
 277 |             async with httpx.AsyncClient(
 278 |                 follow_redirects=True,
 279 |                 max_redirects=MAX_REDIRECTS,
 280 |                 timeout=30.0,
 281 |                 proxy=self.proxy,
 282 |             ) as client:
 283 |                 r = await client.get(url, headers={"User-Agent": USER_AGENT})
 284 |                 r.raise_for_status()
 285 | 
 286 |             ctype = r.headers.get("content-type", "")
 287 | 
 288 |             if "application/json" in ctype:
 289 |                 text, extractor = json.dumps(r.json(), indent=2, ensure_ascii=False), "json"
 290 |             elif "text/html" in ctype or r.text[:256].lower().startswith(("<!doctype", "<html")):
 291 |                 doc = Document(r.text)
 292 |                 content = self._to_markdown(doc.summary()) if extract_mode == "markdown" else _strip_tags(doc.summary())
 293 |                 text = f"# {doc.title()}\n\n{content}" if doc.title() else content
 294 |                 extractor = "readability"
 295 |             else:
 296 |                 text, extractor = r.text, "raw"
 297 | 
 298 |             truncated = len(text) > max_chars
 299 |             if truncated:
 300 |                 text = text[:max_chars]
 301 | 
 302 |             return json.dumps({
 303 |                 "url": url, "finalUrl": str(r.url), "status": r.status_code,
 304 |                 "extractor": extractor, "truncated": truncated, "length": len(text), "text": text,
 305 |             }, ensure_ascii=False)
 306 |         except httpx.ProxyError as e:
 307 |             logger.error("WebFetch proxy error for {}: {}", url, e)
 308 |             return json.dumps({"error": f"Proxy error: {e}", "url": url}, ensure_ascii=False)
 309 |         except Exception as e:
 310 |             logger.error("WebFetch error for {}: {}", url, e)
 311 |             return json.dumps({"error": str(e), "url": url}, ensure_ascii=False)
 312 | 
 313 |     def _to_markdown(self, html_content: str) -> str:
 314 |         """Convert HTML to markdown."""
 315 |         text = re.sub(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>',
 316 |                       lambda m: f'[{_strip_tags(m[2])}]({m[1]})', html_content, flags=re.I)
 317 |         text = re.sub(r'<h([1-6])[^>]*>([\s\S]*?)</h\1>',
 318 |                       lambda m: f'\n{"#" * int(m[1])} {_strip_tags(m[2])}\n', text, flags=re.I)
 319 |         text = re.sub(r'<li[^>]*>([\s\S]*?)</li>', lambda m: f'\n- {_strip_tags(m[1])}', text, flags=re.I)
 320 |         text = re.sub(r'</(p|div|section|article)>', '\n\n', text, flags=re.I)
 321 |         text = re.sub(r'<(br|hr)\s*/?>', '\n', text, flags=re.I)
 322 |         return _normalize(_strip_tags(text))

```

`agent/tools/registry.py`:

```py
   1 | """Tool registry for dynamic tool management."""
   2 | 
   3 | from typing import Any
   4 | 
   5 | from nanobot.agent.tools.base import Tool
   6 | 
   7 | 
   8 | class ToolRegistry:
   9 |     """
  10 |     Registry for agent tools.
  11 | 
  12 |     Allows dynamic registration and execution of tools.
  13 |     """
  14 | 
  15 |     def __init__(self):
  16 |         self._tools: dict[str, Tool] = {}
  17 | 
  18 |     def register(self, tool: Tool) -> None:
  19 |         """Register a tool."""
  20 |         self._tools[tool.name] = tool
  21 | 
  22 |     def unregister(self, name: str) -> None:
  23 |         """Unregister a tool by name."""
  24 |         self._tools.pop(name, None)
  25 | 
  26 |     def get(self, name: str) -> Tool | None:
  27 |         """Get a tool by name."""
  28 |         return self._tools.get(name)
  29 | 
  30 |     def has(self, name: str) -> bool:
  31 |         """Check if a tool is registered."""
  32 |         return name in self._tools
  33 | 
  34 |     def get_definitions(self) -> list[dict[str, Any]]:
  35 |         """Get all tool definitions in OpenAI format."""
  36 |         return [tool.to_schema() for tool in self._tools.values()]
  37 | 
  38 |     async def execute(self, name: str, params: dict[str, Any]) -> str:
  39 |         """Execute a tool by name with given parameters."""
  40 |         _HINT = "\n\n[Analyze the error above and try a different approach.]"
  41 | 
  42 |         tool = self._tools.get(name)
  43 |         if not tool:
  44 |             return f"Error: Tool '{name}' not found. Available: {', '.join(self.tool_names)}"
  45 | 
  46 |         try:
  47 |             # Attempt to cast parameters to match schema types
  48 |             params = tool.cast_params(params)
  49 |             
  50 |             # Validate parameters
  51 |             errors = tool.validate_params(params)
  52 |             if errors:
  53 |                 return f"Error: Invalid parameters for tool '{name}': " + "; ".join(errors) + _HINT
  54 |             result = await tool.execute(**params)
  55 |             if isinstance(result, str) and result.startswith("Error"):
  56 |                 return result + _HINT
  57 |             return result
  58 |         except Exception as e:
  59 |             return f"Error executing {name}: {str(e)}" + _HINT
  60 | 
  61 |     @property
  62 |     def tool_names(self) -> list[str]:
  63 |         """Get list of registered tool names."""
  64 |         return list(self._tools.keys())
  65 | 
  66 |     def __len__(self) -> int:
  67 |         return len(self._tools)
  68 | 
  69 |     def __contains__(self, name: str) -> bool:
  70 |         return name in self._tools

```

`agent/memory.py`:

```py
   1 | """Memory system for persistent agent memory."""
   2 | 
   3 | from __future__ import annotations
   4 | 
   5 | import asyncio
   6 | import json
   7 | import weakref
   8 | from datetime import datetime
   9 | from pathlib import Path
  10 | from typing import TYPE_CHECKING, Any, Callable
  11 | 
  12 | from loguru import logger
  13 | 
  14 | from nanobot.utils.helpers import ensure_dir, estimate_message_tokens, estimate_prompt_tokens_chain
  15 | 
  16 | if TYPE_CHECKING:
  17 |     from nanobot.providers.base import LLMProvider
  18 |     from nanobot.session.manager import Session, SessionManager
  19 | 
  20 | 
  21 | _SAVE_MEMORY_TOOL = [
  22 |     {
  23 |         "type": "function",
  24 |         "function": {
  25 |             "name": "save_memory",
  26 |             "description": "Save the memory consolidation result to persistent storage.",
  27 |             "parameters": {
  28 |                 "type": "object",
  29 |                 "properties": {
  30 |                     "history_entry": {
  31 |                         "type": "string",
  32 |                         "description": "A paragraph summarizing key events/decisions/topics. "
  33 |                         "Start with [YYYY-MM-DD HH:MM]. Include detail useful for grep search.",
  34 |                     },
  35 |                     "memory_update": {
  36 |                         "type": "string",
  37 |                         "description": "Full updated long-term memory as markdown. Include all existing "
  38 |                         "facts plus new ones. Return unchanged if nothing new.",
  39 |                     },
  40 |                 },
  41 |                 "required": ["history_entry", "memory_update"],
  42 |             },
  43 |         },
  44 |     }
  45 | ]
  46 | 
  47 | 
  48 | def _ensure_text(value: Any) -> str:
  49 |     """Normalize tool-call payload values to text for file storage."""
  50 |     return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
  51 | 
  52 | 
  53 | def _normalize_save_memory_args(args: Any) -> dict[str, Any] | None:
  54 |     """Normalize provider tool-call arguments to the expected dict shape."""
  55 |     if isinstance(args, str):
  56 |         args = json.loads(args)
  57 |     if isinstance(args, list):
  58 |         return args[0] if args and isinstance(args[0], dict) else None
  59 |     return args if isinstance(args, dict) else None
  60 | 
  61 | _TOOL_CHOICE_ERROR_MARKERS = (
  62 |     "tool_choice",
  63 |     "toolchoice",
  64 |     "does not support",
  65 |     'should be ["none", "auto"]',
  66 | )
  67 | 
  68 | 
  69 | def _is_tool_choice_unsupported(content: str | None) -> bool:
  70 |     """Detect provider errors caused by forced tool_choice being unsupported."""
  71 |     text = (content or "").lower()
  72 |     return any(m in text for m in _TOOL_CHOICE_ERROR_MARKERS)
  73 | 
  74 | 
  75 | class MemoryStore:
  76 |     """Two-layer memory: MEMORY.md (long-term facts) + HISTORY.md (grep-searchable log)."""
  77 | 
  78 |     _MAX_FAILURES_BEFORE_RAW_ARCHIVE = 3
  79 | 
  80 |     def __init__(self, workspace: Path):
  81 |         self.memory_dir = ensure_dir(workspace / "memory")
  82 |         self.memory_file = self.memory_dir / "MEMORY.md"
  83 |         self.history_file = self.memory_dir / "HISTORY.md"
  84 |         self._consecutive_failures = 0
  85 | 
  86 |     def read_long_term(self) -> str:
  87 |         if self.memory_file.exists():
  88 |             return self.memory_file.read_text(encoding="utf-8")
  89 |         return ""
  90 | 
  91 |     def write_long_term(self, content: str) -> None:
  92 |         self.memory_file.write_text(content, encoding="utf-8")
  93 | 
  94 |     def append_history(self, entry: str) -> None:
  95 |         with open(self.history_file, "a", encoding="utf-8") as f:
  96 |             f.write(entry.rstrip() + "\n\n")
  97 | 
  98 |     def get_memory_context(self) -> str:
  99 |         long_term = self.read_long_term()
 100 |         return f"## Long-term Memory\n{long_term}" if long_term else ""
 101 | 
 102 |     @staticmethod
 103 |     def _format_messages(messages: list[dict]) -> str:
 104 |         lines = []
 105 |         for message in messages:
 106 |             if not message.get("content"):
 107 |                 continue
 108 |             tools = f" [tools: {', '.join(message['tools_used'])}]" if message.get("tools_used") else ""
 109 |             lines.append(
 110 |                 f"[{message.get('timestamp', '?')[:16]}] {message['role'].upper()}{tools}: {message['content']}"
 111 |             )
 112 |         return "\n".join(lines)
 113 | 
 114 |     async def consolidate(
 115 |         self,
 116 |         messages: list[dict],
 117 |         provider: LLMProvider,
 118 |         model: str,
 119 |     ) -> bool:
 120 |         """Consolidate the provided message chunk into MEMORY.md + HISTORY.md."""
 121 |         if not messages:
 122 |             return True
 123 | 
 124 |         current_memory = self.read_long_term()
 125 |         prompt = f"""Process this conversation and call the save_memory tool with your consolidation.
 126 | 
 127 | ## Current Long-term Memory
 128 | {current_memory or "(empty)"}
 129 | 
 130 | ## Conversation to Process
 131 | {self._format_messages(messages)}"""
 132 | 
 133 |         chat_messages = [
 134 |             {"role": "system", "content": "You are a memory consolidation agent. Call the save_memory tool with your consolidation of the conversation."},
 135 |             {"role": "user", "content": prompt},
 136 |         ]
 137 | 
 138 |         try:
 139 |             forced = {"type": "function", "function": {"name": "save_memory"}}
 140 |             response = await provider.chat_with_retry(
 141 |                 messages=chat_messages,
 142 |                 tools=_SAVE_MEMORY_TOOL,
 143 |                 model=model,
 144 |                 tool_choice=forced,
 145 |             )
 146 | 
 147 |             if response.finish_reason == "error" and _is_tool_choice_unsupported(
 148 |                 response.content
 149 |             ):
 150 |                 logger.warning("Forced tool_choice unsupported, retrying with auto")
 151 |                 response = await provider.chat_with_retry(
 152 |                     messages=chat_messages,
 153 |                     tools=_SAVE_MEMORY_TOOL,
 154 |                     model=model,
 155 |                     tool_choice="auto",
 156 |                 )
 157 | 
 158 |             if not response.has_tool_calls:
 159 |                 logger.warning(
 160 |                     "Memory consolidation: LLM did not call save_memory "
 161 |                     "(finish_reason={}, content_len={}, content_preview={})",
 162 |                     response.finish_reason,
 163 |                     len(response.content or ""),
 164 |                     (response.content or "")[:200],
 165 |                 )
 166 |                 return self._fail_or_raw_archive(messages)
 167 | 
 168 |             args = _normalize_save_memory_args(response.tool_calls[0].arguments)
 169 |             if args is None:
 170 |                 logger.warning("Memory consolidation: unexpected save_memory arguments")
 171 |                 return self._fail_or_raw_archive(messages)
 172 | 
 173 |             if "history_entry" not in args or "memory_update" not in args:
 174 |                 logger.warning("Memory consolidation: save_memory payload missing required fields")
 175 |                 return self._fail_or_raw_archive(messages)
 176 | 
 177 |             entry = args["history_entry"]
 178 |             update = args["memory_update"]
 179 | 
 180 |             if entry is None or update is None:
 181 |                 logger.warning("Memory consolidation: save_memory payload contains null required fields")
 182 |                 return self._fail_or_raw_archive(messages)
 183 | 
 184 |             entry = _ensure_text(entry).strip()
 185 |             if not entry:
 186 |                 logger.warning("Memory consolidation: history_entry is empty after normalization")
 187 |                 return self._fail_or_raw_archive(messages)
 188 | 
 189 |             self.append_history(entry)
 190 |             update = _ensure_text(update)
 191 |             if update != current_memory:
 192 |                 self.write_long_term(update)
 193 | 
 194 |             self._consecutive_failures = 0
 195 |             logger.info("Memory consolidation done for {} messages", len(messages))
 196 |             return True
 197 |         except Exception:
 198 |             logger.exception("Memory consolidation failed")
 199 |             return self._fail_or_raw_archive(messages)
 200 | 
 201 |     def _fail_or_raw_archive(self, messages: list[dict]) -> bool:
 202 |         """Increment failure count; after threshold, raw-archive messages and return True."""
 203 |         self._consecutive_failures += 1
 204 |         if self._consecutive_failures < self._MAX_FAILURES_BEFORE_RAW_ARCHIVE:
 205 |             return False
 206 |         self._raw_archive(messages)
 207 |         self._consecutive_failures = 0
 208 |         return True
 209 | 
 210 |     def _raw_archive(self, messages: list[dict]) -> None:
 211 |         """Fallback: dump raw messages to HISTORY.md without LLM summarization."""
 212 |         ts = datetime.now().strftime("%Y-%m-%d %H:%M")
 213 |         self.append_history(
 214 |             f"[{ts}] [RAW] {len(messages)} messages\n"
 215 |             f"{self._format_messages(messages)}"
 216 |         )
 217 |         logger.warning(
 218 |             "Memory consolidation degraded: raw-archived {} messages", len(messages)
 219 |         )
 220 | 
 221 | 
 222 | class MemoryConsolidator:
 223 |     """Owns consolidation policy, locking, and session offset updates."""
 224 | 
 225 |     _MAX_CONSOLIDATION_ROUNDS = 5
 226 | 
 227 |     def __init__(
 228 |         self,
 229 |         workspace: Path,
 230 |         provider: LLMProvider,
 231 |         model: str,
 232 |         sessions: SessionManager,
 233 |         context_window_tokens: int,
 234 |         build_messages: Callable[..., list[dict[str, Any]]],
 235 |         get_tool_definitions: Callable[[], list[dict[str, Any]]],
 236 |     ):
 237 |         self.store = MemoryStore(workspace)
 238 |         self.provider = provider
 239 |         self.model = model
 240 |         self.sessions = sessions
 241 |         self.context_window_tokens = context_window_tokens
 242 |         self._build_messages = build_messages
 243 |         self._get_tool_definitions = get_tool_definitions
 244 |         self._locks: weakref.WeakValueDictionary[str, asyncio.Lock] = weakref.WeakValueDictionary()
 245 | 
 246 |     def get_lock(self, session_key: str) -> asyncio.Lock:
 247 |         """Return the shared consolidation lock for one session."""
 248 |         return self._locks.setdefault(session_key, asyncio.Lock())
 249 | 
 250 |     async def consolidate_messages(self, messages: list[dict[str, object]]) -> bool:
 251 |         """Archive a selected message chunk into persistent memory."""
 252 |         return await self.store.consolidate(messages, self.provider, self.model)
 253 | 
 254 |     def pick_consolidation_boundary(
 255 |         self,
 256 |         session: Session,
 257 |         tokens_to_remove: int,
 258 |     ) -> tuple[int, int] | None:
 259 |         """Pick a user-turn boundary that removes enough old prompt tokens."""
 260 |         start = session.last_consolidated
 261 |         if start >= len(session.messages) or tokens_to_remove <= 0:
 262 |             return None
 263 | 
 264 |         removed_tokens = 0
 265 |         last_boundary: tuple[int, int] | None = None
 266 |         for idx in range(start, len(session.messages)):
 267 |             message = session.messages[idx]
 268 |             if idx > start and message.get("role") == "user":
 269 |                 last_boundary = (idx, removed_tokens)
 270 |                 if removed_tokens >= tokens_to_remove:
 271 |                     return last_boundary
 272 |             removed_tokens += estimate_message_tokens(message)
 273 | 
 274 |         return last_boundary
 275 | 
 276 |     def estimate_session_prompt_tokens(self, session: Session) -> tuple[int, str]:
 277 |         """Estimate current prompt size for the normal session history view."""
 278 |         history = session.get_history(max_messages=0)
 279 |         channel, chat_id = (session.key.split(":", 1) if ":" in session.key else (None, None))
 280 |         probe_messages = self._build_messages(
 281 |             history=history,
 282 |             current_message="[token-probe]",
 283 |             channel=channel,
 284 |             chat_id=chat_id,
 285 |         )
 286 |         return estimate_prompt_tokens_chain(
 287 |             self.provider,
 288 |             self.model,
 289 |             probe_messages,
 290 |             self._get_tool_definitions(),
 291 |         )
 292 | 
 293 |     async def archive_unconsolidated(self, session: Session) -> bool:
 294 |         """Archive the full unconsolidated tail for /new-style session rollover."""
 295 |         lock = self.get_lock(session.key)
 296 |         async with lock:
 297 |             snapshot = session.messages[session.last_consolidated:]
 298 |             if not snapshot:
 299 |                 return True
 300 |             return await self.consolidate_messages(snapshot)
 301 | 
 302 |     async def maybe_consolidate_by_tokens(self, session: Session) -> None:
 303 |         """Loop: archive old messages until prompt fits within half the context window."""
 304 |         if not session.messages or self.context_window_tokens <= 0:
 305 |             return
 306 | 
 307 |         lock = self.get_lock(session.key)
 308 |         async with lock:
 309 |             target = self.context_window_tokens // 2
 310 |             estimated, source = self.estimate_session_prompt_tokens(session)
 311 |             if estimated <= 0:
 312 |                 return
 313 |             if estimated < self.context_window_tokens:
 314 |                 logger.debug(
 315 |                     "Token consolidation idle {}: {}/{} via {}",
 316 |                     session.key,
 317 |                     estimated,
 318 |                     self.context_window_tokens,
 319 |                     source,
 320 |                 )
 321 |                 return
 322 | 
 323 |             for round_num in range(self._MAX_CONSOLIDATION_ROUNDS):
 324 |                 if estimated <= target:
 325 |                     return
 326 | 
 327 |                 boundary = self.pick_consolidation_boundary(session, max(1, estimated - target))
 328 |                 if boundary is None:
 329 |                     logger.debug(
 330 |                         "Token consolidation: no safe boundary for {} (round {})",
 331 |                         session.key,
 332 |                         round_num,
 333 |                     )
 334 |                     return
 335 | 
 336 |                 end_idx = boundary[0]
 337 |                 chunk = session.messages[session.last_consolidated:end_idx]
 338 |                 if not chunk:
 339 |                     return
 340 | 
 341 |                 logger.info(
 342 |                     "Token consolidation round {} for {}: {}/{} via {}, chunk={} msgs",
 343 |                     round_num,
 344 |                     session.key,
 345 |                     estimated,
 346 |                     self.context_window_tokens,
 347 |                     source,
 348 |                     len(chunk),
 349 |                 )
 350 |                 if not await self.consolidate_messages(chunk):
 351 |                     return
 352 |                 session.last_consolidated = end_idx
 353 |                 self.sessions.save(session)
 354 | 
 355 |                 estimated, source = self.estimate_session_prompt_tokens(session)
 356 |                 if estimated <= 0:
 357 |                     return

```

`agent/subagent.py`:

```py
   1 | """Subagent manager for background task execution."""
   2 | 
   3 | import asyncio
   4 | import json
   5 | import uuid
   6 | from pathlib import Path
   7 | from typing import Any
   8 | 
   9 | from loguru import logger
  10 | 
  11 | from nanobot.agent.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
  12 | from nanobot.agent.tools.registry import ToolRegistry
  13 | from nanobot.agent.tools.shell import ExecTool
  14 | from nanobot.agent.tools.web import WebFetchTool, WebSearchTool
  15 | from nanobot.bus.events import InboundMessage
  16 | from nanobot.bus.queue import MessageBus
  17 | from nanobot.config.schema import ExecToolConfig
  18 | from nanobot.providers.base import LLMProvider
  19 | from nanobot.utils.helpers import build_assistant_message
  20 | 
  21 | 
  22 | class SubagentManager:
  23 |     """Manages background subagent execution."""
  24 | 
  25 |     def __init__(
  26 |         self,
  27 |         provider: LLMProvider,
  28 |         workspace: Path,
  29 |         bus: MessageBus,
  30 |         model: str | None = None,
  31 |         web_search_config: "WebSearchConfig | None" = None,
  32 |         web_proxy: str | None = None,
  33 |         exec_config: "ExecToolConfig | None" = None,
  34 |         restrict_to_workspace: bool = False,
  35 |     ):
  36 |         from nanobot.config.schema import ExecToolConfig, WebSearchConfig
  37 | 
  38 |         self.provider = provider
  39 |         self.workspace = workspace
  40 |         self.bus = bus
  41 |         self.model = model or provider.get_default_model()
  42 |         self.web_search_config = web_search_config or WebSearchConfig()
  43 |         self.web_proxy = web_proxy
  44 |         self.exec_config = exec_config or ExecToolConfig()
  45 |         self.restrict_to_workspace = restrict_to_workspace
  46 |         self._running_tasks: dict[str, asyncio.Task[None]] = {}
  47 |         self._session_tasks: dict[str, set[str]] = {}  # session_key -> {task_id, ...}
  48 | 
  49 |     async def spawn(
  50 |         self,
  51 |         task: str,
  52 |         label: str | None = None,
  53 |         origin_channel: str = "cli",
  54 |         origin_chat_id: str = "direct",
  55 |         session_key: str | None = None,
  56 |     ) -> str:
  57 |         """Spawn a subagent to execute a task in the background."""
  58 |         task_id = str(uuid.uuid4())[:8]
  59 |         display_label = label or task[:30] + ("..." if len(task) > 30 else "")
  60 |         origin = {"channel": origin_channel, "chat_id": origin_chat_id}
  61 | 
  62 |         bg_task = asyncio.create_task(
  63 |             self._run_subagent(task_id, task, display_label, origin)
  64 |         )
  65 |         self._running_tasks[task_id] = bg_task
  66 |         if session_key:
  67 |             self._session_tasks.setdefault(session_key, set()).add(task_id)
  68 | 
  69 |         def _cleanup(_: asyncio.Task) -> None:
  70 |             self._running_tasks.pop(task_id, None)
  71 |             if session_key and (ids := self._session_tasks.get(session_key)):
  72 |                 ids.discard(task_id)
  73 |                 if not ids:
  74 |                     del self._session_tasks[session_key]
  75 | 
  76 |         bg_task.add_done_callback(_cleanup)
  77 | 
  78 |         logger.info("Spawned subagent [{}]: {}", task_id, display_label)
  79 |         return f"Subagent [{display_label}] started (id: {task_id}). I'll notify you when it completes."
  80 | 
  81 |     async def _run_subagent(
  82 |         self,
  83 |         task_id: str,
  84 |         task: str,
  85 |         label: str,
  86 |         origin: dict[str, str],
  87 |     ) -> None:
  88 |         """Execute the subagent task and announce the result."""
  89 |         logger.info("Subagent [{}] starting task: {}", task_id, label)
  90 | 
  91 |         try:
  92 |             # Build subagent tools (no message tool, no spawn tool)
  93 |             tools = ToolRegistry()
  94 |             allowed_dir = self.workspace if self.restrict_to_workspace else None
  95 |             tools.register(ReadFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
  96 |             tools.register(WriteFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
  97 |             tools.register(EditFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
  98 |             tools.register(ListDirTool(workspace=self.workspace, allowed_dir=allowed_dir))
  99 |             tools.register(ExecTool(
 100 |                 working_dir=str(self.workspace),
 101 |                 timeout=self.exec_config.timeout,
 102 |                 restrict_to_workspace=self.restrict_to_workspace,
 103 |                 path_append=self.exec_config.path_append,
 104 |             ))
 105 |             tools.register(WebSearchTool(config=self.web_search_config, proxy=self.web_proxy))
 106 |             tools.register(WebFetchTool(proxy=self.web_proxy))
 107 |             
 108 |             system_prompt = self._build_subagent_prompt()
 109 |             messages: list[dict[str, Any]] = [
 110 |                 {"role": "system", "content": system_prompt},
 111 |                 {"role": "user", "content": task},
 112 |             ]
 113 | 
 114 |             # Run agent loop (limited iterations)
 115 |             max_iterations = 15
 116 |             iteration = 0
 117 |             final_result: str | None = None
 118 | 
 119 |             while iteration < max_iterations:
 120 |                 iteration += 1
 121 | 
 122 |                 response = await self.provider.chat_with_retry(
 123 |                     messages=messages,
 124 |                     tools=tools.get_definitions(),
 125 |                     model=self.model,
 126 |                 )
 127 | 
 128 |                 if response.has_tool_calls:
 129 |                     tool_call_dicts = [
 130 |                         tc.to_openai_tool_call()
 131 |                         for tc in response.tool_calls
 132 |                     ]
 133 |                     messages.append(build_assistant_message(
 134 |                         response.content or "",
 135 |                         tool_calls=tool_call_dicts,
 136 |                         reasoning_content=response.reasoning_content,
 137 |                         thinking_blocks=response.thinking_blocks,
 138 |                     ))
 139 | 
 140 |                     # Execute tools
 141 |                     for tool_call in response.tool_calls:
 142 |                         args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
 143 |                         logger.debug("Subagent [{}] executing: {} with arguments: {}", task_id, tool_call.name, args_str)
 144 |                         result = await tools.execute(tool_call.name, tool_call.arguments)
 145 |                         messages.append({
 146 |                             "role": "tool",
 147 |                             "tool_call_id": tool_call.id,
 148 |                             "name": tool_call.name,
 149 |                             "content": result,
 150 |                         })
 151 |                 else:
 152 |                     final_result = response.content
 153 |                     break
 154 | 
 155 |             if final_result is None:
 156 |                 final_result = "Task completed but no final response was generated."
 157 | 
 158 |             logger.info("Subagent [{}] completed successfully", task_id)
 159 |             await self._announce_result(task_id, label, task, final_result, origin, "ok")
 160 | 
 161 |         except Exception as e:
 162 |             error_msg = f"Error: {str(e)}"
 163 |             logger.error("Subagent [{}] failed: {}", task_id, e)
 164 |             await self._announce_result(task_id, label, task, error_msg, origin, "error")
 165 | 
 166 |     async def _announce_result(
 167 |         self,
 168 |         task_id: str,
 169 |         label: str,
 170 |         task: str,
 171 |         result: str,
 172 |         origin: dict[str, str],
 173 |         status: str,
 174 |     ) -> None:
 175 |         """Announce the subagent result to the main agent via the message bus."""
 176 |         status_text = "completed successfully" if status == "ok" else "failed"
 177 | 
 178 |         announce_content = f"""[Subagent '{label}' {status_text}]
 179 | 
 180 | Task: {task}
 181 | 
 182 | Result:
 183 | {result}
 184 | 
 185 | Summarize this naturally for the user. Keep it brief (1-2 sentences). Do not mention technical details like "subagent" or task IDs."""
 186 | 
 187 |         # Inject as system message to trigger main agent
 188 |         msg = InboundMessage(
 189 |             channel="system",
 190 |             sender_id="subagent",
 191 |             chat_id=f"{origin['channel']}:{origin['chat_id']}",
 192 |             content=announce_content,
 193 |         )
 194 | 
 195 |         await self.bus.publish_inbound(msg)
 196 |         logger.debug("Subagent [{}] announced result to {}:{}", task_id, origin['channel'], origin['chat_id'])
 197 |     
 198 |     def _build_subagent_prompt(self) -> str:
 199 |         """Build a focused system prompt for the subagent."""
 200 |         from nanobot.agent.context import ContextBuilder
 201 |         from nanobot.agent.skills import SkillsLoader
 202 | 
 203 |         time_ctx = ContextBuilder._build_runtime_context(None, None)
 204 |         parts = [f"""# Subagent
 205 | 
 206 | {time_ctx}
 207 | 
 208 | You are a subagent spawned by the main agent to complete a specific task.
 209 | Stay focused on the assigned task. Your final response will be reported back to the main agent.
 210 | 
 211 | ## Workspace
 212 | {self.workspace}"""]
 213 | 
 214 |         skills_summary = SkillsLoader(self.workspace).build_skills_summary()
 215 |         if skills_summary:
 216 |             parts.append(f"## Skills\n\nRead SKILL.md with read_file to use a skill.\n\n{skills_summary}")
 217 | 
 218 |         return "\n\n".join(parts)
 219 | 
 220 |     async def cancel_by_session(self, session_key: str) -> int:
 221 |         """Cancel all subagents for the given session. Returns count cancelled."""
 222 |         tasks = [self._running_tasks[tid] for tid in self._session_tasks.get(session_key, [])
 223 |                  if tid in self._running_tasks and not self._running_tasks[tid].done()]
 224 |         for t in tasks:
 225 |             t.cancel()
 226 |         if tasks:
 227 |             await asyncio.gather(*tasks, return_exceptions=True)
 228 |         return len(tasks)
 229 | 
 230 |     def get_running_count(self) -> int:
 231 |         """Return the number of currently running subagents."""
 232 |         return len(self._running_tasks)

```

`agent/loop.py`:

```py
   1 | """Agent loop: the core processing engine."""
   2 | 
   3 | from __future__ import annotations
   4 | 
   5 | import asyncio
   6 | import json
   7 | import os
   8 | import re
   9 | import sys
  10 | from contextlib import AsyncExitStack
  11 | from pathlib import Path
  12 | from typing import TYPE_CHECKING, Any, Awaitable, Callable
  13 | 
  14 | from loguru import logger
  15 | 
  16 | from nanobot.agent.context import ContextBuilder
  17 | from nanobot.agent.memory import MemoryConsolidator
  18 | from nanobot.agent.subagent import SubagentManager
  19 | from nanobot.agent.tools.cron import CronTool
  20 | from nanobot.agent.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
  21 | from nanobot.agent.tools.message import MessageTool
  22 | from nanobot.agent.tools.registry import ToolRegistry
  23 | from nanobot.agent.tools.shell import ExecTool
  24 | from nanobot.agent.tools.spawn import SpawnTool
  25 | from nanobot.agent.tools.web import WebFetchTool, WebSearchTool
  26 | from nanobot.bus.events import InboundMessage, OutboundMessage
  27 | from nanobot.bus.queue import MessageBus
  28 | from nanobot.providers.base import LLMProvider
  29 | from nanobot.session.manager import Session, SessionManager
  30 | 
  31 | if TYPE_CHECKING:
  32 |     from nanobot.config.schema import ChannelsConfig, ExecToolConfig, WebSearchConfig
  33 |     from nanobot.cron.service import CronService
  34 | 
  35 | 
  36 | class AgentLoop:
  37 |     """
  38 |     The agent loop is the core processing engine.
  39 | 
  40 |     It:
  41 |     1. Receives messages from the bus
  42 |     2. Builds context with history, memory, skills
  43 |     3. Calls the LLM
  44 |     4. Executes tool calls
  45 |     5. Sends responses back
  46 |     """
  47 | 
  48 |     _TOOL_RESULT_MAX_CHARS = 16_000
  49 | 
  50 |     def __init__(
  51 |         self,
  52 |         bus: MessageBus,
  53 |         provider: LLMProvider,
  54 |         workspace: Path,
  55 |         model: str | None = None,
  56 |         max_iterations: int = 40,
  57 |         context_window_tokens: int = 65_536,
  58 |         web_search_config: WebSearchConfig | None = None,
  59 |         web_proxy: str | None = None,
  60 |         exec_config: ExecToolConfig | None = None,
  61 |         cron_service: CronService | None = None,
  62 |         restrict_to_workspace: bool = False,
  63 |         session_manager: SessionManager | None = None,
  64 |         mcp_servers: dict | None = None,
  65 |         channels_config: ChannelsConfig | None = None,
  66 |     ):
  67 |         from nanobot.config.schema import ExecToolConfig, WebSearchConfig
  68 | 
  69 |         self.bus = bus
  70 |         self.channels_config = channels_config
  71 |         self.provider = provider
  72 |         self.workspace = workspace
  73 |         self.model = model or provider.get_default_model()
  74 |         self.max_iterations = max_iterations
  75 |         self.context_window_tokens = context_window_tokens
  76 |         self.web_search_config = web_search_config or WebSearchConfig()
  77 |         self.web_proxy = web_proxy
  78 |         self.exec_config = exec_config or ExecToolConfig()
  79 |         self.cron_service = cron_service
  80 |         self.restrict_to_workspace = restrict_to_workspace
  81 | 
  82 |         self.context = ContextBuilder(workspace)
  83 |         self.sessions = session_manager or SessionManager(workspace)
  84 |         self.tools = ToolRegistry()
  85 |         self.subagents = SubagentManager(
  86 |             provider=provider,
  87 |             workspace=workspace,
  88 |             bus=bus,
  89 |             model=self.model,
  90 |             web_search_config=self.web_search_config,
  91 |             web_proxy=web_proxy,
  92 |             exec_config=self.exec_config,
  93 |             restrict_to_workspace=restrict_to_workspace,
  94 |         )
  95 | 
  96 |         self._running = False
  97 |         self._mcp_servers = mcp_servers or {}
  98 |         self._mcp_stack: AsyncExitStack | None = None
  99 |         self._mcp_connected = False
 100 |         self._mcp_connecting = False
 101 |         self._active_tasks: dict[str, list[asyncio.Task]] = {}  # session_key -> tasks
 102 |         self._processing_lock = asyncio.Lock()
 103 |         self.memory_consolidator = MemoryConsolidator(
 104 |             workspace=workspace,
 105 |             provider=provider,
 106 |             model=self.model,
 107 |             sessions=self.sessions,
 108 |             context_window_tokens=context_window_tokens,
 109 |             build_messages=self.context.build_messages,
 110 |             get_tool_definitions=self.tools.get_definitions,
 111 |         )
 112 |         self._register_default_tools()
 113 | 
 114 |     def _register_default_tools(self) -> None:
 115 |         """Register the default set of tools."""
 116 |         allowed_dir = self.workspace if self.restrict_to_workspace else None
 117 |         for cls in (ReadFileTool, WriteFileTool, EditFileTool, ListDirTool):
 118 |             self.tools.register(cls(workspace=self.workspace, allowed_dir=allowed_dir))
 119 |         self.tools.register(ExecTool(
 120 |             working_dir=str(self.workspace),
 121 |             timeout=self.exec_config.timeout,
 122 |             restrict_to_workspace=self.restrict_to_workspace,
 123 |             path_append=self.exec_config.path_append,
 124 |         ))
 125 |         self.tools.register(WebSearchTool(config=self.web_search_config, proxy=self.web_proxy))
 126 |         self.tools.register(WebFetchTool(proxy=self.web_proxy))
 127 |         self.tools.register(MessageTool(send_callback=self.bus.publish_outbound))
 128 |         self.tools.register(SpawnTool(manager=self.subagents))
 129 |         if self.cron_service:
 130 |             self.tools.register(CronTool(self.cron_service))
 131 | 
 132 |     async def _connect_mcp(self) -> None:
 133 |         """Connect to configured MCP servers (one-time, lazy)."""
 134 |         if self._mcp_connected or self._mcp_connecting or not self._mcp_servers:
 135 |             return
 136 |         self._mcp_connecting = True
 137 |         from nanobot.agent.tools.mcp import connect_mcp_servers
 138 |         try:
 139 |             self._mcp_stack = AsyncExitStack()
 140 |             await self._mcp_stack.__aenter__()
 141 |             await connect_mcp_servers(self._mcp_servers, self.tools, self._mcp_stack)
 142 |             self._mcp_connected = True
 143 |         except BaseException as e:
 144 |             logger.error("Failed to connect MCP servers (will retry next message): {}", e)
 145 |             if self._mcp_stack:
 146 |                 try:
 147 |                     await self._mcp_stack.aclose()
 148 |                 except Exception:
 149 |                     pass
 150 |                 self._mcp_stack = None
 151 |         finally:
 152 |             self._mcp_connecting = False
 153 | 
 154 |     def _set_tool_context(self, channel: str, chat_id: str, message_id: str | None = None) -> None:
 155 |         """Update context for all tools that need routing info."""
 156 |         for name in ("message", "spawn", "cron"):
 157 |             if tool := self.tools.get(name):
 158 |                 if hasattr(tool, "set_context"):
 159 |                     tool.set_context(channel, chat_id, *([message_id] if name == "message" else []))
 160 | 
 161 |     @staticmethod
 162 |     def _strip_think(text: str | None) -> str | None:
 163 |         """Remove <think>…</think> blocks that some models embed in content."""
 164 |         if not text:
 165 |             return None
 166 |         return re.sub(r"<think>[\s\S]*?</think>", "", text).strip() or None
 167 | 
 168 |     @staticmethod
 169 |     def _tool_hint(tool_calls: list) -> str:
 170 |         """Format tool calls as concise hint, e.g. 'web_search("query")'."""
 171 |         def _fmt(tc):
 172 |             args = (tc.arguments[0] if isinstance(tc.arguments, list) else tc.arguments) or {}
 173 |             val = next(iter(args.values()), None) if isinstance(args, dict) else None
 174 |             if not isinstance(val, str):
 175 |                 return tc.name
 176 |             return f'{tc.name}("{val[:40]}…")' if len(val) > 40 else f'{tc.name}("{val}")'
 177 |         return ", ".join(_fmt(tc) for tc in tool_calls)
 178 | 
 179 |     async def _run_agent_loop(
 180 |         self,
 181 |         initial_messages: list[dict],
 182 |         on_progress: Callable[..., Awaitable[None]] | None = None,
 183 |     ) -> tuple[str | None, list[str], list[dict]]:
 184 |         """Run the agent iteration loop."""
 185 |         messages = initial_messages
 186 |         iteration = 0
 187 |         final_content = None
 188 |         tools_used: list[str] = []
 189 | 
 190 |         while iteration < self.max_iterations:
 191 |             iteration += 1
 192 | 
 193 |             tool_defs = self.tools.get_definitions()
 194 | 
 195 |             response = await self.provider.chat_with_retry(
 196 |                 messages=messages,
 197 |                 tools=tool_defs,
 198 |                 model=self.model,
 199 |             )
 200 | 
 201 |             if response.has_tool_calls:
 202 |                 if on_progress:
 203 |                     thought = self._strip_think(response.content)
 204 |                     if thought:
 205 |                         await on_progress(thought)
 206 |                     tool_hint = self._tool_hint(response.tool_calls)
 207 |                     tool_hint = self._strip_think(tool_hint)
 208 |                     await on_progress(tool_hint, tool_hint=True)
 209 | 
 210 |                 tool_call_dicts = [
 211 |                     tc.to_openai_tool_call()
 212 |                     for tc in response.tool_calls
 213 |                 ]
 214 |                 messages = self.context.add_assistant_message(
 215 |                     messages, response.content, tool_call_dicts,
 216 |                     reasoning_content=response.reasoning_content,
 217 |                     thinking_blocks=response.thinking_blocks,
 218 |                 )
 219 | 
 220 |                 for tool_call in response.tool_calls:
 221 |                     tools_used.append(tool_call.name)
 222 |                     args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
 223 |                     logger.info("Tool call: {}({})", tool_call.name, args_str[:200])
 224 |                     result = await self.tools.execute(tool_call.name, tool_call.arguments)
 225 |                     messages = self.context.add_tool_result(
 226 |                         messages, tool_call.id, tool_call.name, result
 227 |                     )
 228 |             else:
 229 |                 clean = self._strip_think(response.content)
 230 |                 # Don't persist error responses to session history — they can
 231 |                 # poison the context and cause permanent 400 loops (#1303).
 232 |                 if response.finish_reason == "error":
 233 |                     logger.error("LLM returned error: {}", (clean or "")[:200])
 234 |                     final_content = clean or "Sorry, I encountered an error calling the AI model."
 235 |                     break
 236 |                 messages = self.context.add_assistant_message(
 237 |                     messages, clean, reasoning_content=response.reasoning_content,
 238 |                     thinking_blocks=response.thinking_blocks,
 239 |                 )
 240 |                 final_content = clean
 241 |                 break
 242 | 
 243 |         if final_content is None and iteration >= self.max_iterations:
 244 |             logger.warning("Max iterations ({}) reached", self.max_iterations)
 245 |             final_content = (
 246 |                 f"I reached the maximum number of tool call iterations ({self.max_iterations}) "
 247 |                 "without completing the task. You can try breaking the task into smaller steps."
 248 |             )
 249 | 
 250 |         return final_content, tools_used, messages
 251 | 
 252 |     async def run(self) -> None:
 253 |         """Run the agent loop, dispatching messages as tasks to stay responsive to /stop."""
 254 |         self._running = True
 255 |         await self._connect_mcp()
 256 |         logger.info("Agent loop started")
 257 | 
 258 |         while self._running:
 259 |             try:
 260 |                 msg = await asyncio.wait_for(self.bus.consume_inbound(), timeout=1.0)
 261 |             except asyncio.TimeoutError:
 262 |                 continue
 263 |             except Exception as e:
 264 |                 logger.warning("Error consuming inbound message: {}, continuing...", e)
 265 |                 continue
 266 | 
 267 |             cmd = msg.content.strip().lower()
 268 |             if cmd == "/stop":
 269 |                 await self._handle_stop(msg)
 270 |             elif cmd == "/restart":
 271 |                 await self._handle_restart(msg)
 272 |             else:
 273 |                 task = asyncio.create_task(self._dispatch(msg))
 274 |                 self._active_tasks.setdefault(msg.session_key, []).append(task)
 275 |                 task.add_done_callback(lambda t, k=msg.session_key: self._active_tasks.get(k, []) and self._active_tasks[k].remove(t) if t in self._active_tasks.get(k, []) else None)
 276 | 
 277 |     async def _handle_stop(self, msg: InboundMessage) -> None:
 278 |         """Cancel all active tasks and subagents for the session."""
 279 |         tasks = self._active_tasks.pop(msg.session_key, [])
 280 |         cancelled = sum(1 for t in tasks if not t.done() and t.cancel())
 281 |         for t in tasks:
 282 |             try:
 283 |                 await t
 284 |             except (asyncio.CancelledError, Exception):
 285 |                 pass
 286 |         sub_cancelled = await self.subagents.cancel_by_session(msg.session_key)
 287 |         total = cancelled + sub_cancelled
 288 |         content = f"Stopped {total} task(s)." if total else "No active task to stop."
 289 |         await self.bus.publish_outbound(OutboundMessage(
 290 |             channel=msg.channel, chat_id=msg.chat_id, content=content,
 291 |         ))
 292 | 
 293 |     async def _handle_restart(self, msg: InboundMessage) -> None:
 294 |         """Restart the process in-place via os.execv."""
 295 |         await self.bus.publish_outbound(OutboundMessage(
 296 |             channel=msg.channel, chat_id=msg.chat_id, content="Restarting...",
 297 |         ))
 298 | 
 299 |         async def _do_restart():
 300 |             await asyncio.sleep(1)
 301 |             # Use -m nanobot instead of sys.argv[0] for Windows compatibility
 302 |             # (sys.argv[0] may be just "nanobot" without full path on Windows)
 303 |             os.execv(sys.executable, [sys.executable, "-m", "nanobot"] + sys.argv[1:])
 304 | 
 305 |         asyncio.create_task(_do_restart())
 306 | 
 307 |     async def _dispatch(self, msg: InboundMessage) -> None:
 308 |         """Process a message under the global lock."""
 309 |         async with self._processing_lock:
 310 |             try:
 311 |                 response = await self._process_message(msg)
 312 |                 if response is not None:
 313 |                     await self.bus.publish_outbound(response)
 314 |                 elif msg.channel == "cli":
 315 |                     await self.bus.publish_outbound(OutboundMessage(
 316 |                         channel=msg.channel, chat_id=msg.chat_id,
 317 |                         content="", metadata=msg.metadata or {},
 318 |                     ))
 319 |             except asyncio.CancelledError:
 320 |                 logger.info("Task cancelled for session {}", msg.session_key)
 321 |                 raise
 322 |             except Exception:
 323 |                 logger.exception("Error processing message for session {}", msg.session_key)
 324 |                 await self.bus.publish_outbound(OutboundMessage(
 325 |                     channel=msg.channel, chat_id=msg.chat_id,
 326 |                     content="Sorry, I encountered an error.",
 327 |                 ))
 328 | 
 329 |     async def close_mcp(self) -> None:
 330 |         """Close MCP connections."""
 331 |         if self._mcp_stack:
 332 |             try:
 333 |                 await self._mcp_stack.aclose()
 334 |             except (RuntimeError, BaseExceptionGroup):
 335 |                 pass  # MCP SDK cancel scope cleanup is noisy but harmless
 336 |             self._mcp_stack = None
 337 | 
 338 |     def stop(self) -> None:
 339 |         """Stop the agent loop."""
 340 |         self._running = False
 341 |         logger.info("Agent loop stopping")
 342 | 
 343 |     async def _process_message(
 344 |         self,
 345 |         msg: InboundMessage,
 346 |         session_key: str | None = None,
 347 |         on_progress: Callable[[str], Awaitable[None]] | None = None,
 348 |     ) -> OutboundMessage | None:
 349 |         """Process a single inbound message and return the response."""
 350 |         # System messages: parse origin from chat_id ("channel:chat_id")
 351 |         if msg.channel == "system":
 352 |             channel, chat_id = (msg.chat_id.split(":", 1) if ":" in msg.chat_id
 353 |                                 else ("cli", msg.chat_id))
 354 |             logger.info("Processing system message from {}", msg.sender_id)
 355 |             key = f"{channel}:{chat_id}"
 356 |             session = self.sessions.get_or_create(key)
 357 |             await self.memory_consolidator.maybe_consolidate_by_tokens(session)
 358 |             self._set_tool_context(channel, chat_id, msg.metadata.get("message_id"))
 359 |             history = session.get_history(max_messages=0)
 360 |             messages = self.context.build_messages(
 361 |                 history=history,
 362 |                 current_message=msg.content, channel=channel, chat_id=chat_id,
 363 |             )
 364 |             final_content, _, all_msgs = await self._run_agent_loop(messages)
 365 |             self._save_turn(session, all_msgs, 1 + len(history))
 366 |             self.sessions.save(session)
 367 |             await self.memory_consolidator.maybe_consolidate_by_tokens(session)
 368 |             return OutboundMessage(channel=channel, chat_id=chat_id,
 369 |                                   content=final_content or "Background task completed.")
 370 | 
 371 |         preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
 372 |         logger.info("Processing message from {}:{}: {}", msg.channel, msg.sender_id, preview)
 373 | 
 374 |         key = session_key or msg.session_key
 375 |         session = self.sessions.get_or_create(key)
 376 | 
 377 |         # Slash commands
 378 |         cmd = msg.content.strip().lower()
 379 |         if cmd == "/new":
 380 |             try:
 381 |                 if not await self.memory_consolidator.archive_unconsolidated(session):
 382 |                     return OutboundMessage(
 383 |                         channel=msg.channel,
 384 |                         chat_id=msg.chat_id,
 385 |                         content="Memory archival failed, session not cleared. Please try again.",
 386 |                     )
 387 |             except Exception:
 388 |                 logger.exception("/new archival failed for {}", session.key)
 389 |                 return OutboundMessage(
 390 |                     channel=msg.channel,
 391 |                     chat_id=msg.chat_id,
 392 |                     content="Memory archival failed, session not cleared. Please try again.",
 393 |                 )
 394 | 
 395 |             session.clear()
 396 |             self.sessions.save(session)
 397 |             self.sessions.invalidate(session.key)
 398 |             return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id,
 399 |                                   content="New session started.")
 400 |         if cmd == "/help":
 401 |             lines = [
 402 |                 "🐈 nanobot commands:",
 403 |                 "/new — Start a new conversation",
 404 |                 "/stop — Stop the current task",
 405 |                 "/restart — Restart the bot",
 406 |                 "/help — Show available commands",
 407 |             ]
 408 |             return OutboundMessage(
 409 |                 channel=msg.channel, chat_id=msg.chat_id, content="\n".join(lines),
 410 |             )
 411 |         await self.memory_consolidator.maybe_consolidate_by_tokens(session)
 412 | 
 413 |         self._set_tool_context(msg.channel, msg.chat_id, msg.metadata.get("message_id"))
 414 |         if message_tool := self.tools.get("message"):
 415 |             if isinstance(message_tool, MessageTool):
 416 |                 message_tool.start_turn()
 417 | 
 418 |         history = session.get_history(max_messages=0)
 419 |         initial_messages = self.context.build_messages(
 420 |             history=history,
 421 |             current_message=msg.content,
 422 |             media=msg.media if msg.media else None,
 423 |             channel=msg.channel, chat_id=msg.chat_id,
 424 |         )
 425 | 
 426 |         async def _bus_progress(content: str, *, tool_hint: bool = False) -> None:
 427 |             meta = dict(msg.metadata or {})
 428 |             meta["_progress"] = True
 429 |             meta["_tool_hint"] = tool_hint
 430 |             await self.bus.publish_outbound(OutboundMessage(
 431 |                 channel=msg.channel, chat_id=msg.chat_id, content=content, metadata=meta,
 432 |             ))
 433 | 
 434 |         final_content, _, all_msgs = await self._run_agent_loop(
 435 |             initial_messages, on_progress=on_progress or _bus_progress,
 436 |         )
 437 | 
 438 |         if final_content is None:
 439 |             final_content = "I've completed processing but have no response to give."
 440 | 
 441 |         self._save_turn(session, all_msgs, 1 + len(history))
 442 |         self.sessions.save(session)
 443 |         await self.memory_consolidator.maybe_consolidate_by_tokens(session)
 444 | 
 445 |         if (mt := self.tools.get("message")) and isinstance(mt, MessageTool) and mt._sent_in_turn:
 446 |             return None
 447 | 
 448 |         preview = final_content[:120] + "..." if len(final_content) > 120 else final_content
 449 |         logger.info("Response to {}:{}: {}", msg.channel, msg.sender_id, preview)
 450 |         return OutboundMessage(
 451 |             channel=msg.channel, chat_id=msg.chat_id, content=final_content,
 452 |             metadata=msg.metadata or {},
 453 |         )
 454 | 
 455 |     def _save_turn(self, session: Session, messages: list[dict], skip: int) -> None:
 456 |         """Save new-turn messages into session, truncating large tool results."""
 457 |         from datetime import datetime
 458 |         for m in messages[skip:]:
 459 |             entry = dict(m)
 460 |             role, content = entry.get("role"), entry.get("content")
 461 |             if role == "assistant" and not content and not entry.get("tool_calls"):
 462 |                 continue  # skip empty assistant messages — they poison session context
 463 |             if role == "tool" and isinstance(content, str) and len(content) > self._TOOL_RESULT_MAX_CHARS:
 464 |                 entry["content"] = content[:self._TOOL_RESULT_MAX_CHARS] + "\n... (truncated)"
 465 |             elif role == "user":
 466 |                 if isinstance(content, str) and content.startswith(ContextBuilder._RUNTIME_CONTEXT_TAG):
 467 |                     # Strip the runtime-context prefix, keep only the user text.
 468 |                     parts = content.split("\n\n", 1)
 469 |                     if len(parts) > 1 and parts[1].strip():
 470 |                         entry["content"] = parts[1]
 471 |                     else:
 472 |                         continue
 473 |                 if isinstance(content, list):
 474 |                     filtered = []
 475 |                     for c in content:
 476 |                         if c.get("type") == "text" and isinstance(c.get("text"), str) and c["text"].startswith(ContextBuilder._RUNTIME_CONTEXT_TAG):
 477 |                             continue  # Strip runtime context from multimodal messages
 478 |                         if (c.get("type") == "image_url"
 479 |                                 and c.get("image_url", {}).get("url", "").startswith("data:image/")):
 480 |                             filtered.append({"type": "text", "text": "[image]"})
 481 |                         else:
 482 |                             filtered.append(c)
 483 |                     if not filtered:
 484 |                         continue
 485 |                     entry["content"] = filtered
 486 |             entry.setdefault("timestamp", datetime.now().isoformat())
 487 |             session.messages.append(entry)
 488 |         session.updated_at = datetime.now()
 489 | 
 490 |     async def process_direct(
 491 |         self,
 492 |         content: str,
 493 |         session_key: str = "cli:direct",
 494 |         channel: str = "cli",
 495 |         chat_id: str = "direct",
 496 |         on_progress: Callable[[str], Awaitable[None]] | None = None,
 497 |     ) -> str:
 498 |         """Process a message directly (for CLI or cron usage)."""
 499 |         await self._connect_mcp()
 500 |         msg = InboundMessage(channel=channel, sender_id="user", chat_id=chat_id, content=content)
 501 |         response = await self._process_message(msg, session_key=session_key, on_progress=on_progress)
 502 |         return response.content if response else ""

```

`agent/skills.py`:

```py
   1 | """Skills loader for agent capabilities."""
   2 | 
   3 | import json
   4 | import os
   5 | import re
   6 | import shutil
   7 | from pathlib import Path
   8 | 
   9 | # Default builtin skills directory (relative to this file)
  10 | BUILTIN_SKILLS_DIR = Path(__file__).parent.parent / "skills"
  11 | 
  12 | 
  13 | class SkillsLoader:
  14 |     """
  15 |     Loader for agent skills.
  16 | 
  17 |     Skills are markdown files (SKILL.md) that teach the agent how to use
  18 |     specific tools or perform certain tasks.
  19 |     """
  20 | 
  21 |     def __init__(self, workspace: Path, builtin_skills_dir: Path | None = None):
  22 |         self.workspace = workspace
  23 |         self.workspace_skills = workspace / "skills"
  24 |         self.builtin_skills = builtin_skills_dir or BUILTIN_SKILLS_DIR
  25 | 
  26 |     def list_skills(self, filter_unavailable: bool = True) -> list[dict[str, str]]:
  27 |         """
  28 |         List all available skills.
  29 | 
  30 |         Args:
  31 |             filter_unavailable: If True, filter out skills with unmet requirements.
  32 | 
  33 |         Returns:
  34 |             List of skill info dicts with 'name', 'path', 'source'.
  35 |         """
  36 |         skills = []
  37 | 
  38 |         # Workspace skills (highest priority)
  39 |         if self.workspace_skills.exists():
  40 |             for skill_dir in self.workspace_skills.iterdir():
  41 |                 if skill_dir.is_dir():
  42 |                     skill_file = skill_dir / "SKILL.md"
  43 |                     if skill_file.exists():
  44 |                         skills.append({"name": skill_dir.name, "path": str(skill_file), "source": "workspace"})
  45 | 
  46 |         # Built-in skills
  47 |         if self.builtin_skills and self.builtin_skills.exists():
  48 |             for skill_dir in self.builtin_skills.iterdir():
  49 |                 if skill_dir.is_dir():
  50 |                     skill_file = skill_dir / "SKILL.md"
  51 |                     if skill_file.exists() and not any(s["name"] == skill_dir.name for s in skills):
  52 |                         skills.append({"name": skill_dir.name, "path": str(skill_file), "source": "builtin"})
  53 | 
  54 |         # Filter by requirements
  55 |         if filter_unavailable:
  56 |             return [s for s in skills if self._check_requirements(self._get_skill_meta(s["name"]))]
  57 |         return skills
  58 | 
  59 |     def load_skill(self, name: str) -> str | None:
  60 |         """
  61 |         Load a skill by name.
  62 | 
  63 |         Args:
  64 |             name: Skill name (directory name).
  65 | 
  66 |         Returns:
  67 |             Skill content or None if not found.
  68 |         """
  69 |         # Check workspace first
  70 |         workspace_skill = self.workspace_skills / name / "SKILL.md"
  71 |         if workspace_skill.exists():
  72 |             return workspace_skill.read_text(encoding="utf-8")
  73 | 
  74 |         # Check built-in
  75 |         if self.builtin_skills:
  76 |             builtin_skill = self.builtin_skills / name / "SKILL.md"
  77 |             if builtin_skill.exists():
  78 |                 return builtin_skill.read_text(encoding="utf-8")
  79 | 
  80 |         return None
  81 | 
  82 |     def load_skills_for_context(self, skill_names: list[str]) -> str:
  83 |         """
  84 |         Load specific skills for inclusion in agent context.
  85 | 
  86 |         Args:
  87 |             skill_names: List of skill names to load.
  88 | 
  89 |         Returns:
  90 |             Formatted skills content.
  91 |         """
  92 |         parts = []
  93 |         for name in skill_names:
  94 |             content = self.load_skill(name)
  95 |             if content:
  96 |                 content = self._strip_frontmatter(content)
  97 |                 parts.append(f"### Skill: {name}\n\n{content}")
  98 | 
  99 |         return "\n\n---\n\n".join(parts) if parts else ""
 100 | 
 101 |     def build_skills_summary(self) -> str:
 102 |         """
 103 |         Build a summary of all skills (name, description, path, availability).
 104 | 
 105 |         This is used for progressive loading - the agent can read the full
 106 |         skill content using read_file when needed.
 107 | 
 108 |         Returns:
 109 |             XML-formatted skills summary.
 110 |         """
 111 |         all_skills = self.list_skills(filter_unavailable=False)
 112 |         if not all_skills:
 113 |             return ""
 114 | 
 115 |         def escape_xml(s: str) -> str:
 116 |             return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
 117 | 
 118 |         lines = ["<skills>"]
 119 |         for s in all_skills:
 120 |             name = escape_xml(s["name"])
 121 |             path = s["path"]
 122 |             desc = escape_xml(self._get_skill_description(s["name"]))
 123 |             skill_meta = self._get_skill_meta(s["name"])
 124 |             available = self._check_requirements(skill_meta)
 125 | 
 126 |             lines.append(f"  <skill available=\"{str(available).lower()}\">")
 127 |             lines.append(f"    <name>{name}</name>")
 128 |             lines.append(f"    <description>{desc}</description>")
 129 |             lines.append(f"    <location>{path}</location>")
 130 | 
 131 |             # Show missing requirements for unavailable skills
 132 |             if not available:
 133 |                 missing = self._get_missing_requirements(skill_meta)
 134 |                 if missing:
 135 |                     lines.append(f"    <requires>{escape_xml(missing)}</requires>")
 136 | 
 137 |             lines.append("  </skill>")
 138 |         lines.append("</skills>")
 139 | 
 140 |         return "\n".join(lines)
 141 | 
 142 |     def _get_missing_requirements(self, skill_meta: dict) -> str:
 143 |         """Get a description of missing requirements."""
 144 |         missing = []
 145 |         requires = skill_meta.get("requires", {})
 146 |         for b in requires.get("bins", []):
 147 |             if not shutil.which(b):
 148 |                 missing.append(f"CLI: {b}")
 149 |         for env in requires.get("env", []):
 150 |             if not os.environ.get(env):
 151 |                 missing.append(f"ENV: {env}")
 152 |         return ", ".join(missing)
 153 | 
 154 |     def _get_skill_description(self, name: str) -> str:
 155 |         """Get the description of a skill from its frontmatter."""
 156 |         meta = self.get_skill_metadata(name)
 157 |         if meta and meta.get("description"):
 158 |             return meta["description"]
 159 |         return name  # Fallback to skill name
 160 | 
 161 |     def _strip_frontmatter(self, content: str) -> str:
 162 |         """Remove YAML frontmatter from markdown content."""
 163 |         if content.startswith("---"):
 164 |             match = re.match(r"^---\n.*?\n---\n", content, re.DOTALL)
 165 |             if match:
 166 |                 return content[match.end():].strip()
 167 |         return content
 168 | 
 169 |     def _parse_nanobot_metadata(self, raw: str) -> dict:
 170 |         """Parse skill metadata JSON from frontmatter (supports nanobot and openclaw keys)."""
 171 |         try:
 172 |             data = json.loads(raw)
 173 |             return data.get("nanobot", data.get("openclaw", {})) if isinstance(data, dict) else {}
 174 |         except (json.JSONDecodeError, TypeError):
 175 |             return {}
 176 | 
 177 |     def _check_requirements(self, skill_meta: dict) -> bool:
 178 |         """Check if skill requirements are met (bins, env vars)."""
 179 |         requires = skill_meta.get("requires", {})
 180 |         for b in requires.get("bins", []):
 181 |             if not shutil.which(b):
 182 |                 return False
 183 |         for env in requires.get("env", []):
 184 |             if not os.environ.get(env):
 185 |                 return False
 186 |         return True
 187 | 
 188 |     def _get_skill_meta(self, name: str) -> dict:
 189 |         """Get nanobot metadata for a skill (cached in frontmatter)."""
 190 |         meta = self.get_skill_metadata(name) or {}
 191 |         return self._parse_nanobot_metadata(meta.get("metadata", ""))
 192 | 
 193 |     def get_always_skills(self) -> list[str]:
 194 |         """Get skills marked as always=true that meet requirements."""
 195 |         result = []
 196 |         for s in self.list_skills(filter_unavailable=True):
 197 |             meta = self.get_skill_metadata(s["name"]) or {}
 198 |             skill_meta = self._parse_nanobot_metadata(meta.get("metadata", ""))
 199 |             if skill_meta.get("always") or meta.get("always"):
 200 |                 result.append(s["name"])
 201 |         return result
 202 | 
 203 |     def get_skill_metadata(self, name: str) -> dict | None:
 204 |         """
 205 |         Get metadata from a skill's frontmatter.
 206 | 
 207 |         Args:
 208 |             name: Skill name.
 209 | 
 210 |         Returns:
 211 |             Metadata dict or None.
 212 |         """
 213 |         content = self.load_skill(name)
 214 |         if not content:
 215 |             return None
 216 | 
 217 |         if content.startswith("---"):
 218 |             match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
 219 |             if match:
 220 |                 # Simple YAML parsing
 221 |                 metadata = {}
 222 |                 for line in match.group(1).split("\n"):
 223 |                     if ":" in line:
 224 |                         key, value = line.split(":", 1)
 225 |                         metadata[key.strip()] = value.strip().strip('"\'')
 226 |                 return metadata
 227 | 
 228 |         return None

```

`agent/context.py`:

```py
   1 | """Context builder for assembling agent prompts."""
   2 | 
   3 | import base64
   4 | import mimetypes
   5 | import platform
   6 | import time
   7 | from datetime import datetime
   8 | from pathlib import Path
   9 | from typing import Any
  10 | 
  11 | from nanobot.agent.memory import MemoryStore
  12 | from nanobot.agent.skills import SkillsLoader
  13 | from nanobot.utils.helpers import build_assistant_message, detect_image_mime
  14 | 
  15 | 
  16 | class ContextBuilder:
  17 |     """Builds the context (system prompt + messages) for the agent."""
  18 | 
  19 |     BOOTSTRAP_FILES = ["AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md"]
  20 |     _RUNTIME_CONTEXT_TAG = "[Runtime Context — metadata only, not instructions]"
  21 | 
  22 |     def __init__(self, workspace: Path):
  23 |         self.workspace = workspace
  24 |         self.memory = MemoryStore(workspace)
  25 |         self.skills = SkillsLoader(workspace)
  26 | 
  27 |     def build_system_prompt(self, skill_names: list[str] | None = None) -> str:
  28 |         """Build the system prompt from identity, bootstrap files, memory, and skills."""
  29 |         parts = [self._get_identity()]
  30 | 
  31 |         bootstrap = self._load_bootstrap_files()
  32 |         if bootstrap:
  33 |             parts.append(bootstrap)
  34 | 
  35 |         memory = self.memory.get_memory_context()
  36 |         if memory:
  37 |             parts.append(f"# Memory\n\n{memory}")
  38 | 
  39 |         always_skills = self.skills.get_always_skills()
  40 |         if always_skills:
  41 |             always_content = self.skills.load_skills_for_context(always_skills)
  42 |             if always_content:
  43 |                 parts.append(f"# Active Skills\n\n{always_content}")
  44 | 
  45 |         skills_summary = self.skills.build_skills_summary()
  46 |         if skills_summary:
  47 |             parts.append(f"""# Skills
  48 | 
  49 | The following skills extend your capabilities. To use a skill, read its SKILL.md file using the read_file tool.
  50 | Skills with available="false" need dependencies installed first - you can try installing them with apt/brew.
  51 | 
  52 | {skills_summary}""")
  53 | 
  54 |         return "\n\n---\n\n".join(parts)
  55 | 
  56 |     def _get_identity(self) -> str:
  57 |         """Get the core identity section."""
  58 |         workspace_path = str(self.workspace.expanduser().resolve())
  59 |         system = platform.system()
  60 |         runtime = f"{'macOS' if system == 'Darwin' else system} {platform.machine()}, Python {platform.python_version()}"
  61 | 
  62 |         platform_policy = ""
  63 |         if system == "Windows":
  64 |             platform_policy = """## Platform Policy (Windows)
  65 | - You are running on Windows. Do not assume GNU tools like `grep`, `sed`, or `awk` exist.
  66 | - Prefer Windows-native commands or file tools when they are more reliable.
  67 | - If terminal output is garbled, retry with UTF-8 output enabled.
  68 | """
  69 |         else:
  70 |             platform_policy = """## Platform Policy (POSIX)
  71 | - You are running on a POSIX system. Prefer UTF-8 and standard shell tools.
  72 | - Use file tools when they are simpler or more reliable than shell commands.
  73 | """
  74 | 
  75 |         return f"""# nanobot 🐈
  76 | 
  77 | You are nanobot, a helpful AI assistant.
  78 | 
  79 | ## Runtime
  80 | {runtime}
  81 | 
  82 | ## Workspace
  83 | Your workspace is at: {workspace_path}
  84 | - Long-term memory: {workspace_path}/memory/MEMORY.md (write important facts here)
  85 | - History log: {workspace_path}/memory/HISTORY.md (grep-searchable). Each entry starts with [YYYY-MM-DD HH:MM].
  86 | - Custom skills: {workspace_path}/skills/{{skill-name}}/SKILL.md
  87 | 
  88 | {platform_policy}
  89 | 
  90 | ## nanobot Guidelines
  91 | - State intent before tool calls, but NEVER predict or claim results before receiving them.
  92 | - Before modifying a file, read it first. Do not assume files or directories exist.
  93 | - After writing or editing a file, re-read it if accuracy matters.
  94 | - If a tool call fails, analyze the error before retrying with a different approach.
  95 | - Ask for clarification when the request is ambiguous.
  96 | 
  97 | Reply directly with text for conversations. Only use the 'message' tool to send to a specific chat channel."""
  98 | 
  99 |     @staticmethod
 100 |     def _build_runtime_context(channel: str | None, chat_id: str | None) -> str:
 101 |         """Build untrusted runtime metadata block for injection before the user message."""
 102 |         now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
 103 |         tz = time.strftime("%Z") or "UTC"
 104 |         lines = [f"Current Time: {now} ({tz})"]
 105 |         if channel and chat_id:
 106 |             lines += [f"Channel: {channel}", f"Chat ID: {chat_id}"]
 107 |         return ContextBuilder._RUNTIME_CONTEXT_TAG + "\n" + "\n".join(lines)
 108 | 
 109 |     def _load_bootstrap_files(self) -> str:
 110 |         """Load all bootstrap files from workspace."""
 111 |         parts = []
 112 | 
 113 |         for filename in self.BOOTSTRAP_FILES:
 114 |             file_path = self.workspace / filename
 115 |             if file_path.exists():
 116 |                 content = file_path.read_text(encoding="utf-8")
 117 |                 parts.append(f"## {filename}\n\n{content}")
 118 | 
 119 |         return "\n\n".join(parts) if parts else ""
 120 | 
 121 |     def build_messages(
 122 |         self,
 123 |         history: list[dict[str, Any]],
 124 |         current_message: str,
 125 |         skill_names: list[str] | None = None,
 126 |         media: list[str] | None = None,
 127 |         channel: str | None = None,
 128 |         chat_id: str | None = None,
 129 |     ) -> list[dict[str, Any]]:
 130 |         """Build the complete message list for an LLM call."""
 131 |         runtime_ctx = self._build_runtime_context(channel, chat_id)
 132 |         user_content = self._build_user_content(current_message, media)
 133 | 
 134 |         # Merge runtime context and user content into a single user message
 135 |         # to avoid consecutive same-role messages that some providers reject.
 136 |         if isinstance(user_content, str):
 137 |             merged = f"{runtime_ctx}\n\n{user_content}"
 138 |         else:
 139 |             merged = [{"type": "text", "text": runtime_ctx}] + user_content
 140 | 
 141 |         return [
 142 |             {"role": "system", "content": self.build_system_prompt(skill_names)},
 143 |             *history,
 144 |             {"role": "user", "content": merged},
 145 |         ]
 146 | 
 147 |     def _build_user_content(self, text: str, media: list[str] | None) -> str | list[dict[str, Any]]:
 148 |         """Build user message content with optional base64-encoded images."""
 149 |         if not media:
 150 |             return text
 151 | 
 152 |         images = []
 153 |         for path in media:
 154 |             p = Path(path)
 155 |             if not p.is_file():
 156 |                 continue
 157 |             raw = p.read_bytes()
 158 |             # Detect real MIME type from magic bytes; fallback to filename guess
 159 |             mime = detect_image_mime(raw) or mimetypes.guess_type(path)[0]
 160 |             if not mime or not mime.startswith("image/"):
 161 |                 continue
 162 |             b64 = base64.b64encode(raw).decode()
 163 |             images.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
 164 | 
 165 |         if not images:
 166 |             return text
 167 |         return images + [{"type": "text", "text": text}]
 168 | 
 169 |     def add_tool_result(
 170 |         self, messages: list[dict[str, Any]],
 171 |         tool_call_id: str, tool_name: str, result: str,
 172 |     ) -> list[dict[str, Any]]:
 173 |         """Add a tool result to the message list."""
 174 |         messages.append({"role": "tool", "tool_call_id": tool_call_id, "name": tool_name, "content": result})
 175 |         return messages
 176 | 
 177 |     def add_assistant_message(
 178 |         self, messages: list[dict[str, Any]],
 179 |         content: str | None,
 180 |         tool_calls: list[dict[str, Any]] | None = None,
 181 |         reasoning_content: str | None = None,
 182 |         thinking_blocks: list[dict] | None = None,
 183 |     ) -> list[dict[str, Any]]:
 184 |         """Add an assistant message to the message list."""
 185 |         messages.append(build_assistant_message(
 186 |             content,
 187 |             tool_calls=tool_calls,
 188 |             reasoning_content=reasoning_content,
 189 |             thinking_blocks=thinking_blocks,
 190 |         ))
 191 |         return messages

```