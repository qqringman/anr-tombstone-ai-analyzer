"""
基礎 AI 日誌包裝器
"""
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional, Dict, Any
from datetime import datetime

from ..config.base import BaseApiConfig, AnalysisMode, ModelProvider
from ..utils.status_manager import EnhancedStatusManager
from ..utils.logger import StructuredLogger
from ..core.cancellation import CancellationToken

class BaseAiLogWrapper(ABC):
    """基礎 AI 日誌包裝器"""
    
    def __init__(self, 
                 config: BaseApiConfig,
                 status_manager: Optional[EnhancedStatusManager] = None):
        """
        初始化包裝器
        
        Args:
            config: API 配置
            status_manager: 狀態管理器
        """
        self.config = config
        self.status_manager = status_manager or EnhancedStatusManager()
        self.logger = StructuredLogger(f"{self.__class__.__name__}")
        
        # 分析器實例快取
        self._anr_analyzer = None
        self._tombstone_analyzer = None
        
        # API 調用統計
        self._api_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost": 0.0
        }
    
    @property
    @abstractmethod
    def provider(self) -> ModelProvider:
        """獲取 AI 提供者"""
        pass
    
    @abstractmethod
    async def analyze_anr(self, 
                         content: str, 
                         mode: AnalysisMode,
                         cancellation_token: Optional[CancellationToken] = None) -> AsyncIterator[str]:
        """
        分析 ANR 日誌
        
        Args:
            content: ANR 日誌內容
            mode: 分析模式
            cancellation_token: 取消令牌
            
        Yields:
            分析結果片段
        """
        pass
    
    @abstractmethod
    async def analyze_tombstone(self, 
                              content: str, 
                              mode: AnalysisMode,
                              cancellation_token: Optional[CancellationToken] = None) -> AsyncIterator[str]:
        """
        分析 Tombstone 日誌
        
        Args:
            content: Tombstone 日誌內容
            mode: 分析模式  
            cancellation_token: 取消令牌
            
        Yields:
            分析結果片段
        """
        pass
    
    async def analyze(self, 
                     content: str, 
                     log_type: str, 
                     mode: AnalysisMode,
                     cancellation_token: Optional[CancellationToken] = None) -> AsyncIterator[str]:
        """
        統一的分析入口
        
        Args:
            content: 日誌內容
            log_type: 日誌類型 ('anr' 或 'tombstone')
            mode: 分析模式
            cancellation_token: 取消令牌
            
        Yields:
            分析結果片段
        """
        log_type = log_type.lower()
        
        if log_type == 'anr':
            async for chunk in self.analyze_anr(content, mode, cancellation_token):
                yield chunk
        elif log_type == 'tombstone':
            async for chunk in self.analyze_tombstone(content, mode, cancellation_token):
                yield chunk
        else:
            raise ValueError(f"Unsupported log type: {log_type}")
    
    def validate_config(self) -> bool:
        """驗證配置是否有效"""
        if not self.config.api_key:
            self.logger.error("API key is missing")
            return False
        
        if not self.config.models:
            self.logger.error("No models configured")
            return False
        
        return True
    
    def get_model_for_mode(self, mode: AnalysisMode) -> str:
        """根據分析模式獲取模型"""
        return self.config.get_model_for_mode(mode)
    
    def calculate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """計算 API 調用成本"""
        return self.config.calculate_cost(input_tokens, output_tokens, model)
    
    def update_api_stats(self, 
                        input_tokens: int, 
                        output_tokens: int, 
                        cost: float,
                        success: bool = True):
        """更新 API 統計資訊"""
        self._api_stats["total_requests"] += 1
        
        if success:
            self._api_stats["successful_requests"] += 1
            self._api_stats["total_input_tokens"] += input_tokens
            self._api_stats["total_output_tokens"] += output_tokens
            self._api_stats["total_cost"] += cost
        else:
            self._api_stats["failed_requests"] += 1
    
    def get_api_stats(self) -> Dict[str, Any]:
        """獲取 API 統計資訊"""
        return {
            **self._api_stats,
            "average_cost_per_request": (
                self._api_stats["total_cost"] / self._api_stats["successful_requests"]
                if self._api_stats["successful_requests"] > 0 else 0
            ),
            "success_rate": (
                self._api_stats["successful_requests"] / self._api_stats["total_requests"]
                if self._api_stats["total_requests"] > 0 else 0
            )
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """健康檢查"""
        try:
            # 基本檢查
            is_configured = self.validate_config()
            
            # 可以添加 API 連接測試
            # TODO: 實作 API ping 測試
            
            return {
                "provider": self.provider.value,
                "status": "healthy" if is_configured else "unhealthy",
                "configured": is_configured,
                "api_stats": self.get_api_stats(),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "provider": self.provider.value,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def estimate_cost(self, 
                          content: str, 
                          log_type: str, 
                          mode: AnalysisMode) -> Dict[str, Any]:
        """估算分析成本"""
        # 估算 tokens
        input_tokens = self._estimate_tokens(content)
        output_tokens = int(input_tokens * 0.3)  # 假設輸出為輸入的 30%
        
        # 獲取模型
        model = self.get_model_for_mode(mode)
        
        # 計算成本
        cost = self.calculate_cost(input_tokens, output_tokens, model)
        
        return {
            "provider": self.provider.value,
            "model": model,
            "estimated_input_tokens": input_tokens,
            "estimated_output_tokens": output_tokens,
            "estimated_cost": cost,
            "mode": mode.value
        }
    
    def _estimate_tokens(self, text: str) -> int:
        """估算文本的 token 數量（基本實作）"""
        # 粗略估算：每 4 個字符約 1 個 token
        return int(len(text) / 4)
    
    async def __aenter__(self):
        """異步上下文管理器進入"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """異步上下文管理器退出"""
        # 可以在這裡進行清理工作
        pass