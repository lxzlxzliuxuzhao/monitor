#!/bin/bash

# 项目启动脚本：转发 Prometheus + 启动 FastAPI

# 设置命名空间和服务名（可根据实际调整）
NAMESPACE="monitoring"
PROM_SERVICE="prometheus-kube-prometheus-prometheus"
LOCAL_PORT=19090
REMOTE_PORT=9090

# 1. 检查是否已经存在端口转发
echo "🔌 Checking existing Prometheus port-forward..."
EXISTING_PID=$(lsof -ti tcp:$LOCAL_PORT)
if [ -n "$EXISTING_PID" ]; then
    echo "⚠️  Port $LOCAL_PORT is already in use (PID $EXISTING_PID), skipping port-forward."
else
    echo "🔁 Starting port-forward from $PROM_SERVICE ($REMOTE_PORT → $LOCAL_PORT)..."
    kubectl port-forward -n $NAMESPACE svc/$PROM_SERVICE $LOCAL_PORT:$REMOTE_PORT > /dev/null 2>&1 &
    sleep 2  # 给 Prometheus 转发一点启动时间
fi

# 2. 启动 FastAPI 服务
echo "🚀 Starting FastAPI server at http://localhost:8000 ..."
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
