"""
BFCL 评测脚本 —— 测试你的 LLM Provider 的 Function Calling 能力。

使用方法：直接运行本文件即可
    python nanobot/utils/bfcl_eval.py

运行前请确保：
1. 已克隆 BFCL 数据集到 Test_Dataset/temp_gorilla/
2. 已在 ~/.nanobot/config.json 中配置好 API Key 和模型
"""

# ==========================================================================
# ⚙️ 配置区 —— 在这里修改你要测试的参数
# ==========================================================================

# 测试类别，可选值:
#   "simple_python"      - 简单 Python 函数调用（推荐先测这个）
#   "multiple"           - 多个函数按顺序调用
#   "parallel"           - 多个函数并行调用
#   "parallel_multiple"  - 并行 + 顺序混合
#   "live_simple"        - 用户贡献的简单调用
#   "live_multiple"      - 用户贡献的多函数调用
TEST_CATEGORY = "simple_python"

# 测试多少条数据？设为 None 表示测试全部（simple_python 共约 400 条）
# 建议先设为 5 跑通流程，再改成 None 跑全量
MAX_SAMPLES = 5

# LLM 采样温度（评测建议用 0，确保结果可复现）
TEMPERATURE = 0.0

# 结果输出目录
RESULT_DIR = "./bfcl_results"

# ==========================================================================
# 以下是代码实现，一般不需要修改
# ==========================================================================

import asyncio
import json
import time
from pathlib import Path


# --------------------------------------------------------------------------
# 第 1 步：找到 BFCL 数据集的位置
# --------------------------------------------------------------------------

def find_data_directory() -> Path:
    """找到 BFCL 数据集目录。

    会从当前文件往上找项目根目录，
    然后定位到 Test_Dataset/temp_gorilla/.../data/
    """
    # 从当前文件出发，往上两级就是项目根目录
    # bfcl_eval.py → utils/ → nanobot/ → 项目根目录
    project_root = Path(__file__).resolve().parents[2]

    data_dir = (
        project_root
        / "Test_Dataset"
        / "temp_gorilla"
        / "berkeley-function-call-leaderboard"
        / "bfcl_eval"
        / "data"
    )

    if not data_dir.exists():
        print(f"❌ 找不到 BFCL 数据目录: {data_dir}")
        print("请先克隆 BFCL 仓库:")
        print("  cd Test_Dataset")
        print("  git clone https://github.com/ShishirPatil/gorilla.git temp_gorilla")
        raise SystemExit(1)

    return data_dir


# --------------------------------------------------------------------------
# 第 2 步：加载 BFCL 数据集
# --------------------------------------------------------------------------

def load_dataset(category: str, data_dir: Path) -> list[dict]:
    """从 BFCL 数据文件中加载测试用例。

    数据文件是 JSONL 格式（每行一个 JSON），每条数据包含:
    - id: 样本ID，如 "simple_python_0"
    - question: 用户问题，格式 [[{"role": "user", "content": "..."}]]
    - function: 可用的函数定义列表
    """
    file_path = data_dir / f"BFCL_v4_{category}.json"

    if not file_path.exists():
        # 列出所有可用的类别
        available = sorted(f.stem.replace("BFCL_v4_", "") for f in data_dir.glob("BFCL_v4_*.json"))
        print(f"❌ 找不到类别 '{category}' 的数据文件: {file_path}")
        print(f"可用的类别: {available}")
        raise SystemExit(1)

    dataset = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                dataset.append(json.loads(line))

    print(f"✅ 已加载 {len(dataset)} 条测试数据 (类别: {category})")
    return dataset


# --------------------------------------------------------------------------
# 第 3 步：把 BFCL 的函数定义转换为 OpenAI 格式
# --------------------------------------------------------------------------

def fix_schema(value):
    """递归修复 BFCL schema 中和 OpenAI 不兼容的类型名。

    BFCL 数据集用的是 Python 风格:
        "type": "dict"   →  应改为 "type": "object"
        "type": "float"  →  应改为 "type": "number"

    OpenAI API 用的是 JSON Schema 标准:
        "type": "object"
        "type": "number"

    如果不转换，发给 OpenAI 会报错。
    """
    if isinstance(value, dict):
        new_dict = {}
        for key, val in value.items():
            if key == "type" and val == "dict":
                new_dict[key] = "object"
            elif key == "type" and val == "float":
                new_dict[key] = "number"
            else:
                new_dict[key] = fix_schema(val)
        return new_dict

    if isinstance(value, list):
        return [fix_schema(item) for item in value]

    return value


def convert_functions_to_openai_tools(bfcl_functions: list[dict]) -> list[dict]:
    """把 BFCL 的函数定义列表转成 OpenAI 的 tools 格式。

    输入（BFCL 格式）:
        {"name": "math.factorial", "description": "...", "parameters": {"type": "dict", ...}}

    输出（OpenAI 格式）:
        {"type": "function", "function": {"name": "math_factorial", ...}}

    注意: BFCL 的函数名可能包含 "."（如 math.factorial），
    但很多 LLM API（如 DeepSeek、OpenAI）要求函数名只能是 [a-zA-Z0-9_-]。
    所以这里把 "." 替换成 "_"，拿到结果后再换回来。
    """
    openai_tools = []

    for func in bfcl_functions:
        # 把函数名中的 "." 替换为 "_"，避免 API 报错
        safe_name = func["name"].replace(".", "_")

        tool = {
            "type": "function",
            "function": {
                "name": safe_name,
                "description": func.get("description", ""),
                "parameters": fix_schema(func.get("parameters", {})),
            },
        }
        openai_tools.append(tool)

    return openai_tools


# --------------------------------------------------------------------------
# 第 4 步：从 BFCL 数据中提取用户问题
# --------------------------------------------------------------------------

def extract_user_question(question_data) -> str:
    """从 BFCL 的 question 字段中提取用户问题文本。

    BFCL 的 question 格式是嵌套列表:
        [[{"role": "user", "content": "Find the area..."}]]
        ^  ^
        |  └── 第 1 轮的消息列表
        └── 所有轮次

    对于单轮测试，我们只取第 1 轮第 1 条消息的内容。
    """
    first_turn = question_data[0]       # 第 1 轮
    first_message = first_turn[0]       # 第 1 条消息
    user_question = first_message["content"]  # 文本内容
    return user_question


# --------------------------------------------------------------------------
# 第 5 步：创建 nanobot 的 LLM Provider
# --------------------------------------------------------------------------

def create_provider():
    """从 nanobot 配置文件创建 LLM Provider。

    读取 ~/.nanobot/config.json 中的配置,
    自动选择正确的 Provider（LiteLLM / Azure / Custom）,
    这样你不需要在脚本中硬编码 API Key。

    返回: (provider实例, 模型名)
    """
    from nanobot.config.loader import load_config
    from nanobot.providers.base import GenerationSettings

    # 加载 nanobot 配置
    config = load_config()
    model_name = config.agents.defaults.model
    provider_name = config.get_provider_name(model_name)
    provider_config = config.get_provider(model_name)

    print(f"📋 使用模型: {model_name}")
    print(f"📋 Provider: {provider_name}")

    # 根据配置创建对应的 Provider
    if provider_name == "custom":
        from nanobot.providers.custom_provider import CustomProvider
        provider = CustomProvider(
            api_key=provider_config.api_key if provider_config else "no-key",
            api_base=config.get_api_base(model_name) or "http://localhost:8000/v1",
            default_model=model_name,
        )
    elif provider_name == "azure_openai":
        from nanobot.providers.azure_openai_provider import AzureOpenAIProvider
        provider = AzureOpenAIProvider(
            api_key=provider_config.api_key,
            api_base=provider_config.api_base,
            default_model=model_name,
        )
    else:
        from nanobot.providers.litellm_provider import LiteLLMProvider
        provider = LiteLLMProvider(
            api_key=provider_config.api_key if provider_config else None,
            api_base=config.get_api_base(model_name),
            default_model=model_name,
            extra_headers=provider_config.extra_headers if provider_config else None,
            provider_name=provider_name,
        )

    # 应用默认的生成参数
    defaults = config.agents.defaults
    provider.generation = GenerationSettings(
        temperature=defaults.temperature,
        max_tokens=defaults.max_tokens,
        reasoning_effort=defaults.reasoning_effort,
    )

    return provider, model_name


# --------------------------------------------------------------------------
# 第 6 步：调用 LLM 进行 function calling
# --------------------------------------------------------------------------

async def ask_llm_to_call_functions(provider, model_name, user_question, openai_tools):
    """把用户问题和可用函数发给 LLM，让它返回 function call。

    这一步直接调用 provider.chat()，等价于 nanobot Agent 循环中的:
        response = await self.provider.chat_with_retry(
            messages=messages, tools=tool_defs, model=self.model)

    但我们跳过了 Agent 的 system prompt、历史记录等，
    只测试 LLM 的 原始 function calling 能力。

    返回: LLMResponse 对象，包含:
        .tool_calls: 函数调用列表 [ToolCallRequest, ...]
        .content: 文本回复（如果没有调用函数的话）
        .usage: token 用量统计
    """
    messages = [
        {"role": "user", "content": user_question}
    ]

    llm_response = await provider.chat(
        messages=messages,
        tools=openai_tools,
        model=model_name,
        temperature=TEMPERATURE,
        max_tokens=512,
    )

    return llm_response


# --------------------------------------------------------------------------
# 第 7 步：把 LLM 的 tool call 转成 BFCL 要求的字符串格式
# --------------------------------------------------------------------------

def convert_tool_calls_to_result_string(tool_calls, original_functions) -> str:
    """把 LLM 返回的 tool calls 转成 BFCL 评分器期望的字符串。

    LLM 返回的 tool call（ToolCallRequest 对象）:
        name = "math_factorial"        ← 发送时 "." 被替换成了 "_"
        arguments = {"number": 5}

    BFCL 评分器期望的字符串:
        'math.factorial(number=5)'     ← 需要把 "." 还原回来

    Args:
        tool_calls: LLM 返回的 tool call 列表
        original_functions: BFCL 原始的函数定义列表（用于还原函数名中的 "."）
    """
    if not tool_calls:
        return ""

    # 构建映射表: "math_factorial" → "math.factorial"
    # 这样就能把发送时替换掉的 "." 还原回来
    name_restore_map = {}
    for func in original_functions:
        original_name = func["name"]              # "math.factorial"
        safe_name = original_name.replace(".", "_")  # "math_factorial"
        name_restore_map[safe_name] = original_name

    call_strings = []

    for tool_call in tool_calls:
        # 还原函数名: "math_factorial" → "math.factorial"
        function_name = name_restore_map.get(tool_call.name, tool_call.name)
        arguments = tool_call.arguments

        # 把每个参数格式化为 "key=value"
        argument_parts = []
        for param_name, param_value in arguments.items():
            # repr() 会自动处理字符串加引号: repr("hello") → "'hello'"
            argument_parts.append(f"{param_name}={repr(param_value)}")

        # 拼成 "func_name(arg1=val1, arg2=val2)"
        arguments_string = ", ".join(argument_parts)
        call_string = f"{function_name}({arguments_string})"
        call_strings.append(call_string)

    # 单个函数调用不加括号，多个用方括号包起来
    if len(call_strings) == 1:
        return call_strings[0]
    else:
        return "[" + ", ".join(call_strings) + "]"


# --------------------------------------------------------------------------
# 第 8 步：保存结果到文件
# --------------------------------------------------------------------------

def save_results(results: list[dict], category: str, model_name: str, result_dir: str):
    """把评测结果保存为 BFCL 评分器能读取的文件。

    BFCL 期望的文件结构:
        result_dir/
        └── model_name/
            └── non_live/              (或 live/ 或 multi_turn/)
                └── BFCL_v4_{category}_result.json

    文件是 JSONL 格式，每行一个 JSON:
        {"id": "simple_python_0", "result": "func(a=1)"}
    """
    result_path = Path(result_dir)

    # 模型名中的 "/" 替换为 "_"，避免创建子目录
    safe_model_name = model_name.replace("/", "_")

    # 根据类别名决定放在哪个子目录
    if category.startswith("live_"):
        group_folder = "live"
    elif category.startswith("multi_turn_"):
        group_folder = "multi_turn"
    else:
        group_folder = "non_live"

    output_dir = result_path / safe_model_name / group_folder
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"BFCL_v4_{category}_result.json"

    with open(output_file, "w", encoding="utf-8") as f:
        for entry in results:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"💾 结果已保存到: {output_file}")
    return output_file


# --------------------------------------------------------------------------
# 第 9 步：主流程 —— 把以上所有步骤串起来
# --------------------------------------------------------------------------

async def run_evaluation():
    """执行完整的 BFCL 评测流程。"""

    print("=" * 60)
    print("🚀 BFCL 评测开始")
    print("=" * 60)

    # --- 步骤 A：准备数据 ---
    data_dir = find_data_directory()
    dataset = load_dataset(TEST_CATEGORY, data_dir)

    # 限制样本数
    if MAX_SAMPLES is not None:
        dataset = dataset[:MAX_SAMPLES]
        print(f"📋 限制测试样本数: {MAX_SAMPLES}")

    # --- 步骤 B：创建 Provider ---
    provider, model_name = create_provider()

    # --- 步骤 C：逐条测试 ---
    total_count = len(dataset)
    success_count = 0        # 成功返回 tool call 的次数
    no_tool_call_count = 0   # LLM 没有返回 tool call 的次数
    error_count = 0          # 出错的次数
    total_time = 0.0         # 总耗时

    all_results = []

    print(f"\n开始测试 {total_count} 条数据...\n")

    for index, test_item in enumerate(dataset):
        sample_id = test_item["id"]
        user_question = extract_user_question(test_item["question"])
        openai_tools = convert_functions_to_openai_tools(test_item["function"])

        # 打印进度
        print(f"[{index + 1}/{total_count}] 测试 {sample_id}")
        print(f"  问题: {user_question[:80]}{'...' if len(user_question) > 80 else ''}")

        try:
            # 调用 LLM
            start_time = time.time()
            llm_response = await ask_llm_to_call_functions(
                provider, model_name, user_question, openai_tools
            )
            elapsed_time = time.time() - start_time
            total_time += elapsed_time

            # 检查 LLM 是否返回了 tool calls
            if llm_response.tool_calls:
                result_string = convert_tool_calls_to_result_string(
                    llm_response.tool_calls, test_item["function"]
                )
                success_count += 1
                print(f"  ✅ 返回: {result_string[:80]}  ({elapsed_time:.1f}s)")
            else:
                # LLM 没有调用函数，而是回复了文字
                result_string = llm_response.content or ""
                no_tool_call_count += 1
                print(f"  ⚠️  未调用函数，文字回复: {result_string[:60]}")

            # 保存这条结果
            all_results.append({
                "id": sample_id,
                "result": result_string,
            })

        except Exception as error:
            error_count += 1
            print(f"  ❌ 出错: {error}")
            all_results.append({
                "id": sample_id,
                "result": "",
            })

    # --- 步骤 D：保存结果文件 ---
    print()
    output_file = save_results(all_results, TEST_CATEGORY, model_name, RESULT_DIR)

    # --- 步骤 E：打印汇总 ---
    print()
    print("=" * 60)
    print("📊 评测结果汇总")
    print("=" * 60)
    print(f"  模型:           {model_name}")
    print(f"  测试类别:        {TEST_CATEGORY}")
    print(f"  总样本数:        {total_count}")
    print(f"  成功调用函数:     {success_count}")
    print(f"  未调用函数:       {no_tool_call_count}")
    print(f"  出错:            {error_count}")

    if total_count > 0:
        success_rate = success_count / total_count * 100
        print(f"  Tool Call 率:    {success_rate:.1f}%")

    if total_count > 0:
        average_time = total_time / total_count
        print(f"  平均耗时:        {average_time:.2f} 秒/条")

    print(f"  结果文件:        {output_file}")
    print()
    print("下一步：使用 BFCL 官方评估器打分（需先安装 BFCL）：")
    print(f"  cd Test_Dataset/temp_gorilla/berkeley-function-call-leaderboard")
    print(f"  pip install -e .")
    safe_model = model_name.replace("/", "_")
    print(f"  bfcl evaluate --model {safe_model} "
          f"--test-category {TEST_CATEGORY} "
          f"--result-dir {Path(RESULT_DIR).resolve()}")
    print("=" * 60)


# --------------------------------------------------------------------------
# 入口：直接运行这个文件就会执行评测
# --------------------------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(run_evaluation())
