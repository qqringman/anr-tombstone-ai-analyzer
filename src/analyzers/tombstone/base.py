"""
基礎 Tombstone 分析器
"""
from typing import Optional, List, Dict, Any
import re

from ..base import BaseAnalyzer
from ...config.base import AnalysisMode, ModelProvider

class BaseTombstoneAnalyzer(BaseAnalyzer):
    """基礎 Tombstone 分析器"""
    
    def validate_content(self, content: str) -> bool:
        """驗證是否為有效的 Tombstone 日誌"""
        # Tombstone 日誌特徵
        tombstone_indicators = [
            r"\*\*\* \*\*\* \*\*\*",
            r"Build fingerprint:",
            r"ABI:",
            r"signal \d+ \(SIG\w+\)",
            r"backtrace:",
            r"#\d+ pc [0-9a-f]+",
            r"Tombstone written to:",
            r"pid: \d+, tid: \d+",
            r"Abort message:"
        ]
        
        # 檢查是否包含 Tombstone 特徵
        matches = 0
        for indicator in tombstone_indicators:
            if re.search(indicator, content, re.IGNORECASE):
                matches += 1
        
        # 至少匹配 3 個特徵才認為是 Tombstone 日誌
        return matches >= 3
    
    def extract_key_info(self, content: str) -> Dict[str, Any]:
        """提取關鍵資訊"""
        info = {
            "pid": None,
            "tid": None,
            "signal": None,
            "signal_name": None,
            "abort_message": None,
            "fault_address": None,
            "process_name": None,
            "build_fingerprint": None
        }
        
        # 提取 PID 和 TID
        pid_tid_match = re.search(r"pid: (\d+), tid: (\d+)", content)
        if pid_tid_match:
            info["pid"] = pid_tid_match.group(1)
            info["tid"] = pid_tid_match.group(2)
        
        # 提取信號
        signal_match = re.search(r"signal (\d+) \((\w+)\)", content)
        if signal_match:
            info["signal"] = signal_match.group(1)
            info["signal_name"] = signal_match.group(2)
        
        # 提取 abort 訊息
        abort_match = re.search(r"Abort message: '([^']+)'", content)
        if abort_match:
            info["abort_message"] = abort_match.group(1)
        
        # 提取錯誤地址
        fault_match = re.search(r"fault addr (0x[0-9a-f]+)", content)
        if fault_match:
            info["fault_address"] = fault_match.group(1)
        
        # 提取進程名
        process_match = re.search(r">>> ([\w\.]+) <<<", content)
        if process_match:
            info["process_name"] = process_match.group(1)
        
        # 提取 build fingerprint
        build_match = re.search(r"Build fingerprint: '([^']+)'", content)
        if build_match:
            info["build_fingerprint"] = build_match.group(1)
        
        return info
    
    def get_prompt(self, content: str, mode: AnalysisMode) -> str:
        """獲取 Tombstone 分析提示詞"""
        key_info = self.extract_key_info(content)
        
        base_prompt = f"""你是一位 Android Native 開發專家，專門分析 Tombstone (Native Crash) 問題。
請分析以下 Tombstone 日誌，並提供詳細的崩潰分析報告。

關鍵資訊：
- PID/TID: {key_info['pid']}/{key_info['tid']}
- 信號: {key_info['signal']} ({key_info['signal_name']})
- 進程: {key_info['process_name']}
- Abort 訊息: {key_info['abort_message']}
- 錯誤地址: {key_info['fault_address']}

"""
        
        if mode == AnalysisMode.QUICK:
            base_prompt += """
請提供簡潔的分析，包括：
1. **崩潰原因**：一句話說明崩潰原因
2. **問題定位**：最可能的問題代碼位置
3. **快速修復**：立即可行的修復方案（2-3個）

保持簡潔，直指問題核心。
"""
        elif mode == AnalysisMode.INTELLIGENT:
            base_prompt += """
請提供全面的崩潰分析，包括：
1. **崩潰摘要**：清晰描述崩潰情況
2. **堆疊追蹤分析**：
   - 關鍵幀解析
   - 函數調用鏈
   - 可能的問題代碼
3. **根本原因分析**：
   - 信號含義
   - 記憶體問題分析
   - 並發問題檢查
4. **解決方案**：
   - 代碼修復建議
   - 防禦性編程建議
5. **調試建議**：如何進一步調試

請使用 Markdown 格式，包含代碼示例。
"""
        elif mode == AnalysisMode.LARGE_FILE:
            base_prompt += """
這是一個詳細的 Tombstone 日誌。請進行深入分析：
1. **執行摘要**：崩潰概述
2. **完整堆疊分析**：
   - 所有線程的堆疊
   - 符號解析
   - 內存佈局分析
3. **系統狀態分析**：
   - 寄存器狀態
   - 內存映射
   - 共享庫加載
4. **問題診斷**：
   - 記憶體錯誤（溢出、野指針等）
   - 並發問題（競態、死鎖等）
   - 系統資源問題
5. **完整解決方案**：
   - 具體代碼修改
   - 架構改進
   - 測試策略

請提供深入的技術分析。
"""
        else:  # MAX_TOKEN
            base_prompt += """
請提供最詳盡的崩潰分析報告：
1. **執行摘要**
2. **崩潰時間軸重建**
3. **完整堆疊追蹤分析**：
   - 每個堆疊幀的詳細解析
   - 反彙編代碼分析
   - 源代碼定位
4. **記憶體分析**：
   - 堆疊狀態
   - 堆使用情況
   - 內存洩漏檢測
5. **系統級分析**：
   - CPU 寄存器狀態
   - 信號處理機制
   - 內核態/用戶態切換
6. **代碼審查**：
   - 問題代碼識別
   - 安全漏洞檢查
   - 最佳實踐違反
7. **修復方案**：
   - 短期修復
   - 長期改進
   - 預防措施
8. **測試建議**：
   - 單元測試
   - 壓力測試
   - 模糊測試
9. **監控方案**

請盡可能詳細，包含所有技術細節和代碼示例。
"""
        
        base_prompt += f"\n\nTombstone 日誌內容：\n{content}"
        
        return base_prompt
    
    def preprocess_content(self, content: str) -> str:
        """預處理 Tombstone 內容"""
        content = super().preprocess_content(content)
        
        # Tombstone 特定的預處理
        # 保留所有內容，因為每一行都可能包含重要資訊
        
        return content
    
    async def chunk_content(self, content: str, mode: AnalysisMode) -> List[str]:
        """Tombstone 特定的分塊策略"""
        # 嘗試按主要區段分塊
        sections = []
        current_section = []
        
        lines = content.split('\n')
        section_markers = [
            "*** *** ***",
            "backtrace:",
            "stack:",
            "memory near",
            "code around",
            "registers:",
            "memory map:"
        ]
        
        for line in lines:
            # 檢查是否為新區段
            is_new_section = any(marker in line.lower() for marker in section_markers)
            
            if is_new_section and current_section:
                sections.append('\n'.join(current_section))
                current_section = [line]
            else:
                current_section.append(line)
        
        if current_section:
            sections.append('\n'.join(current_section))
        
        # 根據模式合併區段
        if mode == AnalysisMode.QUICK:
            # 快速模式：只保留最重要的部分
            important_sections = []
            for section in sections:
                if any(marker in section.lower() for marker in ["*** *** ***", "backtrace:", "abort message"]):
                    important_sections.append(section)
            return important_sections[:3]  # 最多 3 個區段
        
        elif mode == AnalysisMode.MAX_TOKEN:
            # 最大 token 模式：返回所有區段
            return sections
        
        else:
            # 其他模式：根據大小合併區段
            chunk_size = 100000 if mode == AnalysisMode.INTELLIGENT else 150000
            chunks = []
            current_chunk = []
            current_size = 0
            
            for section in sections:
                section_size = len(section)
                
                if current_size + section_size > chunk_size and current_chunk:
                    chunks.append('\n\n'.join(current_chunk))
                    current_chunk = [section]
                    current_size = section_size
                else:
                    current_chunk.append(section)
                    current_size += section_size
            
            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))
            
            return chunks
    
    def analyze_backtrace(self, content: str) -> List[Dict[str, Any]]:
        """分析 backtrace"""
        frames = []
        backtrace_pattern = re.compile(
            r"#(\d+)\s+pc\s+([0-9a-f]+)\s+(/[^\s]+)\s*\(([^\)]*)\)"
        )
        
        for match in backtrace_pattern.finditer(content):
            frame = {
                "number": int(match.group(1)),
                "pc": match.group(2),
                "library": match.group(3),
                "function": match.group(4) if match.group(4) else "unknown"
            }
            frames.append(frame)
        
        return frames