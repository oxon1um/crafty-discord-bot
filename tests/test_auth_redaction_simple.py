"""Simple test to verify authorization header redaction works correctly"""

import pytest
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.crafty_api import CraftyAPI, redact_authorization


class TestAuthRedactionSimple:
    """Simple tests to verify the core functionality"""
    
    def test_redact_authorization_function(self):
        """Test the redact_authorization function directly"""
        headers = {
            'Authorization': 'Bearer secret-token-12345',
            'Content-Type': 'application/json',
            'User-Agent': 'Test/1.0'
        }
        
        redacted = asyncio.run(redact_authorization(headers))
        
        # Authorization should be redacted
        assert redacted['Authorization'] == 'REDACTED'
        
        # Other headers should remain unchanged
        assert redacted['Content-Type'] == 'application/json'
        assert redacted['User-Agent'] == 'Test/1.0'
        
        # Original headers should be unchanged
        assert headers['Authorization'] == 'Bearer secret-token-12345'
        
        print("✓ Authorization header redaction works correctly")
    
    def test_redact_authorization_no_auth(self):
        """Test redaction when no Authorization header is present"""
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Test/1.0'
        }
        
        redacted = asyncio.run(redact_authorization(headers))
        
        # Should be identical to original
        assert redacted == headers
        assert 'Authorization' not in redacted
        
        print("✓ Headers without Authorization remain unchanged")
    
    def test_redact_authorization_case_sensitivity(self):
        """Test that redaction is case-sensitive"""
        headers = {
            'authorization': 'Bearer secret-1',  # lowercase
            'Authorization': 'Bearer secret-2',  # proper case
            'AUTHORIZATION': 'Bearer secret-3',  # uppercase
            'Content-Type': 'application/json'
        }
        
        redacted = asyncio.run(redact_authorization(headers))
        
        # Only 'Authorization' (proper case) should be redacted
        assert redacted['Authorization'] == 'REDACTED'
        assert redacted['authorization'] == 'Bearer secret-1'
        assert redacted['AUTHORIZATION'] == 'Bearer secret-3'
        assert redacted['Content-Type'] == 'application/json'
        
        print("✓ Case-sensitive redaction works correctly")
    
    @pytest.mark.asyncio
    async def test_api_logging_redaction(self):
        """Test that the API correctly logs redacted headers"""
        import logging
        from io import StringIO
        from unittest.mock import patch, Mock, AsyncMock
        
        # Set up logging capture
        logger = logging.getLogger('utils.crafty_api')
        log_buffer = StringIO()
        handler = logging.StreamHandler(log_buffer)
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        
        # Mock response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"status": "ok", "data": {}})
        
        api_client = CraftyAPI("http://localhost:8443", "secret-token-12345")
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            async with api_client as api:
                await api.get_server_info("f1bf6997-9f43-4f36-b06f-9d3daefc7a8a")
                
                # Check log output
                log_output = log_buffer.getvalue()
                
                # Should contain redacted authorization
                assert 'Authorization' in log_output
                assert 'REDACTED' in log_output
                
                # Should NOT contain the actual token
                assert 'secret-token-12345' not in log_output
                
                # Should contain other debug info
                assert 'Content-Type' in log_output
                assert 'application/json' in log_output
                
        # Clean up
        logger.removeHandler(handler)
        print("✓ API logging correctly redacts Authorization headers")
    
    def test_performance(self):
        """Test that redaction is fast enough for production use"""
        import time
        
        headers = {
            'Authorization': 'Bearer ' + 'x' * 1000,  # Large token
            'Content-Type': 'application/json',
            'User-Agent': 'Test/1.0',
            'X-Custom-Header': 'custom-value'
        }
        
        # Time 1000 redactions
        start_time = time.time()
        for _ in range(1000):
            asyncio.run(redact_authorization(headers))
        end_time = time.time()
        
        duration = end_time - start_time
        assert duration < 0.5, f"Redaction took too long: {duration:.3f} seconds"
        
        print(f"✓ Performance test passed: 1000 redactions in {duration:.3f} seconds")


if __name__ == '__main__':
    # Run the tests directly
    test = TestAuthRedactionSimple()
    test.test_redact_authorization_function()
    test.test_redact_authorization_no_auth()
    test.test_redact_authorization_case_sensitivity()
    
    # Run async test
    asyncio.run(test.test_api_logging_redaction())
    
    test.test_performance()
    
    print("\n🎉 All authorization redaction tests passed!")
