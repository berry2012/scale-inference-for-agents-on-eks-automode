#!/usr/bin/env python3
"""Integration tests for summitassistant agent.

Tests end-to-end workflows with real services via Docker Compose.
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from summitassistant.models import MeetingRequest, MeetingNote
from summitassistant.storage_manager import StorageManager
from summitassistant.llm_client import LLMServiceClient
from summitassistant.calendar_manager import MCPServerClient

# Configure for local testing
os.environ["S3_ENDPOINT"] = "http://localhost:4566"
os.environ["S3_BUCKET_NAME"] = "summitassistant-demo-bucket"
os.environ["S3_REGION"] = "us-east-2"
os.environ["OPENAI_API_BASE_URL"] = "http://localhost:8000"
os.environ["MCP_SERVER_URL"] = "http://localhost:8081"


async def test_meeting_scheduling():
    """Test end-to-end meeting scheduling flow."""
    print("\n=== Test 1: Meeting Scheduling ===")
    
    mcp_client = MCPServerClient()
    
    request = MeetingRequest(
        date="2026-03-15",
        time="14:00",
        duration_minutes=60,
        attendees=["alice@example.com", "bob@example.com"],
        title="Integration Test Meeting",
        description="Testing meeting scheduling"
    )
    
    # Validate request
    errors = request.validate()
    assert len(errors) == 0, f"Validation failed: {errors}"
    print("✓ Meeting request validation passed")
    
    # Schedule meeting
    try:
        response = await mcp_client.schedule_meeting(
            date=request.date,
            time=request.time,
            duration_minutes=request.duration_minutes,
            attendees=request.attendees,
            title=request.title,
            description=request.description
        )
        
        assert "meeting_id" in response, "Response missing meeting_id"
        assert response["status"] == "confirmed", "Meeting not confirmed"
        print(f"✓ Meeting scheduled successfully: {response['meeting_id']}")
        return True
    except Exception as e:
        print(f"✗ Meeting scheduling failed: {e}")
        return False


async def test_summarization():
    """Test end-to-end summarization flow."""
    print("\n=== Test 2: Meeting Summarization ===")
    
    storage_manager = StorageManager()
    llm_client = LLMServiceClient()
    
    # Create test meeting note
    meeting_id = "test-summarization-001"
    meeting_note = MeetingNote(
        meeting_id=meeting_id,
        timestamp=datetime.utcnow(),
        attendees=["test@example.com"],
        title="Test Meeting",
        content="This is a test meeting with important decisions and action items.",
        metadata={"test": True}
    )
    
    # Save meeting note
    try:
        await storage_manager.save_meeting_note(meeting_id, meeting_note)
        print(f"✓ Meeting note saved: {meeting_id}")
    except Exception as e:
        print(f"✗ Failed to save meeting note: {e}")
        return False
    
    # Generate summary
    try:
        summary = await llm_client.summarize_meeting_notes(meeting_note.content)
        assert summary, "Summary is empty"
        assert len(summary) > 0, "Summary has no content"
        print(f"✓ Summary generated: {summary[:100]}...")
        return True
    except Exception as e:
        print(f"✗ Summarization failed: {e}")
        return False


async def test_meeting_retrieval():
    """Test end-to-end meeting retrieval flow."""
    print("\n=== Test 3: Meeting Retrieval ===")
    
    storage_manager = StorageManager()
    
    # Search for all meetings
    try:
        results = await storage_manager.search_meetings(limit=10)
        assert isinstance(results, list), "Results should be a list"
        print(f"✓ Retrieved {len(results)} meetings")
        
        if len(results) > 0:
            # Verify meeting structure
            first_meeting = results[0]
            assert hasattr(first_meeting, "meeting_id"), "Meeting missing meeting_id"
            assert hasattr(first_meeting, "title"), "Meeting missing title"
            assert hasattr(first_meeting, "content"), "Meeting missing content"
            print(f"✓ First meeting: {first_meeting.title}")
        
        # Test search by attendee
        attendee_results = await storage_manager.search_meetings(
            attendee="alice@example.com",
            limit=10
        )
        print(f"✓ Found {len(attendee_results)} meetings with alice@example.com")
        
        return True
    except Exception as e:
        print(f"✗ Meeting retrieval failed: {e}")
        return False


async def test_session_state_persistence():
    """Test session state persistence across restarts."""
    print("\n=== Test 4: Session State Persistence ===")
    
    from summitassistant.models import SessionState, ConversationMessage
    
    storage_manager = StorageManager()
    session_id = "test-session-001"
    
    # Create session state
    state = SessionState(
        session_id=session_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        conversation_history=[
            ConversationMessage(
                role="user",
                content="Schedule a meeting",
                timestamp=datetime.utcnow()
            ),
            ConversationMessage(
                role="assistant",
                content="Meeting scheduled",
                timestamp=datetime.utcnow()
            )
        ],
        context={"test": "data"}
    )
    
    # Save state
    try:
        await storage_manager.save_session_state(session_id, state)
        print(f"✓ Session state saved: {session_id}")
    except Exception as e:
        print(f"✗ Failed to save session state: {e}")
        return False
    
    # Load state
    try:
        loaded_state = await storage_manager.load_session_state(session_id)
        assert loaded_state is not None, "Failed to load session state"
        assert loaded_state.session_id == session_id, "Session ID mismatch"
        assert len(loaded_state.conversation_history) == 2, "Conversation history mismatch"
        print(f"✓ Session state loaded successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to load session state: {e}")
        return False


async def run_integration_tests():
    """Run all integration tests."""
    print("=" * 60)
    print("summitassistant Integration Tests")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Meeting Scheduling", await test_meeting_scheduling()))
    results.append(("Summarization", await test_summarization()))
    results.append(("Meeting Retrieval", await test_meeting_retrieval()))
    results.append(("Session State Persistence", await test_session_state_persistence()))
    
    # Print summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    print("=" * 60)
    
    return passed == total


def main():
    """Main entry point."""
    try:
        success = asyncio.run(run_integration_tests())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
