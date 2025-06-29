"""
核心分析引擎
"""
from typing import Dict, Optional, AsyncIterator, Any
import asyncio

from ..config import SystemConfig
from models import ModelProvider, AnalysisMode
from ..wrappers import AnthropicAiLogWrapper, OpenAiLogWrapper
from ..utils import EnhancedStatusManager, CacheManager, StructuredLogger, HealthChecker
from ..storage import ResultStorage, AnalysisTask


class AiAnalysisEngine:
    """統一的 AI 分析引擎"""
    
    def __init__(self, config_path: str = "config.yaml"):
        # 載入系統配置
        self.config = SystemConfig.from_yaml(config_path)
        
        # 初始化元件
        self.status_manager = EnhancedStatusManager()
        self.cache_manager = CacheManager(self.config.cache.directory)
        self.logger = StructuredLogger("ai_analysis_engine")
        self.storage = ResultStorage(self.config.database.url)
        self.health_checker = HealthChecker(self)
        
        # 初始化 wrappers
        self._wrappers: Dict[ModelProvider, BaseAiLogWrapper] = {}
        self._current_provider: Optional[ModelProvider] = None
        self._init_wrappers()
        
        # 任務佇列
        self.task_queue = TaskQueue(self.config.limits.max_concurrent_analyses)
        
        self.logger.log_analysis("info", "引擎初始化完成", config=self.config.dict())
    
    def _init_wrappers(self):
        """初始化所有 wrapper"""
        # Anthropic
        if self.config.api_keys.anthropic:
            from ..config import AnthropicApiConfig
            anthropic_config = AnthropicApiConfig()
            anthropic_config.api_key = self.config.api_keys.anthropic
            
            self._wrappers[ModelProvider.ANTHROPIC] = AnthropicAiLogWrapper(
                anthropic_config, self.status_manager
            )
            self.logger.log_analysis("info", "Anthropic wrapper 初始化成功")
        
        # OpenAI
        if self.config.api_keys.openai:
            from ..config import OpenApiConfig
            openai_config = OpenApiConfig()
            openai_config.api_key = self.config.api_keys.openai
            
            self._wrappers[ModelProvider.OPENAI] = OpenAiLogWrapper(
                openai_config, self.status_manager
            )
            self.logger.log_analysis("info", "OpenAI wrapper 初始化成功")
        
        # 設定預設提供者
        if self.config.model_preferences.default_provider:
            provider = ModelProvider(self.config.model_preferences.default_provider)
            if provider in self._wrappers:
                self._current_provider = provider
    
    async def analyze(self, 
                     content: str, 
                     log_type: str, 
                     mode: AnalysisMode = AnalysisMode.INTELLIGENT,
                     provider: Optional[ModelProvider] = None,
                     use_cache: bool = True) -> AsyncIterator[str]:
        """統一分析入口"""
        
        start_time = datetime.now()
        
        try:
            # 記錄開始
            self.logger.log_analysis(
                "info", 
                "開始分析",
                log_type=log_type,
                mode=mode.value,
                provider=provider.value if provider else None,
                content_size=len(content)
            )
            
            # 檢查快取
            if use_cache and self.config.cache.enabled:
                cached_result = await self.cache_manager.get(
                    content, mode, 
                    self._get_model_for_mode(mode, provider)
                )
                if cached_result:
                    self.logger.log_analysis("info", "使用快取結果")
                    yield cached_result
                    return
            
            # 選擇提供者
            if provider:
                self.set_provider(provider)
            
            if not self._current_provider:
                raise ValueError("No AI provider available")
            
            wrapper = self._wrappers[self._current_provider]
            
            # 執行分析
            result_chunks = []
            
            if log_type.lower() == 'anr':
                async for chunk in wrapper.analyze_anr(content, mode):
                    result_chunks.append(chunk)
                    yield chunk
            elif log_type.lower() == 'tombstone':
                async for chunk in wrapper.analyze_tombstone(content, mode):
                    result_chunks.append(chunk)
                    yield chunk
            else:
                raise ValueError(f"Unknown log type: {log_type}")
            
            # 儲存結果
            complete_result = ''.join(result_chunks)
            
            # 快取結果
            if use_cache and self.config.cache.enabled:
                await self.cache_manager.set(
                    content, mode,
                    self._get_model_for_mode(mode, self._current_provider),
                    complete_result
                )
            
            # 記錄完成
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.log_analysis(
                "info",
                "分析完成",
                duration=duration,
                result_length=len(complete_result)
            )
            
        except Exception as e:
            self.logger.log_analysis(
                "error",
                "分析失敗",
                error=str(e),
                error_type=type(e).__name__
            )
            raise
    
    def set_provider(self, provider: ModelProvider):
        """設定 AI 提供者"""
        if provider in self._wrappers:
            self._current_provider = provider
            self.logger.log_analysis("info", f"切換到 {provider.value}")
        else:
            raise ValueError(f"Provider {provider} not available")
    
    def get_status(self) -> Dict[str, Any]:
        """獲取當前狀態"""
        status = self.status_manager.get_status()
        status['current_provider'] = self._current_provider.value if self._current_provider else None
        status['available_providers'] = [p.value for p in self._wrappers.keys()]
        return status
    
    async def get_health_status(self) -> Dict[str, Any]:
        """獲取健康狀態"""
        return await self.health_checker.check_all()
    
    def add_status_listener(self, callback: callable):
        """添加狀態監聽器"""
        self.status_manager.add_listener(callback)
    
    async def submit_task(self, 
                         content: str,
                         log_type: str,
                         mode: AnalysisMode = AnalysisMode.INTELLIGENT,
                         provider: Optional[ModelProvider] = None,
                         priority: int = 0) -> str:
        """提交分析任務到佇列"""
        task = AnalysisTask(
            content=content,
            log_type=log_type,
            mode=mode,
            provider=provider,
            priority=priority
        )
        
        task_id = await self.task_queue.add_task(task)
        self.logger.log_analysis("info", f"任務已提交: {task_id}")
        
        return task_id
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """獲取任務狀態"""
        task = self.task_queue.get_task_status(task_id)
        if task:
            return {
                'id': task.id,
                'status': task.status,
                'created_at': task.created_at.isoformat(),
                'mode': task.mode.value,
                'log_type': task.log_type,
                'has_result': task.result is not None,
                'has_error': task.error is not None,
                'error': task.error
            }
        return None
    
    def _get_model_for_mode(self, mode: AnalysisMode, provider: Optional[ModelProvider]) -> str:
        """根據模式獲取模型名稱"""
        provider_name = (provider or self._current_provider).value
        mode_overrides = self.config.model_preferences.mode_overrides
        
        if mode.value in mode_overrides:
            return mode_overrides[mode.value].get(provider_name, "default")
        
        return "default"
    
    async def start(self):
        """啟動引擎服務"""
        # 啟動任務工作者
        await self.task_queue.start_workers(self, num_workers=3)
        
        # 定期清理快取
        asyncio.create_task(self._periodic_cache_cleanup())
        
        # 定期健康檢查
        asyncio.create_task(self._periodic_health_check())
        
        self.logger.log_analysis("info", "引擎服務已啟動")
    
    async def shutdown(self):
        """關閉引擎服務"""
        await self.task_queue.shutdown()
        self.logger.log_analysis("info", "引擎服務已關閉")
    
    async def _periodic_cache_cleanup(self):
        """定期清理快取"""
        while True:
            await asyncio.sleep(3600)  # 每小時
            self.cache_manager.clear_expired()
            self.logger.log_analysis("info", "快取清理完成")
    
    async def _periodic_health_check(self):
        """定期健康檢查"""
        while True:
            await asyncio.sleep(self.config.monitoring.health_check_interval)
            health_status = await self.get_health_status()
            
            if health_status['overall']['status'] != 'healthy':
                self.logger.log_analysis(
                    "warning", 
                    "健康檢查發現問題",
                    health_status=health_status
                )