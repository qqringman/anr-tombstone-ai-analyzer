"""
Unit tests for cancellation mechanism
"""
import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch

from core.cancellation import CancellationToken, CancellationManager
from utils.status_manager import EnhancedStatusManager


class TestCancellationToken:
    """Test cancellation token functionality"""
    
    def test_initialization(self):
        """Test token initialization"""
        token = CancellationToken("test-id-123")
        
        assert token.analysis_id == "test-id-123"
        assert token.is_cancelled is False
        assert token.created_at > 0
        assert token.cancelled_at is None
    
    def test_cancel(self):
        """Test token cancellation"""
        token = CancellationToken("test-id")
        
        # Cancel the token
        token.cancel()
        
        assert token.is_cancelled is True
        assert token.cancelled_at is not None
        assert token.cancelled_at > token.created_at
    
    def test_multiple_cancellations(self):
        """Test multiple cancel calls"""
        token = CancellationToken("test-id")
        
        # First cancellation
        token.cancel()
        first_cancelled_at = token.cancelled_at
        
        # Second cancellation should not change timestamp
        time.sleep(0.01)
        token.cancel()
        
        assert token.cancelled_at == first_cancelled_at
    
    def test_check_cancellation(self):
        """Test cancellation checking"""
        token = CancellationToken("test-id")
        
        # Should not raise when not cancelled
        token.check_cancelled()
        
        # Cancel token
        token.cancel()
        
        # Should raise when cancelled
        with pytest.raises(asyncio.CancelledError):
            token.check_cancelled()
    
    @pytest.mark.asyncio
    async def test_async_check_cancellation(self):
        """Test async cancellation checking"""
        token = CancellationToken("test-id")
        
        # Should not raise when not cancelled
        await token.check_cancelled_async()
        
        # Cancel token
        token.cancel()
        
        # Should raise when cancelled
        with pytest.raises(asyncio.CancelledError):
            await token.check_cancelled_async()
    
    def test_cancellation_callbacks(self):
        """Test cancellation callbacks"""
        token = CancellationToken("test-id")
        
        # Track callback calls
        callback_called = []
        
        def callback():
            callback_called.append(True)
        
        # Register callback
        token.add_callback(callback)
        
        # Cancel should trigger callback
        token.cancel()
        
        assert len(callback_called) == 1
    
    @pytest.mark.asyncio
    async def test_async_cancellation_callbacks(self):
        """Test async cancellation callbacks"""
        token = CancellationToken("test-id")
        
        # Track callback calls
        callback_called = []
        
        async def async_callback():
            callback_called.append(True)
        
        # Register async callback
        token.add_callback(async_callback)
        
        # Cancel should trigger callback
        token.cancel()
        
        # Give async callback time to execute
        await asyncio.sleep(0.01)
        
        assert len(callback_called) == 1
    
    def test_multiple_callbacks(self):
        """Test multiple callbacks"""
        token = CancellationToken("test-id")
        
        calls = []
        
        # Register multiple callbacks
        token.add_callback(lambda: calls.append(1))
        token.add_callback(lambda: calls.append(2))
        token.add_callback(lambda: calls.append(3))
        
        # Cancel should trigger all callbacks
        token.cancel()
        
        assert calls == [1, 2, 3]
    
    def test_callback_exceptions(self):
        """Test callback exception handling"""
        token = CancellationToken("test-id")
        
        calls = []
        
        # Register callbacks, one that raises
        token.add_callback(lambda: calls.append(1))
        token.add_callback(lambda: 1/0)  # Will raise
        token.add_callback(lambda: calls.append(3))
        
        # Cancel should still call all callbacks
        token.cancel()
        
        assert 1 in calls
        assert 3 in calls


class TestCancellationManager:
    """Test cancellation manager functionality"""
    
    @pytest.fixture
    async def manager(self):
        """Create cancellation manager instance"""
        manager = CancellationManager()
        yield manager
        await manager.cancel_all()
    
    @pytest.mark.asyncio
    async def test_create_token(self, manager):
        """Test token creation"""
        analysis_id = "test-analysis-123"
        
        token = await manager.create_token(analysis_id)
        
        assert token is not None
        assert token.analysis_id == analysis_id
        assert token.is_cancelled is False
        
        # Should be stored in manager
        retrieved_token = manager.get_token(analysis_id)
        assert retrieved_token is token
    
    @pytest.mark.asyncio
    async def test_cancel_analysis(self, manager):
        """Test cancelling specific analysis"""
        # Create token
        analysis_id = "test-analysis"
        token = await manager.create_token(analysis_id)
        
        # Cancel it
        success = await manager.cancel_analysis(analysis_id)
        
        assert success is True
        assert token.is_cancelled is True
    
    @pytest.mark.asyncio
    async def test_cancel_nonexistent_analysis(self, manager):
        """Test cancelling non-existent analysis"""
        success = await manager.cancel_analysis("non-existent-id")
        
        assert success is False
    
    @pytest.mark.asyncio
    async def test_cancel_all(self, manager):
        """Test cancelling all analyses"""
        # Create multiple tokens
        tokens = []
        for i in range(5):
            token = await manager.create_token(f"analysis-{i}")
            tokens.append(token)
        
        # Cancel all
        count = await manager.cancel_all()
        
        assert count == 5
        for token in tokens:
            assert token.is_cancelled is True
    
    @pytest.mark.asyncio
    async def test_cleanup_old_tokens(self, manager):
        """Test cleanup of old tokens"""
        # Create old tokens
        old_tokens = []
        for i in range(3):
            token = await manager.create_token(f"old-{i}")
            token.created_at = time.time() - 3700  # More than 1 hour old
            old_tokens.append(token)
        
        # Create recent tokens
        recent_tokens = []
        for i in range(2):
            token = await manager.create_token(f"recent-{i}")
            recent_tokens.append(token)
        
        # Run cleanup
        cleaned = await manager.cleanup_old_tokens(max_age_seconds=3600)
        
        assert cleaned == 3
        
        # Old tokens should be removed
        for token in old_tokens:
            assert manager.get_token(token.analysis_id) is None
        
        # Recent tokens should remain
        for token in recent_tokens:
            assert manager.get_token(token.analysis_id) is not None
    
    @pytest.mark.asyncio
    async def test_get_active_analyses(self, manager):
        """Test getting active analyses"""
        # Create some tokens
        await manager.create_token("active-1")
        await manager.create_token("active-2")
        cancelled_token = await manager.create_token("cancelled-1")
        cancelled_token.cancel()
        
        # Get active analyses
        active = await manager.get_active_analyses()
        
        assert len(active) == 2
        assert "active-1" in active
        assert "active-2" in active
        assert "cancelled-1" not in active
    
    @pytest.mark.asyncio
    async def test_concurrent_operations(self, manager):
        """Test concurrent token operations"""
        analysis_ids = [f"concurrent-{i}" for i in range(10)]
        
        # Create tokens concurrently
        create_tasks = [
            manager.create_token(aid) for aid in analysis_ids
        ]
        tokens = await asyncio.gather(*create_tasks)
        
        assert len(tokens) == 10
        
        # Cancel half concurrently
        cancel_tasks = [
            manager.cancel_analysis(aid) 
            for aid in analysis_ids[:5]
        ]
        results = await asyncio.gather(*cancel_tasks)
        
        assert all(results)
        
        # Check results
        for i, aid in enumerate(analysis_ids):
            token = manager.get_token(aid)
            if i < 5:
                assert token.is_cancelled is True
            else:
                assert token.is_cancelled is False


class TestCancellationIntegration:
    """Test cancellation integration with other components"""
    
    @pytest.mark.asyncio
    async def test_cancellation_with_status_manager(self):
        """Test cancellation updates status manager"""
        status_manager = EnhancedStatusManager()
        manager = CancellationManager()
        
        # Create and track analysis
        analysis_id = "test-analysis"
        token = await manager.create_token(analysis_id)
        
        # Register status update callback
        status_updates = []
        
        def on_cancel():
            status_manager.update_feedback(
                "info",
                "Analysis cancelled",
                {"analysis_id": analysis_id}
            )
            status_updates.append(True)
        
        token.add_callback(on_cancel)
        
        # Cancel
        await manager.cancel_analysis(analysis_id)
        
        # Check status was updated
        assert len(status_updates) == 1
        status = status_manager.get_status()
        assert len(status['feedback']['messages']) > 0
        assert status['feedback']['messages'][-1]['message'] == "Analysis cancelled"
    
    @pytest.mark.asyncio
    async def test_cancellation_during_streaming(self):
        """Test cancellation during streaming operation"""
        token = CancellationToken("streaming-test")
        chunks_processed = []
        
        async def simulate_streaming():
            chunks = ["chunk1", "chunk2", "chunk3", "chunk4", "chunk5"]
            
            for i, chunk in enumerate(chunks):
                # Check cancellation before processing
                await token.check_cancelled_async()
                
                # Simulate processing
                await asyncio.sleep(0.01)
                chunks_processed.append(chunk)
                
                # Cancel after 3rd chunk
                if i == 2:
                    token.cancel()
        
        # Run streaming with cancellation
        with pytest.raises(asyncio.CancelledError):
            await simulate_streaming()
        
        # Should have processed only 3 chunks
        assert len(chunks_processed) == 3
        assert chunks_processed == ["chunk1", "chunk2", "chunk3"]
    
    @pytest.mark.asyncio
    async def test_cancellation_with_cleanup(self):
        """Test cancellation with cleanup operations"""
        cleanup_called = []
        
        class MockAnalyzer:
            def __init__(self):
                self.token = CancellationToken("cleanup-test")
                self.resources_allocated = True
            
            async def analyze(self):
                try:
                    # Simulate long operation
                    for i in range(10):
                        await self.token.check_cancelled_async()
                        await asyncio.sleep(0.01)
                except asyncio.CancelledError:
                    # Cleanup on cancellation
                    await self.cleanup()
                    raise
            
            async def cleanup(self):
                self.resources_allocated = False
                cleanup_called.append(True)
        
        # Run analysis with cancellation
        analyzer = MockAnalyzer()
        
        # Start analysis
        analysis_task = asyncio.create_task(analyzer.analyze())
        
        # Cancel after short delay
        await asyncio.sleep(0.02)
        analyzer.token.cancel()
        
        # Wait for task to complete
        with pytest.raises(asyncio.CancelledError):
            await analysis_task
        
        # Cleanup should have been called
        assert len(cleanup_called) == 1
        assert analyzer.resources_allocated is False
    
    @pytest.mark.asyncio
    async def test_cancellation_propagation(self):
        """Test cancellation propagation through nested operations"""
        token = CancellationToken("propagation-test")
        levels_reached = []
        
        async def level_3():
            levels_reached.append(3)
            await token.check_cancelled_async()
            await asyncio.sleep(0.1)
            levels_reached.append("3-complete")
        
        async def level_2():
            levels_reached.append(2)
            await token.check_cancelled_async()
            await level_3()
            levels_reached.append("2-complete")
        
        async def level_1():
            levels_reached.append(1)
            await token.check_cancelled_async()
            await level_2()
            levels_reached.append("1-complete")
        
        # Start nested operation
        task = asyncio.create_task(level_1())
        
        # Cancel after reaching level 3
        while 3 not in levels_reached:
            await asyncio.sleep(0.01)
        
        token.cancel()
        
        # Wait for cancellation
        with pytest.raises(asyncio.CancelledError):
            await task
        
        # Should have reached all levels but not completed any
        assert 1 in levels_reached
        assert 2 in levels_reached
        assert 3 in levels_reached
        assert "1-complete" not in levels_reached
        assert "2-complete" not in levels_reached
        assert "3-complete" not in levels_reached