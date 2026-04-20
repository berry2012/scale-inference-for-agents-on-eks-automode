"""summitassistant agent orchestration logic."""

import os
import logging
import uuid
import httpx
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

from strands import Agent, tool
from strands_tools import current_time

from summitassistant.models import (
    MeetingRequest,
    MeetingNote,
    Summary,
    SessionState,
    ConversationMessage,
    OperationStatus,
    OperationResult
)
from summitassistant.storage_manager import StorageManager
from summitassistant.llm_client import LLMServiceClient, ValidationError as LLMValidationError
from summitassistant.calendar_manager import MCPServerClient, MCPServerError, ValidationError as MCPValidationError
from summitassistant.retry_manager import RetryManager

logger = logging.getLogger(__name__)


class summitassistant:
    """AI agent for meeting management with calendar, LLM, and storage integration.
    
    This class wraps the Strands Agent framework and provides tools for:
    - Scheduling meetings via Google Calendar (MCP server)
    - Summarizing meeting notes using LLM
    - Retrieving past meetings from S3 storage
    """

    def __init__(
        self,
        storage_manager: Optional[StorageManager] = None,
        llm_client: Optional[LLMServiceClient] = None,
        mcp_client: Optional[MCPServerClient] = None,
        retry_manager: Optional[RetryManager] = None,
        session_id: Optional[str] = None,
        model: Optional[str] = None,
        weather_agent_url: Optional[str] = None
    ):
        """Initialize summitassistant agent.
        
        Args:
            storage_manager: StorageManager instance (creates default if not provided)
            llm_client: LLMServiceClient instance (creates default if not provided)
            mcp_client: MCPServerClient instance (creates default if not provided)
            retry_manager: RetryManager instance (creates default if not provided)
            session_id: Session ID for state persistence (generates new if not provided)
            model: Model identifier for Strands Agent (defaults to Bedrock)
            weather_agent_url: URL for Weather Agent service (defaults to env var)
        """
        # Initialize retry manager first (used by other components)
        self.retry_manager = retry_manager or RetryManager(max_retries=3, base_delay=1.0)
        
        # Initialize service clients
        self.storage_manager = storage_manager or StorageManager(retry_manager=self.retry_manager)
        self.llm_client = llm_client or LLMServiceClient(retry_manager=self.retry_manager)
        self.mcp_client = mcp_client or MCPServerClient()
        
        # Weather Agent configuration
        self.weather_agent_url = weather_agent_url or os.getenv(
            "WEATHER_AGENT_URL", 
            "http://strands-weather-agent/agent"
        )
        
        # Session management
        self.session_id = session_id or str(uuid.uuid4())
        self.session_state: Optional[SessionState] = None
        
        # Create tool instances bound to this agent instance
        self._schedule_meeting_tool = self._create_schedule_meeting_tool()
        self._summarize_meeting_tool = self._create_summarize_meeting_tool()
        self._retrieve_meetings_tool = self._create_retrieve_meetings_tool()
        self._weather_agent_tool = self._create_weather_agent_tool()
        
        # Initialize Strands Agent with tools
        self.agent = Agent(
            model=model,
            name="summitassistant",
            description="AI agent for meeting management with calendar, LLM, and storage integration",
            tools=[
                self._schedule_meeting_tool,
                self._summarize_meeting_tool,
                self._retrieve_meetings_tool,
                self._weather_agent_tool,
                current_time
            ],
            system_prompt="""You are summitassistant, an AI agent that helps manage meetings and provides information.

You have access to five tools:
1. schedule_meeting: Schedule meetings in Google Calendar
2. summarize_meeting: Generate summaries of meeting notes using LLM
3. retrieve_meetings: Search and retrieve past meetings from storage
4. ask_weather_agent: Get time or weather information for any location by asking the Weather Agent
5. current_time: Get the current date and time

IMPORTANT: When users ask about meetings from relative time periods (e.g., "past week", "last month"), 
you MUST first call the current_time tool to get the actual current date, then calculate the date range 
based on that. Do NOT assume the current date.

When users ask about weather or time in a specific location, use the ask_weather_agent tool to get 
accurate information from the specialized Weather Agent.

Always use the appropriate tool based on the user's request. Provide clear, helpful responses."""
        )
        
        logger.info(f"summitassistant initialized with session_id={self.session_id}, weather_agent_url={self.weather_agent_url}")

    async def initialize(self) -> None:
        """Initialize agent by loading or creating session state.
        
        This method should be called after instantiation to load existing
        session state from S3 or create a new default state.
        """
        logger.info(f"Initializing agent session: {self.session_id}")
        
        # Try to load existing session state
        self.session_state = await self.storage_manager.load_session_state(self.session_id)
        
        if self.session_state:
            logger.info(f"Loaded existing session state with {len(self.session_state.conversation_history)} messages")
        else:
            # Create default session state
            logger.info("No existing session state found, creating new session")
            self.session_state = SessionState(
                session_id=self.session_id,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                conversation_history=[],
                context={}
            )
            
            # Save initial state
            await self.storage_manager.save_session_state(self.session_id, self.session_state)
        
        logger.info("Agent initialization complete")

    async def _update_session_state(self, user_message: Optional[str] = None, assistant_message: Optional[str] = None) -> None:
        """Update session state with new messages and save to S3.
        
        Args:
            user_message: User message to add to history
            assistant_message: Assistant message to add to history
        """
        if not self.session_state:
            logger.warning("Session state not initialized, skipping update")
            return
        
        now = datetime.now()
        
        # Add messages to conversation history
        if user_message:
            self.session_state.conversation_history.append(
                ConversationMessage(role="user", content=user_message, timestamp=now)
            )
        
        if assistant_message:
            self.session_state.conversation_history.append(
                ConversationMessage(role="assistant", content=assistant_message, timestamp=now)
            )
        
        # Update timestamp
        self.session_state.updated_at = now
        
        # Save to S3
        await self.storage_manager.save_session_state(self.session_id, self.session_state)
        logger.debug(f"Session state updated and saved")

    def _create_schedule_meeting_tool(self):
        """Create the schedule_meeting tool bound to this agent instance."""
        agent_self = self  # Capture self for closure
        
        @tool(
            name="schedule_meeting",
            description="Schedule a meeting in Google Calendar via MCP server"
        )
        async def schedule_meeting_tool(
            date: str,
            time: str,
            duration_minutes: int,
            attendees: List[str],
            title: str,
            description: Optional[str] = None
        ) -> Dict[str, Any]:
            """Schedule a meeting in Google Calendar.
            
            Args:
                date: Meeting date in ISO 8601 format (YYYY-MM-DD)
                time: Meeting time in HH:MM format
                duration_minutes: Meeting duration in minutes
                attendees: List of attendee email addresses
                title: Meeting title
                description: Optional meeting description
                
            Returns:
                Dictionary with meeting_id, status, and calendar_link
            """
            request = MeetingRequest(
                date=date,
                time=time,
                duration_minutes=duration_minutes,
                attendees=attendees,
                title=title,
                description=description
            )
            result = await agent_self.schedule_meeting(request)
            return result.__dict__
        
        return schedule_meeting_tool
    
    def _create_summarize_meeting_tool(self):
        """Create the summarize_meeting tool bound to this agent instance."""
        agent_self = self
        
        @tool(
            name="summarize_meeting",
            description="Generate a summary of meeting notes using LLM and save to S3"
        )
        async def summarize_meeting_tool(
            meeting_id: str,
            title: str,
            content: str,
            attendees: List[str],
            timestamp: Optional[str] = None
        ) -> Dict[str, Any]:
            """Summarize meeting notes and save to storage.
            
            Args:
                meeting_id: Unique meeting identifier
                title: Meeting title
                content: Meeting notes content (max 10000 characters)
                attendees: List of attendee email addresses
                timestamp: Optional meeting timestamp in ISO format
                
            Returns:
                Dictionary with summary and metadata
            """
            note = MeetingNote(
                meeting_id=meeting_id,
                timestamp=datetime.fromisoformat(timestamp) if timestamp else datetime.now(),
                attendees=attendees,
                title=title,
                content=content,
                metadata={}
            )
            result = await agent_self.summarize_meeting(note)
            return result.__dict__
        
        return summarize_meeting_tool
    
    def _create_retrieve_meetings_tool(self):
        """Create the retrieve_meetings tool bound to this agent instance."""
        agent_self = self
        
        @tool(
            name="retrieve_meetings",
            description="Search and retrieve past meetings from S3 storage"
        )
        async def retrieve_meetings_tool(
            meeting_id: Optional[str] = None,
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
            attendee: Optional[str] = None
        ) -> Dict[str, Any]:
            """Retrieve past meetings based on search criteria.
            
            Args:
                meeting_id: Specific meeting ID for exact match
                start_date: Start date for date range filter (ISO format)
                end_date: End date for date range filter (ISO format)
                attendee: Filter by attendee email address
                
            Returns:
                Dictionary with list of meetings and summaries
            """
            date_range = None
            if start_date and end_date:
                date_range = (start_date, end_date)
            
            result = await agent_self.retrieve_meetings(
                meeting_id=meeting_id,
                date_range=date_range,
                attendee=attendee
            )
            return result.__dict__
        
        return retrieve_meetings_tool

    def _create_weather_agent_tool(self):
        """Create the weather_agent tool for agent-to-agent communication."""
        agent_self = self
        
        @tool(
            name="ask_weather_agent",
            description="Ask the Weather Agent for time or weather information for any location"
        )
        async def weather_agent_tool(query: str) -> Dict[str, Any]:
            """Query the Weather Agent for time or weather information.
            
            Args:
                query: Natural language query about time or weather (e.g., "What's the weather in Amsterdam?")
                
            Returns:
                Dictionary with the Weather Agent's response
            """
            result = await agent_self.call_weather_agent(query)
            return result
        
        return weather_agent_tool


    async def schedule_meeting(self, request: MeetingRequest) -> OperationResult:
        """Schedule a meeting via MCP server.
        
        Workflow:
        1. Validate meeting request
        2. Call MCP server to schedule meeting
        3. Update session state
        4. Return result
        
        Args:
            request: Meeting request with date, time, duration, attendees, title
            
        Returns:
            OperationResult with meeting_id on success or error message on failure
        """
        logger.info(f"Processing schedule_meeting request: {request.title}")
        
        # Step 1: Validate meeting request
        validation_errors = request.validate()
        if validation_errors:
            error_msg = f"Invalid meeting request: {', '.join(validation_errors)}"
            logger.warning(error_msg)
            
            # Update session state
            await self._update_session_state(
                user_message=f"Schedule meeting: {request.title}",
                assistant_message=error_msg
            )
            
            return OperationResult(
                status=OperationStatus.FAILED,
                message=error_msg,
                error=error_msg
            )
        
        # Step 2: Call MCP server
        try:
            mcp_response = await self.mcp_client.schedule_meeting(
                date=request.date,
                time=request.time,
                duration_minutes=request.duration_minutes,
                attendees=request.attendees,
                title=request.title,
                description=request.description
            )
            
            meeting_id = mcp_response.get("meeting_id")
            success_msg = f"Meeting scheduled successfully: {meeting_id}"
            logger.info(success_msg)
            
            # Update session state
            await self._update_session_state(
                user_message=f"Schedule meeting: {request.title} on {request.date} at {request.time}",
                assistant_message=success_msg
            )
            
            return OperationResult(
                status=OperationStatus.SUCCESS,
                message=success_msg,
                data=mcp_response
            )
            
        except MCPValidationError as e:
            error_msg = f"MCP validation error: {str(e)}"
            logger.error(error_msg)
            
            await self._update_session_state(
                user_message=f"Schedule meeting: {request.title}",
                assistant_message=error_msg
            )
            
            return OperationResult(
                status=OperationStatus.FAILED,
                message=error_msg,
                error=str(e)
            )
            
        except MCPServerError as e:
            error_msg = f"MCP server error: {str(e)}"
            logger.error(error_msg)
            
            await self._update_session_state(
                user_message=f"Schedule meeting: {request.title}",
                assistant_message=error_msg
            )
            
            return OperationResult(
                status=OperationStatus.FAILED,
                message=error_msg,
                error=str(e)
            )

    async def summarize_meeting(self, note: MeetingNote) -> OperationResult:
        """Summarize meeting notes using LLM and save to S3.
        
        Workflow:
        1. Validate meeting note
        2. Call LLM service to generate summary
        3. Save meeting note to S3
        4. Save summary to S3
        5. Update session state
        6. Return result
        
        Args:
            note: Meeting note to summarize
            
        Returns:
            OperationResult with summary on success or error message on failure
        """
        logger.info(f"Processing summarize_meeting request: {note.meeting_id}")
        
        # Step 1: Validate meeting note
        if not note.content or not note.content.strip():
            error_msg = "Meeting note content cannot be empty"
            logger.warning(error_msg)
            
            await self._update_session_state(
                user_message=f"Summarize meeting: {note.title}",
                assistant_message=error_msg
            )
            
            return OperationResult(
                status=OperationStatus.FAILED,
                message=error_msg,
                error=error_msg
            )
        
        if len(note.content) > 10000:
            error_msg = "Meeting note content exceeds 10000 character limit"
            logger.warning(error_msg)
            
            await self._update_session_state(
                user_message=f"Summarize meeting: {note.title}",
                assistant_message=error_msg
            )
            
            return OperationResult(
                status=OperationStatus.FAILED,
                message=error_msg,
                error=error_msg
            )
        
        # Step 2: Call LLM service
        try:
            summary_text = await self.llm_client.summarize_meeting_notes(note.content)
            
            # Validate summary is non-empty
            if not summary_text or not summary_text.strip():
                error_msg = "LLM returned empty summary"
                logger.error(error_msg)
                
                await self._update_session_state(
                    user_message=f"Summarize meeting: {note.title}",
                    assistant_message=error_msg
                )
                
                return OperationResult(
                    status=OperationStatus.FAILED,
                    message=error_msg,
                    error=error_msg
                )
            
            # Create Summary object with metadata
            summary = Summary(
                meeting_id=note.meeting_id,
                summary=summary_text,
                generated_at=datetime.now(),
                model=self.llm_client.model,
                key_topics=[],  # Could be extracted from summary in future
                action_items=[]  # Could be extracted from summary in future
            )
            
            logger.info(f"Generated summary for meeting {note.meeting_id}")
            
        except LLMValidationError as e:
            error_msg = f"LLM validation error: {str(e)}"
            logger.error(error_msg)
            
            await self._update_session_state(
                user_message=f"Summarize meeting: {note.title}",
                assistant_message=error_msg
            )
            
            return OperationResult(
                status=OperationStatus.FAILED,
                message=error_msg,
                error=str(e)
            )
            
        except (TimeoutError, Exception) as e:
            error_msg = f"LLM service error: {str(e)}"
            logger.error(error_msg)
            
            await self._update_session_state(
                user_message=f"Summarize meeting: {note.title}",
                assistant_message=error_msg
            )
            
            return OperationResult(
                status=OperationStatus.FAILED,
                message=error_msg,
                error=str(e)
            )
        
        # Step 3: Save meeting note to S3
        try:
            await self.storage_manager.save_meeting_note(note.meeting_id, note)
            logger.info(f"Saved meeting note to S3: {note.meeting_id}")
        except Exception as e:
            error_msg = f"Failed to save meeting note: {str(e)}"
            logger.error(error_msg)
            
            await self._update_session_state(
                user_message=f"Summarize meeting: {note.title}",
                assistant_message=error_msg
            )
            
            return OperationResult(
                status=OperationStatus.FAILED,
                message=error_msg,
                error=str(e)
            )
        
        # Step 4: Save summary to S3
        try:
            await self.storage_manager.save_summary(note.meeting_id, summary)
            logger.info(f"Saved summary to S3: {note.meeting_id}")
        except Exception as e:
            error_msg = f"Failed to save summary: {str(e)}"
            logger.error(error_msg)
            
            await self._update_session_state(
                user_message=f"Summarize meeting: {note.title}",
                assistant_message=error_msg
            )
            
            return OperationResult(
                status=OperationStatus.FAILED,
                message=error_msg,
                error=str(e)
            )
        
        # Step 5: Update session state
        success_msg = f"Meeting summarized successfully: {note.meeting_id}"
        await self._update_session_state(
            user_message=f"Summarize meeting: {note.title}",
            assistant_message=success_msg
        )
        
        return OperationResult(
            status=OperationStatus.SUCCESS,
            message=success_msg,
            data={"summary": summary.to_json()}
        )

    async def retrieve_meetings(
        self,
        meeting_id: Optional[str] = None,
        date_range: Optional[Tuple[str, str]] = None,
        attendee: Optional[str] = None
    ) -> OperationResult:
        """Retrieve past meetings from S3 based on query parameters.
        
        Workflow:
        1. Search for meetings matching criteria
        2. For each meeting, retrieve note and summary
        3. Update session state
        4. Return results
        
        Args:
            meeting_id: Specific meeting ID (exact match)
            date_range: Tuple of (start_date, end_date) in ISO format
            attendee: Filter by attendee email
            
        Returns:
            OperationResult with list of meetings and summaries
        """
        logger.info(f"Processing retrieve_meetings request: meeting_id={meeting_id}, date_range={date_range}, attendee={attendee}")
        
        # Step 1: Search for meetings
        try:
            matching_notes = await self.storage_manager.search_meetings(
                meeting_id=meeting_id,
                date_range=date_range,
                attendee=attendee,
                limit=10
            )
            
            if not matching_notes:
                msg = "No matching meetings found"
                logger.info(msg)
                
                await self._update_session_state(
                    user_message=f"Retrieve meetings: meeting_id={meeting_id}, date_range={date_range}, attendee={attendee}",
                    assistant_message=msg
                )
                
                return OperationResult(
                    status=OperationStatus.SUCCESS,
                    message=msg,
                    data={"meetings": []}
                )
            
            logger.info(f"Found {len(matching_notes)} matching meetings")
            
        except Exception as e:
            error_msg = f"Failed to search meetings: {str(e)}"
            logger.error(error_msg)
            
            await self._update_session_state(
                user_message=f"Retrieve meetings: meeting_id={meeting_id}, date_range={date_range}, attendee={attendee}",
                assistant_message=error_msg
            )
            
            return OperationResult(
                status=OperationStatus.FAILED,
                message=error_msg,
                error=str(e)
            )
        
        # Step 2: Retrieve summaries for each meeting
        meetings_with_summaries = []
        
        for note in matching_notes:
            try:
                # Retrieve summary (may be None if not generated yet)
                summary = await self.storage_manager.get_summary(note.meeting_id)
                
                meeting_data = {
                    "note": note.to_json(),
                    "summary": summary.to_json() if summary else None
                }
                
                meetings_with_summaries.append(meeting_data)
                
            except Exception as e:
                logger.warning(f"Failed to retrieve summary for meeting {note.meeting_id}: {e}")
                # Include meeting without summary
                meetings_with_summaries.append({
                    "note": note.to_json(),
                    "summary": None
                })
        
        # Step 3: Update session state
        success_msg = f"Retrieved {len(meetings_with_summaries)} meetings"
        await self._update_session_state(
            user_message=f"Retrieve meetings: meeting_id={meeting_id}, date_range={date_range}, attendee={attendee}",
            assistant_message=success_msg
        )
        
        return OperationResult(
            status=OperationStatus.SUCCESS,
            message=success_msg,
            data={"meetings": meetings_with_summaries}
        )

    async def call_weather_agent(self, query: str) -> Dict[str, Any]:
        """Call the Weather Agent for time or weather information.
        
        This enables agent-to-agent communication using HTTP API.
        
        Args:
            query: Natural language query about time or weather
            
        Returns:
            Dictionary with the Weather Agent's response
        """
        logger.info(f"Calling Weather Agent with query: {query}")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.weather_agent_url,
                    json={"query": query}
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("status") == "success":
                    weather_response = data.get("response", "No response from Weather Agent")
                    logger.info(f"Weather Agent response: {weather_response}")
                    
                    return {
                        "status": "success",
                        "response": weather_response
                    }
                else:
                    error_msg = "Weather Agent returned error status"
                    logger.error(error_msg)
                    return {
                        "status": "error",
                        "response": error_msg
                    }
                    
        except httpx.TimeoutException as e:
            error_msg = f"Weather Agent request timed out: {str(e)}"
            logger.error(error_msg)
            return {
                "status": "error",
                "response": "Weather service is currently unavailable (timeout)"
            }
            
        except httpx.HTTPStatusError as e:
            error_msg = f"Weather Agent returned error status {e.response.status_code}"
            logger.error(error_msg)
            return {
                "status": "error",
                "response": f"Weather service error: {e.response.status_code}"
            }
            
        except Exception as e:
            error_msg = f"Failed to call Weather Agent: {str(e)}"
            logger.error(error_msg)
            return {
                "status": "error",
                "response": "Weather service is currently unavailable"
            }

    async def chat(self, message: str) -> str:
        """Process a natural language message through the Strands agent.
        
        This method allows users to interact with the agent using natural language.
        The agent will automatically determine which tools to use based on the message.
        
        Args:
            message: Natural language message from the user
            
        Returns:
            Agent's response as a string
            
        Example:
            >>> agent = summitassistant()
            >>> await agent.initialize()
            >>> response = await agent.chat("Schedule a meeting tomorrow at 2pm with alice@example.com")
            >>> print(response)
        """
        logger.info(f"Processing chat message: {message[:100]}...")
        
        # Call the Strands agent
        result = self.agent(message)
        
        # Extract the response text from AgentResult
        response_text = ""
        
        # AgentResult has a __str__ method that returns the response text
        if hasattr(result, '__str__'):
            response_text = str(result)
        
        # Fallback: try to extract from message attribute
        if not response_text and hasattr(result, 'message'):
            message_obj = result.message
            if isinstance(message_obj, dict):
                # Try common dict keys
                for key in ['content', 'text', 'response']:
                    if key in message_obj:
                        response_text = message_obj[key]
                        break
            elif isinstance(message_obj, str):
                response_text = message_obj
        
        logger.info(f"Extracted response text: {response_text[:200] if response_text else 'EMPTY'}")
        
        if not response_text:
            response_text = "I'm sorry, I couldn't process that request."
        
        # Update session state
        await self._update_session_state(
            user_message=message,
            assistant_message=response_text
        )
        
        return response_text
