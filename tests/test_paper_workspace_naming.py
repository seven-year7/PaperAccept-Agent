"""论文工作区目录按时间戳（精确到分）命名。"""

from pathlib import Path
from unittest.mock import patch

from app.services.paper_workflow_service import _allocate_workspace_dir


def test_allocate_workspace_first_uses_base_timestamp(tmp_path: Path) -> None:
    root = tmp_path
    rel = Path("paper_ws")
    with patch(
        "app.services.paper_workflow_service._paper_run_timestamp_str",
        return_value="2026-04-05_1623",
    ):
        run_id, ws = _allocate_workspace_dir(root, rel)
    assert run_id == "2026-04-05_1623"
    assert ws == (root / rel / "2026-04-05_1623").resolve()
    assert ws.is_dir()


def test_allocate_workspace_collision_adds_numeric_suffix(tmp_path: Path) -> None:
    root = tmp_path
    rel = Path("paper_ws")
    existing = (root / rel / "2026-04-05_1623").resolve()
    existing.mkdir(parents=True)
    with patch(
        "app.services.paper_workflow_service._paper_run_timestamp_str",
        return_value="2026-04-05_1623",
    ):
        run_id, ws = _allocate_workspace_dir(root, rel)
    assert run_id == "2026-04-05_1623_2"
    assert ws == (root / rel / "2026-04-05_1623_2").resolve()
    assert ws.is_dir()
