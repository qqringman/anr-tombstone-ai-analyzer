"""
Pytest configuration and fixtures
"""
import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config.system_config import SystemConfig
from config.anthropic_config import AnthropicApiConfig
from config.openai_config import OpenApiConfig
from config.base import AnalysisMode, ModelProvider
from utils.status_manager import EnhancedStatusManager
from utils.cache_manager import CacheManager
from core.cancellation import CancellationToken, CancellationManager
from storage.database import Database

# Pytest configuration
pytest_plugins = ['pytest_asyncio']


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_config(temp_dir):
    """Create test configuration"""
    config = SystemConfig()
    config.api_keys.anthropic = "test_anthropic_key"
    config.api_keys.openai = "test_openai_key"
    config.cache.directory = str(temp_dir / "cache")
    config.database.url = f"sqlite:///{temp_dir}/test.db"
    config.logging.directory = str(temp_dir / "logs")
    return config


@pytest.fixture
def anthropic_config():
    """Create test Anthropic configuration"""
    config = AnthropicApiConfig()
    config.api_key = "test_anthropic_key"
    return config


@pytest.fixture
def openai_config():
    """Create test OpenAI configuration"""
    config = OpenApiConfig()
    config.api_key = "test_openai_key"
    return config


@pytest.fixture
async def status_manager():
    """Create status manager instance"""
    manager = EnhancedStatusManager()
    yield manager
    await manager.reset()


@pytest.fixture
def cache_manager(temp_dir):
    """Create cache manager instance"""
    return CacheManager(str(temp_dir / "cache"))


@pytest.fixture
def cancellation_token():
    """Create cancellation token"""
    return CancellationToken("test-analysis-id")


@pytest.fixture
async def cancellation_manager():
    """Create cancellation manager"""
    manager = CancellationManager()
    yield manager
    await manager.cancel_all()


@pytest.fixture
async def test_db(temp_dir):
    """Create test database"""
    db_url = f"sqlite:///{temp_dir}/test.db"
    db = Database(db_url)
    db.initialize()
    db.create_tables()
    yield db
    db.close()


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client"""
    with patch('anthropic.AsyncAnthropic') as mock:
        client = AsyncMock()
        mock.return_value = client
        
        # Mock streaming response
        async def mock_stream():
            events = [
                Mock(type='message_start', usage=Mock(input_tokens=100)),
                Mock(type='content_block_delta', delta=Mock(text='Test analysis result')),
                Mock(type='message_delta', usage=Mock(output_tokens=50))
            ]
            for event in events:
                yield event
        
        client.messages.create = AsyncMock(return_value=mock_stream())
        yield client


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client"""
    with patch('openai.AsyncOpenAI') as mock:
        client = AsyncMock()
        mock.return_value = client
        
        # Mock streaming response
        async def mock_stream():
            chunks = [
                Mock(choices=[Mock(delta=Mock(content='Test'))]),
                Mock(choices=[Mock(delta=Mock(content=' analysis'))]),
                Mock(choices=[Mock(delta=Mock(content=' result'))]),
                Mock(usage=Mock(prompt_tokens=100, completion_tokens=50))
            ]
            for chunk in chunks:
                yield chunk
        
        client.chat.completions.create = AsyncMock(return_value=mock_stream())
        yield client


@pytest.fixture
def sample_anr_log():
    """Sample ANR log content"""
    return """
----- pid 12345 at 2024-01-15 10:30:45 -----
Cmd line: com.example.app
ABI: 'arm64'

"main" prio=5 tid=1 Blocked
  | group="main" sCount=1 dsCount=0 flags=1
  | state=S schedstat=( 0 0 0 ) utm=0 stm=0 core=0 HZ=100
  at android.os.MessageQueue.nativePollOnce(Native Method)
  at android.os.MessageQueue.next(MessageQueue.java:336)
  at android.os.Looper.loop(Looper.java:174)
  at android.app.ActivityThread.main(ActivityThread.java:7356)

"AsyncTask #1" prio=5 tid=12 Waiting
  | group="main" sCount=1 dsCount=0 flags=1
  | state=S schedstat=( 0 0 0 ) utm=0 stm=0 core=0 HZ=100
  at java.lang.Object.wait(Native Method)
  at java.lang.Thread.parkFor$(Thread.java:2127)
  at sun.misc.Unsafe.park(Unsafe.java:325)
"""


@pytest.fixture
def sample_tombstone_log():
    """Sample tombstone log content"""
    return """
*** *** *** *** *** *** *** *** *** *** *** *** *** *** *** ***
Build fingerprint: 'google/coral/coral:11/RP1A.201005.004/6782484:user/release-keys'
Revision: '0'
ABI: 'arm64'
Timestamp: 2024-01-15 10:30:45+0800
pid: 12345, tid: 12345, name: example.app  >>> com.example.app <<<
uid: 10234
signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x0
Cause: null pointer dereference
    x0  0000000000000000  x1  0000007fd8f9e5a0  x2  0000000000000010  x3  0000000000000000
    x4  0000007fd8f9e5b0  x5  0000000000000000  x6  0000000000000000  x7  0000000000000000

backtrace:
      #00 pc 000000000006d4f8  /system/lib64/libc.so (strlen+12)
      #01 pc 00000000000a1234  /data/app/com.example.app/lib/arm64/libnative.so
      #02 pc 000000000001e456  /data/app/com.example.app/lib/arm64/libnative.so
"""


@pytest.fixture
def large_anr_log():
    """Large ANR log for testing"""
    base_thread = '''
"Thread-{}" prio=5 tid={} Waiting
  | group="main" sCount=1 dsCount=0 flags=1
  | state=S schedstat=( 0 0 0 ) utm=0 stm=0 core=0 HZ=100
  at java.lang.Object.wait(Native Method)
  at java.lang.Thread.parkFor$(Thread.java:2127)
  at sun.misc.Unsafe.park(Unsafe.java:325)
  at java.util.concurrent.locks.LockSupport.park(LockSupport.java:190)
  at java.util.concurrent.locks.AbstractQueuedSynchronizer.parkAndCheckInterrupt(AbstractQueuedSynchronizer.java:868)
'''
    
    header = """
----- pid 12345 at 2024-01-15 10:30:45 -----
Cmd line: com.example.largeapp
ABI: 'arm64'

DALVIK THREADS (100):
"""
    
    threads = [base_thread.format(i, i+10) for i in range(100)]
    return header + '\n'.join(threads)


@pytest.fixture
def mock_flask_app():
    """Mock Flask application for API testing"""
    from flask import Flask
    from api.app import app
    
    app.config['TESTING'] = True
    return app


@pytest.fixture
def api_client(mock_flask_app):
    """Flask test client"""
    return mock_flask_app.test_client()


@pytest.fixture
def async_api_client(mock_flask_app):
    """Async Flask test client"""
    return mock_flask_app.test_client()


@pytest.fixture
def mock_sse_response():
    """Mock SSE response generator"""
    async def generate():
        yield 'data: {"type": "start", "analysis_id": "test-123"}\n\n'
        yield 'data: {"type": "content", "content": "Analysis in progress..."}\n\n'
        yield 'data: {"type": "progress", "progress": {"progress_percentage": 50}}\n\n'
        yield 'data: {"type": "content", "content": "Analysis complete."}\n\n'
        yield 'data: {"type": "complete"}\n\n'
    
    return generate


@pytest.fixture
def mock_time():
    """Mock time for consistent testing"""
    with patch('time.time') as mock_time:
        mock_time.return_value = 1234567890.0
        yield mock_time


@pytest.fixture
def mock_datetime():
    """Mock datetime for consistent testing"""
    fixed_time = datetime(2024, 1, 15, 10, 30, 45)
    with patch('datetime.datetime') as mock_dt:
        mock_dt.now.return_value = fixed_time
        mock_dt.utcnow.return_value = fixed_time
        yield mock_dt


# Markers
def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "slow: Slow tests")
    config.addinivalue_line("markers", "requires_api_key: Tests requiring real API keys")


# Auto-use fixtures
@pytest.fixture(autouse=True)
def reset_environment():
    """Reset environment variables before each test"""
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture(autouse=True)
async def cleanup_async():
    """Cleanup async resources after each test"""
    yield
    # Clean up any pending tasks
    tasks = [task for task in asyncio.all_tasks() if not task.done()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)