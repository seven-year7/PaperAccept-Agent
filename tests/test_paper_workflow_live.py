"""
/**
 * @Module: tests/test_paper_workflow_live.py
 * @Description: 论文工作流「整图完全真实」集成测试：真 OpenRouter、真 arXiv、真 retrieve_knowledge（Milvus/混合检索等与线上一致），不 patch 业务链。
 *   默认跳过（需 PAPER_WORKFLOW_LIVE_TEST=1 与密钥）；工作区默认落盘到项目内 `data/paper_workflow_live_preview/{run_id}/`（`run_id` 为 `YYYY-mm-dd_HHMM` 时间戳，同分钟冲突时 `_2`…；根目录可 env 覆盖），便于本地查看 readings.md / report.md。写作阶段默认不调用知识库（config.paper_writing_rag_enabled=false）；整图测 Milvus 时可将 PAPER_WRITING_RAG_ENABLED=true 或保留 fixture 内 connect 以兼容后续扩展。
 * @Interface: PAPER_WORKFLOW_LIVE_TEST=1 pytest tests/test_paper_workflow_live.py -v -o addopts=
 */
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from app.config import config
from app.core.milvus_client import milvus_manager
from app.services.paper_workflow_service import run_paper_research_stream

# 与 Mock e2e 对齐，便于对照「同一用户意图」下真链路与假链路
FIXED_USER_REQUEST = "帮我查询最近一年的网络攻击的论文"

pytestmark = pytest.mark.integration

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
# 相对项目根，与 paper_workflow_service._project_root 拼接一致
_DEFAULT_LIVE_WS_REL = "data/paper_workflow_live_preview"


def _live_workspace_root_relative() -> str:
    custom = (os.environ.get("PAPER_WORKFLOW_LIVE_WORKSPACE_ROOT") or "").strip()
    rel = custom if custom else _DEFAULT_LIVE_WS_REL
    return rel.replace("\\", "/")


def _paper_workflow_live_skip_reason() -> str:
    # @Step: 1 - 双闸：防误扣费 + 无密钥时 skip（CI 默认全绿）
    if os.environ.get("PAPER_WORKFLOW_LIVE_TEST", "").strip() != "1":
        return "Set PAPER_WORKFLOW_LIVE_TEST=1 to run (see readme.txt)."
    if not (config.openrouter_api_key or "").strip():
        return "Missing OPENROUTER_API_KEY / openrouter_api_key in .env."
    return ""


_LIVE_SKIP_REASON = _paper_workflow_live_skip_reason()


@pytest.fixture
def paper_live_isolation(monkeypatch):
    """工作区默认固定到项目内目录（便于肉眼看 md）；可设 PAPER_WORKFLOW_LIVE_WORKSPACE_ROOT 覆盖。

    pytest 进程不会走 FastAPI lifespan，也未必 import vector_store_manager；
    必须在首帧 retrieve_knowledge 前执行 milvus_manager.connect()，否则报
    「Collection 未初始化，请先调用 connect()」。
    """
    rel = _live_workspace_root_relative()
    ws_root = (_PROJECT_ROOT / rel).resolve()
    ws_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "paper_workspace_root", rel)
    monkeypatch.setattr(config, "paper_arxiv_query_delay_seconds", 0.0)
    monkeypatch.setattr(config, "paper_search_human_confirm_enabled", False)
    max_results = int(os.environ.get("PAPER_WORKFLOW_LIVE_ARXIV_MAX_RESULTS", "5"))
    monkeypatch.setattr(config, "paper_arxiv_max_results", max(1, min(max_results, 50)))
    timeout_ms = int(os.environ.get("PAPER_WORKFLOW_LIVE_TIMEOUT_MS", "0"))
    monkeypatch.setattr(config, "paper_workflow_timeout_ms", max(0, timeout_ms))
    milvus_manager.connect()
    try:
        yield ws_root
    finally:
        milvus_manager.close()


@pytest.mark.skipif(
    _LIVE_SKIP_REASON != "",
    reason=_LIVE_SKIP_REASON or "paper workflow live gated",
)
@pytest.mark.asyncio
async def test_paper_workflow_full_stack_real_llm_arxiv_rag(paper_live_isolation):
    """
    真链路跑通：done.ok、检索到论文、readings/report 落盘且篇幅合理。
    不断言固定模型措辞；不强依赖知识库必命中某条向量（空库允许现有降级逻辑）。
    """
    tenant_id = (os.environ.get("PAPER_WORKFLOW_LIVE_TENANT_ID") or "live-tenant").strip()
    session_id = (os.environ.get("PAPER_WORKFLOW_LIVE_SESSION_ID") or "live-integration-session").strip()

    events: list = []
    async for msg in run_paper_research_stream(
        user_request=FIXED_USER_REQUEST,
        session_id=session_id,
        tenant_id=tenant_id,
    ):
        events.append(msg)

    assert len(events) >= 2
    assert events[-1]["type"] == "done"
    done = events[-1]["data"]
    assert isinstance(done, dict)
    assert done.get("ok") is True, f"workflow failed: {done}"

    paper_count = None
    for e in events:
        if e.get("type") != "phase" or not isinstance(e.get("data"), dict):
            continue
        d = e["data"]
        if d.get("node") == "search" and d.get("status") == "end":
            paper_count = (d.get("detail") or {}).get("paper_count")
    assert paper_count is not None, "missing search phase end with paper_count"
    assert int(paper_count) >= 1, f"expected at least one paper, got {paper_count}"

    ws = Path(done["workspace_dir"])
    assert ws.is_dir()
    readings_path = ws / "readings.md"
    report_path = ws / "report.md"
    assert readings_path.is_file()
    assert report_path.is_file()

    reading_text = readings_path.read_text(encoding="utf-8")
    report_text = report_path.read_text(encoding="utf-8")
    assert len(reading_text.strip()) >= 80, "readings.md unexpectedly empty"
    assert len(report_text.strip()) >= 500, "report.md shorter than expected; model may have returned brief output"

    types_seen = {e.get("type") for e in events}
    assert "error" not in types_seen, "unexpected error event in stream"
    assert "phase" in types_seen and "done" in types_seen

    # 固定目录下每次 run_id 不同；pytest -s 时可在控制台看到本次路径
    print(f"\n[paper_workflow_live] readings/report 目录: {ws}\n")


if __name__ == "__main__":
    _args = [__file__, "-v", "-o", "addopts=", "-m", "integration"] + sys.argv[1:]
    raise SystemExit(pytest.main(_args))
