"""
Anthropic API 配置
"""
from typing import Dict
from .base import BaseApiConfig, ModelConfig, AnalysisMode

class AnthropicApiConfig(BaseApiConfig):
    """Anthropic API 配置"""
    
    base_url: str = "https://api.anthropic.com"
    api_version: str = "2023-06-01"
    
    # Anthropic 模型配置
    models: Dict[str, ModelConfig] = {
        # Claude 3.5 系列
        "claude-3-5-haiku-20241022": ModelConfig(
            name="claude-3-5-haiku-20241022",
            max_tokens=8192,
            input_cost_per_1k=1.0,
            output_cost_per_1k=5.0,
            context_window=200000,
            supports_streaming=True
        ),
        "claude-3-5-sonnet-20241022": ModelConfig(
            name="claude-3-5-sonnet-20241022",
            max_tokens=8192,
            input_cost_per_1k=3.0,
            output_cost_per_1k=15.0,
            context_window=200000,
            supports_streaming=True
        ),
        
        # Claude 4 系列 (假設的價格，實際請參考官方)
        "claude-sonnet-4-20250514": ModelConfig(
            name="claude-sonnet-4-20250514",
            max_tokens=16000,
            input_cost_per_1k=5.0,
            output_cost_per_1k=25.0,
            context_window=200000,
            supports_streaming=True
        ),
        "claude-opus-4-20250514": ModelConfig(
            name="claude-opus-4-20250514",
            max_tokens=32000,
            input_cost_per_1k=15.0,
            output_cost_per_1k=75.0,
            context_window=200000,
            supports_streaming=True
        )
    }
    
    default_model: str = "claude-sonnet-4-20250514"
    
    # 模式對應的模型
    mode_model_mapping: Dict[AnalysisMode, str] = {
        AnalysisMode.QUICK: "claude-3-5-haiku-20241022",
        AnalysisMode.INTELLIGENT: "claude-sonnet-4-20250514",
        AnalysisMode.LARGE_FILE: "claude-sonnet-4-20250514",
        AnalysisMode.MAX_TOKEN: "claude-opus-4-20250514"
    }
    
    # Anthropic 特定設定
    max_tokens_to_sample: int = 8192
    temperature: float = 0.3
    top_p: float = 0.95
    stop_sequences: list[str] = []
    
    def get_model_for_mode(self, mode: AnalysisMode) -> str:
        """根據分析模式獲取模型名稱"""
        return self.mode_model_mapping.get(mode, self.default_model)
    
    def get_model_config(self, model_name: str) -> ModelConfig:
        """獲取模型配置"""
        if model_name not in self.models:
            raise ValueError(f"Unknown model: {model_name}")
        return self.models[model_name]
    
    def get_headers(self) -> Dict[str, str]:
        """獲取請求標頭"""
        return {
            "x-api-key": self.api_key,
            "anthropic-version": self.api_version,
            "content-type": "application/json"
        }
    
    def get_tier_models(self, tier: int) -> list[str]:
        """根據層級獲取模型列表"""
        tier_mapping = {
            2: ["claude-3-5-haiku-20241022"],
            3: ["claude-3-5-sonnet-20241022", "claude-sonnet-4-20250514"],
            4: ["claude-opus-4-20250514"]
        }
        return tier_mapping.get(tier, [])
    
    def estimate_tokens(self, text: str) -> int:
        """估算文本的 token 數量"""
        # Anthropic 的 token 估算：大約每個字符 0.4 個 token
        return int(len(text) * 0.4)
    
    def chunk_text(self, text: str, mode: AnalysisMode) -> list[str]:
        """根據模式切分文本"""
        chunk_sizes = {
            AnalysisMode.QUICK: 50000,
            AnalysisMode.INTELLIGENT: 150000,
            AnalysisMode.LARGE_FILE: 200000,
            AnalysisMode.MAX_TOKEN: 180000
        }
        
        chunk_size = chunk_sizes.get(mode, 150000)
        chunks = []
        
        for i in range(0, len(text), chunk_size):
            chunks.append(text[i:i + chunk_size])
        
        return chunks