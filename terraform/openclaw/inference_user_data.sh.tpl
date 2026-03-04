#!/bin/bash
set -e

# vLLM Inference Server Bootstrap
# Model: ${vllm_model}
# Instance: g5.xlarge (1x NVIDIA A10G 24GB)

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"

echo "[vllm] Starting inference server setup..."

# Install Docker
yum install -y docker
systemctl enable docker
systemctl start docker

# Add NVIDIA container toolkit repo and install
curl -fsSL https://nvidia.github.io/libnvidia-container/stable/rpm/nvidia-container-toolkit.repo \
  | tee /etc/yum.repos.d/nvidia-container-toolkit.repo
yum install -y nvidia-container-toolkit

# Configure Docker to use NVIDIA runtime
nvidia-ctk runtime configure --runtime=docker
systemctl restart docker

# Verify GPU is accessible
echo "[vllm] GPU status:"
nvidia-smi

# Create persistent model cache (survives container restarts, not instance termination)
mkdir -p /opt/vllm-cache

# Pull vLLM image
echo "[vllm] Pulling vLLM image..."
docker pull vllm/vllm-openai:nightly

# Run vLLM server
echo "[vllm] Starting vLLM with model ${vllm_model}..."
docker run -d \
  --name vllm-qwen \
  --restart unless-stopped \
  --gpus all \
  --shm-size=8g \
  -p 8000:8000 \
  -v /opt/vllm-cache:/root/.cache/huggingface \
  -e VLLM_API_KEY="${vllm_api_key}" \
  vllm/vllm-openai:nightly \
  --model "${vllm_model}" \
  --quantization awq_marlin \
  --max-model-len 32768 \
  --gpu-memory-utilization 0.90 \
  --served-model-name qwen3 \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  --trust-remote-code

echo "[vllm] Container started. Model download may take 5-10 minutes on first boot."
echo "[vllm] Monitor: docker logs vllm-qwen --follow"

# Wait for vLLM to become healthy (model download + load)
echo "[vllm] Waiting for model to load..."
for i in $(seq 1 60); do
  if curl -sf http://localhost:8000/v1/models > /dev/null 2>&1; then
    echo "[vllm] Server ready after $((i * 15)) seconds"
    break
  fi
  echo "[vllm] Waiting... ($((i * 15))s)"
  sleep 15
done

# Final health check
if curl -sf http://localhost:8000/v1/models > /dev/null 2>&1; then
  echo "[vllm] Inference server is HEALTHY"
  touch /opt/vllm-ready
else
  echo "[vllm] WARNING: Server not yet ready. Model may still be downloading."
  echo "[vllm] Check: docker logs vllm-qwen --follow"
fi
