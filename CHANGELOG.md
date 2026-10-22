# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2026-10-21

### User experience
- Rebranded the Telegram home message and admin dashboard as Nethinat Mail Service.
- Formatted bank account number and transfer amount as Telegram copyable code fields and removed the SlipOK provider name from customer-facing transfer instructions.

### Telegram bank top-ups
- Added optional `BANK_NAME` configuration and display it in bank transfer instructions so users can identify the recipient bank before transferring.

### Bank transfer top-ups
- Added a bounded SlipOK client and private-chat bank transfer flow that displays configured recipient details, randomized satang amount, and expected credit.
- Added a separate PostgreSQL bank top-up/payment ledger path; it checks the exact amount, transaction timestamp, and unique SlipOK transaction reference before atomically crediting the wallet.
- Enforced the 150 THB minimum, 33.50 THB per credit conversion, 15-minute payment window, image size/type limits, and no-credit behavior for unverified/ambiguous slips.
- Added bank payments to admin top-up history and successful top-up dashboard totals; preserved the existing Binance flow.
- Added environment configuration and setup instructions; recipient account details remain only in ignored local/server `.env` files.
- Live bank payments remain disabled until SlipOK API key and branch ID are configured on the VPS and verified with the matching recipient account.

### Admin web and notifications
- Suppressed Discord purchase and refund notifications for owner/admin Telegram IDs while retaining normal order delivery and status updates.
- Displayed admin timestamps in Thailand time, translated audit actions/details and record statuses, and formatted credit amounts for readability.
- Expired top-up requests automatically in the payment worker and admin top-up page; retained payment matching for transfers timestamped within the original request window.
- Replaced the dashboard's pending top-up card with a count of successfully credited payments.

### Telegram
- Added the Telegram display name beside the user ID in the `/start` and `/menu` home message.
- Reduced purchase-path latency by allowing Telegram to skip loading email bodies during the purchase transaction; the durable worker still loads and delivers them normally.

### Admin web
- Formatted fixed-point unit values in admin tables as readable credit or USDT amounts without changing stored database values.

### Operations
- Changed Discord order events to omit pending notifications, report success only after all email delivery parts complete, and report failed/refunded orders; top-up and order messages now include the Telegram display name and ID.
- Updated `bot-manager.bat` to use a configurable known_hosts file, require strict SSH host-key verification on every action, and explain how to select the Windows profile's known_hosts when launched from a separate runtime.
- Simplified Telegram admin credit adjustments to accept only a Telegram ID and amount, either in one message or as two prompts; positive amounts add credit, negative amounts deduct it, with an automatic audit reason and the existing confirmation/balance guard retained.
- Fixed the VPS `SUPABASE_URL` base to the project origin after the admin login showed a generic auth failure; verified Supabase Auth health/settings return HTTP 200 and email sign-in is enabled.
- Published the admin dashboard at the VPS public IP over HTTPS using Nginx on ports 80/443 and a short-lived IP certificate with Certbot auto-renewal and an Nginx reload hook; kept app port 8001 loopback-only and port 8000 unchanged.
- Verified external HTTP redirects to HTTPS and HTTPS GET returns 200 with a trusted certificate; confirmed the Certbot renewal timer and all bot services are active.
- Completed VPS setup after the owner populated `.env`; initialized Supabase schema and enabled the bot, worker, and web Screen services at boot.
- Set the VPS web URL/allowed-host values to loopback-only operation and verified the login page; documented SSH tunnel access for deployments without a domain.
- Ran the same VPS command sequence as `bot-manager.bat` menu 5: fast-forward pull, locked dependency install, app install, DB initialization, unit enablement, and restart of all services.
- Protected the VPS `.env` with owner-only permissions; preserved the existing trading service on port 8000 while the admin web listens on loopback port 8001.
- Ran the full local suite: 145 passed and six PostgreSQL integration tests skipped because `TEST_DATABASE_URL` was not configured. No real payment or Discord test message was sent.

### Fixed
- Kept Binance transaction IDs up to the API's 256-character limit intact through manual review, wallet ledger references and notification deduplication; added a one-time PostgreSQL migration for existing databases.
- Preserved each login rate-limit bucket's own expiry so unrelated requests cannot clear a longer login window.
- Made database initialization atomic across table creation, RLS enablement and public grant revocation.

### Performance
- Batched email inventory imports, allowed concurrent purchases to share the price read lock, and removed duplicate order completion work and quadratic payment-history accumulation.
- Replaced Telegram summary reads with focused price and stock queries and moved user/email search filtering into SQL.
- Added the versioned PostgreSQL column-width migration and VPS manager to the explicitly allowed source release archive.
- Added a Windows manager action that fast-forward pulls `main`, installs locked dependencies, runs idempotent DB initialization, and restarts all three VPS services over SSH.
- Installed VPS prerequisites, cloned the repository, provisioned Python 3.11 and dependencies, and registered boot units; services remain disabled until the owner supplies `.env` credentials.
- Updated VPS setup instructions to use Git checkout and a Python 3.11 runtime so the Windows `git pull` updater works with the deployment.

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
