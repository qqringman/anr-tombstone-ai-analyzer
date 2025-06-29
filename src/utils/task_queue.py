"""
任務佇列系統
"""
import asyncio
import uuid
from typing import Dict, Optional, List, Any, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import heapq
from collections import deque

from ..config.base import AnalysisMode, ModelProvider

class TaskStatus(Enum):
    """任務狀態"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class AnalysisTask:
    """分析任務"""
    content: str
    log_type: str
    mode: AnalysisMode
    provider: Optional[ModelProvider] = None
    priority: int = 0  # 優先級，數值越小優先級越高
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __lt__(self, other):
        """用於優先級佇列比較"""
        return self.priority < other.priority

class TaskQueue:
    """任務佇列"""
    
    def __init__(self, max_concurrent: int = 5, max_queue_size: int = 100):
        """
        初始化任務佇列
        
        Args:
            max_concurrent: 最大並行任務數
            max_queue_size: 最大佇列大小
        """
        self.max_concurrent = max_concurrent
        self.max_queue_size = max_queue_size
        
        # 優先級佇列
        self._queue: List[AnalysisTask] = []
        self._task_map: Dict[str, AnalysisTask] = {}
        
        # 執行中的任務
        self._running_tasks: Dict[str, asyncio.Task] = {}
        
        # 工作者
        self._workers: List[asyncio.Task] = []
        self._shutdown = False
        
        # 鎖
        self._lock = asyncio.Lock()
        
        # 統計
        self._stats = {
            "total_submitted": 0,
            "total_completed": 0,
            "total_failed": 0,
            "total_cancelled": 0
        }
        
        # 回調
        self._task_callbacks: Dict[str, List[Callable]] = {}
    
    async def add_task(self, task: AnalysisTask) -> str:
        """添加任務到佇列"""
        async with self._lock:
            if len(self._queue) >= self.max_queue_size:
                raise ValueError(f"Queue is full (max size: {self.max_queue_size})")
            
            # 添加到佇列
            heapq.heappush(self._queue, task)
            self._task_map[task.id] = task
            self._stats["total_submitted"] += 1
            
            return task.id
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任務"""
        async with self._lock:
            task = self._task_map.get(task_id)
            if not task:
                return False
            
            if task.status == TaskStatus.PENDING:
                # 從佇列中移除
                self._queue = [t for t in self._queue if t.id != task_id]
                heapq.heapify(self._queue)
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()
                self._stats["total_cancelled"] += 1
                
                # 執行回調
                await self._execute_callbacks(task_id, task)
                return True
            
            elif task.status == TaskStatus.RUNNING and task_id in self._running_tasks:
                # 取消執行中的任務
                self._running_tasks[task_id].cancel()
                return True
            
            return False
    
    def get_task_status(self, task_id: str) -> Optional[AnalysisTask]:
        """獲取任務狀態"""
        return self._task_map.get(task_id)
    
    def get_queue_status(self) -> Dict[str, Any]:
        """獲取佇列狀態"""
        status_counts = {status: 0 for status in TaskStatus}
        for task in self._task_map.values():
            status_counts[task.status] += 1
        
        return {
            "queue_size": len(self._queue),
            "running_tasks": len(self._running_tasks),
            "total_tasks": len(self._task_map),
            "status_counts": {s.value: c for s, c in status_counts.items()},
            "stats": self._stats,
            "is_full": len(self._queue) >= self.max_queue_size
        }
    
    def add_task_callback(self, task_id: str, callback: Callable):
        """添加任務完成回調"""
        if task_id not in self._task_callbacks:
            self._task_callbacks[task_id] = []
        self._task_callbacks[task_id].append(callback)
    
    async def start_workers(self, engine, num_workers: Optional[int] = None):
        """啟動工作者"""
        if num_workers is None:
            num_workers = self.max_concurrent
        
        for i in range(num_workers):
            worker = asyncio.create_task(self._worker(engine, i))
            self._workers.append(worker)
    
    async def shutdown(self):
        """關閉佇列"""
        self._shutdown = True
        
        # 等待所有工作者完成
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        
        # 取消所有執行中的任務
        for task in self._running_tasks.values():
            task.cancel()
    
    async def _worker(self, engine, worker_id: int):
        """工作者主循環"""
        while not self._shutdown:
            try:
                # 獲取任務
                task = await self._get_next_task()
                if not task:
                    await asyncio.sleep(0.1)
                    continue
                
                # 執行任務
                await self._execute_task(engine, task)
                
            except Exception as e:
                # 記錄錯誤但繼續運行
                print(f"Worker {worker_id} error: {e}")
    
    async def _get_next_task(self) -> Optional[AnalysisTask]:
        """獲取下一個任務"""
        async with self._lock:
            # 檢查是否可以執行新任務
            if len(self._running_tasks) >= self.max_concurrent:
                return None
            
            if not self._queue:
                return None
            
            # 獲取優先級最高的任務
            task = heapq.heappop(self._queue)
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            
            return task
    
    async def _execute_task(self, engine, task: AnalysisTask):
        """執行任務"""
        task_future = asyncio.create_task(self._run_analysis(engine, task))
        self._running_tasks[task.id] = task_future
        
        try:
            await task_future
        finally:
            # 清理
            self._running_tasks.pop(task.id, None)
    
    async def _run_analysis(self, engine, task: AnalysisTask):
        """運行分析"""
        try:
            # 收集結果
            result_chunks = []
            
            async for chunk in engine.analyze(
                task.content,
                task.log_type,
                task.mode,
                task.provider
            ):
                result_chunks.append(chunk)
            
            # 更新任務狀態
            async with self._lock:
                task.result = ''.join(result_chunks)
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now()
                self._stats["total_completed"] += 1
            
            # 執行回調
            await self._execute_callbacks(task.id, task)
            
        except asyncio.CancelledError:
            # 任務被取消
            async with self._lock:
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()
                task.error = "Task cancelled"
                self._stats["total_cancelled"] += 1
            
            await self._execute_callbacks(task.id, task)
            raise
            
        except Exception as e:
            # 任務失敗
            async with self._lock:
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now()
                task.error = str(e)
                self._stats["total_failed"] += 1
            
            await self._execute_callbacks(task.id, task)
    
    async def _execute_callbacks(self, task_id: str, task: AnalysisTask):
        """執行任務回調"""
        callbacks = self._task_callbacks.get(task_id, [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(task)
                else:
                    callback(task)
            except Exception:
                pass  # 忽略回調錯誤
        
        # 清理回調
        self._task_callbacks.pop(task_id, None)
    
    def get_pending_tasks(self) -> List[AnalysisTask]:
        """獲取待處理任務列表"""
        return sorted(
            [t for t in self._task_map.values() if t.status == TaskStatus.PENDING],
            key=lambda t: (t.priority, t.created_at)
        )
    
    def get_running_tasks(self) -> List[AnalysisTask]:
        """獲取執行中任務列表"""
        return [t for t in self._task_map.values() if t.status == TaskStatus.RUNNING]
    
    def clear_completed_tasks(self, older_than_hours: int = 24):
        """清理已完成的任務"""
        cutoff_time = datetime.now() - timedelta(hours=older_than_hours)
        
        to_remove = []
        for task_id, task in self._task_map.items():
            if (task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED] and
                task.completed_at and task.completed_at < cutoff_time):
                to_remove.append(task_id)
        
        for task_id in to_remove:
            del self._task_map[task_id]
        
        return len(to_remove)