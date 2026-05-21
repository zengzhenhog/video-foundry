from video_foundry.shared.schemas import ScriptSegment
from video_foundry.storyboard.planner import plan_storyboard


def test_planner_generates_continuous_shots() -> None:
    storyboard = plan_storyboard(
        project_id="project_1",
        segments=[
            ScriptSegment(start_sec=0, end_sec=4, text="Opening line."),
            ScriptSegment(start_sec=4, end_sec=10, text="Second line."),
        ],
        duration_sec=20,
        format_name="vertical_1080x1920",
        fps=30,
        safe_area={"top": 0.08, "right": 0.06, "bottom": 0.12, "left": 0.06},
    )

    assert storyboard.duration_sec == 20
    assert [shot.start_sec for shot in storyboard.shots] == [0, 8]
    assert [shot.end_sec for shot in storyboard.shots] == [8, 20]
    assert storyboard.shots[0].caption == "Opening line."

