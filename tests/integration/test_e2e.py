"""
End-to-end integration tests
"""
import pytest
import asyncio
import json
import time
from unittest.mock import patch, AsyncMock, Mock
from pathlib import Path

from core.engine import AiAnalysisEngine
from api.app import create_app
from config.base import AnalysisMode, ModelProvider
from storage.database import Database


class TestE2EScenarios:
    """Test complete end-to-end scenarios"""
    
    @pytest.fixture
    async def full_system(self, test_config, temp_dir):
        """Setup full system for E2E testing"""
        # Create app
        app = create_app(test_config)
        app.config['TESTING'] = True
        client = app.test_client()
        
        # Create engine
        engine = AiAnalysisEngine()
        
        # Mock AI clients
        with patch('anthropic.AsyncAnthropic') as mock_anthropic:
            with patch('openai.AsyncOpenAI') as mock_openai:
                # Setup mock responses
                async def mock_anthropic_stream():
                    yield Mock(type='message_start', usage=Mock(input_tokens=100))
                    yield Mock(type='content_block_delta', delta=Mock(text='Anthropic analysis result'))
                    yield Mock(type='message_delta', usage=Mock(output_tokens=50))
                
                async def mock_openai_stream():
                    yield Mock(choices=[Mock(delta=Mock(content='OpenAI analysis result'))])
                    yield Mock(usage=Mock(prompt_tokens=100, completion_tokens=50))
                
                mock_anthropic.return_value.messages.create = AsyncMock(
                    return_value=mock_anthropic_stream()
                )
                mock_openai.return_value.chat.completions.create = AsyncMock(
                    return_value=mock_openai_stream()
                )
                
                engine._init_wrappers()
                await engine.start()
                
                yield {
                    'app': app,
                    'client': client,
                    'engine': engine,
                    'config': test_config
                }
                
                await engine.shutdown()
    
    @pytest.mark.asyncio
    async def test_complete_anr_analysis_flow(self, full_system, sample_anr_log):
        """Test complete ANR analysis flow from API to result"""
        client = full_system['client']
        
        headers = {
            'Authorization': 'Bearer test-token',
            'Content-Type': 'application/json'
        }
        
        # Step 1: Check file size
        file_size = len(sample_anr_log.encode('utf-8'))
        
        response = client.post(
            '/api/ai/check-file-size',
            headers=headers,
            json={'file_size': file_size}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['data']['is_valid'] is True
        
        # Step 2: Estimate cost
        file_size_kb = file_size / 1024
        
        response = client.post(
            '/api/ai/estimate-analysis-cost',
            headers=headers,
            json={
                'file_size_kb': file_size_kb,
                'mode': 'intelligent'
            }
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        estimates = data['data']['cost_estimates']
        assert len(estimates) > 0
        
        # Step 3: Perform analysis
        response = client.post(
            '/api/ai/analyze-with-ai',
            headers=headers,
            json={
                'content': sample_anr_log,
                'log_type': 'anr',
                'mode': 'intelligent',
                'provider': 'anthropic'
            }
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'result' in data['data']
        assert 'Anthropic analysis result' in data['data']['result']
    
    @pytest.mark.asyncio
    async def test_streaming_analysis_with_cancellation(self, full_system, sample_anr_log):
        """Test streaming analysis with cancellation"""
        client = full_system['client']
        engine = full_system['engine']
        
        headers = {
            'Authorization': 'Bearer test-token',
            'Content-Type': 'application/json'
        }
        
        # Mock slow streaming
        async def slow_stream():
            for i in range(10):
                yield Mock(
                    type='content_block_delta',
                    delta=Mock(text=f'Chunk {i} ')
                )
                await asyncio.sleep(0.1)
        
        # Patch the engine's wrapper
        engine._wrappers[ModelProvider.ANTHROPIC]._client.messages.create = AsyncMock(
            return_value=slow_stream()
        )
        
        # Start streaming analysis
        response = client.post(
            '/api/ai/analyze-with-cancellation',
            headers=headers,
            json={
                'content': sample_anr_log,
                'log_type': 'anr',
                'mode': 'quick'
            }
        )
        
        assert response.status_code == 200
        assert response.content_type == 'text/event-stream'
        
        # Parse SSE events
        events = []
        analysis_id = None
        
        for line in response.get_data(as_text=True).split('\n'):
            if line.startswith('data: '):
                event = json.loads(line[6:])
                events.append(event)
                
                if event['type'] == 'start':
                    analysis_id = event.get('analysis_id')
        
        # Should have received some events
        assert len(events) > 0
        assert analysis_id is not None
    
    @pytest.mark.asyncio
    async def test_batch_processing_scenario(self, full_system):
        """Test batch processing of multiple files"""
        client = full_system['client']
        
        headers = {
            'Authorization': 'Bearer test-token',
            'Content-Type': 'application/json'
        }
        
        # Simulate batch of ANR logs
        anr_logs = [
            f"ANR log {i}\nMain thread blocked\nStack trace..." 
            for i in range(5)
        ]
        
        results = []
        total_cost = 0
        
        for i, log_content in enumerate(anr_logs):
            # Estimate cost for each
            file_size_kb = len(log_content) / 1024
            
            response = client.post(
                '/api/ai/estimate-analysis-cost',
                headers=headers,
                json={
                    'file_size_kb': file_size_kb,
                    'mode': 'quick'
                }
            )
            
            cost_data = json.loads(response.data)
            cheapest = min(
                cost_data['data']['cost_estimates'],
                key=lambda x: x['total_cost']
            )
            total_cost += cheapest['total_cost']
            
            # Analyze
            response = client.post(
                '/api/ai/analyze-with-ai',
                headers=headers,
                json={
                    'content': log_content,
                    'log_type': 'anr',
                    'mode': 'quick',
                    'provider': cheapest['provider']
                }
            )
            
            result = json.loads(response.data)
            results.append(result)
        
        # Verify all completed
        assert len(results) == 5
        assert all(r['success'] for r in results)
        assert total_cost > 0
        
        print(f"Batch processing completed. Total cost: ${total_cost:.4f}")
    
    @pytest.mark.asyncio
    async def test_provider_fallback_scenario(self, full_system, sample_anr_log):
        """Test provider fallback on failure"""
        client = full_system['client']
        engine = full_system['engine']
        
        headers = {
            'Authorization': 'Bearer test-token',
            'Content-Type': 'application/json'
        }
        
        # Make Anthropic fail
        call_count = 0
        
        async def failing_anthropic_stream():
            nonlocal call_count
            call_count += 1
            raise Exception("Anthropic API temporarily unavailable")
        
        engine._wrappers[ModelProvider.ANTHROPIC]._client.messages.create = AsyncMock(
            side_effect=failing_anthropic_stream
        )
        
        # First attempt with Anthropic (should fail)
        response = client.post(
            '/api/ai/analyze-with-ai',
            headers=headers,
            json={
                'content': sample_anr_log,
                'log_type': 'anr',
                'mode': 'quick',
                'provider': 'anthropic'
            }
        )
        
        assert response.status_code == 500
        error_data = json.loads(response.data)
        assert 'temporarily unavailable' in error_data['error']
        
        # Retry with OpenAI (should succeed)
        response = client.post(
            '/api/ai/analyze-with-ai',
            headers=headers,
            json={
                'content': sample_anr_log,
                'log_type': 'anr',
                'mode': 'quick',
                'provider': 'openai'
            }
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'OpenAI analysis result' in data['data']['result']
    
    @pytest.mark.asyncio
    async def test_concurrent_user_scenario(self, full_system, sample_anr_log):
        """Test handling concurrent users"""
        client = full_system['client']
        
        # Simulate multiple users
        async def simulate_user(user_id: int):
            headers = {
                'Authorization': f'Bearer user-{user_id}-token',
                'Content-Type': 'application/json'
            }
            
            # Each user analyzes slightly different content
            content = f"{sample_anr_log}\nUser {user_id} variant"
            
            response = client.post(
                '/api/ai/analyze-with-ai',
                headers=headers,
                json={
                    'content': content,
                    'log_type': 'anr',
                    'mode': 'quick'
                }
            )
            
            return json.loads(response.data)
        
        # Simulate 10 concurrent users
        tasks = [simulate_user(i) for i in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check results
        successful = [r for r in results if isinstance(r, dict) and r.get('success')]
        errors = [r for r in results if isinstance(r, Exception)]
        
        assert len(successful) >= 8  # At least 80% success rate
        assert len(errors) <= 2  # Maximum 20% errors
        
        print(f"Concurrent test: {len(successful)}/10 successful")
    
    @pytest.mark.asyncio
    async def test_full_monitoring_scenario(self, full_system):
        """Test system monitoring during operations"""
        client = full_system['client']
        engine = full_system['engine']
        
        headers = {
            'Authorization': 'Bearer test-token',
            'Content-Type': 'application/json'
        }
        
        # Get initial health status
        response = client.get('/api/health')
        initial_health = json.loads(response.data)
        assert initial_health['status'] == 'healthy'
        
        # Perform some operations
        for i in range(3):
            client.post(
                '/api/ai/analyze-with-ai',
                headers=headers,
                json={
                    'content': f'Test log {i}',
                    'log_type': 'anr',
                    'mode': 'quick'
                }
            )
        
        # Check metrics
        response = client.get('/metrics')
        metrics = response.get_data(as_text=True)
        
        assert 'ai_analysis_requests_total' in metrics
        assert 'http_requests_total' in metrics
        
        # Get final status
        final_status = engine.get_status()
        
        assert final_status['api_usage']['requests_count'] >= 3
        assert final_status['api_usage']['input_tokens'] > 0
        assert final_status['api_usage']['output_tokens'] > 0
    
    @pytest.mark.asyncio
    async def test_cache_effectiveness(self, full_system, sample_anr_log):
        """Test cache effectiveness in reducing costs"""
        client = full_system['client']
        
        headers = {
            'Authorization': 'Bearer test-token',
            'Content-Type': 'application/json'
        }
        
        # First analysis (cache miss)
        start_time = time.time()
        response = client.post(
            '/api/ai/analyze-with-ai',
            headers=headers,
            json={
                'content': sample_anr_log,
                'log_type': 'anr',
                'mode': 'quick'
            }
        )
        first_duration = time.time() - start_time
        
        assert response.status_code == 200
        first_result = json.loads(response.data)
        
        # Second analysis (cache hit)
        start_time = time.time()
        response = client.post(
            '/api/ai/analyze-with-ai',
            headers=headers,
            json={
                'content': sample_anr_log,
                'log_type': 'anr',
                'mode': 'quick'
            }
        )
        second_duration = time.time() - start_time
        
        assert response.status_code == 200
        second_result = json.loads(response.data)
        
        # Cache hit should be much faster
        assert second_duration < first_duration / 2
        
        # Results should be identical
        assert first_result['data']['result'] == second_result['data']['result']
        
        print(f"Cache effectiveness: {first_duration:.2f}s -> {second_duration:.2f}s")
    
    @pytest.mark.asyncio
    async def test_large_file_handling(self, full_system, large_anr_log):
        """Test handling of large log files"""
        client = full_system['client']
        
        headers = {
            'Authorization': 'Bearer test-token',
            'Content-Type': 'application/json'
        }
        
        # Check if file size is acceptable
        file_size = len(large_anr_log.encode('utf-8'))
        
        response = client.post(
            '/api/ai/check-file-size',
            headers=headers,
            json={'file_size': file_size}
        )
        
        size_check = json.loads(response.data)
        
        if size_check['data']['is_valid']:
            # Proceed with analysis
            response = client.post(
                '/api/ai/analyze-with-ai',
                headers=headers,
                json={
                    'content': large_anr_log,
                    'log_type': 'anr',
                    'mode': 'quick'
                }
            )
            
            assert response.status_code == 200
            result = json.loads(response.data)
            assert result['success'] is True
        else:
            # File too large
            assert size_check['data']['max_size'] > 0
            print(f"File too large: {file_size} > {size_check['data']['max_size']}")
    
    @pytest.mark.asyncio
    async def test_error_recovery_scenario(self, full_system):
        """Test system recovery from various errors"""
        client = full_system['client']
        engine = full_system['engine']
        
        headers = {
            'Authorization': 'Bearer test-token',
            'Content-Type': 'application/json'
        }
        
        # Simulate transient error
        error_count = 0
        
        async def flaky_stream():
            nonlocal error_count
            error_count += 1
            
            if error_count <= 2:
                raise Exception("Temporary network error")
            else:
                # Success on third attempt
                yield Mock(type='content_block_delta', delta=Mock(text='Recovery successful'))
        
        engine._wrappers[ModelProvider.ANTHROPIC]._client.messages.create = AsyncMock(
            side_effect=flaky_stream
        )
        
        # First attempts should fail
        for i in range(2):
            response = client.post(
                '/api/ai/analyze-with-ai',
                headers=headers,
                json={
                    'content': 'Test recovery',
                    'log_type': 'anr',
                    'mode': 'quick'
                }
            )
            assert response.status_code == 500
        
        # Third attempt should succeed
        response = client.post(
            '/api/ai/analyze-with-ai',
            headers=headers,
            json={
                'content': 'Test recovery',
                'log_type': 'anr',
                'mode': 'quick'
            }
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'Recovery successful' in data['data']['result']