"""Tests for learning-path progression and prerequisite behavior."""

from backend.app.learning_paths.repository import LearningPathRepository


def test_required_lesson_locks_following_lessons_until_complete() -> None:
    """An incomplete required lesson closes the sequential progression gate."""
    completed, locked, next_gate = LearningPathRepository._lesson_state(40, True, True)

    assert not completed
    assert not locked
    assert not next_gate

    completed, locked, next_gate = LearningPathRepository._lesson_state(
        0, next_gate, True
    )

    assert not completed
    assert locked
    assert not next_gate


def test_optional_lesson_does_not_block_the_next_lesson() -> None:
    """Optional enrichment can be skipped without closing the path."""
    completed, locked, next_gate = LearningPathRepository._lesson_state(0, True, False)

    assert not completed
    assert not locked
    assert next_gate


def test_path_progress_includes_partially_read_lessons() -> None:
    """Path progress should move before the first lesson is fully completed."""
    assert LearningPathRepository._path_progress(150, 3) == 50
    assert LearningPathRepository._path_progress(0, 0) == 0
