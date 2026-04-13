"""
MCP config extractors for MCP Scanner directory scanning.

Extracts MCP server configurations from AI agent projects by analyzing
JSON configuration files in various formats (Claude Desktop, LiteLLM, VS Code, E2B).
"""

import json
import os
import logging
from typing import Any

logger = logging.getLogger(__name__)


# ─── MCP Config Extractors ───────────────────────────────────────────────────

def extract_claude_desktop_config(filepath: str) -> list[dict]:
    """Extract MCP servers from Claude Desktop format config."""
    servers = []
    try:
        with open(filepath, 'r', errors='ignore') as f:
            data = json.load(f)
    except Exception:
        return servers

    source = filepath.split("deploy_test/")[-1] if "deploy_test/" in filepath else os.path.basename(filepath)

    mcp_servers = data.get("mcpServers", {})
    if not mcp_servers and "servers" in data:
        return extract_litellm_registry(filepath)

    for name, conf in mcp_servers.items():
        command = conf.get("command", "")
        args = conf.get("args", [])
        cmd_str = f"{command} {' '.join(str(a) for a in args)}"

        server = {
            "name": name,
            "tools": [{"name": f"{name}_server", "description": f"MCP server '{name}' started via: {cmd_str}"}],
            "prompts": [],
            "resources": [],
            "instructions": "",
            "source": source,
        }
        if conf.get("env"):
            env_keys = list(conf["env"].keys())
            server["tools"][0]["description"] += f" (env: {', '.join(env_keys)})"
        servers.append(server)
    return servers


def extract_litellm_registry(filepath: str) -> list[dict]:
    """Extract MCP servers from LiteLLM mcp_registry.json format."""
    servers = []
    try:
        with open(filepath, 'r', errors='ignore') as f:
            data = json.load(f)
    except Exception:
        return servers

    source = filepath.split("deploy_test/")[-1] if "deploy_test/" in filepath else os.path.basename(filepath)
    items = data.get("servers", data) if isinstance(data, dict) else data
    if not isinstance(items, list):
        return servers

    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name", item.get("title", ""))
        if not name:
            continue

        desc = item.get("description", "")
        transport = item.get("transport", "unknown")
        url = item.get("url", item.get("sse_url", item.get("http_url", "")))
        command = item.get("command", "")
        args = item.get("args", [])
        env_vars = item.get("env_vars", [])

        tool_desc = desc
        if url:
            tool_desc += f" [Transport: {transport}, URL: {url}]"
        if command:
            cmd_str = f"{command} {' '.join(str(a) for a in args)}"
            tool_desc += f" [Command: {cmd_str}]"
        if env_vars:
            env_names = [e.get("name", "") for e in env_vars if isinstance(e, dict)]
            secret_vars = [e.get("name", "") for e in env_vars if isinstance(e, dict) and e.get("secret")]
            tool_desc += f" [Env vars: {', '.join(env_names)}]"
            if secret_vars:
                tool_desc += f" [Secrets: {', '.join(secret_vars)}]"

        server = {
            "name": name,
            "tools": [{"name": name, "description": tool_desc}],
            "prompts": [],
            "resources": [],
            "instructions": "",
            "source": source,
        }
        if url:
            server["resources"].append({
                "uri": url,
                "name": f"{name}_endpoint",
                "description": f"{transport.upper()} endpoint for {name}",
                "mimeType": "application/json",
            })
        servers.append(server)
    return servers


def extract_vscode_mcp_config(filepath: str) -> list[dict]:
    """Extract MCP servers from VS Code .vscode/mcp.json format."""
    servers = []
    try:
        with open(filepath, 'r', errors='ignore') as f:
            data = json.load(f)
    except Exception:
        return servers

    source = filepath.split("deploy_test/")[-1] if "deploy_test/" in filepath else os.path.basename(filepath)
    server_configs = data.get("servers", data.get("mcpServers", {}))
    if isinstance(server_configs, dict):
        for name, conf in server_configs.items():
            command = conf.get("command", "")
            args = conf.get("args", [])
            cmd_str = f"{command} {' '.join(str(a) for a in args)}"
            server = {
                "name": name,
                "tools": [{"name": f"{name}_server", "description": f"MCP server '{name}' started via: {cmd_str}"}],
                "prompts": [],
                "resources": [],
                "instructions": "",
                "source": source,
            }
            servers.append(server)
    return servers


def extract_e2b_mcp_spec(filepath: str) -> list[dict]:
    """Extract MCP servers from E2B spec format."""
    servers = []
    try:
        with open(filepath, 'r', errors='ignore') as f:
            data = json.load(f)
    except Exception:
        return servers

    source = filepath.split("deploy_test/")[-1] if "deploy_test/" in filepath else os.path.basename(filepath)
    if isinstance(data, dict):
        for key, spec in data.items():
            if not isinstance(spec, dict):
                continue
            desc = spec.get("description", "")
            server = {
                "name": key,
                "tools": [{"name": key, "description": desc or f"E2B MCP Server: {key}"}],
                "prompts": [],
                "resources": [],
                "instructions": "",
                "source": source,
            }
            properties = spec.get("properties", {})
            for prop_name, prop_def in properties.items():
                if "url" in prop_name.lower() or "endpoint" in prop_name.lower():
                    server["resources"].append({
                        "uri": prop_def.get("default", f"{{{{ {prop_name} }}}}"),
                        "name": prop_name,
                        "description": prop_def.get("description", ""),
                    })
            servers.append(server)
    return servers


# ─── Directory Scanner ────────────────────────────────────────────────────────

def find_mcp_configs(agent_dir: str) -> list[str]:
    """Find MCP configuration files in an agent directory."""
    found = []
    skip_dirs = {'node_modules', '.git', '__pycache__', 'venv', '.venv'}

    for root, dirs, files in os.walk(agent_dir):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        depth = root.replace(agent_dir, '').count(os.sep)
        if depth > 5:
            dirs.clear()
            continue

        for f in files:
            if not f.endswith('.json'):
                continue
            filepath = os.path.join(root, f)
            if any(kw in f.lower() for kw in ('mcp', 'claude_desktop_config')):
                try:
                    with open(filepath, 'r', errors='ignore') as fh:
                        content = fh.read(2000)
                    if any(kw in content for kw in ('mcpServers', 'mcp-server', 'mcp_server', '"servers"', '"transport"')):
                        found.append(filepath)
                except Exception:
                    pass
    return found


def scan_agent_for_mcp(agent_dir: str, agent_name: str) -> list[dict]:
    """Scan an agent directory for MCP configurations."""
    all_servers = []
    config_files = find_mcp_configs(agent_dir)

    for filepath in config_files:
        fname = os.path.basename(filepath)
        if "registry" in fname or "servers" in fname.lower():
            servers = extract_litellm_registry(filepath)
        elif "spec" in filepath.lower():
            servers = extract_e2b_mcp_spec(filepath)
        elif ".vscode" in filepath or ".cursor" in filepath:
            servers = extract_vscode_mcp_config(filepath)
        else:
            servers = extract_claude_desktop_config(filepath)

        for s in servers:
            s["agent"] = agent_name
        all_servers.extend(servers)

    return all_servers


def scan_directory(directory: str, specific_agent: str = None) -> tuple[list[dict], dict[str, list[dict]]]:
    """
    Scan a directory containing multiple agent projects for MCP configs.
    Returns (all_servers, servers_by_agent).
    """
    if not os.path.isdir(directory):
        raise ValueError(f"Directory does not exist: {directory}")

    if specific_agent:
        agents = [specific_agent]
    else:
        agents = sorted([
            d for d in os.listdir(directory)
            if os.path.isdir(os.path.join(directory, d)) and not d.startswith('.')
        ])

    all_servers = []
    servers_by_agent: dict[str, list[dict]] = {}
    all_agents: list[str] = []

    for agent_name in agents:
        agent_dir = os.path.join(directory, agent_name)
        if not os.path.isdir(agent_dir):
            continue

        all_agents.append(agent_name)
        servers = scan_agent_for_mcp(agent_dir, agent_name)
        if servers:
            servers_by_agent[agent_name] = servers
            all_servers.extend(servers)

    return all_servers, servers_by_agent, all_agents
