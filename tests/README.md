# Discord Bot Error Handling Testing Framework

This testing framework provides comprehensive unit and live testing for the Discord bot's error handling system, specifically designed to prevent common Discord API errors like 40060 (interaction already acknowledged) and 10062 (unknown interaction).

## Overview

The testing framework consists of several components:

1. **Unit Tests** (`test_error_handler.py`) - Mock-based tests for interaction handling
2. **Live Tests** (`live_test_bot.py`) - Mock command execution stress testing
3. **Deployment Tests** (`deploy_test_bot.py`) - Real Discord bot deployment testing
4. **Test Runner** (`run_tests.py`) - Unified test execution and reporting

## Quick Start

```bash
# Run all tests
python tests/run_tests.py

# Run only unit tests
python tests/run_tests.py --unit-only

# Check deployment readiness
python tests/run_tests.py --check-deployment

# Deploy to test guild for live testing
python tests/deploy_test_bot.py
```

## Test Components

### 1. Unit Tests (`test_error_handler.py`)

Tests the core error handling logic using mock Discord interactions:

**TestInteractionMocking:**
- ✅ Normal interaction can respond
- ✅ Expired interaction cannot respond  
- ✅ Already responded interaction cannot respond
- ✅ Safe respond async normal flow
- ✅ Safe respond async with expired interaction
- ✅ Safe respond async with already responded interaction
- ✅ Safe followup async normal flow
- ✅ Safe followup async with expired interaction

**TestErrorHandlerBehavior:**
- ✅ Error handler uses respond for fresh interactions
- ✅ Error handler uses followup for responded interactions
- ✅ Error handler handles missing permissions
- ✅ Error handler handles cooldown errors
- ✅ Error handler handles transformer errors
- ✅ Error handler handles secondary errors
- ✅ Error handler truncates long messages

**TestDiscordErrorSimulation:**
- ✅ Safe respond handles 40060 error (interaction already acknowledged)
- ✅ Safe respond handles 10062 error (unknown interaction)
- ✅ Safe followup handles 10062 error (unknown interaction)
- ✅ Safe followup handles expired interaction
- ✅ Comprehensive error flow testing

### 2. Live Tests (`live_test_bot.py`)

Stress tests the bot using mock interactions to simulate high-load scenarios:

**Features:**
- Command stress testing with configurable iterations and delays
- Rapid-fire testing with multiple commands
- Concurrent execution testing
- Comprehensive error logging and metrics
- Timeout detection and handling

**Usage:**
```bash
python tests/live_test_bot.py
```

### 3. Deployment Tests (`deploy_test_bot.py`)

Deploys the actual Discord bot to a test guild for real-world testing:

**Features:**
- Real Discord API interaction testing
- Comprehensive error monitoring and logging
- Periodic status reporting
- Command execution statistics
- Error code detection (40060, 10062)
- Deployment health metrics

**Usage:**
```bash
python tests/deploy_test_bot.py
```

**Requirements:**
- Valid Discord bot token
- Test guild ID configured
- All environment variables set

### 4. Test Runner (`run_tests.py`)

Unified test execution with comprehensive reporting:

**Features:**
- Runs all test suites
- Environment validation
- Deployment readiness checks
- Consolidated reporting
- Next steps guidance

## Environment Setup

Create a `.env` file with the following variables:

```env
DISCORD_TOKEN=your_discord_bot_token
CRAFTY_URL=your_crafty_controller_url
CRAFTY_TOKEN=your_crafty_api_token
SERVER_ID=your_minecraft_server_uuid
GUILD_ID=your_test_discord_guild_id
```

## Key Testing Scenarios

### 1. Interaction State Testing

Tests the bot's ability to handle Discord interactions in various states:

- **Fresh Interactions**: Can respond normally
- **Expired Interactions**: Cannot respond, proper error handling
- **Already Responded**: Cannot respond again, uses followup instead

### 2. Error Code Prevention

Specifically tests prevention of critical Discord API errors:

- **40060 (Interaction Already Acknowledged)**: Ensures bot doesn't try to respond to already-handled interactions
- **10062 (Unknown Interaction)**: Handles cases where Discord doesn't recognize the interaction

### 3. Error Handler Decision Logic

Tests the `on_app_command_error_handler` decision-making:

- **Fresh Interaction**: Uses `interaction.response.send_message()`
- **Responded Interaction**: Uses `interaction.followup.send()`
- **Expired Interaction**: Logs warning and exits gracefully

### 4. Resilience Testing

Tests the bot's ability to handle edge cases:

- **Secondary Errors**: Errors in the error handler itself
- **Long Messages**: Automatic truncation of oversized error messages
- **Network Timeouts**: Proper timeout handling and reporting

## Test Results Interpretation

### Unit Test Results
```
✅ 20 passed - All core error handling logic working correctly
❌ X failed - Review failed tests and fix underlying issues
```

### Live Test Results
```
Commands executed: 100
Successful responses: 98
Failed responses: 2
Success rate: 98.00%

40060 errors: 0  ✅ (Target: 0)
10062 errors: 0  ✅ (Target: 0)
Other errors: 2  ⚠️ (Review logs)
```

### Deployment Test Results
```
✅ SUCCESS: No critical 40060 or 10062 errors detected!
❌ FAILURE: X critical errors detected! (Review logs)
```

## Troubleshooting

### Common Issues

1. **Tests failing due to missing dependencies**:
   ```bash
   pip install pytest pytest-asyncio
   ```

2. **Environment variables not set**:
   - Check `.env` file exists and contains all required variables
   - Verify Discord bot token is valid
   - Ensure GUILD_ID is a test guild, not production

3. **40060 errors in live testing**:
   - Review interaction handling logic
   - Check for duplicate response attempts
   - Verify `can_respond()` function usage

4. **10062 errors in live testing**:
   - Check interaction timeout handling
   - Review Discord API rate limits
   - Verify network connectivity

### Best Practices

1. **Always test in a dedicated test guild**
2. **Never run live tests against production**
3. **Review error logs after each test run**
4. **Run tests after any error handling changes**
5. **Monitor success rates and investigate drops**

## Contributing

When adding new error handling features:

1. Add corresponding unit tests in `test_error_handler.py`
2. Update live test scenarios if needed
3. Test with both mock and real Discord interactions
4. Document any new error codes or scenarios
5. Update this README with new test descriptions

## Files

- `test_error_handler.py` - Core unit tests
- `live_test_bot.py` - Live stress testing
- `deploy_test_bot.py` - Real Discord deployment testing
- `run_tests.py` - Test runner and reporting
- `README.md` - This documentation

## Success Criteria

For the error handling system to be considered robust:

1. ✅ All unit tests pass (20/20)
2. ✅ Live tests show >95% success rate
3. ✅ Zero 40060 errors in deployment testing
4. ✅ Zero 10062 errors in deployment testing
5. ✅ Proper error message formatting and logging
6. ✅ Graceful handling of secondary errors

## Next Steps

After testing passes:

1. Deploy to production with confidence
2. Monitor production logs for any new error patterns
3. Set up automated testing in CI/CD pipeline
4. Regular stress testing during maintenance windows
5. Update tests when Discord API changes
