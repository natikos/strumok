-- Issue #159: idempotency for reminder dispatch, so a reminder trigger that
-- fires more than once for the same period/variant (an external cron
-- retrying, or two overlapping runs) never double-sends.
CREATE TABLE IF NOT EXISTS reminder_dispatches (
    id serial PRIMARY KEY,
    period text NOT NULL,
    variant text NOT NULL,
    started_at timestamp NOT NULL,
    finished_at timestamp,
    sent integer NOT NULL DEFAULT 0,
    removed integer NOT NULL DEFAULT 0,
    CONSTRAINT uq_reminder_dispatch_period_variant UNIQUE (period, variant)
);

CREATE TABLE IF NOT EXISTS notification_log (
    id serial PRIMARY KEY,
    user_id integer NOT NULL REFERENCES users (id),
    period text NOT NULL,
    variant text NOT NULL,
    channel text NOT NULL DEFAULT 'push',
    status text NOT NULL DEFAULT 'sent',
    sent_at timestamp NOT NULL,
    CONSTRAINT uq_notification_log_user_period_variant_channel
        UNIQUE (user_id, period, variant, channel)
);

CREATE INDEX IF NOT EXISTS ix_notification_log_user_id ON notification_log (user_id);
