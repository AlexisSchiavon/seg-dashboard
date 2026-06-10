# Pitfalls Research

**Domain:** Talent-agency commercial intelligence dashboard (FastAPI + SQLite + Pipedrive/Sheets/Trello/Claude integrations, Docker/EasyPanel deploy)
**Researched:** 2026-06-09
**Confidence:** HIGH (auth, SQLite, Pipedrive, Sheets, Trello, Claude pricing — all verified against current docs/community sources). MEDIUM for EasyPanel-specific volume behavior (less documented, inferred from Docker general practice + community examples).

## Critical Pitfalls

### Pitfall 1: bcrypt/passlib breakage on Python 3.12 (auth foundation rot before you even start)

**What goes wrong:**
The classic FastAPI security tutorial (`passlib[bcrypt]` + `CryptContext`) is currently broken on fresh installs. `passlib` is unmaintained (last release ~3 years ago), imports the deprecated `crypt` module (removed in Python 3.13, warns in 3.12), and `bcrypt` 5.0+ removed the `__about__` attribute that passlib's backend detection relies on — causing import errors or silent failures. Separately, bcrypt has a hard 72-byte password limit; bcrypt 5.0+ raises `ValueError` instead of silently truncating, which can crash registration/login for users with long passwords or passphrases.

**Why it happens:**
Developers copy the official FastAPI security tutorial verbatim without checking current package compatibility. This is a textbook "training data is stale" trap — the tutorial code was correct when written but the dependency chain has since broken.

**How to avoid:**
- Use `bcrypt` directly (the `bcrypt` package, not passlib) OR pin `bcrypt<5.0` if using passlib, OR use a maintained alternative like `pwdlib` (designed as passlib's spiritual successor) or `argon2-cffi`.
- If using bcrypt directly, pre-hash long passwords with SHA-256 before bcrypt, or enforce a max password length at the Pydantic schema level (e.g., 64 chars) to stay under 72 bytes.
- Pin exact versions in `pyproject.toml` and verify the hash/verify roundtrip works in a quick test before building anything on top of it.

**Warning signs:**
- `ImportError` or `AttributeError` mentioning `__about__` on first run of auth code.
- DeprecationWarning about the `crypt` module at startup.
- Login works in dev but throws 500 errors for users with longer passwords.

**Phase to address:**
M1 (FastAPI base + JWT + health check) — this is the literal foundation; get it right before anything depends on it.

---

### Pitfall 2: JWT secret management and token lifetime decisions baked in wrong from M1

**What goes wrong:**
Two common failure modes: (1) `SECRET_KEY` hardcoded or committed in `.env` to git, or generated once and never rotatable; (2) access tokens issued with long expiry (days) with no refresh mechanism, OR short expiry with no refresh token at all — forcing users to re-login constantly or leaving stale long-lived tokens that can't be revoked.

**Why it happens:**
At M1, "JWT auth" feels like a solved/boilerplate problem, so teams pick whatever expiry value works for local testing (often very long, like 7 days, "so I don't have to log in again") and never revisit it. Since this app has "no roles, same access for everyone," it's tempting to under-engineer auth entirely.

**How to avoid:**
- Generate `SECRET_KEY` with `openssl rand -hex 32`, store only in `.env` (gitignored), document in `.env.example` as a placeholder. Load via `pydantic-settings` `BaseSettings`.
- Use short-lived access tokens (15-30 min) for a small internal team tool — even without refresh tokens, the team logging in once a day is acceptable. If adding refresh tokens, store them server-side (DB table) so they can be revoked, not just signed JWTs.
- Given this is a small internal team (2-5 users), a pragmatic middle ground is acceptable: longer-lived access tokens (e.g., 8-24h matching a workday) WITHOUT refresh token complexity — but document this as a deliberate tradeoff, not an oversight, since it affects M7 security posture.

**Warning signs:**
- `.env` file appears in `git status` as tracked or staged.
- SECRET_KEY value is a short/predictable string (e.g., "secret123").
- No documented token expiry value anywhere in code/config.

**Phase to address:**
M1. Decide and document the expiry/refresh strategy explicitly as a Key Decision — don't let it be implicit.

---

### Pitfall 3: SQLite "database is locked" errors once Pipedrive/Sheets/Trello sync writes overlap with dashboard reads

**What goes wrong:**
SQLite uses a single writer lock for the whole database file. Once M2-M4 add background sync jobs (polling Pipedrive, refreshing Sheets data, processing Trello webhooks) that write to SQLite while users are simultaneously loading dashboard pages (which read), you start getting intermittent `sqlite3.OperationalError: database is locked` errors — especially under FastAPI's async request handling where multiple requests can be in-flight concurrently.

**Why it happens:**
M1 ships with default SQLite settings (rollback journal mode, default busy timeout of 0 or very low). It works fine with zero concurrent writers during initial development. The problem only appears once M2+ introduces a second writer (sync jobs), often discovered in M5-M7 under "real" usage when it's expensive to retrofit.

**How to avoid:**
- In M1, configure SQLite for WAL (Write-Ahead Logging) mode immediately: `PRAGMA journal_mode=WAL;` — this allows concurrent readers during a write.
- Set a busy timeout of 5-10 seconds: `PRAGMA busy_timeout=10000;` (configure via SQLAlchemy `connect_args` or an event listener on connect).
- Keep write transactions short — don't hold a transaction open while making external API calls (e.g., don't do "open DB transaction → call Pipedrive API → write results" in one transaction; fetch from API first, then do a quick DB write).
- For SQLAlchemy, use `connect_args={"check_same_thread": False, "timeout": 10}` and consider `NullPool` or careful session management to avoid long-held connections from async endpoints.
- Architect sync jobs (M2-M4) to run as scheduled background tasks (not per-request), writing in small batches/transactions.

**Warning signs:**
- Any `OperationalError: database is locked` in logs, even rarely — it will get worse under load, not better.
- Sync jobs and dashboard endpoints sharing the same DB file with default pragma settings.

**Phase to address:**
M1 (set WAL mode + busy_timeout as part of `database.py` setup, before any other module is built on top of it). Re-verify in M2 when the first background sync job is added.

---

### Pitfall 4: SQLite database file lost on redeploy — no persistent volume configured on EasyPanel

**What goes wrong:**
The SQLite file (`seg.db`) lives inside the container filesystem by default. Every redeploy (which is frequent in an incremental M1-M7 build) creates a fresh container, wiping the database — losing all talent config, cached Pipedrive data, report history, etc. This is often discovered the first time someone redeploys after adding real data, with no backup.

**Why it happens:**
Dockerfile/docker-compose works fine locally where the bind mount is implicit (working directory). When translated to EasyPanel, if the volume mount for the DB path isn't explicitly configured in EasyPanel's "Mounts" / storage settings, the container filesystem is ephemeral.

**How to avoid:**
- In `docker-compose.yml`, explicitly define a named volume or bind mount for the directory containing `seg.db` (e.g., `/app/data:/data` with `DATABASE_URL=sqlite:////data/seg.db`).
- In EasyPanel, configure a persistent volume mount pointing to that same path — verify it survives a manual redeploy before relying on it.
- Add a simple backup strategy even at MVP scale: a cron/script that copies `seg.db` to cloud storage periodically (or use Litestream for continuous SQLite replication to S3-compatible storage — well-documented pattern for EasyPanel + SQLite).
- Test the "redeploy and confirm data survives" flow explicitly as part of M7 acceptance criteria — don't assume it.

**Warning signs:**
- DB path defaults to a relative path inside the app directory (e.g., `./seg.db`) with no corresponding volume declared.
- No documented backup/restore procedure.
- First redeploy after seeding data results in empty tables.

**Phase to address:**
M7 (Deploy + Docker + EasyPanel) — but the `DATABASE_URL` path convention should be decided in M1 so it's consistent (e.g., always `/data/seg.db` from day one, even running locally via a mounted `./data` folder), avoiding a path migration later.

---

### Pitfall 5: Pipedrive custom fields referenced by label/name instead of field key (hash)

**What goes wrong:**
Pipedrive custom fields (loss reason, brand category, expected collection date) are exposed in the API as long hash keys (e.g., `a1b2c3d4e5f6...40chars`), not by their human-readable names. If integration code reads/writes these fields using the displayed label ("Razón de pérdida"), the Pipedrive API silently ignores unrecognized fields on writes, and reads return `null`/`KeyError` on the wrong key — with no obvious error, just missing/empty data in the dashboard.

**Why it happens:**
Developers test against the Pipedrive UI (which shows labels) and assume the API mirrors that. The API actually returns `{"a1b2c3...": "value"}` for custom fields on a deal object. This is the single most common Pipedrive integration mistake — over half of initial custom-field update failures stem from this.

**How to avoid:**
- On integration startup (or a one-time setup script), call the `dealFields` endpoint to fetch all custom field definitions, build a name→key mapping, and store/cache this mapping (don't hardcode hash keys in business logic).
- Reference fields by their stable `name` in your code/config (e.g., a `FIELD_MAP = {"loss_reason": <looked up at runtime>, ...}`), resolving to the current hash key dynamically — this survives field deletion/recreation.
- Write an integration test early in M2 that fetches one real deal and asserts the three custom fields (loss reason, brand category, expected collection date) resolve to non-null values using this mapping — catches the issue immediately rather than as a silent data gap discovered in M5 reports.

**Warning signs:**
- Custom field values appear as `None`/empty in the dashboard despite being filled in Pipedrive.
- Hardcoded 40-character hex strings anywhere in `integrations/pipedrive.py`.

**Phase to address:**
M2 (Pipedrive integration) — build the field-key resolution layer as part of the initial Pipedrive client, not as a later patch.

---

### Pitfall 6: Polling Pipedrive without pagination/rate-limit handling, missing the 2000-deal status filter cap

**What goes wrong:**
Pipedrive deal-list endpoints default to 100 items per page (max 500), and filtering deals by status (e.g., "won") has an upper limit of 2000 results returned. For 21 talents with ongoing deal history, this cap likely won't be hit immediately, but as the agency grows or historical data accumulates, a naive "fetch all deals" call that doesn't paginate will silently return only the first page — making KPIs/funnel counts wrong without any error.

**Why it happens:**
Initial development tests against a small dataset where one page covers everything. The pagination/cursor logic is "obviously needed eventually" but gets deferred, and since the bug manifests as "numbers are slightly low" rather than a crash, it can go unnoticed for a long time — directly undermining the "trustworthy revenue numbers" core value of this dashboard.

**How to avoid:**
- Implement pagination handling (`start`/`limit` or cursor-based, depending on endpoint) in the Pipedrive client from the first integration call, even if current data volume doesn't require it.
- Add a basic test/assertion: total deals fetched via pagination matches the `additional_data.pagination.more_items_in_collection` flag being `false` at the end.
- Implement exponential backoff for 429 responses (Pipedrive enforces per-token rate limits and bans webhooks after repeated failures — same backoff discipline applies to polling).

**Warning signs:**
- Funnel/KPI totals that don't match manual counts in the Pipedrive UI as data grows.
- No loop/cursor logic in `integrations/pipedrive.py` — a single API call assumed to return "everything."

**Phase to address:**
M2 (Pipedrive integration) — build pagination into the base client function from the start.

---

### Pitfall 7: Relying on the Pipedrive "won deal → Trello card" automation without a reconciliation/fallback mechanism

**What goes wrong:**
The automation (Pipedrive deal marked "won" → create Trello card with collection date) is a webhook- or polling-driven side effect. If implemented purely as "fire-and-forget" on a webhook event, any missed event (webhook ban after failures, network blip, deploy downtime during the event) means a won deal silently never gets a Trello card — and nobody notices until collections are missed.

**Why it happens:**
Webhooks feel "real-time and complete," but Pipedrive's webhook ban system disables a webhook after 10 consecutive failures (banned for 30 min, escalating), and Trello similarly disables webhooks after sustained failures over 30 days. During M4-M7 development (frequent redeploys = the receiving endpoint is down often), webhook events fired during downtime are simply lost — there's no built-in retry/replay queue from either Pipedrive or Trello.

**How to avoid:**
- Treat the webhook as a "trigger to check now" rather than the sole source of truth. Pair it with a periodic reconciliation job (e.g., every N hours, query Pipedrive for deals that are "won" + don't yet have a corresponding Trello card flag in your DB, and create missing cards).
- Store the automation's state in your own DB (e.g., a `deal_id -> trello_card_id` mapping with a `synced_at` timestamp) so reconciliation is idempotent (don't create duplicate cards).
- Log every automation attempt (success/failure) so a human can audit "which won deals don't have Trello cards yet."

**Warning signs:**
- Automation logic exists only inside a webhook handler with no scheduled job as backup.
- No DB table tracking deal→card linkage — re-running the sync would create duplicate Trello cards.

**Phase to address:**
M4 (Trello integration) — design the linkage table and reconciliation job alongside the webhook handler, not as a follow-up.

---

### Pitfall 8: Google Sheets schema drift breaking the leads ingestion silently

**What goes wrong:**
The Gmail-derived leads sheet is maintained by humans (sales team), not by code. Column order changes, a column gets renamed, a new column is inserted, or someone adds a filter/extra header row — and `gspread` code that reads rows by column index (`row[3]`) or relies on a fixed header position breaks or, worse, misreads data into the wrong fields (e.g., "fuente" data lands in "talento" field) without any error.

**Why it happens:**
M3 is built against the sheet's current structure, which seems stable during development. But it's a live operational spreadsheet the sales team continues to edit — schema drift is inevitable over the project's lifetime, and gspread doesn't validate structure for you.

**How to avoid:**
- Read by header name, not column index: fetch the header row first, build a column-name→index map, and look up values by name (`gspread`'s `get_all_records()` does this automatically, returning list of dicts keyed by header).
- Validate expected headers exist on each sync run; if a required column is missing/renamed, log a clear error/alert rather than silently mis-mapping or crashing mid-loop.
- Consider a lightweight "sheet contract" doc (which columns are expected, exact names) shared with the team, and a startup check that compares actual headers against this contract.

**Warning signs:**
- Code uses positional indexing (`row[2]`, `row[5]`) into sheet rows.
- Leads dashboard shows obviously wrong data in a field (e.g., dates appearing in a "talento" column) after the sales team edits the sheet.

**Phase to address:**
M3 (Google Sheets integration) — use `get_all_records()` / header-based access from day one, plus a startup schema-validation check.

---

### Pitfall 9: Google Sheets API quota exhaustion from per-request reads in dashboard endpoints

**What goes wrong:**
The Sheets API v4 allows 300 requests/60s per project and 60 requests/60s per user (service account = one "user" for quota purposes). If the leads dashboard tab calls `gspread` directly on every page load/refresh (or every API call to a leads endpoint), a handful of users refreshing the dashboard can exceed 60 req/min, producing `APIError 429 RESOURCE_EXHAUSTED` and a broken Leads tab.

**Why it happens:**
Direct "read sheet on request" feels simplest during M3 development with one developer making occasional requests — quota issues only appear once multiple users/auto-refresh intervals are active, often discovered late.

**How to avoid:**
- Never call gspread directly from a request-handling path. Sync sheet data into SQLite on a schedule (e.g., every 5-15 minutes via a background job), and serve the dashboard from the local DB cache.
- This also solves the schema-validation problem (Pitfall 8) in one place — the sync job is the single point of contact with the sheet.
- If a 429 does occur during sync, implement exponential backoff and retry on the next scheduled run rather than failing the whole sync.

**Warning signs:**
- `integrations/sheets.py` functions called directly from `routers/leads.py` request handlers.
- `APIError: 429` in logs correlating with dashboard usage spikes.

**Phase to address:**
M3 (Google Sheets integration) — establish the "sync to local DB, serve from DB" pattern here; this same pattern should also be used for Pipedrive (M2) and Trello (M4) for consistency and to keep dashboard load times fast regardless of external API latency.

---

### Pitfall 10: Claude-generated PDF reports presenting hallucinated/recalculated numbers as fact

**What goes wrong:**
For M5 (AI PDF reports) and M6 (NL agent), if Claude is asked to "summarize this month's revenue by talent" with the underlying numbers passed loosely in a prompt (or worse, asked to recall/recompute totals itself), there's a real risk of the model producing plausible-but-wrong numbers — especially with multi-step aggregation (sums, percentages, the 70% commission split) done "in its head" rather than via code. In a financial report sent to agency leadership, an incorrect revenue figure is a serious credibility/trust failure for the whole product.

**Why it happens:**
LLMs are good at narrative/insight generation but unreliable at precise arithmetic over many numbers, especially when the numbers are embedded in long context rather than freshly computed. It's tempting to hand Claude a big data dump and a prompt like "write a report with totals and insights" — letting the model both compute and narrate.

**How to avoid:**
- **Strict separation of computation and narration**: All numeric aggregates (totals, percentages, 70% commission splits, funnel counts, projections) must be computed in Python (in `services/kpis.py` / `services/funnel.py`) using the SQLite data — never by the LLM. Pass only pre-computed, already-correct numbers into the prompt.
- Claude's role is narrative/insight generation ON TOP of numbers you supply, formatted clearly in the prompt (e.g., as a structured JSON block or table), with explicit instruction: "Use only the numbers provided below. Do not calculate, estimate, or modify any figures."
- For the M6 NL agent, use tool-use/function-calling: define tools like `get_talent_revenue(talent_id, month)` that execute real SQL queries and return exact numbers — the agent calls these tools and reports their results, rather than reasoning over raw data dumps.
- Add a final rendering step that cross-checks any numbers appearing in the generated report text against the source data (simple regex/number extraction + comparison) before the PDF is finalized — flag mismatches for review rather than auto-publishing.
- Allow/encourage "I don't have data for X" responses in both M5 and M6 rather than the model filling gaps with plausible guesses.

**Warning signs:**
- Prompts that include raw row-level data and ask the model to "calculate the total."
- No automated check comparing report numbers to DB query results.
- NL agent answers questions by reasoning over a text dump instead of calling a query tool.

**Phase to address:**
M5 (AI PDF reports) for the report-generation pattern; M6 (NL agent) for the tool-use/function-calling pattern. Both should be designed around "Claude narrates, code computes" as a hard architectural rule established before M5 starts.

---

### Pitfall 11: Claude API cost runaway from uncached, unbounded NL agent conversations

**What goes wrong:**
The M6 NL agent, if implemented naively (re-sending full system prompt + tool definitions + conversation history on every turn without prompt caching), can become unexpectedly expensive — especially if tool definitions or reference data (e.g., the full talent roster, field mappings, schema descriptions) are large and re-sent on every message. For a small internal tool this might "only" be tens of dollars/month, but it's an easy oversight that compounds, and with no usage caps it can spike if someone scripts repeated queries.

**Why it happens:**
Cost optimization (prompt caching, conversation length limits, model tier selection) is usually an afterthought added "later" — but retrofitting caching requires restructuring how prompts are assembled (stable content must be at the start of the prompt and marked with cache breakpoints), which is harder after the agent's prompt-construction code is already written ad hoc.

**How to avoid:**
- Structure prompts from the start with stable content (system instructions, tool definitions, schema/field reference docs) at the beginning, and use prompt caching cache-control breakpoints on that stable prefix — cache reads cost ~10% of normal input price.
- Cap conversation history length (e.g., last N turns) sent to the API for the NL agent; don't accumulate unbounded context.
- Choose an appropriately-sized model for each use case — the NL agent for internal data queries likely doesn't need the largest/most expensive model tier; reserve higher-capability models for M5's report narrative generation if quality differences justify it.
- Set up basic usage monitoring/alerting via the Anthropic console from M5 onward (cost per report, cost per agent session) so cost trends are visible before they become a surprise bill.

**Warning signs:**
- Prompt-construction code interpolates large static content (tool schemas, field maps) inline with dynamic content on every call, with no `cache_control` markers.
- No visibility into per-feature API spend in the Anthropic console.

**Phase to address:**
M5 (establish prompt-caching-friendly prompt structure for report generation) and M6 (apply same pattern to agent conversations, add history length limits).

---

### Pitfall 12: Talent catalog modeled as a hardcoded list/enum instead of a DB-driven config

**What goes wrong:**
The 21 current talents (Navarretes Show, Don Silverio, etc.) are a concrete, finite list right now — tempting to hardcode as a Python enum, constant list, or even just rely on whatever appears as "products" in Pipedrive. But the explicit requirement is "agregar talentos nuevos sin tocar código" (add new talents without touching code). If M1/M2 models talents implicitly via Pipedrive product names rather than as a first-class DB entity with its own ID, adding a 22nd talent requires code changes or fragile string-matching against Pipedrive product names (which could have typos/variants).

**Why it happens:**
At M1, there's no UI yet for managing talents, so "just hardcode the 21 names for now, build the admin UI later" feels like reasonable MVP scoping. But every downstream module (M2 funnel-by-talent, M3 leads-by-talent, M4 Trello cards, M5 reports) ends up joining/filtering on however talents were modeled in M1-M2 — retrofitting a proper `talents` table later means migrating all those joins.

**How to avoid:**
- In M1 or early M2, create a `talents` table (id, name, pipedrive_product_id/name, active flag, etc.) seeded with the 21 current talents via a migration/seed script — not hardcoded in application code.
- All other modules reference talents by this internal ID, with a mapping layer to Pipedrive's product identifiers (similar pattern to Pitfall 5's field-key resolution).
- Even without a full admin UI, "add a row to the talents table" (via direct DB access or a simple seed script) satisfies "no code changes" for now; a proper admin UI can come later without changing the data model.

**Warning signs:**
- Talent names appear as string literals/enums in multiple files (`routers/`, `services/`).
- No `talents` table in `models.py` by the end of M2.

**Phase to address:**
M1 (define the `talents` table in the initial schema) — even if M1 itself doesn't populate it from real data, getting the schema right first avoids a painful migration when M2 (Pipedrive) and M3 (Sheets) both need to reference talents.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|-----------------|-----------------|
| Calling Pipedrive/Sheets/Trello APIs directly from request handlers (no local sync/cache) | Faster to build, fewer moving parts in M2-M4 | Slow dashboard (external API latency on every load), quota/rate-limit failures, no offline resilience | Never beyond initial M2 prototype — refactor to sync-to-DB pattern before M3 |
| Hardcoding the 21 talents as a Python list/enum | Zero schema work in M1 | Every later module couples to this representation; "add talent" requires code + redeploy, violating stated requirement | Acceptable only for a throwaway M1 health-check demo, not once M2 begins |
| Long-lived JWT (days) with no refresh token | Simple, no token-refresh UI needed | No revocation; stolen token valid for days; harder to retrofit refresh flow later | Acceptable for this small internal team IF documented as deliberate and SECRET_KEY rotation procedure exists |
| Storing `GOOGLE_SERVICE_ACCOUNT_JSON` as a literal multi-line env var | Quick to wire up | Easy to leak in logs/error messages, awkward to rotate, some platforms mangle multi-line env vars | Acceptable if base64-encoded in env and decoded at startup, with `.gitignore` covering any local JSON file |
| Letting Claude compute totals/percentages directly in report prompts | Less Python code in M5 | Hallucination risk on financial figures = trust-breaking errors in client-facing reports | Never — compute in Python, narrate with Claude |
| Default SQLite journal mode (rollback) with no busy_timeout | Zero config in M1 | "Database is locked" errors once M2+ adds background sync jobs | Never beyond local single-user dev |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|-----------------|-------------------|
| Pipedrive | Referencing custom fields by label/name (silently ignored on writes, returns null on reads) | Resolve field name → hash key via `dealFields` endpoint at startup; cache the mapping |
| Pipedrive | Fetching deals without pagination loop (default 100/page, max 500, 2000 cap on status-filtered results) | Implement pagination/cursor loop in base client from first call |
| Pipedrive | Treating "won → Trello card" webhook as the only sync path | Add periodic reconciliation job + DB linkage table (deal_id → trello_card_id) |
| Google Sheets (gspread) | Reading rows by positional index; calling sheet API directly per dashboard request | Use `get_all_records()` (header-based); sync to local DB on a schedule, serve dashboard from DB |
| Google Sheets | Service account lacks "Editor" share permission on the specific sheet (common setup miss) | Explicitly share the target Google Sheet with the service account's email address; verify with a read-only test call before building on it |
| Trello | Assuming webhook delivery is guaranteed/complete | Pair webhook with reconciliation polling; log all automation attempts for audit |
| Trello | Hardcoding board/list IDs as magic strings scattered across code | Centralize board/list ID constants in `config.py`, loaded from env (`TRELLO_BOARD_IDS`), with names resolved once at startup |
| Claude API | Sending raw data dumps and asking Claude to compute totals | Pre-compute all numbers in Python; Claude narrates only |
| Claude API | Re-sending full tool definitions/schema docs every turn with no caching | Structure prompts with stable prefix + `cache_control` breakpoints from the start |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|-----------------|
| Direct external API calls on every dashboard page load | Slow page loads (seconds), occasional 429s from Sheets/Pipedrive | Sync external data to SQLite on a schedule; serve dashboard from local DB | Immediately noticeable with 2+ concurrent users, or any auto-refresh |
| SQLite without WAL mode + busy_timeout | Intermittent `database is locked` errors during sync windows | `PRAGMA journal_mode=WAL` + `busy_timeout=10000` in M1 `database.py` | As soon as a second writer (background sync job) is introduced in M2 |
| Unbounded NL agent conversation history sent to Claude on every turn | Slowly increasing latency and per-message cost in M6 | Cap history length; use prompt caching for stable prefix | Noticeable after ~10-20 turn conversations, or with frequent agent use across the team |
| No caching layer for KPI/funnel calculations recomputed on every dashboard load | Dashboard feels sluggish as deal/lead volume grows | Compute KPIs during the sync job and store results, or cache with short TTL | Becomes noticeable once Pipedrive deal history grows beyond a few hundred records |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Committing `.env` (with real API tokens for Pipedrive/Trello/Anthropic/Google) to git | Full credential leak, especially since this repo may be shared/cloned across client engagements | `.gitignore` `.env` from the very first commit; only commit `.env.example` with placeholder values |
| `GOOGLE_SERVICE_ACCOUNT_JSON` printed in logs/tracebacks during debugging | Service account credential leak in log files/monitoring tools | Never log the full settings object; redact secrets in any debug/error output |
| SECRET_KEY reused across dev/staging/production, or weak/predictable | Token forgery if any environment's key leaks compromises all environments | Generate distinct `openssl rand -hex 32` keys per environment |
| No rate limiting on `/auth/login` endpoint | Brute-force credential attacks against the JWT login endpoint | Add basic rate limiting (e.g., `slowapi`) to login endpoint even for a small internal tool — it's exposed to the public internet via EasyPanel |
| Anthropic API key with no spend limit configured | Runaway cost if key is leaked or agent loop misbehaves | Set a usage/spend limit in the Anthropic console as part of M5 setup |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|------------------|
| Dashboard shows stale data with no "last updated" indicator | Leadership distrusts numbers if they don't match what they just saw in Pipedrive | Show "Datos actualizados: [timestamp]" based on last successful sync job run, for every data source independently |
| Sync failures (Pipedrive down, Sheets quota hit) fail silently, dashboard just shows old/empty data | Users don't know data is wrong, make decisions on bad numbers | Surface sync health/errors somewhere visible (even a small status indicator); log failures clearly |
| AI-generated PDF report has no indication of data cutoff date or which numbers are "actual" vs "projected" | Confusion about whether figures are final or estimates, especially for "cobrado/proyección/pendiente" splits | Explicitly label every figure category in reports and the agent's responses; include a "as of [date]" header on every report |

## "Looks Done But Isn't" Checklist

- [ ] **JWT auth (M1):** Often missing — token expiry actually enforced (test with an expired token, confirm 401, not silent acceptance).
- [ ] **Pipedrive sync (M2):** Often missing — pagination tested with >100 deals (not just the first page); custom fields resolved via dealFields mapping, not hardcoded keys.
- [ ] **Google Sheets sync (M3):** Often missing — behavior when the sheet's headers are reordered/renamed; service account permission verified on the actual production sheet (not just a test sheet).
- [ ] **Trello automation (M4):** Often missing — reconciliation for deals won while the app was down/redeploying; idempotency (re-running sync doesn't create duplicate cards).
- [ ] **AI Reports (M5):** Often missing — verification that report numbers exactly match DB query results (no LLM-computed totals); behavior when a talent has zero data for the period (no hallucinated "estimate").
- [ ] **NL Agent (M6):** Often missing — agent refuses/admits uncertainty when asked about data outside its tool scope, rather than guessing; cost per conversation is bounded/monitored.
- [ ] **Docker/EasyPanel deploy (M7):** Often missing — SQLite data survives a redeploy (tested explicitly, not assumed); `.env` secrets configured in EasyPanel's env settings, not baked into the image.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|-----------------|------------------|
| bcrypt/passlib import errors (Pitfall 1) | LOW | Swap to `bcrypt` directly or `pwdlib`; re-hash existing passwords on next login (force password reset if any users already exist) |
| SQLite locking errors discovered late (Pitfall 3) | MEDIUM | Enable WAL mode + busy_timeout (no schema change needed); audit sync jobs for long-held transactions; if still insufficient, migrate to PostgreSQL (SQLAlchemy makes this mostly a connection-string + minor dialect change) |
| Talents hardcoded instead of DB-driven (Pitfall 12) | MEDIUM-HIGH | Create `talents` table, seed from current hardcoded list, then refactor each module's talent references to FK lookups — touches every module built so far, so cheaper the earlier it's caught |
| Pipedrive custom fields referenced by label (Pitfall 5) | LOW | Add the field-key resolution layer; update the few lookup points (likely isolated to `integrations/pipedrive.py` if module boundaries were respected) |
| Claude-hallucinated numbers shipped in a report (Pitfall 10) | HIGH (trust/reputation) | Retract/reissue the report with corrected numbers; implement the compute/narrate separation retroactively; consider a manual review step for reports until the validation check is built |
| SQLite data lost on EasyPanel redeploy (Pitfall 4) | HIGH if no backup exists | If caught before it happens: configure volume + test. If data already lost: re-sync from Pipedrive/Sheets/Trello (source systems are the real source of truth, so SQLite loss is recoverable via a full re-sync — another argument for treating SQLite as a cache/derived store, not the system of record) |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|-------------------|----------------|
| bcrypt/passlib breakage (#1) | M1 | Run a unit test that hashes and verifies a password roundtrip on a clean install |
| JWT secret/expiry strategy (#2) | M1 | `.env.example` documents SECRET_KEY generation; expiry value documented as a Key Decision |
| SQLite locking (#3) | M1 (config), verified M2 | `PRAGMA` settings present in `database.py`; M2 sync job + concurrent dashboard read tested together without lock errors |
| SQLite volume persistence (#4) | M1 (path convention), M7 (volume) | Redeploy test on EasyPanel confirms data survives |
| Pipedrive field key resolution (#5) | M2 | Integration test asserts non-null values for loss reason, brand category, expected collection date on a real deal |
| Pipedrive pagination (#6) | M2 | Test against a deal set >100 (or mock pagination response) confirms full retrieval |
| Won-deal → Trello reconciliation (#7) | M4 | Manually mark a deal "won" while app is stopped, restart, confirm reconciliation job creates the missing card without duplicating existing ones |
| Sheets schema drift (#8) | M3 | Header-based access (`get_all_records`) used; startup check validates expected columns present |
| Sheets quota (#9) | M3 (and pattern reused M2/M4) | Dashboard endpoints never call gspread/Pipedrive/Trello directly — verified by code review of router files |
| Hallucinated report numbers (#10) | M5 | Automated check comparing every numeric figure in generated report text to DB query results before finalizing PDF |
| Claude cost control (#11) | M5/M6 | Prompt structure uses cache_control on stable prefix; Anthropic console spend limit configured |
| Talent catalog as DB entity (#12) | M1 | `talents` table exists in `models.py` schema before M2 begins, seeded with 21 current talents |

## Sources

- [FastAPI OAuth2/JWT tutorial](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
- [passlib unmaintained / bcrypt 5.0 breaking change discussion (fastapi/fastapi#11773)](https://github.com/fastapi/fastapi/discussions/11773)
- [bcrypt 72-byte limit issue (pyca/bcrypt#1082)](https://github.com/pyca/bcrypt/issues/1082)
- [SQLite concurrent writes and "database is locked" errors](https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/)
- [SQLite for a REST API Database? (matduggan.com)](https://matduggan.com/sqlite-for-a-rest-api-database/)
- [Abusing SQLite to Handle Concurrency (SkyPilot Blog)](https://blog.skypilot.co/abusing-sqlite-to-handle-concurrency/)
- [Pipedrive Custom Fields docs](https://pipedrive.readme.io/docs/core-api-concepts-custom-fields)
- [Pipedrive API Custom Fields pitfalls (AeroLeads)](https://aeroleads.com/blog/pipedrive-api-custom-fields-create-update-keep-data-clean/)
- [Pipedrive Deals API v1 reference (pagination, status filter limits)](https://developers.pipedrive.com/docs/api/v1/Deals)
- [Pipedrive Webhooks v2 guide (ban system)](https://pipedrive.readme.io/docs/guide-for-webhooks-v2)
- [Google Sheets API usage limits](https://developers.google.com/workspace/sheets/api/limits)
- [gspread quota issue discussion (burnash/gspread#583)](https://github.com/burnash/gspread/issues/583)
- [Trello API Rate Limits (Atlassian)](https://developer.atlassian.com/cloud/trello/guides/rest-api/rate-limits/)
- [Trello Webhooks guide (Atlassian)](https://developer.atlassian.com/cloud/trello/guides/rest-api/webhooks/)
- [Reduce hallucinations - Claude API Docs](https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/reduce-hallucinations)
- [Prompt caching - Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [EasyPanel + SQLite + Litestream example (deadcoder0904/easypanel-nextjs-sqlite)](https://github.com/deadcoder0904/easypanel-nextjs-sqlite)
- [Docker volumes / SQLite persistence basics](https://docs.docker.com/get-started/workshop/05_persisting_data/)

---
*Pitfalls research for: SEG Talent Intelligence Dashboard (talent-agency BI dashboard with FastAPI + SQLite + Pipedrive/Sheets/Trello/Claude)*
*Researched: 2026-06-09*
