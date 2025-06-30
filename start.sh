#!/bin/bash
echo "啟動 ANR/Tombstone AI 分析系統..."
source venv/bin/activate 2>/dev/null || python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3.12 -m src.api.app
