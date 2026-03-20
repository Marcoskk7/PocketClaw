# 1. 导入
import asyncio
import html
import json
import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx
from langchain_core.tools import BaseTool, StructuredTool, tool
from loguru import logger
from pydantic import BaseModel, Field

from nanobot.config.schema import WebSearchConfig

# Shared constants
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_2) AppleWebKit/537.36"
MAX_REDIRECTS = 5  # Limit redirects to prevent DoS attacks

def _strip_tags(text: str) -> str:
    """Remove HTML tags and decode entities."""
    text = re.sub(r'<script[\s\S]*?</script>', '', text, flags=re.I)
    text = re.sub(r'<style[\s\S]*?</style>', '', text, flags=re.I)
    text = re.sub(r'<[^>]+>', '', text)
    return html.unescape(text).strip()


def _normalize(text: str) -> str:
    """Normalize whitespace."""
    text = re.sub(r'[ \t]+', ' ', text)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def _validate_url(url: str) -> tuple[bool, str]:
    """Validate URL: must be http(s) with valid domain."""
    try:
        p = urlparse(url)
        if p.scheme not in ('http', 'https'):
            return False, f"Only http/https allowed, got '{p.scheme or 'none'}'"
        if not p.netloc:
            return False, "Missing domain"
        return True, ""
    except Exception as e:
        return False, str(e)
# 2. Pydantic 输入模型 (WebFetchInput)
# lc版本
class WebFetchInput(BaseModel):
    url: str = Field(description='URL to fetch')
    extractMode: str = Field(default='markdown', description='markdown or text')
    maxChars: int | None = Field(default=None, ge=100, description='Maximum characters to return')

class WebSearchInput(BaseModel):
    query: str = Field(description='Search query')
    # 与 web.py 的 WebSearchTool 一致：仅 query 必填；count 省略时用 config.max_results
    count: int | None = Field(default=None, description='Results (1-10)', ge=1, le=10)
# 3. 辅助函数 (_fetch_jina, _fetch_readability, _to_markdown) — 从 web.py 搬过来，去掉 
# ========== 3a. _to_markdown（旧代码有 ，新去掉） ==========

# 旧 web.py 第 313 行:
#   def _to_markdown(, html_content: str) -> str:
# 新:
def _to_markdown(html_content: str) -> str:
    text = re.sub(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>',
                  lambda m: f'[{_strip_tags(m[2])}]({m[1]})', html_content, flags=re.I)
    text = re.sub(r'<h([1-6])[^>]*>([\s\S]*?)</h\1>',
                  lambda m: f'\n{"#" * int(m[1])} {_strip_tags(m[2])}\n', text, flags=re.I)
    text = re.sub(r'<li[^>]*>([\s\S]*?)</li>',
                  lambda m: f'\n- {_strip_tags(m[1])}', text, flags=re.I)
    text = re.sub(r'</(p|div|section|article)>', '\n\n', text, flags=re.I)
    text = re.sub(r'<(br|hr)\s*/?>', '\n', text, flags=re.I)
    return _normalize(_strip_tags(text))


# ========== 3b. _fetch_jina（去掉 ，.proxy → 参数 proxy） ==========

# 旧 web.py 第 238 行:
#   async def _fetch_jina(, url: str, max_chars: int) -> str | None:
#       ... proxy=.proxy ...
# 新:
async def _fetch_jina(url: str, max_chars: int, proxy: str | None) -> str | None:
    try:
        headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
        jina_key = os.environ.get("JINA_API_KEY", "")
        if jina_key:
            headers["Authorization"] = f"Bearer {jina_key}"
        async with httpx.AsyncClient(proxy=proxy, timeout=20.0) as client:
            r = await client.get(f"https://r.jina.ai/{url}", headers=headers)
            if r.status_code == 429:
                logger.debug("Jina Reader rate limited, falling back to readability")
                return None
            r.raise_for_status()

        data = r.json().get("data", {})
        title = data.get("title", "")
        text = data.get("content", "")
        if not text:
            return None

        if title:
            text = f"# {title}\n\n{text}"
        truncated = len(text) > max_chars
        if truncated:
            text = text[:max_chars]

        return json.dumps({
            "url": url, "finalUrl": data.get("url", url), "status": r.status_code,
            "extractor": "jina", "truncated": truncated, "length": len(text), "text": text,
        }, ensure_ascii=False)
    except Exception as e:
        logger.debug("Jina Reader failed for {}, falling back to readability: {}", url, e)
        return None


# ========== 3c. _fetch_readability（去掉 ，.proxy → proxy，._to_markdown → _to_markdown） ==========

# 旧 web.py 第 272 行:
#   async def _fetch_readability(, url, extract_mode, max_chars):
#       ... proxy=.proxy ...
#       ... ._to_markdown(...) ...
# 新:
async def _fetch_readability(url: str, extract_mode: str, max_chars: int, proxy: str | None) -> str:
    from readability import Document

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            max_redirects=MAX_REDIRECTS,
            timeout=30.0,
            proxy=proxy,
        ) as client:
            r = await client.get(url, headers={"User-Agent": USER_AGENT})
            r.raise_for_status()

        ctype = r.headers.get("content-type", "")

        if "application/json" in ctype:
            text, extractor = json.dumps(r.json(), indent=2, ensure_ascii=False), "json"
        elif "text/html" in ctype or r.text[:256].lower().startswith(("<!doctype", "<html")):
            doc = Document(r.text)
            content = _to_markdown(doc.summary()) if extract_mode == "markdown" else _strip_tags(doc.summary())
            text = f"# {doc.title()}\n\n{content}" if doc.title() else content
            extractor = "readability"
        else:
            text, extractor = r.text, "raw"

        truncated = len(text) > max_chars
        if truncated:
            text = text[:max_chars]

        return json.dumps({
            "url": url, "finalUrl": str(r.url), "status": r.status_code,
            "extractor": extractor, "truncated": truncated, "length": len(text), "text": text,
        }, ensure_ascii=False)
    except httpx.ProxyError as e:
        logger.error("WebFetch proxy error for {}: {}", url, e)
        return json.dumps({"error": f"Proxy error: {e}", "url": url}, ensure_ascii=False)
    except Exception as e:
        logger.error("WebFetch error for {}: {}", url, e)
        return json.dumps({"error": str(e), "url": url}, ensure_ascii=False)


# ============== web_search 辅助函数 ======================

def _format_results(query: str, items: list[dict[str, Any]], n: int) -> str:
    """Format provider results into shared plaintext output."""
    if not items:
        return f"No results for: {query}"
    lines = [f"Results for: {query}\n"]
    for i, item in enumerate(items[:n], 1):
        title = _normalize(_strip_tags(item.get("title", "")))
        snippet = _normalize(_strip_tags(item.get("content", "")))
        lines.append(f"{i}. {title}\n   {item.get('url', '')}")
        if snippet:
            lines.append(f"   {snippet}")
    return "\n".join(lines)


async def _search_brave(query: str, n: int, config: WebSearchConfig, proxy: str | None) -> str:
    api_key = config.api_key or os.environ.get("BRAVE_API_KEY", "")
    if not api_key:
        logger.warning("BRAVE_API_KEY not set, falling back to DuckDuckGo")
        return await _search_duckduckgo(query, n, proxy)
    try:
        async with httpx.AsyncClient(proxy=proxy) as client:
            r = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": n},
                headers={"Accept": "application/json", "X-Subscription-Token": api_key},
                timeout=10.0,
            )
            r.raise_for_status()
        items = [
            {"title": x.get("title", ""), "url": x.get("url", ""), "content": x.get("description", "")}
            for x in r.json().get("web", {}).get("results", [])
        ]
        return _format_results(query, items, n)
    except Exception as e:
        return f"Error: {e}"


async def _search_tavily(query: str, n: int, config: WebSearchConfig, proxy: str | None) -> str:
    api_key = config.api_key or os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        logger.warning("TAVILY_API_KEY not set, falling back to DuckDuckGo")
        return await _search_duckduckgo(query, n, proxy)
    try:
        async with httpx.AsyncClient(proxy=proxy) as client:
            r = await client.post(
                "https://api.tavily.com/search",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"query": query, "max_results": n},
                timeout=15.0,
            )
            r.raise_for_status()
        return _format_results(query, r.json().get("results", []), n)
    except Exception as e:
        return f"Error: {e}"


async def _search_searxng(query: str, n: int, config: WebSearchConfig, proxy: str | None) -> str:
    base_url = (config.base_url or os.environ.get("SEARXNG_BASE_URL", "")).strip()
    if not base_url:
        logger.warning("SEARXNG_BASE_URL not set, falling back to DuckDuckGo")
        return await _search_duckduckgo(query, n, proxy)
    endpoint = f"{base_url.rstrip('/')}/search"
    is_valid, error_msg = _validate_url(endpoint)
    if not is_valid:
        return f"Error: invalid SearXNG URL: {error_msg}"
    try:
        async with httpx.AsyncClient(proxy=proxy) as client:
            r = await client.get(
                endpoint,
                params={"q": query, "format": "json"},
                headers={"User-Agent": USER_AGENT},
                timeout=10.0,
            )
            r.raise_for_status()
        return _format_results(query, r.json().get("results", []), n)
    except Exception as e:
        return f"Error: {e}"


async def _search_jina(query: str, n: int, config: WebSearchConfig, proxy: str | None) -> str:
    api_key = config.api_key or os.environ.get("JINA_API_KEY", "")
    if not api_key:
        logger.warning("JINA_API_KEY not set, falling back to DuckDuckGo")
        return await _search_duckduckgo(query, n, proxy)
    try:
        headers = {"Accept": "application/json", "Authorization": f"Bearer {api_key}"}
        async with httpx.AsyncClient(proxy=proxy) as client:
            r = await client.get(
                "https://s.jina.ai/",
                params={"q": query},
                headers=headers,
                timeout=15.0,
            )
            r.raise_for_status()
        data = r.json().get("data", [])[:n]
        items = [
            {"title": d.get("title", ""), "url": d.get("url", ""), "content": d.get("content", "")[:500]}
            for d in data
        ]
        return _format_results(query, items, n)
    except Exception as e:
        return f"Error: {e}"


async def _search_duckduckgo(query: str, n: int, proxy: str | None) -> str:
    try:
        from ddgs import DDGS

        ddgs = DDGS(timeout=10)
        raw = await asyncio.to_thread(ddgs.text, query, max_results=n)
        if not raw:
            return f"No results for: {query}"
        items = [
            {"title": r.get("title", ""), "url": r.get("href", ""), "content": r.get("body", "")}
            for r in raw
        ]
        return _format_results(query, items, n)
    except Exception as e:
        logger.warning("DuckDuckGo search failed: {}", e)
        return f"Error: DuckDuckGo search failed ({e})"
# 4. 工厂函数 create_web_fetch_tool() — 返回 StructuredTool

_DEFAULT_MAX_CHARS = 50000
def create_web_fetch_tool(max_chars: int = _DEFAULT_MAX_CHARS, proxy: str | None = None) :
    """工厂函数: 创建一个带配置的 web_fetch 工具"""

    @tool(args_schema = WebFetchInput)
    async def web_fetch(url: str, extractMode: str = 'markdown', maxChars: int|None = None)->str:
        """Fetch URL and extract readable content (HTML → markdown/text)."""
        effective_max = maxChars or max_chars
        is_valid, error_msg = _validate_url(url)
        if not is_valid:
            return json.dumps(
                {"error": f"URL validation failed: {error_msg}", "url": url},
                ensure_ascii=False,
            )
        result = await _fetch_jina(url, effective_max, proxy)
        if result is None:
            result = await _fetch_readability(url, extractMode, effective_max, proxy)
        return result
    
    return web_fetch

def create_web_search_tool(proxy: str | None = None, config: WebSearchConfig | None = None):
    """工厂函数: 创建一个带配置的 web_search 工具"""
    cfg = config if config is not None else WebSearchConfig()

    @tool(args_schema=WebSearchInput)
    async def web_search(query: str, count: int | None = None) -> str:
        """Search the web. Returns titles, URLs, and snippets."""
        provider = cfg.provider.strip().lower() or "brave"
        n = min(max(count or cfg.max_results, 1), 10)

        if provider == "duckduckgo":
            return await _search_duckduckgo(query, n, proxy)
        elif provider == "tavily":
            return await _search_tavily(query, n, cfg, proxy)
        elif provider == "searxng":
            return await _search_searxng(query, n, cfg, proxy)
        elif provider == "jina":
            return await _search_jina(query, n, cfg, proxy)
        elif provider == "brave":
            return await _search_brave(query, n, cfg, proxy)
        else:
            return f"Error: unknown search provider '{provider}'"

    return web_search