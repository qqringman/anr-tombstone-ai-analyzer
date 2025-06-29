"""
OpenAI AI 日誌包裝器
"""
from typing import AsyncIterator, Optional

from .base_wrapper import BaseAiLogWrapper
from ..config.base import AnalysisMode, ModelProvider
from ..config.openai_config import OpenApiConfig
from ..analyzers.anr.openai_anr import OpenApiStreamingANRAnalyzer
from ..analyzers.tombstone.openai_tombstone import OpenApiStreamingTombstoneAnalyzer
from ..utils.status_manager import EnhancedStatusManager
from ..core.cancellation import CancellationToken

class OpenAiLogWrapper(BaseAiLogWrapper):
    """OpenAI AI 日誌包裝器"""
    
    def __init__(self, 
                 config: OpenApiConfig,
                 status_manager: Optional[EnhancedStatusManager] = None):
        """
        初始化 OpenAI 包裝器
        
        Args:
            config: OpenAI API 配置
            status_manager: 狀態管理器
        """
        super().__init__(config, status_manager)
        self.config: OpenApiConfig = config
        
        # 初始化分析器
        self._init_analyzers()
    
    @property
    def provider(self) -> ModelProvider:
        """獲取 AI 提供者"""
        return ModelProvider.OPENAI
    
    def _init_analyzers(self):
        """初始化分析器"""
        self._anr_analyzer = OpenApiStreamingANRAnalyzer(
            self.config, 
            self.status_manager
        )
        self._tombstone_analyzer = OpenApiStreamingTombstoneAnalyzer(
            self.config,
            self.status_manager
        )
        
        self.logger.info("OpenAI analyzers initialized")
    
    async def analyze_anr(self, 
                         content: str, 
                         mode: AnalysisMode,
                         cancellation_token: Optional[CancellationToken] = None) -> AsyncIterator[str]:
        """分析 ANR 日誌"""
        try:
            # 記錄開始
            self.logger.log_analysis(
                "info",
                "Starting ANR analysis with OpenAI",
                mode=mode.value,
                content_size=len(content)
            )
            
            # 更新狀態
            await self.status_manager.set_status("analyzing_anr")
            
            # 執行分析
            total_output = []
            async for chunk in self._anr_analyzer.analyze(content, mode, cancellation_token):
                total_output.append(chunk)
                yield chunk
            
            # 記錄成功
            self.logger.log_analysis(
                "info",
                "ANR analysis completed successfully",
                output_size=len(''.join(total_output))
            )
            
            # 更新統計（基於估算）
            input_tokens = self.config.estimate_tokens(content)
            output_tokens = self.config.estimate_tokens(''.join(total_output))
            model = self.config.get_model_for_mode(mode)
            cost = self.calculate_cost(input_tokens, output_tokens, model)
            
            self.update_api_stats(input_tokens, output_tokens, cost, True)
            
        except Exception as e:
            # 記錄錯誤
            self.logger.error(
                "ANR analysis failed",
                exception=e,
                mode=mode.value
            )
            
            # 更新統計
            self.update_api_stats(0, 0, 0, False)
            
            raise
    
    async def analyze_tombstone(self, 
                              content: str, 
                              mode: AnalysisMode,
                              cancellation_token: Optional[CancellationToken] = None) -> AsyncIterator[str]:
        """分析 Tombstone 日誌"""
        try:
            # 記錄開始
            self.logger.log_analysis(
                "info",
                "Starting Tombstone analysis with OpenAI",
                mode=mode.value,
                content_size=len(content)
            )
            
            # 更新狀態
            await self.status_manager.set_status("analyzing_tombstone")
            
            # 執行分析
            total_output = []
            async for chunk in self._tombstone_analyzer.analyze(content, mode, cancellation_token):
                total_output.append(chunk)
                yield chunk
            
            # 記錄成功
            self.logger.log_analysis(
                "info",
                "Tombstone analysis completed successfully",
                output_size=len(''.join(total_output))
            )
            
            # 更新統計
            input_tokens = self.config.estimate_tokens(content)
            output_tokens = self.config.estimate_tokens(''.join(total_output))
            model = self.config.get_model_for_mode(mode)
            cost = self.calculate_cost(input_tokens, output_tokens, model)
            
            self.update_api_stats(input_tokens, output_tokens, cost, True)
            
        except Exception as e:
            # 記錄錯誤
            self.logger.error(
                "Tombstone analysis failed",
                exception=e,
                mode=mode.value
            )
            
            # 更新統計
            self.update_api_stats(0, 0, 0, False)
            
            raise
    
    def _estimate_tokens(self, text: str) -> int:
        """估算文本的 token 數量（OpenAI 特定）"""
        return self.config.estimate_tokens(text)
    
    async def test_connection(self) -> bool:
        """測試 API 連接"""
        try:
            # 使用最小的請求測試連接
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                api_key=self.config.api_key,
                organization=self.config.organization
            )
            
            # 發送測試請求
            response = await client.chat.completions.create(
                model="gpt-3.5-turbo",  # 使用最便宜的模型
                messages=[
                    {"role": "user", "content": "Hi"}
                ],
                max_tokens=10
            )
            
            return True
            
        except Exception as e:
            self.logger.error("Connection test failed", exception=e)
            return False
    
    def get_available_models(self) -> list[str]:
        """獲取可用的模型列表"""
        return list(self.config.models.keys())
    
    def get_model_info(self, model: str) -> dict:
        """獲取模型資訊"""
        if model in self.config.models:
            model_config = self.config.models[model]
            return {
                "name": model_config.name,
                "max_tokens": model_config.max_tokens,
                "context_window": model_config.context_window,
                "input_cost_per_1k": model_config.input_cost_per_1k,
                "output_cost_per_1k": model_config.output_cost_per_1k,
                "supports_streaming": model_config.supports_streaming,
                "supports_function_calling": model_config.supports_function_calling
            }
        return {}
    
    async def get_usage_summary(self) -> dict:
        """獲取使用摘要"""
        stats = self.get_api_stats()
        
        return {
            "provider": "OpenAI",
            "total_analyses": stats["total_requests"],
            "successful_analyses": stats["successful_requests"],
            "failed_analyses": stats["failed_requests"],
            "total_cost": f"${stats['total_cost']:.2f}",
            "average_cost": f"${stats['average_cost_per_request']:.2f}",
            "total_tokens": {
                "input": stats["total_input_tokens"],
                "output": stats["total_output_tokens"],
                "total": stats["total_input_tokens"] + stats["total_output_tokens"]
            },
            "models_used": self.get_available_models(),
            "features": {
                "function_calling": any(
                    self.config.models[m].supports_function_calling 
                    for m in self.config.models
                ),
                "streaming": True
            }
        }
    
    async def analyze_with_tools(self,
                               content: str,
                               log_type: str,
                               mode: AnalysisMode,
                               tools: Optional[list] = None,
                               cancellation_token: Optional[CancellationToken] = None) -> AsyncIterator[str]:
        """使用工具進行分析（OpenAI 特有功能）"""
        # 確保使用支援函數調用的模型
        model = self.config.get_model_for_mode(mode)
        model_config = self.config.get_model_config(model)
        
        if not model_config.supports_function_calling:
            # 降級到普通分析
            self.logger.warning(
                f"Model {model} does not support function calling, falling back to regular analysis"
            )
            async for chunk in self.analyze(content, log_type, mode, cancellation_token):
                yield chunk
            return
        
        # 執行帶工具的分析
        if log_type.lower() == 'anr' and hasattr(self._anr_analyzer, 'analyze_with_functions'):
            async for chunk in self._anr_analyzer.analyze_with_functions(
                content, mode, cancellation_token
            ):
                yield chunk
        elif log_type.lower() == 'tombstone' and hasattr(self._tombstone_analyzer, 'analyze_with_debugging_context'):
            async for chunk in self._tombstone_analyzer.analyze_with_debugging_context(
                content, mode, None, cancellation_token
            ):
                yield chunk
        else:
            # 降級到普通分析
            async for chunk in self.analyze(content, log_type, mode, cancellation_token):
                yield chunk