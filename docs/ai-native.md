# AI-Native Operation

CARINA is AI-native rather than AI-adjacent: agents are the **fifth persona**, governed exactly like the four human ones, and the platform ships three AI agents as products — not demos. This document covers grounding, agent governance, the three agents, and self-driving platform operations.

---

## 1. Grounding: the Semantic Layer Is the Only AI Path to Data

**Raw text-to-SQL is banned as a hard architectural constraint** — including as an "expert mode." Direct schema-to-SQL generation plateaus far below decision-grade accuracy on real enterprise schemas, and its failure mode is the worst possible one: a confident, plausible, wrong answer.

Instead:

- The **Analyst agent** resolves natural-language questions against **Cube's governed metrics** (MetricFlow YAML definitions), enriched by **OpenMetadata's MCP server** (lineage, freshness, known issues, glossary).
- Semantic-model **stubs are compiled from data contracts**, so every product is minimally conversable the moment it ships.
- Questions the semantic model cannot answer get an **honest refusal** — which is product input, not failure. The **Steward flywheel** converts query-miss telemetry into proposed MetricFlow model extensions as reviewed PRs, so semantic coverage — the system's real bottleneck — improves itself weekly.
- Every AI answer renders the **"why you can trust this" panel**: source contracts, quality status, freshness, applied policy decisions, and a lineage link.

## 2. Agent Governance: the Fifth Persona

Agents get no special path — and no degraded one:

| Concern | Mechanism (identical to humans) |
|---|---|
| Identity | Keycloak OAuth (client-ID metadata documents, incremental scopes); each agent has its own service identity |
| Authorization | OpenFGA relationships + OPA masks — the same generated Rego that governs analysts |
| Discovery | Tools discoverable **only** through the private MCP registry, with per-tool approval tiers (reads flow freely; mutations require human-in-the-loop) |
| Data access | Only through Cube and OpenMetadata MCP servers — never raw storage, never raw schemas |
| Audit | Every tool call is an OpenLLMetry trace in the evidence plane (AI-Act Article 12) |
| Blast radius | Agent workloads run in vCluster sandboxes; platform mutations only via Git PRs |

**MCP everywhere** is the tool plane: every platform service (catalog, semantic layer, orchestrator, cost, observability) exposes an MCP server, published to the private registry. The registry is the governance point: what an agent *can discover* is the first policy decision, before what it can call.

## 3. The Three Shipped Agents

### The Analyst
Conversational data exploration for business users and analysts, grounded as above. Answers are pinnable to Rill/Evidence. Powers the proactive **Monday-morning brief** — *"the platform already prepared your analysis"*: per-user, per-role digests of metric movements, root causes via lineage, watch items, and anomalies already handled (with the fix PR linked).

### The Engineer
Self-healing pipelines. The loop: **Elementary anomaly → OpenLineage root-cause traversal → fix proposed as a Git PR** with a passing Recce data-diff report attached. Bounded, reversible actions (retry, compaction trigger) can auto-merge under pre-approved classes; anything touching mappings, schemas, or logic waits for human review. The Engineer files the first PR before a human is paged.

### The Steward
Governance hygiene at scale: auto-documentation drafts, contract-drift detection (declared schema vs. observed), PII classification suggestions (always human-approved), retention/erasure hygiene checks, deprecated-metric migration PRs against downstream consumers, and the semantic-coverage flywheel (query misses → proposed model extensions).

## 4. Sovereign Inference

- **vLLM + llm-d + KServe** (`LLMInferenceService` CRs) serve open-weight models in-platform, scheduled by **Kueue** with **Dynamic Resource Allocation** for GPUs.
- Default weights: **Mistral 3 series** (Apache 2.0), with **Apertus / EuroLLM** for EU-language coverage.
- Frontier APIs (non-sovereign) are a **policy-gated tier**: the data classification in the contract decides whether a given interaction may leave the platform, and S1-sovereign deployments run with the tier disabled entirely.
- **MLflow 3** provides the model registry and eval harness; **Langfuse** (self-hosted) provides traces, evals, and prompt/version management; **Feast** serves features for classical ML.
- Vectors: **Lance** on the lakehouse is the system of record for embeddings; **Qdrant** serves the low-latency tier. Both are governed by the same contracts and masks — a vector row about a person is still personal data, and erasure propagates to it.

## 5. Self-Driving Platform Operations

The hard rule: **platform-operating agents act only through Git PRs** into the Argo-CD-governed repository. There is no kubectl for agents.

- **Auto-merge classes** are pre-approved for reversible, bounded actions: pipeline retry, Amoro compaction trigger, replica scale within declared quota, KEDA window adjustment within carbon/cost policy.
- Everything else — schema changes, policy changes, new infrastructure, spend beyond quota — waits for human review.
- Cost and carbon optimization run the same way: OpenCost's MCP server and Kepler feed agents that propose right-sizing and low-carbon batch windows as **quantified PRs** ("this change saves €412/month and 18 kgCO₂/week; here is the query-latency impact analysis").
- Each agent has a **noise budget** tracked as an SLO — an agent that files low-value PRs gets its thresholds retuned, the same way a flaky alert would.

This is what makes autonomous data engineering auditable enough for NIS2 and the AI Act: every agent action is a diff, every diff is reviewed (by policy or by a person), and the platform team's job becomes **reviewing the platform's own pull requests**.

## 6. What CARINA Deliberately Does Not Build

- **No house agent-orchestration framework.** LangGraph + Pydantic AI + MCP are the substrate; CARINA builds governed tools and context, not another loop. (ODAP's Multica/Nanitics experiments stay retired.)
- **No frontier-model pretraining.** CARINA fine-tunes, serves, evaluates, and governs models; it does not pretrain them.
- **No ungoverned "AI sandbox" with production data.** Experimentation happens in vClusters against synthetic twins or policy-scoped grants — the same rules as everywhere else.
