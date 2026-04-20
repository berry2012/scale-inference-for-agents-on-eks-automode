#!/usr/bin/env python3
"""Main entry point and CLI for summitassistant agent.

This module provides the command-line interface for running the summitassistant
agent with support for:
- Starting the agent server
- Initializing mock data for demos
- Graceful shutdown with session state persistence
"""

import asyncio
import logging
import os
import signal
import sys
from typing import Optional

import click
from uvicorn import Config, Server

from summitassistant.agent import summitassistant
from summitassistant.storage_manager import StorageManager
from summitassistant.llm_client import LLMServiceClient
from summitassistant.calendar_manager import MCPServerClient
from summitassistant.retry_manager import RetryManager


# Global agent instance for signal handlers
_agent_instance: Optional[summitassistant] = None
_shutdown_event = asyncio.Event()


def setup_logging() -> None:
    """Set up structured logging with JSON format."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "component": "%(name)s", "message": "%(message)s"}',
        datefmt="%Y-%m-%dT%H:%M:%S%z"
    )
    
    # Set specific log levels for noisy libraries
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def load_config() -> dict:
    """Load configuration from environment variables.
    
    Returns:
        Dictionary with configuration values
    """
    config = {
        # AWS Bedrock Configuration
        "bedrock_model": os.getenv("BEDROCK_MODEL", "us.anthropic.claude-sonnet-4-20250514-v1:0"),
        "aws_region": os.getenv("AWS_REGION", "us-east-1"),
        "llm_max_tokens": int(os.getenv("LLM_MAX_TOKENS", "500")),
        
        # S3 Storage Configuration
        "s3_bucket_name": os.getenv("S3_BUCKET_NAME", "summitassistant-demo-bucket"),
        "s3_region": os.getenv("S3_REGION", "us-east-1"),
        "s3_endpoint_url": os.getenv("S3_ENDPOINT_URL"),  # Optional, for local dev
        
        # MCP Server Configuration
        "mcp_server_url": os.getenv("MCP_SERVER_URL", "http://mcp-server:8080"),
        
        # Agent Configuration
        "session_timeout": int(os.getenv("SESSION_TIMEOUT", "3600")),
        "max_retries": int(os.getenv("MAX_RETRIES", "3")),
        "retry_base_delay": float(os.getenv("RETRY_BASE_DELAY", "1.0")),
        
        # Server Configuration
        "host": os.getenv("HOST", "0.0.0.0"),
        "port": int(os.getenv("PORT", "8080")),
    }
    
    return config


async def initialize_agent(config: dict) -> summitassistant:
    """Initialize summitassistant agent with configuration.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Initialized summitassistant instance
    """
    logger = logging.getLogger(__name__)
    logger.info("Initializing summitassistant agent")
    
    # Initialize retry manager
    retry_manager = RetryManager(
        max_retries=config["max_retries"],
        base_delay=config["retry_base_delay"]
    )
    
    # Initialize storage manager
    storage_manager = StorageManager(
        bucket_name=config["s3_bucket_name"],
        region=config["s3_region"],
        endpoint_url=config["s3_endpoint_url"],
        retry_manager=retry_manager
    )
    
    # Initialize LLM client for Bedrock
    llm_client = LLMServiceClient(
        model=config["bedrock_model"],
        region=config["aws_region"],
        retry_manager=retry_manager
    )
    
    # Initialize MCP client
    mcp_client = MCPServerClient(
        server_url=config["mcp_server_url"]
    )
    
    # Create agent instance with AWS Bedrock
    # Use the same model for both agent orchestration and summarization
    agent = summitassistant(
        storage_manager=storage_manager,
        llm_client=llm_client,
        mcp_client=mcp_client,
        retry_manager=retry_manager,
        model=config["bedrock_model"]
    )
    
    # Initialize agent (load session state)
    await agent.initialize()
    
    logger.info(f"summitassistant agent initialized with session_id={agent.session_id}")
    
    return agent


async def shutdown_handler(sig: signal.Signals) -> None:
    """Handle shutdown signals gracefully.
    
    Args:
        sig: Signal that triggered shutdown
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Received signal {sig.name}, initiating graceful shutdown")
    
    # Save session state if agent is initialized
    if _agent_instance and _agent_instance.session_state:
        try:
            logger.info("Saving session state before shutdown")
            await _agent_instance.storage_manager.save_session_state(
                _agent_instance.session_id,
                _agent_instance.session_state
            )
            logger.info("Session state saved successfully")
        except Exception as e:
            logger.error(f"Failed to save session state during shutdown: {e}")
    
    # Signal shutdown
    _shutdown_event.set()


def setup_signal_handlers() -> None:
    """Set up signal handlers for graceful shutdown."""
    loop = asyncio.get_event_loop()
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(shutdown_handler(s))
        )


@click.group()
def cli():
    """summitassistant - AI-powered meeting management agent."""
    setup_logging()


@cli.command()
@click.option("--host", default=None, help="Host to bind to (default: 0.0.0.0)")
@click.option("--port", default=None, type=int, help="Port to bind to (default: 8080)")
def start(host: Optional[str], port: Optional[int]):
    """Start the summitassistant agent server.
    
    The agent will:
    - Load configuration from environment variables
    - Initialize all service clients (S3, LLM, MCP)
    - Load or create session state
    - Start HTTP server for agent interactions
    - Handle graceful shutdown on SIGTERM/SIGINT
    """
    logger = logging.getLogger(__name__)
    logger.info("Starting summitassistant agent")
    
    # Load configuration
    config = load_config()
    
    # Override with CLI arguments if provided
    if host:
        config["host"] = host
    if port:
        config["port"] = port
    
    logger.info(f"Configuration loaded: Bedrock Model={config['bedrock_model']}, "
                f"AWS Region={config['aws_region']}, S3={config['s3_bucket_name']}, MCP={config['mcp_server_url']}")
    
    async def run_agent():
        """Run the agent with graceful shutdown support."""
        global _agent_instance
        
        try:
            # Initialize agent
            _agent_instance = await initialize_agent(config)
            
            # Set up signal handlers
            setup_signal_handlers()
            
            # Start HTTP server with health checks
            from aiohttp import web
            
            async def health_check(request):
                """Health check endpoint for liveness probe."""
                return web.json_response({"status": "healthy"})
            
            async def readiness_check(request):
                """Readiness check endpoint for readiness probe."""
                if _agent_instance and _agent_instance.session_state:
                    return web.json_response({"status": "ready"})
                return web.Response(status=503, text="Not ready")
            
            async def chat_endpoint(request):
                """Chat endpoint for user interactions."""
                try:
                    data = await request.json()
                    message = data.get("message", "")
                    
                    if not message:
                        return web.json_response({"error": "message is required"}, status=400)
                    
                    # Process message with agent
                    response = await _agent_instance.chat(message)
                    
                    return web.json_response({"response": response})
                except Exception as e:
                    logger.error(f"Error processing chat message: {e}")
                    return web.json_response({"error": str(e)}, status=500)
            
            app = web.Application()
            app.router.add_get('/health', health_check)
            app.router.add_get('/ready', readiness_check)
            app.router.add_post('/chat', chat_endpoint)
            
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, config['host'], config['port'])
            
            logger.info(f"Agent server starting on {config['host']}:{config['port']}")
            logger.info("Press Ctrl+C to stop")
            
            await site.start()
            
            # Keep running until shutdown signal
            while not _shutdown_event.is_set():
                await asyncio.sleep(1)
            
            # Cleanup
            await runner.cleanup()
            logger.info("Shutdown complete")
            
        except Exception as e:
            logger.error(f"Agent failed to start: {e}", exc_info=True)
            sys.exit(1)
    
    # Run the agent
    try:
        asyncio.run(run_agent())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


@cli.command()
def init_mock_data():
    """Initialize mock meeting data for demos.
    
    This command:
    - Creates 5 mock meeting notes with realistic content
    - Uploads them to S3 storage
    - Spans a date range of at least 30 days in the past
    - Is idempotent (skips if data already exists)
    """
    logger = logging.getLogger(__name__)
    logger.info("Initializing mock meeting data")
    
    # Import here to avoid circular dependencies
    from scripts.initialize_mock_data import initialize_mock_data
    
    try:
        asyncio.run(initialize_mock_data())
        logger.info("Mock data initialization completed successfully")
    except Exception as e:
        logger.error(f"Mock data initialization failed: {e}", exc_info=True)
        sys.exit(1)


@cli.command()
def version():
    """Display version information."""
    click.echo("summitassistant v1.0.0")
    click.echo("AI-powered meeting management agent for AWS London Summit 2026 demo")


@cli.command()
def config():
    """Display current configuration."""
    config_dict = load_config()
    
    click.echo("Current Configuration:")
    click.echo("-" * 50)
    
    # Group by category
    click.echo("\nAWS Bedrock:")
    click.echo(f"  Model: {config_dict['bedrock_model']}")
    click.echo(f"  Region: {config_dict['aws_region']}")
    click.echo(f"  Max Tokens: {config_dict['llm_max_tokens']}")
    
    click.echo("\nS3 Storage:")
    click.echo(f"  Bucket: {config_dict['s3_bucket_name']}")
    click.echo(f"  Region: {config_dict['s3_region']}")
    if config_dict['s3_endpoint_url']:
        click.echo(f"  Endpoint: {config_dict['s3_endpoint_url']}")
    
    click.echo("\nMCP Server:")
    click.echo(f"  URL: {config_dict['mcp_server_url']}")
    
    click.echo("\nAgent:")
    click.echo(f"  Session Timeout: {config_dict['session_timeout']}s")
    click.echo(f"  Max Retries: {config_dict['max_retries']}")
    click.echo(f"  Retry Base Delay: {config_dict['retry_base_delay']}s")
    
    click.echo("\nServer:")
    click.echo(f"  Host: {config_dict['host']}")
    click.echo(f"  Port: {config_dict['port']}")


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
