"""
GAIA 评测脚本 —— 测试 nanobot Agent 的综合推理与工具使用能力。

使用方法:
    python nanobot/utils/GAIA_eval.py                     # 默认 validation Level 1, 前5条
    python nanobot/utils/GAIA_eval.py --level 2 --max 20  # Level 2, 前20条
    python nanobot/utils/GAIA_eval.py --level all --max 0  # 全部 Level, 全量
"""

# ==========================================================================
# 配置区
# ==========================================================================

DATASET_DIR = "Test_Dataset/gaia"
RESULT_DIR = "./gaia_results"
SPLIT = "validation"

# ==========================================================================
# 以下是实现
# ==========================================================================


import argparse
import asyncio
import json
import re
import string
import time
import warnings
from pathlib import Path

import pandas as pd


# --------------------------------------------------------------------------
# GAIA 官方评分逻辑 (来自 gaia-benchmark/leaderboard scorer.py)
# --------------------------------------------------------------------------

def _normalize_number_str(number_str: str) -> float:
    for char in ["$", "%", ","]:
        number_str = number_str.replace(char, "")
    try:
        return float(number_str)
    except ValueError:
        return float("inf")


def _normalize_str(input_str: str, remove_punct: bool = True) -> str:
    no_spaces = re.sub(r"\s", "", input_str)
    if remove_punct:
        translator = str.maketrans("", "", string.punctuation)
        return no_spaces.lower().translate(translator)
    return no_spaces.lower()


def _is_float(element) -> bool:
    try:
        float(element)
        return True
    except (ValueError, TypeError):
        return False


def question_scorer(model_answer: str, ground_truth: str) -> bool:
    if model_answer is None:
        model_answer = "None"
    if _is_float(ground_truth):
        return _normalize_number_str(model_answer) == float(ground_truth)
    elif any(c in ground_truth for c in [",", ";"]):
        gt_elems = re.split(r"[,;]", ground_truth)
        ma_elems = re.split(r"[,;]", model_answer)
        if len(gt_elems) != len(ma_elems):
            return False
        return all(
            _normalize_number_str(m) == float(g) if _is_float(g)
            else _normalize_str(m, remove_punct=False) == _normalize_str(g, remove_punct=False)
            for m, g in zip(ma_elems, gt_elems)
        )
    else:
        return _normalize_str(model_answer) == _normalize_str(ground_truth)


# --------------------------------------------------------------------------
# 从 Agent 回答中提取最终答案
# --------------------------------------------------------------------------

_FINAL_ANSWER_RE = re.compile(
    r"(?:FINAL\s*ANSWER|最终答案|答案)[：:\s]*(.+)",
    re.IGNORECASE,
)


def extract_final_answer(response: str) -> str:
    """尝试从 Agent 回复中提取 'FINAL ANSWER: xxx'，否则取最后一行非空文本。"""
    if not response:
        return ""
    for line in reversed(response.strip().splitlines()):
        line = line.strip()
        if not line:
            continue
        m = _FINAL_ANSWER_RE.search(line)
        if m:
            return m.group(1).strip()
    return response.strip().splitlines()[-1].strip()


# --------------------------------------------------------------------------
# 加载数据集
# --------------------------------------------------------------------------

def load_dataset(dataset_dir: str, split: str, level: str | None, max_samples: int) -> list[dict]:
    base = Path(dataset_dir) / "2023" / split
    if level and level != "all":
        pq_file = base / f"metadata.level{level}.parquet"
    else:
        pq_file = base / "metadata.parquet"

    if not pq_file.exists():
        raise FileNotFoundError(f"找不到数据文件: {pq_file}")

    df = pd.read_parquet(pq_file)
    records = df.to_dict("records")
    if max_samples > 0:
        records = records[:max_samples]
    print(f"已加载 {len(records)} 条数据 (split={split}, level={level or 'all'})")
    return records


# --------------------------------------------------------------------------
# 构建 Agent 的提示
# --------------------------------------------------------------------------

GAIA_SYSTEM_HINT = (
    "You are solving a GAIA benchmark question. "
    "Use your tools (web search, file reading, shell commands, etc.) to find the answer. "
    "After you have the answer, state it clearly on a single line prefixed with 'FINAL ANSWER: '. "
    "The answer should be concise: a number, a short string, or a comma-separated list — no extra explanation."
)


def build_prompt(question: str, file_path: str | None, dataset_dir: str) -> str:
    parts = [GAIA_SYSTEM_HINT, "", f"Question: {question}"]
    if file_path:
        abs_path = str(Path(dataset_dir).resolve() / file_path)
        parts.append(f"\nAn attached file is available at: {abs_path}")
    return "\n".join(parts)


# --------------------------------------------------------------------------
# 创建 AgentLoop (复用 nanobot 完整能力)
# --------------------------------------------------------------------------

def create_agent_loop():
    from nanobot.config.loader import load_config
    from nanobot.config.schema import ExecToolConfig, WebSearchConfig
    from nanobot.agent.loop import AgentLoop
    from nanobot.bus.queue import MessageBus

    config = load_config()
    model_name = config.agents.defaults.model
    provider_name = config.get_provider_name(model_name)
    provider_config = config.get_provider(model_name)

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

    ws_cfg = config.agents.defaults
    web_search = WebSearchConfig(**(config.web_search.model_dump() if hasattr(config, "web_search") and config.web_search else {}))
    exec_cfg = ExecToolConfig(**(config.exec.model_dump() if hasattr(config, "exec") and config.exec else {}))

    workspace = Path.cwd()
    bus = MessageBus()
    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=workspace,
        model=model_name,
        max_iterations=ws_cfg.max_iterations if hasattr(ws_cfg, "max_iterations") else 25,
        web_search_config=web_search,
        exec_config=exec_cfg,
    )
    print(f"模型: {model_name} | Provider: {provider_name}")
    return agent, model_name


# --------------------------------------------------------------------------
# 主评测流程
# --------------------------------------------------------------------------

async def run_evaluation(args):
    dataset = load_dataset(args.dataset_dir, args.split, args.level, args.max)
    agent, model_name = create_agent_loop()

    results = []
    correct = {1: 0, 2: 0, 3: 0}
    total = {1: 0, 2: 0, 3: 0}
    t0 = time.time()

    for i, item in enumerate(dataset):
        task_id = item["task_id"]
        question = item["Question"]
        gt = str(item.get("Final answer", ""))
        level = int(item["Level"])
        file_path = item.get("file_path") or item.get("file_name") or ""
        if not file_path or (isinstance(file_path, float)):
            file_path = None

        total[level] = total.get(level, 0) + 1
        prompt = build_prompt(question, file_path, args.dataset_dir)

        print(f"\n[{i+1}/{len(dataset)}] Level {level} | {task_id}")
        print(f"  Q: {question[:100]}{'...' if len(question)>100 else ''}")

        try:
            session_key = f"gaia_eval:{task_id}"
            response = await agent.process_direct(
                content=prompt,
                session_key=session_key,
                channel="cli",
                chat_id=task_id,
            )
            answer = extract_final_answer(response)
            is_correct = question_scorer(answer, gt) if gt else None
            if is_correct:
                correct[level] = correct.get(level, 0) + 1
            status = "✅" if is_correct else "❌"
            print(f"  A: {answer}")
            print(f"  GT: {gt}  {status}")
        except Exception as e:
            answer = ""
            is_correct = False
            print(f"  ❌ Error: {e}")

        results.append({
            "task_id": task_id,
            "level": level,
            "model_answer": answer,
            "ground_truth": gt,
            "correct": is_correct,
        })

    elapsed = time.time() - t0

    # 保存结果
    out_dir = Path(args.result_dir) / model_name.replace("/", "_")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"gaia_{args.split}_level{args.level or 'all'}.jsonl"
    with open(out_file, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 汇总
    print("\n" + "=" * 60)
    print("GAIA 评测结果")
    print("=" * 60)
    print(f"  模型:    {model_name}")
    print(f"  Split:   {args.split}")
    print(f"  总样本:  {len(results)}")
    print(f"  耗时:    {elapsed:.0f}s ({elapsed/max(len(results),1):.1f}s/条)")
    for lv in sorted(total):
        if total[lv] > 0:
            acc = correct[lv] / total[lv] * 100
            print(f"  Level {lv}: {correct[lv]}/{total[lv]} = {acc:.1f}%")
    all_correct = sum(correct.values())
    all_total = sum(total.values())
    if all_total:
        print(f"  Overall: {all_correct}/{all_total} = {all_correct/all_total*100:.1f}%")
    print(f"  结果:    {out_file}")
    print("=" * 60)

    await agent.close_mcp()


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="GAIA Benchmark Evaluation for nanobot Agent")
    parser.add_argument("--level", default="1", help="难度级别: 1, 2, 3 或 all (默认: 1)")
    parser.add_argument("--max", type=int, default=5, help="最大样本数, 0=全部 (默认: 5)")
    parser.add_argument("--split", default=SPLIT, help="数据集 split (默认: validation)")
    parser.add_argument("--dataset-dir", default=DATASET_DIR, help="数据集目录")
    parser.add_argument("--result-dir", default=RESULT_DIR, help="结果输出目录")
    args = parser.parse_args()
    asyncio.run(run_evaluation(args))


if __name__ == "__main__":
    main()
