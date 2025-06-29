"""
基礎配置類別
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, List
from pydantic import BaseModel, Field
from enum import Enum

class ModelProvider(Enum):
    """模型提供者"""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"

class AnalysisMode(Enum):
    """分析模式"""
    QUICK = "quick"
    INTELLIGENT = "intelligent"
    LARGE_FILE = "large_file"
    MAX_TOKEN = "max_token"

class ModelConfig(BaseModel):
    """模型配置"""
    name: str
    max_tokens: int
    input_cost_per_1k: float
    output_cost_per_1k: float
    context_window: int
    supports_streaming: bool = True
    supports_function_calling: bool = False

class BaseApiConfig(BaseModel, ABC):
    """API 配置基類"""
    api_key: Optional[str] = Field(None, description="API Key")
    base_url: Optional[str] = Field(None, description="Base URL")
    timeout: int = Field(300, description="Request timeout in seconds")
    max_retries: int = Field(3, description="Maximum retry attempts")
    retry_delay: float = Field(1.0, description="Delay between retries")
    
    # Rate limiting
    requests_per_minute: int = Field(60, description="Requests per minute limit")
    tokens_per_minute: int = Field(150000, description="Tokens per minute limit")
    
    # Model configurations
    models: Dict[str, ModelConfig] = Field(default_factory=dict)
    default_model: Optional[str] = None
    
    @abstractmethod
    def get_model_for_mode(self, mode: AnalysisMode) -> str:
        """根據分析模式獲取模型名稱"""
        pass
    
    @abstractmethod
    def get_model_config(self, model_name: str) -> ModelConfig:
        """獲取模型配置"""
        pass
    
    def calculate_cost(self, input_tokens: int, output_tokens: int, model_name: str) -> float:
        """計算成本"""
        config = self.get_model_config(model_name)
        input_cost = (input_tokens / 1000) * config.input_cost_per_1k
        output_cost = (output_tokens / 1000) * config.output_cost_per_1k
        return input_cost + output_cost
    
    def validate_token_limit(self, tokens: int, model_name: str) -> bool:
        """驗證 token 限制"""
        config = self.get_model_config(model_name)
        return tokens <= config.context_window
    
    class Config:
        """Pydantic 配置"""
        use_enum_values = True
        validate_assignment = True

class ProviderConfig(BaseModel):
    """提供者配置"""
    enabled: bool = True
    priority: int = 0  # 優先級，數字越小優先級越高
    fallback_provider: Optional[str] = None
    mode_overrides: Dict[str, str] = Field(default_factory=dict)  # 模式對應的模型覆蓋

class SystemLimits(BaseModel):
    """系統限制配置"""
    max_file_size_mb: float = 20.0
    max_tokens_per_request: int = 200000
    default_budget_usd: float = 10.0
    request_timeout_seconds: int = 300
    max_concurrent_analyses: int = 5
    max_queue_size: int = 100
    
class CacheConfig(BaseModel):
    """快取配置"""
    enabled: bool = True
    ttl_hours: int = 24
    max_memory_items: int = 100
    directory: str = ".cache/ai_analysis"
    
class LoggingConfig(BaseModel):
    """日誌配置"""
    level: str = "INFO"
    directory: str = "logs"
    max_file_size_mb: int = 10
    backup_count: int = 5
    format: str = "json"  # json or text
    
class DatabaseConfig(BaseModel):
    """資料庫配置"""
    url: str = "sqlite:///data/analysis.db"
    pool_size: int = 5
    max_overflow: int = 10
    echo: bool = False
    
class RateLimitConfig(BaseModel):
    """速率限制配置"""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_size: int = 10
    
class ModelPreferences(BaseModel):
    """模型偏好設定"""
    default_provider: str = "anthropic"
    fallback_provider: str = "openai"
    mode_overrides: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    
class MonitoringConfig(BaseModel):
    """監控配置"""
    health_check_interval: int = 300  # seconds
    metrics_enabled: bool = True
    metrics_port: int = 9090
    alert_webhooks: List[str] = Field(default_factory=list)