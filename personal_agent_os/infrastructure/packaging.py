from __future__ import annotations

PACKAGE_INCLUDE = [
    "personal_agent_os/**",
    "apps/desktop_frontend/dist/**",
    "config.example.*",
]

PACKAGE_EXCLUDE = [
    "runtime/**",
    "models/**",
    "GPT-SoVITS/**",
    "frontend/node_modules/**",
    "logs/**",
    "TEMP/**",
    "**/__pycache__/**",
    "resona_desktop_pet/ui/**",
]

LEGACY_DEPENDENCY_ALLOWLIST = [
    "resona_desktop_pet/backend/llm_backend.py",
    "resona_desktop_pet/backend/mcp_manager.py",
    "resona_desktop_pet/backend/tts_backend.py",
    "resona_desktop_pet/backend/stt_backend.py",
    "resona_desktop_pet/utils/logger.py",
    "memory/**",
    "mcpserver/**",
]
