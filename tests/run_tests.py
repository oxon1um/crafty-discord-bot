#!/usr/bin/env python3
"""
Test runner for Discord bot error handling tests.
This script runs all the unit tests and provides a summary report.
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path

def run_unit_tests():
    """Run unit tests for error handling"""
    print("🧪 Running unit tests for error handling...")
    
    # Run pytest on the test file
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        "tests/test_error_handler.py", 
        "-v", "--tb=short"
    ], capture_output=True, text=True)
    
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    
    return result.returncode == 0

def run_live_tests():
    """Run live tests (mock interactions only)"""
    print("\n🔴 Running live tests (mock interactions)...")
    
    # Run the live test bot script
    result = subprocess.run([
        sys.executable, "tests/live_test_bot.py"
    ], capture_output=True, text=True)
    
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    
    return result.returncode == 0

def check_deployment_readiness():
    """Check if the bot is ready for deployment testing"""
    print("\n🔍 Checking deployment readiness...")
    
    # Check if required environment variables are set
    required_vars = ['DISCORD_TOKEN', 'CRAFTY_URL', 'CRAFTY_TOKEN', 'SERVER_ID', 'GUILD_ID']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("   Please set these in your .env file before running deployment tests.")
        return False
    
    print("✅ All required environment variables are set")
    
    # Check if bot files exist
    bot_files = ['src/main.py', 'src/utils/bot_commands.py', 'discord_utils.py']
    for file_path in bot_files:
        if not os.path.exists(file_path):
            print(f"❌ Required file missing: {file_path}")
            return False
    
    print("✅ All required bot files exist")
    
    print("\n🚀 Bot is ready for deployment testing!")
    print("   Run: python tests/deploy_test_bot.py")
    print("   This will start the bot in a test guild for live testing.")
    
    return True

def main():
    """Main test runner"""
    parser = argparse.ArgumentParser(description='Discord bot error handling test runner')
    parser.add_argument('--unit-only', action='store_true', help='Run only unit tests')
    parser.add_argument('--live-only', action='store_true', help='Run only live tests')
    parser.add_argument('--check-deployment', action='store_true', help='Check deployment readiness')
    
    args = parser.parse_args()
    
    print("Discord Bot Error Handling Test Suite")
    print("=" * 50)
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    success = True
    
    if args.check_deployment:
        success = check_deployment_readiness()
    elif args.unit_only:
        success = run_unit_tests()
    elif args.live_only:
        success = run_live_tests()
    else:
        # Run all tests
        print("Running comprehensive error handling test suite...")
        
        # 1. Unit tests
        unit_success = run_unit_tests()
        
        # 2. Live tests (mock only)
        live_success = run_live_tests()
        
        # 3. Deployment readiness check
        deployment_ready = check_deployment_readiness()
        
        success = unit_success and live_success and deployment_ready
    
    print("\n" + "=" * 50)
    if success:
        print("✅ All tests passed!")
        print("\nNext steps:")
        print("1. Deploy to test guild: python tests/deploy_test_bot.py")
        print("2. Test commands rapidly to ensure no 40060/10062 errors")
        print("3. Monitor logs for error patterns")
    else:
        print("❌ Some tests failed!")
        print("Please review the output above and fix any issues.")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
