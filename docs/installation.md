# 安裝指南

本指南將幫助您在不同環境中安裝和配置 ANR/Tombstone AI 分析系統。

## 系統需求

### 硬體需求
- CPU: 2 核心以上
- 記憶體: 4GB 以上（建議 8GB）
- 儲存空間: 10GB 以上

### 軟體需求
- Python 3.11 或更高版本
- Docker 和 Docker Compose（可選）
- PostgreSQL 15+（可選，可使用 SQLite）
- Redis 7+（可選）
- Nginx（生產環境）

## 快速開始

### 使用快速啟動腳本

最簡單的方式是使用提供的快速啟動腳本：

```bash
# 克隆專案
git clone https://github.com/your-org/anr-tombstone-ai-analyzer.git
cd anr-tombstone-ai-analyzer

# 賦予執行權限
chmod +x quick_start.sh

# 執行快速啟動
./quick_start.sh
```

腳本會引導您選擇合適的啟動模式。

## 詳細安裝步驟

### 1. 基礎環境準備

#### Python 環境
```bash
# 檢查 Python 版本
python3 --version  # 應該是 3.11+

# 創建虛擬環境
python3 -m venv venv

# 啟動虛擬環境
# Linux/macOS:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# 升級 pip
pip install --upgrade pip
```

#### 安裝依賴
```bash
# 安裝 Python 依賴
pip install -r requirements.txt

# 開發環境額外依賴
pip install -r requirements-dev.txt  # 如果存在
```

### 2. 配置設定

#### 環境變數
```bash
# 複製環境變數範例
cp .env.example .env

# 編輯 .env 檔案
nano .env  # 或使用您喜歡的編輯器
```

必須設定的環境變數：
- `ANTHROPIC_API_KEY`: Anthropic API 金鑰
- `OPENAI_API_KEY`: OpenAI API 金鑰（至少需要其中一個）

#### 系統配置
```bash
# 複製配置範例（如果需要自定義）
cp config.yaml.example config.yaml

# 編輯配置
nano config.yaml
```

### 3. 資料庫設定

#### 選項 A: 使用 SQLite（開發環境）
無需額外設定，系統會自動使用 SQLite。

#### 選項 B: 使用 PostgreSQL（推薦用於生產環境）
```bash
# 安裝 PostgreSQL（Ubuntu/Debian）
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib

# 創建資料庫和用戶
sudo -u postgres psql
CREATE DATABASE ai_analyzer;
CREATE USER analyzer WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE ai_analyzer TO analyzer;
\q

# 更新 .env 中的 DATABASE_URL
DATABASE_URL=postgresql://analyzer:your_password@localhost:5432/ai_analyzer
```

#### 初始化資料庫
```bash
# 執行資料庫初始化腳本
python scripts/setup_db.py

# 或手動執行遷移
alembic upgrade head
```

### 4. Redis 設定（可選）

Redis 用於快取和速率限制：

```bash
# 安裝 Redis（Ubuntu/Debian）
sudo apt-get install redis-server

# 啟動 Redis
sudo systemctl start redis-server
sudo systemctl enable redis-server

# 測試連接
redis-cli ping  # 應該返回 PONG

# 更新 .env 中的 REDIS_URL
REDIS_URL=redis://localhost:6379/0
```

## Docker 安裝

### 1. 安裝 Docker

參考官方文檔：
- [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/)
- [Docker Desktop for Mac](https://docs.docker.com/desktop/install/mac-install/)
- [Docker Engine for Linux](https://docs.docker.com/engine/install/)

### 2. 使用 Docker Compose

```bash
# 構建映像
docker-compose build

# 啟動所有服務
docker-compose up -d

# 查看日誌
docker-compose logs -f

# 停止服務
docker-compose down
```

### 3. Docker 環境變數

創建 `.env` 檔案或使用環境變數：

```bash
# 設定環境變數
export ANTHROPIC_API_KEY=your_key
export OPENAI_API_KEY=your_key

# 或在 docker-compose.yml 中直接設定
```

## 生產環境部署

### 1. Nginx 配置

```bash
# 安裝 Nginx
sudo apt-get install nginx

# 複製配置檔案
sudo cp nginx.conf /etc/nginx/sites-available/anr-analyzer
sudo ln -s /etc/nginx/sites-available/anr-analyzer /etc/nginx/sites-enabled/

# 測試配置
sudo nginx -t

# 重啟 Nginx
sudo systemctl restart nginx
```

### 2. 使用 Gunicorn

```bash
# 安裝 Gunicorn（已包含在 requirements.txt）
pip install gunicorn[gevent]

# 啟動應用
gunicorn -w 4 -k gevent --timeout 300 -b 0.0.0.0:5000 src.api.app:app
```

### 3. 系統服務設定

創建 systemd 服務檔案 `/etc/systemd/system/anr-analyzer.service`：

```ini
[Unit]
Description=ANR/Tombstone AI Analyzer
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/path/to/anr-tombstone-ai-analyzer
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/gunicorn -w 4 -k gevent --timeout 300 -b 0.0.0.0:5000 src.api.app:app
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

啟動服務：
```bash
sudo systemctl daemon-reload
sudo systemctl start anr-analyzer
sudo systemctl enable anr-analyzer
```

## 驗證安裝

### 1. 健康檢查

```bash
# API 健康檢查
curl http://localhost:5000/api/health

# 詳細健康檢查
python scripts/health_check.py
```

### 2. 測試 API

```bash
# 執行 API 測試腳本
python scripts/test_api.py

# 或使用 curl 測試
curl -X POST http://localhost:5000/api/ai/estimate-analysis-cost \
  -H "Content-Type: application/json" \
  -d '{"file_size_kb": 1024, "mode": "intelligent"}'
```

### 3. 存取網頁介面

開啟瀏覽器訪問：
- 開發環境: http://localhost:5566
- Docker 環境: http://localhost
- 生產環境: http://your-domain.com

## 故障排除

### Python 相關
- **ImportError**: 確保虛擬環境已啟動並安裝所有依賴
- **版本不符**: 使用 `pyenv` 或 `conda` 管理 Python 版本

### 資料庫相關
- **連接失敗**: 檢查資料庫服務是否運行，連接字串是否正確
- **權限問題**: 確保資料庫用戶有足夠的權限

### Docker 相關
- **端口衝突**: 修改 docker-compose.yml 中的端口映射
- **權限問題**: 確保 Docker daemon 正在運行，用戶有 Docker 權限

### API 金鑰相關
- **401 錯誤**: 檢查 API 金鑰是否正確設定
- **配額超限**: 檢查 API 使用配額

## 下一步

- 閱讀[配置說明](configuration.md)了解詳細配置選項
- 查看[使用者指南](user-guide.md)開始使用系統
- 參考[API 文檔](api-reference.md)進行整合開發