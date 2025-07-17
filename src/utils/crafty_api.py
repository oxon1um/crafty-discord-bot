"""Crafty Controller API client

Provides an async wrapper for interacting with the Crafty Controller API.
Handles authentication, connection management, and provides convenient methods
for server management operations.
"""

import aiohttp
import asyncio
import logging
from typing import Dict, Any, Optional, Union, List, TYPE_CHECKING, NewType
from dataclasses import dataclass
from datetime import datetime

try:
    from typing import Annotated, Literal, TypeAlias
except ImportError:
    from typing_extensions import Annotated, Literal, TypeAlias  # type: ignore

logger = logging.getLogger(__name__)

# Type aliases for better readability
UUIDStr = NewType("UUIDStr", str)
ServerID: TypeAlias = Annotated[str, "Server ID must be a UUID-like string"]
MemorySize: TypeAlias = Annotated[str, "Memory size in MB format"]
CPUUsage: TypeAlias = Annotated[float, "CPU usage as percentage"]
PlayerCount: TypeAlias = Annotated[int, "Number of players"]
MemoryPercent: TypeAlias = Annotated[float, "Memory usage percentage"]

# HTTP method literals
HttpMethod: TypeAlias = Literal["GET", "POST", "PUT", "DELETE", "PATCH"]

# Response data union type
ResponseData: TypeAlias = Union[Dict[str, Any], "ServerStats", None]


class CraftyAPIError(Exception):
    """Base exception for Crafty API errors"""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class CraftyAPIConnectionError(CraftyAPIError):
    """Exception raised when connection to Crafty API fails"""
    pass


class CraftyAPITimeoutError(CraftyAPIError):
    """Exception raised when request to Crafty API times out"""
    pass


class CraftyAPIResponseError(CraftyAPIError):
    """Exception raised when Crafty API returns non-200 response"""
    pass


@dataclass
class ServerStats:
    """Data class for server statistics"""
    server_id: ServerID
    server_name: str
    running: bool
    cpu: CPUUsage
    memory: MemorySize
    mem_percent: MemoryPercent
    online_players: PlayerCount
    max_players: PlayerCount
    version: str
    world_name: str
    world_size: MemorySize
    started: str
    crashed: bool
    updating: bool


@dataclass
class ApiResponse:
    """Data class for API responses"""
    success: bool
    message: str
    data: Optional[Union[Dict[str, Any], ServerStats]] = None
    error_code: Optional[int] = None


class CraftyAPI:
    """Async wrapper for Crafty Controller API
    
    This class provides an async interface to the Crafty Controller API,
    managing HTTP sessions and providing convenient methods for server operations.
    
    Usage:
        async with CraftyAPI(base_url, token) as api:
            response = await api.start_server(server_id)
            stats = await api.get_server_stats(server_id)
    """
    
    def __init__(self, base_url: str, token: str) -> None:
        """Initialize the Crafty API client
        
        Args:
            base_url: The base URL of the Crafty Controller instance
            token: The API token for authentication
        """
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self) -> 'CraftyAPI':
        """Async context manager entry"""
        async def on_request_start(session, trace_config_ctx, params):
            print(f"Starting request to {params.url}")
            print(f"Headers: {params.headers}")

        async def on_request_end(session, trace_config_ctx, params):
            print(f"Request to {params.url} ended with status {params.response.status}")

        trace_config = aiohttp.TraceConfig()
        trace_config.on_request_start.append(on_request_start)
        trace_config.on_request_end.append(on_request_end)

        connector = aiohttp.TCPConnector(limit=10, ssl=False)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(sock_connect=5, sock_read=25),
            trace_configs=[trace_config]
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> ApiResponse:
        """Make authenticated request to Crafty Controller API
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            **kwargs: Additional arguments for aiohttp request
            
        Returns:
            ApiResponse object with success status and data
            
        Raises:
            CraftyAPIConnectionError: If connection fails
            CraftyAPITimeoutError: If request times out
            CraftyAPIResponseError: If API returns non-200 status
        """
        if not self.session:
            raise CraftyAPIConnectionError("API session not initialized")
        
        headers = {
            "Authorization": f"Bearer {self.token}",  # Standard format
            "Content-Type": "application/json"
        }
        url = f"{self.base_url}/api/v2{endpoint}"
        
        logger.debug(f"Making {method} request to {url}")
        logger.debug(f"Headers: {headers}")
        if self.session.connector:
            logger.debug(f"Connector connections: {self.session.connector._conns}")
        
        try:
            start_time = asyncio.get_event_loop().time()
            async with self.session.request(method, url, headers=headers, **kwargs) as response:
                end_time = asyncio.get_event_loop().time()
                latency = end_time - start_time
                logger.info(f"Request to {url} took {latency:.2f} seconds.")
                try:
                    response_data = await response.json()
                except aiohttp.ContentTypeError:
                    response_data = {}
                
                if response.status == 200 and response_data.get('status') == 'ok':
                    return ApiResponse(
                        success=True,
                        message="Request successful",
                        data=response_data.get('data')
                    )
                else:
                    error_message = response_data.get('error', f"HTTP {response.status}: {response.reason}")
                    raise CraftyAPIResponseError(
                        f"API request failed: {error_message}",
                        response.status
                    )
                    
        except aiohttp.ClientError as e:
            logger.error(f"Connection error: {e}")
            raise CraftyAPIConnectionError(f"Connection error: {str(e)}")
        except asyncio.TimeoutError:
            logger.error("Request timeout")
            raise CraftyAPITimeoutError("Request timeout")
        except CraftyAPIError:
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise CraftyAPIError(f"Unexpected error: {str(e)}")
    
    async def start_server(self, server_id: str) -> ApiResponse:
        """Start a server
        
        Args:
            server_id: The UUID string of the server to start
            
        Returns:
            ApiResponse indicating success or failure
            
        Raises:
            CraftyAPIError: If the request fails
        """
        try:
            response = await self._make_request("POST", f"/servers/{server_id}/action/start_server")
            response.message = f"Server {server_id} start command sent successfully"
            return response
        except CraftyAPIError as e:
            return ApiResponse(
                success=False,
                message=f"Failed to start server {server_id}: {str(e)}",
                error_code=e.status_code
            )
    
    async def stop_server(self, server_id: str) -> ApiResponse:
        """Stop a server
        
        Args:
            server_id: The UUID string of the server to stop
            
        Returns:
            ApiResponse indicating success or failure
            
        Raises:
            CraftyAPIError: If the request fails
        """
        try:
            response = await self._make_request("POST", f"/servers/{server_id}/action/stop_server")
            response.message = f"Server {server_id} stop command sent successfully"
            return response
        except CraftyAPIError as e:
            return ApiResponse(
                success=False,
                message=f"Failed to stop server {server_id}: {str(e)}",
                error_code=e.status_code
            )
    
    async def restart_server(self, server_id: str) -> ApiResponse:
        """Restart a server
        
        Args:
            server_id: The UUID string of the server to restart
            
        Returns:
            ApiResponse indicating success or failure
            
        Raises:
            CraftyAPIError: If the request fails
        """
        try:
            response = await self._make_request("POST", f"/servers/{server_id}/action/restart_server")
            response.message = f"Server {server_id} restart command sent successfully"
            return response
        except CraftyAPIError as e:
            return ApiResponse(
                success=False,
                message=f"Failed to restart server {server_id}: {str(e)}",
                error_code=e.status_code
            )
    
    async def kill_server(self, server_id: str) -> ApiResponse:
        """Force kill a server
        
        Args:
            server_id: The UUID string of the server to kill
            
        Returns:
            ApiResponse indicating success or failure
            
        Raises:
            CraftyAPIError: If the request fails
        """
        try:
            response = await self._make_request("POST", f"/servers/{server_id}/action/kill_server")
            response.message = f"Server {server_id} force kill command sent successfully"
            return response
        except CraftyAPIError as e:
            return ApiResponse(
                success=False,
                message=f"Failed to kill server {server_id}: {str(e)}",
                error_code=e.status_code
            )
    
    async def get_server_info(self, server_id: str) -> ApiResponse:
        """Get basic server information
        
        Args:
            server_id: The UUID string of the server to get info for
            
        Returns:
            ApiResponse containing server information
            
        Raises:
            CraftyAPIError: If the request fails
        """
        try:
            response = await self._make_request("GET", f"/servers/{server_id}")
            response.message = f"Server {server_id} information retrieved successfully"
            return response
        except CraftyAPIError as e:
            return ApiResponse(
                success=False,
                message=f"Failed to get server info for {server_id}: {str(e)}",
                error_code=e.status_code
            )
    
    async def get_server_stats(self, server_id: str) -> ApiResponse:
        """Get server statistics and status via the /stats endpoint
        
        This method calls the Crafty Controller API's /servers/{server_id}/stats endpoint
        to retrieve comprehensive server statistics including CPU usage, memory usage,
        player counts, and server status information.
        
        Args:
            server_id: The UUID string of the server to get stats for
            
        Returns:
            ApiResponse containing ServerStats object or error info
            
        Raises:
            CraftyAPIError: If the request fails
        """
        try:
            # Use the correct API endpoint for server statistics
            logger.debug(f"Requesting stats for server {server_id} from /servers/{server_id}/stats")
            response = await self._make_request("GET", f"/servers/{server_id}/stats")
            
            if response.success and response.data and isinstance(response.data, dict):
                stats_data: Dict[str, Any] = response.data
                try:
                    # Parse the server stats from the API response
                    logger.debug(f"Successfully retrieved stats data for server {server_id}")
                    logger.debug(f"Raw stats data keys: {list(stats_data.keys())}")
                    
                    # Extract server name from the data
                    server_info = stats_data.get('server_id', {})
                    server_name = server_info.get('server_name', 'Unknown') if isinstance(server_info, dict) else 'Unknown'
                    
                    # Parse server status information with safe casting
                    running = bool(stats_data.get('running', False))
                    
                    # Safe float casting with defaults
                    try:
                        cpu = float(stats_data.get('cpu', 0.0))
                    except (ValueError, TypeError):
                        cpu = 0.0
                    
                    try:
                        mem_percent = float(stats_data.get('mem_percent', 0.0))
                    except (ValueError, TypeError):
                        mem_percent = 0.0
                    
                    # Memory is a string format like "1.6GB"
                    memory = str(stats_data.get('mem', '0MB'))
                    
                    # Safe int casting with defaults for player counts
                    try:
                        online_players = int(stats_data.get('online', 0))
                    except (ValueError, TypeError):
                        online_players = 0
                    
                    try:
                        max_players = int(stats_data.get('max', 0))
                    except (ValueError, TypeError):
                        max_players = 0
                    
                    # Parse version and other info with safe defaults
                    version = str(stats_data.get('version', 'Unknown'))
                    world_name = str(stats_data.get('world_name', 'world'))
                    world_size = str(stats_data.get('world_size', '0MB'))
                    started = str(stats_data.get('started', 'Unknown'))
                    crashed = bool(stats_data.get('crashed', False))
                    updating = bool(stats_data.get('updating', False))
                    
                    server_stats = ServerStats(
                        server_id=server_id,
                        server_name=server_name,
                        running=running,
                        cpu=cpu,
                        memory=memory,
                        mem_percent=mem_percent,
                        online_players=online_players,
                        max_players=max_players,
                        version=version,
                        world_name=world_name,
                        world_size=world_size,
                        started=started,
                        crashed=crashed,
                        updating=updating
                    )
                    
                    response.data = server_stats
                    response.message = f"Server {server_id} statistics retrieved successfully"
                    logger.debug(f"Successfully parsed server stats for {server_id}: {server_name}")
                    
                except Exception as e:
                    logger.error(f"Error parsing server stats: {e}")
                    logger.error(f"Raw response data: {stats_data}")
                    return ApiResponse(
                        success=False,
                        message=f"Error parsing server statistics: {str(e)}",
                        error_code=500
                    )
            
            return response
            
        except CraftyAPIError as e:
            return ApiResponse(
                success=False,
                message=f"Failed to get server stats for {server_id}: {str(e)}",
                error_code=e.status_code
            )
    
    async def send_stdin_command(self, server_id: str, command: str) -> ApiResponse:
        """Send a command to a server's stdin
        
        Args:
            server_id: The UUID string of the server to send the command to
            command: The command to send
            
        Returns:
            ApiResponse indicating success or failure
            
        Raises:
            CraftyAPIError: If the request fails
        """
        try:
            # According to the API docs, the request body should be just the command text
            response = await self._make_request(
                "POST", 
                f"/servers/{server_id}/stdin", 
                data=command.encode('utf-8'),
                headers={'Content-Type': 'text/plain'}
            )
            response.message = f"Command '{command}' sent to server {server_id} successfully"
            return response
        except CraftyAPIError as e:
            return ApiResponse(
                success=False,
                message=f"Failed to send command to server {server_id}: {str(e)}",
                error_code=e.status_code
            )
    
    async def backup_server(self, server_id: str) -> ApiResponse:
        """Backup a server
        
        Args:
            server_id: The UUID string of the server to backup
            
        Returns:
            ApiResponse indicating success or failure
            
        Raises:
            CraftyAPIError: If the request fails
        """
        try:
            response = await self._make_request("POST", f"/servers/{server_id}/action/backup_server")
            response.message = f"Server {server_id} backup command sent successfully"
            return response
        except CraftyAPIError as e:
            return ApiResponse(
                success=False,
                message=f"Failed to backup server {server_id}: {str(e)}",
                error_code=e.status_code
            )


# Export all public classes and functions
__all__ = [
    'CraftyAPI',
    'ApiResponse', 
    'ServerStats',
    'UUIDStr',
    'ServerID',
    'CraftyAPIError',
    'CraftyAPIConnectionError',
    'CraftyAPITimeoutError',
    'CraftyAPIResponseError'
]
