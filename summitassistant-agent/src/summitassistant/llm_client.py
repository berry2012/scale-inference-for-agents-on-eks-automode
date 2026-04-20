"""LLM service client for AWS Bedrock integration."""

import os
import logging
from typing import Optional
import boto3
from botocore.exceptions import ClientError

from .retry_manager import RetryManager

logger = logging.getLogger(__name__)


class LLMServiceError(Exception):
    """Exception raised for LLM service failures."""
    pass


class ValidationError(Exception):
    """Exception raised for validation failures."""
    pass


class LLMServiceClient:
    """Client for AWS Bedrock inference service."""

    def __init__(
        self,
        model: str = "us.anthropic.claude-sonnet-4-20250514-v1:0",
        region: Optional[str] = None,
        retry_manager: Optional[RetryManager] = None
    ):
        """Initialize LLM service client for AWS Bedrock.
        
        Args:
            model: Bedrock model ID to use for inference (defaults to Claude Sonnet 4)
            region: AWS region for Bedrock (defaults to AWS_REGION or us-east-1)
            retry_manager: RetryManager instance for retry logic
        """
        self.model = model
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self.retry_manager = retry_manager or RetryManager()
        
        # Initialize Bedrock Runtime client
        self.bedrock_client = boto3.client(
            service_name='bedrock-runtime',
            region_name=self.region
        )
        
        logger.info(f"LLMServiceClient initialized with Bedrock model={self.model}, region={self.region}")

    async def summarize_meeting_notes(
        self,
        meeting_notes: str,
        max_length: int = 500
    ) -> str:
        """Generate a summary of meeting notes.
        
        Args:
            meeting_notes: Raw meeting notes (max 10000 chars)
            max_length: Maximum summary length in tokens
            
        Returns:
            Summary text
            
        Raises:
            ValidationError: If meeting notes are invalid
            LLMServiceError: On inference failures
            TimeoutError: On request timeout
        """
        # Validate input
        if not meeting_notes or not meeting_notes.strip():
            raise ValidationError("meeting_notes cannot be empty")
        
        if len(meeting_notes) > 10000:
            raise ValidationError("meeting_notes cannot exceed 10000 characters")
        
        # Wrap the actual API call with retry logic
        async def _make_request():
            return await self._call_llm_api(meeting_notes, max_length)
        
        # Retry on TimeoutError and LLMServiceError, but not ValidationError
        try:
            summary = await self.retry_manager.execute_with_retry(
                _make_request,
                (TimeoutError, LLMServiceError)
            )
            return summary
        except (TimeoutError, LLMServiceError) as e:
            logger.error(f"Failed to summarize meeting notes after retries: {e}")
            raise

    async def _call_llm_api(self, meeting_notes: str, max_tokens: int) -> str:
        """Make the actual API call to AWS Bedrock.
        
        Args:
            meeting_notes: Meeting notes to summarize
            max_tokens: Maximum tokens for summary
            
        Returns:
            Summary text
            
        Raises:
            LLMServiceError: On API failures
            TimeoutError: On request timeout
        """
        import json
        import asyncio
        
        # Format prompt for Claude
        prompt = (
            "Summarize the following meeting notes, highlighting key topics, "
            f"decisions, and action items:\n\n{meeting_notes}"
        )
        
        # Prepare request body for Claude on Bedrock
        # Using Anthropic Messages API format
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": 0.3,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        try:
            # Call Bedrock API (synchronous, so wrap in executor)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.bedrock_client.invoke_model(
                    modelId=self.model,
                    body=json.dumps(request_body),
                    contentType="application/json",
                    accept="application/json"
                )
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            
            # Extract summary from Claude response
            if "content" not in response_body or not response_body["content"]:
                raise LLMServiceError("Invalid response format: missing content")
            
            # Claude returns content as array of content blocks
            summary = response_body["content"][0].get("text", "").strip()
            
            # Validate summary is non-empty
            if not summary:
                raise ValidationError("LLM returned empty summary")
            
            logger.info(f"Successfully generated summary ({len(summary)} chars)")
            return summary
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            if error_code == 'ThrottlingException':
                logger.error(f"Bedrock API throttled: {error_message}")
                raise TimeoutError(f"Bedrock API throttled: {error_message}") from e
            else:
                logger.error(f"Bedrock API error ({error_code}): {error_message}")
                raise LLMServiceError(f"Bedrock API error ({error_code}): {error_message}") from e
            
        except (KeyError, IndexError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to parse Bedrock response: {e}")
            raise LLMServiceError(f"Failed to parse Bedrock response: {e}") from e
        
        except Exception as e:
            logger.error(f"Unexpected error calling Bedrock: {e}")
            raise LLMServiceError(f"Unexpected error calling Bedrock: {e}") from e
