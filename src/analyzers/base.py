"""
基礎分析器類別
"""
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional, Dict, Any, List
from datetime import datetime

from ..config.base import AnalysisMode, ModelProvider
from ..utils.status_manager import EnhancedStatusManager
from ..utils.logger import StructuredLogger
from ..core.cancellation import CancellationToken
from ..core.exceptions import InvalidLogTypeException, CancellationException

class BaseAnalyzer(ABC):
    """基礎分析器抽象類別"""
    
    def __init__(self, 
                 provider: ModelProvider,
                 status_manager: Optional[EnhancedStatusManager] = None,
                 logger: Optional[StructuredLogger] = None):
        """
        初始化分析器
        
        Args:
            provider: AI 提供者
            status_manager: 狀態管理器
            logger: 日誌記錄器
        """
        self.provider = provider
        self.status_manager = status_manager or EnhancedStatusManager()
        self.logger = logger or StructuredLogger(f"{provider.value}_analyzer")
        
        # 分析統計
        self._stats = {
            "total_analyses": 0,
            "total_chunks": 0,
            "total_tokens": 0,
            "total_time": 0.0
        }
    
    @abstractmethod
    async def analyze(self, 
                     content: str, 
                     mode: AnalysisMode,
                     cancellation_token: Optional[CancellationToken] = None) -> AsyncIterator[str]:
        """
        執行分析
        
        Args:
            content: 要分析的內容
            mode: 分析模式
            cancellation_token: 取消令牌
            
        Yields:
            分析結果片段
        """
        pass
    
    @abstractmethod
    def get_prompt(self, content: str, mode: AnalysisMode) -> str:
        """
        獲取分析提示詞
        
        Args:
            content: 要分析的內容
            mode: 分析模式
            
        Returns:
            提示詞
        """
        pass
    
    @abstractmethod
    def validate_content(self, content: str) -> bool:
        """
        驗證內容是否為有效的日誌格式
        
        Args:
            content: 要驗證的內容
            
        Returns:
            是否有效
        """
        pass
    
    def preprocess_content(self, content: str) -> str:
        """
        預處理內容
        
        Args:
            content: 原始內容
            
        Returns:
            處理後的內容
        """
        # 移除多餘的空白
        content = content.strip()
        
        # 標準化換行符
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        
        return content
    
    async def chunk_content(self, content: str, mode: AnalysisMode) -> List[str]:
        """
        將內容分塊
        
        Args:
            content: 要分塊的內容
            mode: 分析模式
            
        Returns:
            內容塊列表
        """
        # 子類可以覆寫此方法實現自定義分塊邏輯
        # 預設實作：根據模式決定塊大小
        chunk_sizes = {
            AnalysisMode.QUICK: 50000,
            AnalysisMode.INTELLIGENT: 150000,
            AnalysisMode.LARGE_FILE: 200000,
            AnalysisMode.MAX_TOKEN: 180000
        }
        
        chunk_size = chunk_sizes.get(mode, 150000)
        
        if len(content) <= chunk_size:
            return [content]
        
        # 智能分塊：在換行符處分割
        chunks = []
        current_chunk = []
        current_size = 0
        
        lines = content.split('\n')
        for line in lines:
            line_size = len(line) + 1  # +1 for newline
            
            if current_size + line_size > chunk_size and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_size = line_size
            else:
                current_chunk.append(line)
                current_size += line_size
        
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        return chunks
    
    async def post_process(self, result: str) -> str:
        """
        後處理結果
        
        Args:
            result: 原始結果
            
        Returns:
            處理後的結果
        """
        # 子類可以覆寫此方法實現自定義後處理
        return result
    
    def get_statistics(self) -> Dict[str, Any]:
        """獲取分析統計"""
        return {
            "provider": self.provider.value,
            "total_analyses": self._stats["total_analyses"],
            "total_chunks": self._stats["total_chunks"],
            "total_tokens": self._stats["total_tokens"],
            "total_time": self._stats["total_time"],
            "average_time": self._stats["total_time"] / self._stats["total_analyses"] 
                           if self._stats["total_analyses"] > 0 else 0
        }
    
    async def check_cancellation(self, token: Optional[CancellationToken]):
        """檢查取消狀態"""
        if token:
            token.check()
    
    def format_analysis_header(self, log_type: str, mode: AnalysisMode) -> str:
        """格式化分析標題"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"""# {log_type.upper()} 分析報告

**生成時間**: {timestamp}  
**分析模式**: {mode.value}  
**AI 提供者**: {self.provider.value}

---

"""
    
    def format_chunk_header(self, chunk_index: int, total_chunks: int) -> str:
        """格式化塊標題"""
        if total_chunks > 1:
            return f"\n## 第 {chunk_index + 1}/{total_chunks} 部分\n\n"
        return ""
    
    def format_error_response(self, error: Exception) -> str:
        """格式化錯誤響應"""
        return f"""## ❌ 分析錯誤

**錯誤類型**: {type(error).__name__}  
**錯誤訊息**: {str(error)}

請檢查日誌內容是否正確，或嘗試使用其他分析模式。
"""