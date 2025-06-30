"""
取消機制實作
"""
import asyncio
from typing import Dict, Optional, Callable
from datetime import datetime
from enum import Enum
import uuid
import threading

from .exceptions import CancellationException

class CancellationReason(Enum):
    """取消原因"""
    USER_CANCELLED = "user_cancelled"
    TIMEOUT = "timeout"
    BUDGET_EXCEEDED = "budget_exceeded"
    ERROR = "error"
    SYSTEM_SHUTDOWN = "system_shutdown"

class CancellationToken:
    """取消令牌"""
    def __init__(self, analysis_id: str):
        self.analysis_id = analysis_id
        self.is_cancelled = False
        self.reason: Optional[CancellationReason] = None
        self.cancelled_at: Optional[datetime] = None
        self._callbacks: list[Callable] = []
        self._lock = threading.Lock()  # 使用線程鎖而不是異步鎖
    
    def cancel(self, reason: CancellationReason = CancellationReason.USER_CANCELLED):
        """取消操作"""
        with self._lock:
            if not self.is_cancelled:
                self.is_cancelled = True
                self.reason = reason
                self.cancelled_at = datetime.now()
                
                # 執行所有回調
                for callback in self._callbacks:
                    try:
                        callback()
                    except Exception:
                        pass
    
    def check(self):
        """檢查是否已取消，如果已取消則拋出異常"""
        if self.is_cancelled:
            raise CancellationException(self.reason.value)
    
    def add_callback(self, callback: Callable):
        """添加取消回調"""
        with self._lock:
            self._callbacks.append(callback)
            
            # 如果已經取消，立即執行回調
            if self.is_cancelled:
                try:
                    callback()
                except Exception:
                    pass

class CancellationManager:
    """取消管理器"""
    def __init__(self):
        self._tokens: Dict[str, CancellationToken] = {}
        self._lock = threading.Lock()  # 使用線程鎖
    
    async def create_token(self, analysis_id: Optional[str] = None) -> CancellationToken:
        """創建取消令牌"""
        if not analysis_id:
            analysis_id = str(uuid.uuid4())
        
        with self._lock:
            token = CancellationToken(analysis_id)
            self._tokens[analysis_id] = token
            return token
    
    async def get_token(self, analysis_id: str) -> Optional[CancellationToken]:
        """獲取取消令牌"""
        with self._lock:
            return self._tokens.get(analysis_id)
    
    async def cancel(self, analysis_id: str, reason: CancellationReason = CancellationReason.USER_CANCELLED) -> bool:
        """取消指定的分析"""
        token = await self.get_token(analysis_id)
        if token and not token.is_cancelled:
            token.cancel(reason)
            return True
        return False
    
    async def remove_token(self, analysis_id: str):
        """移除取消令牌"""
        with self._lock:
            self._tokens.pop(analysis_id, None)
    
    async def cancel_all(self, reason: CancellationReason = CancellationReason.SYSTEM_SHUTDOWN):
        """取消所有分析"""
        async with self._lock:
            for token in self._tokens.values():
                if not token.is_cancelled:
                    token.cancel(reason)
    
    async def cleanup_old_tokens(self, max_age_hours: int = 24):
        """清理舊的取消令牌"""
        async with self._lock:
            now = datetime.now()
            to_remove = []
            
            for analysis_id, token in self._tokens.items():
                if token.cancelled_at:
                    age = (now - token.cancelled_at).total_seconds() / 3600
                    if age > max_age_hours:
                        to_remove.append(analysis_id)
            
            for analysis_id in to_remove:
                del self._tokens[analysis_id]
    
    def get_active_count(self) -> int:
        """獲取活躍的分析數量"""
        return sum(1 for token in self._tokens.values() if not token.is_cancelled)
    
    def get_cancelled_count(self) -> int:
        """獲取已取消的分析數量"""
        return sum(1 for token in self._tokens.values() if token.is_cancelled)

class CancellableOperation:
    """可取消的操作基類"""
    def __init__(self, token: CancellationToken):
        self.token = token
    
    async def check_cancellation(self):
        """檢查取消狀態"""
        self.token.check()
    
    async def run_with_cancellation_check(self, coro, check_interval: float = 0.1):
        """運行協程並定期檢查取消狀態"""
        task = asyncio.create_task(coro)
        
        try:
            while not task.done():
                self.token.check()
                await asyncio.sleep(check_interval)
            
            return await task
        except CancellationException:
            task.cancel()
            raise
        except Exception:
            task.cancel()
            raise

# 全局取消管理器實例
global_cancellation_manager = CancellationManager()

def get_cancellation_manager() -> CancellationManager:
    """獲取全局取消管理器"""
    return global_cancellation_manager