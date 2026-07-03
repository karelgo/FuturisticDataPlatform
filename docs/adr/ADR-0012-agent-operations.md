# ADR-0012: Agents as the Fifth Persona; Platform-Operating Agents Act Only via Git PRs

**Status:** Accepted · **Date:** 2026-07

## Context

ODAP's agent experiments (Multica, Nanitics) sat outside the governance flow — the honest 2024-era pattern, and exactly the wrong foundation: an ungoverned parallel access path that could never be allowed near production data or infrastructure. For agents to be genuinely useful they need real capabilities; for the platform to stay auditable (NIS2, AI Act), every agent action must be as governed as a human's — ideally more visibly so.

## Decision

- **Agents are the fifth persona.** Keycloak identities, OpenFGA relationships, OPA masks identical to humans'; data access only through the semantic layer and catalog MCP servers (ADR-0008); tool discovery only through the **private MCP registry** with per-tool approval tiers (reads flow; mutations require human-in-the-loop). No parallel access path exists, structurally.
- **Platform-operating agents act only through Git PRs** into the Argo-CD-governed repository — there is no kubectl for agents.
- **Auto-merge classes** are pre-approved for bounded, reversible actions: pipeline retry, compaction trigger, replica scale within declared quota, KEDA window adjustment within cost/carbon policy. Everything else waits for human review.
- Three agents ship as platform products — **Analyst, Engineer, Steward** — on LangGraph (+ Pydantic AI), with OpenLLMetry→Langfuse tracing into the evidence plane, and per-agent **noise budgets** tracked as SLOs.

## Alternatives rejected

- **Direct agent access to infrastructure APIs:** unauditable blast radius; one prompt-injection away from an incident.
- **Agents as read-only assistants:** forfeits the platform's largest operational win (self-healing pipelines, autonomous cost/carbon optimization) for no governance gain over the PR model.
- **A bespoke agent framework:** CARINA builds governed tools and context, not another orchestration loop.

## Consequences

- Every agent action is a diff; every diff is reviewed by policy or by a person. The platform team's job shifts to **reviewing the platform's own pull requests**.
- Auto-merge class boundaries are themselves Git-versioned policy — widening one is a human decision with an audit trail.
- Agent throughput is bounded by review capacity — accepted; noise budgets and auto-merge classes are the pressure valves, tuned like alerting.
