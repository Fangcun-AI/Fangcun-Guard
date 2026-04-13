# Fangcun Guard CLI

CLI tool for deploying and managing [Fangcun Guard](https://github.com/Fangcun-AI/Fangcun-Guard) — an open-source AI guardrails platform.

## Installation

```bash
pip install fangcunguard
```

## Usage

```bash
# Initialize a new deployment
fangcunguard init

# Start services
fangcunguard up

# Check status
fangcunguard status

# View logs
fangcunguard logs -f

# Stop services
fangcunguard down
```

## Requirements

- Python >= 3.9
- Docker and Docker Compose

## License

Apache License 2.0
