"""
OpenAI API 配置
"""
from typing import Dict
from .base import BaseApiConfig, ModelConfig, AnalysisMode

class OpenApiConfig(BaseApiConfig):
    """OpenAI API 配置"""
    
    base_url: str = "https://api.openai.com/v1"
    organization: str = None
    
    # OpenAI 模型配置
    models: Dict[str, ModelConfig] = {
        # GPT-4o 系列
        "gpt-4o-mini": ModelConfig(
            name="gpt-4o-mini",
            max_tokens=16384,
            input_cost_per_1k=0.15,
            output_cost_per_1k=0.60,
            context_window=128000,
            supports_streaming=True,
            supports_function_calling=True
        ),
        "gpt-4o": ModelConfig(
            name="gpt-4o",
            max_tokens=16384,
            input_cost_per_1k=2.50,
            output_cost_per_1k=10.0,
            context_window=128000,
            supports_streaming=True,
            supports_function_calling=True
        ),
        
        # GPT-4 Turbo
        "gpt-4-turbo": ModelConfig(
            name="gpt-4-turbo",
            max_tokens=4096,
            input_cost_per_1k=10.0,
            output_cost_per_1k=30.0,
            context_window=128000,
            supports_streaming=True,
            supports_function_calling=True
        ),
        
        # GPT-3.5 Turbo
        "gpt-3.5-turbo": ModelConfig(
            name="gpt-3.5-turbo",
            max_tokens=4096,
            input_cost_per_1k=0.50,
            output_cost_per_1k=1.50,
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
    
    def get_model_config(self, model_name: str) -> ModelConfig:
        """獲取模型配置"""
        if model_name not in self.models:
            raise ValueError(f"Unknown model: {model_name}")
        return self.models[model_name]
    
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
        """估算文本的 token 數量"""
        # OpenAI 的 token 估算：大約每 4 個字符 1 個 token
        return int(len(text) / 4)
    
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
    
    def format_messages(self, system_prompt: str, user_prompt: str) -> list[dict]:
        """格式化消息"""
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]