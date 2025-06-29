"""
系統配置
"""
import os
from typing import Dict, Optional, Any
from pathlib import Path
import yaml
from pydantic import BaseModel, Field, validator
from dotenv import load_dotenv

from .base import (
    SystemLimits, CacheConfig, LoggingConfig, 
    DatabaseConfig, RateLimitConfig, ModelPreferences, 
    MonitoringConfig
)

# 載入環境變數
load_dotenv()

class ApiKeys(BaseModel):
    """API 金鑰配置"""
    anthropic: Optional[str] = Field(None, description="Anthropic API Key")
    openai: Optional[str] = Field(None, description="OpenAI API Key")
    
    @validator('anthropic', 'openai', pre=True)
    def load_from_env(cls, v, field):
        """從環境變數載入 API Key"""
        if v is None:
            env_key = f"{field.name.upper()}_API_KEY"
            v = os.getenv(env_key)
        return v

class SystemInfo(BaseModel):
    """系統資訊"""
    name: str = "ANR/Tombstone AI Analyzer"
    version: str = "1.0.0"
    environment: str = Field("development", description="development, staging, production")
    
    @validator('environment', pre=True)
    def load_environment(cls, v):
        """從環境變數載入環境設定"""
        return os.getenv('ENVIRONMENT', v)

class SystemConfig(BaseModel):
    """完整系統配置"""
    system: SystemInfo = Field(default_factory=SystemInfo)
    api_keys: ApiKeys = Field(default_factory=ApiKeys)
    limits: SystemLimits = Field(default_factory=SystemLimits)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    rate_limits: RateLimitConfig = Field(default_factory=RateLimitConfig)
    model_preferences: ModelPreferences = Field(default_factory=ModelPreferences)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    
    @classmethod
    def from_yaml(cls, config_path: str) -> 'SystemConfig':
        """從 YAML 檔案載入配置"""
        path = Path(config_path)
        if not path.exists():
            # 如果配置檔案不存在，使用預設值
            return cls()
        
        with open(path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f) or {}
        
        # 合併環境變數
        config_data = cls._merge_env_vars(config_data)
        
        return cls(**config_data)
    
    @classmethod
    def from_env(cls) -> 'SystemConfig':
        """僅從環境變數載入配置"""
        return cls()
    
    @staticmethod
    def _merge_env_vars(config_data: Dict[str, Any]) -> Dict[str, Any]:
        """合併環境變數到配置"""
        # API Keys
        if 'api_keys' not in config_data:
            config_data['api_keys'] = {}
        
        for key in ['anthropic', 'openai']:
            env_key = f"{key.upper()}_API_KEY"
            if os.getenv(env_key):
                config_data['api_keys'][key] = os.getenv(env_key)
        
        # Database URL
        if os.getenv('DATABASE_URL'):
            if 'database' not in config_data:
                config_data['database'] = {}
            config_data['database']['url'] = os.getenv('DATABASE_URL')
        
        # Environment
        if os.getenv('ENVIRONMENT'):
            if 'system' not in config_data:
                config_data['system'] = {}
            config_data['system']['environment'] = os.getenv('ENVIRONMENT')
        
        return config_data
    
    def to_yaml(self, output_path: str):
        """將配置保存為 YAML 檔案"""
        config_dict = self.dict(exclude_unset=True)
        
        # 移除敏感資訊
        if 'api_keys' in config_dict:
            for key in config_dict['api_keys']:
                if config_dict['api_keys'][key]:
                    config_dict['api_keys'][key] = f"${{{key.upper()}_API_KEY}}"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)
    
    def validate_config(self) -> tuple[bool, list[str]]:
        """驗證配置是否完整"""
        errors = []
        
        # 檢查至少有一個 API Key
        if not self.api_keys.anthropic and not self.api_keys.openai:
            errors.append("至少需要配置一個 API Key (Anthropic 或 OpenAI)")
        
        # 檢查預設提供者
        if self.model_preferences.default_provider == "anthropic" and not self.api_keys.anthropic:
            errors.append("預設提供者設為 Anthropic，但未配置 Anthropic API Key")
        elif self.model_preferences.default_provider == "openai" and not self.api_keys.openai:
            errors.append("預設提供者設為 OpenAI，但未配置 OpenAI API Key")
        
        # 檢查檔案大小限制
        if self.limits.max_file_size_mb <= 0:
            errors.append("最大檔案大小必須大於 0")
        
        # 檢查並行分析數量
        if self.limits.max_concurrent_analyses <= 0:
            errors.append("最大並行分析數量必須大於 0")
        
        return len(errors) == 0, errors
    
    def get_available_providers(self) -> list[str]:
        """獲取可用的 AI 提供者"""
        providers = []
        if self.api_keys.anthropic:
            providers.append("anthropic")
        if self.api_keys.openai:
            providers.append("openai")
        return providers
    
    def is_production(self) -> bool:
        """是否為生產環境"""
        return self.system.environment == "production"
    
    def is_development(self) -> bool:
        """是否為開發環境"""
        return self.system.environment == "development"
    
    class Config:
        """Pydantic 配置"""
        validate_assignment = True
        use_enum_values = True

# 全局配置實例
_global_config: Optional[SystemConfig] = None

def get_system_config() -> SystemConfig:
    """獲取全局系統配置"""
    global _global_config
    if _global_config is None:
        # 嘗試從預設位置載入
        config_path = os.getenv('CONFIG_PATH', 'config.yaml')
        if os.path.exists(config_path):
            _global_config = SystemConfig.from_yaml(config_path)
        else:
            _global_config = SystemConfig.from_env()
    return _global_config

def set_system_config(config: SystemConfig):
    """設定全局系統配置"""
    global _global_config
    _global_config = config