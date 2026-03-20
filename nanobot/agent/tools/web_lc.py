# 1. 导入
# 2. Pydantic 输入模型 (WebFetchInput)
# 3. 辅助函数 (_fetch_jina, _fetch_readability, _to_markdown) — 从 web.py 搬过来，去掉 self
# 4. 工厂函数 create_web_fetch_tool() — 返回 StructuredTool