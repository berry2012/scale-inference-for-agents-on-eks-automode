"""S3 storage operations for meeting notes and session state."""

from typing import Optional, List, Tuple
import logging
import json
import os
import boto3
from botocore.exceptions import ClientError, EndpointConnectionError, ConnectionError as BotocoreConnectionError
from datetime import datetime

from summitassistant.models import MeetingNote, Summary, SessionState
from summitassistant.retry_manager import RetryManager

logger = logging.getLogger(__name__)


class StorageManager:
    """Manages S3 operations for persistent storage."""

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        region: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        retry_manager: Optional[RetryManager] = None
    ):
        """Initialize storage manager.
        
        Args:
            bucket_name: S3 bucket name (defaults to S3_BUCKET_NAME env var)
            region: AWS region (defaults to S3_REGION env var)
            endpoint_url: S3 endpoint URL (defaults to S3_ENDPOINT env var, for LocalStack/MinIO)
            retry_manager: RetryManager instance (creates default if not provided)
        """
        self.bucket_name = bucket_name or os.getenv("S3_BUCKET_NAME")
        self.region = region or os.getenv("S3_REGION", "us-east-1")
        self.endpoint_url = endpoint_url or os.getenv("S3_ENDPOINT")
        self.retry_manager = retry_manager or RetryManager(max_retries=3, base_delay=1.0)
        
        # Initialize boto3 S3 client
        self.s3_client = boto3.client(
            "s3",
            region_name=self.region,
            endpoint_url=self.endpoint_url
        )
        
        logger.info(
            f"StorageManager initialized with bucket: {self.bucket_name}, "
            f"region: {self.region}, endpoint: {self.endpoint_url}"
        )
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Check if an error is retryable.
        
        Args:
            error: Exception to check
            
        Returns:
            True if error should be retried
        """
        # Network errors are retryable
        if isinstance(error, (EndpointConnectionError, BotocoreConnectionError)):
            return True
        
        # Check ClientError status codes
        if isinstance(error, ClientError):
            error_code = error.response.get("Error", {}).get("Code", "")
            status_code = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
            
            # Don't retry on permissions or not found
            if error_code in ["403", "Forbidden", "AccessDenied"]:
                return False
            if error_code in ["404", "NoSuchKey", "NoSuchBucket"]:
                return False
            
            # Retry on 500/503 status codes
            if status_code in [500, 503]:
                return True
        
        return False

    async def save_meeting_note(
        self,
        meeting_id: str,
        note: MeetingNote
    ) -> bool:
        """Save meeting note to S3.
        
        Args:
            meeting_id: Unique meeting identifier
            note: Meeting note to save
            
        Returns:
            True if successful
            
        Raises:
            Exception: On S3 errors
        """
        async def _save_operation():
            key = f"meetings/{meeting_id}/note.json"
            
            try:
                # Serialize note to JSON
                note_json = json.dumps(note.to_json())
                
                # Upload to S3
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=note_json,
                    ContentType="application/json"
                )
                
                logger.info(f"Successfully saved meeting note: {key}")
                return True
                
            except Exception as e:
                if not self._is_retryable_error(e):
                    logger.error(f"Non-retryable error saving meeting note {key}: {e}")
                    raise
                # Re-raise retryable errors for retry manager
                raise
        
        # Execute with retry logic
        return await self.retry_manager.execute_with_retry(
            _save_operation,
            (ClientError, EndpointConnectionError, BotocoreConnectionError)
        )

    async def save_summary(
        self,
        meeting_id: str,
        summary: Summary
    ) -> bool:
        """Save meeting summary to S3.
        
        Args:
            meeting_id: Meeting identifier
            summary: Summary to save
            
        Returns:
            True if successful
            
        Raises:
            Exception: On S3 errors
        """
        async def _save_operation():
            key = f"meetings/{meeting_id}/summary.json"
            
            try:
                # Serialize summary to JSON
                summary_json = json.dumps(summary.to_json())
                
                # Upload to S3
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=summary_json,
                    ContentType="application/json"
                )
                
                logger.info(f"Successfully saved summary: {key}")
                return True
                
            except Exception as e:
                if not self._is_retryable_error(e):
                    logger.error(f"Non-retryable error saving summary {key}: {e}")
                    raise
                raise
        
        return await self.retry_manager.execute_with_retry(
            _save_operation,
            (ClientError, EndpointConnectionError, BotocoreConnectionError)
        )

    async def get_meeting_note(
        self,
        meeting_id: str
    ) -> Optional[MeetingNote]:
        """Retrieve meeting note from S3.
        
        Args:
            meeting_id: Meeting identifier
            
        Returns:
            MeetingNote if found, None otherwise
        """
        async def _get_operation():
            key = f"meetings/{meeting_id}/note.json"
            
            try:
                # Get object from S3
                response = self.s3_client.get_object(
                    Bucket=self.bucket_name,
                    Key=key
                )
                
                # Parse JSON and deserialize
                note_data = json.loads(response["Body"].read())
                note = MeetingNote.from_json(note_data)
                
                logger.info(f"Successfully retrieved meeting note: {key}")
                return note
                
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code == "NoSuchKey":
                    logger.info(f"Meeting note not found: {key}")
                    return None
                if not self._is_retryable_error(e):
                    logger.error(f"Non-retryable error retrieving meeting note {key}: {e}")
                    raise
                raise
        
        return await self.retry_manager.execute_with_retry(
            _get_operation,
            (ClientError, EndpointConnectionError, BotocoreConnectionError)
        )

    async def get_summary(
        self,
        meeting_id: str
    ) -> Optional[Summary]:
        """Retrieve meeting summary from S3.
        
        Args:
            meeting_id: Meeting identifier
            
        Returns:
            Summary if found, None otherwise
        """
        async def _get_operation():
            key = f"meetings/{meeting_id}/summary.json"
            
            try:
                # Get object from S3
                response = self.s3_client.get_object(
                    Bucket=self.bucket_name,
                    Key=key
                )
                
                # Parse JSON and deserialize
                summary_data = json.loads(response["Body"].read())
                summary = Summary.from_json(summary_data)
                
                logger.info(f"Successfully retrieved summary: {key}")
                return summary
                
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code == "NoSuchKey":
                    logger.info(f"Summary not found: {key}")
                    return None
                if not self._is_retryable_error(e):
                    logger.error(f"Non-retryable error retrieving summary {key}: {e}")
                    raise
                raise
        
        return await self.retry_manager.execute_with_retry(
            _get_operation,
            (ClientError, EndpointConnectionError, BotocoreConnectionError)
        )

    async def search_meetings(
        self,
        meeting_id: Optional[str] = None,
        date_range: Optional[Tuple[str, str]] = None,
        attendee: Optional[str] = None,
        limit: int = 10
    ) -> List[MeetingNote]:
        """Search for meetings matching criteria.
        
        Args:
            meeting_id: Specific meeting ID (exact match)
            date_range: Tuple of (start_date, end_date) in ISO format
            attendee: Filter by attendee email (contains match)
            limit: Maximum results (default: 10)
            
        Returns:
            List of matching meeting notes (max 10)
        """
        # If meeting_id is provided, do exact match
        if meeting_id:
            note = await self.get_meeting_note(meeting_id)
            return [note] if note else []
        
        # Otherwise, list all meetings and filter
        async def _search_operation():
            try:
                # List all objects under meetings/ prefix
                paginator = self.s3_client.get_paginator("list_objects_v2")
                pages = paginator.paginate(
                    Bucket=self.bucket_name,
                    Prefix="meetings/"
                )
                
                matching_notes = []
                
                for page in pages:
                    if "Contents" not in page:
                        continue
                        
                    for obj in page["Contents"]:
                        key = obj["Key"]
                        
                        # Only process note.json files
                        if not key.endswith("/note.json"):
                            continue
                        
                        # Extract meeting_id from key
                        parts = key.split("/")
                        if len(parts) < 3:
                            continue
                        current_meeting_id = parts[1]
                        
                        # Retrieve the note
                        note = await self.get_meeting_note(current_meeting_id)
                        if not note:
                            continue
                        
                        # Apply filters
                        if date_range:
                            start_date, end_date = date_range
                            note_date = note.timestamp.isoformat()
                            if not (start_date <= note_date <= end_date):
                                continue
                        
                        if attendee:
                            if attendee not in note.attendees:
                                continue
                        
                        matching_notes.append(note)
                        
                        # Stop if we've reached the limit
                        if len(matching_notes) >= limit:
                            break
                    
                    # Break outer loop if limit reached
                    if len(matching_notes) >= limit:
                        break
                
                logger.info(f"Search found {len(matching_notes)} matching meetings")
                return matching_notes[:limit]
                
            except Exception as e:
                if not self._is_retryable_error(e):
                    logger.error(f"Non-retryable error searching meetings: {e}")
                    raise
                raise
        
        return await self.retry_manager.execute_with_retry(
            _search_operation,
            (ClientError, EndpointConnectionError, BotocoreConnectionError)
        )

    async def save_session_state(
        self,
        session_id: str,
        state: SessionState
    ) -> bool:
        """Save session state to S3.
        
        Args:
            session_id: Session identifier
            state: Session state to save
            
        Returns:
            True if successful
            
        Raises:
            Exception: On S3 errors
        """
        async def _save_operation():
            key = f"sessions/{session_id}/state.json"
            
            try:
                # Serialize state to JSON
                state_json = json.dumps(state.to_json())
                
                # Upload to S3
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=state_json,
                    ContentType="application/json"
                )
                
                logger.info(f"Successfully saved session state: {key}")
                return True
                
            except Exception as e:
                if not self._is_retryable_error(e):
                    logger.error(f"Non-retryable error saving session state {key}: {e}")
                    raise
                raise
        
        return await self.retry_manager.execute_with_retry(
            _save_operation,
            (ClientError, EndpointConnectionError, BotocoreConnectionError)
        )

    async def load_session_state(
        self,
        session_id: str
    ) -> Optional[SessionState]:
        """Load session state from S3.
        
        Args:
            session_id: Session identifier
            
        Returns:
            SessionState if found, None otherwise
        """
        async def _load_operation():
            key = f"sessions/{session_id}/state.json"
            
            try:
                # Get object from S3
                response = self.s3_client.get_object(
                    Bucket=self.bucket_name,
                    Key=key
                )
                
                # Parse JSON and deserialize
                state_data = json.loads(response["Body"].read())
                state = SessionState.from_json(state_data)
                
                logger.info(f"Successfully loaded session state: {key}")
                return state
                
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code == "NoSuchKey":
                    logger.info(f"Session state not found: {key}")
                    return None
                if not self._is_retryable_error(e):
                    logger.error(f"Non-retryable error loading session state {key}: {e}")
                    raise
                raise
        
        return await self.retry_manager.execute_with_retry(
            _load_operation,
            (ClientError, EndpointConnectionError, BotocoreConnectionError)
        )
