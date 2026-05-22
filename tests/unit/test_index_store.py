from __future__ import annotations

import shutil
from pathlib import Path

from video_foundry.shared.index_store import ProjectIndexStore
from video_foundry.shared.storage import ProjectStorage


def test_project_index_rebuilds_from_project_json_and_repairs_deleted_projects(tmp_path: Path) -> None:
    storage = ProjectStorage(tmp_path / "projects")
    first = storage.create_project(name="Moon import")
    second = storage.create_project(name="Mars queue")
    index = ProjectIndexStore(storage.projects_root)

    assert index.rebuild(storage) == 2
    assert [record.id for record in index.list_projects(query="moon")] == [first.id]

    shutil.rmtree(storage.projects_root / second.id)
    assert index.repair(storage) == 1

    indexed_ids = {record.id for record in index.list_projects()}
    assert indexed_ids == {first.id}
