from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class Decision:
    allow: bool
    requires_approval: bool
    reason: str
    risk: str


class PolicyEngine:
    def __init__(self, auto_approve: bool = False):
        self.auto_approve = auto_approve

    def decide(self, tool_name: str, args: Dict[str, Any], tool_risk: str) -> Decision:
        if tool_name == "write_text":
            path = str(args.get("path", "")).lower()
            if "requirements" in path:
                return Decision(
                    allow=True,
                    requires_approval=True,
                    reason="Editing dependencies always requires approval.",
                    risk="high",
                )

        _ = (tool_name, args)
        if tool_risk == "high":
            return Decision(
                allow=True,
                requires_approval=not self.auto_approve,
                reason="High-impact tool invocation requires explicit approval.",
                risk="high",
            )
        if tool_risk == "medium":
            return Decision(
                allow=True,
                requires_approval=False,
                reason="Medium-impact tool allowed with full audit.",
                risk="medium",
            )
        return Decision(
            allow=True,
            requires_approval=False,
            reason="Low-risk tool allowed.",
            risk="low",
        )
