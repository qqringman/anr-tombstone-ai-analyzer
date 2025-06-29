"""
增強狀態管理器
"""
import asyncio
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json

class MessageType(Enum):
    """訊息類型"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"
    PROGRESS = "progress"

@dataclass
class StatusMessage:
    """狀態訊息"""
    type: MessageType
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    details: Optional[Dict[str, Any]] = None

@dataclass
class ProgressInfo:
    """進度資訊"""
    current_chunk: int = 0
    total_chunks: int = 0
    processed_tokens: int = 0
    estimated_total_tokens: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    
    @property
    def progress_percentage(self) -> float:
        """計算進度百分比"""
        if self.total_chunks == 0:
            return 0.0
        return (self.current_chunk / self.total_chunks) * 100
    
    @property
    def elapsed_time(self) -> timedelta:
        """已經過的時間"""
        return datetime.now() - self.start_time
    
    @property
    def estimated_remaining_time(self) -> Optional[timedelta]:
        """預估剩餘時間"""
        if self.current_chunk == 0:
            return None
        
        elapsed = self.elapsed_time.total_seconds()
        rate = self.current_chunk / elapsed
        remaining_chunks = self.total_chunks - self.current_chunk
        
        if rate > 0:
            remaining_seconds = remaining_chunks / rate
            return timedelta(seconds=remaining_seconds)
        return None

@dataclass
class ApiUsageStats:
    """API 使用統計"""
    requests_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost: float = 0.0
    errors_count: int = 0
    cancelled_count: int = 0
    
    def add_request(self, input_tokens: int, output_tokens: int, cost: float):
        """添加請求統計"""
        self.requests_count += 1
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_cost += cost
    
    def add_error(self):
        """添加錯誤統計"""
        self.errors_count += 1
    
    def add_cancellation(self):
        """添加取消統計"""
        self.cancelled_count += 1

class EnhancedStatusManager:
    """增強狀態管理器"""
    
    def __init__(self, max_messages: int = 100):
        """
        初始化狀態管理器
        
        Args:
            max_messages: 最大保留訊息數量
        """
        self.max_messages = max_messages
        self._messages: List[StatusMessage] = []
        self._progress = ProgressInfo()
        self._api_usage = ApiUsageStats()
        self._current_status = "idle"
        self._listeners: List[Callable] = []
        self._lock = asyncio.Lock()
        
        # 狀態快照
        self._last_snapshot: Optional[Dict[str, Any]] = None
        self._snapshot_time: Optional[datetime] = None
    
    async def update_progress(self, current_chunk: int, total_chunks: int, 
                            processed_tokens: int = 0, estimated_total_tokens: int = 0):
        """更新進度"""
        async with self._lock:
            self._progress.current_chunk = current_chunk
            self._progress.total_chunks = total_chunks
            self._progress.processed_tokens = processed_tokens
            self._progress.estimated_total_tokens = estimated_total_tokens
            
            # 發送進度訊息
            await self.add_message(
                MessageType.PROGRESS,
                f"處理進度: {self._progress.progress_percentage:.1f}%",
                {
                    "current_chunk": current_chunk,
                    "total_chunks": total_chunks,
                    "percentage": self._progress.progress_percentage
                }
            )
            
            await self._notify_listeners()
    
    async def add_message(self, type: MessageType, message: str, 
                         details: Optional[Dict[str, Any]] = None):
        """添加狀態訊息"""
        async with self._lock:
            msg = StatusMessage(type, message, datetime.now(), details)
            self._messages.append(msg)
            
            # 限制訊息數量
            if len(self._messages) > self.max_messages:
                self._messages = self._messages[-self.max_messages:]
            
            await self._notify_listeners()
    
    async def update_api_usage(self, input_tokens: int, output_tokens: int, cost: float):
        """更新 API 使用統計"""
        async with self._lock:
            self._api_usage.add_request(input_tokens, output_tokens, cost)
            await self._notify_listeners()
    
    async def record_error(self, error_message: str, error_details: Optional[Dict[str, Any]] = None):
        """記錄錯誤"""
        async with self._lock:
            self._api_usage.add_error()
            await self.add_message(MessageType.ERROR, error_message, error_details)
    
    async def record_cancellation(self, reason: str):
        """記錄取消操作"""
        async with self._lock:
            self._api_usage.add_cancellation()
            await self.add_message(MessageType.WARNING, f"分析已取消: {reason}")
    
    async def set_status(self, status: str):
        """設定當前狀態"""
        async with self._lock:
            self._current_status = status
            await self._notify_listeners()
    
    async def reset(self):
        """重置狀態"""
        async with self._lock:
            self._messages.clear()
            self._progress = ProgressInfo()
            self._api_usage = ApiUsageStats()
            self._current_status = "idle"
            await self._notify_listeners()
    
    def add_listener(self, callback: Callable):
        """添加狀態變更監聽器"""
        if callback not in self._listeners:
            self._listeners.append(callback)
    
    def remove_listener(self, callback: Callable):
        """移除狀態變更監聽器"""
        if callback in self._listeners:
            self._listeners.remove(callback)
    
    async def _notify_listeners(self):
        """通知所有監聽器"""
        status = await self.get_status()
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(status)
                else:
                    listener(status)
            except Exception:
                pass  # 忽略監聽器錯誤
    
    async def get_status(self) -> Dict[str, Any]:
        """獲取當前狀態快照"""
        async with self._lock:
            # 如果快照還很新鮮（1秒內），直接返回
            if (self._last_snapshot and self._snapshot_time and 
                (datetime.now() - self._snapshot_time).total_seconds() < 1):
                return self._last_snapshot
            
            # 建立新快照
            messages_data = [
                {
                    "type": msg.type.value,
                    "message": msg.message,
                    "timestamp": msg.timestamp.isoformat(),
                    "details": msg.details
                }
                for msg in self._messages[-10:]  # 只返回最近 10 條訊息
            ]
            
            remaining_time = self._progress.estimated_remaining_time
            
            self._last_snapshot = {
                "status": self._current_status,
                "progress": {
                    "current_chunk": self._progress.current_chunk,
                    "total_chunks": self._progress.total_chunks,
                    "progress_percentage": self._progress.progress_percentage,
                    "processed_tokens": self._progress.processed_tokens,
                    "estimated_total_tokens": self._progress.estimated_total_tokens,
                    "elapsed_time": str(self._progress.elapsed_time),
                    "estimated_remaining_time": str(remaining_time) if remaining_time else None
                },
                "api_usage": {
                    "requests_count": self._api_usage.requests_count,
                    "input_tokens": self._api_usage.input_tokens,
                    "output_tokens": self._api_usage.output_tokens,
                    "total_cost": round(self._api_usage.total_cost, 4),
                    "errors_count": self._api_usage.errors_count,
                    "cancelled_count": self._api_usage.cancelled_count
                },
                "feedback": {
                    "messages": messages_data,
                    "has_errors": self._api_usage.errors_count > 0,
                    "is_cancelled": self._api_usage.cancelled_count > 0
                },
                "timestamp": datetime.now().isoformat()
            }
            
            self._snapshot_time = datetime.now()
            return self._last_snapshot
    
    def to_json(self) -> str:
        """將狀態轉換為 JSON"""
        status = asyncio.run(self.get_status())
        return json.dumps(status, ensure_ascii=False, indent=2)