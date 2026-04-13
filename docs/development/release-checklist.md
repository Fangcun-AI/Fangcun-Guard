# Release Checklist

Run through this list before every public release to prevent leaking internal details, insecure defaults, or broken first-run paths.

## 1. Secrets & Credentials

- [ ] `grep -rn 'admin123456\|your_password\|CHANGE-THIS' .` — no hardcoded credentials
- [ ] `grep -rn 'sk-xxai-\|sk-admin-' --include='*.py' --include='*.sql' .` — no real API keys
- [ ] `.env.example` files use `change-me` as the only placeholder for secrets
- [ ] `init_postgres.sql` does **not** insert any admin user or password

## 2. Internal Paths & Hostnames

- [ ] `grep -rn 'deploy_test\|/Users/' .` — no developer machine paths
- [ ] `grep -rn 'yourdomain\|your-host-ip\|YOUR_GPU_SERVER' .` — only in `.env.example` and docs
- [ ] No `localhost` URLs in runtime API responses (search `gateway_url`, `base_url` in Python files)

## 3. Placeholder & Config Consistency

- [ ] All `.env.example` files use the same placeholder style (`change-me`, `http://<host>:<port>/v1`)
- [ ] Required vs optional config is clearly marked in `.env.example`
- [ ] `config.py` startup validation rejects missing required fields (test with empty `.env`)

## 4. Documentation

- [ ] `README.md` and `README_zh.md` doc links point to correct paths under `docs/`
- [ ] Quick Start steps work from a clean clone (test in a fresh directory)
- [ ] No internal team references, meeting notes, or TODO comments in user-facing docs

## 5. Build & Deploy

- [ ] `docker compose config` succeeds with a properly filled `.env`
- [ ] `docker compose down -v && docker compose up -d` starts all services
- [ ] `docker ps` shows all containers healthy
- [ ] `curl http://localhost:3000/platform/` returns the frontend
- [ ] `curl http://localhost:5000/health` returns healthy
- [ ] `curl http://localhost:5001/health` returns healthy
- [ ] `curl http://localhost:5002/health` returns healthy

## 6. Mixed Language

- [ ] `grep -rn '#.*[\u4e00-\u9fff]' backend/ --include='*.py'` — no Chinese in code comments (data strings are OK)
- [ ] Each documentation file uses one primary language consistently

## 7. Feature Flags

- [ ] Startup logs print: `SMTP: disabled`, `Billing: disabled` when not configured
- [ ] SMTP, billing, and payment features are inert when credentials are empty
- [ ] Guard Model Router is disabled by default (requires `GUARD_MODELS_CONFIG_PATH`)
