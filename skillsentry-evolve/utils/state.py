"""State persistence — save/load per-task optimization state."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load(task_out_dir: Path) -> dict[str, Any]:
    state_file = task_out_dir / "state.json"
    if state_file.exists():
        st = json.loads(state_file.read_text(encoding="utf-8"))
        # Ensure all expected keys exist (backwards compat)
        st.setdefault("round", 0)
        st.setdefault("reward_history", [])
        st.setdefault("diff_history", [])
        return st
    return {"round": 0, "reward_history": [], "diff_history": []}


def save(task_out_dir: Path, state: dict[str, Any]) -> None:
    task_out_dir.mkdir(parents=True, exist_ok=True)
    (task_out_dir / "state.json").write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
    )
