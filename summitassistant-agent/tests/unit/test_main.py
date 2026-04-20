"""Unit tests for main.py CLI."""

import os
from unittest.mock import patch, MagicMock
import pytest
from click.testing import CliRunner

from summitassistant.main import cli, load_config, setup_logging


def test_cli_help():
    """Test that CLI help command works."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    
    assert result.exit_code == 0
    assert "summitassistant" in result.output
    assert "start" in result.output
    assert "init-mock-data" in result.output


def test_version_command():
    """Test version command displays version info."""
    runner = CliRunner()
    result = runner.invoke(cli, ["version"])
    
    assert result.exit_code == 0
    assert "summitassistant v1.0.0" in result.output
    assert "AWS London Summit 2026" in result.output


def test_config_command():
    """Test config command displays configuration."""
    runner = CliRunner()
    result = runner.invoke(cli, ["config"])
    
    assert result.exit_code == 0
    assert "Current Configuration:" in result.output
    assert "AWS Bedrock:" in result.output
    assert "S3 Storage:" in result.output
    assert "MCP Server:" in result.output


def test_load_config_defaults():
    """Test load_config returns default values when env vars not set."""
    # Clear environment variables
    env_vars = [
        "BEDROCK_MODEL", "AWS_REGION", "LLM_MAX_TOKENS",
        "S3_BUCKET_NAME", "S3_REGION", "S3_ENDPOINT_URL",
        "MCP_SERVER_URL", "SESSION_TIMEOUT", "MAX_RETRIES", "RETRY_BASE_DELAY",
        "HOST", "PORT"
    ]
    
    with patch.dict(os.environ, {}, clear=True):
        config = load_config()
        
        assert config["bedrock_model"] == "us.anthropic.claude-sonnet-4-20250514-v1:0"
        assert config["aws_region"] == "us-east-1"
        assert config["llm_max_tokens"] == 500
        assert config["s3_bucket_name"] == "summitassistant-demo-bucket"
        assert config["s3_region"] == "us-east-2"
        assert config["s3_endpoint_url"] is None
        assert config["mcp_server_url"] == "http://mcp-server:8080"
        assert config["session_timeout"] == 3600
        assert config["max_retries"] == 3
        assert config["retry_base_delay"] == 1.0
        assert config["host"] == "0.0.0.0"
        assert config["port"] == 8080


def test_load_config_from_env():
    """Test load_config reads from environment variables."""
    env_vars = {
        "BEDROCK_MODEL": "anthropic.claude-3-opus-20240229-v1:0",
        "AWS_REGION": "us-west-2",
        "LLM_MAX_TOKENS": "1000",
        "S3_BUCKET_NAME": "custom-bucket",
        "S3_REGION": "us-west-2",
        "S3_ENDPOINT_URL": "http://localhost:4566",
        "MCP_SERVER_URL": "http://custom-mcp:9090",
        "SESSION_TIMEOUT": "7200",
        "MAX_RETRIES": "5",
        "RETRY_BASE_DELAY": "2.0",
        "HOST": "127.0.0.1",
        "PORT": "9000"
    }
    
    with patch.dict(os.environ, env_vars):
        config = load_config()
        
        assert config["bedrock_model"] == "anthropic.claude-3-opus-20240229-v1:0"
        assert config["aws_region"] == "us-west-2"
        assert config["llm_max_tokens"] == 1000
        assert config["s3_bucket_name"] == "custom-bucket"
        assert config["s3_region"] == "us-west-2"
        assert config["s3_endpoint_url"] == "http://localhost:4566"
        assert config["mcp_server_url"] == "http://custom-mcp:9090"
        assert config["session_timeout"] == 7200
        assert config["max_retries"] == 5
        assert config["retry_base_delay"] == 2.0
        assert config["host"] == "127.0.0.1"
        assert config["port"] == 9000


def test_setup_logging():
    """Test setup_logging configures logging correctly."""
    import logging
    
    # Reset logging configuration
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
        setup_logging()
        
        logger = logging.getLogger()
        
        # Verify log level is set
        assert logger.level == logging.DEBUG


def test_start_command_help():
    """Test start command help displays options."""
    runner = CliRunner()
    result = runner.invoke(cli, ["start", "--help"])
    
    assert result.exit_code == 0
    assert "Start the summitassistant agent server" in result.output
    assert "--host" in result.output
    assert "--port" in result.output


def test_init_mock_data_command_help():
    """Test init-mock-data command help."""
    runner = CliRunner()
    result = runner.invoke(cli, ["init-mock-data", "--help"])
    
    assert result.exit_code == 0
    assert "Initialize mock meeting data" in result.output
