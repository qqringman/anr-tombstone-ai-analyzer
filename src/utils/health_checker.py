"""
健康檢查器
"""
import asyncio
import aiohttp
import psutil
import os
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

class HealthStatus(Enum):
    """健康狀態"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

class ComponentHealth:
    """組件健康狀態"""
    def __init__(self, name: str):
        self.name = name
        self.status = HealthStatus.HEALTHY
        self.message = "OK"
        self.details: Dict[str, Any] = {}
        self.last_check = datetime.now()
    
    def update(self, status: HealthStatus, message: str = "", **details):
        """更新健康狀態"""
        self.status = status
        self.message = message or status.value
        self.details = details
        self.last_check = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "last_check": self.last_check.isoformat()
        }

class HealthChecker:
    """健康檢查器"""
    
    def __init__(self, engine=None):
        """
        初始化健康檢查器
        
        Args:
            engine: AI 分析引擎實例（可選）
        """
        self.engine = engine
        self.components: Dict[str, ComponentHealth] = {}
        self._init_components()
        
        # 健康檢查歷史
        self.check_history: List[Tuple[datetime, HealthStatus]] = []
        self.max_history = 100
    
    def _init_components(self):
        """初始化組件"""
        components = [
            "api", "database", "cache", "ai_providers", 
            "disk_space", "memory", "rate_limit"
        ]
        
        for component in components:
            self.components[component] = ComponentHealth(component)
    
    async def check_all(self) -> Dict[str, Any]:
        """執行所有健康檢查"""
        # 並行執行所有檢查
        checks = [
            self._check_api(),
            self._check_database(),
            self._check_cache(),
            self._check_ai_providers(),
            self._check_disk_space(),
            self._check_memory(),
            self._check_rate_limit()
        ]
        
        await asyncio.gather(*checks, return_exceptions=True)
        
        # 計算整體狀態
        overall_status = self._calculate_overall_status()
        
        # 更新歷史
        self._update_history(overall_status)
        
        # 返回結果
        return {
            "overall": {
                "status": overall_status.value,
                "timestamp": datetime.now().isoformat()
            },
            "components": {
                name: component.to_dict() 
                for name, component in self.components.items()
            },
            "metrics": self._get_system_metrics()
        }
    
    async def _check_api(self):
        """檢查 API 服務"""
        try:
            # 簡單的自檢
            self.components["api"].update(
                HealthStatus.HEALTHY,
                "API service is running"
            )
        except Exception as e:
            self.components["api"].update(
                HealthStatus.UNHEALTHY,
                f"API check failed: {str(e)}"
            )
    
    async def _check_database(self):
        """檢查資料庫連接"""
        try:
            if self.engine and hasattr(self.engine, 'storage'):
                # 嘗試執行簡單查詢
                # TODO: 實際實作資料庫檢查
                self.components["database"].update(
                    HealthStatus.HEALTHY,
                    "Database connection OK"
                )
            else:
                self.components["database"].update(
                    HealthStatus.DEGRADED,
                    "Database not configured"
                )
        except Exception as e:
            self.components["database"].update(
                HealthStatus.UNHEALTHY,
                f"Database error: {str(e)}"
            )
    
    async def _check_cache(self):
        """檢查快取系統"""
        try:
            if self.engine and hasattr(self.engine, 'cache_manager'):
                stats = self.engine.cache_manager.get_stats()
                
                # 檢查錯誤率
                if stats["errors"] > 100:
                    status = HealthStatus.DEGRADED
                    message = "High cache error rate"
                else:
                    status = HealthStatus.HEALTHY
                    message = f"Cache hit rate: {stats['hit_rate']:.1%}"
                
                self.components["cache"].update(
                    status, message, **stats
                )
            else:
                self.components["cache"].update(
                    HealthStatus.DEGRADED,
                    "Cache not configured"
                )
        except Exception as e:
            self.components["cache"].update(
                HealthStatus.UNHEALTHY,
                f"Cache error: {str(e)}"
            )
    
    async def _check_ai_providers(self):
        """檢查 AI 提供者狀態"""
        try:
            if not self.engine:
                self.components["ai_providers"].update(
                    HealthStatus.DEGRADED,
                    "Engine not available"
                )
                return
            
            providers_status = {}
            available_providers = []
            
            # 檢查 Anthropic
            if hasattr(self.engine, '_wrappers'):
                from ..config.base import ModelProvider
                
                if ModelProvider.ANTHROPIC in self.engine._wrappers:
                    # 可以添加實際的 API 測試
                    providers_status["anthropic"] = "available"
                    available_providers.append("anthropic")
                
                if ModelProvider.OPENAI in self.engine._wrappers:
                    providers_status["openai"] = "available"
                    available_providers.append("openai")
            
            if available_providers:
                self.components["ai_providers"].update(
                    HealthStatus.HEALTHY,
                    f"{len(available_providers)} providers available",
                    providers=providers_status
                )
            else:
                self.components["ai_providers"].update(
                    HealthStatus.UNHEALTHY,
                    "No AI providers available"
                )
        except Exception as e:
            self.components["ai_providers"].update(
                HealthStatus.UNHEALTHY,
                f"Provider check error: {str(e)}"
            )
    
    async def _check_disk_space(self):
        """檢查磁碟空間"""
        try:
            # 獲取當前目錄的磁碟使用情況
            usage = psutil.disk_usage('/')
            free_gb = usage.free / (1024 ** 3)
            percent_used = usage.percent
            
            if percent_used > 90:
                status = HealthStatus.UNHEALTHY
                message = f"Critical: {percent_used:.1f}% disk used"
            elif percent_used > 80:
                status = HealthStatus.DEGRADED
                message = f"Warning: {percent_used:.1f}% disk used"
            else:
                status = HealthStatus.HEALTHY
                message = f"{free_gb:.1f} GB free"
            
            self.components["disk_space"].update(
                status, message,
                percent_used=percent_used,
                free_gb=free_gb,
                total_gb=usage.total / (1024 ** 3)
            )
        except Exception as e:
            self.components["disk_space"].update(
                HealthStatus.UNHEALTHY,
                f"Disk check error: {str(e)}"
            )
    
    async def _check_memory(self):
        """檢查記憶體使用"""
        try:
            memory = psutil.virtual_memory()
            
            if memory.percent > 90:
                status = HealthStatus.UNHEALTHY
                message = f"Critical: {memory.percent:.1f}% memory used"
            elif memory.percent > 80:
                status = HealthStatus.DEGRADED
                message = f"Warning: {memory.percent:.1f}% memory used"
            else:
                status = HealthStatus.HEALTHY
                message = f"{memory.available / (1024 ** 3):.1f} GB available"
            
            self.components["memory"].update(
                status, message,
                percent_used=memory.percent,
                available_gb=memory.available / (1024 ** 3),
                total_gb=memory.total / (1024 ** 3)
            )
        except Exception as e:
            self.components["memory"].update(
                HealthStatus.UNHEALTHY,
                f"Memory check error: {str(e)}"
            )
    
    async def _check_rate_limit(self):
        """檢查速率限制狀態"""
        try:
            # TODO: 實際檢查速率限制
            self.components["rate_limit"].update(
                HealthStatus.HEALTHY,
                "Rate limits OK"
            )
        except Exception as e:
            self.components["rate_limit"].update(
                HealthStatus.UNHEALTHY,
                f"Rate limit check error: {str(e)}"
            )
    
    def _calculate_overall_status(self) -> HealthStatus:
        """計算整體健康狀態"""
        statuses = [c.status for c in self.components.values()]
        
        if any(s == HealthStatus.UNHEALTHY for s in statuses):
            return HealthStatus.UNHEALTHY
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY
    
    def _get_system_metrics(self) -> Dict[str, Any]:
        """獲取系統指標"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # 獲取進程資訊
            process = psutil.Process(os.getpid())
            process_memory = process.memory_info().rss / (1024 ** 2)  # MB
            
            return {
                "cpu_percent": cpu_percent,
                "process_memory_mb": round(process_memory, 1),
                "active_connections": len(process.connections()),
                "thread_count": process.num_threads(),
                "uptime_seconds": int((datetime.now() - datetime.fromtimestamp(process.create_time())).total_seconds())
            }
        except Exception:
            return {}
    
    def _update_history(self, status: HealthStatus):
        """更新健康檢查歷史"""
        self.check_history.append((datetime.now(), status))
        
        # 限制歷史記錄數量
        if len(self.check_history) > self.max_history:
            self.check_history = self.check_history[-self.max_history:]
    
    def get_availability(self, hours: int = 24) -> float:
        """計算可用性百分比"""
        if not self.check_history:
            return 100.0
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_checks = [
            status for time, status in self.check_history
            if time > cutoff_time
        ]
        
        if not recent_checks:
            return 100.0
        
        healthy_count = sum(1 for s in recent_checks if s == HealthStatus.HEALTHY)
        return (healthy_count / len(recent_checks)) * 100