"""
核心分析引擎 - 包含可取消的 AI 分析引擎
"""
import asyncio
from typing import Dict, Optional, AsyncIterator, Any, List
from datetime import datetime
from pathlib import Path

from ..config.system_config import SystemConfig, get_system_config
from ..config.base import AnalysisMode, ModelProvider
from ..config.anthropic_config import AnthropicApiConfig
from ..config.openai_config import OpenApiConfig
from ..wrappers.base_wrapper import BaseAiLogWrapper
from ..wrappers.anthropic_wrapper import AnthropicAiLogWrapper
from ..wrappers.openai_wrapper import OpenAiLogWrapper
from ..utils.status_manager import EnhancedStatusManager, MessageType
from ..utils.cache_manager import CacheManager
from ..utils.logger import StructuredLogger
from ..utils.health_checker import HealthChecker
from ..utils.task_queue import TaskQueue, AnalysisTask
from ..storage.result_storage import ResultStorage
from .cancellation import CancellationToken, CancellationManager, CancellationReason, get_cancellation_manager
from .exceptions import (
    ProviderNotAvailableException, 
    CancellationException,
    InvalidLogTypeException,
    ConfigurationException
)


class AiAnalysisEngine:
    """統一的 AI 分析引擎"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化 AI 分析引擎
        
        Args:
            config_path: 配置檔案路徑
        """
        # 載入系統配置
        if config_path:
            self.config = SystemConfig.from_yaml(config_path)
        else:
            self.config = get_system_config()
        
        # 驗證配置
        is_valid, errors = self.config.validate_config()
        if not is_valid:
            raise ConfigurationException(f"Invalid configuration: {'; '.join(errors)}")
        
        # 初始化元件
        self.status_manager = EnhancedStatusManager()
        self.cache_manager = CacheManager(
            self.config.cache.directory,
            self.config.cache.max_memory_items,
            self.config.cache.ttl_hours
        )
        self.logger = StructuredLogger("ai_analysis_engine")
        self.storage = ResultStorage(self.config.database.url)
        self.health_checker = HealthChecker(self)
        
        # 初始化 wrappers
        self._wrappers: Dict[ModelProvider, BaseAiLogWrapper] = {}
        self._current_provider: Optional[ModelProvider] = None
        self._init_wrappers()
        
        # 任務佇列
        self.task_queue = TaskQueue(
            self.config.limits.max_concurrent_analyses,
            self.config.limits.max_queue_size
        )
        
        self.logger.log_analysis("info", "引擎初始化完成", config=self.config.dict())
    
    def _init_wrappers(self):
        """初始化所有 wrapper"""
        # Anthropic
        if self.config.api_keys.anthropic:
            anthropic_config = AnthropicApiConfig()
            anthropic_config.api_key = self.config.api_keys.anthropic
            
            self._wrappers[ModelProvider.ANTHROPIC] = AnthropicAiLogWrapper(
                anthropic_config, self.status_manager
            )
            self.logger.log_analysis("info", "Anthropic wrapper 初始化成功")
        
        # OpenAI
        if self.config.api_keys.openai:
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
        """
        統一分析入口
        
        Args:
            content: 日誌內容
            log_type: 日誌類型 ('anr' 或 'tombstone')
            mode: 分析模式
            provider: AI 提供者
            use_cache: 是否使用快取
            
        Yields:
            分析結果片段
        """
        start_time = datetime.now()
        
        try:
            # 驗證日誌類型
            if log_type.lower() not in ['anr', 'tombstone']:
                raise InvalidLogTypeException(log_type)
            
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
                model = self._get_model_for_mode(mode, provider)
                cached_result = await self.cache_manager.get(content, mode.value, model)
                if cached_result:
                    self.logger.log_analysis("info", "使用快取結果")
                    yield cached_result
                    return
            
            # 選擇提供者
            if provider:
                self.set_provider(provider)
            
            if not self._current_provider:
                raise ProviderNotAvailableException("No AI provider available")
            
            wrapper = self._wrappers[self._current_provider]
            
            # 執行分析
            result_chunks = []
            
            async for chunk in wrapper.analyze(content, log_type, mode):
                result_chunks.append(chunk)
                yield chunk
            
            # 儲存結果
            complete_result = ''.join(result_chunks)
            
            # 快取結果
            if use_cache and self.config.cache.enabled:
                model = self._get_model_for_mode(mode, self._current_provider)
                await self.cache_manager.set(content, mode.value, model, complete_result)
            
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
            raise ProviderNotAvailableException(f"Provider {provider} not available")
    
    def get_status(self) -> Dict[str, Any]:
        """獲取當前狀態"""
        status = asyncio.run(self.status_manager.get_status())
        status['current_provider'] = self._current_provider.value if self._current_provider else None
        status['available_providers'] = [p.value for p in self._wrappers.keys()]
        status['queue_status'] = self.task_queue.get_queue_status()
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
                'status': task.status.value,
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
        provider_value = (provider or self._current_provider).value
        wrapper = self._wrappers.get(provider or self._current_provider)
        if wrapper:
            return wrapper.get_model_for_mode(mode)
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
            await self.cache_manager.clear_expired()
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


class CancellableAiAnalysisEngine(AiAnalysisEngine):
    """支援取消功能的 AI 分析引擎"""
    
    def __init__(self, config_path: Optional[str] = None):
        """初始化可取消的分析引擎"""
        super().__init__(config_path)
        self.cancellation_manager = get_cancellation_manager()
        self._active_analyses: Dict[str, CancellationToken] = {}
    
    async def analyze_with_cancellation(self,
                                      content: str,
                                      log_type: str,
                                      mode: AnalysisMode = AnalysisMode.INTELLIGENT,
                                      provider: Optional[ModelProvider] = None,
                                      analysis_id: Optional[str] = None) -> AsyncIterator[str]:
        """
        支援取消的分析方法
        
        Args:
            content: 日誌內容
            log_type: 日誌類型
            mode: 分析模式
            provider: AI 提供者
            analysis_id: 分析 ID（可選）
            
        Yields:
            分析結果片段
        """
        # 創建取消令牌
        token = await self.cancellation_manager.create_token(analysis_id)
        self._active_analyses[token.analysis_id] = token
        
        try:
            # 記錄分析開始
            await self.storage.create_analysis_record(
                analysis_type=log_type,
                analysis_mode=mode.value,
                provider=(provider or self._current_provider).value,
                model=self._get_model_for_mode(mode, provider),
                content=content
            )
            
            # 更新狀態
            await self.storage.update_analysis_status(token.analysis_id, "running")
            await self.status_manager.add_message(
                MessageType.INFO,
                f"開始分析 (ID: {token.analysis_id})"
            )
            
            # 選擇 wrapper
            if provider:
                self.set_provider(provider)
            
            if not self._current_provider:
                raise ProviderNotAvailableException("No AI provider available")
            
            wrapper = self._wrappers[self._current_provider]
            
            # 執行分析
            result_chunks = []
            input_tokens = 0
            output_tokens = 0
            
            async for chunk in wrapper.analyze(content, log_type, mode, token):
                # 檢查取消狀態
                token.check()
                
                result_chunks.append(chunk)
                yield chunk
                
                # 更新進度（這裡需要從 wrapper 獲取實際的 token 使用情況）
                progress = len(result_chunks) * 10  # 簡單的進度估算
                await self.status_manager.update_progress(
                    progress, 100, input_tokens, output_tokens
                )
            
            # 完成分析
            complete_result = ''.join(result_chunks)
            
            # 獲取實際的 token 使用情況
            api_stats = wrapper.get_api_stats()
            if api_stats:
                input_tokens = api_stats.get('total_input_tokens', 0)
                output_tokens = api_stats.get('total_output_tokens', 0)
                cost = api_stats.get('total_cost', 0.0)
            else:
                cost = 0.0
            
            # 更新資料庫
            await self.storage.update_analysis_result(
                token.analysis_id,
                complete_result,
                input_tokens,
                output_tokens,
                cost,
                "completed"
            )
            
            await self.status_manager.add_message(
                MessageType.SUCCESS,
                f"分析完成 (ID: {token.analysis_id})"
            )
            
        except CancellationException as e:
            # 處理取消
            await self.storage.update_analysis_status(
                token.analysis_id,
                "cancelled",
                str(e)
            )
            await self.status_manager.record_cancellation(str(e))
            raise
            
        except Exception as e:
            # 處理其他錯誤
            await self.storage.update_analysis_status(
                token.analysis_id,
                "failed",
                str(e)
            )
            await self.status_manager.record_error(str(e))
            raise
            
        finally:
            # 清理
            self._active_analyses.pop(token.analysis_id, None)
            await self.cancellation_manager.remove_token(token.analysis_id)
    
    async def cancel_analysis(self, analysis_id: str, reason: CancellationReason = CancellationReason.USER_CANCELLED) -> bool:
        """
        取消分析
        
        Args:
            analysis_id: 分析 ID
            reason: 取消原因
            
        Returns:
            是否成功取消
        """
        success = await self.cancellation_manager.cancel(analysis_id, reason)
        
        if success:
            self.logger.log_cancellation(analysis_id, reason.value)
            
            # 如果是任務佇列中的任務，也要取消
            await self.task_queue.cancel_task(analysis_id)
        
        return success
    
    def get_active_analyses(self) -> List[Dict[str, Any]]:
        """獲取活動中的分析列表"""
        analyses = []
        
        for analysis_id, token in self._active_analyses.items():
            analyses.append({
                'id': analysis_id,
                'is_cancelled': token.is_cancelled,
                'cancelled_at': token.cancelled_at.isoformat() if token.cancelled_at else None,
                'reason': token.reason.value if token.reason else None
            })
        
        return analyses
    
    async def cancel_all_analyses(self, reason: CancellationReason = CancellationReason.SYSTEM_SHUTDOWN):
        """取消所有分析"""
        await self.cancellation_manager.cancel_all(reason)
        self.logger.log_analysis("warning", f"取消所有分析: {reason.value}")
    
    async def cleanup_completed_analyses(self, max_age_hours: int = 24):
        """清理已完成的分析"""
        await self.cancellation_manager.cleanup_old_tokens(max_age_hours)
        
        # 也清理資料庫中的舊記錄
        await self.storage.cleanup_old_records(max_age_hours * 24 // 24)  # 轉換為天數
    
    def get_cancellation_stats(self) -> Dict[str, int]:
        """獲取取消統計"""
        return {
            'active_count': self.cancellation_manager.get_active_count(),
            'cancelled_count': self.cancellation_manager.get_cancelled_count(),
            'total_count': len(self._active_analyses)
        }
    
    async def start(self):
        """啟動引擎服務"""
        await super().start()
        
        # 定期清理已完成的分析
        asyncio.create_task(self._periodic_cleanup())
    
    async def shutdown(self):
        """關閉引擎服務"""
        # 取消所有活動分析
        await self.cancel_all_analyses()
        
        # 關閉父類服務
        await super().shutdown()
    
    async def _periodic_cleanup(self):
        """定期清理已完成的分析"""
        while True:
            await asyncio.sleep(3600)  # 每小時
            await self.cleanup_completed_analyses()
            self.logger.log_analysis("info", "已完成分析清理完成")