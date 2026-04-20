"""MCP server client for Google Calendar integration."""

import os
import logging
from typing import Optional, Dict, Any
import httpx

logger = logging.getLogger(__name__)


class MCPServerError(Exception):
    """Raised when MCP server API fails."""
    pass


class ValidationError(Exception):
    """Raised when MCP server returns validation error (400)."""
    pass


class MCPServerClient:
    """Client for interacting with MCP server for Google Calendar operations."""

    def __init__(self, server_url: Optional[str] = None):
        """Initialize MCP server client.
        
        Args:
            server_url: MCP server endpoint URL (defaults to MCP_SERVER_URL env var)
        """
        self.server_url = server_url or os.getenv("MCP_SERVER_URL")
        if not self.server_url:
            raise ValueError("MCP_SERVER_URL must be provided or set in environment")
        
        logger.info(f"MCPServerClient initialized with server_url={self.server_url}")

    async def schedule_meeting(
        self,
        date: str,
        time: str,
        duration_minutes: int,
        attendees: list[str],
        title: str,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Schedule a meeting in Google Calendar via MCP server.
        
        Args:
            date: Meeting date in ISO 8601 format (YYYY-MM-DD)
            time: Meeting time in HH:MM format
            duration_minutes: Meeting duration in minutes
            attendees: List of attendee email addresses
            title: Meeting title
            description: Optional meeting description
            
        Returns:
            Dictionary containing:
                - meeting_id: Google Calendar event ID
                - status: Confirmation status
                - calendar_link: Link to calendar event
                - created_at: Timestamp of creation
                
        Raises:
            MCPServerError: On API failures or network errors
            ValidationError: On invalid input (400 response)
        """
        meeting_data = {
            "date": date,
            "time": time,
            "duration_minutes": duration_minutes,
            "attendees": attendees,
            "title": title,
        }
        
        if description:
            meeting_data["description"] = description
        
        logger.info(f"Scheduling meeting: {title} on {date} at {time}")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.server_url}/schedule",
                    json=meeting_data,
                    timeout=30.0
                )
                
                # Handle validation errors (400)
                if response.status_code == 400:
                    error_detail = response.json().get("detail", "Invalid request")
                    logger.error(f"Validation error from MCP server: {error_detail}")
                    raise ValidationError(f"Invalid meeting request: {error_detail}")
                
                # Handle other client/server errors
                if response.status_code >= 400:
                    error_detail = response.json().get("detail", "Unknown error")
                    logger.error(
                        f"MCP server error (status {response.status_code}): {error_detail}"
                    )
                    raise MCPServerError(
                        f"MCP server returned error {response.status_code}: {error_detail}"
                    )
                
                # Parse successful response
                response_data = response.json()
                
                result = {
                    "meeting_id": response_data.get("meeting_id"),
                    "status": response_data.get("status"),
                    "calendar_link": response_data.get("calendar_link"),
                    "created_at": response_data.get("created_at")
                }
                
                logger.info(
                    f"Meeting scheduled successfully: meeting_id={result['meeting_id']}"
                )
                
                return result
                
        except httpx.TimeoutException as e:
            logger.error(f"MCP server request timeout: {e}")
            raise MCPServerError(f"MCP server request timeout: {e}")
        except httpx.NetworkError as e:
            logger.error(f"Network error connecting to MCP server: {e}")
            raise MCPServerError(f"Network error: {e}")
        except (ValidationError, MCPServerError):
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling MCP server: {e}")
            raise MCPServerError(f"Unexpected error: {e}")
