"""
Unit tests for configuration modules
"""
import pytest
import os
import tempfile
from pathlib import Path
import yaml

from config.system_config import SystemConfig
from config.base import BaseApiConfig, AnalysisMode, ModelProvider
from config.anthropic_config import AnthropicApiConfig
from config.openai_config import OpenApiConfig


class TestSystemConfig:
    """Test system configuration"""
    
    def test_default_configuration(self):
        """Test default configuration values"""
        config = SystemConfig()
        
        # Test system defaults
        assert config.system.name == "ANR/Tombstone AI Analyzer"
        assert config.system.environment == "development"
        
        # Test limits
        assert config.limits.max_file_size_mb == 20
        assert config.limits.max_tokens_per_request == 200000
        assert config.limits.default_budget_usd == 10.0
        
        # Test cache
        assert config.cache.enabled is True
        assert config.cache.ttl_hours == 24
        
        # Test logging
        assert config.logging.level == "INFO"
        assert config.logging.format == "json"
    
    def test_load_from_yaml(self, temp_dir):
        """Test loading configuration from YAML file"""
        # Create test config file
        config_data = {
            'system': {
                'name': 'Test System',
                'version': '2.0.0',
                'environment': 'production'
            },
            'api_keys': {
                'anthropic': 'test_key_1',
                'openai': 'test_key_2'
            },
            'limits': {
                'max_file_size_mb': 50
            }
        }
        
        config_file = temp_dir / 'test_config.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        # Load configuration
        config = SystemConfig.from_yaml(str(config_file))
        
        # Assert
        assert config.system.name == 'Test System'
        assert config.system.version == '2.0.0'
        assert config.system.environment == 'production'
        assert config.api_keys.anthropic == 'test_key_1'
        assert config.api_keys.openai == 'test_key_2'
        assert config.limits.max_file_size_mb == 50
    
    def test_environment_variable_override(self):
        """Test environment variable override"""
        # Set environment variables
        os.environ['ANTHROPIC_API_KEY'] = 'env_anthropic_key'
        os.environ['OPENAI_API_KEY'] = 'env_openai_key'
        os.environ['ENVIRONMENT'] = 'staging'
        
        # Create config
        config = SystemConfig()
        
        # Environment variables should override defaults
        assert config.api_keys.anthropic == 'env_anthropic_key'
        assert config.api_keys.openai == 'env_openai_key'
        assert config.system.environment == 'staging'
    
    def test_config_validation(self):
        """Test configuration validation"""
        config = SystemConfig()
        
        # Valid configuration
        is_valid, errors = config.validate_config()
        assert is_valid is True
        assert len(errors) == 0
        
        # Invalid configuration - negative values
        config.limits.max_file_size_mb = -1
        config.limits.request_timeout_seconds = 0
        
        is_valid, errors = config.validate_config()
        assert is_valid is False
        assert len(errors) > 0
        assert any('max_file_size_mb' in error for error in errors)
        assert any('timeout' in error for error in errors)
    
    def test_model_preferences(self):
        """Test model preference configuration"""
        config = SystemConfig()
        
        # Test default provider
        assert config.model_preferences.default_provider == "anthropic"
        assert config.model_preferences.fallback_provider == "openai"
        
        # Test mode overrides
        quick_models = config.model_preferences.mode_overrides.get('quick', {})
        assert 'anthropic' in quick_models
        assert 'openai' in quick_models
        
        intelligent_models = config.model_preferences.mode_overrides.get('intelligent', {})
        assert 'anthropic' in intelligent_models
        assert 'openai' in intelligent_models
    
    def test_rate_limits(self):
        """Test rate limit configuration"""
        config = SystemConfig()
        
        assert config.rate_limits.requests_per_minute == 60
        assert config.rate_limits.requests_per_hour == 1000
        assert config.rate_limits.burst_size == 10
    
    def test_database_configuration(self):
        """Test database configuration"""
        config = SystemConfig()
        
        # Default SQLite
        assert 'sqlite:///' in config.database.url
        
        # Test with environment variable
        os.environ['DATABASE_URL'] = 'postgresql://user:pass@localhost/db'
        config = SystemConfig()
        assert config.database.url == 'postgresql://user:pass@localhost/db'
    
    def test_to_dict_method(self):
        """Test converting config to dictionary"""
        config = SystemConfig()
        config_dict = config.dict()
        
        assert isinstance(config_dict, dict)
        assert 'system' in config_dict
        assert 'api_keys' in config_dict
        assert 'limits' in config_dict
        assert 'cache' in config_dict
        
        # Check nested structure
        assert config_dict['system']['name'] == config.system.name
        assert config_dict['limits']['max_file_size_mb'] == config.limits.max_file_size_mb


class TestAnthropicApiConfig:
    """Test Anthropic API configuration"""
    
    def test_default_values(self):
        """Test default configuration values"""
        config = AnthropicApiConfig()
        
        assert config.base_url == "https://api.anthropic.com"
        assert config.api_version == "2023-06-01"
        assert config.default_model == "claude-3-5-sonnet-20241022"
        assert config.max_tokens == 4096
        assert config.temperature == 0.3
    
    def test_model_selection(self):
        """Test model selection for different modes"""
        config = AnthropicApiConfig()
        
        # Quick mode
        assert config.get_model_for_mode(AnalysisMode.QUICK) == "claude-3-5-haiku-20241022"
        
        # Intelligent mode
        assert config.get_model_for_mode(AnalysisMode.INTELLIGENT) == "claude-sonnet-4-20250514"
    
    def test_cost_calculation(self):
        """Test cost calculation"""
        config = AnthropicApiConfig()
        
        # Test with Haiku model
        cost = config.calculate_cost(
            model="claude-3-5-haiku-20241022",
            input_tokens=1000,
            output_tokens=500
        )
        expected_cost = (1000 * 1.00 + 500 * 5.00) / 1_000_000
        assert cost == pytest.approx(expected_cost, rel=1e-6)
        
        # Test with Sonnet model
        cost = config.calculate_cost(
            model="claude-3-5-sonnet-20241022",
            input_tokens=1000,
            output_tokens=500
        )
        expected_cost = (1000 * 3.00 + 500 * 15.00) / 1_000_000
        assert cost == pytest.approx(expected_cost, rel=1e-6)
    
    def test_api_key_validation(self):
        """Test API key validation"""
        config = AnthropicApiConfig()
        
        # No API key
        config.api_key = None
        is_valid, errors = config.validate()
        assert is_valid is False
        assert any('API key' in error for error in errors)
        
        # Valid API key
        config.api_key = "sk-ant-test-key"
        is_valid, errors = config.validate()
        assert is_valid is True
        assert len(errors) == 0
    
    def test_headers_generation(self):
        """Test API headers generation"""
        config = AnthropicApiConfig()
        config.api_key = "test-key"
        
        headers = config.get_headers()
        
        assert headers['x-api-key'] == "test-key"
        assert headers['anthropic-version'] == config.api_version
        assert headers['content-type'] == "application/json"


class TestOpenApiConfig:
    """Test OpenAI API configuration"""
    
    def test_default_values(self):
        """Test default configuration values"""
        config = OpenApiConfig()
        
        assert config.base_url == "https://api.openai.com/v1"
        assert config.default_model == "gpt-4o"
        assert config.max_tokens == 4096
        assert config.temperature == 0.3
    
    def test_model_selection(self):
        """Test model selection for different modes"""
        config = OpenApiConfig()
        
        # Quick mode
        assert config.get_model_for_mode(AnalysisMode.QUICK) == "gpt-4o-mini"
        
        # Intelligent mode
        assert config.get_model_for_mode(AnalysisMode.INTELLIGENT) == "gpt-4o"
    
    def test_cost_calculation(self):
        """Test cost calculation"""
        config = OpenApiConfig()
        
        # Test with GPT-4o-mini
        cost = config.calculate_cost(
            model="gpt-4o-mini",
            input_tokens=1000,
            output_tokens=500
        )
        expected_cost = (1000 * 0.15 + 500 * 0.60) / 1_000_000
        assert cost == pytest.approx(expected_cost, rel=1e-6)
        
        # Test with GPT-4o
        cost = config.calculate_cost(
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500
        )
        expected_cost = (1000 * 2.50 + 500 * 10.00) / 1_000_000
        assert cost == pytest.approx(expected_cost, rel=1e-6)
    
    def test_api_key_validation(self):
        """Test API key validation"""
        config = OpenApiConfig()
        
        # No API key
        config.api_key = None
        is_valid, errors = config.validate()
        assert is_valid is False
        assert any('API key' in error for error in errors)
        
        # Valid API key
        config.api_key = "sk-test-key"
        is_valid, errors = config.validate()
        assert is_valid is True
        assert len(errors) == 0
    
    def test_headers_generation(self):
        """Test API headers generation"""
        config = OpenApiConfig()
        config.api_key = "test-key"
        
        headers = config.get_headers()
        
        assert headers['Authorization'] == "Bearer test-key"
        assert headers['Content-Type'] == "application/json"


class TestBaseApiConfig:
    """Test base API configuration"""
    
    def test_provider_enum(self):
        """Test ModelProvider enum"""
        # Test enum values
        assert ModelProvider.ANTHROPIC.value == "anthropic"
        assert ModelProvider.OPENAI.value == "openai"
        
        # Test enum creation from string
        provider = ModelProvider("anthropic")
        assert provider == ModelProvider.ANTHROPIC
        
        provider = ModelProvider("openai")
        assert provider == ModelProvider.OPENAI
        
        # Test invalid provider
        with pytest.raises(ValueError):
            ModelProvider("invalid_provider")
    
    def test_analysis_mode_enum(self):
        """Test AnalysisMode enum"""
        # Test enum values
        assert AnalysisMode.QUICK.value == "quick"
        assert AnalysisMode.INTELLIGENT.value == "intelligent"
        
        # Test enum creation from string
        mode = AnalysisMode("quick")
        assert mode == AnalysisMode.QUICK
        
        mode = AnalysisMode("intelligent")
        assert mode == AnalysisMode.INTELLIGENT
        
        # Test invalid mode
        with pytest.raises(ValueError):
            AnalysisMode("invalid_mode")
    
    def test_config_inheritance(self):
        """Test configuration inheritance"""
        # Create custom config class
        class CustomApiConfig(BaseApiConfig):
            custom_field: str = "custom_value"
            
            def get_model_for_mode(self, mode: AnalysisMode) -> str:
                return "custom-model"
            
            def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
                return 0.001
        
        # Test custom config
        config = CustomApiConfig()
        assert config.custom_field == "custom_value"
        assert config.get_model_for_mode(AnalysisMode.QUICK) == "custom-model"
        assert config.calculate_cost("any", 1000, 500) == 0.001


class TestConfigurationIntegration:
    """Test configuration integration scenarios"""
    
    def test_multi_provider_setup(self):
        """Test setting up multiple providers"""
        # Create system config
        system_config = SystemConfig()
        system_config.api_keys.anthropic = "anthropic-key"
        system_config.api_keys.openai = "openai-key"
        
        # Create provider configs
        anthropic_config = AnthropicApiConfig()
        anthropic_config.api_key = system_config.api_keys.anthropic
        
        openai_config = OpenApiConfig()
        openai_config.api_key = system_config.api_keys.openai
        
        # Validate both
        anthropic_valid, _ = anthropic_config.validate()
        openai_valid, _ = openai_config.validate()
        
        assert anthropic_valid is True
        assert openai_valid is True
    
    def test_config_file_override_chain(self, temp_dir):
        """Test configuration override chain: defaults -> file -> env"""
        # Create config file
        config_data = {
            'system': {
                'environment': 'staging'
            },
            'limits': {
                'max_file_size_mb': 30
            }
        }
        
        config_file = temp_dir / 'override_test.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        # Set environment variable
        os.environ['ENVIRONMENT'] = 'production'
        
        # Load config
        config = SystemConfig.from_yaml(str(config_file))
        
        # Environment variable should override file
        assert config.system.environment == 'production'
        # File should override default
        assert config.limits.max_file_size_mb == 30
        # Default should remain for unspecified
        assert config.limits.max_tokens_per_request == 200000