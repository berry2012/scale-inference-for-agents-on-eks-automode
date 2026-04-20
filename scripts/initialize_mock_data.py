#!/usr/bin/env python3
"""Initialize mock meeting data for SummitAssistant demo.

This script creates 5 mock meeting notes with realistic content and uploads
them to S3 storage. The script is idempotent - it checks for an initialization
flag and skips creation if mock data already exists.
"""

import asyncio
import logging
import os
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from SummitAssistant.models import MeetingNote
from SummitAssistant.storage_manager import StorageManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Mock meeting data templates
MOCK_MEETINGS = [
    {
        "title": "Q1 Sprint Planning",
        "attendees": [
            "alice@example.com",
            "bob@example.com",
            "charlie@example.com"
        ],
        "content": """Sprint Planning Meeting - Q1 2026

Attendees: Alice (Product Manager), Bob (Tech Lead), Charlie (Engineer)

Topics Discussed:
- Review of Q4 2025 deliverables and lessons learned
- Q1 2026 roadmap priorities and feature planning
- Resource allocation and team capacity
- Technical debt items to address

Key Decisions:
- Prioritize user authentication feature for Q1
- Allocate 20% of sprint capacity to technical debt
- Implement bi-weekly demo sessions for stakeholders
- Adopt new CI/CD pipeline for faster deployments

Action Items:
- Alice: Create detailed user stories for authentication feature by Jan 20
- Bob: Evaluate CI/CD tools and present recommendation by Jan 25
- Charlie: Document technical debt backlog by Jan 22
- Team: Schedule bi-weekly demo slots with stakeholders

Next Meeting: February 1, 2026
""",
        "days_ago": 35
    },
    {
        "title": "Architecture Review: Microservices Migration",
        "attendees": [
            "bob@example.com",
            "david@example.com",
            "eve@example.com"
        ],
        "content": """Architecture Review Meeting

Attendees: Bob (Tech Lead), David (Senior Architect), Eve (DevOps Engineer)

Topics Discussed:
- Current monolithic architecture pain points
- Proposed microservices architecture design
- Service boundaries and API contracts
- Data consistency and distributed transactions
- Deployment strategy and rollout plan

Key Decisions:
- Adopt event-driven architecture with message queues
- Start with 3 core services: Auth, User Management, Notifications
- Use Kubernetes for container orchestration
- Implement API gateway for service routing
- Adopt saga pattern for distributed transactions

Action Items:
- David: Create detailed architecture diagrams by Feb 5
- Eve: Set up EKS cluster for development environment by Feb 10
- Bob: Define API contracts for initial 3 services by Feb 8
- Team: Schedule follow-up review for Feb 15

Technical Considerations:
- Service discovery using Kubernetes DNS
- Centralized logging with CloudWatch
- Distributed tracing with X-Ray
- Circuit breaker pattern for resilience
""",
        "days_ago": 28
    },
    {
        "title": "Security Incident Post-Mortem",
        "attendees": [
            "frank@example.com",
            "grace@example.com",
            "bob@example.com",
            "eve@example.com"
        ],
        "content": """Security Incident Post-Mortem

Attendees: Frank (Security Lead), Grace (SRE), Bob (Tech Lead), Eve (DevOps)

Incident Summary:
- Date: January 18, 2026
- Duration: 2 hours 15 minutes
- Severity: Medium
- Impact: Temporary service degradation, no data breach

Timeline:
- 14:30 UTC: Unusual API traffic patterns detected
- 14:45 UTC: Rate limiting triggered, some requests blocked
- 15:00 UTC: Security team notified, investigation started
- 16:15 UTC: Root cause identified - misconfigured API key rotation
- 16:45 UTC: Issue resolved, services restored

Root Cause:
- Automated API key rotation script had incorrect permissions
- Old keys were invalidated before new keys were distributed
- Monitoring alerts were delayed due to threshold misconfiguration

Key Decisions:
- Implement staged key rotation with overlap period
- Add pre-rotation validation checks
- Improve monitoring alert sensitivity
- Conduct quarterly security drills

Action Items:
- Frank: Update key rotation procedure documentation by Jan 25
- Grace: Implement new monitoring thresholds by Jan 28
- Eve: Add pre-rotation validation to automation scripts by Feb 1
- Bob: Schedule security drill for March 2026

Lessons Learned:
- Need better visibility into key rotation process
- Alert thresholds need regular review and tuning
- Incident response time was good, but detection was delayed
""",
        "days_ago": 21
    },
    {
        "title": "Product Roadmap Review - H1 2026",
        "attendees": [
            "alice@example.com",
            "helen@example.com",
            "bob@example.com"
        ],
        "content": """Product Roadmap Review Meeting

Attendees: Alice (Product Manager), Helen (VP Product), Bob (Tech Lead)

Topics Discussed:
- Customer feedback analysis from Q4 2025
- Market trends and competitive landscape
- H1 2026 feature priorities
- Resource requirements and hiring needs
- Go-to-market strategy for major features

Key Decisions:
- Launch mobile app beta in March 2026
- Implement advanced analytics dashboard by April
- Add multi-language support starting with Spanish and French
- Expand API capabilities for enterprise customers
- Invest in AI-powered recommendation engine

Action Items:
- Alice: Create detailed PRDs for top 3 features by Feb 10
- Helen: Approve budget for 2 additional engineers by Feb 5
- Bob: Provide technical feasibility assessment by Feb 12
- Alice: Schedule customer advisory board meeting for March

Feature Priorities (H1 2026):
1. Mobile app (iOS and Android)
2. Advanced analytics dashboard
3. Multi-language support
4. Enterprise API enhancements
5. AI recommendation engine

Success Metrics:
- Mobile app: 10K downloads in first month
- Analytics: 60% user adoption within 2 months
- Multi-language: 25% international user growth
- API: 5 new enterprise customers
""",
        "days_ago": 14
    },
    {
        "title": "Weekly Team Sync - Engineering",
        "attendees": [
            "bob@example.com",
            "charlie@example.com",
            "david@example.com",
            "eve@example.com",
            "ian@example.com"
        ],
        "content": """Weekly Engineering Team Sync

Attendees: Bob (Tech Lead), Charlie, David, Eve, Ian (Engineers)

Sprint Progress:
- Authentication feature: 75% complete, on track for sprint end
- API rate limiting: 90% complete, testing in progress
- Database migration: 50% complete, some blockers identified
- Documentation updates: 30% complete, needs more attention

Blockers and Issues:
- Database migration blocked on DBA approval for schema changes
- Third-party OAuth provider having intermittent issues
- Test environment instability affecting QA

Key Decisions:
- Escalate database schema approval to VP Engineering
- Implement fallback for OAuth provider issues
- Allocate dedicated time for test environment stabilization
- Add documentation time to sprint planning

Action Items:
- Bob: Escalate DB schema approval by end of day
- Charlie: Implement OAuth fallback by tomorrow
- Eve: Debug and fix test environment issues by Friday
- David: Review and update API documentation by Friday
- Ian: Complete authentication feature testing by Monday

Team Updates:
- New engineer starting next Monday
- Team offsite planned for March 15
- Code review guidelines updated, see wiki
- New deployment process in effect starting next sprint

Next Meeting: February 10, 2026
""",
        "days_ago": 7
    }
]


async def check_initialization_flag(storage_manager: StorageManager) -> bool:
    """Check if mock data has already been initialized.
    
    Args:
        storage_manager: StorageManager instance
        
    Returns:
        True if flag exists (already initialized), False otherwise
    """
    try:
        response = storage_manager.s3_client.head_object(
            Bucket=storage_manager.bucket_name,
            Key="meetings/mock-initialized.flag"
        )
        logger.info("Initialization flag found - mock data already exists")
        return True
    except storage_manager.s3_client.exceptions.NoSuchKey:
        logger.info("Initialization flag not found - proceeding with initialization")
        return False
    except Exception as e:
        logger.warning(f"Error checking initialization flag: {e}")
        return False


async def create_initialization_flag(storage_manager: StorageManager) -> None:
    """Create initialization flag to mark completion.
    
    Args:
        storage_manager: StorageManager instance
    """
    try:
        storage_manager.s3_client.put_object(
            Bucket=storage_manager.bucket_name,
            Key="meetings/mock-initialized.flag",
            Body=f"Initialized at {datetime.utcnow().isoformat()}",
            ContentType="text/plain"
        )
        logger.info("Created initialization flag")
    except Exception as e:
        logger.error(f"Failed to create initialization flag: {e}")
        raise


async def initialize_mock_data() -> None:
    """Initialize mock meeting data in S3.
    
    Creates 5 mock meetings spanning at least 30 days in the past.
    Idempotent - skips initialization if flag file exists.
    """
    logger.info("Starting mock data initialization")
    
    # Initialize storage manager
    storage_manager = StorageManager()
    
    # Check if already initialized
    if await check_initialization_flag(storage_manager):
        logger.info("Mock data already initialized - skipping")
        return
    
    # Generate mock meetings
    now = datetime.utcnow()
    created_count = 0
    
    for i, mock_data in enumerate(MOCK_MEETINGS, start=1):
        # Generate unique meeting ID
        meeting_id = f"mock-{uuid.uuid4()}"
        
        # Calculate timestamp (days ago from now)
        timestamp = now - timedelta(days=mock_data["days_ago"])
        
        # Create MeetingNote object
        meeting_note = MeetingNote(
            meeting_id=meeting_id,
            timestamp=timestamp,
            attendees=mock_data["attendees"],
            title=mock_data["title"],
            content=mock_data["content"],
            metadata={
                "created_by": "initialization_script",
                "version": "1.0",
                "is_mock": True
            }
        )
        
        # Save to S3
        try:
            await storage_manager.save_meeting_note(meeting_id, meeting_note)
            created_count += 1
            logger.info(
                f"Created mock meeting {i}/5: {mock_data['title']} "
                f"(ID: {meeting_id}, Date: {timestamp.date()})"
            )
        except Exception as e:
            logger.error(f"Failed to create mock meeting {i}: {e}")
            raise
    
    # Create initialization flag
    await create_initialization_flag(storage_manager)
    
    logger.info(
        f"Mock data initialization complete - created {created_count} meetings "
        f"spanning {MOCK_MEETINGS[0]['days_ago']} to {MOCK_MEETINGS[-1]['days_ago']} days ago"
    )


def main():
    """Main entry point."""
    try:
        asyncio.run(initialize_mock_data())
        logger.info("Initialization script completed successfully")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Initialization script failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
