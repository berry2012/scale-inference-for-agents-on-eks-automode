#!/usr/bin/env python3
"""Calendar MCP Server with real Google Calendar integration.

This server provides a REST API for scheduling meetings in Google Calendar
using Google Calendar API with service account authentication.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Calendar MCP Server",
    description="MCP server for Google Calendar integration",
    version="2.0.0"
)

# Google Calendar API configuration
SCOPES = ['https://www.googleapis.com/auth/calendar']
CREDENTIALS_PATH = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '/secrets/credentials.json')
CALENDAR_ID = os.getenv('CALENDAR_ID', 'primary')


class MeetingRequest(BaseModel):
    """Meeting scheduling request."""
    date: str = Field(..., description="Meeting date in ISO 8601 format (YYYY-MM-DD)")
    time: str = Field(..., description="Meeting time in HH:MM format")
    duration_minutes: int = Field(..., description="Meeting duration in minutes", gt=0)
    attendees: list[str] = Field(..., description="List of attendee email addresses")
    title: str = Field(..., description="Meeting title")
    description: Optional[str] = Field(None, description="Optional meeting description")


class MeetingResponse(BaseModel):
    """Meeting scheduling response."""
    meeting_id: str = Field(..., description="Unique meeting identifier (Google Calendar event ID)")
    status: str = Field(..., description="Meeting status (confirmed, tentative, cancelled)")
    calendar_link: str = Field(..., description="Link to calendar event")
    created_at: str = Field(..., description="Timestamp of creation")
    hangout_link: Optional[str] = Field(None, description="Google Meet link if available")


def get_calendar_service():
    """Initialize and return Google Calendar API service.
    
    Returns:
        Google Calendar API service instance
        
    Raises:
        Exception: If credentials are invalid or API cannot be initialized
    """
    try:
        credentials = service_account.Credentials.from_service_account_file(
            CREDENTIALS_PATH,
            scopes=SCOPES
        )
        service = build('calendar', 'v3', credentials=credentials)
        logger.info("Google Calendar API service initialized successfully")
        return service
    except Exception as e:
        logger.error(f"Failed to initialize Google Calendar API: {e}")
        raise


@app.get("/health")
def health_check():
    """Health check endpoint.
    
    Verifies that the service can connect to Google Calendar API.
    """
    try:
        # Try to initialize service to verify credentials
        service = get_calendar_service()
        
        # Test API access by fetching calendar info
        calendar = service.calendars().get(calendarId=CALENDAR_ID).execute()
        
        return {
            "status": "healthy",
            "service": "calendar-mcp-server",
            "version": "2.0.0",
            "calendar_id": CALENDAR_ID,
            "calendar_summary": calendar.get('summary', 'Unknown')
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Service unhealthy: {str(e)}"
        )


@app.post("/schedule", response_model=MeetingResponse)
async def schedule_meeting(request: MeetingRequest):
    """Schedule a meeting in Google Calendar.
    
    Creates a calendar event with the specified details and sends invitations
    to all attendees.
    
    Args:
        request: Meeting scheduling request
        
    Returns:
        Meeting response with confirmation details and Google Calendar link
        
    Raises:
        HTTPException: On validation or scheduling errors
    """
    logger.info(f"Scheduling meeting: {request.title} on {request.date} at {request.time}")
    
    # Validate and parse date
    try:
        meeting_date = datetime.strptime(request.date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Expected YYYY-MM-DD"
        )
    
    # Validate and parse time
    try:
        meeting_time = datetime.strptime(request.time, "%H:%M")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid time format. Expected HH:MM"
        )
    
    # Combine date and time
    start_datetime = datetime.combine(
        meeting_date.date(),
        meeting_time.time()
    )
    
    # Calculate end time
    end_datetime = start_datetime + timedelta(minutes=request.duration_minutes)
    
    # Validate attendees
    if not request.attendees:
        raise HTTPException(
            status_code=400,
            detail="At least one attendee is required"
        )
    
    # Build event object
    event = {
        'summary': request.title,
        'description': request.description or '',
        'start': {
            'dateTime': start_datetime.isoformat(),
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': end_datetime.isoformat(),
            'timeZone': 'UTC',
        },
        'attendees': [{'email': email} for email in request.attendees],
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'email', 'minutes': 24 * 60},  # 1 day before
                {'method': 'popup', 'minutes': 10},        # 10 minutes before
            ],
        },
        # Optional: Add Google Meet conference
        'conferenceData': {
            'createRequest': {
                'requestId': f"meet-{start_datetime.timestamp()}",
                'conferenceSolutionKey': {'type': 'hangoutsMeet'}
            }
        }
    }
    
    try:
        # Initialize Calendar API service
        service = get_calendar_service()
        
        # Create the event
        created_event = service.events().insert(
            calendarId=CALENDAR_ID,
            body=event,
            conferenceDataVersion=1,  # Required for Google Meet
            sendUpdates='all'  # Send email invitations to attendees
        ).execute()
        
        # Extract response data
        event_id = created_event['id']
        event_link = created_event.get('htmlLink', f"https://calendar.google.com/event?eid={event_id}")
        status = created_event.get('status', 'confirmed')
        created_at = created_event.get('created', datetime.utcnow().isoformat() + 'Z')
        
        # Extract Google Meet link if available
        hangout_link = None
        if 'conferenceData' in created_event:
            entry_points = created_event['conferenceData'].get('entryPoints', [])
            for entry in entry_points:
                if entry.get('entryPointType') == 'video':
                    hangout_link = entry.get('uri')
                    break
        
        response = MeetingResponse(
            meeting_id=event_id,
            status=status,
            calendar_link=event_link,
            created_at=created_at,
            hangout_link=hangout_link
        )
        
        logger.info(f"Meeting scheduled successfully: {event_id}")
        logger.info(f"Calendar link: {event_link}")
        if hangout_link:
            logger.info(f"Google Meet link: {hangout_link}")
        
        return response
        
    except HttpError as e:
        logger.error(f"Google Calendar API error: {e}")
        
        # Parse error details
        error_details = str(e)
        status_code = 500
        
        if 'insufficient permissions' in error_details.lower():
            status_code = 403
            detail = "Insufficient permissions to access calendar"
        elif 'not found' in error_details.lower():
            status_code = 404
            detail = f"Calendar not found: {CALENDAR_ID}"
        elif 'quota' in error_details.lower():
            status_code = 429
            detail = "API quota exceeded"
        else:
            detail = f"Failed to create calendar event: {error_details}"
        
        raise HTTPException(status_code=status_code, detail=detail)
        
    except Exception as e:
        logger.error(f"Unexpected error scheduling meeting: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/")
def root():
    """Root endpoint with API information."""
    return {
        "service": "Calendar MCP Server",
        "version": "2.0.0",
        "calendar_id": CALENDAR_ID,
        "endpoints": {
            "health": "/health",
            "schedule": "/schedule (POST)",
            "docs": "/docs"
        }
    }


def main():
    """Main entry point."""
    port = int(os.getenv("PORT", "8080"))
    host = os.getenv("HOST", "0.0.0.0")
    
    # Verify credentials exist
    if not os.path.exists(CREDENTIALS_PATH):
        logger.error(f"Credentials file not found: {CREDENTIALS_PATH}")
        logger.error("Please set GOOGLE_APPLICATION_CREDENTIALS environment variable")
        exit(1)
    
    logger.info(f"Starting Calendar MCP Server on {host}:{port}")
    logger.info(f"Using calendar ID: {CALENDAR_ID}")
    logger.info(f"Credentials path: {CREDENTIALS_PATH}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )


if __name__ == "__main__":
    main()
