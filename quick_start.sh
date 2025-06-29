#!/bin/bash
# quick_start.sh - 快速啟動 ANR/Tombstone AI 分析系統

set -e

echo "=========================================="
echo "ANR/Tombstone AI 分析系統 - 快速啟動"
echo "=========================================="
echo ""

# 顏色定義
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 檢查 Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}錯誤: 需要安裝 Python 3${NC}"
    exit 1
fi

# 檢查是否在專案目錄
if [ ! -f "requirements.txt" ]; then
    echo -e "${RED}錯誤: 請在專案根目錄執行此腳本${NC}"
    exit 1
fi

# 選擇啟動模式
echo "請選擇啟動模式:"
echo "1) 開發模式 (快速測試)"
echo "2) Docker 模式 (推薦)"
echo "3) 生產模式 (需要 Nginx)"
echo ""
read -p "請輸入選項 (1-3): " mode

case $mode in
    1)
        echo -e "\n${GREEN}啟動開發模式...${NC}"
        
        # 安裝依賴（如果需要）
        if [ ! -d "venv" ]; then
            echo "創建虛擬環境..."
            python3 -m venv venv
        fi
        
        # 啟動虛擬環境
        source venv/bin/activate
        
        echo "安裝依賴..."
        pip install -q -r requirements.txt
        
        # 檢查環境變數
        if [ ! -f ".env" ]; then
            echo -e "${YELLOW}警告: .env 檔案不存在，複製範例檔案${NC}"
            cp .env.example .env
            echo -e "${YELLOW}請編輯 .env 檔案並填入您的配置資訊 (包括 API_PORT 和 WEB_PORT)${NC}"
        fi
        
        # 從 .env 檔案加載變數
        # 這是一個簡單的解析 .env 檔案的方法
        # 更健壯的方法可能需要使用如 'dotenv' 類的工具，但對於 shell 腳本，這種方式足夠了
        if [ -f ".env" ]; then
            export $(grep -v '^#' .env | xargs)
        fi

        # 設定開發環境
        export ENVIRONMENT=development

        # 使用 .env 中的埠號，如果沒有設定則使用預設值
        API_PORT=${API_PORT:-5000}

        # 檢查並更新 Nginx 配置
        echo -e "\n${GREEN}檢查 Nginx 配置...${NC}"
        CURRENT_DIR=$(pwd)

        # 檢查配置文件是否需要更新
        if [ ! -f "/etc/nginx/sites-available/anr-analyzer" ] || [ "nginx.conf" -nt "/etc/nginx/sites-available/anr-analyzer" ]; then
            echo "更新 Nginx 配置..."
            sudo cp nginx.conf /etc/nginx/sites-available/anr-analyzer
            sudo ln -sf /etc/nginx/sites-available/anr-analyzer /etc/nginx/sites-enabled/
            
            # 更新配置中的路徑
            sudo sed -i "s|root /usr/share/nginx/html;|root $CURRENT_DIR/web;|g" /etc/nginx/sites-available/anr-analyzer
            
            # 如果有預設站點，可能需要禁用它避免衝突
            if [ -f "/etc/nginx/sites-enabled/default" ]; then
                echo "禁用預設站點..."
                sudo rm -f /etc/nginx/sites-enabled/default
            fi
            
            # 測試 Nginx 配置
            echo "測試 Nginx 配置..."
            if sudo nginx -t; then
                echo "✅ Nginx 配置正確"
                
                # 檢查 Nginx 狀態並採取適當行動
                if systemctl is-active --quiet nginx; then
                    echo "重載 Nginx..."
                    sudo systemctl reload nginx
                else
                    echo "啟動 Nginx..."
                    sudo systemctl start nginx
                fi
            else
                echo "❌ Nginx 配置錯誤，請檢查配置文件"
                exit 1
            fi
        else
            echo "✅ Nginx 配置已是最新"
        fi

        # 確保 Nginx 正在運行
        if ! pgrep -x "nginx" > /dev/null; then
            echo -e "${YELLOW}啟動 Nginx...${NC}"
            sudo systemctl start nginx || sudo nginx
        fi

		# 測試 Nginx 配置，確保沒有語法錯誤
		echo "測試 Nginx 配置..."
		sudo nginx -t

		# 檢查 Nginx 服務狀態，如果沒運行就啟動，否則重新載入
		echo "管理 Nginx 服務..."
		if systemctl is-active --quiet nginx; then
			echo "Nginx 正在運行，重新載入配置..."
			sudo systemctl reload nginx
		else
			echo "Nginx 未運行，啟動 Nginx 服務..."
			sudo systemctl start nginx
		fi
        
        # 殺死占用 API 埠號的進程
        echo -e "\n${GREEN}停止舊的 API 服務...${NC}"
        sudo kill -9 $(sudo lsof -t -i :$API_PORT) 2>/dev/null || true

        # 啟動 API 服務
        echo -e "\n${GREEN}啟動 API 服務器 (埠號: $API_PORT)...${NC}"
        python -m src.api.app &
        API_PID=$!
        echo "API PID: $API_PID"

        # 等待 API 啟動
        echo -n "等待 API 服務啟動"
        for i in {1..10}; do
            if curl -s http://$API_HOST:$API_PORT/api/health > /dev/null 2>&1; then
                echo " ✅"
                break
            fi
            echo -n "."
            sleep 1
        done

        # 檢查服務狀態
        echo -e "\n${GREEN}檢查服務狀態...${NC}"
        if curl -s http://$API_HOST:$API_PORT/api/health > /dev/null 2>&1; then
            echo "✅ 系統完整性檢查通過"
        else
            echo "⚠️  無法通過 Nginx 訪問 API，請檢查配置"
        fi

        echo -e "\n${GREEN}=========================================="
        echo "✅ 系統啟動成功！"
        echo "=========================================="
        echo ""
        echo "🌐 服務入口: http://$API_HOST:$API_PORT"
        echo "📊 API 健康檢查: http://$API_HOST:$API_PORT/api/health"
        echo "📚 API 文檔: http://$API_HOST:$API_PORT/api/docs"
        echo ""
        echo "📁 靜態文件目錄: $CURRENT_DIR/web"
        echo "🔧 Nginx 配置: /etc/nginx/sites-available/anr-analyzer"
        echo ""
        echo "按 Ctrl+C 停止服務"
        echo -e "==========================================${NC}"

        # 監控文件變更（可選）
        if command -v inotifywait &> /dev/null; then
            echo -e "\n${YELLOW}提示: 檢測到 inotifywait，可以自動重載前端變更${NC}"
            (
                while true; do
                    inotifywait -r -e modify,create,delete $CURRENT_DIR/web 2>/dev/null
                    echo "檢測到前端文件變更，重載 Nginx..."
                    sudo nginx -s reload
                done
            ) &
            WATCH_PID=$!
            trap "kill $API_PID $WATCH_PID 2>/dev/null; echo -e '\n✋ 服務已停止'" INT
        else
            trap "kill $API_PID 2>/dev/null; echo -e '\n✋ API 服務已停止'" INT
        fi

        wait
        ;;
        
    2)
        echo -e "\n${GREEN}啟動 Docker 模式...${NC}"
        
        # 檢查 Docker
        if ! command -v docker &> /dev/null; then
			echo "https://hackmd.io/@sfagnU0PRimo51yNhxS4JQ/BybieZGuU#%E5%AE%89%E8%A3%9D-docker"
			echo "https://blog.csdn.net/m0_51246196/article/details/138193180"
            echo -e "${RED}錯誤: 需要安裝 Docker${NC}"
            exit 1
        fi
        
        if ! command -v docker-compose &> /dev/null; then
            echo -e "${RED}錯誤: 需要安裝 Docker Compose${NC}"
            exit 1
        fi
        
        # 檢查環境變數
        if [ ! -f ".env" ]; then
            echo -e "${YELLOW}警告: .env 檔案不存在，複製範例檔案${NC}"
            cp .env.example .env
            echo -e "${YELLOW}請編輯 .env 檔案並填入您的 API keys${NC}"
            read -p "按 Enter 繼續..."
        fi
        
        # 構建和啟動
        echo "構建 Docker 映像..."
        docker-compose build
        
        echo "啟動服務..."
        docker-compose up -d
        
        echo -e "\n${GREEN}=========================================="
        echo "✅ Docker 服務啟動成功！"
        echo "=========================================="
        echo ""
        echo "網頁介面: http://localhost"
        echo "API 服務: http://localhost:5000"
        echo ""
        echo "查看日誌: docker-compose logs -f"
        echo "停止服務: docker-compose down"
        echo -e "==========================================${NC}"
        ;;
        
    3)
        echo -e "\n${GREEN}啟動生產模式...${NC}"
        
        # 檢查 Nginx
        if ! command -v nginx &> /dev/null; then
            echo -e "${RED}錯誤: 需要安裝 Nginx${NC}"
            echo "Ubuntu/Debian: sudo apt-get install nginx"
            echo "macOS: brew install nginx"
            exit 1
        fi
        
        # 安裝依賴
        if [ ! -d "venv" ]; then
            python3 -m venv venv
        fi
        source venv/bin/activate
        pip install -q -r requirements.txt
        
		# 啟動生產模式...

		# 啟動 Gunicorn
		echo "啟動 Gunicorn..."
		gunicorn -w 4 -k gevent --timeout 300 -b 0.0.0.0:5000 src.api.app:app --daemon

		# 配置 Nginx
		echo "配置 Nginx..."
		sudo cp nginx.conf /etc/nginx/sites-available/anr-analyzer
		sudo ln -sf /etc/nginx/sites-available/anr-analyzer /etc/nginx/sites-enabled/

		# 更新 Nginx 配置中的路徑 (用於靜態文件)
		CURRENT_DIR=$(pwd)
		sudo sed -i "s|root /usr/share/nginx/html;|root $CURRENT_DIR/web;|g" /etc/nginx/sites-available/anr-analyzer

		# 測試 Nginx 配置，確保沒有語法錯誤
		echo "測試 Nginx 配置..."
		sudo nginx -t

		# 檢查 Nginx 服務狀態，如果沒運行就啟動，否則重新載入
		echo "管理 Nginx 服務..."
		if systemctl is-active --quiet nginx; then
			echo "Nginx 正在運行，重新載入配置..."
			sudo systemctl reload nginx
		else
			echo "Nginx 未運行，啟動 Nginx 服務..."
			sudo systemctl start nginx
		fi

		echo "啟動完成。"
        
        echo -e "\n${GREEN}=========================================="
        echo "✅ 生產模式啟動成功！"
        echo "=========================================="
        echo ""
        echo "網頁介面: http://localhost"
        echo "API 服務: http://localhost:5000"
        echo ""
        echo "停止 Gunicorn: pkill gunicorn"
        echo -e "==========================================${NC}"
        ;;
        
    *)
        echo -e "${RED}無效的選項${NC}"
        exit 1
        ;;
esac

# 執行測試腳本（如果存在）
if [ -f "test_system.py" ]; then
    echo -e "\n${YELLOW}執行系統測試...${NC}"
    sleep 3
    python3 test_system.py
fi