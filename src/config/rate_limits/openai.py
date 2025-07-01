"""
OpenAI Rate Limits 配置
"""
from typing import Dict
from .base import BaseRateLimitsProvider, RateLimitTier, RateLimitConfig

class OpenAIRateLimits(BaseRateLimitsProvider):
    """OpenAI 速率限制配置"""
    
    @property
    def provider_name(self) -> str:
        return "openai"
    
    def _define_tiers(self) -> Dict[RateLimitTier, RateLimitConfig]:
        """定義 OpenAI 的速率限制層級"""
        return {
            RateLimitTier.FREE: RateLimitConfig(
                requests_per_minute=3,
                tokens_per_minute=40000,
                requests_per_day=200,
                tokens_per_day=1000000
            ),
            RateLimitTier.TIER_1: RateLimitConfig(
                requests_per_minute=60,
                tokens_per_minute=60000,
                requests_per_day=3000,
                tokens_per_day=1000000
            ),
            RateLimitTier.TIER_2: RateLimitConfig(
                requests_per_minute=500,
                tokens_per_minute=80000,
                requests_per_day=10000,
                # 模型特定限制
                model_specific_limits={
                    "gpt-4-turbo": {
                        "requests_per_minute": 300,
                        "tokens_per_minute": 60000
                    },
                    "gpt-4o": {
                        "requests_per_minute": 500,
                        "tokens_per_minute": 100000
                    }
                }
            ),
            RateLimitTier.TIER_3: RateLimitConfig(
                requests_per_minute=5000,
                tokens_per_minute=160000
            ),
            RateLimitTier.TIER_4: RateLimitConfig(
                requests_per_minute=5000,
                tokens_per_minute=600000
            ),
            RateLimitTier.TIER_5: RateLimitConfig(
                requests_per_minute=10000,
                tokens_per_minute=800000,
                concurrent_requests=100
            )
        }
    
    def _get_default_tier(self) -> RateLimitTier:
        """預設使用 Tier 1"""
        return RateLimitTier.TIER_1
    
    def _define_model_multipliers(self) -> Dict[str, float]:
        """定義模型倍率"""
        return {
            # GPT-4 系列較慢
            "gpt-4-turbo": 0.6,
            "gpt-4o": 1.0,
            # GPT-3.5 較快
            "gpt-3.5-turbo": 2.0,
            "gpt-4o-mini": 1.5
        }
    
    def get_model_context_limits(self, model: str) -> int:
        """獲取模型的 context window 限制"""
        context_limits = {
            "gpt-4o-mini": 128000,
            "gpt-4o": 128000,
            "gpt-4-turbo": 128000,
            "gpt-3.5-turbo": 16385
        }
        return context_limits.get(model, 128000)