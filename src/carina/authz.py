"""The policy enforcement point (Phase 1 — KEEL, ADR-0009).

One policy, two evaluators: `carina compile` generates Rego for the OPA
sidecars in the cluster profile, and this module enforces the *same
semantics* in-process for the laptop profile. The conformance test in
tests/test_policy_conformance.py evaluates both against the same inputs —
if they ever disagree, the build fails, which is what keeps "generated
policy" from quietly becoming "two policies".

Decision semantics (mirroring compiler.compile_policy_rego):
  - default deny
  - the owning group may read and write
  - `classification: public` → any *authenticated* subject may read
  - contract-declared `access.consumers` groups may read
  - `access.masks` columns are masked for everyone but the owner

Every deny is evidence-logged (`authz.deny`) — the laptop stand-in for OPA
decision logs feeding the evidence plane (ADR-0010).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import duckdb

from . import evidence
from .contracts import Contract


@dataclass
class Actor:
    subject: str
    groups: list[str] = field(default_factory=list)
    authenticated: bool = False
    kind: str = "human"  # human | agent | service

    @classmethod
    def anonymous(cls) -> "Actor":
        return cls(subject="anonymous", authenticated=False)

    @classmethod
    def dev(cls) -> "Actor":
        """CARINA_AUTH_MODE=none — the laptop dev identity, loudly not prod."""
        return cls(subject="dev@local", groups=["platform-team@carina.local"],
                   authenticated=True, kind="human")

    def as_dict(self) -> dict:
        return {"subject": self.subject, "groups": self.groups,
                "authenticated": self.authenticated, "kind": self.kind}


@dataclass
class Decision:
    allow: bool
    reason: str
    contract_id: str
    action: str

    def as_dict(self) -> dict:
        return {"allow": self.allow, "reason": self.reason,
                "contract": self.contract_id, "action": self.action}


def opa_input(contract: Contract, actor: Actor, action: str) -> dict:
    """The exact input document the generated Rego expects — shared with the
    conformance suite so both evaluators are asked the same question."""
    return {
        "action": action,
        "resource": {"table": contract.silver_table},
        "subject": {
            "subject": actor.subject,
            "groups": actor.groups,
            "authenticated": actor.authenticated,
        },
    }


def decide(contract: Contract, actor: Actor, action: str = "read") -> Decision:
    """Evaluate one contract's access policy for an actor."""
    if contract.owner in actor.groups and action in ("read", "write"):
        return Decision(True, f"owner group {contract.owner}", contract.id, action)
    if action == "read":
        if contract.classification == "public" and actor.authenticated:
            return Decision(True, "public data, authenticated subject", contract.id, action)
        consumers = contract.raw.get("access", {}).get("consumers", [])
        granted = [g for g in consumers if g in actor.groups]
        if granted:
            return Decision(True, f"contract-declared consumer {granted[0]}", contract.id, action)
    return Decision(False, "no rule grants access (default deny)", contract.id, action)


def decide_all(
    contracts: list[Contract],
    actor: Actor,
    action: str = "read",
    con: duckdb.DuckDBPyConnection | None = None,
) -> tuple[bool, list[Decision]]:
    """All-or-nothing over the contracts behind a resource (a semantic model
    reads gold built from contracted silver: access requires every input).
    Denies are evidence-logged when a connection is given."""
    decisions = [decide(ct, actor, action) for ct in contracts]
    allowed = all(d.allow for d in decisions)
    if not allowed and con is not None:
        evidence.record(con, "authz.deny", ",".join(d.contract_id for d in decisions if not d.allow), {
            "actor": actor.as_dict(),
            "action": action,
            "decisions": [d.as_dict() for d in decisions],
        }, actor=actor.subject)
    return allowed, decisions


def masks_for(contract: Contract, actor: Actor) -> list[dict]:
    """Columns masked for this actor — everyone but the owning group."""
    if contract.owner in actor.groups:
        return []
    return [
        {"column": m["column"], "treatment": m.get("treatment", "null")}
        for m in contract.raw.get("access", {}).get("masks", [])
    ]
