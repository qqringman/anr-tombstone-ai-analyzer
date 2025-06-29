"""
Unit tests for analyzers
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from config.base import AnalysisMode
from analyzers.anr.anthropic import AnthropicApiStreamingANRAnalyzer
from analyzers.anr.openai import OpenApiStreamingANRAnalyzer
from analyzers.tombstone.anthropic import AnthropicApiStreamingTombstoneAnalyzer
from analyzers.tombstone.openai import OpenApiStreamingTombstoneAnalyzer

class TestAnthropicANRAnalyzer:
    """Test Anthropic ANR analyzer"""
    
    @pytest.fixture
    def analyzer(self, anthropic_config, status_manager):
        """Create analyzer instance"""
        return AnthropicApiStreamingANRAnalyzer(anthropic_config, status_manager)
    
    @pytest.mark.asyncio
    async def test_analyze_anr_quick_mode(self, analyzer, sample_anr_log, mock_anthropic_client):
        """Test ANR analysis in quick mode"""
        # Arrange
        analyzer._client = mock_anthropic_client
        
        # Act
        result_chunks = []
        async for chunk in analyzer.analyze_anr_async(sample_anr_log, AnalysisMode.QUICK):
            result_chunks.append(chunk)
        
        # Assert
        assert len(result_chunks) > 0
        complete_result = ''.join(result_chunks)
        assert 'Test analysis result' in complete_result
        assert analyzer._client.messages.create.called
    
    @pytest.mark.asyncio
    async def test_analyze_anr_intelligent_mode(self, analyzer, sample_anr_log, mock_anthropic_client):
        """Test ANR analysis in intelligent mode"""
        # Arrange
        analyzer._client = mock_anthropic_client
        
        # Act
        result_chunks = []
        async for chunk in analyzer.analyze_anr_async(sample_anr_log, AnalysisMode.INTELLIGENT):
            result_chunks.append(chunk)
        
        # Assert
        assert len(result_chunks) > 0
        # Check model selection for intelligent mode
        call_args = analyzer._client.messages.create.call_args
        assert call_args.kwargs['model'] in ['claude-3-5-sonnet-20241022', 'claude-sonnet-4-20250514']
    
    @pytest.mark.asyncio
    async def test_analyze_with_cancellation(self, analyzer, sample_anr_log, cancellation_token):
        """Test analysis with cancellation"""
        # Arrange
        analyzer.set_cancellation_token(cancellation_token)
        
        # Mock the client to simulate cancellation
        async def mock_stream():
            yield Mock(type='message_start', usage=Mock(input_tokens=100))
            await asyncio.sleep(0.1)
            cancellation_token.cancel()  # Cancel during streaming
            yield Mock(type='content_block_delta', delta=Mock(text='Partial'))
        
        analyzer._client = Mock()
        analyzer._client.messages.create = AsyncMock(return_value=mock_stream())
        
        # Act & Assert
        with pytest.raises(asyncio.CancelledError):
            async for _ in analyzer.analyze_anr_async(sample_anr_log, AnalysisMode.QUICK):
                pass
    
    @pytest.mark.asyncio
    async def test_error_handling(self, analyzer, sample_anr_log):
        """Test error handling during analysis"""
        # Arrange
        analyzer._client = Mock()
        analyzer._client.messages.create = AsyncMock(
            side_effect=Exception("API Error")
        )
        
        # Act & Assert
        with pytest.raises(Exception, match="API Error"):
            async for _ in analyzer.analyze_anr_async(sample_anr_log, AnalysisMode.QUICK):
                pass
    
    def test_prompt_selection(self, analyzer):
        """Test prompt selection for different modes"""
        # Test quick mode
        quick_prompt = analyzer._get_system_prompt(AnalysisMode.QUICK)
        assert "快速" in quick_prompt or "quick" in quick_prompt.lower()
        
        # Test intelligent mode
        intelligent_prompt = analyzer._get_system_prompt(AnalysisMode.INTELLIGENT)
        assert "詳細" in intelligent_prompt or "detailed" in intelligent_prompt.lower()


class TestOpenAIANRAnalyzer:
    """Test OpenAI ANR analyzer"""
    
    @pytest.fixture
    def analyzer(self, openai_config, status_manager):
        """Create analyzer instance"""
        return OpenApiStreamingANRAnalyzer(openai_config, status_manager)
    
    @pytest.mark.asyncio
    async def test_analyze_anr_basic(self, analyzer, sample_anr_log, mock_openai_client):
        """Test basic ANR analysis"""
        # Arrange
        analyzer._client = mock_openai_client
        
        # Act
        result_chunks = []
        async for chunk in analyzer.analyze_anr_async(sample_anr_log, AnalysisMode.QUICK):
            result_chunks.append(chunk)
        
        # Assert
        assert len(result_chunks) > 0
        complete_result = ''.join(result_chunks)
        assert 'Test analysis result' in complete_result
    
    @pytest.mark.asyncio
    async def test_token_tracking(self, analyzer, sample_anr_log, mock_openai_client, status_manager):
        """Test token usage tracking"""
        # Arrange
        analyzer._client = mock_openai_client
        initial_tokens = status_manager.get_status()['api_usage']['input_tokens']
        
        # Act
        async for _ in analyzer.analyze_anr_async(sample_anr_log, AnalysisMode.QUICK):
            pass
        
        # Assert
        final_tokens = status_manager.get_status()['api_usage']['input_tokens']
        assert final_tokens > initial_tokens


class TestAnthropicTombstoneAnalyzer:
    """Test Anthropic tombstone analyzer"""
    
    @pytest.fixture
    def analyzer(self, anthropic_config, status_manager):
        """Create analyzer instance"""
        return AnthropicApiStreamingTombstoneAnalyzer(anthropic_config, status_manager)
    
    @pytest.mark.asyncio
    async def test_analyze_tombstone(self, analyzer, sample_tombstone_log, mock_anthropic_client):
        """Test tombstone analysis"""
        # Arrange
        analyzer._client = mock_anthropic_client
        
        # Act
        result_chunks = []
        async for chunk in analyzer.analyze_tombstone_async(
            sample_tombstone_log, 
            AnalysisMode.INTELLIGENT
        ):
            result_chunks.append(chunk)
        
        # Assert
        assert len(result_chunks) > 0
        complete_result = ''.join(result_chunks)
        assert len(complete_result) > 0
    
    @pytest.mark.asyncio
    async def test_crash_type_detection(self, analyzer, sample_tombstone_log):
        """Test crash type detection in prompt"""
        # Arrange
        prompt = analyzer._get_system_prompt(AnalysisMode.INTELLIGENT)
        
        # Assert
        assert "SIGSEGV" in prompt or "信號" in prompt
        assert "崩潰" in prompt or "crash" in prompt.lower()


class TestOpenAITombstoneAnalyzer:
    """Test OpenAI tombstone analyzer"""
    
    @pytest.fixture
    def analyzer(self, openai_config, status_manager):
        """Create analyzer instance"""
        return OpenApiStreamingTombstoneAnalyzer(openai_config, status_manager)
    
    @pytest.mark.asyncio
    async def test_analyze_tombstone(self, analyzer, sample_tombstone_log, mock_openai_client):
        """Test tombstone analysis"""
        # Arrange
        analyzer._client = mock_openai_client
        
        # Act
        result_chunks = []
        async for chunk in analyzer.analyze_tombstone_async(
            sample_tombstone_log,
            AnalysisMode.QUICK
        ):
            result_chunks.append(chunk)
        
        # Assert
        assert len(result_chunks) > 0
    
    @pytest.mark.asyncio
    async def test_model_selection(self, analyzer, sample_tombstone_log, mock_openai_client):
        """Test model selection for different modes"""
        # Arrange
        analyzer._client = mock_openai_client
        
        # Test quick mode
        async for _ in analyzer.analyze_tombstone_async(
            sample_tombstone_log,
            AnalysisMode.QUICK
        ):
            pass
        
        call_args = analyzer._client.chat.completions.create.call_args
        assert call_args.kwargs['model'] in ['gpt-4o-mini', 'gpt-3.5-turbo']
        
        # Test intelligent mode
        async for _ in analyzer.analyze_tombstone_async(
            sample_tombstone_log,
            AnalysisMode.INTELLIGENT
        ):
            pass
        
        call_args = analyzer._client.chat.completions.create.call_args
        assert call_args.kwargs['model'] in ['gpt-4o', 'gpt-4-turbo']


class TestAnalyzerComparison:
    """Test analyzer behavior consistency"""
    
    @pytest.mark.asyncio
    async def test_output_format_consistency(
        self, 
        anthropic_config, 
        openai_config, 
        status_manager,
        sample_anr_log,
        mock_anthropic_client,
        mock_openai_client
    ):
        """Test that different analyzers produce consistent output format"""
        # Create analyzers
        anthropic_analyzer = AnthropicApiStreamingANRAnalyzer(anthropic_config, status_manager)
        openai_analyzer = OpenApiStreamingANRAnalyzer(openai_config, status_manager)
        
        anthropic_analyzer._client = mock_anthropic_client
        openai_analyzer._client = mock_openai_client
        
        # Analyze with both
        anthropic_result = []
        async for chunk in anthropic_analyzer.analyze_anr_async(
            sample_anr_log, 
            AnalysisMode.QUICK
        ):
            anthropic_result.append(chunk)
        
        openai_result = []
        async for chunk in openai_analyzer.analyze_anr_async(
            sample_anr_log, 
            AnalysisMode.QUICK
        ):
            openai_result.append(chunk)
        
        # Both should produce non-empty results
        assert len(anthropic_result) > 0
        assert len(openai_result) > 0


# Performance tests
class TestAnalyzerPerformance:
    """Test analyzer performance characteristics"""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_large_log_handling(self, anthropic_config, status_manager, large_anr_log):
        """Test handling of large log files"""
        # Create analyzer
        analyzer = AnthropicApiStreamingANRAnalyzer(anthropic_config, status_manager)
        
        # Mock client with delayed response
        async def mock_stream():
            yield Mock(type='message_start', usage=Mock(input_tokens=5000))
            for i in range(10):
                yield Mock(
                    type='content_block_delta', 
                    delta=Mock(text=f'Chunk {i} ')
                )
                await asyncio.sleep(0.01)  # Simulate streaming delay
            yield Mock(type='message_delta', usage=Mock(output_tokens=1000))
        
        analyzer._client = Mock()
        analyzer._client.messages.create = AsyncMock(return_value=mock_stream())
        
        # Measure time
        start_time = asyncio.get_event_loop().time()
        chunks_received = 0
        
        async for _ in analyzer.analyze_anr_async(large_anr_log, AnalysisMode.QUICK):
            chunks_received += 1
        
        elapsed_time = asyncio.get_event_loop().time() - start_time
        
        # Assert
        assert chunks_received == 10
        assert elapsed_time < 1.0  # Should complete within 1 second
        
        # Check token count for large input
        status = status_manager.get_status()
        assert status['api_usage']['input_tokens'] >= 5000