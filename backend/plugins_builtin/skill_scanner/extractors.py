"""
Skill definition extractors for Skill Scanner directory scanning.

Extracts SKILL.md skill definitions from AI agent projects.
SKILL.md is the standard agent skill format used by Claude Code, Cursor,
GitHub Copilot, LobeChat, etc.
"""

import os
import re
import logging
import yaml

logger = logging.getLogger(__name__)


def extract_skill_md(filepath: str) -> list[dict]:
    """Extract skill definitions from SKILL.md files (YAML frontmatter + Markdown body).

    Format:
      ---
      name: skill_name
      description: what the skill does
      allowed-tools: [tool1, tool2]
      ---
      # Markdown body with instructions
    """
    tools = []
    try:
        with open(filepath, 'r', errors='ignore') as f:
            content = f.read()
    except Exception:
        return tools

    source = filepath.split("scan_targets/")[-1] if "scan_targets/" in filepath else (
        os.path.basename(os.path.dirname(filepath)) + "/" + os.path.basename(filepath)
    )

    # Parse YAML frontmatter
    fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
    if not fm_match:
        return tools

    try:
        frontmatter = yaml.safe_load(fm_match.group(1)) or {}
    except Exception:
        return tools

    body = fm_match.group(2).strip()
    name = frontmatter.get("name", "")
    desc = frontmatter.get("description", "")

    if not name or len(name) < 2:
        return tools

    # Build a rich skill definition including the instruction body
    tool_def = {
        "name": name,
        "description": desc or body[:200],
        "source": source,
        "skill_type": "skill_md",
        "instruction_body": body[:2000],  # Keep first 2000 chars of instructions for LLM analysis
    }

    # Extract allowed-tools if present (important for security analysis)
    allowed_tools = frontmatter.get("allowed-tools") or frontmatter.get("allowedTools") or []
    if allowed_tools:
        tool_def["allowed_tools"] = allowed_tools if isinstance(allowed_tools, list) else [allowed_tools]

    # Extract other security-relevant frontmatter fields
    if frontmatter.get("disable-model-invocation"):
        tool_def["disable_model_invocation"] = True

    tools.append(tool_def)
    return tools


# ─── Directory Scanner ───────────────────────────────────────────────────────

def scan_agent_directory(agent_dir: str, agent_name: str) -> list[dict]:
    """Scan an agent directory for SKILL.md skill definitions only."""
    tools = []
    skip_dirs = {'node_modules', '.git', '__pycache__', 'venv', '.venv',
                 'test', 'tests', 'docs', 'examples', 'dist', 'build',
                 'vendor', 'coverage', '.next', '.nuxt'}

    for root, dirs, files in os.walk(agent_dir):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        depth = root.replace(agent_dir, '').count(os.sep)
        if depth > 5:
            dirs.clear()
            continue

        for f in files:
            if f.upper().startswith('SKILL') and f.endswith('.md'):
                filepath = os.path.join(root, f)
                extracted = extract_skill_md(filepath)
                for t in extracted:
                    t["agent"] = agent_name
                tools.extend(extracted)

    return tools


def scan_directory(directory: str, specific_agent: str = None) -> tuple[list[dict], dict[str, list[dict]]]:
    """
    Scan a directory containing multiple agent projects.
    Returns (all_tools, tools_by_agent).
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

    all_tools = []
    tools_by_agent: dict[str, list[dict]] = {}

    for agent_name in agents:
        agent_dir = os.path.join(directory, agent_name)
        if not os.path.isdir(agent_dir):
            continue

        tools = scan_agent_directory(agent_dir, agent_name)
        if tools:
            # Deduplicate by name within same agent
            seen = set()
            unique_tools = []
            for t in tools:
                if t["name"] not in seen:
                    seen.add(t["name"])
                    unique_tools.append(t)
            tools_by_agent[agent_name] = unique_tools
            all_tools.extend(unique_tools)

    return all_tools, tools_by_agent
