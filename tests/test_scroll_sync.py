from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "src"))

from scroll_sync import ScrollCompletion  # noqa: E402


def test_scroll_completion_waits_for_required_cycles():
    completion = ScrollCompletion(required_cycles=2)

    completion.mark_cycle_complete()
    assert completion.completed_cycles == 1
    assert completion.complete is False

    completion.mark_cycle_complete()
    assert completion.completed_cycles == 2
    assert completion.complete is True

    completion.mark_cycle_complete()
    assert completion.completed_cycles == 2


def test_scroll_completion_requires_at_least_one_cycle():
    completion = ScrollCompletion(required_cycles=0)

    completion.mark_cycle_complete()

    assert completion.required_cycles == 1
    assert completion.complete is True
