# #16 — Исправление подтверждённых дефектов настроек UI

Сделано: радио-кнопки Layout и Bar style теперь переключают `aria-checked`; Save сохраняет browser preferences, применяет Cards/List и Rounded/Blocks сразу, а выбор восстанавливается из localStorage после reload. `time_bar` читается из настоящего `GET /api/config` при старте и после сохранения; renderer больше не ожидает `config` в snapshot, а легенда согласована с отображаемой полосой. `hide_stale` применяется в `/api/snapshot` и стартовом/round SSE snapshot: stale/error аккаунты и их лимиты исключаются.

Причины сверены с финальным `docs/reports/15-ui-settings-audit.md`: §сценарии 1, 4, 5 (radio collector не получал click; hide_stale отсутствовал в фактической выдаче; production snapshot не имел `config.ui`). Countdown подтверждён рабочим, forecast first-poll оставлен вне задачи: отчёт не подтверждает их как дефекты UI для этого scope.

Проверено:

```text
$ node scripts/test-settings.mjs
48 passed

$ node scripts/test-format.mjs
61 passed

$ node scripts/test-render.mjs
42 passed

$ node scripts/check-web.mjs
9 suites (270 tests) + 14 checkers
WEB CHECK: clean

$ NOVA_MAIN_REPO=D:\Sources\nv-lang\nova python scripts/nova_run.py test src/server/handlers/snapshot_test.nv
PASS src/server/handlers/snapshot_test
PASS: 1  FAIL: 0

$ NOVA_MAIN_REPO=D:\Sources\nv-lang\nova python scripts/nova_run.py test src/server/
PASS: 21  FAIL: 0  SKIP: 19 (compiled OK; no test blocks)

$ NOVA_MAIN_REPO=D:\Sources\nv-lang\nova python scripts/nova_run.py test src/
PASS: 68  FAIL: 0  SKIP: 63 (compiled OK)

$ python scripts/check-guards-judge-this-tree.py
GUARDS JUDGE THIS TREE: clean

$ NOVA_MAIN_REPO=D:\Sources\nv-lang\nova python scripts/check-no-shared-compiler.py
SHARED COMPILER: clean

$ python scripts/check-no-hidden-index-bits.py
ok: every file is plain `H` -- `git status` sees all of them

$ git diff --check
clean
```

Обратная проба: временно ожидал `aria-checked=false` после выбора Cards; `node scripts/test-settings.mjs` покраснел на проверке `true !== false`. Вернул корректное ожидание `true`; тот же тест прошёл (48 passed). Snapshot test содержит и позитивный hide_stale endpoint probe (stale/error исключаются вместе с лимитами), и default-off контроль (stale остаётся видимым).

Отклонения от входов: не добавлял `config` к snapshot wire DTO, поскольку production snapshot contract намеренно его не содержит; настройки UI берутся через действующий config endpoint. Не добавлял схему/поля API. Чек-листы БД §17 и API §20 не применимы: схема и API-контракт не менялись; hide_stale реализован в существующей выдаче, `GET /api/config` остаётся существующим способом получения `time_bar`.

Открытые вопросы: нет. Внешний production UI/live account запрос не выполнялся; проверены production handler route с synthetic stale/ok/error account DTO и реальный web config response shape.

Дефекты Nova: нет.

Модель: GPT-6 Luna.
