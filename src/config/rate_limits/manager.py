"""
Rate Limits 管理器
"""
import os
from typing import Dict, Optional, Type
from .base import BaseRateLimitsProvider, RateLimitTier
from .anthropic import AnthropicRateLimits
from .openai import OpenAIRateLimits

class RateLimitsManager:
    """統一的速率限制管理器"""
    
    # 註冊的提供者
    _providers: Dict[str, Type[BaseRateLimitsProvider]] = {
        "anthropic": AnthropicRateLimits,
        "openai": OpenAIRateLimits
    }
    
    def __init__(self):
        """初始化管理器"""
        self._instances: Dict[str, BaseRateLimitsProvider] = {}
        self._current_tiers: Dict[str, RateLimitTier] = {}
        
        # 從環境變數載入層級設定
        self._load_tier_settings()
    
    def _load_tier_settings(self):
        """從環境變數載入層級設定"""
        for provider_name in self._providers:
            env_key = f"{provider_name.upper()}_RATE_TIER"
            tier_value = os.getenv(env_key)
            
            if tier_value:
                try:
                    tier = RateLimitTier(tier_value)
                    self._current_tiers[provider_name] = tier
                except ValueError:
                    pass
    
    def get_provider(self, provider_name: str) -> BaseRateLimitsProvider:
        """
        獲取提供者實例
        
        Args:
            provider_name: 提供者名稱
            
        Returns:
            提供者實例
        """
        if provider_name not in self._providers:
            raise ValueError(f"Unknown provider: {provider_name}")
        
        if provider_name not in self._instances:
            self._instances[provider_name] = self._providers[provider_name]()
        
        return self._instances[provider_name]
    
    def get_limits(self, 
                   provider: str, 
                   tier: Optional[RateLimitTier] = None,
                   model: Optional[str] = None):
        """
        獲取速率限制
        
        Args:
            provider: 提供者名稱
            tier: 層級（可選）
            model: 模型名稱（可選）
            
        Returns:
            速率限制配置
        """
        provider_instance = self.get_provider(provider)
        
        # 如果沒有指定層級，使用當前設定的層級
        if tier is None and provider in self._current_tiers:
            tier = self._current_tiers[provider]
        
        return provider_instance.get_limits(tier, model)
    
    def calculate_time_estimate(self,
                               provider: str,
                               total_tokens: int,
                               queries_needed: int,
                               tier: Optional[RateLimitTier] = None,
                               model: Optional[str] = None) -> Dict[str, float]:
        """計算時間估算"""
        provider_instance = self.get_provider(provider)
        
        if tier is None and provider in self._current_tiers:
            tier = self._current_tiers[provider]
        
        return provider_instance.calculate_time_estimate(
            total_tokens, queries_needed, tier, model
        )
    
    def set_tier(self, provider: str, tier: RateLimitTier):
        """設定提供者的層級"""
        if provider not in self._providers:
            raise ValueError(f"Unknown provider: {provider}")
        
        self._current_tiers[provider] = tier
    
    def get_current_tier(self, provider: str) -> Optional[RateLimitTier]:
        """獲取當前層級"""
        return self._current_tiers.get(provider)
    
    def register_provider(self, name: str, provider_class: Type[BaseRateLimitsProvider]):
        """註冊新的提供者"""
        self._providers[name] = provider_class
    
    def get_all_providers(self) -> list[str]:
        """獲取所有已註冊的提供者"""
        return list(self._providers.keys())
    
    def suggest_optimal_settings(self,
                                provider: str,
                                file_size_kb: float,
                                desired_time_minutes: float = 10) -> Dict[str, any]:
        """建議最佳設定"""
        from ...utils.cost_calculator import CostCalculator
        from ...config.base import ModelProvider
        
        provider_instance = self.get_provider(provider)
        calculator = CostCalculator()
        
        # 估算 tokens
        provider_enum = ModelProvider(provider)
        input_tokens, output_tokens = calculator.estimate_tokens(file_size_kb, provider_enum)
        total_tokens = input_tokens + output_tokens
        
        # 獲取預設模型
        if provider == "anthropic":
            from ...config.anthropic_config import AnthropicApiConfig
            config = AnthropicApiConfig()
            default_model = config.default_model
        else:
            from ...config.openai_config import OpenApiConfig
            config = OpenApiConfig()
            default_model = config.default_model
        
        # 估算查詢次數
        context_window = provider_instance.get_model_context_limits(default_model)
        effective_context = int(context_window * 0.8)
        queries_needed = max(1, (input_tokens + effective_context - 1) // effective_context)
        
        # 測試各個層級
        suitable_tiers = []
        
        for tier in provider_instance.get_available_tiers():
            time_estimate = provider_instance.calculate_time_estimate(
                total_tokens, queries_needed, tier, default_model
            )
            
            if time_estimate['actual_time_minutes'] <= desired_time_minutes:
                suitable_tiers.append({
                    'tier': tier,
                    'time_minutes': time_estimate['actual_time_minutes'],
                    'limiting_factor': time_estimate['rate_limiting_factor']
                })
        
        if suitable_tiers:
            # 返回最低成本的層級
            best_tier = min(suitable_tiers, key=lambda x: list(RateLimitTier).index(x['tier']))
            return {
                'recommended_tier': best_tier['tier'],
                'estimated_time': best_tier['time_minutes'],
                'limiting_factor': best_tier['limiting_factor'],
                'all_suitable_tiers': suitable_tiers
            }
        else:
            # 沒有合適的層級，返回最高層級
            highest_tier = list(provider_instance.get_available_tiers())[-1]
            time_estimate = provider_instance.calculate_time_estimate(
                total_tokens, queries_needed, highest_tier, default_model
            )
            
            return {
                'recommended_tier': highest_tier,
                'estimated_time': time_estimate['actual_time_minutes'],
                'limiting_factor': time_estimate['rate_limiting_factor'],
                'warning': f'Cannot complete within {desired_time_minutes} minutes',
                'all_suitable_tiers': []
            }

# 全局實例
_rate_limits_manager = None

def get_rate_limits_manager() -> RateLimitsManager:
    """獲取全局速率限制管理器"""
    global _rate_limits_manager
    if _rate_limits_manager is None:
        _rate_limits_manager = RateLimitsManager()
    return _rate_limits_manager