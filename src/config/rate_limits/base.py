"""
Rate Limits 基類
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional, List
from pydantic import BaseModel, Field
from enum import Enum

class RateLimitTier(Enum):
    """速率限制層級"""
    FREE = "free"
    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    TIER_3 = "tier_3"
    TIER_4 = "tier_4"
    SCALE = "scale"
    ENTERPRISE = "enterprise"

class RateLimitConfig(BaseModel):
    """單個速率限制配置"""
    requests_per_minute: int = Field(description="每分鐘請求數限制")
    tokens_per_minute: int = Field(description="每分鐘 token 數限制")
    requests_per_day: Optional[int] = Field(None, description="每日請求數限制")
    tokens_per_day: Optional[int] = Field(None, description="每日 token 數限制")
    concurrent_requests: Optional[int] = Field(None, description="並發請求數限制")
    
    # 模型特定限制
    model_specific_limits: Optional[Dict[str, Dict[str, int]]] = Field(
        None, 
        description="針對特定模型的限制覆寫"
    )

class BaseRateLimitsProvider(ABC):
    """Rate Limits 提供者基類"""
    
    def __init__(self):
        self._tiers = self._define_tiers()
        self._default_tier = self._get_default_tier()
        self._model_multipliers = self._define_model_multipliers()
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """提供者名稱"""
        pass
    
    @abstractmethod
    def _define_tiers(self) -> Dict[RateLimitTier, RateLimitConfig]:
        """定義各層級的速率限制"""
        pass
    
    @abstractmethod
    def _get_default_tier(self) -> RateLimitTier:
        """獲取預設層級"""
        pass
    
    def _define_model_multipliers(self) -> Dict[str, float]:
        """
        定義模型倍率（某些模型可能有不同的限制）
        預設返回空字典，子類可覆寫
        """
        return {}
    
    def get_limits(self, tier: Optional[RateLimitTier] = None, model: Optional[str] = None) -> RateLimitConfig:
        """
        獲取速率限制配置
        
        Args:
            tier: 層級，如果不指定則使用預設
            model: 模型名稱，用於獲取模型特定限制
            
        Returns:
            速率限制配置
        """
        if tier is None:
            tier = self._default_tier
        
        if tier not in self._tiers:
            raise ValueError(f"Unknown tier {tier} for provider {self.provider_name}")
        
        limits = self._tiers[tier].model_copy()
        
        # 應用模型特定的限制
        if model and limits.model_specific_limits and model in limits.model_specific_limits:
            model_limits = limits.model_specific_limits[model]
            for key, value in model_limits.items():
                if hasattr(limits, key):
                    setattr(limits, key, value)
        
        # 應用模型倍率
        if model and model in self._model_multipliers:
            multiplier = self._model_multipliers[model]
            limits.requests_per_minute = int(limits.requests_per_minute * multiplier)
            limits.tokens_per_minute = int(limits.tokens_per_minute * multiplier)
            if limits.requests_per_day:
                limits.requests_per_day = int(limits.requests_per_day * multiplier)
            if limits.tokens_per_day:
                limits.tokens_per_day = int(limits.tokens_per_day * multiplier)
        
        return limits
    
    def get_available_tiers(self) -> List[RateLimitTier]:
        """獲取所有可用層級"""
        return list(self._tiers.keys())
    
    def calculate_time_estimate(self, 
                               total_tokens: int, 
                               queries_needed: int,
                               tier: Optional[RateLimitTier] = None,
                               model: Optional[str] = None) -> Dict[str, float]:
        """
        基於速率限制計算預估時間
        
        Args:
            total_tokens: 總 token 數
            queries_needed: 需要的查詢次數
            tier: 速率層級
            model: 模型名稱
            
        Returns:
            包含各種時間估算的字典
        """
        limits = self.get_limits(tier, model)
        
        # 基於請求數的時間（分鐘）
        time_by_requests = queries_needed / limits.requests_per_minute
        
        # 基於 token 數的時間（分鐘）
        time_by_tokens = total_tokens / limits.tokens_per_minute
        
        # 考慮每日限制
        time_by_daily_requests = 0
        time_by_daily_tokens = 0
        
        if limits.requests_per_day and queries_needed > limits.requests_per_day:
            days_needed = (queries_needed - 1) // limits.requests_per_day + 1
            time_by_daily_requests = (days_needed - 1) * 24 * 60
        
        if limits.tokens_per_day and total_tokens > limits.tokens_per_day:
            days_needed = (total_tokens - 1) // limits.tokens_per_day + 1
            time_by_daily_tokens = (days_needed - 1) * 24 * 60
        
        # 實際時間是所有限制的最大值
        actual_time = max(
            time_by_requests,
            time_by_tokens,
            time_by_daily_requests,
            time_by_daily_tokens
        )
        
        return {
            'time_by_requests': time_by_requests,
            'time_by_tokens': time_by_tokens,
            'time_by_daily_requests': time_by_daily_requests,
            'time_by_daily_tokens': time_by_daily_tokens,
            'actual_time_minutes': actual_time,
            'rate_limiting_factor': self._determine_limiting_factor(
                time_by_requests, time_by_tokens, 
                time_by_daily_requests, time_by_daily_tokens
            )
        }
    
    def _determine_limiting_factor(self, *times) -> str:
        """判斷限制因素"""
        factors = [
            ('requests_per_minute', times[0]),
            ('tokens_per_minute', times[1]),
            ('daily_requests', times[2]),
            ('daily_tokens', times[3])
        ]
        
        # 過濾掉 0 值
        factors = [(name, time) for name, time in factors if time > 0]
        
        if not factors:
            return 'none'
        
        return max(factors, key=lambda x: x[1])[0]
    
    def format_info(self, tier: Optional[RateLimitTier] = None, model: Optional[str] = None) -> str:
        """格式化顯示速率限制資訊"""
        limits = self.get_limits(tier, model)
        tier_name = tier.value if tier else self._default_tier.value
        
        info = [
            f"Provider: {self.provider_name}",
            f"Tier: {tier_name}",
        ]
        
        if model:
            info.append(f"Model: {model}")
        
        info.extend([
            f"Requests/min: {limits.requests_per_minute:,}",
            f"Tokens/min: {limits.tokens_per_minute:,}"
        ])
        
        if limits.requests_per_day:
            info.append(f"Requests/day: {limits.requests_per_day:,}")
        
        if limits.tokens_per_day:
            info.append(f"Tokens/day: {limits.tokens_per_day:,}")
        
        if limits.concurrent_requests:
            info.append(f"Concurrent: {limits.concurrent_requests}")
        
        return "\n".join(info)