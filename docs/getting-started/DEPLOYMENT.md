# Deployment Guide

Basic setup is covered in the [Quick Start](QUICK_START.md). This page covers model deployment and production hardening.

## Deploy a Detection Model

If you want to self-host the detection model (requires GPU with 8GB+ VRAM):

```bash
pip install vllm

vllm serve Qwen/Qwen3Guard-Gen-8B \
  --port 58002 \
  --served-model-name Qwen3Guard-Gen-8B \
  --max-model-len 8192
```

Then set in `.env`:

```bash
GUARDRAILS_MODEL_API_URL=http://<gpu-server-ip>:58002/v1
```

Or use any OpenAI-compatible API instead — OpenAI, Ollama, etc. all work.

## Production Checklist

- Change `SUPER_ADMIN_PASSWORD` to a strong password
- Set a random `JWT_SECRET_KEY` (e.g., `openssl rand -hex 32`)
- Set a strong `POSTGRES_PASSWORD`
- Configure `CORS_ORIGINS` to your domain
- Set `DEBUG=false`
- Consider tuning worker counts (`ADMIN_UVICORN_WORKERS`, `DETECTION_UVICORN_WORKERS`, `PROXY_UVICORN_WORKERS`) based on your hardware

## Troubleshooting

| Problem | Check |
|---------|-------|
| Container won't start | `fangcunguard logs platform` or `docker logs fangcunguard-platform` |
| Migration error | `fangcunguard logs platform` and look for migration errors |
| Port conflict | `lsof -i :3000` or `lsof -i :5001` |
| Model unreachable | Use `host.docker.internal` instead of `localhost` when the model runs on the host |
| Reset everything | `fangcunguard down -v && fangcunguard up` |
