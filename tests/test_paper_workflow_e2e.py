"""
/**
 * @Module: tests/test_paper_workflow_e2e.py
 * @Description: 论文调研工作流「离线编排契约」测试（Mock LLM / arXiv / RAG，不连外网与 Milvus）。
 *   不替代真大模型与真检索效果验证；整图完全真实集成见 tests/test_paper_workflow_live.py（PAPER_WORKFLOW_LIVE_TEST=1）。
 *   固定用户句「帮我查询最近一年的网络攻击的论文」贯穿主图 search→reading→write 子图→report；
 *   校验 SSE 事件类型、阶段顺序、检索/RAG 调用、落盘内容与 Mock 队列耗尽（整链逻辑闭环）。
 * @Interface: pytest 收集本文件；运行：pytest tests/test_paper_workflow_e2e.py -q -o addopts=
 *   或直接：python tests/test_paper_workflow_e2e.py（内部调用 pytest.main，默认 -v -o addopts=，可跟 pytest 额外参数）
 */
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from app.agent.paper.schemas import (
    OutlineResponse,
    ReadingExtract,
    SectionTask,
    StructuredArxivQuery,
    WritingGlobalReview,
)
from app.config import config
from app.services.paper_workflow_service import run_paper_research_stream

# 固定回归用语：模拟「真实用户一句需求」走完 search → reading → write 子图 → report
FIXED_USER_REQUEST = "帮我查询最近一年的网络攻击的论文"


def _fake_papers():
    from app.agent.paper.schemas import PaperMeta

    return [
        PaperMeta(
            arxiv_id="2401.00001",
            arxiv_short_id="2401.00001v1",
            title="Survey of Network Attack Detection with Deep Learning (2025)",
            authors=["Sec Author"],
            published="2025-06-01T00:00:00",
            published_year=2025,
            summary="This survey reviews network attack trends over the past year, "
            "including DDoS, malware C2, and intrusion detection benchmarks on public datasets.",
            pdf_url="https://arxiv.org/pdf/2401.00001.pdf",
            abs_url="https://arxiv.org/abs/2401.00001",
            primary_category="cs.CR",
            categories=["cs.CR", "cs.NI"],
        )
    ]


def _build_fake_get_paper_chat_model(
    structured_queue: deque,
    raw_queue: deque,
    *,
    report_headline: str,
):
    """search/reading/plan/global 走 with_structured_output（Runnable）；execute 走 prompt|llm，故基座须为真实 Runnable，不能仅用 MagicMock（否则 ainvoke 不消费 raw 队列）。"""

    def fake_get_paper_chat_model(*, temperature: float = 0.2, streaming: bool = False):
        if streaming:
            stream_llm = MagicMock()

            async def _astream(_msgs):
                yield AIMessage(
                    content=(
                        f"{report_headline}\n\n"
                        "围绕「最近一年网络攻击相关预印本」的调研摘要（测试桩）；并概括 DDoS、钓鱼等威胁面。\n"
                    )
                )

            stream_llm.astream = _astream
            stream_llm.bind = lambda **kwargs: stream_llm
            return stream_llm

        async def _chapter_writer(_input):
            if raw_queue:
                return raw_queue.popleft()
            return AIMessage(content="### 章节正文\n测试段落内容。\n")

        base = cast(Any, RunnableLambda(_chapter_writer))

        def _with_structured_output(*_a, **_kw):
            async def _pop_structured(_input):
                if not structured_queue:
                    raise RuntimeError("structured LLM queue exhausted (unexpected extra call)")
                return structured_queue.popleft()

            return RunnableLambda(_pop_structured)

        base.with_structured_output = _with_structured_output
        base.bind = lambda **kwargs: base
        return base

    return fake_get_paper_chat_model


def _structured_queue_for_network_attack_survey() -> deque:
    """与 FIXED_USER_REQUEST 对齐的 LLM 结构化输出序列（模拟「真模型」会给出的检索与时间窗）。"""
    return deque(
        [
            StructuredArxivQuery(
                querys=["network attack", "cyber intrusion", "DDoS detection"],
                start_date="2025-01-01",
                end_date="2026-12-31",
                title_phrase="",
                author="",
                sort_mode="submitted_date",
                categories=["cs.CR"],
            ),
            ReadingExtract(
                core_problem="近一年网络攻击手法与检测难点（含 DDoS、钓鱼等）",
                key_methods="深度学习入侵检测、流量指纹、威胁情报",
                innovation="跨数据集泛化与实时检测权衡",
                limitations="标注成本高、对抗样本",
                contributions="梳理评测指标与公开数据集",
            ),
            OutlineResponse(
                sections=[
                    SectionTask(
                        section_id="background",
                        title="网络攻击与威胁背景",
                        objectives="概括近一年主要攻击面与术语",
                        keywords_for_retrieval="network attack survey 2025",
                    ),
                    SectionTask(
                        section_id="detection",
                        title="检测与防御方法",
                        objectives="归纳检测技术与代表工作",
                        keywords_for_retrieval="intrusion detection deep learning",
                    ),
                    SectionTask(
                        section_id="outlook",
                        title="趋势与展望",
                        objectives="总结开放问题与后续方向",
                        keywords_for_retrieval="",
                    ),
                ]
            ),
            WritingGlobalReview(decision="OK", comment="通过"),
        ]
    )


@dataclass
class PaperE2EHarness:
    """供断言用的夹具句柄：LLM 队列、RAG Mock、传入 PaperSearcher.search 的结构化条件。"""

    structured_queue: deque
    raw_queue: deque
    rag_mock: MagicMock
    arxiv_structured_args: List[Any]


@pytest.fixture
def paper_e2e_mocks(monkeypatch, tmp_path):
    """工作区落到 pytest tmp、去掉 arXiv sleep、关闭整图超时；显式关闭检索人工确认。"""
    ws_root = tmp_path / "paper_ws"
    ws_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "paper_workspace_root", str(ws_root))
    monkeypatch.setattr(config, "paper_arxiv_query_delay_seconds", 0.0)
    monkeypatch.setattr(config, "paper_workflow_timeout_ms", 0)
    monkeypatch.setattr(config, "paper_search_human_confirm_enabled", False)

    structured_q = _structured_queue_for_network_attack_survey()
    raw_q = deque(
        [
            AIMessage(content="### 网络攻击与威胁背景\n近一年典型攻击向量包括钓鱼、勒索与 DDoS（测试桩）。\n"),
            AIMessage(content="### 检测与防御方法\n基于深度学习的流量分类与异常检测流水线（测试桩）。\n"),
            AIMessage(content="### 趋势与展望\n联邦场景与可解释性仍为开放问题（测试桩）。\n"),
        ]
    )

    fake_llm_factory = _build_fake_get_paper_chat_model(
        structured_q,
        raw_q,
        report_headline="# 网络攻击相关论文调研报告",
    )

    patch_targets = [
        "app.agent.paper.nodes.search_node.get_paper_chat_model",
        "app.agent.paper.nodes.reading_node.get_paper_chat_model",
        "app.agent.paper.write.agents.plan_agent.get_paper_chat_model",
        "app.agent.paper.write.agents.execute_runner.get_paper_chat_model",
        "app.agent.paper.write.agents.global_reviewer_agent.get_paper_chat_model",
        "app.agent.paper.nodes.report_node.get_paper_chat_model",
    ]

    stops = []
    for target in patch_targets:
        p = patch(target, new=fake_llm_factory)
        p.start()
        stops.append(p)

    arxiv_structured_args: List[Any] = []

    def _make_searcher(*_a, **_kw):
        m = MagicMock()

        async def _search(structured):
            arxiv_structured_args.append(structured)
            return _fake_papers()

        m.search = AsyncMock(side_effect=_search)
        return m

    ps = patch("app.agent.paper.nodes.search_node.PaperSearcher", side_effect=_make_searcher)
    ps.start()
    stops.append(ps)

    fake_rag = MagicMock()
    fake_rag.invoke = MagicMock(
        return_value=("（知识库摘录）网络攻击态势、MITRE ATT&CK 与入侵检测基准简述。", [])
    )
    for mod in (
        "app.agent.paper.write.agents.plan_agent.retrieve_knowledge",
        "app.agent.paper.write.agents.execute_runner.retrieve_knowledge",
    ):
        pr = patch(mod, fake_rag)
        pr.start()
        stops.append(pr)

    harness = PaperE2EHarness(
        structured_queue=structured_q,
        raw_queue=raw_q,
        rag_mock=fake_rag,
        arxiv_structured_args=arxiv_structured_args,
    )
    yield harness

    for p in reversed(stops):
        p.stop()


def _phase_trail(events: list) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for e in events:
        if e.get("type") != "phase":
            continue
        data = e.get("data")
        if not isinstance(data, dict):
            continue
        node = data.get("node")
        status = data.get("status")
        if isinstance(node, str) and isinstance(status, str):
            out.append((node, status))
    return out


def _first_phase_index(trail: list[tuple[str, str]], node: str, status: str) -> int:
    for i, (n, s) in enumerate(trail):
        if n == node and s == status:
            return i
    return -1


@pytest.mark.asyncio
async def test_paper_workflow_full_graph_logic(paper_e2e_mocks: PaperE2EHarness, tmp_path):
    """主图 + 子图 + SSE + 工具调用 + 落盘 + Mock 耗尽：整链逻辑一次断言。"""
    events: list = []
    async for msg in run_paper_research_stream(
        user_request=FIXED_USER_REQUEST,
        session_id="pytest-session",
        tenant_id="pytest-tenant",
    ):
        events.append(msg)

    assert len(events) >= 2
    assert events[-1]["type"] == "done"
    done = events[-1]["data"]
    assert isinstance(done, dict)
    assert done["ok"] is True, f"workflow failed: {done}"
    run_id = done["run_id"]
    assert run_id
    assert done.get("errors") in (None, [])
    frp = done.get("final_report_path")
    assert isinstance(frp, str) and frp.endswith("report.md")

    ws = Path(done["workspace_dir"])
    assert ws.is_dir()
    assert (ws / "readings.md").is_file()
    assert (ws / "report.md").is_file()
    report_text = (ws / "report.md").read_text(encoding="utf-8")
    assert len(report_text) > 10
    reading_text = (ws / "readings.md").read_text(encoding="utf-8")
    assert "Network Attack" in reading_text or "network attack" in reading_text.lower()
    assert "近一年网络攻击" in reading_text
    assert "核心问题" in reading_text and "关键方法" in reading_text
    assert "DDoS" in reading_text

    types_seen = {e.get("type") for e in events}
    assert "error" not in types_seen
    assert "search_confirm" not in types_seen
    required_types = {"phase", "reading_progress", "writing", "content", "done"}
    missing = required_types - types_seen
    assert not missing, f"missing event types: {missing}"

    trail = _phase_trail(events)
    assert _first_phase_index(trail, "search", "start") >= 0
    assert _first_phase_index(trail, "search", "progress") >= 0
    assert _first_phase_index(trail, "search", "end") >= 0
    assert _first_phase_index(trail, "search", "start") < _first_phase_index(trail, "search", "end")

    prog_ev = next(
        e
        for e in events
        if e.get("type") == "phase"
        and isinstance(e.get("data"), dict)
        and e["data"].get("node") == "search"
        and e["data"].get("status") == "progress"
    )
    sq = (prog_ev["data"].get("detail") or {}).get("structured_query") or {}
    assert isinstance(sq, dict)
    assert "network attack" in " ".join(sq.get("querys") or []).lower()

    search_end = next(
        e
        for e in events
        if e.get("type") == "phase"
        and isinstance(e.get("data"), dict)
        and e["data"].get("node") == "search"
        and e["data"].get("status") == "end"
    )
    assert (search_end["data"].get("detail") or {}).get("paper_count") == 1

    assert _first_phase_index(trail, "reading", "start") < _first_phase_index(trail, "reading", "end")

    rp = [e for e in events if e.get("type") == "reading_progress"]
    assert len(rp) >= 2
    assert any(
        e.get("data", {}).get("arxiv_id") == "2401.00001" and e.get("data", {}).get("status") == "start"
        for e in rp
    )

    for node in ("writePlan", "writeExecute", "writeAudit"):
        assert _first_phase_index(trail, node, "start") >= 0
        assert _first_phase_index(trail, node, "end") >= 0
        assert _first_phase_index(trail, node, "start") < _first_phase_index(trail, node, "end")

    assert _first_phase_index(trail, "reading", "end") < _first_phase_index(trail, "writePlan", "start")
    assert _first_phase_index(trail, "writePlan", "end") < _first_phase_index(trail, "writeExecute", "start")
    assert _first_phase_index(trail, "writeExecute", "end") < _first_phase_index(trail, "writeAudit", "start")
    assert _first_phase_index(trail, "writeAudit", "end") < _first_phase_index(trail, "report", "start")

    rep_start = _first_phase_index(trail, "report", "start")
    rep_run = _first_phase_index(trail, "report", "running")
    rep_end = _first_phase_index(trail, "report", "end")
    assert rep_start >= 0 and rep_run >= 0 and rep_end >= 0
    assert rep_start < rep_run < rep_end
    completed = next(
        e
        for e in events
        if e.get("type") == "phase"
        and isinstance(e.get("data"), dict)
        and e["data"].get("node") == "report"
        and e["data"].get("status") == "end"
    )
    assert (completed["data"].get("detail") or {}).get("stage") == "completed"

    writing_ev = [e for e in events if e.get("type") == "writing"]
    assert len(writing_ev) == 6
    wdata = [e.get("data") for e in writing_ev]
    for sid in ("background", "detection", "outlook"):
        assert sum(1 for d in wdata if isinstance(d, dict) and d.get("section_id") == sid) == 2
        assert any(
            isinstance(d, dict) and d.get("section_id") == sid and d.get("status") == "start" for d in wdata
        )
        assert any(
            isinstance(d, dict) and d.get("section_id") == sid and d.get("status") == "end" for d in wdata
        )

    content_pieces = [e.get("data") for e in events if e.get("type") == "content"]
    assert content_pieces
    assert "网络攻击" in report_text
    assert "预印本" in report_text or "调研摘要" in report_text
    assert "DDoS" in report_text or "钓鱼" in report_text

    assert len(paper_e2e_mocks.arxiv_structured_args) == 1
    passed = paper_e2e_mocks.arxiv_structured_args[0]
    assert any("network" in (q or "").lower() for q in (passed.querys or []))

    # 默认 PAPER_WRITING_RAG_ENABLED=false，写作阶段不调用 retrieve_knowledge
    assert paper_e2e_mocks.rag_mock.invoke.call_count == 0

    assert len(paper_e2e_mocks.structured_queue) == 0, "structured LLM 调用次数应与队列长度一致"
    assert len(paper_e2e_mocks.raw_queue) == 0, "章节 writer ainvoke 次数应与 raw 队列一致"


@pytest.mark.asyncio
async def test_paper_workflow_second_invocation_ok(paper_e2e_mocks: PaperE2EHarness, tmp_path):
    """独立夹具下再跑一轮（新队列）：仍成功且 Mock 耗尽；与主用例隔离，避免同一次 fixture 内二次 invoke 队列已空。"""
    async for msg in run_paper_research_stream(
        user_request=FIXED_USER_REQUEST,
        session_id="pytest-session-2",
        tenant_id="pytest-tenant",
    ):
        last = msg
    assert last["type"] == "done"
    assert last["data"].get("ok") is True
    assert last["data"].get("run_id")
    assert len(paper_e2e_mocks.structured_queue) == 0
    assert len(paper_e2e_mocks.raw_queue) == 0


if __name__ == "__main__":
    import sys

    # 便于 IDE / 命令行直接执行本文件；默认覆盖 pyproject 中可能含 --cov 的 addopts
    _args = [__file__, "-v", "-o", "addopts="] + sys.argv[1:]
    raise SystemExit(pytest.main(_args))
