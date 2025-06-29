"""
Server-Sent Events (SSE) 工具
"""
import json
import asyncio
from typing import AsyncIterator, Dict, Any, Optional
from flask import Response
from datetime import datetime

class SSEMessage:
    """SSE 訊息"""
    
    def __init__(self, 
                 data: Any,
                 event: Optional[str] = None,
                 id: Optional[str] = None,
                 retry: Optional[int] = None):
        """
        初始化 SSE 訊息
        
        Args:
            data: 訊息資料
            event: 事件類型
            id: 訊息 ID
            retry: 重試間隔（毫秒）
        """
        self.data = data
        self.event = event
        self.id = id
        self.retry = retry
    
    def format(self) -> str:
        """格式化為 SSE 格式"""
        lines = []
        
        if self.id:
            lines.append(f"id: {self.id}")
        
        if self.event:
            lines.append(f"event: {self.event}")
        
        if self.retry is not None:
            lines.append(f"retry: {self.retry}")
        
        # 處理資料
        if isinstance(self.data, str):
            for line in self.data.split('\n'):
                lines.append(f"data: {line}")
        else:
            # 轉換為 JSON
            json_data = json.dumps(self.data, ensure_ascii=False)
            lines.append(f"data: {json_data}")
        
        # SSE 格式需要雙換行結尾
        return '\n'.join(lines) + '\n\n'

class SSEStream:
    """SSE 流"""
    
    def __init__(self, 
                 heartbeat_interval: int = 30,
                 retry_interval: int = 3000):
        """
        初始化 SSE 流
        
        Args:
            heartbeat_interval: 心跳間隔（秒）
            retry_interval: 客戶端重連間隔（毫秒）
        """
        self.heartbeat_interval = heartbeat_interval
        self.retry_interval = retry_interval
        self._closed = False
    
    async def send_message(self, 
                          data: Any,
                          event: Optional[str] = None,
                          id: Optional[str] = None) -> str:
        """發送訊息"""
        message = SSEMessage(data, event, id, self.retry_interval)
        return message.format()
    
    async def send_event(self, event_type: str, data: Any) -> str:
        """發送特定類型的事件"""
        return await self.send_message(data, event=event_type)
    
    async def send_heartbeat(self) -> str:
        """發送心跳"""
        return await self.send_message(
            {'type': 'heartbeat', 'timestamp': datetime.utcnow().isoformat()},
            event='heartbeat'
        )
    
    async def stream_with_heartbeat(self, 
                                   data_generator: AsyncIterator[Dict[str, Any]]) -> AsyncIterator[str]:
        """帶心跳的流"""
        last_heartbeat = asyncio.get_event_loop().time()
        
        try:
            async for data in data_generator:
                # 發送資料
                yield await self.send_message(data)
                
                # 檢查是否需要發送心跳
                current_time = asyncio.get_event_loop().time()
                if current_time - last_heartbeat > self.heartbeat_interval:
                    yield await self.send_heartbeat()
                    last_heartbeat = current_time
                
                if self._closed:
                    break
            
        except asyncio.CancelledError:
            # 發送取消事件
            yield await self.send_event('cancelled', {'message': 'Stream cancelled'})
            raise
        except Exception as e:
            # 發送錯誤事件
            yield await self.send_event('error', {'message': str(e)})
            raise
        finally:
            # 發送結束事件
            if not self._closed:
                yield await self.send_event('close', {'message': 'Stream closed'})
    
    def close(self):
        """關閉流"""
        self._closed = True

def create_sse_response(generator: AsyncIterator[str], 
                       mimetype: str = 'text/event-stream') -> Response:
    """
    創建 SSE 響應
    
    Args:
        generator: 異步生成器
        mimetype: MIME 類型
        
    Returns:
        Flask Response
    """
    return Response(
        generator,
        mimetype=mimetype,
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',  # 禁用 Nginx 緩衝
            'Connection': 'keep-alive'
        }
    )

class AnalysisSSEStream(SSEStream):
    """分析專用的 SSE 流"""
    
    async def send_analysis_start(self, analysis_id: str, metadata: Dict[str, Any]) -> str:
        """發送分析開始事件"""
        return await self.send_event('start', {
            'analysis_id': analysis_id,
            'timestamp': datetime.utcnow().isoformat(),
            **metadata
        })
    
    async def send_analysis_progress(self, 
                                   progress: float,
                                   current_chunk: int,
                                   total_chunks: int,
                                   tokens_used: int) -> str:
        """發送分析進度"""
        return await self.send_event('progress', {
            'progress_percentage': progress,
            'current_chunk': current_chunk,
            'total_chunks': total_chunks,
            'tokens_used': tokens_used,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    async def send_analysis_content(self, content: str) -> str:
        """發送分析內容"""
        return await self.send_event('content', {
            'content': content,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    async def send_analysis_complete(self, 
                                   total_tokens: int,
                                   total_cost: float,
                                   duration: float) -> str:
        """發送分析完成事件"""
        return await self.send_event('complete', {
            'total_tokens': total_tokens,
            'total_cost': total_cost,
            'duration_seconds': duration,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    async def send_analysis_error(self, error_message: str, error_type: str) -> str:
        """發送分析錯誤"""
        return await self.send_event('error', {
            'error_type': error_type,
            'message': error_message,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    async def send_feedback(self, message: str, level: str = 'info') -> str:
        """發送回饋訊息"""
        return await self.send_event('feedback', {
            'level': level,  # info, warning, error
            'message': message,
            'timestamp': datetime.utcnow().isoformat()
        })

# 便利函數
def create_analysis_sse_stream() -> AnalysisSSEStream:
    """創建分析 SSE 流"""
    return AnalysisSSEStream()

async def stream_analysis_results(analysis_generator: AsyncIterator[str],
                                analysis_id: str,
                                metadata: Optional[Dict[str, Any]] = None) -> AsyncIterator[str]:
    """
    流式傳輸分析結果
    
    Args:
        analysis_generator: 分析結果生成器
        analysis_id: 分析 ID
        metadata: 元資料
        
    Yields:
        SSE 格式的訊息
    """
    stream = AnalysisSSEStream()
    
    # 發送開始事件
    yield await stream.send_analysis_start(analysis_id, metadata or {})
    
    try:
        content_buffer = []
        async for chunk in analysis_generator:
            # 發送內容
            yield await stream.send_analysis_content(chunk)
            content_buffer.append(chunk)
        
        # 發送完成事件
        yield await stream.send_analysis_complete(
            total_tokens=0,  # TODO: 從實際分析獲取
            total_cost=0.0,  # TODO: 從實際分析獲取
            duration=0.0     # TODO: 從實際分析獲取
        )
        
    except Exception as e:
        # 發送錯誤事件
        yield await stream.send_analysis_error(
            str(e),
            type(e).__name__
        )
        raise