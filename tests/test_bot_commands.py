import unittest
import discord
from unittest.mock import MagicMock
from src.utils.crafty_api import ServerStats
from src.utils.bot_commands import (
    _derive_server_state,
    _format_players,
    _safe_get_attr_multi
)

class TestBotCommands(unittest.TestCase):

    def test_safe_get_attr_multi(self):
        """Test _safe_get_attr_multi returns correct values"""
        mock_stats = ServerStats(
            server_id='test_id',
            server_name='test_server',
            running=True,
            crashed=False,
            updating=False,
            cpu=50.0,
            memory="1024MB",
            mem_percent=50.0,
            online_players=5,
            max_players=10,
            version="1.19",
            world_name="world",
            world_size="100MB",
            started="-1"
        )
        
        # Test existing attribute
        self.assertEqual(_safe_get_attr_multi(mock_stats, ['server_name', 'name']), 'test_server')
        
        # Test fallback attribute
        self.assertEqual(_safe_get_attr_multi(mock_stats, ['name', 'server_name']), 'test_server')
        
        # Test non-existent attribute with fallback value
        self.assertEqual(_safe_get_attr_multi(mock_stats, ['non_existent'], 'default'), 'default')
        
        # Test non-existent attribute without fallback value
        self.assertIsNone(_safe_get_attr_multi(mock_stats, ['non_existent']))

    def test_derive_server_state(self):
        """Test _derive_server_state returns correct state tuples"""
        
        # Running state
        running_stats = ServerStats(running=True, crashed=False, updating=False, server_id=None, server_name=None, cpu=None, memory=None, mem_percent=None, online_players=None, max_players=None, version=None, world_name=None, world_size=None, started=None)
        self.assertEqual(_derive_server_state(running_stats), ("🟢", "Running", discord.Color.green()))
        
        # Stopped state
        stopped_stats = ServerStats(running=False, crashed=False, updating=False, server_id=None, server_name=None, cpu=None, memory=None, mem_percent=None, online_players=None, max_players=None, version=None, world_name=None, world_size=None, started=None)
        self.assertEqual(_derive_server_state(stopped_stats), ("🔴", "Stopped", discord.Color.red()))
        
        # Crashed state
        crashed_stats = ServerStats(running=False, crashed=True, updating=False, server_id=None, server_name=None, cpu=None, memory=None, mem_percent=None, online_players=None, max_players=None, version=None, world_name=None, world_size=None, started=None)
        self.assertEqual(_derive_server_state(crashed_stats), ("💥", "Crashed", discord.Color.orange()))
        
        # Updating state
        updating_stats = ServerStats(running=False, crashed=False, updating=True, server_id=None, server_name=None, cpu=None, memory=None, mem_percent=None, online_players=None, max_players=None, version=None, world_name=None, world_size=None, started=None)
        self.assertEqual(_derive_server_state(updating_stats), ("🔄", "Updating", discord.Color.blue()))

    def test_format_players(self):
        """Test _format_players correctly formats player counts"""
        
        # Both online and max players
        stats1 = MagicMock()
        stats1.online_players = 5
        stats1.max_players = 10
        self.assertEqual(_format_players(stats1), "5/10")
        
        # Only online players
        stats2 = MagicMock()
        stats2.online_players = 5
        stats2.max_players = None
        self.assertEqual(_format_players(stats2), "5/?")
        
        # Only max players
        stats3 = MagicMock()
        stats3.online_players = None
        stats3.max_players = 20
        self.assertEqual(_format_players(stats3), "?/20")
        
        # Neither online nor max players
        stats4 = MagicMock()
        stats4.online_players = None
        stats4.max_players = None
        self.assertEqual(_format_players(stats4), "Unknown")
        
        # Non-integer values
        stats5 = MagicMock()
        stats5.online_players = '5a'
        stats5.max_players = '10b'
        self.assertEqual(_format_players(stats5), "5a/10b")

if __name__ == '__main__':
    unittest.main()

