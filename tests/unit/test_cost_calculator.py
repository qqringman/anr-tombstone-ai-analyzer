"""
Unit tests for cost calculator
"""
import pytest
from unittest.mock import Mock, patch

from utils.cost_calculator import CostCalculator, ModelCostInfo
from config.base import AnalysisMode, ModelProvider


class TestCostCalculator:
    """Test cost calculator functionality"""
    
    @pytest.fixture
    def calculator(self):
        """Create cost calculator instance"""
        return CostCalculator()
    
    def test_initialization(self, calculator):
        """Test calculator initialization"""
        # Check that model costs are loaded
        assert len(calculator.model_costs) > 0
        
        # Check specific models exist
        assert "gpt-4o" in calculator.model_costs
        assert "gpt-4o-mini" in calculator.model_costs
        assert "claude-3-5-sonnet-20241022" in calculator.model_costs
        assert "claude-3-5-haiku-20241022" in calculator.model_costs
    
    def test_model_cost_info(self):
        """Test ModelCostInfo dataclass"""
        cost_info = ModelCostInfo(
            model_name="test-model",
            provider=ModelProvider.OPENAI,
            input_cost_per_million=1.0,
            output_cost_per_million=2.0,
            context_window=128000,
            max_output_tokens=4096
        )
        
        assert cost_info.model_name == "test-model"
        assert cost_info.provider == ModelProvider.OPENAI
        assert cost_info.input_cost_per_million == 1.0
        assert cost_info.output_cost_per_million == 2.0
    
    def test_estimate_tokens_from_text(self, calculator):
        """Test token estimation from text"""
        # Test English text
        text = "Hello world! This is a test message."
        tokens = calculator.estimate_tokens_from_text(text)
        assert 5 <= tokens <= 15  # Reasonable range for this text
        
        # Test Chinese text
        chinese_text = "你好世界！這是一個測試消息。"
        tokens = calculator.estimate_tokens_from_text(chinese_text)
        assert 10 <= tokens <= 20  # Chinese typically uses more tokens
        
        # Test empty text
        assert calculator.estimate_tokens_from_text("") == 0
        
        # Test long text
        long_text = "word " * 1000
        tokens = calculator.estimate_tokens_from_text(long_text)
        assert 900 <= tokens <= 1100  # Close to word count
    
    def test_estimate_tokens_from_file_size(self, calculator):
        """Test token estimation from file size"""
        # Test small file
        tokens = calculator.estimate_tokens_from_file_size(1.0)  # 1KB
        assert 200 <= tokens <= 300
        
        # Test medium file
        tokens = calculator.estimate_tokens_from_file_size(10.0)  # 10KB
        assert 2000 <= tokens <= 3000
        
        # Test large file
        tokens = calculator.estimate_tokens_from_file_size(100.0)  # 100KB
        assert 20000 <= tokens <= 30000
        
        # Test zero size
        assert calculator.estimate_tokens_from_file_size(0) == 0
    
    def test_calculate_single_model_cost(self, calculator):
        """Test single model cost calculation"""
        # Test GPT-4o
        cost_estimate = calculator.calculate_single_model_cost(
            "gpt-4o",
            input_tokens=1000,
            output_tokens=500
        )
        
        assert cost_estimate['model'] == "gpt-4o"
        assert cost_estimate['provider'] == "openai"
        assert cost_estimate['input_tokens'] == 1000
        assert cost_estimate['output_tokens'] == 500
        assert cost_estimate['input_cost'] > 0
        assert cost_estimate['output_cost'] > 0
        assert cost_estimate['total_cost'] == cost_estimate['input_cost'] + cost_estimate['output_cost']
        
        # Test Claude
        cost_estimate = calculator.calculate_single_model_cost(
            "claude-3-5-sonnet-20241022",
            input_tokens=2000,
            output_tokens=1000
        )
        
        assert cost_estimate['model'] == "claude-3-5-sonnet-20241022"
        assert cost_estimate['provider'] == "anthropic"
        assert cost_estimate['total_cost'] > 0
    
    def test_calculate_analysis_cost_by_mode(self, calculator):
        """Test cost calculation by analysis mode"""
        # Test quick mode
        costs = calculator.calculate_analysis_cost(
            file_size_kb=10.0,
            mode=AnalysisMode.QUICK
        )
        
        # Should include both quick mode models
        model_names = [c['model'] for c in costs]
        assert "gpt-4o-mini" in model_names
        assert "claude-3-5-haiku-20241022" in model_names
        
        # Test intelligent mode
        costs = calculator.calculate_analysis_cost(
            file_size_kb=10.0,
            mode=AnalysisMode.INTELLIGENT
        )
        
        # Should include intelligent mode models
        model_names = [c['model'] for c in costs]
        assert "gpt-4o" in model_names
        assert any("sonnet" in name for name in model_names)
    
    def test_compare_models_cost(self, calculator):
        """Test model cost comparison"""
        comparisons = calculator.compare_models_cost(
            file_size_kb=5.0,
            mode=AnalysisMode.QUICK
        )
        
        # Should be sorted by total cost
        costs = [c['total_cost'] for c in comparisons]
        assert costs == sorted(costs)
        
        # Each comparison should have all required fields
        for comp in comparisons:
            assert 'model' in comp
            assert 'provider' in comp
            assert 'total_cost' in comp
            assert 'cost_per_1k_tokens' in comp
            assert 'relative_cost' in comp
            assert 'analysis_time_estimate' in comp
        
        # Relative cost of cheapest should be 1.0
        assert comparisons[0]['relative_cost'] == 1.0
    
    def test_get_budget_recommendations(self, calculator):
        """Test budget recommendations"""
        recommendations = calculator.get_budget_recommendations(
            budget_usd=10.0,
            file_size_kb=50.0
        )
        
        assert 'budget' in recommendations
        assert 'estimated_tokens' in recommendations
        assert 'recommendations' in recommendations
        
        # Should have recommendations for different modes
        assert 'quick' in recommendations['recommendations']
        assert 'intelligent' in recommendations['recommendations']
        
        # Each recommendation should have model info
        quick_rec = recommendations['recommendations']['quick']
        assert 'model' in quick_rec
        assert 'analyses_possible' in quick_rec
        assert 'cost_per_analysis' in quick_rec
    
    def test_estimate_analysis_time(self, calculator):
        """Test analysis time estimation"""
        # Small file, quick mode
        time_est = calculator.estimate_analysis_time(
            file_size_kb=1.0,
            mode=AnalysisMode.QUICK
        )
        assert 0.1 <= time_est <= 1.0  # Should be fast
        
        # Large file, intelligent mode
        time_est = calculator.estimate_analysis_time(
            file_size_kb=100.0,
            mode=AnalysisMode.INTELLIGENT
        )
        assert 2.0 <= time_est <= 10.0  # Should take longer
        
        # Test with custom tokens
        time_est = calculator.estimate_analysis_time(
            file_size_kb=10.0,
            mode=AnalysisMode.QUICK,
            estimated_tokens=5000
        )
        assert time_est > 0
    
    def test_format_cost_breakdown(self, calculator):
        """Test cost breakdown formatting"""
        breakdown = calculator.format_cost_breakdown(
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500
        )
        
        assert isinstance(breakdown, str)
        assert "gpt-4o" in breakdown
        assert "Input" in breakdown
        assert "Output" in breakdown
        assert "Total" in breakdown
        assert "$" in breakdown  # Should include currency symbol
    
    def test_get_cheapest_model(self, calculator):
        """Test getting cheapest model"""
        # Test for quick mode
        cheapest = calculator.get_cheapest_model(AnalysisMode.QUICK)
        assert cheapest is not None
        assert cheapest['model'] in ["gpt-4o-mini", "claude-3-5-haiku-20241022"]
        
        # Test for intelligent mode
        cheapest = calculator.get_cheapest_model(AnalysisMode.INTELLIGENT)
        assert cheapest is not None
        assert cheapest['model'] in ["gpt-4o", "claude-3-5-sonnet-20241022", "claude-sonnet-4-20250514"]
    
    def test_validate_token_count(self, calculator):
        """Test token count validation"""
        # Test within limits
        is_valid, message = calculator.validate_token_count(
            "gpt-4o",
            input_tokens=50000
        )
        assert is_valid is True
        
        # Test exceeding limits
        is_valid, message = calculator.validate_token_count(
            "gpt-4o",
            input_tokens=200000  # Exceeds context window
        )
        assert is_valid is False
        assert "exceeds" in message.lower()
        
        # Test unknown model
        is_valid, message = calculator.validate_token_count(
            "unknown-model",
            input_tokens=1000
        )
        assert is_valid is True  # Should pass for unknown models
    
    def test_cost_calculation_accuracy(self, calculator):
        """Test cost calculation accuracy"""
        # GPT-4o-mini: $0.15/$0.60 per million
        cost = calculator.calculate_single_model_cost(
            "gpt-4o-mini",
            input_tokens=1_000_000,
            output_tokens=1_000_000
        )
        
        expected_total = 0.15 + 0.60  # $0.75
        assert abs(cost['total_cost'] - expected_total) < 0.001
        
        # Claude-3-5-haiku: $1.00/$5.00 per million
        cost = calculator.calculate_single_model_cost(
            "claude-3-5-haiku-20241022",
            input_tokens=1_000_000,
            output_tokens=1_000_000
        )
        
        expected_total = 1.00 + 5.00  # $6.00
        assert abs(cost['total_cost'] - expected_total) < 0.001
    
    def test_batch_cost_estimation(self, calculator):
        """Test batch processing cost estimation"""
        # Simulate batch of files
        file_sizes = [5.0, 10.0, 15.0, 20.0]  # KB
        total_cost = 0
        
        for size in file_sizes:
            costs = calculator.calculate_analysis_cost(
                file_size_kb=size,
                mode=AnalysisMode.QUICK
            )
            # Get cheapest option
            total_cost += min(c['total_cost'] for c in costs)
        
        assert total_cost > 0
        assert total_cost < 1.0  # Should be reasonable for quick mode
    
    def test_cost_with_custom_output_ratio(self, calculator):
        """Test cost calculation with custom output ratio"""
        # Test with high output ratio (like detailed analysis)
        input_tokens = 1000
        output_tokens = 3000  # 3:1 output ratio
        
        cost = calculator.calculate_single_model_cost(
            "gpt-4o",
            input_tokens=input_tokens,
            output_tokens=output_tokens
        )
        
        # Output cost should be significantly higher
        assert cost['output_cost'] > cost['input_cost'] * 2
    
    @patch('utils.cost_calculator.CostCalculator._load_model_costs')
    def test_custom_model_costs(self, mock_load):
        """Test with custom model costs"""
        # Mock custom model costs
        mock_load.return_value = {
            "custom-model": ModelCostInfo(
                model_name="custom-model",
                provider=ModelProvider.OPENAI,
                input_cost_per_million=10.0,
                output_cost_per_million=20.0,
                context_window=32000,
                max_output_tokens=4096
            )
        }
        
        calculator = CostCalculator()
        
        cost = calculator.calculate_single_model_cost(
            "custom-model",
            input_tokens=1000,
            output_tokens=1000
        )
        
        expected_total = (10.0 * 1000 + 20.0 * 1000) / 1_000_000
        assert abs(cost['total_cost'] - expected_total) < 0.001