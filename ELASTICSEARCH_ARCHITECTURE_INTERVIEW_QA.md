# Elasticsearch Interview Q&A (Beginner → Expert)

A simple, practical guide focused on **Elasticsearch architecture**.

- Style: easy words, short answers
- Flow: beginner to expert
- Goal: help you explain concepts clearly in interviews

---

## How to Use This File

1. Start from Beginner and move level by level.
2. For each answer, first explain in simple words, then add one real-world example.
3. If interviewer asks deeper, move to the "Deep follow-up" points.

---

## Level 1 — Beginner (Foundations)

### 1) What is Elasticsearch?
**Answer:**
Elasticsearch is a distributed search and analytics engine. It stores data as JSON documents and helps you do fast text search, filtering, and aggregations.

**Real-world use:** product search, log search, security events, analytics dashboards.

---

### 2) Is Elasticsearch a database?
**Answer:**
It can store data, but usually it is used as a **search engine**, not the main source of truth.

- Source of truth: PostgreSQL/MySQL/MongoDB
- Search layer: Elasticsearch

---

### 3) What is an index?
**Answer:**
An index is like a table in SQL. It groups similar documents.

Example: `products`, `orders`, `logs-2026.03.14`

---

### 4) What is a document?
**Answer:**
A document is one JSON record inside an index.

Example:
```json
{
  "id": 10,
  "name": "Wireless Mouse",
  "price": 29.99
}
```

---

### 5) What is a field?
**Answer:**
A field is one property in a document, like `name`, `price`, or `created_at`.

---

### 6) What is a node?
**Answer:**
A node is one Elasticsearch server instance.

A cluster can have one or many nodes.

---

### 7) What is a cluster?
**Answer:**
A cluster is a group of nodes working together and sharing the same data.

---

### 8) What is a shard?
**Answer:**
A shard is a piece of an index. Elasticsearch splits an index into shards so data can be distributed across nodes.

---

### 9) What is a replica shard?
**Answer:**
A replica is a copy of a primary shard.

Why replicas matter:
- High availability (data survives node failure)
- Better read performance (search can run on replicas)

---

### 10) What is near real-time search?
**Answer:**
Elasticsearch is not instantly searchable at write time. It usually becomes searchable after a refresh (default around 1 second).

---

## Level 2 — Intermediate (Architecture Basics)

### 11) Explain primary vs replica shards in one line.
**Answer:**
Primary shard accepts writes first; replica shard stores a copy for safety and read scale.

---

### 12) How does Elasticsearch decide which shard gets a document?
**Answer:**
It hashes the routing value (default: document `_id`) and maps it to a shard.

Formula idea:
`shard = hash(routing) % number_of_primary_shards`

---

### 13) What happens when you index a document? (write flow)
**Answer:**
1. Client sends request to any node (coordinating node).
2. Request is routed to the correct primary shard.
3. Primary writes data and forwards to replicas.
4. After refresh, document becomes searchable.

---

### 14) What is the role of the coordinating node?
**Answer:**
It receives client requests, sends them to relevant shards, collects shard results, merges them, and returns final response.

---

### 15) What is mapping?
**Answer:**
Mapping defines field types and how fields are indexed.

Examples:
- `text` for full-text search
- `keyword` for exact match, sorting, aggregations
- `date`, `integer`, `float`, `boolean`

---

### 16) Difference between `text` and `keyword`?
**Answer:**
- `text`: analyzed/tokenized, good for search
- `keyword`: exact value, good for filters/sort/aggs

Common pattern: use both with multi-fields.

---

### 17) What is an analyzer?
**Answer:**
Analyzer processes text at index/search time.

It usually includes:
- tokenizer (split text)
- token filters (lowercase, stemming, stopwords)

---

### 18) Why is Elasticsearch fast for full-text search?
**Answer:**
Because it uses an **inverted index** (word → list of document IDs), so it does quick lookups instead of scanning every row.

---

### 19) What is refresh vs flush?
**Answer:**
- **Refresh:** makes recent writes searchable
- **Flush:** commits data/translog to durable storage

---

### 20) What is translog?
**Answer:**
Transaction log for durability. It helps recover operations if node crashes before full segment commit.

---

## Level 3 — Advanced (Deep Architecture + Scale)

### 21) What is cluster state?
**Answer:**
Cluster state is metadata about indices, mappings, shards, and node assignments.

Master node manages it and publishes updates to all nodes.

---

### 22) Why can too many shards be bad?
**Answer:**
Each shard has memory and CPU overhead. Too many shards cause:
- high heap usage
- slower cluster state updates
- slower queries and recovery

Rule: avoid tiny shards in large numbers.

---

### 23) How do you choose number of shards?
**Answer:**
Based on data size, growth, and query pattern.

Practical target: shard sizes often in tens of GB (for many workloads).

---

### 24) What happens when one node fails?
**Answer:**
If replicas exist, cluster promotes replica to primary and continues serving.

If no replica exists for a shard, data for that shard becomes unavailable until recovery.

---

### 25) What is split-brain and how is it prevented?
**Answer:**
Split-brain means multiple masters due to network partition.

Modern Elasticsearch uses quorum-based cluster coordination and voting to avoid this.

Best practice: 3 dedicated master-eligible nodes.

---

### 26) Explain query phase and fetch phase.
**Answer:**
- **Query phase:** each shard finds matching docs and scores top candidates.
- **Fetch phase:** coordinating node asks shards for full document data of top hits.

---

### 27) What is relevance score (`_score`)?
**Answer:**
It shows how well a document matches a query.

By default Elasticsearch uses BM25 scoring.

---

### 28) Difference between query context and filter context?
**Answer:**
- Query context: computes score
- Filter context: no score, faster, cache-friendly

Use filters for exact constraints like status/category/date range.

---

### 29) What is `bool` query and why important?
**Answer:**
`bool` combines clauses:
- `must`
- `should`
- `filter`
- `must_not`

It is the main building block for real-world search logic.

---

### 30) How do you do zero-downtime reindex?
**Answer:**
Use index aliases.

Flow:
1. Create new index (`products_v2`) with new mapping.
2. Reindex from old index (`products_v1`).
3. Switch alias `products_current` from v1 to v2 atomically.
4. Roll back alias if needed.

---

### 31) Why not use deep pagination with large `from`?
**Answer:**
Large `from + size` is expensive because shards must sort and skip many docs.

Use `search_after` (and PIT) for deep pagination.

---

### 32) What is ILM (Index Lifecycle Management)?
**Answer:**
ILM automates index lifecycle:
- Hot (frequent writes/reads)
- Warm (less active)
- Cold (rarely queried)
- Delete (retention end)

Useful for logs/time-series data.

---

## Level 4 — Expert (System Design + Trade-offs)

### 33) Design architecture for e-commerce search.
**Answer (short design):**
- PostgreSQL = source of truth
- Kafka/CDC or app events = change stream
- Indexer service = transform + bulk index to Elasticsearch
- Elasticsearch = search API backend
- Redis/cache = hot query cache (optional)
- Kibana/metrics = observability

Key point: **eventual consistency** between DB and Elasticsearch.

---

### 34) How do you handle eventual consistency in user-facing APIs?
**Answer:**
- Write to DB first (authoritative)
- Async sync to Elasticsearch
- Show user-friendly messages for short delay
- Add retry + dead-letter queue for failed index events
- Use fallback query path for critical reads

---

### 35) How do you tune indexing throughput?
**Answer:**
- Use Bulk API
- Increase batch size carefully
- Temporarily reduce refresh frequency
- Disable replicas during one-time backfill (then restore)
- Use proper hardware and monitor merge pressure

---

### 36) How do you tune search latency?
**Answer:**
- Use filters where possible
- Keep mapping clean (avoid unnecessary analyzed fields)
- Avoid too many shards
- Use doc values for sort/aggs fields
- Profile slow queries and simplify query DSL

---

### 37) How do you handle mapping evolution safely?
**Answer:**
Field type changes are not in-place safe.

Production-safe way:
1. Create new index with new mapping
2. Reindex data
3. Switch alias
4. Delete old index later

---

### 38) Nested vs denormalized vs parent-child — when to choose?
**Answer:**
- **Denormalized:** simplest, fastest reads, more storage
- **Nested:** good when object-level relation in arrays matters
- **Parent-child:** useful when child updates are very frequent and huge in number

Use the simplest model that meets query needs.

---

### 39) How do you design high availability across zones?
**Answer:**
- Minimum 3 master-eligible nodes (quorum)
- Data nodes across zones
- Shard allocation awareness by zone
- Replicas placed in different zones
- Snapshot strategy for disaster recovery

---

### 40) What is your production checklist for Elasticsearch architecture?
**Answer:**
1. Security enabled (TLS, auth, least privilege)
2. Shard strategy documented
3. ILM policy defined
4. Snapshot/restore tested
5. Alerting for disk, heap, CPU, unassigned shards
6. Query and indexing SLOs defined
7. Reindex + rollback playbook ready

---

## Common Interview Follow-ups (Quick Answers)

### Q: Why not only PostgreSQL full-text?
Because Elasticsearch gives better relevance ranking, typo tolerance, analyzers, aggregations at scale, and search-specific capabilities.

### Q: Why not only Elasticsearch, no SQL DB?
Because many apps need strong transactions and relational integrity in a primary DB.

### Q: Biggest production mistake?
Treating Elasticsearch like a normal SQL DB and ignoring shard sizing, mapping planning, and operational monitoring.

---

## 1-Minute Architecture Pitch (Memorize)

"In production, we keep PostgreSQL as source of truth and Elasticsearch as search engine. Data changes are synced to Elasticsearch asynchronously through events or indexing jobs. Elasticsearch index is sharded for scale and replicated for high availability. Queries are distributed to shards and merged by coordinating nodes. We use aliases for zero-downtime reindex, ILM for lifecycle control, and monitoring for latency, heap, and shard health."

---

## Practice Plan (7 Days)

- **Day 1-2:** Level 1 + 2 answers (speak in simple words)
- **Day 3-4:** Level 3 internals (write/read flow, shard strategy)
- **Day 5:** Level 4 system design answers
- **Day 6:** Mock interview (architecture whiteboard)
- **Day 7:** Revise weak areas and explain trade-offs clearly

---

If you want, I can also generate a **"Top 25 most-asked Elasticsearch architecture questions"** short version (one-page cheat sheet).