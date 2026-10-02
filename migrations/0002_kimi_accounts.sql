-- 0002_kimi_accounts.sql — Kimi Code accounts in the history (plan 01.6 П3, 01.2 amendment
-- 2026-10-02, the owner's "3 — да").
--
-- WHAT CHANGES. `account` learns its provider: a Claude account is keyed by its e-mail as
-- before; a Kimi Code account has no e-mail and is keyed by its credentials file's stem
-- (`cred_key`). `limit_window.kind` learns `monthly`, and a monthly window may carry a model
-- ('' for the month's total, 'code' for its Code part), as `weekly_scoped` must.
--
-- WHY A REBUILD AND NOT ALTER (measured 2026-10-02 on the bundled DuckDB 1.5.5, a scratch
-- probe against a seeded 0001): `ADD COLUMN` with a constraint -- "not yet supported";
-- `ALTER COLUMN email DROP NOT NULL` -- "Cannot alter entry "account" because there are
-- entries that depend on it" (the foreign keys); `DROP CONSTRAINT` / `ADD CONSTRAINT` --
-- "No support for that ALTER TABLE option yet"; `RENAME` of a referenced table -- the same
-- dependency error. A CHECK list cannot be widened in place, so the tables that carry the
-- two changed definitions, and every table whose foreign key points at them, are copied
-- out, dropped, created anew and filled back -- in ONE transaction (the runner's), after
-- the backup the start takes before any migration (01.2 §5). A failure rolls the whole
-- thing back; the file is never half-migrated.
--
-- UNCHANGED TABLES ARE TRANSCRIBED FROM 0001, NOT RETYPED: the DDL below for occupancy,
-- poll, window_cycle, sample, lock_period and daily_rollup is 0001's, character for
-- character. `folder`, `login_dir`, `config_history`, `schema_meta` are not touched: no
-- foreign key reaches them.
--
-- The views are dropped and created again with the tables they read; their text is 0001's.
--
-- WHICH PROVIDER GOES WITH WHICH KEY IS HELD BY THE WRITER, NOT BY A CHECK (measured
-- 2026-10-02, a scratch probe of six account shapes on the bundled DuckDB): a CHECK that
-- names the UNIQUE `email` together with another column -- `(provider = 'claude') =
-- (email IS NOT NULL)` -- turns `INSERT ... ON CONFLICT (email) DO UPDATE` into a delete
-- and an insert, and the second tick of an account dies on "Violates foreign key
-- constraint ... still referenced" (DuckDB's over-eager constraint checking). A CHECK on
-- one column, or on columns no index covers, does not. So each key column checks only
-- itself, and `storage/repo.nv` (`upsert_account_sql`) writes the triple (provider,
-- email, cred_key) from one decision, under a test.

-- ── copy out ──────────────────────────────────────────────────────

CREATE TEMP TABLE m2_account      AS SELECT * FROM account;
CREATE TEMP TABLE m2_occupancy    AS SELECT * FROM occupancy;
CREATE TEMP TABLE m2_poll         AS SELECT * FROM poll;
CREATE TEMP TABLE m2_limit_window AS SELECT * FROM limit_window;
CREATE TEMP TABLE m2_window_cycle AS SELECT * FROM window_cycle;
CREATE TEMP TABLE m2_sample       AS SELECT * FROM sample;
CREATE TEMP TABLE m2_lock_period  AS SELECT * FROM lock_period;
CREATE TEMP TABLE m2_daily_rollup AS SELECT * FROM daily_rollup;

-- ── drop, dependents first ────────────────────────────────────────

DROP VIEW v_current_occupancy;
DROP VIEW v_latest_sample;
DROP VIEW v_sample_local;

DROP TABLE daily_rollup;
DROP TABLE lock_period;
DROP TABLE sample;
DROP TABLE window_cycle;
DROP TABLE limit_window;
DROP TABLE poll;
DROP TABLE occupancy;
DROP TABLE account;

-- ── 01.2 §3.6, amendment 2026-10-02 ───────────────────────────────

CREATE TABLE account (
  id                UUID PRIMARY KEY,
  created_at        TIMESTAMPTZ NOT NULL,        -- служебный набор (конвенция §6)
  updated_at        TIMESTAMPTZ NOT NULL,
  deleted_at        TIMESTAMPTZ,                 -- только внутри forget (§3.15) до физического удаления
  created_by        UUID NOT NULL,
  updated_by        UUID NOT NULL,
  provider          VARCHAR(32) NOT NULL CHECK (provider IN ('claude','kimi')),  -- чей это логин (поправка 2026-10-02)
  email             VARCHAR,                     -- ПДн (§10); свойство сущности, не внешний ключ; у Kimi нет (NULL)
  cred_key          VARCHAR,                     -- Kimi: имя файла кредов без .json — ключ учётки, у которой почты нет; у Claude NULL
  org_name          VARCHAR,                     -- ПДн (§10); функция — подпись строки учётки
  subscription_type VARCHAR,                     -- .credentials.json: subscriptionType; не ПДн; функция — разбор 429 и размеров окон в логе и CLI, в API не отдаётся
  rate_limit_tier   VARCHAR,                     -- .credentials.json: rateLimitTier; то же
  color_slot        TINYINT NOT NULL,            -- закреплённый цвет серии (план 01.1 §8), не меняется
  first_seen_at     TIMESTAMPTZ NOT NULL,
  last_seen_at      TIMESTAMPTZ NOT NULL,
  CONSTRAINT account_email_uq UNIQUE (email),
  CONSTRAINT account_cred_key_uq UNIQUE (cred_key),
  CONSTRAINT account_email_ck CHECK (email = lower(email) AND email = trim(email)),  -- нормализуется до записи
  CONSTRAINT account_cred_key_ck CHECK (cred_key = trim(cred_key) AND cred_key <> ''),  -- связь provider↔ключ держит код записи (шапка файла)
  CONSTRAINT account_seen_ck CHECK (last_seen_at >= first_seen_at)
);

-- ── 01.2 §3.7 (0001) ──────────────────────────────────────────────

CREATE TABLE occupancy (
  id           UUID PRIMARY KEY,
  created_at   TIMESTAMPTZ NOT NULL,             -- служебный набор (конвенция §6); deleted_at не применим — журнал
  updated_at   TIMESTAMPTZ NOT NULL,
  created_by   UUID NOT NULL,
  updated_by   UUID NOT NULL,
  login_dir_id UUID NOT NULL,                    -- → login_dir(id); БЕЗ REFERENCES по той же причине, что folder_id у login_dir (01.5 вопрос 7)
  account_id   UUID REFERENCES account(id),      -- NULL = логина нет, либо учётка забыта (§3.15)
  token_state  VARCHAR(32) NOT NULL CHECK (token_state IN ('ok','expired','rejected','none')),
  started_at   TIMESTAMPTZ NOT NULL,
  ended_at     TIMESTAMPTZ,                      -- NULL = текущая запись
  CONSTRAINT occupancy_ended_ck CHECK (ended_at IS NULL OR ended_at >= started_at)
);

-- ── 01.2 §3.8 (0001) ──────────────────────────────────────────────

CREATE TABLE poll (
  id              UUID PRIMARY KEY,
  created_at      TIMESTAMPTZ NOT NULL,          -- служебный набор (конвенция §6); deleted_at не применим — журнал
  updated_at      TIMESTAMPTZ NOT NULL,
  created_by      UUID NOT NULL,
  updated_by      UUID NOT NULL,
  account_id      UUID NOT NULL REFERENCES account(id),
  polled_at       TIMESTAMPTZ NOT NULL,
  outcome         VARCHAR(32) NOT NULL CHECK (outcome IN ('ok','http_401','http_429','http_5xx','http_other','network','parse','skipped_expired','skipped_backoff')),
  http_status     SMALLINT,
  retry_after_sec INTEGER,                       -- из Retry-After при 429
  latency_ms      INTEGER,
  error           VARCHAR,                       -- ≤ 200 символов, без токенов и заголовков (§6)
  CONSTRAINT poll_account_polled_uq UNIQUE (account_id, polled_at)  -- естественный ключ факта (конвенция §3.1)
);

-- ── 01.2 §3.9, amendment 2026-10-02 ───────────────────────────────

CREATE TABLE limit_window (
  id            UUID PRIMARY KEY,
  created_at    TIMESTAMPTZ NOT NULL,            -- служебный набор (конвенция §6)
  updated_at    TIMESTAMPTZ NOT NULL,
  deleted_at    TIMESTAMPTZ,                     -- модель исчезла из ответа: окно закрывается, история остаётся
  created_by    UUID NOT NULL,
  updated_by    UUID NOT NULL,
  account_id    UUID NOT NULL REFERENCES account(id),
  kind          VARCHAR(32) NOT NULL CHECK (kind IN ('session','weekly_all','weekly_scoped','monthly')),
  model         VARCHAR NOT NULL DEFAULT '',     -- display_name модели для weekly_scoped; у monthly '' (весь месяц) или 'code'; иначе '' (НЕ NULL: UNIQUE считает NULL-ы различными, и окно без модели удваивалось на каждом тике -- замер 2026-09-30)
  first_seen_at TIMESTAMPTZ NOT NULL,
  last_seen_at  TIMESTAMPTZ NOT NULL,
  CONSTRAINT limit_window_account_kind_model_uq UNIQUE (account_id, kind, model),
  CONSTRAINT limit_window_seen_ck CHECK (last_seen_at >= first_seen_at),
  CONSTRAINT limit_window_model_ck CHECK ((kind <> 'weekly_scoped' OR model <> '') AND (kind IN ('weekly_scoped','monthly') OR model = ''))
);

-- ── 01.2 §3.10 (0001) ─────────────────────────────────────────────

CREATE TABLE window_cycle (
  id         UUID PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL,               -- служебный набор (конвенция §6); deleted_at не применим
  updated_at TIMESTAMPTZ NOT NULL,
  created_by UUID NOT NULL,
  updated_by UUID NOT NULL,
  window_id  UUID NOT NULL REFERENCES limit_window(id),
  starts_at  TIMESTAMPTZ NOT NULL,               -- resets_at − длина окна (5 ч / 7 сут)
  resets_at  TIMESTAMPTZ NOT NULL,
  CONSTRAINT window_cycle_window_resets_uq UNIQUE (window_id, resets_at),
  CONSTRAINT window_cycle_order_ck CHECK (resets_at > starts_at)
);

-- ── 01.2 §3.11 (0001) ─────────────────────────────────────────────

CREATE TABLE sample (
  id              UUID PRIMARY KEY,              -- v7 (конвенция §3.1: единый вид ключа и у фактов)
  created_at      TIMESTAMPTZ NOT NULL,          -- служебный набор (конвенция §6); deleted_at не применим — факт
  updated_at      TIMESTAMPTZ NOT NULL,
  created_by      UUID NOT NULL,
  updated_by      UUID NOT NULL,
  window_id       UUID NOT NULL REFERENCES limit_window(id),
  sampled_at      TIMESTAMPTZ NOT NULL,          -- время опроса (poll.polled_at)
  cycle_id        UUID NOT NULL REFERENCES window_cycle(id),
  percent         TINYINT NOT NULL,
  locked          BOOLEAN NOT NULL DEFAULT false,
  locked_reason   VARCHAR,
  server_severity VARCHAR,                       -- severity, как его назвал эндпоинт; наша — по порогам
  active          BOOLEAN,                       -- limits[].is_active эндпоинта: это окно сейчас ограничивает; без is_ (конвенция §9)
  CONSTRAINT sample_window_sampled_uq UNIQUE (window_id, sampled_at),  -- естественный ключ факта; по нему идут идемпотентные вставки
  CONSTRAINT sample_percent_ck CHECK (percent BETWEEN 0 AND 100)
);

-- ── 01.2 §3.12 (0001) ─────────────────────────────────────────────

CREATE TABLE lock_period (
  id         UUID PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL,               -- служебный набор (конвенция §6); deleted_at не применим
  updated_at TIMESTAMPTZ NOT NULL,
  created_by UUID NOT NULL,
  updated_by UUID NOT NULL,
  window_id  UUID NOT NULL REFERENCES limit_window(id),
  cycle_id   UUID NOT NULL REFERENCES window_cycle(id),
  started_at TIMESTAMPTZ NOT NULL,               -- первый замер с locked
  ended_at   TIMESTAMPTZ,                        -- первый замер без locked после; NULL = идёт сейчас
  reason     VARCHAR(32) NOT NULL CHECK (reason IN ('server','percent_100')),  -- список lock_reason (§3.2); текст сервера — в sample.locked_reason тех же замеров
  CONSTRAINT lock_period_ended_ck CHECK (ended_at IS NULL OR ended_at >= started_at)
);

-- ── 01.2 §3.13 (0001) ─────────────────────────────────────────────

CREATE TABLE daily_rollup (
  id             UUID PRIMARY KEY,
  created_at     TIMESTAMPTZ NOT NULL,           -- служебный набор (конвенция §6); deleted_at не применим
  updated_at     TIMESTAMPTZ NOT NULL,
  created_by     UUID NOT NULL,
  updated_by     UUID NOT NULL,
  window_id      UUID NOT NULL REFERENCES limit_window(id),
  day_on         DATE NOT NULL,                  -- календарный день в поясе schema_meta.rollup_tz
  samples        INTEGER NOT NULL,
  peak_percent   TINYINT NOT NULL,
  avg_percent    DECIMAL(5,2) NOT NULL,
  locked_sec     INTEGER NOT NULL DEFAULT 0,     -- длительность с единицей в имени (конвенция §5, §9)
  resets         INTEGER NOT NULL DEFAULT 0,     -- сколько раз окно сбрасывалось за день
  CONSTRAINT daily_rollup_window_day_uq UNIQUE (window_id, day_on),
  CONSTRAINT daily_rollup_percent_ck CHECK (peak_percent BETWEEN 0 AND 100 AND avg_percent BETWEEN 0 AND 100)
);

-- ── fill back: every 0001 account was a Claude account ────────────

INSERT INTO account (id, created_at, updated_at, deleted_at, created_by, updated_by, provider, email, cred_key,
                     org_name, subscription_type, rate_limit_tier, color_slot, first_seen_at, last_seen_at)
  SELECT id, created_at, updated_at, deleted_at, created_by, updated_by, 'claude', email, NULL,
         org_name, subscription_type, rate_limit_tier, color_slot, first_seen_at, last_seen_at
  FROM m2_account;
INSERT INTO occupancy    SELECT * FROM m2_occupancy;
INSERT INTO poll         SELECT * FROM m2_poll;
INSERT INTO limit_window SELECT * FROM m2_limit_window;
INSERT INTO window_cycle SELECT * FROM m2_window_cycle;
INSERT INTO sample       SELECT * FROM m2_sample;
INSERT INTO lock_period  SELECT * FROM m2_lock_period;
INSERT INTO daily_rollup SELECT * FROM m2_daily_rollup;

DROP TABLE m2_account;
DROP TABLE m2_occupancy;
DROP TABLE m2_poll;
DROP TABLE m2_limit_window;
DROP TABLE m2_window_cycle;
DROP TABLE m2_sample;
DROP TABLE m2_lock_period;
DROP TABLE m2_daily_rollup;

-- ── 01.2 §3.17 (0001) ─────────────────────────────────────────────

CREATE VIEW v_current_occupancy AS
  SELECT ld.path AS dir, ld.name, a.email, o.token_state, o.started_at
  FROM occupancy o JOIN login_dir ld ON ld.id = o.login_dir_id
  LEFT JOIN account a ON a.id = o.account_id
  WHERE o.ended_at IS NULL AND ld.deleted_at IS NULL;

CREATE VIEW v_latest_sample AS
  SELECT s.* FROM sample s JOIN limit_window w ON w.id = s.window_id
  WHERE w.deleted_at IS NULL                     -- текущее состояние: закрытые окна не участвуют (конвенция §8)
  QUALIFY row_number() OVER (PARTITION BY s.window_id ORDER BY s.sampled_at DESC) = 1;

-- время в поясе машины для отладки в CLI duckdb (в приложении не используется)
CREATE VIEW v_sample_local AS
  SELECT a.email, w.kind, w.model, s.percent, s.locked,
         s.sampled_at AT TIME ZONE (SELECT value FROM schema_meta WHERE key = 'rollup_tz') AS sampled_local,
         c.resets_at  AT TIME ZONE (SELECT value FROM schema_meta WHERE key = 'rollup_tz') AS resets_local
  FROM sample s JOIN limit_window w ON w.id = s.window_id
  JOIN account a ON a.id = w.account_id JOIN window_cycle c ON c.id = s.cycle_id;
