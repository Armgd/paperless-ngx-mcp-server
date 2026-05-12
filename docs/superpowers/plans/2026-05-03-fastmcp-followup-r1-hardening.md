# FastMCP Followup — Phase 1 Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wrap up cheap-and-correct items from the FastMCP best-practices review: dedup the binary-headers HTTP path, guard `interactive_search` against clients without elicitation support, and document `MCP_STATELESS` + module-import semantics.

**Architecture:** All edits are surgical — one helper consolidation, one defensive wrapper, two doc snippets. No new files. No public tool-surface changes; only `PaperlessClient.request` gains an additive keyword arg. Phases 2 (typed Pydantic responses) and 3 (MCP resources) are deferred to separate plans because their shape depends on empirical paperless responses and an open scoping decision respectively.

**Tech Stack:** Python 3.12, FastMCP 3.2.4, httpx 0.28+, pytest-asyncio, mypy, ruff. Uses `mcp.shared.exceptions.McpError` (re-exported as `mcp.McpError`) and `fastmcp.exceptions.ToolError`.

---

## File Structure

**Modify:**
- `src/paperless_mcp/client.py` — extend `request()` with `expect_headers: bool = False`; refactor `get_binary_with_headers` to delegate.
- `src/paperless_mcp/tools/highlevel.py` — wrap first `ctx.elicit()` call with try/except; raise `ToolError` on `McpError`/`NotImplementedError`/`RuntimeError`.
- `tests/test_client.py` — add coverage for `expect_headers=True` path.
- `tests/test_interactive_search.py` — add coverage for elicit-unsupported case.
- `README.md` — append `MCP_STATELESS` env-var doc to HTTP/Docker section.
- `CLAUDE.md` — append note that `Settings.from_env()` runs at import time.

**No new files. No deleted files.**

---

## Task 1: Add `expect_headers` to `PaperlessClient.request`

**Files:**
- Modify: `src/paperless_mcp/client.py:35-55`
- Test: `tests/test_client.py`

- [ ] **Step 1: Read current `request()` signature and body**

Run: `sed -n '35,60p' src/paperless_mcp/client.py`

Expected: shows `request(self, method, path, *, params=None, json=None, expect_binary=False) -> Any`.

- [ ] **Step 2: Write the failing test**

Append to `tests/test_client.py` (after the last existing test, around line 126):

```python
async def test_request_expect_headers_returns_tuple() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=b"PNGDATA", headers={"content-type": "image/png"}
        )

    c = _make_client(handler)
    body, headers = await c.request(
        "GET",
        "/api/documents/1/thumb/",
        expect_binary=True,
        expect_headers=True,
    )
    assert body == b"PNGDATA"
    assert headers["content-type"] == "image/png"
    await c.aclose()
```

This reuses the existing `_make_client` + `httpx.MockTransport` helper at the top of `tests/test_client.py:11-28`. Do not introduce a new mocking library.

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_client.py::test_request_expect_headers_returns_tuple -v`

Expected: FAIL with `TypeError: request() got an unexpected keyword argument 'expect_headers'`.

- [ ] **Step 4: Implement `expect_headers` in `request()`**

Replace the entire current `request()` method body (lines 35-55 of `src/paperless_mcp/client.py`) with:

```python
    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        expect_binary: bool = False,
        expect_headers: bool = False,
    ) -> Any:
        clean = {k: v for k, v in (params or {}).items() if v is not None}
        resp = await self._client.request(method, path, params=clean, json=json)
        if resp.status_code >= 400:
            raise PaperlessAPIError(resp.status_code, resp.text, method, path)
        if resp.status_code == 204 or not resp.content:
            body: Any = None
        elif expect_binary:
            body = resp.content
        else:
            ctype = resp.headers.get("content-type", "")
            body = resp.json() if "application/json" in ctype else resp.content
        if expect_headers:
            return body, dict(resp.headers)
        return body
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_client.py::test_request_expect_headers_returns_tuple -v`

Expected: PASS.

- [ ] **Step 6: Refactor `get_binary_with_headers` to delegate**

Replace the body of `get_binary_with_headers` (currently lines 63-70 of `src/paperless_mcp/client.py`) with a one-line delegation:

```python
    async def get_binary_with_headers(
        self, path: str, **kw: Any
    ) -> tuple[bytes, dict[str, str]]:
        return await self.request(
            "GET", path, expect_binary=True, expect_headers=True, **kw
        )
```

- [ ] **Step 7: Run full test suite**

Run: `uv run pytest`

Expected: 89/89 prior tests PASS plus the one new test = 90/90 PASS.

- [ ] **Step 8: Run lint + mypy**

Run: `uv run ruff check . && uv run mypy src`

Expected: `All checks passed!` and `Success: no issues found in 18 source files`.

- [ ] **Step 9: Commit**

```bash
git add src/paperless_mcp/client.py tests/test_client.py
git commit -m "refactor(client): fold get_binary_with_headers into request(expect_headers=True)"
```

---

## Task 2: Guard `interactive_search` when client lacks elicitation

**Files:**
- Modify: `src/paperless_mcp/tools/highlevel.py:123-141`
- Test: `tests/test_interactive_search.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_interactive_search.py`:

```python
async def test_elicit_unsupported_raises_tool_error(
    mcp_client: Client, fake_client: FakeClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastmcp.exceptions import ToolError
    from mcp import McpError
    from mcp.types import ErrorData

    from paperless_mcp.app import mcp

    tool = await mcp.get_tool("interactive_search")
    original = tool.fn

    class _NoElicitContext:
        async def elicit(self, *_: object, **__: object) -> object:
            raise McpError(
                ErrorData(code=-32601, message="elicitation not supported")
            )

    async def wrapper(_injected_ctx: object = None, **kwargs: object) -> object:
        return await original(_NoElicitContext(), **kwargs)

    monkeypatch.setattr(tool, "fn", wrapper)

    with pytest.raises(ToolError) as excinfo:
        await mcp_client.call_tool("interactive_search", {})
    assert "elicit" in str(excinfo.value).lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_interactive_search.py::test_elicit_unsupported_raises_tool_error -v`

Expected: FAIL — currently `McpError` either propagates as a non-`ToolError` exception or is wrapped by FastMCP into a different shape. Capture the exact failure mode in the output before moving on; if it surfaces as a different exception type, Step 4's `except` tuple may need to be widened.

- [ ] **Step 3: Add imports to `highlevel.py`**

Open `src/paperless_mcp/tools/highlevel.py`. After the existing line `from fastmcp import Context` and before `from pydantic import Field`, add:

```python
from fastmcp.exceptions import ToolError
from mcp import McpError
```

- [ ] **Step 4: Wrap the first elicit call**

Locate the body of `interactive_search` in `src/paperless_mcp/tools/highlevel.py` (function starts around line 124). Replace the first elicit block — currently:

```python
    strategy = await ctx.elicit(
        "How do you want to search?",
        response_type=["full_text", "filters", "recent"],  # type: ignore[arg-type]
    )
```

…with the guarded version:

```python
    try:
        strategy = await ctx.elicit(
            "How do you want to search?",
            response_type=["full_text", "filters", "recent"],  # type: ignore[arg-type]
        )
    except (McpError, NotImplementedError, RuntimeError) as exc:
        raise ToolError(
            "interactive_search requires a client that supports MCP elicitation. "
            "Use find_documents, answer_from_documents, or recent_documents instead."
        ) from exc
```

Keep the rest of the function (the `if strategy.action != "accept":` line and below) unchanged.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_interactive_search.py::test_elicit_unsupported_raises_tool_error -v`

Expected: PASS. If it still fails, the failure output from Step 2 will indicate which extra exception class to add to the `except` tuple — add it and retry.

- [ ] **Step 6: Run full test suite**

Run: `uv run pytest`

Expected: 90/90 from Task 1 plus the new test = 91/91 PASS.

- [ ] **Step 7: Run lint + mypy**

Run: `uv run ruff check . && uv run mypy src`

Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add src/paperless_mcp/tools/highlevel.py tests/test_interactive_search.py
git commit -m "fix(highlevel): raise ToolError when client does not support elicitation"
```

---

## Task 3: Document `MCP_STATELESS` env var in README

**Files:**
- Modify: `README.md` (HTTP / Docker section, lines 91-95)

- [ ] **Step 1: Read the existing HTTP / Docker section**

Run: `sed -n '91,96p' README.md`

Expected: shows the two-line description of `MCP_TRANSPORT=http` and `MCP_AUTH_TOKEN`.

- [ ] **Step 2: Append `MCP_STATELESS` documentation**

Edit `README.md`. Find the existing line:

```
HTTP transport refuses to start without `MCP_AUTH_TOKEN`. Set it to a long random string; clients send `Authorization: Bearer <token>`.
```

…and immediately after it, insert a blank line then this new paragraph:

```markdown
By default `MCP_STATELESS=true` — each request stands alone, no MCP session continuity. Set `MCP_STATELESS=false` only if your client maintains a streamable HTTP session and relies on per-session state (most don't).
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(readme): document MCP_STATELESS env var default"
```

---

## Task 4: Document `Settings.from_env()` import-time semantics in CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Locate the conventions section**

Run: `grep -n "^## Conventions" CLAUDE.md`

Expected: returns one line number (the start of the Conventions section).

- [ ] **Step 2: Append a bullet under Conventions**

Edit `CLAUDE.md`. Inside the `## Conventions` section, after the last existing bullet, add:

```markdown
- `Settings.from_env()` runs at import of `paperless_mcp.app` (transitively via `paperless_mcp.config`). Tests must set `PAPERLESS_URL` and `PAPERLESS_TOKEN` *before* importing any project module — see `tests/conftest.py:8-9`.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude): note Settings.from_env() runs at import time"
```

---

## Final verification

- [ ] **Step 1: Run full quality gate**

Run: `uv run pytest && uv run ruff check . && uv run mypy src`

Expected: 91/91 PASS, ruff clean, mypy clean.

- [ ] **Step 2: Push to both remotes**

```bash
git push origin main
git push github main
```

Expected: both pushes succeed without rejection. The forgejo remote is `origin`, GitHub is `github`.

---

## Out of scope (deferred to future plans)

These items from the broader review intentionally do not appear here:

- **Phase 2 — Typed Pydantic response models (M2):** needs empirical paperless API responses to design `DocumentSummary`/`FindDocumentsResult` field shapes accurately. Plan after Phase 1 lands.
- **Phase 3 — MCP Resources (M3):** needs scoping decision (taxonomy-only vs. include documents) before plan.
- **`FileSystemProvider` auto-discovery (M4):** low value at current 8-module size; revisit only if more tool modules are added.

Each will be a standalone plan in `docs/superpowers/plans/` once unblocked.
