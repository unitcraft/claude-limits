# Задача #5 — /api/health из живого состояния и версия
Сделано: `health_at` (src/server/start.nv) больше не собирается один раз при старте: на каждый запрос берёт часы (uptime от `started_at`), последний/следующий опрос из вида хранилища (`fetched_at`/`next_poll_at`), число аккаунтов по состояниям ok/stale/unknown/error (скрытые из `ui.hidden_accounts` — отдельно в `hidden`, `total` = все аккаунты любых провайдеров), число папок-логинов (уникальные пути dirs), `history_days` из базы (новый запрос `read_history_days` в history_read.nv, обёртка `read_history_days_in` в startup.nv, `history_days_from_db` в claude_limits.nv; база недоступна → 0 и строка в лог). Версия: единый источник `src/version.nv`, значение 0.1.0; `--version`, справка и `app_version` берут её оттуда (страница версию не показывает). Форма ответа и OpenAPI не менялись.
Проверено (команды через crew_watch machine:true, `NOVA_MAIN_REPO=D:/Sources/nv-lang/nova ./nova.sh test <файл>`):
  src/server/start_test.nv · handlers/health_test.nv · app_test.nv · version_test.nv · storage/history_read_live_test.nv · serde_parity_test.nv
  → у каждого `PASS: 1  FAIL: 0`
  $ node scripts/check-web.mjs → `8 suites (248 tests) + 14 checkers · WEB CHECK: clean`
  $ python scripts/check-*.py (17 штук) → все ok, `GUARDS JUDGE THIS TREE: clean`
  Живой прогон (свой worktree, порт 7399, временные CLAUDE_LIMITS_DATA и конфиг; 7391 и основной exe не тронуты):
  `claude-limits --version` → `claude-limits 0.1.0`; `GET /api/health` → `app_version":"0.1.0"`, `uptime_sec":14`, затем `18`, `poll.last_at/next_at` заполнены, `schema_version":3`, `history_days":0`. `accounts.total` 0 — во временном конфиге нет папок; живые числа по трём аккаунтам покрыты тестом ниже.
Новые тесты: start_test — health с 3 аккаунтами (ok/stale/error), опросом и 17 днями отдаёт 750 с uptime, 3/1/1/0/1/0, 4 папки, 17 дней; скрытый аккаунт считается в hidden, не в состоянии; до первого опроса poll пустой, uptime не отрицательный; версия 0.1.0; через `sources_at_start`/роутер (как в `--serve`) в теле 3 аккаунта, `history_days:9`, `last_at`/`next_at`. history_read_live_test — на живой базе один день замеров = `days=1`, день сводки + день замеров = `days=2`. version_test — 0.1.0, не 0.0.0.
Обратная проба: в `health_now` подставил пустой вид, `[]` и `0` вместо живых данных → `RUN-FAIL start_test: the router a start builds reports the live counts and the days of the history — start_test.nv:182: assert failed: w.contains("accounts":{"total":3,…})` → вернул → `PASS: 1  FAIL: 0`.
Тесты не ослаблены: изменён только вызов `health_at` (новый параметр) и ожидание версии 0.0.0 → 0.1.0 в version_test, по заданию.
Отклонения от входов: нет. План 01.3 §3.2 и код по форме совпадают. Решение, которого в плане нет: hidden не входит в ok/stale/…, чтобы `total` = сумма пяти счётчиков, как в примере плана. `sse_clients` остаётся 0 (хранилище числа подписчиков не отдаёт; не в задаче).
Конвенции: схему БД не менялась (только чтение, `SELECT`), контракт API не менялся — чек-листы §17/§20 не применимы.
Замечание: первый запуск version_test дал CC-FAIL `duckdb.h not found` на холодной сборке зависимости; повторный запуск зелёный (дважды). `nova.toml` `version = "0.0.0"` (пакет) не трогал.
Открытые вопросы: нет
Дефекты Nova: нет
Модель: sonnet
