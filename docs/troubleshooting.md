# 故障排除指南

本指南幫助您解決使用 ANR/Tombstone AI 分析系統時可能遇到的常見問題。

## 快速檢查清單

遇到問題時，請先檢查以下項目：

- [ ] API 金鑰是否正確設定？
- [ ] 網路連接是否正常？
- [ ] 檔案格式和大小是否符合要求？
- [ ] 系統服務是否都在運行？
- [ ] 是否有足夠的系統資源？
- [ ] 日誌中是否有錯誤訊息？

## 常見問題

### 安裝問題

#### 問題：pip install 失敗

**錯誤訊息：**
```
ERROR: Could not find a version that satisfies the requirement...
```

**解決方法：**
1. 確認 Python 版本：
   ```bash
   python --version  # 應該是 3.11+
   ```

2. 更新 pip：
   ```bash
   python -m pip install --upgrade pip
   ```

3. 使用國內鏡像源（如果在中國）：
   ```bash
   pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
   ```

4. 逐個安裝依賴：
   ```bash
   pip install anthropic
   pip install openai
   # 繼續其他套件...
   ```

#### 問題：Docker 構建失敗

**錯誤訊息：**
```
docker: Error response from daemon...
```

**解決方法：**
1. 檢查 Docker 服務：
   ```bash
   docker --version
   systemctl status docker  # Linux
   ```

2. 清理 Docker 資源：
   ```bash
   docker system prune -a
   ```

3. 增加 Docker 資源限制：
   - Docker Desktop: Settings → Resources
   - 增加 Memory 到至少 4GB
   - 增加 Disk 空間

4. 使用 BuildKit：
   ```bash
   DOCKER_BUILDKIT=1 docker build -t anr-analyzer .
   ```

### 配置問題

#### 問題：環境變數未生效

**症狀：**
- API 金鑰錯誤
- 使用預設配置而非自定義配置

**解決方法：**
1. 確認 .env 檔案位置：
   ```bash
   ls -la .env  # 應該在專案根目錄
   ```

2. 檢查 .env 格式：
   ```bash
   # 正確格式（無空格）
   ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
   
   # 錯誤格式
   ANTHROPIC_API_KEY = sk-ant-api03-xxxxx
   ```

3. 手動載入環境變數：
   ```bash
   export $(cat .env | xargs)
   ```

4. 使用 python-dotenv 驗證：
   ```python
   from dotenv import load_dotenv
   import os
   
   load_dotenv()
   print(os.getenv('ANTHROPIC_API_KEY'))
   ```

#### 問題：資料庫連接失敗

**錯誤訊息：**
```
sqlalchemy.exc.OperationalError: could not connect to server
```

**解決方法：**
1. PostgreSQL 問題：
   ```bash
   # 檢查服務
   sudo systemctl status postgresql
   
   # 測試連接
   psql -U analyzer -d ai_analyzer -h localhost
   
   # 檢查監聽地址
   sudo nano /etc/postgresql/15/main/postgresql.conf
   # listen_addresses = 'localhost'
   
   # 檢查認證
   sudo nano /etc/postgresql/15/main/pg_hba.conf
   # local all all md5
   ```

2. SQLite 問題：
   ```bash
   # 確保目錄存在
   mkdir -p data
   
   # 檢查權限
   chmod 755 data
   ```

3. 使用連接池：
   ```python
   # 在 config.yaml 中
   database:
     pool_size: 5
     pool_pre_ping: true
     pool_recycle: 3600
   ```

### API 問題

#### 問題：401 Unauthorized

**錯誤訊息：**
```json
{
  "status": "error",
  "message": "Invalid API token"
}
```

**解決方法：**
1. 檢查 API Token：
   ```bash
   curl -H "Authorization: Bearer YOUR_TOKEN" \
        http://localhost:5000/api/health
   ```

2. 生成新 Token：
   ```python
   import secrets
   print(secrets.token_urlsafe(32))
   ```

3. 檢查請求頭格式：
   ```javascript
   // 正確
   headers: {
     'Authorization': 'Bearer YOUR_TOKEN'
   }
   
   // 錯誤
   headers: {
     'Authorization': 'YOUR_TOKEN'
   }
   ```

#### 問題：429 Rate Limit Exceeded

**錯誤訊息：**
```json
{
  "status": "error",
  "message": "Rate limit exceeded",
  "retry_after": 45
}
```

**解決方法：**
1. 實作重試邏輯：
   ```python
   import time
   import requests
   
   def request_with_retry(url, max_retries=3):
       for i in range(max_retries):
           response = requests.get(url)
           if response.status_code == 429:
               retry_after = int(response.headers.get('Retry-After', 60))
               time.sleep(retry_after)
           else:
               return response
   ```

2. 調整速率限制：
   ```yaml
   # config.yaml
   limits:
     rate_limits:
       per_minute: 120  # 增加限制
       burst_size: 20
   ```

3. 使用快取減少請求：
   ```python
   from functools import lru_cache
   
   @lru_cache(maxsize=100)
   def cached_analysis(content_hash):
       return analyze(content_hash)
   ```

### 分析問題

#### 問題：分析超時

**錯誤訊息：**
```
AnalysisTimeoutException: Analysis timeout after 300 seconds
```

**解決方法：**
1. 增加超時時間：
   ```yaml
   # config.yaml
   analysis_modes:
     large_file:
       timeout: 900  # 15 分鐘
   ```

2. 使用分塊處理：
   ```python
   # 手動分塊
   def split_log(content, chunk_size=100000):
       return [content[i:i+chunk_size] 
               for i in range(0, len(content), chunk_size)]
   ```

3. 優化檔案大小：
   ```bash
   # 壓縮日誌
   grep -E "(main|FATAL|ERROR)" large.log > filtered.log
   ```

#### 問題：記憶體不足

**錯誤訊息：**
```
MemoryError: Unable to allocate array
```

**解決方法：**
1. 監控記憶體使用：
   ```python
   import psutil
   
   # 檢查可用記憶體
   memory = psutil.virtual_memory()
   if memory.available < 1024 * 1024 * 1024:  # 1GB
       raise MemoryError("Insufficient memory")
   ```

2. 使用串流處理：
   ```python
   # 串流讀取大檔案
   def read_in_chunks(file_path, chunk_size=1024*1024):
       with open(file_path, 'r') as f:
           while True:
               chunk = f.read(chunk_size)
               if not chunk:
                   break
               yield chunk
   ```

3. 調整工作者數量：
   ```yaml
   # 減少並行數
   parallel_processing:
     max_workers: 2  # 從 5 減少到 2
   ```

#### 問題：分析結果不準確

**症狀：**
- 錯誤識別問題
- 建議不相關
- 遺漏重要資訊

**解決方法：**
1. 提供更多上下文：
   ```python
   # 添加元資料
   enhanced_content = f"""
   App Version: 1.2.3
   Device: Pixel 6
   Android: 13
   
   {original_content}
   """
   ```

2. 使用更高階的模型：
   ```yaml
   # 使用 tier 4 模型
   model_preferences:
     mode_overrides:
       intelligent:
         anthropic: "claude-opus-4-20250514"
   ```

3. 調整 temperature：
   ```yaml
   providers:
     anthropic:
       temperature: 0.1  # 降低隨機性
   ```

### 網頁介面問題

#### 問題：檔案上傳失敗

**錯誤訊息：**
```
Failed to upload file
```

**解決方法：**
1. 檢查檔案大小限制：
   ```javascript
   // 在瀏覽器控制台
   console.log(file.size / 1024 / 1024 + ' MB');
   ```

2. 檢查 Nginx 配置：
   ```nginx
   # nginx.conf
   client_max_body_size 25M;
   ```

3. 檢查 Flask 配置：
   ```python
   app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024
   ```

#### 問題：SSE 連接中斷

**症狀：**
- 進度停止更新
- 無法接收即時訊息

**解決方法：**
1. 禁用 Nginx 緩衝：
   ```nginx
   location /api/ai/analyze-with-cancellation {
       proxy_buffering off;
       proxy_cache off;
       proxy_set_header X-Accel-Buffering no;
   }
   ```

2. 添加心跳機制：
   ```javascript
   eventSource.addEventListener('heartbeat', (e) => {
       console.log('Heartbeat received');
   });
   ```

3. 實作自動重連：
   ```javascript
   let retryCount = 0;
   
   eventSource.onerror = (error) => {
       if (retryCount < 3) {
           setTimeout(() => {
               retryCount++;
               reconnect();
           }, 5000);
       }
   };
   ```

### 效能問題

#### 問題：系統運行緩慢

**症狀：**
- API 響應慢
- 網頁載入慢
- 分析時間過長

**診斷步驟：**
1. 檢查系統資源：
   ```bash
   # CPU 和記憶體
   htop
   
   # 磁碟 I/O
   iotop
   
   # 網路
   iftop
   ```

2. 分析慢查詢：
   ```sql
   -- PostgreSQL
   SELECT query, mean_time, calls
   FROM pg_stat_statements
   ORDER BY mean_time DESC
   LIMIT 10;
   ```

3. 檢查日誌：
   ```bash
   # 查找錯誤
   grep ERROR logs/app.log | tail -50
   
   # 查找慢請求
   grep "duration" logs/app.log | awk '$NF > 5'
   ```

**優化方法：**
1. 啟用快取：
   ```yaml
   cache:
     enabled: true
     backend: redis
   ```

2. 優化資料庫：
   ```sql
   -- 添加索引
   CREATE INDEX idx_analysis_created 
   ON analysis_records(created_at);
   
   -- 清理舊資料
   DELETE FROM analysis_records 
   WHERE created_at < NOW() - INTERVAL '30 days';
   ```

3. 使用 CDN：
   ```html
   <!-- 使用 CDN 載入靜態資源 -->
   <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
   ```

### 日誌和調試

#### 啟用詳細日誌

1. **開發環境：**
   ```yaml
   logging:
     level: DEBUG
     handlers:
       console:
         level: DEBUG
   ```

2. **查看特定模組日誌：**
   ```python
   import logging
   logging.getLogger('src.analyzers').setLevel(logging.DEBUG)
   ```

3. **追蹤請求：**
   ```python
   # 添加請求 ID
   @app.before_request
   def before_request():
       g.request_id = str(uuid.uuid4())
       logger.info(f"Request started: {g.request_id}")
   ```

#### 使用調試工具

1. **Python 調試器：**
   ```python
   import pdb
   pdb.set_trace()  # 設置斷點
   ```

2. **Flask 調試模式：**
   ```bash
   export FLASK_ENV=development
   export FLASK_DEBUG=1
   ```

3. **瀏覽器開發工具：**
   - Network 標籤：檢查 API 請求
   - Console 標籤：查看 JavaScript 錯誤
   - Application 標籤：檢查 LocalStorage

### 緊急恢復

#### 資料庫損壞

1. **備份現有資料：**
   ```bash
   pg_dump ai_analyzer > backup_$(date +%Y%m%d).sql
   ```

2. **重建資料庫：**
   ```bash
   dropdb ai_analyzer
   createdb ai_analyzer
   psql ai_analyzer < schema.sql
   ```

3. **恢復資料：**
   ```bash
   psql ai_analyzer < backup_20250115.sql
   ```

#### 服務無法啟動

1. **檢查端口占用：**
   ```bash
   lsof -i :5000
   kill -9 <PID>
   ```

2. **清理臨時檔案：**
   ```bash
   rm -rf .cache/*
   rm -rf logs/*.log
   ```

3. **重置服務：**
   ```bash
   systemctl restart anr-analyzer
   systemctl status anr-analyzer
   ```

## 獲取幫助

### 收集診斷資訊

運行診斷腳本：
```bash
python scripts/collect_diagnostics.py
```

這會收集：
- 系統資訊
- 配置檔案（去除敏感資訊）
- 最近的日誌
- 健康檢查結果

### 回報問題

提交問題時請包含：
1. 錯誤訊息完整截圖
2. 重現步驟
3. 系統環境（OS、Python 版本等）
4. 診斷資訊（運行上述腳本）

### 社群支援

- GitHub Issues: https://github.com/your-org/anr-analyzer/issues
- Discord: https://discord.gg/anr-analyzer
- Stack Overflow: 標籤 `anr-analyzer`

### 商業支援

如需商業支援，請聯繫：
- Email: support@anr-analyzer.com
- 電話: +1-XXX-XXX-XXXX
- 線上客服: https://support.anr-analyzer.com