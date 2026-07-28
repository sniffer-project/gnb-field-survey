"""Errors raised when the survey inputs are unusable.

Field data gets mislabelled, transcribed twice, and exported in the wrong
format. Every one of those must stop the run with a message naming the file
and the point, never a silently dropped row.
"""

from __future__ import annotations


class SurveyDataError(ValueError):
    """An input file is malformed, internally inconsistent, or contradicts its pair."""
