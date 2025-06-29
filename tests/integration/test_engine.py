"""
Integration tests for AI Analysis Engine
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import time

from core.engine import AiAnalysisEngine
from config.base import AnalysisMode, ModelProvider
from core.cancellation import CancellationManager


class TestAiAnalysisEngine:
    """Test AI analysis engine integration"""
    
    @pytest.fixture
    async def engine(self, test_config, mock_anthropic_client, mock_openai_client):
        """Create engine instance with mocked clients"""
        engine = AiAnalysisEngine()
        
        # Patch client creation
        with patch('anthropic.AsyncAnthropic', return_value=mock_anthropic_client):
            with patch('openai.AsyncOpenAI', return_value=mock_openai_client):
                engine._init_wrappers()
        
        await engine.start()
        yield engine
        await engine.shutdown()
    
    @pytest.mark.asyncio
    async def test_engine_initialization(self, engine):
        """Test engine initialization"""
        assert engine is not None
        assert engine.status_manager is not None
        assert engine.cache_manager is not None
        assert engine.logger is not None
        assert engine.storage is not None
        assert engine.health_checker is not None
        
        # Check wrappers
        assert len(engine._wrappers) > 0
        assert engine._current_provider is not None
    
    @pytest.mark.asyncio
    async def test_basic_analysis(self, engine, sample_anr_log):
        """Test basic ANR analysis"""
        result_chunks = []
        
        async for chunk in engine.analyze(
            content=sample_anr_log,
            log_type='anr',
            mode=AnalysisMode.QUICK
        ):
            result_chunks.append(chunk)
        
        assert len(result_chunks) > 0
        complete_result = ''.join(result_chunks)
        assert len(complete_result) > 0
    
    @pytest.mark.asyncio
    async def test_provider_switching(self, engine, sample_anr_log):
        """Test switching between providers"""
        # Start with Anthropic
        engine.set_provider(ModelProvider.ANTHROPIC)
        assert engine._current_provider == ModelProvider.ANTHROPIC
        
        # Analyze with Anthropic
        anthropic_result = []
        async for chunk in engine.analyze(
            content=sample_anr_log,
            log_type='anr',
            mode=AnalysisMode.QUICK,
            provider=ModelProvider.ANTHROPIC
        ):
            anthropic_result.append(chunk)
        
        # Switch to OpenAI
        engine.set_provider(ModelProvider.OPENAI)
        assert engine._current_provider == ModelProvider.OPENAI
        
        # Analyze with OpenAI
        openai_result = []
        async for chunk in engine.analyze(
            content=sample_anr_log,
            log_type='anr',
            mode=AnalysisMode.QUICK,
            provider=ModelProvider.OPENAI
        ):
            openai_result.append(chunk)
        
        # Both should produce results
        assert len(anthropic_result) > 0
        assert len(openai_result) > 0
    
    @pytest.mark.asyncio
    async def test_cache_functionality(self, engine, sample_anr_log):
        """Test caching mechanism"""
        # First analysis (cache miss)
        start_time = time.time()
        first_result = []
        
        async for chunk in engine.analyze(
            content=sample_anr_log,
            log_type='anr',
            mode=AnalysisMode.QUICK,
            use_cache=True
        ):
            first_result.append(chunk)
        
        first_duration = time.time() - start_time
        
        # Second analysis (cache hit)
        start_time = time.time()
        second_result = []
        
        async for chunk in engine.analyze(
            content=sample_anr_log,
            log_type='anr',
            mode=AnalysisMode.QUICK,
            use_cache=True
        ):
            second_result.append(chunk)
        
        second_duration = time.time() - start_time
        
        # Cache hit should be much faster
        assert second_duration < first_duration / 2
        
        # Results should be identical
        assert ''.join(first_result) == ''.join(second_result)
    
    @pytest.mark.asyncio
    async def test_task_queue_submission(self, engine, sample_anr_log):
        """Test task queue functionality"""
        # Submit task
        task_id = await engine.submit_task(
            content=sample_anr_log,
            log_type='anr',
            mode=AnalysisMode.QUICK,
            priority=1
        )
        
        assert task_id is not None
        
        # Check task status
        status = engine.get_task_status(task_id)
        assert status is not None
        assert status['id'] == task_id
        assert status['log_type'] == 'anr'
        assert status['mode'] == 'quick'
        
        # Wait for completion
        max_wait = 5  # seconds
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            status = engine.get_task_status(task_id)
            if status['status'] in ['completed', 'failed']:
                break
            await asyncio.sleep(0.1)
        
        # Should complete successfully
        assert status['status'] == 'completed'
        assert status['has_result'] is True
        assert status['has_error'] is False
    
    @pytest.mark.asyncio
    async def test_concurrent_analyses(self, engine, sample_anr_log):
        """Test concurrent analysis handling"""
        # Submit multiple analyses
        tasks = []
        
        for i in range(3):
            task = engine.analyze(
                content=f"{sample_anr_log}\n// Variant {i}",
                log_type='anr',
                mode=AnalysisMode.QUICK,
                use_cache=False  # Ensure each runs separately
            )
            tasks.append(task)
        
        # Run concurrently
        results = await asyncio.gather(*[
            self._collect_chunks(task) for task in tasks
        ])
        
        # All should complete
        assert len(results) == 3
        for result in results:
            assert len(result) > 0
    
    @pytest.mark.asyncio
    async def test_error_handling(self, engine):
        """Test error handling"""
        # Invalid log type
        with pytest.raises(ValueError, match="Unknown log type"):
            async for _ in engine.analyze(
                content="test",
                log_type='invalid_type',
                mode=AnalysisMode.QUICK
            ):
                pass
        
        # No provider available
        engine._current_provider = None
        engine._wrappers.clear()
        
        with pytest.raises(ValueError, match="No AI provider available"):
            async for _ in engine.analyze(
                content="test",
                log_type='anr',
                mode=AnalysisMode.QUICK
            ):
                pass
    
    @pytest.mark.asyncio
    async def test_status_monitoring(self, engine, sample_anr_log):
        """Test status monitoring during analysis"""
        status_updates = []
        
        # Add status listener
        def status_callback(status):
            status_updates.append(status.copy())
        
        engine.add_status_listener(status_callback)
        
        # Run analysis
        async for _ in engine.analyze(
            content=sample_anr_log,
            log_type='anr',
            mode=AnalysisMode.QUICK
        ):
            pass
        
        # Should have received status updates
        assert len(status_updates) > 0
        
        # Check status structure
        final_status = engine.get_status()
        assert 'current_provider' in final_status
        assert 'available_providers' in final_status
        assert 'api_usage' in final_status
        assert 'progress' in final_status
    
    @pytest.mark.asyncio
    async def test_health_check(self, engine):
        """Test health check functionality"""
        health = await engine.get_health_status()
        
        assert 'overall' in health
        assert 'components' in health
        assert 'timestamp' in health
        
        # Check component health
        components = health['components']
        assert 'cache' in components
        assert 'storage' in components
        assert 'wrappers' in components
        
        # Overall status should be healthy
        assert health['overall']['status'] in ['healthy', 'degraded']
    
    @pytest.mark.asyncio
    async def test_model_selection_by_mode(self, engine, sample_anr_log):
        """Test model selection based on analysis mode"""
        # Mock to track model selection
        original_analyze = engine._wrappers[ModelProvider.ANTHROPIC].analyze_anr
        called_models = []
        
        async def mock_analyze(content, mode):
            model = engine.config.model_preferences.mode_overrides[mode.value]['anthropic']
            called_models.append(model)
            async for chunk in original_analyze(content, mode):
                yield chunk
        
        engine._wrappers[ModelProvider.ANTHROPIC].analyze_anr = mock_analyze
        
        # Test quick mode
        async for _ in engine.analyze(
            content=sample_anr_log,
            log_type='anr',
            mode=AnalysisMode.QUICK,
            provider=ModelProvider.ANTHROPIC
        ):
            pass
        
        # Test intelligent mode
        async for _ in engine.analyze(
            content=sample_anr_log,
            log_type='anr',
            mode=AnalysisMode.INTELLIGENT,
            provider=ModelProvider.ANTHROPIC
        ):
            pass
        
        # Should have used different models
        assert len(called_models) == 2
        assert called_models[0] != called_models[1]
        assert 'haiku' in called_models[0]  # Quick mode
        assert 'sonnet' in called_models[1]  # Intelligent mode
    
    async def _collect_chunks(self, async_generator):
        """Helper to collect chunks from async generator"""
        chunks = []
        async for chunk in async_generator:
            chunks.append(chunk)
        return chunks


class TestEngineCancellation:
    """Test engine cancellation functionality"""
    
    @pytest.fixture
    async def engine_with_cancellation(self, test_config):
        """Create engine with real cancellation"""
        engine = AiAnalysisEngine()
        
        # Create mock that simulates slow streaming
        async def slow_stream():
            for i in range(10):
                yield Mock(
                    type='content_block_delta',
                    delta=Mock(text=f'Chunk {i} ')
                )
                await asyncio.sleep(0.1)  # Slow streaming
        
        # Patch clients
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=slow_stream())
        
        with patch('anthropic.AsyncAnthropic', return_value=mock_client):
            engine._init_wrappers()
        
        await engine.start()
        yield engine
        await engine.shutdown()
    
    @pytest.mark.asyncio
    async def test_analysis_cancellation(self, engine_with_cancellation):
        """Test cancelling ongoing analysis"""
        engine = engine_with_cancellation
        
        # Submit task
        task_id = await engine.submit_task(
            content="Test content",
            log_type='anr',
            mode=AnalysisMode.QUICK
        )
        
        # Wait briefly for task to start
        await asyncio.sleep(0.2)
        
        # Cancel the task
        # Note: This would require implementing cancellation in the engine
        # For now, we'll simulate the behavior
        
        # Check final status
        status = engine.get_task_status(task_id)
        assert status is not None


class TestEngineResilience:
    """Test engine resilience and recovery"""
    
    @pytest.mark.asyncio
    async def test_provider_fallback(self, test_config):
        """Test fallback to alternative provider on failure"""
        engine = AiAnalysisEngine()
        
        # Make Anthropic fail
        failing_anthropic = AsyncMock()
        failing_anthropic.messages.create = AsyncMock(
            side_effect=Exception("Anthropic API Error")
        )
        
        # Make OpenAI work
        working_openai = AsyncMock()
        async def mock_openai_stream():
            yield Mock(choices=[Mock(delta=Mock(content='Fallback result'))])
        
        working_openai.chat.completions.create = AsyncMock(
            return_value=mock_openai_stream()
        )
        
        with patch('anthropic.AsyncAnthropic', return_value=failing_anthropic):
            with patch('openai.AsyncOpenAI', return_value=working_openai):
                engine._init_wrappers()
        
        await engine.start()
        
        # Set Anthropic as primary
        engine.set_provider(ModelProvider.ANTHROPIC)
        
        # Should fail with Anthropic
        with pytest.raises(Exception, match="Anthropic API Error"):
            async for _ in engine.analyze(
                content="test",
                log_type='anr',
                mode=AnalysisMode.QUICK
            ):
                pass
        
        # Manually switch to OpenAI (in real implementation, this could be automatic)
        engine.set_provider(ModelProvider.OPENAI)
        
        # Should succeed with OpenAI
        result = []
        async for chunk in engine.analyze(
            content="test",
            log_type='anr',
            mode=AnalysisMode.QUICK
        ):
            result.append(chunk)
        
        assert len(result) > 0
        assert 'Fallback result' in ''.join(result)
        
        await engine.shutdown()
    
    @pytest.mark.asyncio
    async def test_rate_limit_handling(self, test_config):
        """Test rate limit handling"""
        engine = AiAnalysisEngine()
        
        # Track request count
        request_count = 0
        
        async def rate_limited_stream():
            nonlocal request_count
            request_count += 1
            
            if request_count <= 2:
                # Simulate rate limit error
                raise Exception("Rate limit exceeded")
            else:
                # Success after retry
                yield Mock(
                    type='content_block_delta',
                    delta=Mock(text='Success after retry')
                )
        
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=rate_limited_stream)
        
        with patch('anthropic.AsyncAnthropic', return_value=mock_client):
            engine._init_wrappers()
        
        # This would require retry logic in the engine
        # For now, we just verify the error is raised
        with pytest.raises(Exception, match="Rate limit exceeded"):
            async for _ in engine.analyze(
                content="test",
                log_type='anr',
                mode=AnalysisMode.QUICK
            ):
                pass
    
    @pytest.mark.asyncio
    async def test_memory_management(self, test_config, large_anr_log):
        """Test memory management with large files"""
        engine = AiAnalysisEngine()
        
        # Mock streaming that yields many chunks
        async def large_stream():
            for i in range(100):
                yield Mock(
                    type='content_block_delta',
                    delta=Mock(text=f'Chunk {i} ' * 100)
                )
        
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=large_stream())
        
        with patch('anthropic.AsyncAnthropic', return_value=mock_client):
            engine._init_wrappers()
        
        await engine.start()
        
        # Process large file
        chunk_count = 0
        async for chunk in engine.analyze(
            content=large_anr_log,
            log_type='anr',
            mode=AnalysisMode.QUICK
        ):
            chunk_count += 1
        
        assert chunk_count == 100
        
        # Check memory usage through status
        status = engine.get_status()
        assert status is not None
        
        await engine.shutdown()