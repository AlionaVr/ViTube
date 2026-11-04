# 0007. Search: PostgreSQL FTS + pg_trgm

**Status:** accepted · 2026-11-04

**Context.** Search by title. `ILIKE '%…%'` ignores word forms and can't use an index.

**Decision.**

- Generated column `videos.search_vector`: title has weight A, description weight B. GIN index, ranked with `ts_rank`.
- `pg_trgm` GIN index on the title for typo tolerance and search suggestions.
- Results include only `public` + `READY` + not hidden videos.

**Alternatives.**

- ILIKE: slow, no word forms.
- Elasticsearch: a heavy extra service plus data sync; overkill here.

**Consequences.**

- ➕ No extra service.
- ➖ Simpler ranking than a dedicated search engine.
