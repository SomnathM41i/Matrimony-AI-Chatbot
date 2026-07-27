# Qdrant VPS Setup

Install Qdrant as a native binary on your Hostinger KVM 1 VPS (4GB RAM, 1 vCPU, 50GB NVMe).

## SSH into VPS

```bash
ssh root@your-vps-ip
```

## Install Qdrant

```bash
# Download latest Qdrant binary
wget https://github.com/qdrant/qdrant/releases/latest/download/qdrant-x86_64-unknown-linux-gnu.tar.gz
tar -xzf qdrant-x86_64-unknown-linux-gnu.tar.gz
sudo mv qdrant /usr/local/bin/
rm qdrant-x86_64-unknown-linux-gnu.tar.gz

# Create storage directory
mkdir -p ~/qdrant/storage
```

## Configure (Optional)

```bash
cat > ~/qdrant/config.yaml << 'EOF'
storage:
  storage_path: /root/qdrant/storage
  performance:
    max_indexing_threads: 2

service:
  host: 0.0.0.0
  grpc_port: 6334
  http_port: 6333
EOF
```

## Start Qdrant

```bash
# Test run first
qdrant --storage ~/qdrant/storage

# Then run in background
nohup qdrant --config ~/qdrant/config.yaml > ~/qdrant/qdrant.log 2>&1 &
```

## Verify

```bash
curl http://localhost:6333/healthz
# Should return: OK
```

## Configure Firewall

```bash
# Allow Qdrant port from your laptop IP only
ufw allow from your-laptop-ip to any port 6333 proto tcp
```

## Update .env

On your laptop, set `QDRANT_HOST` in `backend/.env`:

```
QDRANT_HOST=your-vps-ip
QDRANT_PORT=6333
```

## Run Re-index

From your laptop:

```bash
cd backend
python reindex_profiles.py
```

## Auto-reindex on start

The app automatically re-indexes if the Qdrant collection is empty on startup. Legacy `CHAT_ENGINE` flag has been removed — hybrid RAG is now the only engine.

## Resource Usage on KVM 1 (4GB RAM)

| Component | RAM (approx) |
|-----------|-------------|
| Qdrant | ~300 MB |
| bge-m3 model (FP16) | ~2 GB |
| FastAPI + Python | ~500 MB |
| OS overhead | ~500 MB |
| **Total** | **~3.3 GB** |
