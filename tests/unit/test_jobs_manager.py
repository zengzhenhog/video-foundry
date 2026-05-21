from pathlib import Path

from video_foundry.jobs.manager import JobManager
from video_foundry.jobs.models import JobError, JobStatus
from video_foundry.shared.storage import ProjectStorage


def test_job_manager_persists_status_transitions_and_reads_after_restart(tmp_path: Path) -> None:
    storage = ProjectStorage(tmp_path / "projects")
    project = storage.create_project(name="Jobs")
    manager = JobManager(storage)

    job = manager.create_job(project.id, "render_preview", summary="Queued.")
    manager.start(project.id, job.id, step="render_preview", summary="Started.")
    manager.update_progress(project.id, job.id, progress=0.4, summary="Rendering frames.")
    manager.succeed(
        project.id,
        job.id,
        output_paths=["renders/render-manifest.json", "renders/preview_vertical_1080x1920.mp4"],
        summary="Done.",
    )

    reloaded = JobManager(storage).get_job(job.id)

    assert reloaded.status is JobStatus.SUCCEEDED
    assert reloaded.progress == 1
    assert reloaded.output_paths == ["renders/render-manifest.json", "renders/preview_vertical_1080x1920.mp4"]
    assert (storage.projects_root / project.id / "logs" / "jobs" / f"{job.id}.json").exists()
    assert "Rendering frames." in (storage.projects_root / project.id / "logs" / "pipeline.log").read_text(
        encoding="utf-8"
    )


def test_job_failure_writes_error_json_and_marks_project_failed(tmp_path: Path) -> None:
    storage = ProjectStorage(tmp_path / "projects")
    project = storage.create_project(name="Failed job")
    manager = JobManager(storage)
    job = manager.create_job(project.id, "export_final", summary="Queued.")
    manager.start(project.id, job.id, step="export_final", summary="Started.")

    manager.fail(
        project.id,
        job.id,
        error=JobError(
            code="quality_gate_failed",
            step="quality_gate",
            reason="Export quality checks did not pass.",
            retryable=True,
            suggested_correction="Fix failed checks.",
        ),
    )

    failed = manager.get_job(job.id)
    error = storage.read_json(project.id, "logs/error.json")
    failed_project = storage.read_project(project.id)

    assert failed.status is JobStatus.FAILED
    assert failed.error and failed.error.step == "quality_gate"
    assert error["reason"] == "Export quality checks did not pass."
    assert failed_project.status == "failed"
    assert failed_project.current_step == "quality_gate"

