"""
基礎 ANR 分析器
"""
from typing import Optional, List, Dict, Any
import re

from ..base import BaseAnalyzer
from ...config.base import AnalysisMode, ModelProvider

class BaseANRAnalyzer(BaseAnalyzer):
    """基礎 ANR 分析器"""

    def validate_content(self, content: str) -> bool:
        """驗證是否為有效的 ANR 日誌"""
        # ANR 日誌特徵
        anr_indicators = [
            r"----- pid \d+ at",
            r"Cmd line:",
            r"DALVIK THREADS",
            r'"main" prio=\d+ tid=\d+',
            r"at android\.",
            r"at com\.android\.",
            r"ActivityManager: ANR in"
        ]
        
        # 檢查是否包含 ANR 特徵
        matches = 0
        for indicator in anr_indicators:
            if re.search(indicator, content, re.IGNORECASE):
                matches += 1
        
        # 至少匹配 2 個特徵才認為是 ANR 日誌
        return matches >= 2
    
    def extract_key_info(self, content: str) -> Dict[str, Any]:
        """提取關鍵資訊"""
        info = {
            "pid": None,
            "package": None,
            "timestamp": None,
            "main_thread_state": None,
            "total_threads": 0
        }
        
        # 提取 PID
        pid_match = re.search(r"----- pid (\d+) at ([\d-]+ [\d:]+)", content)
        if pid_match:
            info["pid"] = pid_match.group(1)
            info["timestamp"] = pid_match.group(2)
        
        # 提取包名
        cmd_match = re.search(r"Cmd line: ([\w\.]+)", content)
        if cmd_match:
            info["package"] = cmd_match.group(1)
        
        # 提取主線程狀態
        main_thread_match = re.search(r'"main".*?tid=\d+ (\w+)', content)
        if main_thread_match:
            info["main_thread_state"] = main_thread_match.group(1)
        
        # 計算線程總數
        info["total_threads"] = len(re.findall(r'".*?" prio=\d+ tid=\d+', content))
        
        return info
    
    def get_prompt(self, content: str, mode: AnalysisMode) -> str:
        """獲取 ANR 分析提示詞"""
        key_info = self.extract_key_info(content)
        
        base_prompt = f"""你是一位 Android 系統專家，專門分析 ANR (Application Not Responding) 問題。
請分析以下 ANR 日誌，並提供詳細的分析報告。

關鍵資訊：
- PID: {key_info['pid']}
- 包名: {key_info['package']}
- 時間: {key_info['timestamp']}
- 主線程狀態: {key_info['main_thread_state']}
- 總線程數: {key_info['total_threads']}

"""
        
        if mode == AnalysisMode.QUICK:
            base_prompt += """
請提供簡潔的分析，包括：
1. **問題摘要**：一句話描述問題
2. **根本原因**：最可能的原因（1-2個）
3. **快速解決方案**：立即可行的解決方案（2-3個）

保持簡潔，重點突出。
"""
        elif mode == AnalysisMode.INTELLIGENT:
            base_prompt += """
請提供全面的分析，包括：
1. **問題摘要**：清晰描述 ANR 的情況
2. **線程狀態分析**：
   - 主線程阻塞位置
   - 相關線程狀態
   - 死鎖檢測
3. **根本原因分析**：深入分析可能的原因
4. **詳細解決方案**：
   - 短期修復方案
   - 長期優化建議
5. **預防措施**：如何避免類似問題

請使用 Markdown 格式，包含代碼示例。
"""
        elif mode == AnalysisMode.LARGE_FILE:
            base_prompt += """
這是一個大型 ANR 日誌。請進行深入分析：
1. **執行摘要**：問題概述
2. **詳細線程分析**：
   - 所有相關線程的狀態
   - 線程間的依賴關係
   - 資源競爭情況
3. **系統狀態分析**：
   - CPU 使用情況
   - 記憶體狀態
   - I/O 操作
4. **完整解決方案**：
   - 程式碼級別的修復
   - 架構改進建議
   - 性能優化策略
5. **監控建議**：如何監控和預防

請提供技術深度的分析。
"""
        else:  # MAX_TOKEN
            base_prompt += """
請提供最詳盡的分析報告：
1. **執行摘要**
2. **問題時間軸重建**
3. **完整線程分析**：
   - 每個線程的詳細狀態
   - 堆疊追蹤解析
   - 線程間互動分析
4. **系統級分析**：
   - 系統資源狀態
   - 進程優先級
   - Binder 交易分析
5. **程式碼級問題定位**：
   - 具體問題代碼
   - 修復示例
6. **架構和設計建議**
7. **性能優化方案**
8. **測試建議**
9. **監控和告警方案**

請盡可能詳細，包含所有技術細節。
"""
        
        base_prompt += f"\n\nANR 日誌內容：\n{content}"
        
        return base_prompt
    
    def preprocess_content(self, content: str) -> str:
        """預處理 ANR 內容"""
        content = super().preprocess_content(content)
        
        # 移除一些不必要的重複資訊
        lines = content.split('\n')
        processed_lines = []
        
        for line in lines:
            # 跳過某些不重要的行
            if line.strip() and not line.startswith('  | sysTid='):
                processed_lines.append(line)
        
        return '\n'.join(processed_lines)
    
    async def chunk_content(self, content: str, mode: AnalysisMode) -> List[str]:
        """ANR 特定的分塊策略 - 按線程分塊"""
        # 獲取基於模型的 chunk 大小
        max_chunk_size = await self._calculate_chunk_size(mode)
        
        # 嘗試按線程分塊
        thread_blocks = re.split(r'\n(?="[^"]*" prio=\d+ tid=\d+)', content)
        
        if len(thread_blocks) > 1:
            # 第一塊包含頭部資訊
            chunks = []
            header = thread_blocks[0]
            
            # 根據 chunk 大小決定每塊包含多少線程
            # 估算每個線程區塊的平均大小
            avg_thread_size = sum(len(block) for block in thread_blocks[1:]) / max(len(thread_blocks) - 1, 1)
            threads_per_chunk = max(1, int(max_chunk_size / avg_thread_size))
            
            # 根據模式調整線程數
            mode_thread_limits = {
                AnalysisMode.QUICK: min(threads_per_chunk, 20),
                AnalysisMode.INTELLIGENT: min(threads_per_chunk, 50),
                AnalysisMode.LARGE_FILE: min(threads_per_chunk, 100),
                AnalysisMode.MAX_TOKEN: threads_per_chunk  # 使用計算出的最大值
            }
            
            threads_per_chunk = mode_thread_limits.get(mode, 50)
            
            current_chunk = [header]
            current_size = len(header)
            thread_count = 0
            
            for thread_block in thread_blocks[1:]:
                block_size = len(thread_block)
                
                # 檢查是否會超過大小限制
                if current_size + block_size > max_chunk_size and current_chunk:
                    chunks.append('\n'.join(current_chunk))
                    current_chunk = [header]  # 每塊都包含頭部
                    current_size = len(header)
                    thread_count = 0
                
                current_chunk.append(thread_block)
                current_size += block_size
                thread_count += 1
                
                # 檢查線程數限制
                if thread_count >= threads_per_chunk:
                    chunks.append('\n'.join(current_chunk))
                    current_chunk = [header]
                    current_size = len(header)
                    thread_count = 0
            
            if len(current_chunk) > 1:  # 不只有 header
                chunks.append('\n'.join(current_chunk))
            
            self.logger.log_analysis(
                "info",
                f"ANR content chunked by threads",
                total_threads=len(thread_blocks) - 1,
                chunks=len(chunks),
                threads_per_chunk=threads_per_chunk
            )
            
            return chunks
        else:
            # 沒有線程結構，使用基類的分塊方法
            return await super().chunk_content(content, mode)
    
    def analyze_thread_state(self, thread_info: str) -> Dict[str, Any]:
        """分析單個線程狀態"""
        state = {
            "name": None,
            "tid": None,
            "state": None,
            "blocked_on": None,
            "held_locks": [],
            "waiting_locks": []
        }
        
        # 提取線程名和 ID
        header_match = re.search(r'"([^"]*)".*?tid=(\d+)\s+(\w+)', thread_info)
        if header_match:
            state["name"] = header_match.group(1)
            state["tid"] = header_match.group(2)
            state["state"] = header_match.group(3)
        
        # 查找阻塞資訊
        blocked_match = re.search(r'waiting to lock <(0x[0-9a-f]+)>', thread_info)
        if blocked_match:
            state["blocked_on"] = blocked_match.group(1)
        
        # 查找持有的鎖
        held_locks = re.findall(r'locked <(0x[0-9a-f]+)>', thread_info)
        state["held_locks"] = held_locks
        
        return state