"""论文多 Agent 工作流（arXiv 检索 + 阅读 + 写作 + 报告）。

包内子模块（如 schemas）导入时不应再 eagerly 加载 graph，以免与 tools.paper_arxiv_tool 形成循环依赖。
"""

from __future__ import annotations

from typing import Any


def __getattr__(name: str) -> Any:
    if name == "build_paper_graph":
        from app.agent.paper.graph import build_paper_graph

        return build_paper_graph
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["build_paper_graph"]
