"""Unit tests for authorization header redaction in logs

This module contains comprehensive tests to ensure that Authorization headers
are properly redacted in logs while maintaining other debug information.
Uses mock requests to verify the behavior.
"""

import pytest
import asyncio
import aiohttp
import logging
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Dict, Any, List
from io import StringIO
from aioresponses import aioresponses

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.crafty_api import CraftyAPI, redact_authorization


class TestAuthorizationRedaction:
    """Test cases for authorization header redaction functionality"""

    def test_redact_authorization_with_auth_header(self):
        """Test redaction of Authorization header"""
        headers = {
            'Authorization': 'Bearer secret-token-123',
            'Content-Type': 'application/json',
            'User-Agent': 'CraftyAPI/1.0'
        }
        
        redacted = asyncio.run(redact_authorization(headers))
        
        assert redacted['Authorization'] == 'REDACTED'
        assert redacted['Content-Type'] == 'application/json'
        assert redacted['User-Agent'] == 'CraftyAPI/1.0'
        # Ensure original dict is not modified
        assert headers['Authorization'] == 'Bearer secret-token-123'

    def test_redact_authorization_without_auth_header(self):
        """Test redaction when no Authorization header is present"""
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'CraftyAPI/1.0',
            'X-Custom-Header': 'custom-value'
        }
        
        redacted = asyncio.run(redact_authorization(headers))
        
        assert redacted == headers
        assert 'Authorization' not in redacted
        assert redacted['Content-Type'] == 'application/json'
        assert redacted['User-Agent'] == 'CraftyAPI/1.0'
        assert redacted['X-Custom-Header'] == 'custom-value'

    def test_redact_authorization_empty_headers(self):
        """Test redaction with empty headers dict"""
        headers = {}
        
        redacted = asyncio.run(redact_authorization(headers))
        
        assert redacted == {}
        assert 'Authorization' not in redacted

    def test_redact_authorization_case_sensitivity(self):
        """Test that redaction is case-sensitive for Authorization header"""
        headers = {
            'authorization': 'Bearer secret-token-123',  # lowercase
            'Authorization': 'Bearer another-secret',    # proper case
            'AUTHORIZATION': 'Bearer third-secret',      # uppercase
            'Content-Type': 'application/json'
        }
        
        redacted = asyncio.run(redact_authorization(headers))
        
        # Only 'Authorization' (proper case) should be redacted
        assert redacted['Authorization'] == 'REDACTED'
        assert redacted['authorization'] == 'Bearer secret-token-123'
        assert redacted['AUTHORIZATION'] == 'Bearer third-secret'
        assert redacted['Content-Type'] == 'application/json'

    def test_redact_authorization_preserves_original(self):
        """Test that original headers dict is not modified"""
        original_headers = {
            'Authorization': 'Bearer secret-token-123',
            'Content-Type': 'application/json'
        }
        
        # Keep reference to original Authorization value
        original_auth = original_headers['Authorization']
        
        redacted = asyncio.run(redact_authorization(original_headers))
        
        # Original should be unchanged
        assert original_headers['Authorization'] == original_auth
        assert original_headers['Authorization'] == 'Bearer secret-token-123'
        
        # Redacted should be different
        assert redacted['Authorization'] == 'REDACTED'


class TestLoggingRedaction:
    """Test cases for logging redaction in actual API requests"""

    @pytest.fixture
    def api_client(self):
        """Fixture to create CraftyAPI instance"""
        return CraftyAPI("http://localhost:8443", "test_token_12345")

    @pytest.fixture
    def mock_logger(self):
        """Fixture to create a mock logger for capturing log messages"""
        logger = logging.getLogger('utils.crafty_api')
        # Create a string buffer to capture log output
        log_buffer = StringIO()
        handler = logging.StreamHandler(log_buffer)
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        
        # Store original handlers to restore later
        original_handlers = logger.handlers[:-1]
        
        yield logger, log_buffer
        
        # Restore original handlers
        logger.handlers = original_handlers

    @pytest.mark.asyncio
    async def test_trace_config_redacts_auth_header(self, api_client):
        """Test that trace configuration redacts Authorization header in logs"""
        # This test uses a real API call to verify trace configuration works
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"status": "ok", "data": {}})
        
        captured_prints = []
        
        def capture_print(*args, **kwargs):
            captured_prints.append(args[0] if args else "")
        
        with patch('builtins.print', side_effect=capture_print), \
             patch('aiohttp.ClientSession.request') as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            async with api_client as api:
                # Make a real API call which will trigger trace callbacks
                await api.get_server_info("f1bf6997-9f43-4f36-b06f-9d3daefc7a8a")
                
                # Find the headers print call
                headers_calls = [p for p in captured_prints if p.startswith("Headers:")]
                assert len(headers_calls) >= 1
                
                headers_call = headers_calls[0]
                assert 'REDACTED' in headers_call
                assert 'test_token_12345' not in headers_call
                assert 'Content-Type' in headers_call
                assert 'application/json' in headers_call

    @pytest.mark.asyncio
    async def test_make_request_logs_redacted_headers(self, api_client, mock_logger):
        """Test that _make_request logs redacted headers"""
        logger, log_buffer = mock_logger
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"status": "ok", "data": {"test": "data"}})
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            async with api_client as api:
                await api._make_request("GET", "/servers/f1bf6997-9f43-4f36-b06f-9d3daefc7a8a/stats")
                
                # Get log output
                log_output = log_buffer.getvalue()
                
                # Check that Authorization header is redacted in logs
                assert 'Authorization' in log_output
                assert 'REDACTED' in log_output or 'test_token_12345' not in log_output
                assert 'Content-Type' in log_output
                assert 'application/json' in log_output

    @pytest.mark.asyncio
    async def test_multiple_requests_consistent_redaction(self, api_client):
        """Test that multiple requests consistently redact Authorization headers"""
        captured_prints = []
        
        def capture_print(*args, **kwargs):
            captured_prints.append(args[0] if args else "")
        
        # Mock successful responses
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"status": "ok", "data": {}})
        
        with patch('builtins.print', side_effect=capture_print), \
             patch('aiohttp.ClientSession.request') as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            async with api_client as api:
                # Make multiple actual API calls
                server_id = "f1bf6997-9f43-4f36-b06f-9d3daefc7a8a"
                await api.get_server_stats(server_id)
                await api.get_server_info(server_id)
                await api.start_server(server_id)
                
                # Check all captured prints
                headers_prints = [p for p in captured_prints if p.startswith("Headers:")]
                
                # Should have 3 headers prints, one for each request
                assert len(headers_prints) >= 3
                
                # All should have redacted Authorization headers
                for print_msg in headers_prints:
                    assert 'REDACTED' in print_msg
                    assert 'test_token_12345' not in print_msg
                    assert 'Content-Type' in print_msg
                    assert 'application/json' in print_msg

    @pytest.mark.asyncio
    async def test_server_operations_redact_auth_headers(self, api_client):
        """Test that server operations properly redact Authorization headers"""
        server_id = "f1bf6997-9f43-4f36-b06f-9d3daefc7a8a"
        captured_prints = []
        
        def capture_print(*args, **kwargs):
            captured_prints.append(args[0] if args else "")
        
        # Mock successful responses
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"status": "ok", "data": {}})
        
        with patch('builtins.print', side_effect=capture_print), \
             patch('aiohttp.ClientSession.request') as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            async with api_client as api:
                # Test various server operations
                await api.start_server(server_id)
                await api.stop_server(server_id)
                await api.restart_server(server_id)
                await api.get_server_stats(server_id)
                await api.get_server_info(server_id)
                
                # Check that all requests redacted Authorization headers
                headers_prints = [p for p in captured_prints if p.startswith("Headers:")]
                
                # Should have prints for all operations
                assert len(headers_prints) >= 5
                
                # All should have redacted Authorization headers
                for print_msg in headers_prints:
                    assert 'REDACTED' in print_msg
                    assert 'test_token_12345' not in print_msg

    @pytest.mark.asyncio
    async def test_debug_info_preserved_with_redaction(self, api_client):
        """Test that debug information is preserved while Authorization is redacted"""
        captured_prints = []
        
        def capture_print(*args, **kwargs):
            captured_prints.append(args[0] if args else "")
        
        # Mock successful responses
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"status": "ok", "data": {}})
        
        with patch('builtins.print', side_effect=capture_print), \
             patch('aiohttp.ClientSession.request') as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            async with api_client as api:
                # Make a real API call to trigger trace callbacks
                await api.get_server_stats("f1bf6997-9f43-4f36-b06f-9d3daefc7a8a")
                
                # Check prints
                all_prints = captured_prints
                
                # Should have URL and headers info
                url_prints = [p for p in all_prints if "Starting request to" in p]
                headers_prints = [p for p in all_prints if p.startswith("Headers:")]
                end_prints = [p for p in all_prints if "ended with status" in p]
                
                assert len(url_prints) >= 1
                assert len(headers_prints) >= 1
                assert len(end_prints) >= 1
                
                # Check that URL info is preserved
                url_print = url_prints[0]
                assert "http://localhost:8443/api/v2/servers/f1bf6997-9f43-4f36-b06f-9d3daefc7a8a/stats" in url_print
                
                # Check that headers are redacted but other info preserved
                headers_print = headers_prints[0]
                assert 'REDACTED' in headers_print
                assert 'test_token_12345' not in headers_print
                assert 'Content-Type' in headers_print
                assert 'application/json' in headers_print
                
                # Check that response info is preserved
                end_print = end_prints[0]
                assert "ended with status 200" in end_print

    @pytest.mark.asyncio
    async def test_concurrent_requests_redaction(self, api_client):
        """Test that concurrent requests all have proper Authorization redaction"""
        server_id = "f1bf6997-9f43-4f36-b06f-9d3daefc7a8a"
        captured_prints = []
        
        def capture_print(*args, **kwargs):
            captured_prints.append(args[0] if args else "")
        
        # Mock successful responses
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"status": "ok", "data": {}})
        
        with patch('builtins.print', side_effect=capture_print), \
             patch('aiohttp.ClientSession.request') as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            async with api_client as api:
                # Run multiple concurrent requests
                tasks = [
                    api.start_server(server_id),
                    api.stop_server(server_id),
                    api.get_server_stats(server_id),
                    api.get_server_info(server_id),
                    api.restart_server(server_id)
                ]
                
                await asyncio.gather(*tasks)
                
                # Check that all requests redacted Authorization headers
                headers_prints = [p for p in captured_prints if p.startswith("Headers:")]
                
                # Should have prints for all concurrent operations
                assert len(headers_prints) >= 5
                
                # All should have redacted Authorization headers
                for print_msg in headers_prints:
                    assert 'REDACTED' in print_msg
                    assert 'test_token_12345' not in print_msg
                    # Should still have other debug info
                    assert 'Content-Type' in print_msg or 'application/json' in print_msg

    def test_redaction_performance(self):
        """Test that redaction doesn't significantly impact performance"""
        import time
        
        # Create a large headers dict
        headers = {
            'Authorization': 'Bearer ' + 'x' * 1000,  # Long token
            **{f'X-Custom-Header-{i}': f'value-{i}' for i in range(100)}
        }
        
        # Time the redaction
        start_time = time.time()
        for _ in range(1000):
            asyncio.run(redact_authorization(headers))
        end_time = time.time()
        
        # Should complete quickly (less than 1 second for 1000 operations)
        duration = end_time - start_time
        assert duration < 1.0, f"Redaction took too long: {duration:.3f} seconds"
        
        # Verify correctness wasn't sacrificed for performance
        redacted = asyncio.run(redact_authorization(headers))
        assert redacted['Authorization'] == 'REDACTED'
        assert len(redacted) == len(headers)


class TestEdgeCases:
    """Test edge cases for authorization redaction"""
    
    def test_redaction_with_none_values(self):
        """Test redaction with None values in headers"""
        headers = {
            'Authorization': 'Bearer secret-token',
            'Content-Type': None,
            'X-Null-Header': None
        }
        
        redacted = asyncio.run(redact_authorization(headers))
        
        assert redacted['Authorization'] == 'REDACTED'
        assert redacted['Content-Type'] is None
        assert redacted['X-Null-Header'] is None

    def test_redaction_with_empty_auth_value(self):
        """Test redaction with empty Authorization value"""
        headers = {
            'Authorization': '',
            'Content-Type': 'application/json'
        }
        
        redacted = asyncio.run(redact_authorization(headers))
        
        assert redacted['Authorization'] == 'REDACTED'
        assert redacted['Content-Type'] == 'application/json'

    def test_redaction_with_special_characters(self):
        """Test redaction with special characters in header values"""
        headers = {
            'Authorization': 'Bearer token-with-special-chars!@#$%^&*()',
            'Content-Type': 'application/json; charset=utf-8',
            'X-Special': 'value with spaces and "quotes"'
        }
        
        redacted = asyncio.run(redact_authorization(headers))
        
        assert redacted['Authorization'] == 'REDACTED'
        assert redacted['Content-Type'] == 'application/json; charset=utf-8'
        assert redacted['X-Special'] == 'value with spaces and "quotes"'

    def test_redaction_thread_safety(self):
        """Test that redaction is thread-safe"""
        import threading
        import concurrent.futures
        
        headers = {
            'Authorization': 'Bearer secret-token',
            'Content-Type': 'application/json'
        }
        
        def redact_in_thread():
            return asyncio.run(redact_authorization(headers))
        
        # Run redaction in multiple threads
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(redact_in_thread) for _ in range(50)]
            results = [future.result() for future in futures]
        
        # All results should be consistent
        for result in results:
            assert result['Authorization'] == 'REDACTED'
            assert result['Content-Type'] == 'application/json'
            assert 'secret-token' not in str(result)
