"""Data models for summitassistant agent."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum


@dataclass
class MeetingRequest:
    """User request to schedule a meeting."""
    
    date: str  # ISO 8601 date
    time: str  # HH:MM format
    duration_minutes: int
    attendees: List[str]
    title: str
    description: Optional[str] = None
    
    def validate(self) -> List[str]:
        """Validate required fields and formats.
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        if not self.date:
            errors.append("date is required")
        if not self.time:
            errors.append("time is required")
        if self.duration_minutes <= 0:
            errors.append("duration must be positive")
        if not self.attendees:
            errors.append("at least one attendee is required")
        if not self.title:
            errors.append("title is required")
        return errors


@dataclass
class MeetingNote:
    """Meeting notes with metadata."""
    
    meeting_id: str
    timestamp: datetime
    attendees: List[str]
    title: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_json(self) -> dict:
        """Serialize to JSON format for S3 storage."""
        return {
            "meeting_id": self.meeting_id,
            "timestamp": self.timestamp.isoformat(),
            "attendees": self.attendees,
            "title": self.title,
            "content": self.content,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_json(cls, data: dict) -> 'MeetingNote':
        """Deserialize from JSON format."""
        return cls(
            meeting_id=data["meeting_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            attendees=data["attendees"],
            title=data["title"],
            content=data["content"],
            metadata=data["metadata"]
        )


@dataclass
class Summary:
    """LLM-generated meeting summary."""
    
    meeting_id: str
    summary: str
    generated_at: datetime
    model: str
    key_topics: List[str]
    action_items: List[str]
    
    def to_json(self) -> dict:
        """Serialize to JSON format for S3 storage."""
        return {
            "meeting_id": self.meeting_id,
            "summary": self.summary,
            "generated_at": self.generated_at.isoformat(),
            "model": self.model,
            "key_topics": self.key_topics,
            "action_items": self.action_items
        }
    
    @classmethod
    def from_json(cls, data: dict) -> 'Summary':
        """Deserialize from JSON format."""
        return cls(
            meeting_id=data["meeting_id"],
            summary=data["summary"],
            generated_at=datetime.fromisoformat(data["generated_at"]),
            model=data["model"],
            key_topics=data["key_topics"],
            action_items=data["action_items"]
        )


@dataclass
class ConversationMessage:
    """Single message in conversation history."""
    
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime


@dataclass
class SessionState:
    """Agent session state for persistence."""
    
    session_id: str
    created_at: datetime
    updated_at: datetime
    conversation_history: List[ConversationMessage]
    context: Dict[str, Any]
    
    def to_json(self) -> dict:
        """Serialize to JSON format for S3 storage."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "conversation_history": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat()
                }
                for msg in self.conversation_history
            ],
            "context": self.context
        }
    
    @classmethod
    def from_json(cls, data: dict) -> 'SessionState':
        """Deserialize from JSON format."""
        return cls(
            session_id=data["session_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            conversation_history=[
                ConversationMessage(
                    role=msg["role"],
                    content=msg["content"],
                    timestamp=datetime.fromisoformat(msg["timestamp"])
                )
                for msg in data["conversation_history"]
            ],
            context=data["context"]
        )


class OperationStatus(Enum):
    """Status of agent operations."""
    
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    PARTIAL = "partial"


@dataclass
class OperationResult:
    """Result of an agent operation."""
    
    status: OperationStatus
    message: str
    data: Optional[Any] = None
    error: Optional[str] = None
