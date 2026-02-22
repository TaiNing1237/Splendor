#!/usr/bin/env bash
# 一鍵啟動 Splendor 後端
# 使用方式：bash start.sh

cd "$(dirname "$0")"

echo "=== 璀璨寶石 Splendor 後端 ==="

# 安裝依賴（若未安裝）
if ! python -c "import fastapi" &>/dev/null; then
  echo ">> 安裝依賴套件..."
  pip install -r requirements.txt
fi

echo ">> 啟動伺服器於 http://localhost:8000"
echo ">> 前端請直接開啟 frontend/index.html 或訪問 http://localhost:8000"
echo ">> 按 Ctrl+C 停止"

python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
