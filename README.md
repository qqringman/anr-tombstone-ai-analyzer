# ANR/Tombstone AI 分析系統

<div align="center">
  <h3>🤖 使用 AI 技術分析 Android 崩潰日誌的專業工具</h3>
  
  [![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
  [![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
  [![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](Dockerfile)
</div>

## ✨ 主要特色

- 🤖 **多 AI 支援**: Anthropic Claude 4 和 OpenAI GPT-4
- 🎯 **智能分析**: 4 種分析模式適應不同需求
- ⚡ **即時串流**: 支援大檔案處理和即時進度更新
- 🛑 **可中斷**: 隨時取消進行中的分析
- 💰 **成本控制**: 預估和監控 API 使用成本
- 📊 **視覺化**: 美觀的網頁介面和圖表展示

## 🚀 快速開始

```bash
# 1. 安裝依賴
pip install -r requirements.txt

# 2. 設定環境變數
cp .env.example .env
# 編輯 .env 填入 API keys

# 3. 啟動服務
python -m src.api.app

# 或使用 Docker
docker-compose up -d
```

詳細文檔請參考 [docs/](docs/) 目錄。
