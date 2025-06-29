"""
Prompt 管理器
"""
import os
import yaml
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
import json

from .templates import PromptTemplate
from ..config.base import AnalysisMode, ModelProvider

class PromptManager:
    """Prompt 管理器"""
    
    def __init__(self, prompts_dir: str = None):
        """
        初始化 Prompt 管理器
        
        Args:
            prompts_dir: Prompt 檔案目錄
        """
        if prompts_dir is None:
            # 預設使用 src/prompts/data 目錄
            prompts_dir = Path(__file__).parent / "data"
        
        self.prompts_dir = Path(prompts_dir)
        self.prompts_cache: Dict[str, PromptTemplate] = {}
        
        # 載入所有 prompts
        self._load_prompts()
    
    def _load_prompts(self):
        """載入所有 prompt 檔案"""
        if not self.prompts_dir.exists():
            return
        
        # 載入 YAML 檔案
        for yaml_file in self.prompts_dir.glob("*.yaml"):
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                
                if data and isinstance(data, dict):
                    for key, prompt_data in data.items():
                        template = PromptTemplate.from_dict(prompt_data)
                        self.prompts_cache[key] = template
                        
            except Exception as e:
                print(f"Error loading {yaml_file}: {e}")
    
    def get_prompt(self, 
                  log_type: str, 
                  mode: AnalysisMode,
                  provider: Optional[ModelProvider] = None) -> Optional[PromptTemplate]:
        """
        獲取 prompt 模板
        
        Args:
            log_type: 日誌類型 (anr/tombstone)
            mode: 分析模式
            provider: AI 提供者（可選）
            
        Returns:
            Prompt 模板
        """
        # 構建 key
        keys = [
            f"{log_type}_{mode.value}_{provider.value}" if provider else None,
            f"{log_type}_{mode.value}",
            f"{log_type}_default"
        ]
        
        # 查找第一個匹配的 prompt
        for key in keys:
            if key and key in self.prompts_cache:
                return self.prompts_cache[key]
        
        return None
    
    def add_prompt(self, key: str, template: PromptTemplate):
        """添加 prompt 模板"""
        self.prompts_cache[key] = template
    
    def update_prompt(self, key: str, template: PromptTemplate):
        """更新 prompt 模板"""
        if key in self.prompts_cache:
            self.prompts_cache[key] = template
            template.updated_at = datetime.now()
    
    def delete_prompt(self, key: str):
        """刪除 prompt 模板"""
        if key in self.prompts_cache:
            del self.prompts_cache[key]
    
    def list_prompts(self) -> List[Dict[str, Any]]:
        """列出所有 prompts"""
        prompts = []
        for key, template in self.prompts_cache.items():
            prompts.append({
                "key": key,
                "name": template.name,
                "description": template.description,
                "version": template.version,
                "tags": template.tags,
                "created_at": template.created_at.isoformat() if template.created_at else None,
                "updated_at": template.updated_at.isoformat() if template.updated_at else None
            })
        return prompts
    
    def search_prompts(self, query: str) -> List[str]:
        """搜尋 prompts"""
        query = query.lower()
        results = []
        
        for key, template in self.prompts_cache.items():
            # 搜尋名稱、描述和標籤
            if (query in key.lower() or
                query in template.name.lower() or
                query in template.description.lower() or
                any(query in tag.lower() for tag in template.tags)):
                results.append(key)
        
        return results
    
    def save_prompts(self, output_dir: Optional[str] = None):
        """保存所有 prompts 到檔案"""
        if output_dir is None:
            output_dir = self.prompts_dir
        else:
            output_dir = Path(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 按類型分組
        grouped_prompts = {}
        for key, template in self.prompts_cache.items():
            # 從 key 中提取類型
            parts = key.split('_')
            if parts:
                prompt_type = parts[0]
                if prompt_type not in grouped_prompts:
                    grouped_prompts[prompt_type] = {}
                grouped_prompts[prompt_type][key] = template.to_dict()
        
        # 保存到不同檔案
        for prompt_type, prompts in grouped_prompts.items():
            output_file = output_dir / f"{prompt_type}_prompts.yaml"
            with open(output_file, 'w', encoding='utf-8') as f:
                yaml.dump(prompts, f, default_flow_style=False, allow_unicode=True)
    
    def export_prompts(self, format: str = "json") -> str:
        """匯出所有 prompts"""
        data = {
            key: template.to_dict() 
            for key, template in self.prompts_cache.items()
        }
        
        if format == "json":
            return json.dumps(data, ensure_ascii=False, indent=2, default=str)
        elif format == "yaml":
            return yaml.dump(data, default_flow_style=False, allow_unicode=True)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def import_prompts(self, data: str, format: str = "json"):
        """匯入 prompts"""
        if format == "json":
            prompts_data = json.loads(data)
        elif format == "yaml":
            prompts_data = yaml.safe_load(data)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        for key, prompt_data in prompts_data.items():
            template = PromptTemplate.from_dict(prompt_data)
            self.prompts_cache[key] = template
    
    def validate_prompt(self, template: PromptTemplate) -> List[str]:
        """驗證 prompt 模板"""
        errors = []
        
        # 檢查必要欄位
        if not template.name:
            errors.append("Name is required")
        
        if not template.system_prompt and not template.user_prompt:
            errors.append("At least one of system_prompt or user_prompt is required")
        
        # 檢查變數
        all_vars = set()
        if template.system_prompt:
            all_vars.update(template._extract_variables(template.system_prompt))
        if template.user_prompt:
            all_vars.update(template._extract_variables(template.user_prompt))
        
        # 確保所有變數都有預設值或在必要變數中
        for var in all_vars:
            if var not in template.variables and var not in template.required_variables:
                errors.append(f"Variable '{var}' is not defined")
        
        return errors
    
    def get_prompt_stats(self) -> Dict[str, Any]:
        """獲取 prompt 統計資訊"""
        total = len(self.prompts_cache)
        by_type = {}
        by_mode = {}
        
        for key in self.prompts_cache:
            parts = key.split('_')
            
            # 統計類型
            if parts:
                log_type = parts[0]
                by_type[log_type] = by_type.get(log_type, 0) + 1
            
            # 統計模式
            if len(parts) > 1:
                mode = parts[1]
                by_mode[mode] = by_mode.get(mode, 0) + 1
        
        return {
            "total": total,
            "by_type": by_type,
            "by_mode": by_mode,
            "cache_size": len(str(self.prompts_cache))
        }

# 全局 prompt 管理器實例
_global_prompt_manager: Optional[PromptManager] = None

def get_prompt_manager() -> PromptManager:
    """獲取全局 prompt 管理器"""
    global _global_prompt_manager
    if _global_prompt_manager is None:
        _global_prompt_manager = PromptManager()
    return _global_prompt_manager