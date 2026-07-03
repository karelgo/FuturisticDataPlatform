# ADR-0006: AutoMQ + RisingWave + Debezium Streaming Spine; Flink for the Heavyweight Tier

**Status:** Accepted · **Date:** 2026-07

## Context

ODAP shipped with NiFi/Kafka templates disabled — streaming never became real because classic Kafka's disk-and-replication economics made it the most expensive always-on component in a modest cluster. Since then, object-storage-native brokers (AutoMQ, WarpStream, Bufstream; Kafka's own KIP-1150 diskless work) collapsed that cost, and in-broker stream→Iceberg materialization ("Table Topics") removed the copy job between the stream and the lakehouse.

## Decision

- **Debezium 3.4+** is the CDC lingua franca for operational databases.
- **AutoMQ** (Apache 2.0, Kafka wire protocol, diskless on S3) is the broker; **Table Topics** materialize streams directly into Iceberg through Lakekeeper.
- **RisingWave** (Postgres wire protocol) is the default SQL streaming / incremental-view-maintenance tier.
- **Apache Flink 2.x** is retained for heavyweight CEP and whole-database synchronization only.
- A Confluent-compatible **schema registry enforces contract schemas broker-side at write** — contracts enforced where enforcement is cheapest.

## Alternatives rejected

- **Classic Apache Kafka / Strimzi:** decade-hardened but wrong economics for scale-to-zero; KIP-1150 is watched — if upstream diskless matures, the wire protocol makes a swap invisible to producers.
- **WarpStream:** proprietary control plane (and hyperscaler-acquired) — violates the no-proprietary-control-plane rule.
- **Flink-everywhere:** operational weight unjustified for the 80% of streaming that is SQL-shaped IVM.

## Consequences

- S3 becomes the only broker state → streaming DR collapses into object-storage DR (Tier 2).
- Streaming-born small files make Amoro compaction non-optional (ADR-0001).
- Bet risk: AutoMQ and RisingWave are younger than their incumbents. Mitigation: **the Kafka and Postgres wire protocols are the contracts** — broker/engine swaps don't touch producers or consumers.
