#!/usr/bin/env python3
"""Calendar MCP Server for Google Calendar integration.

This server provides a REST API for scheduling meetings in Google Calendar.
It can be deployed to EKS alongside the SummitAssistant agent.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional
import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Calendar MCP Server",
    description="MCP server for Google Calendar integration",
    version="1.0.0"
)


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
    meeting_id: str = Field(..., description="Unique meeting identifier")
    status: str = Field(..., description="Meeting status (confirmed, pending, etc.)")
    calendar_link: str = Field(..., description="Link to calendar event")
    created_at: str = Field(..., description="Timestamp of creation")


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "calendar-mcp-server",
        "version": "1.0.0"
    }


@app.post("/schedule", response_model=MeetingResponse)
async def schedule_meeting(request: MeetingRequest):
    """Schedule a meeting in Google Calendar.
    
    This is a mock implementation for demo purposes. In production, this would
    integrate with the actual Google Calendar API.
    
    Args:
        request: Meeting scheduling request
        
    Returns:
        Meeting response with confirmation details
        
    Raises:
        HTTPException: On validation or scheduling errors
    """
    logger.info(f"Scheduling meeting: {request.title} on {request.date} at {request.time}")
    
    # Validate date format
    try:
        meeting_date = datetime.strptime(request.date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Expected YYYY-MM-DD"
        )
    
    # Validate time format
    try:
        meeting_time = datetime.strptime(request.time, "%H:%M")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid time format. Expected HH:MM"
        )
    
    # Validate attendees
    if not request.attendees:
        raise HTTPException(
            status_code=400,
            detail="At least one attendee is required"
        )
    
    # Generate unique meeting ID
    meeting_id = str(uuid.uuid4())
    
    # In production, this would call Google Calendar API
    # For demo, we return a mock response
    response = MeetingResponse(
        meeting_id=meeting_id,
        status="confirmed",
        calendar_link=f"https://calendar.google.com/event/{meeting_id}",
        created_at=datetime.utcnow().isoformat() + "Z"
    )
    
    logger.info(f"Meeting scheduled successfully: {meeting_id}")
    
    return response


@app.get("/")
def root():
    """Root endpoint with API information."""
    return {
        "service": "Calendar MCP Server",
        "version": "1.0.0",
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
    
    logger.info(f"Starting Calendar MCP Server on {host}:{port}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )


if __name__ == "__main__":
    main()
