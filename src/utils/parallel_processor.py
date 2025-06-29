"""
並行處理器
"""
import asyncio
from typing import List, Callable, Any, Optional, AsyncIterator, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime
import time

@dataclass
class ProcessResult:
    """處理結果"""
    index: int
    success: bool
    result: Any
    error: Optional[Exception] = None
    duration: float = 0.0

class ParallelProcessor:
    """並行處理器"""
    
    def __init__(self, max_concurrent: int = 5, timeout: Optional[float] = None):
        """
        初始化並行處理器
        
        Args:
            max_concurrent: 最大並行數
            timeout: 超時時間（秒）
        """
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self._semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_batch(
        self, 
        items: List[Any], 
        processor: Callable[[Any], Any],
        return_exceptions: bool = True
    ) -> List[ProcessResult]:
        """
        批次處理項目
        
        Args:
            items: 要處理的項目列表
            processor: 處理函數（可以是同步或異步）
            return_exceptions: 是否返回異常而不是拋出
            
        Returns:
            處理結果列表
        """
        tasks = []
        for i, item in enumerate(items):
            task = self._process_item(i, item, processor)
            tasks.append(task)
        
        # 並行執行所有任務
        if return_exceptions:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            results = await asyncio.gather(*tasks)
        
        return results
    
    async def _process_item(
        self, 
        index: int, 
        item: Any, 
        processor: Callable
    ) -> ProcessResult:
        """處理單個項目"""
        async with self._semaphore:
            start_time = time.time()
            
            try:
                # 處理項目
                if asyncio.iscoroutinefunction(processor):
                    result = await self._with_timeout(processor(item))
                else:
                    result = await self._with_timeout(
                        asyncio.get_event_loop().run_in_executor(None, processor, item)
                    )
                
                duration = time.time() - start_time
                return ProcessResult(
                    index=index,
                    success=True,
                    result=result,
                    duration=duration
                )
                
            except Exception as e:
                duration = time.time() - start_time
                return ProcessResult(
                    index=index,
                    success=False,
                    result=None,
                    error=e,
                    duration=duration
                )
    
    async def _with_timeout(self, coro):
        """添加超時控制"""
        if self.timeout:
            return await asyncio.wait_for(coro, timeout=self.timeout)
        return await coro
    
    async def map_async(
        self,
        func: Callable[[Any], Any],
        items: List[Any],
        ordered: bool = True
    ) -> List[Any]:
        """
        異步 map 操作
        
        Args:
            func: 映射函數
            items: 項目列表
            ordered: 是否保持順序
            
        Returns:
            結果列表
        """
        results = await self.process_batch(items, func)
        
        if ordered:
            # 按原始順序返回結果
            return [r.result if r.success else None for r in results]
        else:
            # 只返回成功的結果
            return [r.result for r in results if r.success]
    
    async def filter_async(
        self,
        predicate: Callable[[Any], bool],
        items: List[Any]
    ) -> List[Any]:
        """
        異步 filter 操作
        
        Args:
            predicate: 過濾函數
            items: 項目列表
            
        Returns:
            過濾後的列表
        """
        async def check_item(item):
            if asyncio.iscoroutinefunction(predicate):
                should_include = await predicate(item)
            else:
                should_include = predicate(item)
            return (item, should_include)
        
        results = await self.process_batch(items, check_item)
        
        return [
            r.result[0] for r in results 
            if r.success and r.result[1]
        ]
    
    async def reduce_async(
        self,
        func: Callable[[Any, Any], Any],
        items: List[Any],
        initial: Any = None
    ) -> Any:
        """
        異步 reduce 操作
        
        Args:
            func: 歸約函數
            items: 項目列表
            initial: 初始值
            
        Returns:
            歸約結果
        """
        if not items:
            return initial
        
        if initial is None:
            result = items[0]
            items = items[1:]
        else:
            result = initial
        
        for item in items:
            if asyncio.iscoroutinefunction(func):
                result = await func(result, item)
            else:
                result = func(result, item)
        
        return result
    
    async def chunk_process(
        self,
        items: List[Any],
        chunk_size: int,
        processor: Callable[[List[Any]], Any]
    ) -> List[ProcessResult]:
        """
        分塊處理
        
        Args:
            items: 項目列表
            chunk_size: 塊大小
            processor: 處理函數（處理整個塊）
            
        Returns:
            處理結果列表
        """
        chunks = [
            items[i:i + chunk_size] 
            for i in range(0, len(items), chunk_size)
        ]
        
        return await self.process_batch(chunks, processor)
    
    async def pipeline(
        self,
        items: List[Any],
        processors: List[Callable]
    ) -> List[Any]:
        """
        管道處理
        
        Args:
            items: 項目列表
            processors: 處理器列表（按順序執行）
            
        Returns:
            最終結果列表
        """
        results = items
        
        for processor in processors:
            results = await self.map_async(processor, results)
            # 過濾掉 None 結果
            results = [r for r in results if r is not None]
        
        return results
    
    async def stream_process(
        self,
        stream: AsyncIterator[Any],
        processor: Callable[[Any], Any],
        buffer_size: int = 100
    ) -> AsyncIterator[ProcessResult]:
        """
        流式處理
        
        Args:
            stream: 異步迭代器
            processor: 處理函數
            buffer_size: 緩衝區大小
            
        Yields:
            處理結果
        """
        buffer = []
        index = 0
        
        async for item in stream:
            buffer.append((index, item))
            index += 1
            
            if len(buffer) >= buffer_size:
                # 處理緩衝區
                results = await self.process_batch(
                    buffer,
                    lambda x: processor(x[1])
                )
                
                for i, result in enumerate(results):
                    result.index = buffer[i][0]
                    yield result
                
                buffer = []
        
        # 處理剩餘的項目
        if buffer:
            results = await self.process_batch(
                buffer,
                lambda x: processor(x[1])
            )
            
            for i, result in enumerate(results):
                result.index = buffer[i][0]
                yield result
    
    def get_statistics(self, results: List[ProcessResult]) -> Dict[str, Any]:
        """
        獲取處理統計資訊
        
        Args:
            results: 處理結果列表
            
        Returns:
            統計資訊字典
        """
        total = len(results)
        successful = sum(1 for r in results if r.success)
        failed = total - successful
        
        durations = [r.duration for r in results if r.success]
        
        return {
            "total": total,
            "successful": successful,
            "failed": failed,
            "success_rate": successful / total if total > 0 else 0,
            "average_duration": sum(durations) / len(durations) if durations else 0,
            "min_duration": min(durations) if durations else 0,
            "max_duration": max(durations) if durations else 0,
            "total_duration": sum(r.duration for r in results)
        }

class BatchProcessor(ParallelProcessor):
    """批次處理器（特化版本）"""
    
    async def process_in_batches(
        self,
        items: List[Any],
        batch_size: int,
        processor: Callable[[List[Any]], Any],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[Any]:
        """
        分批處理項目
        
        Args:
            items: 項目列表
            batch_size: 批次大小
            processor: 批次處理函數
            progress_callback: 進度回調函數
            
        Returns:
            所有結果的平坦列表
        """
        total_batches = (len(items) + batch_size - 1) // batch_size
        all_results = []
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            batch_num = i // batch_size + 1
            
            # 進度回調
            if progress_callback:
                progress_callback(batch_num, total_batches)
            
            # 處理批次
            if asyncio.iscoroutinefunction(processor):
                result = await processor(batch)
            else:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, processor, batch
                )
            
            # 假設結果是列表，展開它
            if isinstance(result, list):
                all_results.extend(result)
            else:
                all_results.append(result)
        
        return all_results