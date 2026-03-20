from pathlib import Path
from code2prompt_rs import Code2Prompt
from litellm import completion

# 你想问 LLM 的问题
QUESTION = "请分析这个项目的 agent 模块架构，并说明各文件的职责"

# 生成提示词
c2p = Code2Prompt(
    path="./nanobot/agent",
    include_patterns=["*.py"],
    exclude_patterns=["__pycache__/*", "*.pyc"],
    line_numbers=True,
    code_blocks=True,
)

result = c2p.generate()
tokens = c2p.token_count(encoding="cl100k")
print(f"Token 数量 (cl100k): {tokens}")

# 保存到文件（可选，方便复用）
output_file = Path("prompt_output.md")
output_file.write_text(result.prompt, encoding="utf-8")
print(f"提示词已保存到 {output_file}")

# 拼接最终消息：代码上下文 + 你的问题
final_prompt = f"{result.prompt}\n\n---\n\n{QUESTION}"

# # 发送给 LLM（litellm 支持 OpenAI / Claude / Gemini 等）
# response = completion(
#     model="gemini/gemini-2.0-flash",   # 换成你使用的模型
#     messages=[{"role": "user", "content": final_prompt}],
# )

# print(response.choices[0].message.content)