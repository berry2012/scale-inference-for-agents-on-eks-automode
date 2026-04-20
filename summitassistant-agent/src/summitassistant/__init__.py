"""summitassistant - AI-powered meeting management agent.

This package provides an AI agent built using the Strands Agents framework
for orchestrating meeting-related tasks including calendar management,
note summarization, and persistent storage.
"""

from summitassistant.agent import summitassistant
from summitassistant.models import (
    MeetingRequest,
    MeetingNote,
    Summary,
    SessionState,
    OperationStatus,
    OperationResult,
)

__version__ = "0.1.0"

__all__ = [
    "summitassistant",
    "MeetingRequest",
    "MeetingNote",
    "Summary",
    "SessionState",
    "OperationStatus",
    "OperationResult",
]
