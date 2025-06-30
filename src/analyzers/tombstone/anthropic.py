"""
Anthropic Tombstone 分析器
"""
from typing import AsyncIterator, Dict, Optional
import anthropic
from anthropic import AsyncAnthropic

from .base import BaseTombstoneAnalyzer
from ...config.base import AnalysisMode, ModelProvider
from ...config.anthropic_config import AnthropicApiConfig
from ...utils.status_manager import EnhancedStatusManager, MessageType
from ...core.cancellation import CancellationToken
from ...core.exceptions import CancellationException

class AnthropicApiStreamingTombstoneAnalyzer(BaseTombstoneAnalyzer):
    """Anthropic API 串流 Tombstone 分析器"""
    
    def __init__(self, 
                 config: AnthropicApiConfig,
                 status_manager: Optional[EnhancedStatusManager] = None):
        """
        初始化 Anthropic Tombstone 分析器
        
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
            
            # 提取關鍵資訊用於狀態顯示
            key_info = self.extract_key_info(content)
            crash_info = f"信號 {key_info['signal_name']} (PID: {key_info['pid']})"
            
            # 分塊
            chunks = await self.chunk_content(content, mode)
            total_chunks = len(chunks)
            
            await self.status_manager.update_progress(0, total_chunks)
            await self.status_manager.add_message(
                MessageType.INFO,
                f"開始分析 Tombstone 崩潰日誌 - {crash_info}"
            )
            
            # 輸出分析標題
            yield self.format_analysis_header("Tombstone", mode)
            
            # 如果有 abort message，先顯示
            if key_info['abort_message']:
                yield f"**Abort Message**: `{key_info['abort_message']}`\n\n"
            
            # 處理每個塊
            for i, chunk in enumerate(chunks):
                # 檢查取消
                await self.check_cancellation(cancellation_token)
                
                # 獲取提示詞
                prompt = self.get_prompt(chunk, mode)
                
                # 選擇模型
                model = self.config.get_model_for_mode(mode)
                
                # 輸出塊標題
                if total_chunks > 1:
                    yield self.format_chunk_header(i, total_chunks)
                
                # 呼叫 Claude API
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
                
                # 串流輸出
                chunk_tokens = 0
                async for event in stream:
                    # 檢查取消
                    await self.check_cancellation(cancellation_token)
                    
                    if event.type == 'content_block_delta':
                        text = event.delta.text
                        if text:
                            yield text
                            chunk_tokens += self.config.estimate_tokens(text)
                    
                    elif event.type == 'message_start':
                        # 更新使用統計
                        if hasattr(event, 'usage'):
                            await self.status_manager.update_api_usage(
                                event.usage.input_tokens,
                                0,
                                0
                            )
                    
                    elif event.type == 'message_delta':
                        # 更新輸出 tokens
                        if hasattr(event, 'usage'):
                            await self.status_manager.update_api_usage(
                                0,
                                event.usage.output_tokens,
                                self.config.calculate_cost(
                                    event.usage.input_tokens,
                                    event.usage.output_tokens,
                                    model
                                )
                            )
                
                # 更新進度
                await self.status_manager.update_progress(i + 1, total_chunks)
                
                # 塊之間添加分隔
                if i < total_chunks - 1:
                    yield "\n\n---\n\n"
            
            # 完成
            await self.status_manager.add_message(
                MessageType.SUCCESS,
                f"Tombstone 分析完成 - {crash_info}"
            )
            
            # 更新統計
            self._stats["total_analyses"] += 1
            self._stats["total_chunks"] += total_chunks
            
        except CancellationException:
            await self.status_manager.record_cancellation("用戶取消")
            raise
        except Exception as e:
            await self.status_manager.record_error(f"分析錯誤: {str(e)}")
            yield self.format_error_response(e)
            raise
    
    async def analyze_with_symbols(self, 
                                  content: str, 
                                  mode: AnalysisMode,
                                  symbol_files: Optional[Dict[str, str]] = None,
                                  cancellation_token: Optional[CancellationToken] = None) -> AsyncIterator[str]:
        """帶符號表的分析"""
        # 構建增強的提示詞
        enhanced_prompt = self.get_prompt(content, mode)
        
        if symbol_files:
            enhanced_prompt += "\n\n可用的符號資訊：\n"
            for lib_name, symbols in symbol_files.items():
                enhanced_prompt += f"\n{lib_name}:\n{symbols}\n"
        
        # 使用增強提示詞進行分析
        model = self.config.get_model_for_mode(mode)
        
        stream = await self.client.messages.create(
            model=model,
            max_tokens=self.config.get_model_config(model).max_tokens,
            temperature=self.config.temperature,
            system="""你是一位 Android Native 開發專家，擅長分析 Tombstone 崩潰日誌。
你能夠：
1. 解讀複雜的堆疊追蹤和記憶體轉儲
2. 識別常見的 Native 崩潰模式（記憶體錯誤、並發問題等）
3. 提供具體的代碼級修復建議
4. 使用符號表將地址解析為函數名

請基於提供的資訊進行深入分析。""",
            messages=[
                {
                    "role": "user",
                    "content": enhanced_prompt
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