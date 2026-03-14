# PostgreSQL vs Elasticsearch — Learn by Doing

A hands-on Django REST project that teaches Elasticsearch concepts by running **the same queries** against both PostgreSQL and Elasticsearch, so you can see the differences in real-time.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Core Concepts: PostgreSQL vs Elasticsearch](#core-concepts)
3. [Architecture Overview](#architecture)
4. [API Endpoints Guide](#api-endpoints)
5. [Deep Dive: What Elasticsearch Does Better](#deep-dive)
6. [When to Use What](#when-to-use-what)
7. [Project Structure](#project-structure)

---

## Quick Start

```bash
# 1. Start everything (PostgreSQL + Elasticsearch + Kibana + Django)
docker compose up --build -d

# 2. Wait for services to be healthy (~30 seconds)
docker compose ps   # All should show "healthy" or "running"

# 3. Seed the database with 500 products
docker compose exec web python manage.py seed_products --count 500

# 4. Rebuild the Elasticsearch index
docker compose exec web python manage.py search_index --rebuild -f

# 5. Open the API overview
#    http://localhost:8000/api/
```

**Services:**

| Service        | URL                        | Purpose                    |
| -------------- | -------------------------- | -------------------------- |
| Django API     | http://localhost:8000/api/ | REST API                   |
| Elasticsearch  | http://localhost:9200/     | Search engine              |
| Kibana         | http://localhost:5601/     | ES visual dashboard        |
| PostgreSQL     | localhost:5432             | Relational database        |

---

## Core Concepts

### What is PostgreSQL?

PostgreSQL is a **relational database** (RDBMS). It stores data in **tables with rows and columns**, enforces schemas, supports ACID transactions, and uses **SQL** for queries. It's your **source of truth**.

### What is Elasticsearch?

Elasticsearch is a **distributed search and analytics engine** built on Apache Lucene. It stores data as **JSON documents** in **indexes**, and is designed for **full-text search, aggregations, and real-time analytics**.

### The Key Mental Model

```
┌─────────────────────────────────────────────────────────┐
│                      Your App                           │
│                                                         │
│   WRITE ──► PostgreSQL (source of truth)                │
│                │                                        │
│                │ auto-sync (django-elasticsearch-dsl)    │
│                ▼                                        │
│   READ  ──► Elasticsearch (search & analytics)          │
│                                                         │
│   PostgreSQL = WHERE your data LIVES                    │
│   Elasticsearch = HOW your data is SEARCHED             │
└─────────────────────────────────────────────────────────┘
```

### Terminology Mapping

| PostgreSQL         | Elasticsearch      | Description                            |
| ------------------ | ------------------ | -------------------------------------- |
| Database           | Cluster            | Top-level container                    |
| Table              | Index              | Collection of similar data             |
| Row                | Document           | Single data record                     |
| Column             | Field              | Single property of a record            |
| Schema             | Mapping            | Structure definition                   |
| SQL query          | Query DSL (JSON)   | How you ask for data                   |
| `SELECT`           | `_search` API      | Retrieve data                          |
| `WHERE`            | `bool` query       | Filter data                            |
| `GROUP BY`         | Aggregations       | Summarize data                         |
| `JOIN`             | Denormalization    | Combine related data                   |
| B-tree index       | Inverted index     | Speed up lookups                       |

---

## PostgreSQL Limitations for Search (and How ES Solves Them)

### 1. Full-Text Search Quality

**PostgreSQL (`ILIKE`):**
```sql
SELECT * FROM products WHERE name ILIKE '%laptop%';
```
- ❌ No relevance scoring — results aren't ranked by quality
- ❌ No stemming — "running" won't match "run"
- ❌ No synonyms — "laptop" won't match "notebook"
- ❌ No typo tolerance — "laptp" returns nothing
- ❌ Scans entire column = slow on millions of rows

**Elasticsearch:**
```json
{
  "query": {
    "multi_match": {
      "query": "laptp",
      "fields": ["name^3", "description"],
      "fuzziness": "AUTO"
    }
  }
}
```
- ✅ BM25 relevance scoring (best matches first)
- ✅ Stemming ("running" → "run" → matches "runner", "runs")
- ✅ Synonyms ("laptop" → also searches "notebook", "portable computer")
- ✅ Fuzzy matching ("laptp" still finds "laptop")
- ✅ Inverted index = near-instant regardless of data size

### 2. How Inverted Index Works (The Core of ES)

PostgreSQL uses a **B-tree index** — like a book's table of contents:
```
Row 1: "Samsung Galaxy Phone"
Row 2: "Apple iPhone Pro"
Row 3: "Samsung Galaxy Tab"

B-tree on 'name': points to row numbers in sorted order
→ To find "Galaxy": scan until you find matching rows
```

Elasticsearch uses an **inverted index** — like a book's **back-of-the-book index**:
```
"samsung"  → [doc1, doc3]
"galaxy"   → [doc1, doc3]
"phone"    → [doc1]
"apple"    → [doc2]
"iphone"   → [doc2]
"pro"      → [doc2]
"tab"      → [doc3]

Search "galaxy" → instantly returns [doc1, doc3]
```

The inverted index maps **every word** to the documents containing it. This is why ES is blazing fast for text search — it's a direct lookup, not a scan.

### 3. Analysis Pipeline (Why ES Understands Language)

When you index a document in ES, the text goes through an **analysis pipeline**:

```
"The Quick Brown Foxes jumped!" 
    │
    ▼ Tokenizer (split into words)
["The", "Quick", "Brown", "Foxes", "jumped!"]
    │
    ▼ Lowercase filter
["the", "quick", "brown", "foxes", "jumped!"]
    │
    ▼ Stop word removal
["quick", "brown", "foxes", "jumped"]
    │
    ▼ Stemming
["quick", "brown", "fox", "jump"]
    │
    ▼ Stored in inverted index
```

Now searching for "jumping fox" matches because:
- "jumping" → stems to "jump" ✓
- "fox" → matches "fox" (stemmed from "foxes") ✓

**PostgreSQL has none of this.** `ILIKE '%fox%'` will match "foxes" by substring, but it's accidental, not linguistic.

### 4. Aggregations Speed

**PostgreSQL:**
```sql
-- Need MULTIPLE queries:
SELECT category, COUNT(*) FROM products GROUP BY category;
SELECT AVG(price) FROM products;
SELECT brand, AVG(rating) FROM products GROUP BY brand;
-- Each is a separate DB round-trip
```

**Elasticsearch — ALL in ONE request:**
```json
{
  "size": 0,
  "aggs": {
    "by_category": { "terms": { "field": "category.raw" } },
    "avg_price": { "avg": { "field": "price" } },
    "brand_ratings": {
      "terms": { "field": "brand.raw" },
      "aggs": { "avg_rating": { "avg": { "field": "rating" } } }
    },
    "price_histogram": {
      "histogram": { "field": "price", "interval": 50 }
    }
  }
}
```

### 5. Scoring & Ranking

PostgreSQL returns results in **insertion order** (or whatever `ORDER BY` you specify). There's no concept of "this row matches better than that row" for text searches.

Elasticsearch uses **BM25 scoring**:
- Term frequency: How often the word appears in the document
- Inverse document frequency: Rare words score higher (searching "quantum" is more specific than "the")
- Field length: Matching in a short field (name) scores higher than in a long field (description)
- You can **boost** certain fields: `name^3` means name matches are 3× more important

### 6. JOINs vs Denormalization

**PostgreSQL** normalizes data and uses JOINs:
```sql
SELECT p.name, c.name, b.name
FROM products p
JOIN categories c ON p.category_id = c.id
JOIN brands b ON p.brand_id = b.id
WHERE p.name ILIKE '%wireless%';
-- JOINs can be expensive at scale
```

**Elasticsearch** denormalizes — stores everything in one document:
```json
{
  "name": "Wireless Headphones Pro",
  "category": { "name": "Audio", "slug": "audio" },
  "brand": { "name": "Sony", "country": "Japan" },
  "tags": [{"name": "wireless"}, {"name": "bluetooth"}]
}
```
No JOINs needed. Every document contains all the data needed to display it. The trade-off is **storage space** and **keeping data in sync**.

---

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Client     │────▶│   Django     │────▶│  PostgreSQL  │
│  (Browser/   │     │   REST API   │     │  (storage)   │
│   Postman)   │     │              │     └──────────────┘
└──────────────┘     │  /api/pg/*   │            │
                     │  /api/es/*   │     auto-sync via
                     │              │     django-elasticsearch-dsl
                     │              │            │
                     │              │────▶┌──────────────┐
                     └──────────────┘     │Elasticsearch │
                                          │  (search)    │
                           ┌──────────────┤              │
                           │              └──────────────┘
                     ┌──────────────┐
                     │   Kibana     │
                     │  (ES UI)     │
                     └──────────────┘
```

**Data flow:**
1. Products are created/updated in **PostgreSQL** (Django ORM)
2. `django-elasticsearch-dsl` **automatically syncs** changes to ES index
3. **`/api/pg/*`** endpoints query PostgreSQL directly
4. **`/api/es/*`** endpoints query Elasticsearch directly
5. Compare the results side-by-side!

---

## API Endpoints

### Overview
```
GET http://localhost:8000/api/
```

### 1. Full-Text Search
```bash
# PostgreSQL — simple ILIKE (no ranking, no fuzzy)
curl "http://localhost:8000/api/pg/search/?q=laptop"

# Elasticsearch — multi_match with scoring + fuzzy
curl "http://localhost:8000/api/es/search/?q=laptop"

# Try a TYPO — only ES handles this:
curl "http://localhost:8000/api/es/search/?q=laptp"

# Try a SYNONYM — only ES handles this:
curl "http://localhost:8000/api/es/search/?q=notebook"
```

### 2. Autocomplete
```bash
# PostgreSQL — prefix match only
curl "http://localhost:8000/api/pg/autocomplete/?q=sam"

# Elasticsearch — edge_ngram (matches any word)
curl "http://localhost:8000/api/es/autocomplete/?q=pro"
```

### 3. Aggregations / Facets
```bash
# PostgreSQL — multiple GROUP BY queries
curl "http://localhost:8000/api/pg/aggregations/"

# Elasticsearch — ALL aggregations in one query
curl "http://localhost:8000/api/es/aggregations/"

# With search filter
curl "http://localhost:8000/api/es/aggregations/?q=wireless"
```

### 4. Filtered Search
```bash
# PostgreSQL
curl "http://localhost:8000/api/pg/filter/?q=wireless&category=Electronics&min_price=10&max_price=100&min_rating=4"

# Elasticsearch
curl "http://localhost:8000/api/es/filter/?q=wireless&category=Electronics&min_price=10&max_price=100&min_rating=4"
```

### 5. Sorting
```bash
# PostgreSQL — can sort by field, but NOT by relevance
curl "http://localhost:8000/api/pg/sort/?q=phone&sort=price_asc"

# Elasticsearch — sort by relevance, or custom scoring
curl "http://localhost:8000/api/es/sort/?q=phone&sort=relevance"
curl "http://localhost:8000/api/es/sort/?q=phone&sort=best"
```

### 6. Geo Search (ES only)
```bash
# Find products from warehouses near New York City
curl "http://localhost:8000/api/es/geo/?lat=40.7128&lon=-74.0060&distance=100km"

# Near San Francisco
curl "http://localhost:8000/api/es/geo/?lat=37.7749&lon=-122.4194&distance=50km"
```

---

## Deep Dive: Key Elasticsearch Concepts in This Project

### Document Mapping (see `products/documents.py`)

```python
# A single field can have MULTIPLE sub-fields with different analyzers:
name = fields.TextField(
    analyzer="default_analyzer",          # Full-text (stemmed)
    fields={
        "raw": fields.KeywordField(),     # Exact match / sorting
        "suggest": fields.TextField(      # Autocomplete
            analyzer="autocomplete_analyzer",
        ),
        "synonym": fields.TextField(      # Synonym expansion
            analyzer="synonym_analyzer",
        ),
    },
)
```

This means the `name` field is indexed **4 different ways** simultaneously:
- `name` → for full-text search with stemming
- `name.raw` → for exact match, sorting, aggregations
- `name.suggest` → for autocomplete (edge n-grams)
- `name.synonym` → for synonym matching

PostgreSQL would need **4 separate columns or indexes** for this!

### Custom Analyzers (see `products/documents.py`)

```python
"analyzer": {
    # Autocomplete: "sam" matches "samsung", "sample", etc.
    "autocomplete_analyzer": {
        "tokenizer": "edge_ngram",  # "samsung" → ["sa", "sam", "sams", ...]
        "filter": ["lowercase"],
    },
    # Synonyms: "phone" also matches "mobile", "smartphone"
    "synonym_analyzer": {
        "filter": ["lowercase", {
            "type": "synonym",
            "synonyms": ["laptop, notebook, portable computer"]
        }],
    },
}
```

### Bool Query (see `products/views.py` — EsFilteredSearch)

The `bool` query is ES's most powerful query type:

```python
bool_query = {
    "must": [...],      # MUST match (affects score)
    "should": [...],    # SHOULD match (boosts score)
    "filter": [...],    # MUST match (NO scoring, CACHED → fast)
    "must_not": [...],  # Must NOT match
}
```

**Key insight:** `filter` context doesn't calculate scores and results are **cached**. This is why ES can combine full-text search with filters efficiently — filters are essentially free after the first execution.

### Function Score (see `products/views.py` — EsSortedSearch)

```python
# Combine text relevance + popularity + recency
"function_score": {
    "query": {"match": {"name": "phone"}},
    "functions": [
        # Boost high-rated products
        {"field_value_factor": {"field": "rating", "modifier": "log1p"}},
        # Prefer recent products (decay over 30 days)
        {"gauss": {"created_at": {"origin": "now", "scale": "30d"}}},
    ],
    "score_mode": "multiply"
}
```

This is **impossible in PostgreSQL** — you'd need to compute a custom score in application code.

---

## When to Use What

| Use Case                         | PostgreSQL | Elasticsearch | Why                                              |
| -------------------------------- | ---------- | ------------- | ------------------------------------------------ |
| **Source of truth**              | ✅          | ❌             | PG has ACID transactions                         |
| **User authentication**         | ✅          | ❌             | Relational integrity needed                      |
| **Orders / payments**           | ✅          | ❌             | Transactions are critical                        |
| **Product search**              | ❌          | ✅             | Full-text, fuzzy, relevance scoring              |
| **Autocomplete**                | ❌          | ✅             | Edge n-grams, instant results                    |
| **Faceted navigation**          | ⚠️          | ✅             | Single query, histograms, nested aggs            |
| **Log / event analytics**       | ⚠️          | ✅             | Time-series, high write throughput               |
| **Geo search**                  | ⚠️ PostGIS  | ✅             | Built-in, no extension needed                    |
| **Complex JOINs**               | ✅          | ❌             | ES doesn't support traditional JOINs             |
| **Foreign key constraints**     | ✅          | ❌             | ES has no referential integrity                  |
| **Reporting with exact counts** | ✅          | ⚠️             | ES aggregation counts can be approximate         |

### The Golden Rule

> **PostgreSQL is your database. Elasticsearch is your search engine.**
> 
> Write to PostgreSQL. Sync to Elasticsearch. Search from Elasticsearch.
> Never use Elasticsearch as your primary data store.

---

## Project Structure

```
elastic-search/
├── docker-compose.yml          # All services (PG, ES, Kibana, Django)
├── Dockerfile                  # Django container
├── requirements.txt            # Python dependencies
├── .env                        # Environment variables
├── manage.py                   # Django CLI
├── config/
│   ├── settings.py             # Django + ES configuration
│   ├── urls.py                 # Root URL routing
│   └── wsgi.py
└── products/
    ├── models.py               # Django models (PostgreSQL tables)
    ├── documents.py            # ES document mapping (⭐ key file)
    ├── serializers.py          # DRF serializers (PG + ES)
    ├── views.py                # Side-by-side PG vs ES views (⭐ key file)
    ├── urls.py                 # API routes
    ├── admin.py                # Django admin
    └── management/commands/
        └── seed_products.py    # Generate test data
```

### Key Files to Study

1. **`products/documents.py`** — How Django models map to ES documents, custom analyzers, multi-field mappings
2. **`products/views.py`** — Side-by-side PostgreSQL vs Elasticsearch queries with detailed comments
3. **`products/models.py`** — Traditional Django models with PostgreSQL indexes

---

## Useful Commands

```bash
# Start all services
docker compose up --build -d

# Stop all services
docker compose down

# View logs
docker compose logs -f web
docker compose logs -f elasticsearch

# Seed data
docker compose exec web python manage.py seed_products --count 1000

# Rebuild Elasticsearch index
docker compose exec web python manage.py search_index --rebuild -f

# Django shell (useful for experimenting)
docker compose exec web python manage.py shell

# Check Elasticsearch health
curl http://localhost:9200/_cluster/health?pretty

# View index mapping
curl http://localhost:9200/products/_mapping?pretty

# View index stats
curl http://localhost:9200/products/_stats?pretty

# Direct ES query (from terminal)
curl -X GET "http://localhost:9200/products/_search?pretty" \
  -H 'Content-Type: application/json' \
  -d '{"query": {"match": {"name": "wireless"}}}'

# Create superuser for Django admin
docker compose exec web python manage.py createsuperuser
```

---

## Learning Path

1. **Start here:** Read this README fully
2. **Run it:** `docker compose up --build -d` → seed → try endpoints
3. **Compare:** Hit the same search on `/api/pg/search/` and `/api/es/search/` — notice the difference
4. **Study `documents.py`:** Understand how analyzers and multi-fields work
5. **Study `views.py`:** Each view class has detailed docstrings explaining the concepts
6. **Experiment in Kibana:** Go to http://localhost:5601 → Dev Tools → run raw ES queries
7. **Break things:** Try removing fuzzy matching, changing boost values, adding new synonyms
