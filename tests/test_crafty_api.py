"""Unit tests for CraftyAPI class

This module contains comprehensive unit tests for the CraftyAPI class
and its associated data structures, covering all public methods and
error conditions.
"""

import pytest
import asyncio
import aiohttp
from unittest.mock import Mock, patch, AsyncMock
from dataclasses import dataclass
from typing import Dict, Any, Optional
from aioresponses import aioresponses

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.crafty_api import (
    CraftyAPI,
    ApiResponse,
    ServerStats,
    CraftyAPIError,
    CraftyAPIConnectionError,
    CraftyAPITimeoutError,
    CraftyAPIResponseError
)


class TestServerStats:
    """Test cases for ServerStats dataclass"""

    def test_server_stats_creation(self):
        """Test creation of ServerStats object"""
        stats = ServerStats(
            server_id="f1bf6997-9f43-4f36-b06f-9d3daefc7a8a",
            server_name="Test Server",
            running=True,
            cpu=15.5,
            memory="512MB",
            mem_percent=25.0,
            online_players=5,
            max_players=20,
            version="1.20.1",
            world_name="Test World",
            world_size="100MB",
            started="2023-01-01 12:00:00",
            crashed=False,
            updating=False
        )
        
        assert stats.server_id == "f1bf6997-9f43-4f36-b06f-9d3daefc7a8a"
        assert stats.server_name == "Test Server"
        assert stats.running is True
        assert abs(stats.cpu - 15.5) < 0.01
        assert stats.memory == "512MB"
        assert abs(stats.mem_percent - 25.0) < 0.01
        assert stats.online_players == 5
        assert stats.max_players == 20
        assert stats.version == "1.20.1"
        assert stats.world_name == "Test World"
        assert stats.world_size == "100MB"
        assert stats.started == "2023-01-01 12:00:00"
        assert stats.crashed is False
        assert stats.updating is False


class TestApiResponse:
    """Test cases for ApiResponse dataclass"""

    def test_api_response_creation_success(self):
        """Test creation of successful ApiResponse"""
        response = ApiResponse(
            success=True,
            message="Operation successful",
            data={"key": "value"}
        )
        
        assert response.success is True
        assert response.message == "Operation successful"
        assert response.data == {"key": "value"}
        assert response.error_code is None

    def test_api_response_creation_failure(self):
        """Test creation of failed ApiResponse"""
        response = ApiResponse(
            success=False,
            message="Operation failed",
            error_code=400
        )
        
        assert response.success is False
        assert response.message == "Operation failed"
        assert response.data is None
        assert response.error_code == 400


class TestCraftyAPIExceptions:
    """Test cases for CraftyAPI custom exceptions"""

    def test_crafty_api_error_base(self):
        """Test base CraftyAPIError exception"""
        error = CraftyAPIError("Test error", 500)
        assert str(error) == "Test error"
        assert error.status_code == 500

    def test_crafty_api_connection_error(self):
        """Test CraftyAPIConnectionError exception"""
        error = CraftyAPIConnectionError("Connection failed", 503)
        assert str(error) == "Connection failed"
        assert error.status_code == 503
        assert isinstance(error, CraftyAPIError)

    def test_crafty_api_timeout_error(self):
        """Test CraftyAPITimeoutError exception"""
        error = CraftyAPITimeoutError("Request timeout", 408)
        assert str(error) == "Request timeout"
        assert error.status_code == 408
        assert isinstance(error, CraftyAPIError)

    def test_crafty_api_response_error(self):
        """Test CraftyAPIResponseError exception"""
        error = CraftyAPIResponseError("Bad response", 400)
        assert str(error) == "Bad response"
        assert error.status_code == 400
        assert isinstance(error, CraftyAPIError)


class TestCraftyAPI:
    """Test cases for CraftyAPI class"""

    @pytest.fixture
    def api_client(self):
        """Fixture to create CraftyAPI instance"""
        return CraftyAPI("http://localhost:8443", "test_token")

    def test_init(self, api_client):
        """Test CraftyAPI initialization"""
        assert api_client.base_url == "http://localhost:8443"
        assert api_client.token == "test_token"
        assert api_client.session is None

    def test_init_strips_trailing_slash(self):
        """Test that base_url trailing slash is stripped"""
        api = CraftyAPI("http://localhost:8443/", "test_token")
        assert api.base_url == "http://localhost:8443"

    @pytest.mark.asyncio
    async def test_context_manager_entry(self, api_client):
        """Test async context manager entry"""
        async with api_client as api:
            assert api.session is not None
            assert isinstance(api.session, aiohttp.ClientSession)

    @pytest.mark.asyncio
    async def test_context_manager_exit(self, api_client):
        """Test async context manager exit"""
        async with api_client as api:
            session = api.session
            
        # Session should be closed after exiting context
        assert session.closed

    @pytest.mark.asyncio
    async def test_make_request_no_session(self, api_client):
        """Test _make_request without initialized session"""
        with pytest.raises(CraftyAPIConnectionError) as exc_info:
            await api_client._make_request("GET", "/test")
        assert "API session not initialized" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_make_request_success(self, api_client):
        """Test successful _make_request"""
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"status": "ok", "data": {"test": "data"}})
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            async with api_client as api:
                response = await api._make_request("GET", "/test")
                
                assert response.success is True
                assert response.message == "Request successful"
                assert response.data == {"test": "data"}

    @pytest.mark.asyncio
    async def test_make_request_api_error(self, api_client):
        """Test _make_request with API error response"""
        mock_response = Mock()
        mock_response.status = 400
        mock_response.reason = "Bad Request"
        mock_response.json = AsyncMock(return_value={"error": "Invalid request"})
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            async with api_client as api:
                with pytest.raises(CraftyAPIResponseError) as exc_info:
                    await api._make_request("GET", "/test")
                
                assert "API request failed: Invalid request" in str(exc_info.value)
                assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_make_request_connection_error(self, api_client):
        """Test _make_request with connection error"""
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_request.side_effect = aiohttp.ClientError("Connection failed")
            
            async with api_client as api:
                with pytest.raises(CraftyAPIConnectionError) as exc_info:
                    await api._make_request("GET", "/test")
                
                assert "Connection error: Connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_make_request_timeout_error(self, api_client):
        """Test _make_request with timeout error"""
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_request.side_effect = asyncio.TimeoutError()
            
            async with api_client as api:
                with pytest.raises(CraftyAPITimeoutError) as exc_info:
                    await api._make_request("GET", "/test")
                
                assert "Request timeout" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_start_server_success(self, api_client):
        """Test successful server start"""
        test_server_id = "f1bf6997-9f43-4f36-b06f-9d3daefc7a8a"
        with aioresponses() as m:
            m.post(f"http://localhost:8443/api/v2/servers/{test_server_id}/action/start_server", status=200, payload={"status": "ok", "data": {}})
            
            async with api_client as api:
                response = await api.start_server(test_server_id)
                
                assert response.success is True
                assert f"Server {test_server_id} start command sent successfully" in response.message

    @pytest.mark.asyncio
    async def test_start_server_failure(self, api_client):
        """Test failed server start"""
        test_server_id = "f1bf6997-9f43-4f36-b06f-9d3daefc7a8a"
        with patch.object(api_client, '_make_request') as mock_request:
            mock_request.side_effect = CraftyAPIResponseError("Server not found", 404)
            
            async with api_client as api:
                response = await api.start_server(test_server_id)
                
                assert response.success is False
                assert f"Failed to start server {test_server_id}" in response.message
                assert response.error_code == 404

    @pytest.mark.asyncio
    async def test_stop_server_success(self, api_client):
        """Test successful server stop"""
        with patch.object(api_client, '_make_request') as mock_request:
            mock_request.return_value = ApiResponse(success=True, message="OK")
            
            async with api_client as api:
                response = await api.stop_server("f1bf6997-9f43-4f36-b06f-9d3daefc7a8a")
                
                assert response.success is True
                assert "Server f1bf6997-9f43-4f36-b06f-9d3daefc7a8a stop command sent successfully" in response.message
                mock_request.assert_called_once_with("POST", "/servers/f1bf6997-9f43-4f36-b06f-9d3daefc7a8a/action/stop_server")

    @pytest.mark.asyncio
    async def test_stop_server_failure(self, api_client):
        """Test failed server stop"""
        with patch.object(api_client, '_make_request') as mock_request:
            mock_request.side_effect = CraftyAPIResponseError("Server not found", 404)
            
            async with api_client as api:
                response = await api.stop_server("test-server-1")
                
                assert response.success is False
                assert "Failed to stop server test-server-1" in response.message
                assert response.error_code == 404

    @pytest.mark.asyncio
    async def test_restart_server_success(self, api_client):
        """Test successful server restart"""
        with patch.object(api_client, '_make_request') as mock_request:
            mock_request.return_value = ApiResponse(success=True, message="OK")
            
            async with api_client as api:
                response = await api.restart_server("test-server-1")
                
                assert response.success is True
                assert "Server test-server-1 restart command sent successfully" in response.message
                mock_request.assert_called_once_with("POST", "/servers/test-server-1/action/restart_server")

    @pytest.mark.asyncio
    async def test_restart_server_failure(self, api_client):
        """Test failed server restart"""
        with patch.object(api_client, '_make_request') as mock_request:
            mock_request.side_effect = CraftyAPIResponseError("Server not found", 404)
            
            async with api_client as api:
                response = await api.restart_server("test-server-1")
                
                assert response.success is False
                assert "Failed to restart server test-server-1" in response.message
                assert response.error_code == 404

    @pytest.mark.asyncio
    async def test_kill_server_success(self, api_client):
        """Test successful server kill"""
        with patch.object(api_client, '_make_request') as mock_request:
            mock_request.return_value = ApiResponse(success=True, message="OK")
            
            async with api_client as api:
                response = await api.kill_server("test-server-1")
                
                assert response.success is True
                assert "Server test-server-1 force kill command sent successfully" in response.message
                mock_request.assert_called_once_with("POST", "/servers/test-server-1/action/kill_server")

    @pytest.mark.asyncio
    async def test_kill_server_failure(self, api_client):
        """Test failed server kill"""
        with patch.object(api_client, '_make_request') as mock_request:
            mock_request.side_effect = CraftyAPIResponseError("Server not found", 404)
            
            async with api_client as api:
                response = await api.kill_server("test-server-1")
                
                assert response.success is False
                assert "Failed to kill server test-server-1" in response.message
                assert response.error_code == 404

    @pytest.mark.asyncio
    async def test_get_server_stats_with_realistic_crafty_response(self, api_client):
        """Test ServerStats construction with realistic Crafty Controller /stats response"""
        test_server_id = "f1bf6997-9f43-4f36-b06f-9d3daefc7a8a"
        
        # Mock JSON response imitating actual Crafty Controller /stats endpoint
        mock_stats_data = {
            "stats_id": 457,
            "created": "2022-05-25T18:47:41.814015",
            "server_id": {
                "server_id": test_server_id,
                "created": "2022-05-25T01:24:22.427327",
                "server_uuid": "6079f8b1-d690-4974-9c0d-792480307a86",
                "server_name": "Minecraft Production Server",
                "path": "/home/crafty/servers/6079f8b1-d690-4974-9c0d-792480307a86",
                "backup_path": "/home/crafty/backups/6079f8b1-d690-4974-9c0d-792480307a86",
                "executable": "paper-1.19.4.jar",
                "log_path": "/home/crafty/servers/6079f8b1-d690-4974-9c0d-792480307a86/logs/latest.log",
                "execution_command": "java -Xms2000M -Xmx4000M -jar paper-1.19.4.jar nogui",
                "auto_start": True,
                "auto_start_delay": 10,
                "crash_detection": True,
                "stop_command": "stop",
                "executable_update_url": "",
                "server_ip": "0.0.0.0",
                "server_port": 25565,
                "logs_delete_after": 0,
                "type": "minecraft-java"
            },
            "started": "2023-12-01 14:30:15",
            "running": True,
            "cpu": 23.7,
            "mem": "2.8GB",
            "mem_percent": 35.2,
            "world_name": "survival_world",
            "world_size": "1.2GB",
            "server_port": 25565,
            "int_ping_results": "True",
            "online": 12,
            "max": 50,
            "players": "[{\"name\": \"Steve\"}, {\"name\": \"Alex\"}]",
            "desc": "A Minecraft Server",
            "version": "Paper 1.19.4",
            "updating": False,
            "waiting_start": False,
            "first_run": False,
            "crashed": False,
            "downloading": False
        }
        
        with patch.object(api_client, '_make_request') as mock_request:
            mock_request.return_value = ApiResponse(
                success=True,
                message="OK",
                data=mock_stats_data
            )
            
            async with api_client as api:
                response = await api.get_server_stats(test_server_id)
                
                # Assert correct ServerStats construction
                assert response.success is True
                assert isinstance(response.data, ServerStats)
                
                # Test all ServerStats fields are correctly populated
                stats = response.data
                assert stats.server_id == test_server_id
                assert stats.server_name == "Minecraft Production Server"
                assert stats.running is True
                assert abs(stats.cpu - 23.7) < 0.01
                assert stats.memory == "2.8GB"
                assert abs(stats.mem_percent - 35.2) < 0.01
                assert stats.online_players == 12
                assert stats.max_players == 50
                assert stats.version == "Paper 1.19.4"
                assert stats.world_name == "survival_world"
                assert stats.world_size == "1.2GB"
                assert stats.started == "2023-12-01 14:30:15"
                assert stats.crashed is False
                assert stats.updating is False
                
                # Verify the correct API endpoint was called
                mock_request.assert_called_once_with("GET", f"/servers/{test_server_id}/stats")

    @pytest.mark.asyncio
    async def test_get_server_stats_success(self, api_client):
        """Test successful server stats retrieval"""
        test_server_id = "f1bf6997-9f43-4f36-b06f-9d3daefc7a8a"
        mock_stats_data = {
            "server_id": {"server_id": test_server_id, "server_name": "Test Server"},
            "running": True,
            "cpu": 15.5,
            "mem": "512MB",
            "mem_percent": 25.0,
            "online": 5,
            "max": 20,
            "version": "1.20.1",
            "world_name": "Test World",
            "world_size": "100MB",
            "started": "2023-01-01 12:00:00",
            "crashed": False,
            "updating": False
        }
        
        with patch.object(api_client, '_make_request') as mock_request:
            mock_request.return_value = ApiResponse(
                success=True,
                message="OK",
                data=mock_stats_data
            )
            
            async with api_client as api:
                response = await api.get_server_stats(test_server_id)
                
                assert response.success is True
                assert isinstance(response.data, ServerStats)
                assert response.data.server_id == test_server_id
                assert response.data.server_name == "Test Server"
                assert response.data.running is True
                assert abs(response.data.cpu - 15.5) < 0.01
                mock_request.assert_called_once_with("GET", f"/servers/{test_server_id}/stats")

    @pytest.mark.asyncio
    async def test_get_server_stats_parsing_error(self, api_client):
        """Test server stats with missing fields uses defaults"""
        mock_stats_data = {"invalid": "data"}
        
        with patch.object(api_client, '_make_request') as mock_request:
            mock_request.return_value = ApiResponse(
                success=True,
                message="OK",
                data=mock_stats_data
            )
            
            async with api_client as api:
                response = await api.get_server_stats("test-server-1")
                
                assert response.success is True
                assert isinstance(response.data, ServerStats)
                # Check that defaults were used for missing fields
                assert response.data.server_name == "Unknown"
                assert response.data.running is False
                assert abs(response.data.cpu - 0.0) < 0.01
                assert response.data.version == "Unknown"

    @pytest.mark.asyncio
    async def test_get_server_stats_failure(self, api_client):
        """Test failed server stats retrieval"""
        with patch.object(api_client, '_make_request') as mock_request:
            mock_request.side_effect = CraftyAPIResponseError("Server not found", 404)
            
            async with api_client as api:
                response = await api.get_server_stats("test-server-1")
                
                assert response.success is False
                assert "Failed to get server stats for test-server-1" in response.message
                assert response.error_code == 404


class TestCraftyAPIWithAioresponses:
    """Test CraftyAPI with aioresponses for HTTP mocking"""

    @pytest.fixture
    def api_client(self):
        """Fixture to create CraftyAPI instance"""
        return CraftyAPI("http://localhost:8443", "test_token")

    @pytest.mark.asyncio
    async def test_get_server_stats_with_aioresponses(self, api_client):
        """Test server stats retrieval with aioresponses"""
        mock_stats_data = {
            "status": "ok",
            "data": {
                "server_id": {"server_id": 1, "server_name": "Test Server"},
                "running": True,
                "cpu": 15.5,
                "mem": "512MB",
                "mem_percent": 25.0,
                "online": 5,
                "max": 20,
                "version": "1.20.1",
                "world_name": "Test World",
                "world_size": "100MB",
                "started": "2023-01-01 12:00:00",
                "crashed": False,
                "updating": False
            }
        }
        
        with aioresponses() as m:
            m.get("http://localhost:8443/api/v2/servers/1/stats", payload=mock_stats_data)
            
            async with api_client as api:
                response = await api.get_server_stats(1)
                
                assert response.success is True
                assert isinstance(response.data, ServerStats)
                assert response.data.server_id == 1
                assert response.data.server_name == "Test Server"
                assert response.data.running is True
                assert abs(response.data.cpu - 15.5) < 0.01

    @pytest.mark.asyncio
    async def test_stop_server_with_aioresponses(self, api_client):
        """Test server stop with aioresponses"""
        with aioresponses() as m:
            m.post("http://localhost:8443/api/v2/servers/1/action/stop_server", status=200, payload={"status": "ok", "data": {}})
            
            async with api_client as api:
                response = await api.stop_server(1)
                
                assert response.success is True
                assert "Server 1 stop command sent successfully" in response.message

    @pytest.mark.asyncio
    async def test_server_not_found_with_aioresponses(self, api_client):
        """Test server not found error with aioresponses"""
        with aioresponses() as m:
            m.post("http://localhost:8443/api/v2/servers/999/action/start_server", status=404, payload={"error": "Server not found"})
            
            async with api_client as api:
                response = await api.start_server(999)
                
                assert response.success is False
                assert "Failed to start server 999" in response.message
                assert response.error_code == 404

    @pytest.mark.asyncio
    async def test_multiple_operations_workflow(self, api_client):
        """Test multiple operations in sequence"""
        with aioresponses() as m:
            # Mock status check
            m.get("http://localhost:8443/api/v2/servers/1/stats", payload={
                "status": "ok",
                "data": {
                    "server_id": {"server_id": 1, "server_name": "Test Server"},
                    "running": False,
                    "cpu": 0.0,
                    "mem": "0MB",
                    "mem_percent": 0.0,
                    "online": 0,
                    "max": 20,
                    "version": "1.20.1",
                    "world_name": "Test World",
                    "world_size": "100MB",
                    "started": "Unknown",
                    "crashed": False,
                    "updating": False
                }
            })
            
            # Mock start server
            m.post("http://localhost:8443/api/v2/servers/1/action/start_server", payload={"status": "ok", "data": {}})
            
            # Mock second status check
            m.get("http://localhost:8443/api/v2/servers/1/stats", payload={
                "status": "ok",
                "data": {
                    "server_id": {"server_id": 1, "server_name": "Test Server"},
                    "running": True,
                    "cpu": 15.5,
                    "mem": "512MB",
                    "mem_percent": 25.0,
                    "online": 5,
                    "max": 20,
                    "version": "1.20.1",
                    "world_name": "Test World",
                    "world_size": "100MB",
                    "started": "2023-01-01 12:00:00",
                    "crashed": False,
                    "updating": False
                }
            })
            
            async with api_client as api:
                # Check initial status
                status_response = await api.get_server_stats(1)
                assert status_response.success is True
                assert status_response.data.running is False
                
                # Start server
                start_response = await api.start_server(1)
                assert start_response.success is True
                
                # Check status again
                status_response2 = await api.get_server_stats(1)
                assert status_response2.success is True
                assert status_response2.data.running is True


class TestCraftyAPIIntegration:
    """Integration tests for CraftyAPI class"""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test a complete workflow with multiple operations"""
        # This would be expanded with actual integration tests
        # when connecting to a real Crafty Controller instance
        pass

    @pytest.mark.asyncio
    async def test_error_handling_workflow(self):
        """Test error handling in complex workflows"""
        # This would test error recovery and handling
        # across multiple API operations
        pass


if __name__ == "__main__":
    pytest.main([__file__])
