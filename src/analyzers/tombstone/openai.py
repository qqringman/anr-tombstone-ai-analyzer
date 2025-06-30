"""
OpenAI Tombstone 分析器
"""
from typing import AsyncIterator, Optional, Dict, Any
import openai
from openai import AsyncOpenAI

from .base import BaseTombstoneAnalyzer
from ...config.base import AnalysisMode, ModelProvider
from ...config.openai_config import OpenApiConfig
from ...utils.status_manager import EnhancedStatusManager, MessageType
from ...core.cancellation import CancellationToken
from ...core.exceptions import CancellationException

class OpenApiStreamingTombstoneAnalyzer(BaseTombstoneAnalyzer):
    """OpenAI API 串流 Tombstone 分析器"""
    
    def __init__(self, 
                 config: OpenApiConfig,
                 status_manager: Optional[EnhancedStatusManager] = None):
        """
        初始化 OpenAI Tombstone 分析器
        
        Args:
            config: OpenAI API 配置
            status_manager: 狀態管理器
        """
        super().__init__(ModelProvider.OPENAI, status_manager)
        self.config = config
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            organization=config.organization
        )
    
    async def analyze(self, 
                     content: str, 
                     mode: AnalysisMode,
                     cancellation_token: Optional[CancellationToken] = None) -> AsyncIterator[str]:
        """執行 Tombstone 分析"""
        try:
            # 驗證內容
            if not self.validate_content(content):
                await self.status_manager.add_message(
                    MessageType.WARNING,
                    "內容可能不是有效的 Tombstone 日誌"
                )
            
            # 預處理
            content = self.preprocess_content(content)
            
            # 提取關鍵資訊
            key_info = self.extract_key_info(content)
            
            # 分塊
            chunks = await self.chunk_content(content, mode)
            total_chunks = len(chunks)
            
            await self.status_manager.update_progress(0, total_chunks)
            await self.status_manager.add_message(
                MessageType.INFO,
                f"開始使用 GPT 分析 Native 崩潰（{key_info['signal_name']}）"
            )
            
            # 輸出分析標題
            yield self.format_analysis_header("Tombstone", mode)
            
            # 系統提示詞
            system_prompt = self._get_system_prompt(mode)
            
            # 處理每個塊
            total_input_tokens = 0
            total_output_tokens = 0
            
            for i, chunk in enumerate(chunks):
                # 檢查取消
                await self.check_cancellation(cancellation_token)
                
                # 獲取提示詞
                user_prompt = self.get_prompt(chunk, mode)
                
                # 選擇模型
                model = self.config.get_model_for_mode(mode)
                
                # 輸出塊標題
                if total_chunks > 1:
                    yield self.format_chunk_header(i, total_chunks)
                
                # 呼叫 OpenAI API
                stream = await self.client.chat.completions.create(
                    model=model,
                    messages=self.config.format_messages(system_prompt, user_prompt),
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    top_p=self.config.top_p,
                    stream=True,
                    stream_options={"include_usage": True}
                )
                
                # 串流輸出
                async for chunk_response in stream:
                    # 檢查取消
                    await self.check_cancellation(cancellation_token)
                    
                    # 處理內容
                    if chunk_response.choices:
                        delta = chunk_response.choices[0].delta
                        if delta.content:
                            yield delta.content
                    
                    # 處理使用統計
                    if hasattr(chunk_response, 'usage') and chunk_response.usage:
                        total_input_tokens = chunk_response.usage.prompt_tokens
                        total_output_tokens = chunk_response.usage.completion_tokens
                
                # 更新 API 使用統計
                cost = self.config.calculate_cost(
                    total_input_tokens,
                    total_output_tokens,
                    model
                )
                await self.status_manager.update_api_usage(
                    total_input_tokens,
                    total_output_tokens,
                    cost
                )
                
                # 更新進度
                await self.status_manager.update_progress(i + 1, total_chunks)
                
                # 塊之間添加分隔
                if i < total_chunks - 1:
                    yield "\n\n---\n\n"
            
            # 完成
            await self.status_manager.add_message(
                MessageType.SUCCESS,
                f"Tombstone 分析完成（信號: {key_info['signal_name']}）"
            )
            
            # 更新統計
            self._stats["total_analyses"] += 1
            self._stats["total_chunks"] += total_chunks
            self._stats["total_tokens"] += total_input_tokens + total_output_tokens
            
        except CancellationException:
            await self.status_manager.record_cancellation("用戶取消")
            raise
        except openai.APIError as e:
            await self.status_manager.record_error(f"OpenAI API 錯誤: {str(e)}")
            yield self.format_error_response(e)
            raise
        except Exception as e:
            await self.status_manager.record_error(f"分析錯誤: {str(e)}")
            yield self.format_error_response(e)
            raise
    
    def _get_system_prompt(self, mode: AnalysisMode) -> str:
        """獲取系統提示詞"""
        base_prompt = """You are an expert Android Native developer specializing in crash analysis. 
You have deep expertise in:
- Native code debugging and crash analysis
- Memory management in C/C++
- Signal handling and system calls
- Android NDK and system libraries
- Assembly language and stack traces

Please provide analysis in Traditional Chinese (繁體中文) with high technical accuracy."""
        
        mode_specific = {
            AnalysisMode.QUICK: """
Focus on:
- Immediate crash cause identification
- Critical fixes only
- Clear and actionable solutions""",
            
            AnalysisMode.INTELLIGENT: """
Provide:
- Detailed stack trace analysis
- Memory corruption detection
- Signal interpretation
- Code-level recommendations
- Debugging strategies""",
            
            AnalysisMode.LARGE_FILE: """
Analyze:
- Complete memory state
- All thread interactions
- Register states
- Memory mappings
- System resource usage""",
            
            AnalysisMode.MAX_TOKEN: """
Include:
- Frame-by-frame stack analysis
- Assembly code interpretation
- Memory layout examination
- Comprehensive debugging guide
- Performance impact analysis
- Security implications"""
        }
        
        return base_prompt + mode_specific.get(mode, "")
    
    async def analyze_with_debugging_context(self, 
                                           content: str, 
                                           mode: AnalysisMode,
                                           debug_info: Optional[Dict[str, Any]] = None,
                                           cancellation_token: Optional[CancellationToken] = None) -> AsyncIterator[str]:
        """帶調試上下文的分析"""
        # 增強提示詞
        enhanced_messages = []
        
        # 系統提示
        system_prompt = self._get_system_prompt(mode)
        if debug_info:
            system_prompt += f"\n\n調試資訊：\n"
            if debug_info.get("source_code"):
                system_prompt += f"相關源代碼：\n{debug_info['source_code']}\n"
            if debug_info.get("build_config"):
                system_prompt += f"構建配置：{debug_info['build_config']}\n"
            if debug_info.get("previous_crashes"):
                system_prompt += f"歷史崩潰記錄：{debug_info['previous_crashes']}\n"
        
        enhanced_messages.append({"role": "system", "content": system_prompt})
        
        # 用戶提示
        user_prompt = self.get_prompt(content, mode)
        enhanced_messages.append({"role": "user", "content": user_prompt})
        
        # 使用增強的消息進行分析
        model = self.config.get_model_for_mode(mode)
        
        # 如果支持函數調用，添加調試函數
        if self.config.get_model_config(model).supports_function_calling:
            functions = [
                {
                    "name": "analyze_memory_corruption",
                    "description": "分析記憶體損壞",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "corruption_type": {
                                "type": "string",
                                "enum": ["buffer_overflow", "use_after_free", "double_free", "null_pointer"]
                            },
                            "affected_address": {"type": "string"},
                            "likely_cause": {"type": "string"}
                        }
                    }
                },
                {
                    "name": "suggest_debugging_steps",
                    "description": "建議調試步驟",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "steps": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "tools": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        }
                    }
                }
            ]
            
            stream = await self.client.chat.completions.create(
                model=model,
                messages=enhanced_messages,
                functions=functions,
                function_call="auto",
                stream=True
            )
        else:
            stream = await self.client.chat.completions.create(
                model=model,
                messages=enhanced_messages,
                stream=True
            )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content