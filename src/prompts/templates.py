"""
Prompt 模板類別
"""
from typing import Dict, Any, Optional, List, Set
from datetime import datetime
from dataclasses import dataclass, field
import re

@dataclass
class PromptTemplate:
    """Prompt 模板"""
    name: str
    description: str
    system_prompt: Optional[str] = None
    user_prompt: Optional[str] = None
    variables: Dict[str, Any] = field(default_factory=dict)
    required_variables: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    version: str = "1.0.0"
    created_at: Optional[datetime] = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def render(self, **kwargs) -> Dict[str, str]:
        """
        渲染 prompt 模板
        
        Args:
            **kwargs: 變數值
            
        Returns:
            包含 system_prompt 和 user_prompt 的字典
        """
        # 檢查必要變數
        missing_vars = set(self.required_variables) - set(kwargs.keys())
        if missing_vars:
            raise ValueError(f"Missing required variables: {missing_vars}")
        
        # 合併預設值和提供的值
        context = {**self.variables, **kwargs}
        
        result = {}
        
        # 渲染 system prompt
        if self.system_prompt:
            result['system_prompt'] = self._render_template(self.system_prompt, context)
        
        # 渲染 user prompt
        if self.user_prompt:
            result['user_prompt'] = self._render_template(self.user_prompt, context)
        
        return result
    
    def _render_template(self, template: str, context: Dict[str, Any]) -> str:
        """
        渲染單個模板字串
        
        Args:
            template: 模板字串
            context: 變數上下文
            
        Returns:
            渲染後的字串
        """
        # 使用簡單的字串格式化
        # 支援 {variable} 和 {variable|default} 語法
        def replace_var(match):
            var_expr = match.group(1)
            
            # 檢查是否有預設值
            if '|' in var_expr:
                var_name, default_value = var_expr.split('|', 1)
                var_name = var_name.strip()
                default_value = default_value.strip()
            else:
                var_name = var_expr.strip()
                default_value = ''
            
            # 獲取值
            value = context.get(var_name, default_value)
            
            # 處理特殊情況
            if value is None:
                value = default_value
            elif isinstance(value, (list, tuple)):
                value = ', '.join(str(v) for v in value)
            elif isinstance(value, dict):
                value = str(value)
            
            return str(value)
        
        # 替換所有變數
        pattern = r'\{([^}]+)\}'
        return re.sub(pattern, replace_var, template)
    
    def _extract_variables(self, template: str) -> Set[str]:
        """提取模板中的變數名"""
        pattern = r'\{([^}|]+)(?:\|[^}]*)?\}'
        matches = re.findall(pattern, template)
        return set(match.strip() for match in matches)
    
    def get_all_variables(self) -> Set[str]:
        """獲取所有變數名"""
        all_vars = set()
        
        if self.system_prompt:
            all_vars.update(self._extract_variables(self.system_prompt))
        
        if self.user_prompt:
            all_vars.update(self._extract_variables(self.user_prompt))
        
        return all_vars
    
    def validate(self) -> bool:
        """驗證模板是否有效"""
        # 至少要有一個 prompt
        if not self.system_prompt and not self.user_prompt:
            return False
        
        # 檢查所有必要變數是否有預設值
        all_vars = self.get_all_variables()
        for req_var in self.required_variables:
            if req_var not in all_vars:
                return False
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return {
            "name": self.name,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "variables": self.variables,
            "required_variables": self.required_variables,
            "tags": self.tags,
            "version": self.version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PromptTemplate':
        """從字典創建"""
        # 處理日期時間
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        
        return cls(**data)
    
    def clone(self) -> 'PromptTemplate':
        """複製模板"""
        return PromptTemplate(
            name=f"{self.name} (Copy)",
            description=self.description,
            system_prompt=self.system_prompt,
            user_prompt=self.user_prompt,
            variables=self.variables.copy(),
            required_variables=self.required_variables.copy(),
            tags=self.tags.copy(),
            version=self.version,
            created_at=datetime.now(),
            updated_at=None,
            metadata=self.metadata.copy()
        )
    
    def merge(self, other: 'PromptTemplate') -> 'PromptTemplate':
        """合併兩個模板"""
        # 合併 prompts
        system_prompt = self.system_prompt or other.system_prompt
        user_prompt = self.user_prompt or other.user_prompt
        
        # 合併變數
        variables = {**other.variables, **self.variables}
        
        # 合併必要變數
        required_vars = list(set(self.required_variables + other.required_variables))
        
        # 合併標籤
        tags = list(set(self.tags + other.tags))
        
        return PromptTemplate(
            name=f"{self.name} + {other.name}",
            description=f"Merged: {self.description} | {other.description}",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            variables=variables,
            required_variables=required_vars,
            tags=tags,
            version="1.0.0",
            created_at=datetime.now()
        )

# 預定義的 prompt 模板
DEFAULT_PROMPTS = {
    "anr_quick": PromptTemplate(
        name="ANR Quick Analysis",
        description="Quick analysis template for ANR logs",
        system_prompt="""You are an Android expert specializing in ANR analysis. 
Provide concise and actionable insights.""",
        user_prompt="""Analyze this ANR log and provide:
1. Root cause (1 sentence)
2. Quick fix (2-3 bullet points)
3. Priority level (High/Medium/Low)

ANR Log:
{content}""",
        variables={"content": ""},
        required_variables=["content"],
        tags=["anr", "quick", "android"]
    ),
    
    "tombstone_intelligent": PromptTemplate(
        name="Tombstone Intelligent Analysis",
        description="Comprehensive analysis for native crashes",
        system_prompt="""You are an Android Native development expert. 
Analyze crash logs with deep technical insights.""",
        user_prompt="""Perform a comprehensive analysis of this tombstone:

Key Info:
- Signal: {signal_name} ({signal})
- Process: {process_name}
- Abort Message: {abort_message|None}

Please provide:
1. **Crash Summary**
2. **Stack Trace Analysis**
3. **Root Cause Investigation**
4. **Code-level Solutions**
5. **Prevention Strategies**

Tombstone Log:
{content}""",
        variables={
            "content": "",
            "signal_name": "UNKNOWN",
            "signal": "0",
            "process_name": "unknown",
            "abort_message": None
        },
        required_variables=["content"],
        tags=["tombstone", "intelligent", "native", "crash"]
    )
}