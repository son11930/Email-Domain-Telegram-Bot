-- Apply once to an existing PostgreSQL database before deploying this release.
-- The payment API accepts transaction IDs up to 256 characters. Derived ledger
-- references and outbox dedupe keys need room for their prefixes as well.
BEGIN;
ALTER TABLE payment_events
    ALTER COLUMN transaction_id TYPE varchar(256);
ALTER TABLE wallet_ledger
    ALTER COLUMN reference TYPE varchar(300);
ALTER TABLE delivery_outbox
    ALTER COLUMN dedupe_key TYPE varchar(300);
COMMIT;
