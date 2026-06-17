from __future__ import annotations

from typing import Iterable, List

from personal_agent_os.domain import ClientCapabilities, PermissionBlocked, ToolManifest


class CapabilityGuard:
    def check(self, manifest: ToolManifest, capabilities: ClientCapabilities) -> PermissionBlocked | None:
        missing: List[str] = []
        for capability in manifest.required_capabilities:
            if not bool(getattr(capabilities, capability, False)):
                missing.append(capability)
        if not missing:
            return None
        return PermissionBlocked(
            reason=f"Tool '{manifest.name}' requires capabilities that this client did not grant.",
            missing_capabilities=missing,
            alternative_actions=[
                "Return a read-only explanation instead.",
                "Ask the user to confirm or switch to a client with the required capability.",
            ],
            requires_user_confirmation=True,
        )

    def require(self, required: Iterable[str], capabilities: ClientCapabilities, name: str = "operation") -> PermissionBlocked | None:
        manifest = ToolManifest(name=name, required_capabilities=list(required))
        return self.check(manifest, capabilities)
