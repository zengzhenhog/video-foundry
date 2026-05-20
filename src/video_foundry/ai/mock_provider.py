from __future__ import annotations

from datetime import datetime, timezone

from video_foundry.ai.base import ScriptGenerationInput
from video_foundry.shared.schemas import Script, ScriptSegment


DETERMINISTIC_TIMESTAMP = datetime(2026, 1, 1, tzinfo=timezone.utc)


class MockScriptProvider:
    provider_name = "mock"

    def generate_script(self, script_input: ScriptGenerationInput) -> Script:
        title = script_input.title.strip() or "Untitled source"
        description = _single_line(script_input.description)
        draft = _single_line(script_input.user_draft or "")
        duration = float(script_input.target_duration_sec)

        if draft:
            narration = (
                f"{title}. {description} "
                f"User draft context: {draft} "
                f"Source credit: {script_input.credit}."
            )
        else:
            narration = f"{title}. {description} Source credit: {script_input.credit}."

        midpoint = round(duration / 2, 2)
        segments = [
            ScriptSegment(
                start_sec=0,
                end_sec=midpoint,
                text=f"{title}. {description}",
            ),
            ScriptSegment(
                start_sec=midpoint,
                end_sec=round(duration, 2),
                text=f"Source and credit: {script_input.credit}.",
            ),
        ]
        if draft:
            segments.append(
                ScriptSegment(
                    start_sec=round(duration, 2),
                    end_sec=round(duration, 2),
                    text=f"User draft considered: {draft}",
                )
            )

        return Script(
            project_id=script_input.project_id,
            language=script_input.target_language,
            duration_target_sec=duration,
            title=title,
            narration=narration,
            segments=segments,
            review_notes=(
                "Grounding: narration uses only the saved source description, "
                "source URL, credit, title, and optional user draft. No unsourced "
                "dates, distances, object classifications, causal claims, or "
                "observation details were added."
            ),
            approved=False,
            updated_at=DETERMINISTIC_TIMESTAMP,
        )


def _single_line(value: str) -> str:
    return " ".join(value.strip().split())
