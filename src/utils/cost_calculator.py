"""
成本計算器
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from ..config.base import AnalysisMode, ModelProvider
from ..config.anthropic_config import AnthropicApiConfig
from ..config.openai_config import OpenApiConfig

@dataclass
class ModelCostInfo:
    """模型成本資訊"""
    provider: str
    model: str
    tier: int
    input_cost_per_1k: float
    output_cost_per_1k: float
    context_window: int
    speed_rating: int  # 1-5, 5 最快
    quality_rating: int  # 1-5, 5 最好
    
    @property
    def total_cost_per_1k(self) -> float:
        """每 1K tokens 的總成本"""
        return self.input_cost_per_1k + self.output_cost_per_1k

@dataclass
class CostEstimate:
    """成本估算結果"""
    provider: str
    model: str
    file_size_kb: float
    estimated_input_tokens: int
    estimated_output_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float
    analysis_time_estimate: float  # 分鐘
    is_within_budget: bool
    warnings: List[str]
    api_calls: int = 1  # API 調用次數    

class CostCalculator:
    """成本計算器"""
    
    def __init__(self):
        """初始化成本計算器"""
        # 初始化配置
        self.anthropic_config = AnthropicApiConfig()
        self.openai_config = OpenApiConfig()
        
        # 模型資訊快取
        self._model_info_cache: Dict[str, ModelCostInfo] = {}
        self._init_model_info()
    
    def _init_model_info(self):
        """初始化模型資訊 - 修正價格單位"""
        # Anthropic 模型 (價格從每 million tokens 轉換為每 1k tokens)
        self._model_info_cache.update({
            "claude-3-5-haiku-20241022": ModelCostInfo(
                provider="anthropic",
                model="claude-3-5-haiku-20241022",
                tier=2,
                input_cost_per_1k=0.00025,  # $0.25 per million = $0.00025 per 1k
                output_cost_per_1k=0.00125, # $1.25 per million = $0.00125 per 1k
                context_window=200000,
                speed_rating=5,
                quality_rating=3
            ),
            "claude-3-5-sonnet-20241022": ModelCostInfo(
                provider="anthropic",
                model="claude-3-5-sonnet-20241022",
                tier=3,
                input_cost_per_1k=0.003,   # $3 per million = $0.003 per 1k
                output_cost_per_1k=0.015,  # $15 per million = $0.015 per 1k
                context_window=200000,
                speed_rating=4,
                quality_rating=4
            ),
            "claude-sonnet-4-20250514": ModelCostInfo(
                provider="anthropic",
                model="claude-sonnet-4-20250514",
                tier=3,
                input_cost_per_1k=0.005,   # $5 per million = $0.005 per 1k
                output_cost_per_1k=0.025,  # $25 per million = $0.025 per 1k
                context_window=200000,
                speed_rating=4,
                quality_rating=5
            ),
            "claude-opus-4-20250514": ModelCostInfo(
                provider="anthropic",
                model="claude-opus-4-20250514",
                tier=4,
                input_cost_per_1k=0.015,   # $15 per million = $0.015 per 1k
                output_cost_per_1k=0.075,  # $75 per million = $0.075 per 1k
                context_window=200000,
                speed_rating=3,
                quality_rating=5
            )
        })
        
        # OpenAI 模型 (價格從每 million tokens 轉換為每 1k tokens)
        self._model_info_cache.update({
            "gpt-4o-mini": ModelCostInfo(
                provider="openai",
                model="gpt-4o-mini",
                tier=2,
                input_cost_per_1k=0.00015,  # $0.15 per million = $0.00015 per 1k
                output_cost_per_1k=0.0006,  # $0.60 per million = $0.0006 per 1k
                context_window=128000,
                speed_rating=5,
                quality_rating=3
            ),
            "gpt-4o": ModelCostInfo(
                provider="openai",
                model="gpt-4o",
                tier=3,
                input_cost_per_1k=0.0025,   # $2.50 per million = $0.0025 per 1k
                output_cost_per_1k=0.01,    # $10 per million = $0.01 per 1k
                context_window=128000,
                speed_rating=4,
                quality_rating=4
            ),
            "gpt-4-turbo": ModelCostInfo(
                provider="openai",
                model="gpt-4-turbo",
                tier=4,
                input_cost_per_1k=0.01,     # $10 per million = $0.01 per 1k
                output_cost_per_1k=0.03,    # $30 per million = $0.03 per 1k
                context_window=128000,
                speed_rating=3,
                quality_rating=5
            ),
            "gpt-3.5-turbo": ModelCostInfo(
                provider="openai",
                model="gpt-3.5-turbo",
                tier=1,
                input_cost_per_1k=0.0005,   # $0.50 per million = $0.0005 per 1k
                output_cost_per_1k=0.0015,  # $1.50 per million = $0.0015 per 1k
                context_window=16385,
                speed_rating=5,
                quality_rating=2
            )
        })
    
    def estimate_tokens(self, file_size_kb: float, provider: ModelProvider) -> Tuple[int, int]:
        """
        估算輸入和輸出 tokens
        
        Returns:
            (input_tokens, output_tokens)
        """
        # 轉換為字符數（1KB ≈ 1024 字符）
        chars = file_size_kb * 1024
        
        # 根據 provider 使用不同的估算方式
        if provider == ModelProvider.ANTHROPIC:
            # Claude 的 token 估算
            # 英文：約 4 字符/token，中文：約 2 字符/token
            # 假設混合內容，平均 2.5 字符/token
            input_tokens = int(chars / 2.5)
        else:
            # OpenAI 的 token 估算
            # 使用 GPT 的標準：約 4 字符/token
            input_tokens = int(chars / 4)
        
        # 輸出 tokens 估算：根據分析模式調整
        output_ratio = {
            AnalysisMode.QUICK: 0.2,      # 快速模式：輸出較少
            AnalysisMode.INTELLIGENT: 0.4, # 智能模式：中等輸出
            AnalysisMode.LARGE_FILE: 0.5,  # 大檔模式：較多輸出
            AnalysisMode.MAX_TOKEN: 0.8    # 深度模式：最多輸出
        }
        
        # 預設使用 intelligent 模式的比例
        output_tokens = int(input_tokens * 0.4)
        
        return input_tokens, output_tokens
    
    def calculate_api_calls_for_mode(self, total_tokens: int, context_window: int, mode: AnalysisMode) -> int:
        """根據模式計算需要的 API 調用次數"""
        # 根據模式調整有效 context window
        mode_context_ratio = {
            AnalysisMode.QUICK: 0.9,       # 快速模式：使用更多 context
            AnalysisMode.INTELLIGENT: 0.7,  # 智能模式：標準比例
            AnalysisMode.LARGE_FILE: 0.6,   # 大檔模式：保留更多空間
            AnalysisMode.MAX_TOKEN: 0.5     # 深度模式：最保守
        }
        
        ratio = mode_context_ratio.get(mode, 0.7)
        effective_context = int(context_window * ratio)
        
        # 計算需要的 API 調用次數
        api_calls = max(1, (total_tokens + effective_context - 1) // effective_context)
        
        return api_calls
    
    def calculate_cost(self, file_size_kb: float, model: str, 
                      budget: float = 10.0, mode: AnalysisMode = AnalysisMode.INTELLIGENT) -> CostEstimate:
        """計算單一模型的成本"""
        if model not in self._model_info_cache:
            raise ValueError(f"Unknown model: {model}")
        
        model_info = self._model_info_cache[model]
        provider = ModelProvider(model_info.provider)
        
        # 估算 tokens
        input_tokens, output_tokens = self.estimate_tokens(file_size_kb, provider)
        
        # 根據模式調整輸出 tokens
        output_ratio = {
            AnalysisMode.QUICK: 0.2,
            AnalysisMode.INTELLIGENT: 0.4,
            AnalysisMode.LARGE_FILE: 0.5,
            AnalysisMode.MAX_TOKEN: 0.8
        }
        output_tokens = int(input_tokens * output_ratio.get(mode, 0.4))
        
        # 計算成本
        input_cost = (input_tokens / 1000.0) * model_info.input_cost_per_1k
        output_cost = (output_tokens / 1000.0) * model_info.output_cost_per_1k
        total_cost = input_cost + output_cost
        
        # 計算 API 調用次數
        api_calls = self.calculate_api_calls_for_mode(input_tokens, model_info.context_window, mode)
        
        # 估算處理時間（基於模型速度評級、檔案大小和 API 調用次數）
        base_time = file_size_kb / 100  # 基礎時間：每 100KB 1 分鐘
        speed_factor = 6 - model_info.speed_rating  # 速度因子
        api_call_overhead = (api_calls - 1) * 0.5  # 每個額外 API 調用增加 0.5 分鐘
        analysis_time = (base_time * speed_factor) + api_call_overhead
        
        # 檢查預算和生成警告
        warnings = []
        is_within_budget = total_cost <= budget
        
        if not is_within_budget:
            warnings.append(f"預估成本 ${total_cost:.2f} 超過預算 ${budget:.2f}")
        
        if api_calls > 1:
            warnings.append(f"檔案將分成 {api_calls} 個區塊處理")
        
        if analysis_time > 10:
            warnings.append(f"預計需要較長處理時間（{analysis_time:.1f} 分鐘）")
        
        return CostEstimate(
            provider=model_info.provider,
            model=model,
            file_size_kb=file_size_kb,
            estimated_input_tokens=input_tokens,
            estimated_output_tokens=output_tokens,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=total_cost,
            analysis_time_estimate=analysis_time,
            is_within_budget=is_within_budget,
            warnings=warnings,
            api_calls=api_calls
        )
    
    def compare_models_cost(self, file_size_kb: float, mode: AnalysisMode, 
                           budget: float = 10.0) -> List[Dict[str, any]]:
        """比較不同模型的成本"""
        comparisons = []
        
        # 獲取適合該模式的模型
        anthropic_model = self.anthropic_config.get_model_for_mode(mode)
        openai_model = self.openai_config.get_model_for_mode(mode)
        
        # 計算所有相關模型的成本
        relevant_models = set()
        
        # 添加模式對應的模型
        relevant_models.add(anthropic_model)
        relevant_models.add(openai_model)
        
        # 根據模式添加其他可能的模型
        if mode == AnalysisMode.QUICK:
            relevant_models.update([
                "claude-3-5-haiku-20241022",
                "gpt-4o-mini",
                "gpt-3.5-turbo"
            ])
        elif mode == AnalysisMode.MAX_TOKEN:
            relevant_models.update([
                "claude-opus-4-20250514",
                "gpt-4-turbo"
            ])
        
        # 計算每個模型的成本
        for model in relevant_models:
            if model in self._model_info_cache:
                try:
                    estimate = self.calculate_cost(file_size_kb, model, budget, mode)
                    model_info = self._model_info_cache[model]
                    
                    comparisons.append({
                        "provider": estimate.provider,
                        "model": model,
                        "tier": model_info.tier,
                        "total_cost": round(estimate.total_cost, 4),
                        "input_cost": round(estimate.input_cost, 4),
                        "output_cost": round(estimate.output_cost, 4),
                        "analysis_time_estimate": round(estimate.analysis_time_estimate, 1),
                        "is_within_budget": estimate.is_within_budget,
                        "quality_rating": model_info.quality_rating,
                        "speed_rating": model_info.speed_rating,
                        "warnings": estimate.warnings,
                        "api_calls": estimate.api_calls,
                        "tokens_per_api_call": int(model_info.context_window * 0.7)
                    })
                except Exception:
                    continue
        
        # 按成本排序
        comparisons.sort(key=lambda x: x["total_cost"])
        
        return comparisons
    
    def get_tier_models(self, tier: int) -> List[str]:
        """獲取指定層級的所有模型"""
        return [
            model for model, info in self._model_info_cache.items()
            if info.tier == tier
        ]
    
    def recommend_model(self, file_size_kb: float, mode: AnalysisMode, 
                       budget: float = 10.0, 
                       prefer_quality: bool = True) -> Optional[str]:
        """推薦最適合的模型"""
        comparisons = self.compare_models_cost(file_size_kb, mode, budget)
        
        # 過濾出預算內的模型
        within_budget = [c for c in comparisons if c["is_within_budget"]]
        
        if not within_budget:
            # 如果沒有預算內的模型，返回最便宜的
            return comparisons[0]["model"] if comparisons else None
        
        if prefer_quality:
            # 優先考慮品質
            within_budget.sort(key=lambda x: (-x["quality_rating"], x["total_cost"]))
        else:
            # 優先考慮速度
            within_budget.sort(key=lambda x: (-x["speed_rating"], x["total_cost"]))
        
        return within_budget[0]["model"] if within_budget else None
    
    def format_cost_summary(self, estimate: CostEstimate) -> str:
        """格式化成本摘要"""
        lines = [
            f"模型: {estimate.model} ({estimate.provider})",
            f"檔案大小: {estimate.file_size_kb:.1f} KB",
            f"預估 Tokens: 輸入 {estimate.estimated_input_tokens:,} / 輸出 {estimate.estimated_output_tokens:,}",
            f"API 調用次數: {estimate.api_calls}",
            f"成本明細:",
            f"  - 輸入成本: ${estimate.input_cost:.4f}",
            f"  - 輸出成本: ${estimate.output_cost:.4f}",
            f"  - 總成本: ${estimate.total_cost:.4f}",
            f"預估時間: {estimate.analysis_time_estimate:.1f} 分鐘",
            f"預算狀態: {'✓ 在預算內' if estimate.is_within_budget else '✗ 超出預算'}"
        ]
        
        if estimate.warnings:
            lines.append("\n警告:")
            for warning in estimate.warnings:
                lines.append(f"  - {warning}")
        
        return "\n".join(lines)