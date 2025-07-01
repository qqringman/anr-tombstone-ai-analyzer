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
    
    def get_model_config(self, model: str) -> ModelConfig:
        """
        獲取模型配置
        
        Args:
            model: 模型名稱
            
        Returns:
            模型配置對象
        """
        if model not in self.models:
            raise ValueError(f"Unknown model: {model}")
        
        return self.models[model]
    
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
        """
        估算文本的 token 數量
        
        Args:
            text: 文本內容
            
        Returns:
            估算的 token 數
        """
        if not text:
            return 0
        
        # 使用更準確的估算方法
        # 對於英文：平均每個 token 約 4 個字符
        # 對於中文：平均每個字符約 2 個 tokens
        
        # 簡單估算：計算中英文字符
        chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
        other_chars = len(text) - chinese_chars
        
        # 中文字符 * 2 + 其他字符 / 4
        estimated_tokens = chinese_chars * 2 + other_chars / 4
        
        # 添加 10% 的緩衝
        return int(estimated_tokens * 1.1)
    
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