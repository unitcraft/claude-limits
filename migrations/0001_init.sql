-- 0001_init.sql — the schema of claude-limits, first migration (task T2.3).
--
-- TRANSCRIBED FROM 01.2, NOT RETYPED. Every statement below is the one in the
-- subplan: §3.3 `schema_meta`, §3.4–§3.13 the ten tables, §3.14 `config_history`,
-- §3.17 the three views. The assembly is mechanical on purpose — a CHECK list retyped
-- from memory loses a value silently, and nothing downstream would notice.
--
-- `notification` IS DELIBERATELY ABSENT. 01.2 §3.14 says so in its own words: it
-- arrives by a migration of phase F5, together with `history.notifications_keep_days`,
-- a line in `forget` and its retention. A draft table shipped early is a table the
-- code starts using before its rules exist.
--
-- Applied in ONE transaction with `schema_meta.schema_version` set to 1 (01.2 §5).
-- The runner does that; this file is only the statements.

-- ── 01.2 §3.3 ──────────────────────────────────────────────────

CREATE TABLE schema_meta (
  key   VARCHAR PRIMARY KEY,
  value VARCHAR NOT NULL
);
-- ключи: schema_version, created_at, app_version, duckdb_version, extensions ('core_functions,icu'),
--        app_instance_id (экземпляр, создавший базу), last_opened_by (экземпляр, открывший её последним; §3.1),
--        last_checkpoint_at, last_rollup_day,
--        rollup_tz (IANA-имя пояса свёрток, напр. 'Europe/Moscow')

-- ── 01.2 §3.4 ──────────────────────────────────────────────────

CREATE TABLE folder (
  id             UUID PRIMARY KEY,               -- v7 из приложения
  created_at     TIMESTAMPTZ NOT NULL,           -- служебный набор (конвенция §6)
  updated_at     TIMESTAMPTZ NOT NULL,
  deleted_at     TIMESTAMPTZ,                    -- убрана из конфига или пропала с диска; строка остаётся ради истории
  deleted_reason VARCHAR(32) CHECK (deleted_reason IN ('removed_from_config','not_found','forgotten')),
  created_by     UUID NOT NULL,
  updated_by     UUID NOT NULL,
  path           VARCHAR NOT NULL,               -- нормализованный абсолютный путь: прямые слэши, без хвостового, после раскрытия ~ и переменных
  kind           VARCHAR(32) NOT NULL CHECK (kind IN ('single','parent','empty','missing')),
  source         VARCHAR(32) NOT NULL CHECK (source IN ('config','default','env')),
  first_seen_at  TIMESTAMPTZ NOT NULL,           -- доменные моменты поверх набора: когда впервые/последний раз наблюдали
  last_seen_at   TIMESTAMPTZ NOT NULL,
  CONSTRAINT folder_path_uq UNIQUE (path),
  CONSTRAINT folder_path_ck CHECK (path = trim(path) AND right(path, 1) NOT IN ('/', '\')),
  CONSTRAINT folder_seen_ck CHECK (last_seen_at >= first_seen_at),
  CONSTRAINT folder_deleted_ck CHECK ((deleted_at IS NULL) = (deleted_reason IS NULL))
);

-- ── 01.2 §3.5 ──────────────────────────────────────────────────

CREATE TABLE login_dir (
  id             UUID PRIMARY KEY,
  created_at     TIMESTAMPTZ NOT NULL,           -- служебный набор (конвенция §6)
  updated_at     TIMESTAMPTZ NOT NULL,
  deleted_at     TIMESTAMPTZ,
  deleted_reason VARCHAR(32) CHECK (deleted_reason IN ('removed_from_config','not_found','forgotten')),
  created_by     UUID NOT NULL,
  updated_by     UUID NOT NULL,
  folder_id      UUID NOT NULL REFERENCES folder(id),
  path           VARCHAR NOT NULL,               -- ПДн: содержит имя пользователя ОС (§10); нормализация как у folder.path; у каталога с deleted_at старше rollup_keep_days заменяется на 'deleted:<id>' (§5)
  name           VARCHAR NOT NULL,               -- короткое имя для подписи: nv-lang, dev, dev-wsl
  layout         VARCHAR(32) NOT NULL CHECK (layout IN ('default','config_dir')),  -- .claude.json РЯДОМ или ВНУТРИ
  first_seen_at  TIMESTAMPTZ NOT NULL,
  last_seen_at   TIMESTAMPTZ NOT NULL,
  CONSTRAINT login_dir_path_uq UNIQUE (path),
  CONSTRAINT login_dir_path_ck CHECK (path = trim(path) AND right(path, 1) NOT IN ('/', '\')),
  CONSTRAINT login_dir_seen_ck CHECK (last_seen_at >= first_seen_at),
  CONSTRAINT login_dir_deleted_ck CHECK ((deleted_at IS NULL) = (deleted_reason IS NULL))
);

-- ── 01.2 §3.6 ──────────────────────────────────────────────────

CREATE TABLE account (
  id                UUID PRIMARY KEY,
  created_at        TIMESTAMPTZ NOT NULL,        -- служебный набор (конвенция §6)
  updated_at        TIMESTAMPTZ NOT NULL,
  deleted_at        TIMESTAMPTZ,                 -- только внутри forget (§3.15) до физического удаления
  created_by        UUID NOT NULL,
  updated_by        UUID NOT NULL,
  email             VARCHAR NOT NULL,            -- ПДн (§10); свойство сущности, не внешний ключ
  org_name          VARCHAR,                     -- ПДн (§10); функция — подпись строки учётки
  subscription_type VARCHAR,                     -- .credentials.json: subscriptionType; не ПДн; функция — разбор 429 и размеров окон в логе и CLI, в API не отдаётся
  rate_limit_tier   VARCHAR,                     -- .credentials.json: rateLimitTier; то же
  color_slot        TINYINT NOT NULL,            -- закреплённый цвет серии (план 01.1 §8), не меняется
  first_seen_at     TIMESTAMPTZ NOT NULL,
  last_seen_at      TIMESTAMPTZ NOT NULL,
  CONSTRAINT account_email_uq UNIQUE (email),
  CONSTRAINT account_email_ck CHECK (email = lower(email) AND email = trim(email)),  -- нормализуется до записи
  CONSTRAINT account_seen_ck CHECK (last_seen_at >= first_seen_at)
);

-- ── 01.2 §3.7 ──────────────────────────────────────────────────

CREATE TABLE occupancy (
  id           UUID PRIMARY KEY,
  created_at   TIMESTAMPTZ NOT NULL,             -- служебный набор (конвенция §6); deleted_at не применим — журнал
  updated_at   TIMESTAMPTZ NOT NULL,
  created_by   UUID NOT NULL,
  updated_by   UUID NOT NULL,
  login_dir_id UUID NOT NULL REFERENCES login_dir(id),
  account_id   UUID REFERENCES account(id),      -- NULL = логина нет, либо учётка забыта (§3.15)
  token_state  VARCHAR(32) NOT NULL CHECK (token_state IN ('ok','expired','rejected','none')),
  started_at   TIMESTAMPTZ NOT NULL,
  ended_at     TIMESTAMPTZ,                      -- NULL = текущая запись
  CONSTRAINT occupancy_ended_ck CHECK (ended_at IS NULL OR ended_at >= started_at)
);

-- ── 01.2 §3.8 ──────────────────────────────────────────────────

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

-- ── 01.2 §3.9 ──────────────────────────────────────────────────

CREATE TABLE limit_window (
  id            UUID PRIMARY KEY,
  created_at    TIMESTAMPTZ NOT NULL,            -- служебный набор (конвенция §6)
  updated_at    TIMESTAMPTZ NOT NULL,
  deleted_at    TIMESTAMPTZ,                     -- модель исчезла из ответа: окно закрывается, история остаётся
  created_by    UUID NOT NULL,
  updated_by    UUID NOT NULL,
  account_id    UUID NOT NULL REFERENCES account(id),
  kind          VARCHAR(32) NOT NULL CHECK (kind IN ('session','weekly_all','weekly_scoped')),
  model         VARCHAR,                         -- display_name модели для weekly_scoped, иначе NULL
  first_seen_at TIMESTAMPTZ NOT NULL,
  last_seen_at  TIMESTAMPTZ NOT NULL,
  CONSTRAINT limit_window_account_kind_model_uq UNIQUE (account_id, kind, model),
  CONSTRAINT limit_window_seen_ck CHECK (last_seen_at >= first_seen_at),
  CONSTRAINT limit_window_model_ck CHECK ((kind = 'weekly_scoped') = (model IS NOT NULL))
);

-- ── 01.2 §3.10 ──────────────────────────────────────────────────

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

-- ── 01.2 §3.11 ──────────────────────────────────────────────────

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

-- ── 01.2 §3.12 ──────────────────────────────────────────────────

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

-- ── 01.2 §3.13 ──────────────────────────────────────────────────

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

-- ── 01.2 §3.14 ──────────────────────────────────────────────────

CREATE TABLE config_history (
  id         UUID PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL,               -- служебный набор (конвенция §6); момент сохранения версии
  updated_at TIMESTAMPTZ NOT NULL,
  created_by UUID NOT NULL,
  updated_by UUID NOT NULL,
  source     VARCHAR(32) NOT NULL CHECK (source IN ('ui','widget','file','migration')),
  toml       VARCHAR NOT NULL                    -- полный текст файла ДО записи; access_token заменён на '***'; ПДн (§10)
);

-- ── 01.2 §3.17 ──────────────────────────────────────────────────

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

