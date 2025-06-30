"""
Anthropic ANR 分析器
"""
from typing import Any, AsyncIterator, Dict, Optional
import anthropic
from anthropic import AsyncAnthropic

from .base import BaseANRAnalyzer
from ...config.base import AnalysisMode, ModelProvider
from ...config.anthropic_config import AnthropicApiConfig
from ...utils.status_manager import EnhancedStatusManager, MessageType
from ...core.cancellation import CancellationToken
from ...core.exceptions import CancellationException

class AnthropicApiStreamingANRAnalyzer(BaseANRAnalyzer):
    """Anthropic API 串流 ANR 分析器"""
    
    def __init__(self, 
                 config: AnthropicApiConfig,
                 status_manager: Optional[EnhancedStatusManager] = None):
        """
        初始化 Anthropic ANR 分析器
        
        Args:
            config: Anthropic API 配置
            status_manager: 狀態管理器
        """
        super().__init__(ModelProvider.ANTHROPIC, status_manager)
        self.config = config
        self.client = AsyncAnthropic(api_key=config.api_key)
    
    async def analyze(self, 
                 content: str, 
                 mode: AnalysisMode,
                 cancellation_token: Optional[CancellationToken] = None) -> AsyncIterator[str]:
        """執行 ANR 分析"""
        print(f"[DEBUG] Starting analyze method")
        try:
            # 驗證內容
            if not self.validate_content(content):
                print(f"[DEBUG] Content validation failed")
                # 不要等待 status_manager，直接輸出警告
                yield "⚠️ 警告：內容可能不是有效的 ANR 日誌\n\n"
            
            print(f"[DEBUG] Preprocessing content")
            # 預處理
            content = self.preprocess_content(content)
            
            print(f"[DEBUG] Chunking content")
            # 分塊
            chunks = await self.chunk_content(content, mode)
            total_chunks = len(chunks)
            print(f"[DEBUG] Total chunks: {total_chunks}")
            
            # 不使用 status_manager 的更新，直接輸出
            yield f"開始分析 ANR 日誌（{total_chunks} 個區塊）\n\n"
            
            # 輸出分析標題
            yield self.format_analysis_header("ANR", mode)
            
            # 處理每個塊
            for i, chunk in enumerate(chunks):
                print(f"[DEBUG] Processing chunk {i+1}/{total_chunks}")
                
                # 檢查取消
                if cancellation_token:
                    cancellation_token.check()
                
                # 獲取提示詞
                prompt = self.get_prompt(chunk, mode)
                
                # 選擇模型
                model = self.config.get_model_for_mode(mode)
                print(f"[DEBUG] Using model: {model}")
                
                # 輸出塊標題
                if total_chunks > 1:
                    yield self.format_chunk_header(i, total_chunks)
                
                try:
                    # 呼叫 Claude API
                    print(f"[DEBUG] Calling Anthropic API")
                    stream = await self.client.messages.create(
                        model=model,
                        max_tokens=self.config.get_model_config(model).max_tokens,
                        temperature=self.config.temperature,
                        messages=[
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        stream=True
                    )
                    
                    print(f"[DEBUG] Got stream response")
                    
                    # 串流輸出
                    async for event in stream:
                        if cancellation_token:
                            cancellation_token.check()
                        
                        if event.type == 'content_block_delta':
                            text = event.delta.text
                            if text:
                                yield text
                    
                    print(f"[DEBUG] Finished chunk {i+1}")
                    
                except Exception as e:
                    print(f"[DEBUG] API call error: {e}")
                    raise
                
                # 塊之間添加分隔
                if i < total_chunks - 1:
                    yield "\n\n---\n\n"
            
            # 完成
            yield "\n\n✅ ANR 分析完成\n"
            print(f"[DEBUG] Analysis completed")
            
        except Exception as e:
            print(f"[DEBUG] Analysis error: {e}")
            import traceback
            traceback.print_exc()
            yield self.format_error_response(e)
            raise
    
    async def analyze_with_context(self, 
                                  content: str, 
                                  mode: AnalysisMode,
                                  context: Dict[str, Any],
                                  cancellation_token: Optional[CancellationToken] = None) -> AsyncIterator[str]:
        """帶上下文的分析（支援多輪對話）"""
        # 構建系統提示詞
        system_prompt = """你是一位專業的 Android 系統專家，專門分析 ANR 問題。
你具有以下能力：
1. 深入理解 Android 系統架構和線程模型
2. 精通 Java/Kotlin 併發編程
3. 熟悉常見的 ANR 原因和解決方案
4. 能夠從堆疊追蹤中找出問題根源

請基於你的專業知識提供準確、實用的分析和建議。"""
        
        # 添加上下文資訊
        if context.get("previous_analysis"):
            system_prompt += f"\n\n之前的分析結果：\n{context['previous_analysis']}"
        
        if context.get("app_info"):
            system_prompt += f"\n\n應用資訊：\n{context['app_info']}"
        
        # 使用系統提示詞進行分析
        prompt = self.get_prompt(content, mode)
        model = self.config.get_model_for_mode(mode)
        
        stream = await self.client.messages.create(
            model=model,
            max_tokens=self.config.get_model_config(model).max_tokens,
            temperature=self.config.temperature,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            stream=True
        )
        
        async for event in stream:
            await self.check_cancellation(cancellation_token)
            
            if event.type == 'content_block_delta':
                text = event.delta.text
                if text:
                    yield text