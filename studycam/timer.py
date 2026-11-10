"""Calculations for alternating focus and break periods."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TimerProgress:
    in_break: bool
    phase_start: float
    focus_seconds: float
    transitions: int


def advance_timer(phase_start: float, in_break: bool, previous: float, now: float,
                  focus_duration: float, break_duration: float) -> TimerProgress:
    """Carry elapsed time across all phase boundaries."""
    if focus_duration <= 0 or break_duration <= 0:
        raise ValueError("phase durations must be positive")
    focus_seconds = 0.0
    transitions = 0
    cursor = max(previous, phase_start)
    while cursor < now:
        boundary = phase_start + (break_duration if in_break else focus_duration)
        end = min(now, boundary)
        if not in_break:
            focus_seconds += max(0.0, end - cursor)
        cursor = max(cursor, end)
        if now < boundary:
            break
        phase_start = boundary
        in_break = not in_break
        transitions += 1
    return TimerProgress(in_break, phase_start, focus_seconds, transitions)
