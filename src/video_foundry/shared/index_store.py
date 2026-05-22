from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Iterable

from pydantic import BaseModel, ConfigDict

from video_foundry.shared.schemas import Project
from video_foundry.shared.storage import ProjectStorage


INDEX_DB_FILENAME = "_project_index.sqlite3"


class ProjectIndexRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    status: str
    target_language: str
    target_duration_sec: float
    current_step: str
    updated_at: str


class ProjectIndexRebuildResponse(BaseModel):
    indexed: int


class ProjectIndexListResponse(BaseModel):
    projects: list[ProjectIndexRecord]


class ProjectIndexStore:
    def __init__(self, projects_root: Path) -> None:
        self.projects_root = Path(projects_root)
        self.path = self.projects_root / INDEX_DB_FILENAME

    def rebuild(self, storage: ProjectStorage) -> int:
        self.projects_root.mkdir(parents=True, exist_ok=True)
        projects = storage.list_projects()
        with self._connect() as connection:
            _ensure_schema(connection)
            connection.execute("DELETE FROM projects")
            self._upsert_many(connection, projects)
        return len(projects)

    def repair(self, storage: ProjectStorage) -> int:
        return self.rebuild(storage)

    def upsert_project(self, project: Project) -> None:
        self.projects_root.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            _ensure_schema(connection)
            self._upsert_many(connection, [project])

    def list_projects(self, *, query: str | None = None, status: str | None = None) -> list[ProjectIndexRecord]:
        with self._connect() as connection:
            _ensure_schema(connection)
            clauses: list[str] = []
            params: list[str] = []
            if query and query.strip():
                clauses.append("(lower(id) LIKE ? OR lower(name) LIKE ?)")
                like_query = f"%{query.strip().lower()}%"
                params.extend([like_query, like_query])
            if status and status.strip():
                clauses.append("status = ?")
                params.append(status.strip())
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            rows = connection.execute(
                f"""
                SELECT id, name, status, target_language, target_duration_sec, current_step, updated_at
                FROM projects
                {where}
                ORDER BY updated_at DESC
                """,
                params,
            ).fetchall()
        return [
            ProjectIndexRecord(
                id=row["id"],
                name=row["name"],
                status=row["status"],
                target_language=row["target_language"],
                target_duration_sec=row["target_duration_sec"],
                current_step=row["current_step"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _upsert_many(self, connection: sqlite3.Connection, projects: Iterable[Project]) -> None:
        connection.executemany(
            """
            INSERT INTO projects (
              id, name, status, target_language, target_duration_sec, current_step, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              name = excluded.name,
              status = excluded.status,
              target_language = excluded.target_language,
              target_duration_sec = excluded.target_duration_sec,
              current_step = excluded.current_step,
              updated_at = excluded.updated_at
            """,
            [
                (
                    project.id,
                    project.name,
                    str(project.status),
                    project.target_language,
                    project.target_duration_sec,
                    project.current_step,
                    project.updated_at.isoformat(),
                )
                for project in projects
            ],
        )


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          status TEXT NOT NULL,
          target_language TEXT NOT NULL,
          target_duration_sec REAL NOT NULL,
          current_step TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_projects_updated_at ON projects(updated_at)")
