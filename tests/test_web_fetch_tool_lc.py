"""Tests for LangChain web_fetch tool (web_lc.py)."""

import json

import httpx
import pytest
from langchain_core.utils.function_calling import convert_to_openai_function

from nanobot.agent.tools.web_lc import create_web_fetch_tool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _response(
    status: int = 200,
    json_data: dict | None = None,
    text: str = "",
    content_type: str = "text/html",
) -> httpx.Response:
    """Build a mock httpx.Response with optional JSON / plain-text body."""
    if json_data is not None:
        r = httpx.Response(status, json=json_data)
    else:
        r = httpx.Response(status, text=text, headers={"content-type": content_type})
    r._request = httpx.Request("GET", "https://mock")
    return r


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def test_schema():
    """验证 OpenAI function-calling schema 格式正确。"""
    tool = create_web_fetch_tool()
    schema = convert_to_openai_function(tool)

    assert schema["name"] == "web_fetch"
    props = schema["parameters"]["properties"]
    assert "url" in props
    assert "extractMode" in props
    assert "maxChars" in props
    assert "url" in schema["parameters"].get("required", [])


# ---------------------------------------------------------------------------
# URL validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalid_url_no_scheme():
    tool = create_web_fetch_tool()
    result = await tool.ainvoke({"url": "not-a-url"})
    data = json.loads(result)
    assert "error" in data
    assert "URL validation failed" in data["error"]


@pytest.mark.asyncio
async def test_invalid_url_ftp_scheme():
    tool = create_web_fetch_tool()
    result = await tool.ainvoke({"url": "ftp://example.com/file"})
    data = json.loads(result)
    assert "error" in data
    assert "http" in data["error"].lower() or "ftp" in data["error"].lower()


# ---------------------------------------------------------------------------
# Jina Reader path (happy path)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_jina_fetch_success(monkeypatch):
    """Jina Reader 返回正常内容时，应使用 jina extractor。"""
    async def mock_get(self, url, **kw):
        assert "r.jina.ai" in str(url)
        return _response(json_data={
            "data": {
                "title": "Example Page",
                "url": "https://example.com",
                "content": "Hello from Jina",
            }
        })

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    tool = create_web_fetch_tool()
    result = await tool.ainvoke({"url": "https://example.com"})
    data = json.loads(result)

    assert data["extractor"] == "jina"
    assert "Hello from Jina" in data["text"]
    assert "# Example Page" in data["text"]
    assert data["url"] == "https://example.com"


# ---------------------------------------------------------------------------
# Jina 429 → readability fallback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_jina_rate_limited_falls_back_to_readability(monkeypatch):
    """Jina 返回 429 时应回退到 readability。"""
    call_count = {"jina": 0, "readability": 0}

    async def mock_get(self, url, **kw):
        if "r.jina.ai" in str(url):
            call_count["jina"] += 1
            return _response(status=429, text="rate limited")
        call_count["readability"] += 1
        return _response(
            text="<html><head><title>Fallback</title></head>"
                 "<body><p>Readability content</p></body></html>",
            content_type="text/html",
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    tool = create_web_fetch_tool()
    result = await tool.ainvoke({"url": "https://example.com"})
    data = json.loads(result)

    assert call_count["jina"] == 1
    assert call_count["readability"] == 1
    assert data["extractor"] == "readability"
    assert "Readability content" in data["text"] or "Fallback" in data["text"]


# ---------------------------------------------------------------------------
# Jina exception → readability fallback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_jina_exception_falls_back_to_readability(monkeypatch):
    """Jina 抛异常时应回退到 readability。"""
    async def mock_get(self, url, **kw):
        if "r.jina.ai" in str(url):
            raise httpx.ConnectError("connection refused")
        return _response(
            text="<html><head><title>OK</title></head><body><p>works</p></body></html>",
            content_type="text/html",
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    tool = create_web_fetch_tool()
    result = await tool.ainvoke({"url": "https://example.com"})
    data = json.loads(result)

    assert data["extractor"] == "readability"


# ---------------------------------------------------------------------------
# Readability: JSON response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_readability_json_response(monkeypatch):
    """当目标返回 JSON 时，extractor 应为 'json'。"""
    async def mock_get(self, url, **kw):
        if "r.jina.ai" in str(url):
            raise httpx.ConnectError("skip jina")
        return _response(
            json_data={"key": "value", "nested": {"a": 1}},
            content_type="application/json",
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    tool = create_web_fetch_tool()
    result = await tool.ainvoke({"url": "https://api.example.com/data"})
    data = json.loads(result)

    assert data["extractor"] == "json"
    assert '"key"' in data["text"]


# ---------------------------------------------------------------------------
# Readability: plain text / raw response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_readability_raw_text_response(monkeypatch):
    """非 HTML/JSON 的响应应使用 'raw' extractor。"""
    async def mock_get(self, url, **kw):
        if "r.jina.ai" in str(url):
            raise httpx.ConnectError("skip jina")
        return _response(text="plain text body", content_type="text/plain")

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    tool = create_web_fetch_tool()
    result = await tool.ainvoke({"url": "https://example.com/robots.txt"})
    data = json.loads(result)

    assert data["extractor"] == "raw"
    assert "plain text body" in data["text"]


# ---------------------------------------------------------------------------
# Truncation (maxChars)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_truncation_with_max_chars(monkeypatch):
    """内容超过 maxChars 时应被截断。"""
    long_content = "A" * 500

    async def mock_get(self, url, **kw):
        assert "r.jina.ai" in str(url)
        return _response(json_data={
            "data": {"title": "", "url": url, "content": long_content}
        })

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    tool = create_web_fetch_tool()
    result = await tool.ainvoke({"url": "https://example.com", "maxChars": 200})
    data = json.loads(result)

    assert data["truncated"] is True
    assert data["length"] == 200


@pytest.mark.asyncio
async def test_no_truncation_when_content_short(monkeypatch):
    """内容未超过 maxChars 时 truncated 应为 False。"""
    async def mock_get(self, url, **kw):
        return _response(json_data={
            "data": {"title": "", "url": url, "content": "short"}
        })

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    tool = create_web_fetch_tool()
    result = await tool.ainvoke({"url": "https://example.com"})
    data = json.loads(result)

    assert data["truncated"] is False


# ---------------------------------------------------------------------------
# extract_mode = text
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extract_mode_text(monkeypatch):
    """extractMode='text' 时不应输出 markdown 格式的链接。"""
    html_body = (
        "<html><head><title>Page</title></head>"
        '<body><p>Hello <a href="https://link.com">Link</a></p></body></html>'
    )

    async def mock_get(self, url, **kw):
        if "r.jina.ai" in str(url):
            raise httpx.ConnectError("skip jina")
        return _response(text=html_body, content_type="text/html")

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    tool = create_web_fetch_tool()
    result = await tool.ainvoke({"url": "https://example.com", "extractMode": "text"})
    data = json.loads(result)

    assert "[Link]" not in data["text"]
    assert data["extractor"] == "readability"


# ---------------------------------------------------------------------------
# Factory default max_chars
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_factory_default_max_chars(monkeypatch):
    """工厂函数的 max_chars 参数应在未传 maxChars 时生效。"""
    long_content = "B" * 1000

    async def mock_get(self, url, **kw):
        return _response(json_data={
            "data": {"title": "", "url": url, "content": long_content}
        })

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    tool = create_web_fetch_tool(max_chars=300)
    result = await tool.ainvoke({"url": "https://example.com"})
    data = json.loads(result)

    assert data["truncated"] is True
    assert data["length"] == 300


# ---------------------------------------------------------------------------
# Network error in readability path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_readability_network_error(monkeypatch):
    """Jina 和 readability 都失败时应返回 error JSON。"""
    async def mock_get(self, url, **kw):
        raise httpx.ConnectError("network down")

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    tool = create_web_fetch_tool()
    result = await tool.ainvoke({"url": "https://example.com"})
    data = json.loads(result)

    assert "error" in data
