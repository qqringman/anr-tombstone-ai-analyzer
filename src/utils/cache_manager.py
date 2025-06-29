"""
快取管理器
"""
import os
import json
import hashlib
import pickle
import aiofiles
from pathlib import Path
from typing import Optional, Any, Dict, List
from datetime import datetime, timedelta
import asyncio
from dataclasses import dataclass, field

from ..core.exceptions import CacheException

@dataclass
class CacheEntry:
    """快取項目"""
    key: str
    value: Any
    created_at: datetime = field(default_factory=datetime.now)
    accessed_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    size_bytes: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def update_access(self):
        """更新訪問資訊"""
        self.accessed_at = datetime.now()
        self.access_count += 1
    
    def is_expired(self, ttl_hours: int) -> bool:
        """檢查是否過期"""
        age = datetime.now() - self.created_at
        return age > timedelta(hours=ttl_hours)

class CacheManager:
    """快取管理器"""
    
    def __init__(self, cache_dir: str = ".cache/ai_analysis", 
                 max_memory_items: int = 100,
                 ttl_hours: int = 24):
        """
        初始化快取管理器
        
        Args:
            cache_dir: 快取目錄
            max_memory_items: 記憶體中最大快取項目數
            ttl_hours: 快取過期時間（小時）
        """
        self.cache_dir = Path(cache_dir)
        self.max_memory_items = max_memory_items
        self.ttl_hours = ttl_hours
        
        # 記憶體快取
        self._memory_cache: Dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()
        
        # 確保快取目錄存在
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 統計資訊
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "errors": 0
        }
    
    def _generate_key(self, content: str, mode: str, model: str) -> str:
        """生成快取鍵"""
        # 使用內容的前 1000 個字符 + 完整內容的 hash
        content_preview = content[:1000]
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        key_data = f"{content_preview}:{content_hash}:{mode}:{model}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _get_file_path(self, key: str) -> Path:
        """獲取快取檔案路徑"""
        # 使用前兩個字符作為子目錄，避免單一目錄檔案過多
        subdir = self.cache_dir / key[:2]
        subdir.mkdir(exist_ok=True)
        return subdir / f"{key}.cache"
    
    async def get(self, content: str, mode: str, model: str) -> Optional[str]:
        """從快取獲取結果"""
        key = self._generate_key(content, mode, model)
        
        try:
            # 首先檢查記憶體快取
            async with self._lock:
                if key in self._memory_cache:
                    entry = self._memory_cache[key]
                    if not entry.is_expired(self.ttl_hours):
                        entry.update_access()
                        self._stats["hits"] += 1
                        return entry.value
                    else:
                        # 過期了，移除
                        del self._memory_cache[key]
            
            # 檢查磁碟快取
            file_path = self._get_file_path(key)
            if file_path.exists():
                async with aiofiles.open(file_path, 'rb') as f:
                    data = await f.read()
                    entry = pickle.loads(data)
                
                if not entry.is_expired(self.ttl_hours):
                    # 更新訪問資訊並加入記憶體快取
                    entry.update_access()
                    await self._add_to_memory(key, entry)
                    self._stats["hits"] += 1
                    return entry.value
                else:
                    # 過期了，刪除檔案
                    file_path.unlink()
            
            self._stats["misses"] += 1
            return None
            
        except Exception as e:
            self._stats["errors"] += 1
            raise CacheException(f"Cache get error: {str(e)}")
    
    async def set(self, content: str, mode: str, model: str, result: str):
        """將結果存入快取"""
        key = self._generate_key(content, mode, model)
        
        try:
            # 創建快取項目
            entry = CacheEntry(
                key=key,
                value=result,
                size_bytes=len(result.encode()),
                metadata={
                    "mode": mode,
                    "model": model,
                    "content_length": len(content)
                }
            )
            
            # 存入記憶體快取
            await self._add_to_memory(key, entry)
            
            # 存入磁碟快取
            file_path = self._get_file_path(key)
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(pickle.dumps(entry))
                
        except Exception as e:
            self._stats["errors"] += 1
            raise CacheException(f"Cache set error: {str(e)}")
    
    async def _add_to_memory(self, key: str, entry: CacheEntry):
        """添加到記憶體快取"""
        async with self._lock:
            # 如果超過限制，使用 LRU 策略移除最少使用的項目
            if len(self._memory_cache) >= self.max_memory_items:
                # 找出最少使用的項目
                lru_key = min(
                    self._memory_cache.keys(),
                    key=lambda k: (
                        self._memory_cache[k].access_count,
                        self._memory_cache[k].accessed_at
                    )
                )
                del self._memory_cache[lru_key]
                self._stats["evictions"] += 1
            
            self._memory_cache[key] = entry
    
    async def clear(self):
        """清空所有快取"""
        async with self._lock:
            self._memory_cache.clear()
        
        # 刪除所有快取檔案
        for cache_file in self.cache_dir.rglob("*.cache"):
            try:
                cache_file.unlink()
            except Exception:
                pass
    
    async def clear_expired(self):
        """清理過期的快取"""
        # 清理記憶體快取
        async with self._lock:
            expired_keys = [
                key for key, entry in self._memory_cache.items()
                if entry.is_expired(self.ttl_hours)
            ]
            for key in expired_keys:
                del self._memory_cache[key]
        
        # 清理磁碟快取
        for cache_file in self.cache_dir.rglob("*.cache"):
            try:
                async with aiofiles.open(cache_file, 'rb') as f:
                    data = await f.read()
                    entry = pickle.loads(data)
                
                if entry.is_expired(self.ttl_hours):
                    cache_file.unlink()
            except Exception:
                # 如果無法讀取或解析，直接刪除
                cache_file.unlink()
    
    def get_stats(self) -> Dict[str, Any]:
        """獲取快取統計資訊"""
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total_requests if total_requests > 0 else 0
        
        # 計算磁碟使用量
        disk_usage = sum(
            f.stat().st_size for f in self.cache_dir.rglob("*.cache")
        )
        
        return {
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "hit_rate": round(hit_rate, 3),
            "evictions": self._stats["evictions"],
            "errors": self._stats["errors"],
            "memory_items": len(self._memory_cache),
            "disk_usage_mb": round(disk_usage / 1024 / 1024, 2)
        }
    
    async def warmup(self, recent_hours: int = 24):
        """預熱快取（載入最近使用的項目到記憶體）"""
        recent_time = datetime.now() - timedelta(hours=recent_hours)
        loaded_count = 0
        
        for cache_file in self.cache_dir.rglob("*.cache"):
            if loaded_count >= self.max_memory_items:
                break
            
            try:
                # 檢查檔案修改時間
                mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
                if mtime < recent_time:
                    continue
                
                # 載入快取項目
                async with aiofiles.open(cache_file, 'rb') as f:
                    data = await f.read()
                    entry = pickle.loads(data)
                
                if not entry.is_expired(self.ttl_hours):
                    await self._add_to_memory(entry.key, entry)
                    loaded_count += 1
            except Exception:
                pass
        
        return loaded_count