"""
Anthropic API 配置
"""
from typing import Dict
from .base import BaseApiConfig, ModelConfig, AnalysisMode

class AnthropicApiConfig(BaseApiConfig):
    """Anthropic API 配置"""
    
    base_url: str = "https://api.anthropic.com"
    api_version: str = "2023-06-01"
    
    # Anthropic 模型配置 - 修正價格單位（每 1k tokens）
    models: Dict[str, ModelConfig] = {
        # Claude 3.5 系列
        "claude-3-5-haiku-20241022": ModelConfig(
            name="claude-3-5-haiku-20241022",
            max_tokens=8192,
            input_cost_per_1k=0.00025,   # $0.25 per million = $0.00025 per 1k
            output_cost_per_1k=0.00125,  # $1.25 per million = $0.00125 per 1k
            context_window=200000,
            supports_streaming=True
        ),
        "claude-3-5-sonnet-20241022": ModelConfig(
            name="claude-3-5-sonnet-20241022",
            max_tokens=8192,
            input_cost_per_1k=0.003,     # $3 per million = $0.003 per 1k
            output_cost_per_1k=0.015,    # $15 per million = $0.015 per 1k
            context_window=200000,
            supports_streaming=True
        ),
        
        # Claude 4 系列 (假設的價格，實際請參考官方)
        "claude-sonnet-4-20250514": ModelConfig(
            name="claude-sonnet-4-20250514",
            max_tokens=16000,
            input_cost_per_1k=0.005,     # $5 per million = $0.005 per 1k
            output_cost_per_1k=0.025,    # $25 per million = $0.025 per 1k
            context_window=200000,
            supports_streaming=True
        ),
        "claude-opus-4-20250514": ModelConfig(
            name="claude-opus-4-20250514",
            max_tokens=32000,
            input_cost_per_1k=0.015,     # $15 per million = $0.015 per 1k
            output_cost_per_1k=0.075,    # $75 per million = $0.075 per 1k
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
    
    def calculate_api_calls(self, file_size_kb: float, mode: AnalysisMode) -> int:
        """計算需要的 API 調用次數"""
        # 估算總 tokens
        chars = file_size_kb * 1024
        total_tokens = int(chars / 2.5)  # 平均 2.5 字符/token
        
        model = self.get_model_for_mode(mode)
        model_config = self.get_model_config(model)
        
        # 根據模式調整有效 context window
        mode_context_ratio = {
            AnalysisMode.QUICK: 0.9,
            AnalysisMode.INTELLIGENT: 0.7,
            AnalysisMode.LARGE_FILE: 0.6,
            AnalysisMode.MAX_TOKEN: 0.5
        }
        
        ratio = mode_context_ratio.get(mode, 0.7)
        effective_context = int(model_config.context_window * ratio)
        
        # 計算 API 調用次數
        return max(1, (total_tokens + effective_context - 1) // effective_context)
    
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

    def get_model_context_window(self, model: str) -> int:
        """獲取模型的 context window"""
        if model in self.models:
            return self.models[model].context_window
        return 200000  # 預設值