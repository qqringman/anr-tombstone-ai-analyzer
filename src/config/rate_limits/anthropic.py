"""
Anthropic Rate Limits 配置
"""
from typing import Dict
from .base import BaseRateLimitsProvider, RateLimitTier, RateLimitConfig

class AnthropicRateLimits(BaseRateLimitsProvider):
    """Anthropic 速率限制配置"""
    
    @property
    def provider_name(self) -> str:
        return "anthropic"
    
    def _define_tiers(self) -> Dict[RateLimitTier, RateLimitConfig]:
        """定義 Anthropic 的速率限制層級"""
        return {
            RateLimitTier.FREE: RateLimitConfig(
                requests_per_minute=5,
                tokens_per_minute=25000,
                requests_per_day=300,
                tokens_per_day=300000
            ),
            RateLimitTier.TIER_1: RateLimitConfig(
                requests_per_minute=50,
                tokens_per_minute=50000,
                requests_per_day=5000,
                tokens_per_day=5000000
            ),
            RateLimitTier.TIER_2: RateLimitConfig(
                requests_per_minute=1000,
                tokens_per_minute=100000,
                requests_per_day=100000,
                tokens_per_day=25000000
            ),
            RateLimitTier.TIER_3: RateLimitConfig(
                requests_per_minute=2000,
                tokens_per_minute=200000,
                requests_per_day=200000,
                tokens_per_day=50000000
            ),
            RateLimitTier.TIER_4: RateLimitConfig(
                requests_per_minute=4000,
                tokens_per_minute=400000,
                concurrent_requests=100,
                # Tier 4 通常沒有每日限制
                model_specific_limits={
                    # Claude 3.5 Haiku 有更高的限制
                    "claude-3-5-haiku-20241022": {
                        "tokens_per_minute": 800000
                    },
                    # Claude Opus 4 較慢但更強大
                    "claude-opus-4-20250514": {
                        "requests_per_minute": 2000,
                        "tokens_per_minute": 300000
                    }
                }
            ),
            RateLimitTier.SCALE: RateLimitConfig(
                requests_per_minute=8000,
                tokens_per_minute=800000,
                concurrent_requests=200
            )
        }
    
    def _get_default_tier(self) -> RateLimitTier:
        """預設使用 Tier 2"""
        return RateLimitTier.TIER_2
    
    def _define_model_multipliers(self) -> Dict[str, float]:
        """定義模型倍率"""
        return {
            # Haiku 模型有更高的處理能力
            "claude-3-5-haiku-20241022": 1.5,
            # Opus 模型較慢
            "claude-opus-4-20250514": 0.7
        }
    
    def get_model_context_limits(self, model: str) -> int:
        """獲取模型的 context window 限制"""
        # Anthropic 大多數模型都是 200k context window
        context_limits = {
            "claude-3-5-haiku-20241022": 200000,
            "claude-3-5-sonnet-20241022": 200000,
            "claude-sonnet-4-20250514": 200000,
            "claude-opus-4-20250514": 200000
        }
        return context_limits.get(model, 200000)