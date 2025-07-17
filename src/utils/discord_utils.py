"""
Discord utility functions for safe interaction handling and response management.

This module provides helper functions to handle Discord interactions safely,
including checking if interactions are still valid and sending responses
without triggering errors when interactions have expired.
"""

import asyncio
import logging
import discord
from typing import Optional, Dict, Any, Union

logger = logging.getLogger(__name__)

def can_respond(interaction: discord.Interaction) -> bool:
    """
    Check if an interaction can still receive responses.
    
    Args:
        interaction: The Discord interaction to check
        
    Returns:
        bool: True if the interaction can still receive responses, False otherwise
    """
    # Check if interaction is expired (generally 3 seconds for initial response, 15 minutes for followups)
    if interaction.is_expired():
        return False
    
    # Check if we already responded
    if interaction.response.is_done():
        # If we already responded, we can only send followup messages
        return True
    
    # If we haven't responded yet, we can respond
    return True


async def safe_respond_async(interaction: discord.Interaction, content: Optional[str] = None, 
                            embed: Optional[discord.Embed] = None, ephemeral: bool = False) -> bool:
    """
    Safely send a response to a Discord interaction without raising exceptions (async version).
    
    Args:
        interaction: The Discord interaction to respond to
        content: Optional text content for the response
        embed: Optional embed for the response
        ephemeral: Whether the response should be ephemeral (only visible to the user)
        
    Returns:
        bool: True if the response was sent successfully, False otherwise
    """
    if not can_respond(interaction):
        logger.warning(
            "Skipping response to expired interaction",
            extra={
                "interaction_id": interaction.id,
                "interaction_type": interaction.type.name if interaction.type else "unknown",
                "user_id": interaction.user.id if interaction.user else None,
                "guild_id": interaction.guild.id if interaction.guild else None,
                "channel_id": interaction.channel.id if interaction.channel else None,
                "command_name": getattr(interaction.command, 'name', None) if hasattr(interaction, 'command') else None,
                "skip_reason": "interaction_expired"
            }
        )
        return False
    
    try:
        if not interaction.response.is_done():
            # Send initial response
            await interaction.response.send_message(
                content=content, 
                embed=embed, 
                ephemeral=ephemeral
            )
            return True
        else:
            # Send followup response
            await interaction.followup.send(
                content=content, 
                embed=embed, 
                ephemeral=ephemeral
            )
            return True
    except discord.InteractionResponded:
        logger.warning(
            "Attempted to respond to already responded interaction",
            extra={
                "interaction_id": interaction.id,
                "interaction_type": interaction.type.name if interaction.type else "unknown",
                "user_id": interaction.user.id if interaction.user else None,
                "guild_id": interaction.guild.id if interaction.guild else None,
                "channel_id": interaction.channel.id if interaction.channel else None,
                "command_name": getattr(interaction.command, 'name', None) if hasattr(interaction, 'command') else None,
                "skip_reason": "already_responded"
            }
        )
        return False
    except discord.HTTPException as e:
        logger.warning(
            "HTTP error when responding to interaction",
            extra={
                "interaction_id": interaction.id,
                "interaction_type": interaction.type.name if interaction.type else "unknown",
                "user_id": interaction.user.id if interaction.user else None,
                "guild_id": interaction.guild.id if interaction.guild else None,
                "channel_id": interaction.channel.id if interaction.channel else None,
                "command_name": getattr(interaction.command, 'name', None) if hasattr(interaction, 'command') else None,
                "skip_reason": "http_error",
                "error_code": e.code if hasattr(e, 'code') else None,
                "error_text": str(e)
            }
        )
        return False
    except Exception as e:
        logger.warning(
            "Unexpected error when responding to interaction",
            extra={
                "interaction_id": interaction.id,
                "interaction_type": interaction.type.name if interaction.type else "unknown",
                "user_id": interaction.user.id if interaction.user else None,
                "guild_id": interaction.guild.id if interaction.guild else None,
                "channel_id": interaction.channel.id if interaction.channel else None,
                "command_name": getattr(interaction.command, 'name', None) if hasattr(interaction, 'command') else None,
                "skip_reason": "unexpected_error",
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
        )
        return False

async def safe_followup_async(interaction: discord.Interaction, content: Optional[str] = None, 
                             embed: Optional[discord.Embed] = None, ephemeral: bool = False) -> bool:
    """
    Safely send a followup message to a Discord interaction without raising exceptions.
    
    Args:
        interaction: The Discord interaction to send followup to
        content: Optional text content for the followup
        embed: Optional embed for the followup
        ephemeral: Whether the followup should be ephemeral (only visible to the user)
        
    Returns:
        bool: True if the followup was sent successfully, False otherwise
    """
    if interaction.is_expired():
        logger.warning(
            "Skipping followup to expired interaction",
            extra={
                "interaction_id": interaction.id,
                "interaction_type": interaction.type.name if interaction.type else "unknown",
                "user_id": interaction.user.id if interaction.user else None,
                "guild_id": interaction.guild.id if interaction.guild else None,
                "channel_id": interaction.channel.id if interaction.channel else None,
                "command_name": getattr(interaction.command, 'name', None) if hasattr(interaction, 'command') else None,
                "skip_reason": "interaction_expired"
            }
        )
        return False
    
    try:
        await interaction.followup.send(
            content=content, 
            embed=embed, 
            ephemeral=ephemeral
        )
        return True
    except discord.HTTPException as e:
        logger.warning(
            "HTTP error when sending followup to interaction",
            extra={
                "interaction_id": interaction.id,
                "interaction_type": interaction.type.name if interaction.type else "unknown",
                "user_id": interaction.user.id if interaction.user else None,
                "guild_id": interaction.guild.id if interaction.guild else None,
                "channel_id": interaction.channel.id if interaction.channel else None,
                "command_name": getattr(interaction.command, 'name', None) if hasattr(interaction, 'command') else None,
                "skip_reason": "http_error",
                "error_code": e.code if hasattr(e, 'code') else None,
                "error_text": str(e)
            }
        )
        return False
    except Exception as e:
        logger.warning(
            "Unexpected error when sending followup to interaction",
            extra={
                "interaction_id": interaction.id,
                "interaction_type": interaction.type.name if interaction.type else "unknown",
                "user_id": interaction.user.id if interaction.user else None,
                "guild_id": interaction.guild.id if interaction.guild else None,
                "channel_id": interaction.channel.id if interaction.channel else None,
                "command_name": getattr(interaction.command, 'name', None) if hasattr(interaction, 'command') else None,
                "skip_reason": "unexpected_error",
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
        )
        return False
