# ABC Sales AI - Lead Intake & Triage Service

A Flask-based backend service for ingesting, validating, classifying, and storing sales leads from messaging channels. Part of the ABC Sales AI technical assessment.

## Project Status

- ✅ **Part A (Core)** — Complete
  - Lead ingestion with validation
  - Phone normalization to E.164
  - Lead classification (hot/warm/cold)
  - Database persistence
  - Error tracking
  
- 🚧 **Part B (Extensions)** — In Progress
  - §4: LLM extraction (planned)
  - §5: Relationship storage explanation (Neo4j)

---

## Quick Start

### Prerequisites

- Python 3.10+ (required for type hint syntax `str | None`)
- MySQL 5.7+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/JingYang0404/ABC_SalesAI_PracticalAssessment.git
cd ABC_SalesAI_PracticalAssessment

# Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Setup Database

```bash
# 1. Create database and tables
mysql -u root -p < schema.sql

# 2. Update config.py with your MySQL credentials
# Edit config.py:
#   DB_CONNECTION['host'] = 'your_host'
#   DB_CONNECTION['user'] = 'your_user'
#   DB_CONNECTION['password'] = 'your_password'
```

### Run the Service

```bash
# Start Flask app
python -m flask run
# or
py -3.12 app.py
```

Server runs on: `http://localhost:5000`

---

## API Endpoints

### Create Lead
```bash
POST /leads

{
  "name": "Aisyah Binti Rahman",
  "phone": "0123456789",
  "message": "I'm interested in your premium plan. What's the pricing?"
}

Response (201):
{
  "id": 1,
  "name": "Aisyah Binti Rahman",
  "phone_e164": "+60123456789",
  "classification": "warm",
  "created_at": "2026-06-28T12:34:56"
}
```

### List Leads
```bash
GET /leads
GET /leads?status=hot
GET /leads?status=warm
GET /leads?status=cold

Response (200):
{
  "count": 5,
  "leads": [
    {"id": 1, "name": "...", "classification": "hot", ...},
    ...
  ]
}
```

### Health Check
```bash
GET /health

Response (200):
{"status": "ok"}
```

### View Failed Leads
```bash
GET /failed_leads

Response (200):
{
  "count": 2,
  "failed_leads": [
    {"id": 1, "error_code": "INVALID_PHONE_FORMAT", ...},
    ...
  ]
}
```

---

## Running Tests

```bash
# Run Jupyter notebook with interactive tests
jupyter notebook test_interactive.ipynb

# Then run all test cells in order
# Tests cover:
# - Health check
# - Lead creation (hot/warm/cold)
# - Phone normalization
# - Input validation
# - Duplicate detection
# - Failed lead tracking
```

---

## Design Decisions

### Part A: Core

**Phone Normalization**
- Used `phonenumbers` library (Python) for E.164 formatting
- Handles leading zeros (Malaysia: 01x → +601x)
- Handles already-international numbers (+60xx)
- Default region configurable in `config.py`

**Classification Rules**
- Configurable rule engine in `config.py` (not hardcoded)
- Priority hierarchy: hot > warm > cold
- Keywords extracted by lowercase message matching
- Easy to update without code changes

**Database Design**
- `leads` table: core lead data + timestamps
- `failed_leads` table: audit trail of validation failures
- Phone stored as original + normalized for debugging
- Composite keys and unique constraints for data integrity

**Error Tracking**
- All validation failures logged to `failed_leads` table
- Includes error code, reason, and timestamp
- Accessible via `/failed_leads` endpoint for operational visibility
- Supports investigation: "why did this lead fail?"

**Fail-Fast Startup**
- Database connection checked at app startup
- If DB is unavailable, app exits immediately with exit(1)
- Prevents silent data loss (leads accepted but not stored)
- Operational clarity: team knows when system is down

---

## Error Codes

| Code | Status | Meaning |
|------|--------|---------|
| — | 201 | Lead created successfully |
| MISSING_FIELD | 400 | Required field missing |
| INVALID_NAME_FORMAT | 400 | Name invalid (numbers, symbols) |
| INVALID_PHONE_FORMAT | 422 | Phone can't parse to E.164 |
| DUPLICATE_LEAD | 409 | Phone already exists |
| DATABASE_ERROR | 500 | Database unavailable or error |

---

## Project Structure

```
ABC_SalesAI_PracticalAssessment/
├── app.py                    # Main Flask application
├── config.py                 # Configuration (DB, rules, etc)
├── extraction.py             # LLM extraction interface (Part B)
├── requirements.txt          # Dependencies
├── test_interactive.ipynb    # Interactive Jupyter tests
├── README.md                 # This file
└── schema.sql                # Database schema
```

---

## Part B: Extensions (Planned)

### §4: LLM Extraction (In Progress)

**What**: Extract structured fields from free-text messages using Claude API.

**Fields extracted**:
- `intent`: purchase | inquiry | complaint | null
- `product_interest`: string (e.g., "premium plan")
- `entities`: list of products/competitors mentioned
- `budget_mentioned`: boolean
- `urgency_level`: high | medium | low | null

**Design**:
- Clean interface (`LeadExtractor` ABC) for swapping LLM providers
- Injection-safe prompt design with message delimiters
- Stub implementation for testing (no API calls)
- Real Claude API integration optional

**Safety**:
- Prompt injection test included (proves instruction-in-data is ignored)
- Message wrapped in `MESSAGE START`/`MESSAGE END` delimiters
- LLM instructed to respond only with JSON (no markdown)

### §5: Relationship Storage (Design Explanation in README)

**Why Neo4j?**

At the scale of this exercise (hundreds to low thousands of leads), Neo4j makes sense if you need:
- Multi-hop relationships: "leads interested in Product X, who mention Competitor Y"
- Entity connections: shared products, shared intent, shared competitors
- Real-time graph traversals: `MATCH (l1:Lead)-[:INTERESTED_IN]->(:Product)<-[:INTERESTED_IN]-(l2:Lead) RETURN l2`

**Graph Model**:
```
Lead --[INTERESTED_IN]--> Product
Lead --[MENTIONS]--> Competitor
Lead --[HAS_INTENT]--> Intent
```

**Trade-offs**:

| Factor | Relational (SQLite/MySQL) | Graph (Neo4j) |
|--------|---------------------------|---------------|
| Simple queries | ✅ Better | ❌ Overkill |
| Multi-hop joins | ❌ Expensive | ✅ Native |
| Operational complexity | ✅ Simple | ❌ Extra service |
| Query latency (single hop) | ✅ Fast | ✅ Fast |
| Query latency (3+ hops) | ❌ Slow | ✅ Fast |
| Scalability | ✅ To 1M rows | ✅ To 1B nodes |

**When to flip**: If you need traversals deeper than 2-3 hops, or if you have >100k entities with dense relationship graphs, Neo4j wins. For this exercise, relational with denormalized entity columns is sufficient, but a graph model is architecturally cleaner for relationship-heavy queries.

**Queries we'd build**:
```cypher
-- Find leads interested in Product X
MATCH (l:Lead)-[:INTERESTED_IN]->(:Product {name: "Premium Plan"})
RETURN l

-- Find leads that mention competitors mentioned by Lead #5
MATCH (lead5:Lead)-[:MENTIONS]->(comp:Competitor)<-[:MENTIONS]-(other:Lead)
RETURN DISTINCT other
```

---

## What I'd Do Next (If Continuing)

1. **§4 Complete**
   - Add real Claude API calls (behind config flag)
   - Store extracted fields in `leads` table
   - Return extracted data in GET /leads responses
   - Add extraction to POST /leads response

2. **§5 Implementation** (if time)
   - Add Neo4j connection pool
   - Build entity graph from extracted fields
   - Implement `GET /leads/{id}/related` endpoint
   - Add aggregation queries

3. **§6 & §7**
   - Multi-hop traversal queries
   - Batch import endpoint
   - Deduplication across batch

---

## Testing

All tests are in `test_interactive.ipynb`. Run cells in order:

1. **Setup** — Load dependencies and set BASE_URL
2. **Health check** — Verify API is running
3. **Lead creation** — Test hot/warm/cold classification
4. **Validation** — Test error cases (missing fields, invalid phone, etc)
5. **Filtering** — Test GET /leads?status=X
6. **Injection safety** — Prove prompt injection doesn't hijack extraction (Part B)

---

## Deployment Notes

- **Database**: Recommend managed MySQL (AWS RDS, Google Cloud SQL) in production
- **Secrets**: Never commit `config.py` with real credentials; use environment variables
- **Logging**: Add structured logging (JSON) for operational monitoring
- **Monitoring**: Track `/failed_leads` endpoint for validation trends

---

## Contact & Questions

Built for ABC Sales AI technical assessment, June 2026.

GitHub: [@JingYang0404](https://github.com/JingYang0404)
