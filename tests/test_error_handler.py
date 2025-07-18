#!/usr/bin/env python3
"""
Unit tests for the Discord bot's error handling system.
Tests interaction response handling for various interaction states.
"""

import pytest
import asyncio
import unittest.mock as mock
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import discord
from discord import app_commands
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.bot_commands import on_app_command_error_handler
from utils.discord_utils import can_respond, safe_respond_async, safe_followup_async


class TestInteractionMocking:
    """Test cases for mocking Discord interactions in different states"""
    
    def create_mock_interaction(self, is_expired=False, is_responded=False, interaction_id=None):
        """Create a mock Discord interaction with specified state"""
        interaction = Mock(spec=discord.Interaction)
        interaction.id = interaction_id or 123456789
        interaction.is_expired.return_value = is_expired
        
        # Mock the response object
        response = Mock()
        response.is_done.return_value = is_responded
        response.send_message = AsyncMock()
        interaction.response = response
        
        # Mock the followup object
        followup = Mock()
        followup.send = AsyncMock()
        interaction.followup = followup
        
        return interaction
    
    def test_normal_interaction_can_respond(self):
        """Test that a normal interaction can respond"""
        interaction = self.create_mock_interaction(is_expired=False, is_responded=False)
        
        # Test can_respond function
        assert can_respond(interaction) is True
        
        # Verify calls
        interaction.is_expired.assert_called_once()
        interaction.response.is_done.assert_called_once()
        interaction.response.is_done.assert_called_once()
    
    def test_expired_interaction_cannot_respond(self):
        """Test that an expired interaction cannot respond"""
        interaction = self.create_mock_interaction(is_expired=True, is_responded=False)
        
        # Test can_respond function
        assert can_respond(interaction) is False
        
        # Verify calls
        interaction.is_expired.assert_called_once()
        # is_done should not be called if already expired
        interaction.response.is_done.assert_not_called()
    
    def test_already_responded_interaction_cannot_respond(self):
        """Test that an already responded interaction cannot respond"""
        interaction = self.create_mock_interaction(is_expired=False, is_responded=True)
        
        # Test can_respond function
        assert can_respond(interaction) is False
        
        # Verify calls
        interaction.is_expired.assert_called_once()
        interaction.response.is_done.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_safe_respond_async_normal_flow(self):
        """Test safe_respond_async with a normal interaction"""
        interaction = self.create_mock_interaction(is_expired=False, is_responded=False)
        
        # Test safe_respond_async
        result = await safe_respond_async(interaction, content="Test message", ephemeral=True)
        
        # Verify result and calls
        assert result is True
        interaction.response.send_message.assert_called_once_with(ephemeral=True, content="Test message")
        interaction.followup.send.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_safe_respond_async_expired_interaction(self):
        """Test safe_respond_async with an expired interaction"""
        interaction = self.create_mock_interaction(is_expired=True, is_responded=False)
        
        # Test safe_respond_async
        result = await safe_respond_async(interaction, content="Test message", ephemeral=True)
        
        # Verify result and calls
        assert result is False
        interaction.response.send_message.assert_not_called()
        interaction.followup.send.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_safe_respond_async_already_responded(self):
        """Test safe_respond_async with an already responded interaction"""
        interaction = self.create_mock_interaction(is_expired=False, is_responded=True)
        
        # Test safe_respond_async
        result = await safe_respond_async(interaction, content="Test message", ephemeral=True)
        
        # Verify result and calls
        assert result is False
        interaction.response.send_message.assert_not_called()
        interaction.followup.send.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_safe_followup_async_normal_flow(self):
        """Test safe_followup_async with a normal interaction"""
        interaction = self.create_mock_interaction(is_expired=False, is_responded=True)
        
        # Test safe_followup_async
        result = await safe_followup_async(interaction, content="Test followup", ephemeral=True)
        
        # Verify result and calls
        assert result is True
        interaction.followup.send.assert_called_once_with(ephemeral=True, content="Test followup")
        interaction.response.send_message.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_safe_followup_async_expired_interaction(self):
        """Test safe_followup_async with an expired interaction"""
        interaction = self.create_mock_interaction(is_expired=True, is_responded=True)
        
        # Test safe_followup_async
        result = await safe_followup_async(interaction, content="Test followup", ephemeral=True)
        
        # Verify result and calls
        assert result is False
        interaction.followup.send.assert_not_called()
        interaction.response.send_message.assert_not_called()


class TestErrorHandlerBehavior:
    """Test the error handler's decision-making logic"""
    
    def create_mock_interaction(self, is_expired=False, is_responded=False, interaction_id=None):
        """Create a mock Discord interaction with specified state"""
        interaction = Mock(spec=discord.Interaction)
        interaction.id = interaction_id or 123456789
        interaction.is_expired.return_value = is_expired
        
        # Mock the response object
        response = Mock()
        response.is_done.return_value = is_responded
        response.send_message = AsyncMock()
        interaction.response = response
        
        # Mock the followup object
        followup = Mock()
        followup.send = AsyncMock()
        interaction.followup = followup
        
        return interaction
    
    @pytest.mark.asyncio
    async def test_error_handler_uses_respond_for_fresh_interaction(self):
        """Test that error handler uses respond for fresh interactions"""
        interaction = self.create_mock_interaction(is_expired=False, is_responded=False)
        # Create a mock command
        mock_command = Mock()
        mock_command.name = "test_command"
        error = app_commands.CommandInvokeError(mock_command, ValueError("Test error"))
        
        with patch('utils.bot_commands.safe_respond_async') as mock_respond, \
             patch('utils.bot_commands.safe_followup_async') as mock_followup, \
             patch('utils.bot_commands.can_respond', return_value=True):
            
            await on_app_command_error_handler(interaction, error)
            
            # Verify respond was called, not followup
            mock_respond.assert_called_once()
            mock_followup.assert_not_called()
            
            # Check the error message contains the original error
            args, kwargs = mock_respond.call_args
            assert args[1].startswith("❌ Invalid value:")
            assert kwargs['ephemeral'] is True
    
    @pytest.mark.asyncio
    async def test_error_handler_uses_followup_for_responded_interaction(self):
        """Test that error handler uses followup for already responded interactions"""
        interaction = self.create_mock_interaction(is_expired=False, is_responded=True)
        # Create a mock command
        mock_command = Mock()
        mock_command.name = "test_command"
        error = app_commands.CommandInvokeError(mock_command, ValueError("Test error"))
        
        with patch('utils.bot_commands.safe_respond_async') as mock_respond, \
             patch('utils.bot_commands.safe_followup_async') as mock_followup, \
             patch('utils.bot_commands.can_respond', return_value=False):
            
            await on_app_command_error_handler(interaction, error)
            
            # Verify followup was called, not respond
            mock_followup.assert_called_once()
            mock_respond.assert_not_called()
            
            # Check the error message contains the original error
            args, kwargs = mock_followup.call_args
            assert args[1].startswith("❌ Invalid value:")
            assert kwargs['ephemeral'] is True
    
    @pytest.mark.asyncio
    async def test_error_handler_handles_missing_permissions(self):
        """Test error handler formats MissingPermissions errors correctly"""
        interaction = self.create_mock_interaction(is_expired=False, is_responded=False)
        error = app_commands.MissingPermissions(missing_permissions=["administrator"])
        
        with patch('utils.bot_commands.safe_respond_async') as mock_respond, \
             patch('utils.bot_commands.can_respond', return_value=True):
            
            await on_app_command_error_handler(interaction, error)
            
            # Verify the specific error message for permissions
            args, kwargs = mock_respond.call_args
            assert args[1] == "❌ You don't have permission to use this command."
            assert kwargs['ephemeral'] is True
    
    @pytest.mark.asyncio
    async def test_error_handler_handles_cooldown_errors(self):
        """Test error handler formats CommandOnCooldown errors correctly"""
        interaction = self.create_mock_interaction(is_expired=False, is_responded=False)
        error = app_commands.CommandOnCooldown(cooldown=None, retry_after=45.5)
        
        with patch('utils.bot_commands.safe_respond_async') as mock_respond, \
             patch('utils.bot_commands.can_respond', return_value=True):
            
            await on_app_command_error_handler(interaction, error)
            
            # Verify the specific error message for cooldown
            args, kwargs = mock_respond.call_args
            assert "❌ Command is on cooldown. Try again in 45.50 seconds." in args[1]
            assert kwargs['ephemeral'] is True
    
    @pytest.mark.asyncio
    async def test_error_handler_handles_transformer_errors(self):
        """Test error handler formats TransformerError correctly"""
        interaction = self.create_mock_interaction(is_expired=False, is_responded=False)
        # Create a mock transformer
        mock_transformer = Mock()
        mock_transformer._error_display_name = "test_transformer"
        error = app_commands.TransformerError("invalid", str, mock_transformer)
        
        with patch('utils.bot_commands.safe_respond_async') as mock_respond, \
             patch('utils.bot_commands.can_respond', return_value=True):
            
            await on_app_command_error_handler(interaction, error)
            
            # Verify the specific error message for transformer
            args, kwargs = mock_respond.call_args
            assert args[1] == "❌ Invalid argument provided. Please check your input."
            assert kwargs['ephemeral'] is True
    
    @pytest.mark.asyncio
    async def test_error_handler_handles_secondary_errors(self):
        """Test error handler gracefully handles secondary errors"""
        interaction = self.create_mock_interaction(is_expired=False, is_responded=False)
        error = ValueError("Primary error")
        
        # Mock safe_respond_async to raise an exception
        with patch('utils.bot_commands.safe_respond_async', side_effect=discord.HTTPException(mock.Mock(), "Secondary error")) as mock_respond, \
             patch('utils.bot_commands.can_respond', return_value=True), \
             patch('utils.bot_commands.logger') as mock_logger:
            
            await on_app_command_error_handler(interaction, error)
            
            # Verify that secondary error handling was attempted
            mock_respond.assert_called()
            mock_logger.error.assert_called()
            
            # Check that the secondary error was logged
            error_calls = [call for call in mock_logger.error.call_args_list if "Secondary error" in str(call)]
            assert len(error_calls) > 0
    
    @pytest.mark.asyncio
    async def test_error_handler_truncates_long_messages(self):
        """Test error handler truncates very long error messages"""
        interaction = self.create_mock_interaction(is_expired=False, is_responded=False)
        long_error_message = "A" * 3000  # Create a very long error message
        error = RuntimeError(long_error_message)
        
        with patch('utils.bot_commands.safe_respond_async') as mock_respond, \
             patch('utils.bot_commands.can_respond', return_value=True):
            
            await on_app_command_error_handler(interaction, error)
            
            # Verify the message was truncated
            args, kwargs = mock_respond.call_args
            assert len(args[1]) < 2000
            assert args[1] == "❌ An unexpected error occurred. Please try again later."
            assert kwargs['ephemeral'] is True


class TestDiscordErrorSimulation:
    """Test error scenarios that simulate Discord API errors"""
    
    def create_mock_interaction(self, is_expired=False, is_responded=False, interaction_id=None):
        """Create a mock Discord interaction with specified state"""
        interaction = Mock(spec=discord.Interaction)
        interaction.id = interaction_id or 123456789
        interaction.is_expired.return_value = is_expired
        
        # Mock the response object
        response = Mock()
        response.is_done.return_value = is_responded
        response.send_message = AsyncMock()
        interaction.response = response
        
        # Mock the followup object
        followup = Mock()
        followup.send = AsyncMock()
        interaction.followup = followup
        
        return interaction
    
    @pytest.mark.asyncio
    async def test_safe_respond_handles_40060_error(self):
        """Test safe_respond_async handles 40060 (interaction already acknowledged) error"""
        interaction = self.create_mock_interaction(is_expired=False, is_responded=False)
        
        # Mock the response to raise InteractionResponded error (40060)
        interaction.response.send_message.side_effect = discord.InteractionResponded(interaction=interaction)
        
        with patch('utils.discord_utils.logger') as mock_logger:
            result = await safe_respond_async(interaction, content="Test message")
            
            # Verify error was handled gracefully
            assert result is True
            mock_logger.warning.assert_called()
            
            # Check that the specific error was logged
            warning_calls = [call for call in mock_logger.warning.call_args_list 
                          if "InteractionResponded" in str(call)]
            assert len(warning_calls) > 0
    
    @pytest.mark.asyncio
    async def test_safe_respond_handles_10062_error(self):
        """Test safe_respond_async handles 10062 (unknown interaction) error"""
        interaction = self.create_mock_interaction(is_expired=False, is_responded=False)
        
        # Mock the response to raise NotFound error (10062)
        response_mock = AsyncMock()
        response_mock.status = 404
        interaction.response.send_message.side_effect = discord.NotFound(response_mock, 'Unknown interaction')
        
        with patch('utils.discord_utils.logger') as mock_logger:
            result = await safe_respond_async(interaction, content="Test message")
            
            # Verify error was handled gracefully
            assert result is False
            mock_logger.warning.assert_called()
            
            # Check that the specific error was logged
            warning_calls = [call for call in mock_logger.warning.call_args_list 
                          if "NotFound" in str(call)]
            assert len(warning_calls) > 0
    
    @pytest.mark.asyncio
    async def test_safe_followup_handles_10062_error(self):
        """Test safe_followup_async handles 10062 (unknown interaction) error"""
        interaction = self.create_mock_interaction(is_expired=False, is_responded=True)
        
        # Mock the followup to raise NotFound error (10062)
        response_mock = AsyncMock()
        response_mock.status = 404
        interaction.followup.send.side_effect = discord.NotFound(response_mock, 'Unknown interaction')
        
        with patch('utils.discord_utils.logger') as mock_logger:
            result = await safe_followup_async(interaction, content="Test followup")
            
            # Verify error was handled gracefully
            assert result is False
            mock_logger.warning.assert_called()
            
            # Check that the specific error was logged
            warning_calls = [call for call in mock_logger.warning.call_args_list 
                          if "NotFound" in str(call)]
            assert len(warning_calls) > 0
    
    @pytest.mark.asyncio
    async def test_safe_followup_handles_expired_interaction(self):
        """Test safe_followup_async handles expired interactions"""
        interaction = self.create_mock_interaction(is_expired=True, is_responded=True)
        
        with patch('utils.discord_utils.logger') as mock_logger:
            result = await safe_followup_async(interaction, content="Test followup")
            
            # Verify error was handled gracefully
            assert result is False
            mock_logger.warning.assert_called_with("Skipping followup to expired interaction", extra={
                'interaction_id': interaction.id,
                'interaction_type': interaction.type.name,
                'user_id': interaction.user.id,
                'guild_id': interaction.guild.id,
                'channel_id': interaction.channel.id,
                'command_name': interaction.command.name,
                'skip_reason': 'interaction_expired'
            })
    
    @pytest.mark.asyncio
    async def test_comprehensive_error_flow(self):
        """Test comprehensive error flow covering all decision points"""
        interaction = self.create_mock_interaction(is_expired=False, is_responded=False)
        error = ValueError("Test error")
        
        # First, test normal respond path
        with patch('utils.bot_commands.safe_respond_async', return_value=True) as mock_respond, \
             patch('utils.bot_commands.can_respond', return_value=True):
            
            await on_app_command_error_handler(interaction, error)
            mock_respond.assert_called_once()
        
        # Then, test fallback to followup path
        interaction2 = self.create_mock_interaction(is_expired=False, is_responded=True)
        with patch('utils.bot_commands.safe_followup_async', return_value=True) as mock_followup, \
             patch('utils.bot_commands.can_respond', return_value=False):
            
            await on_app_command_error_handler(interaction2, error)
            mock_followup.assert_called_once()


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
