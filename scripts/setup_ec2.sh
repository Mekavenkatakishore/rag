#!/bin/bash
set -e

echo "=========================================================="
echo "  Setting up AWS EC2 Server for RAG Pro & HR Assistant"
echo "=========================================================="

# 1. Update system packages
echo "[1/5] Updating system packages..."
sudo apt-get update -y
sudo apt-get upgrade -y

# 2. Install Docker and Docker Compose plugin
echo "[2/5] Installing Docker and Docker Compose..."
sudo apt-get install -y docker.io docker-compose-v2 curl
sudo usermod -aG docker ubuntu

# 3. Configure 2GB Swap Memory (Prevents Out-Of-Memory during AI model loading)
if [ ! -f /swapfile ]; then
    echo "[3/5] Allocating 2GB Swap Memory for AI Embeddings..."
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
else
    echo "[3/5] Swap already configured. Skipping."
fi

# 4. Create application directories
echo "[4/5] Creating /opt/rag_pro application directory..."
sudo mkdir -p /opt/rag_pro/data/storage
sudo mkdir -p /opt/rag_pro/data/chroma_db
sudo mkdir -p /opt/rag_pro/data/uploaded_files
sudo mkdir -p /opt/rag_pro/data/logs
sudo chown -R ubuntu:ubuntu /opt/rag_pro

# 5. Write Production Docker Compose File
echo "[5/5] Writing production docker-compose.yml..."
cat << 'EOF' > /opt/rag_pro/docker-compose.yml
version: '3.8'

services:
  rag-pro:
    image: ghcr.io/mekavenkatakishore/rag:latest
    container_name: rag_pro_app
    restart: unless-stopped
    ports:
      - "80:8000"
    env_file:
      - .env
    environment:
      - USER_DATABASE_PATH=/app/data/users.db
      - HR_DATABASE_PATH=/app/data/hr_system.db
      - HF_HOME=/app/data/huggingface
    volumes:
      - ./data/storage:/app/data
      - ./data/chroma_db:/app/chroma_db
      - ./data/uploaded_files:/app/uploaded_files
      - ./data/logs:/app/logs
EOF

echo "=========================================================="
echo "  ✅ Server Setup Complete!"
echo "  Docker is installed, Swap is enabled, and /opt/rag_pro is ready."
echo "=========================================================="

