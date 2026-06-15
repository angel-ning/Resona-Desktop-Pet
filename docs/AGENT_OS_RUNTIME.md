# Resona Agent OS Runtime

This document tracks the migration from desktop-pet MVP to Personal Agent OS.

## Runtime Boundary

`resona_desktop_pet/agent_os` is the new compatibility runtime. It does not
replace the existing PySide6 controller yet; it wraps it with stable Agent OS
contracts:

- `AgentRequest`: normalized user/client input.
- `AgentIntent`: structured intent and selected skill.
- `ToolInvocation`: deterministic tool execution request.
- `ToolResult`: executed, blocked, confirmation-required, or error result.
- `AgentEvent`: streamable runtime state for thin clients.
- `AgentResponse`: future runtime response envelope.

## Current Migration Slice

- Existing packs are projected through `LegacyPackAdapter` into persona, skills,
  tool policy, triggers, assets, and config overrides.
- Existing `SkillRouter` v1 remains the default router.
- Existing `MCPManager` remains the active tool backend.
- `ToolExecutionService` is now the final runtime gate for LLM-originated MCP
  calls during the compatibility period.
- `ApplicationController` sends desktop, web, and idle text requests through
  `AgentRuntime` while preserving current `LLMResponse` behavior.

## Execution Policy

Persona and prompts do not decide tool execution. Skill Router controls visible
tools, but runtime policy is the final authority before execution.

Payment-sensitive tools require confirmation. Dangerous tools such as shell,
file writes, and process-kill actions are blocked unless a future explicit
policy grants them.

## Provider Priority

1. MCP: active today.
2. Playwright: deterministic H5/browser scripts.
3. Browser-Use: semantic browser navigation.
4. OpenClaw: desktop computer-use fallback.

SwiftUI/iOS and future React clients should consume the Runtime Gateway event
stream instead of owning business logic.
