"""
OpenAI ANR 分析器
"""
from typing import AsyncIterator, Optional
import openai
from openai import AsyncOpenAI

from .base_anr import BaseANRAnalyzer
from ...config.base import AnalysisMode, ModelProvider
from ...config.openai_config import OpenApiConfig
from ...utils.status_manager import EnhancedStatusManager, MessageType
from ...core.cancellation import CancellationToken
from ...core.exceptions import CancellationException

class OpenApiStreamingANRAnalyzer(BaseANRAnalyzer):
    """OpenAI API 串流 ANR 分析器"""
    
    def __init__(self, 
                 config: OpenApiConfig,
                 status_manager: Optional[EnhancedStatusManager] = None):
        """
        初始化 OpenAI ANR 分析器
        
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
        """執行 ANR 分析"""
        try:
            # 驗證內容
            if not self.validate_content(content):
                await self.status_manager.add_message(
                    MessageType.WARNING,
                    "內容可能不是有效的 ANR 日誌"
                )
            
            # 預處理
            content = self.preprocess_content(content)
            
            # 分塊
            chunks = await self.chunk_content(content, mode)
            total_chunks = len(chunks)
            
            await self.status_manager.update_progress(0, total_chunks)
            await self.status_manager.add_message(
                MessageType.INFO,
                f"開始使用 GPT 分析 ANR 日誌（{total_chunks} 個區塊）"
            )
            
            # 輸出分析標題
            yield self.format_analysis_header("ANR", mode)
            
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
                chunk_content = []
                async for chunk_response in stream:
                    # 檢查取消
                    await self.check_cancellation(cancellation_token)
                    
                    # 處理內容
                    if chunk_response.choices:
                        delta = chunk_response.choices[0].delta
                        if delta.content:
                            yield delta.content
                            chunk_content.append(delta.content)
                    
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
                f"ANR 分析完成（使用模型: {model}）"
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
        base_prompt = """You are an expert Android system engineer specializing in ANR (Application Not Responding) analysis. 
You have deep knowledge of:
- Android system architecture and threading model
- Java/Kotlin concurrency and synchronization
- Common ANR patterns and their solutions
- Performance optimization techniques

Please provide analysis in Traditional Chinese (繁體中文) with technical accuracy."""
        
        mode_specific = {
            AnalysisMode.QUICK: """
Focus on:
- Quick identification of the root cause
- Most impactful solutions
- Clear and concise explanations""",
            
            AnalysisMode.INTELLIGENT: """
Provide:
- Comprehensive thread state analysis
- Detailed root cause investigation
- Multiple solution approaches
- Code examples when relevant""",
            
            AnalysisMode.LARGE_FILE: """
Analyze:
- All thread interactions and dependencies
- System resource usage patterns
- Complex synchronization issues
- Architecture-level problems""",
            
            AnalysisMode.MAX_TOKEN: """
Include:
- Exhaustive thread-by-thread analysis
- Complete call stack interpretation
- Detailed code-level recommendations
- Performance profiling suggestions
- Testing and monitoring strategies"""
        }
        
        return base_prompt + mode_specific.get(mode, "")
    
    async def analyze_with_functions(self, 
                                   content: str, 
                                   mode: AnalysisMode,
                                   cancellation_token: Optional[CancellationToken] = None) -> AsyncIterator[str]:
        """使用函數調用的分析（GPT-4 特性）"""
        # 定義分析函數
        functions = [
            {
                "name": "identify_blocked_thread",
                "description": "識別被阻塞的線程",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "thread_name": {"type": "string"},
                        "blocked_on": {"type": "string"},
                        "holding_thread": {"type": "string"}
                    }
                }
            },
            {
                "name": "suggest_fix",
                "description": "建議修復方案",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "issue_type": {"type": "string"},
                        "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                        "fix_description": {"type": "string"},
                        "code_example": {"type": "string"}
                    }
                }
            }
        ]
        
        # 使用函數調用進行分析
        model = self.config.get_model_for_mode(mode)
        
        response = await self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": self._get_system_prompt(mode)},
                {"role": "user", "content": self.get_prompt(content, mode)}
            ],
            functions=functions,
            function_call="auto",
            stream=True
        )
        
        async for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content