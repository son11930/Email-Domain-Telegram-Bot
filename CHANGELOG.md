# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2026-10-21

### Fixed
- Kept Binance transaction IDs up to the API's 256-character limit intact through manual review, wallet ledger references and notification deduplication; added a one-time PostgreSQL migration for existing databases.
- Preserved each login rate-limit bucket's own expiry so unrelated requests cannot clear a longer login window.
- Made database initialization atomic across table creation, RLS enablement and public grant revocation.

### Performance
- Batched email inventory imports, allowed concurrent purchases to share the price read lock, and removed duplicate order completion work and quadratic payment-history accumulation.
- Replaced Telegram summary reads with focused price and stock queries and moved user/email search filtering into SQL.
- Added the versioned PostgreSQL column-width migration and VPS manager to the explicitly allowed source release archive.
- Added a Windows manager action that fast-forward pulls `main`, installs locked dependencies, runs idempotent DB initialization, and restarts all three VPS services over SSH.

### Changed
- Switched the documented VPS run path from Docker Compose to three GNU Screen sessions for the bot, worker, and web; added systemd start/status/log/stop/restart guidance for boot startup and process recovery.
- Updated setup, operations, README, project plan, and validation notes to match the Screen-based VPS workflow.
- Added a systemd template to launch and supervise the three Screen sessions at boot and restart them if their processes exit.
- Moved the admin web listener and Nginx upstream to localhost port 8001 to avoid the user's existing service on port 8000; added bounded log rotation and graceful Screen stop handling.
- Replaced credential-bearing values in `.env.example` with empty fields/placeholders, expanded local-tool ignores, and excluded Python egg-info from release archives before GitHub publication.
- Added log and local Codex workspace exclusions, documented the repository description in README, and removed unrelated machine-specific changelog notes before publication.
- Added a Windows batch manager for checking, starting, stopping, restarting, and viewing logs for the VPS bot, worker, and web services, plus Screen session listing and SSH access.
- Excluded `.env.example` from Git so credential placeholders and configuration examples are not published with the repository.
- Updated public setup docs to create `.env` directly and list required settings without relying on the excluded `.env.example`.

### Implemented
- Added the public Thai Telegram bot with instant 0.30-credit purchases, bulk confirmation, TXT plus copyable text delivery, history/resend and protected admin import/credit/delete actions.
- Added PostgreSQL transactional inventory, exact integer wallet ledger, permanent unique payment reservations, refunds, manual exception review, persistent pricing and audit records. Production schema denies anonymous/API roles by default with RLS.
- Added the Supabase-authenticated admin website with CSRF protection, credit confirmation, stale-balance checks, individual/bulk soft deletion and management history.
- Added read-only signed Binance Pay reconciliation, late-payment handling, durable checkpoints, two Discord webhook channels and outbox retries with ownership leases.
- Added runtime configuration, secret-redacting logging, dependency lock, Docker/Nginx deployment templates and Thai setup/operations documentation.
- Verified 141 automated tests including six real PostgreSQL concurrency/RLS cases; combined coverage 92.24%, Ruff and dependency consistency checks passed. Dependency vulnerability audit found no known vulnerabilities after upgrading the isolated pip tool.
- No production accounts were configured, no real payments/messages were sent, and no VPS deployment was performed; see `docs/VALIDATION.md` for remaining live checks.

### Changed
- Revised `plan.md` to allow public Telegram registration, set 0.30 credit per domain email and 1 USDT = 1 credit, and specify automatic Binance UID top-ups using unique randomized amounts with 3–4 decimal places.
- Replaced the local SQLite proposal with external Supabase Free PostgreSQL and a dedicated admin website for credit and email management; added separate Discord top-up/order webhooks, bulk text plus one TXT file, API key setup guidance, and late-payment/idempotency requirements.
- Updated `PROJECT_PLAN.md` to reflect the confirmed requirements and revised phases. Changes remain documentation only.

### Added
- Added `plan.md` for review of an internal Telegram email allocation bot, including one-click allocation, credit accounting, admin-only email import, Binance UID top-ups, free database options, and VPS operations.
- Added `PROJECT_PLAN.md` with planning status and implementation approval gates. This update contains documentation only; no bot implementation, database, live payment integration, or deployment was created.
