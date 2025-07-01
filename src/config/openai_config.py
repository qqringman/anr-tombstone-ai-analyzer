"""
OpenAI API 配置
"""
from typing import Dict
from .base import BaseApiConfig, ModelConfig, AnalysisMode

class OpenApiConfig(BaseApiConfig):
    """OpenAI API 配置"""
    
    base_url: str = "https://api.openai.com/v1"
    organization: str = None
    
    # OpenAI 模型配置 - 修正價格單位（每 1k tokens）
    models: Dict[str, ModelConfig] = {
        # GPT-4o 系列
        "gpt-4o-mini": ModelConfig(
            name="gpt-4o-mini",
            max_tokens=16384,
            input_cost_per_1k=0.00015,   # $0.15 per million = $0.00015 per 1k
            output_cost_per_1k=0.0006,   # $0.60 per million = $0.0006 per 1k
            context_window=128000,
            supports_streaming=True,
            supports_function_calling=True
        ),
        "gpt-4o": ModelConfig(
            name="gpt-4o",
            max_tokens=16384,
            input_cost_per_1k=0.0025,    # $2.50 per million = $0.0025 per 1k
            output_cost_per_1k=0.01,     # $10 per million = $0.01 per 1k
            context_window=128000,
            supports_streaming=True,
            supports_function_calling=True
        ),
        
        # GPT-4 Turbo
        "gpt-4-turbo": ModelConfig(
            name="gpt-4-turbo",
            max_tokens=4096,
            input_cost_per_1k=0.01,      # $10 per million = $0.01 per 1k
            output_cost_per_1k=0.03,     # $30 per million = $0.03 per 1k
            context_window=128000,
            supports_streaming=True,
            supports_function_calling=True
        ),
        
        # GPT-3.5 Turbo
        "gpt-3.5-turbo": ModelConfig(
            name="gpt-3.5-turbo",
            max_tokens=4096,
            input_cost_per_1k=0.0005,    # $0.50 per million = $0.0005 per 1k
            output_cost_per_1k=0.0015,   # $1.50 per million = $0.0015 per 1k
            context_window=16385,
            supports_streaming=True,
            supports_function_calling=True
        )
    }
    
    default_model: str = "gpt-4o"
    
    # 模式對應的模型
    mode_model_mapping: Dict[AnalysisMode, str] = {
        AnalysisMode.QUICK: "gpt-4o-mini",
        AnalysisMode.INTELLIGENT: "gpt-4o",
        AnalysisMode.LARGE_FILE: "gpt-4o",
        AnalysisMode.MAX_TOKEN: "gpt-4-turbo"
    }
    
    # OpenAI 特定設定
    temperature: float = 0.3
    top_p: float = 0.95
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    max_tokens: int = 4096
    stop: list[str] = None
    
    def get_model_for_mode(self, mode: AnalysisMode) -> str:
        """根據分析模式獲取模型名稱"""
        return self.mode_model_mapping.get(mode, self.default_model)
    
    def get_model_config(self, model: str) -> ModelConfig:
        """
        獲取模型配置
        
        Args:
            model: 模型名稱
            
        Returns:
            模型配置對象
        """
        if model not in self.models:
            raise ValueError(f"Unknown model: {model}")
        
        return self.models[model]
    
    def get_headers(self) -> Dict[str, str]:
        """獲取請求標頭"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        if self.organization:
            headers["OpenAI-Organization"] = self.organization
        return headers
    
    def estimate_tokens(self, text: str) -> int:
        """
        估算文本的 token 數量
        
        Args:
            text: 文本內容
            
        Returns:
            估算的 token 數
        """
        if not text:
            return 0
        
        # OpenAI 的 token 估算
        # 使用 tiktoken 庫會更準確，但這裡使用簡單估算
        
        # 計算中英文字符
        chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
        other_chars = len(text) - chinese_chars
        
        # 中文字符平均 2 個 tokens，英文平均 4 個字符一個 token
        estimated_tokens = chinese_chars * 2 + other_chars / 4
        
        # 添加 10% 的緩衝
        return int(estimated_tokens * 1.1)
    
    def calculate_api_calls(self, file_size_kb: float, mode: AnalysisMode) -> int:
        """計算需要的 API 調用次數"""
        # 估算總 tokens
        chars = file_size_kb * 1024
        total_tokens = int(chars / 4)  # OpenAI 平均 4 字符/token
        
        model = self.get_model_for_mode(mode)
        model_config = self.get_model_config(model)
        
        # 根據模式調整有效 context window
        mode_context_ratio = {
            AnalysisMode.QUICK: 0.9,
            AnalysisMode.INTELLIGENT: 0.7,
            AnalysisMode.LARGE_FILE: 0.6,
            AnalysisMode.MAX_TOKEN: 0.5
        }
        
        ratio = mode_context_ratio.get(mode, 0.7)
        effective_context = int(model_config.context_window * ratio)
        
        # 計算 API 調用次數
        return max(1, (total_tokens + effective_context - 1) // effective_context)
    
    def chunk_text(self, text: str, mode: AnalysisMode) -> list[str]:
        """根據模式切分文本"""
        # 根據模型的 context window 來決定 chunk 大小
        model = self.get_model_for_mode(mode)
        model_config = self.get_model_config(model)
        
        # 保留一些空間給系統 prompt 和輸出
        max_chunk_tokens = int(model_config.context_window * 0.7)
        max_chunk_chars = max_chunk_tokens * 4  # 粗略估算
        
        chunks = []
        
        # 如果文本較小，直接返回
        if len(text) <= max_chunk_chars:
            return [text]
        
        # 切分文本
        lines = text.split('\n')
        current_chunk = []
        current_size = 0
        
        for line in lines:
            line_size = len(line) + 1  # +1 for newline
            
            if current_size + line_size > max_chunk_chars and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_size = line_size
            else:
                current_chunk.append(line)
                current_size += line_size
        
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        return chunks
    
    def format_messages(self, system_prompt: str, user_prompt: str) -> list:
        """
        格式化消息列表
        
        Args:
            system_prompt: 系統提示詞
            user_prompt: 用戶提示詞
            
        Returns:
            格式化的消息列表
        """
        messages = []
        
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        messages.append({
            "role": "user",
            "content": user_prompt
        })
        
        return messages

    def get_model_context_window(self, model: str) -> int:
        """獲取模型的 context window"""
        if model in self.models:
            return self.models[model].context_window
        return 128000  # 預設值