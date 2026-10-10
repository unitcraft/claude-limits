# #15 — Независимый аудит настроек через UI

## Результат

Проверен настоящий UI Edge на собственном стенде одобренного бинаря `claude-limits.exe`, отдельном профиле браузера, `127.0.0.1:17439`, private config/data/log dirs и копии синтетической фикстуры `fixtures/dirs/expired`. Конфиг стенда явно содержит `refresh.enabled=false`; наружу через Claude CLI/refresh не ходили. Порт `7391`, пользовательские конфиги/БД и рабочие процессы не тронуты.

Итог по спорным находкам: `Cards`/`Blocks` действительно не переключаются; `countdown` сохраняется только в localStorage и переживает reload; `hide_stale=true` не скрывает просроченный login. Synthetic renderer probe показал, что `time_bar=false` не гасит полосу и после reload, потому что live snapshot DTO не передаёт `config.ui`. Backend audit test показал, что forecast=false игнорируется на первом poll, но учитывается на следующем. Polling и thresholds сохраняются с `restart_required=true`; интервал 120 с вступил в силу после перезапуска своего стенда.

## Сценарии и результаты

| Настройка / действие в UI | HTTP / сохранённое значение | Наблюдение после Save / Cancel / reload / restart | Вердикт |
|---|---|---|---|
| Layout → клик `Cards`; Bar style → клик `Blocks`; Save и reload | UI-only: PUT нет; `localStorage.view="list"`, `bar_style="rounded"` | ARIA остаётся `Cards=false`, `Blocks=false`; после reload выбраны `list` и `rounded`. См. [снимок radio controls](assets/15-settings-top-radio-controls.png). | **Подтверждено: не работает.** Кодовая причина: `src/web/app.js:546-570`, `onPanelClick` обслуживает toggle/day и action, но не `.choice-option`; поэтому aria не меняется и collector сохраняет прежний выбор. `src/web/settings.js:191-203` создаёт radio-кнопки, но обработчика выбора нет. |
| Reset time / countdown: toggle off → Save → reload; затем toggle on → Cancel | PUT отсутствует; после Save `localStorage.countdown="false"` | При повторном открытии после reload `aria-checked=false`; Cancel не меняет сохранённое `false`. | **Подтверждено: работает** (настройка этого браузера, не сервера). Причина: `src/web/settings.js:395-400,412-421`, `src/web/app.js:621-629` отдельно сохраняет browser-only prefs до проверки пустого config diff. |
| Notifications flag / системное разрешение | Не отправлял запрос на разрешение ОС и не считал сохранённый browser-флаг доказательством | Permission prompt и фактическая доставка уведомления не проверялись. | **Не проверено.** |
| `ui.hide_stale=true` на искусственной expired учётке; Save | В частичном PUT ниже; GET `/api/config` подтверждает `true` | Несмотря на `hide_stale=true`, страница продолжила показывать искусственно просроченный login и «token expired». Снимок [сохранённого состояния](assets/15-expired-login-visible-with-hide-stale.png). Поиск `src/web` на чтение `hide_stale` находит настройку только в `settings.js`, не renderer. | **Подтверждено: не действует в UI.** |
| `ui.time_bar=false`; Save и reload | Реальный PUT `/api/config` с `If-Match`, `{ "ui": {"time_bar": false} }` → `200`; GET до и после reload вернул `false` | CDP-only renderer probe подменял только browser responses `/api/snapshot` + `/api/events` synthetic account/limit `40%`, `resets_at=now+1h`; UI отрисовал timebar (2 DOM nodes: list+cards) после Save и reload. См. [снимок после reload](assets/15-timebar-false-after-reload-synthetic.png). **Это synthetic renderer-доказательство, не backend snapshot.** Контрольный CDP fixture с искусственно добавленным `config.ui.time_bar=false` убрал полосы; см. [контрольный снимок](assets/15-timebar-control-config-prop.png). | **Подтверждено: настройка сохранена, но реальная форма snapshot не передаёт `config`, поэтому UI не получает false и рисует полосу.** Причины: `src/server/dto.nv:384-400` сериализует только fetched_at/next_poll_at/tz/restored/worst/accounts/limits; `src/web/app.js:368` читает `snap.config.ui`; без этого `src/web/format.js:123-127` оставляет default `time_bar=true`, которым управляет `src/web/render.js:108`. |
| `forecast.enabled=false`; Save → restart → first/next poll | UI PUT `/api/config` с `{"forecast":{"enabled":false},"thresholds":{"warning":85,"critical":95}}` → `200`, ответ `applied.restart_required=true`; GET после restart сохранил false | Реальный бинарный stand после собственного restart выполнил first poll и следующий tick (health: interval 60, два `last_at` разнесены на 60 с), но **accounts=0/limits=0**: живые usage readings не создавались. Отдельный Nova harness вызывает production `feed.store_and_poll`, `Rounds`, `forecast_join.with_forecasts` на двух local synthetic polls: при file `enabled=false` первый `ConfNow` всё ещё default enabled и даёт forecast; после reread второй round видит false и даёт `forecast=null`. Reverse control с file true даёт forecast на обоих раундах. | **Backend-effect подтверждён harness: первый poll игнорирует false, следующий учитывает false.** Настоящий binary stand без usage не мог показать forecast строку/ghost. |
| Рабочие дни/часы: выбрать Saturday, `08:30–17:30`, off-hours rate `5`; Save при `working_hours=false` | GET `/api/config` вернул эти значения и `working_hours=false` | Панель содержит дни/часы/rate, но переключателя `forecast.working_hours` в ней нет (`src/web/settings.js:275-295`). Расписание не может включить рабочий график; эффект при выключенном флаге не измерялся. | **Сохранение полей подтверждено; включить расписание из UI нельзя.** |
| Polling `60→120`, thresholds `65/85→66/86`; Save | Частичный PUT получил `200`; ответ включал `applied.restart_required=true`; GET подтвердил оба новых значения | После перезапуска только PID своего стенда `/api/health` показал `interval_sec=120`, listener `17439`; последующий health: `last_at=14:03:37Z`, `next_at=14:05:37Z`. Дополнительно thresholds `85/95` сохранены через UI с тем же PUT/restart-required, затем проверены backend harness на тех же bounds и одном synthetic usage 80%. Код: `src/claude_limits.nv:976-977` строит `Rounds` из config thresholds; `src/server/feed.nv:328-335` передаёт bounds в snapshot; `src/model/snapshot.nv:69-73` применяет inclusive warning/critical boundaries. | **Polling подтверждён после restart и следующего тика; backend effect thresholds подтверждён harness: 80% — warning при 70/90, normal при 85/95.** Цветная страница с реальным API usage не наблюдалась. |
| Неверный интервал `30`; Save (негативная проба) | Браузерный `PUT /api/config`, `If-Match` присутствует, тело `{"poll":{"interval_sec":30}}` → `422`. Ответ: `{"type":"urn:claude-limits:problem:invalid-config","title":"Invalid settings","status":422,"code":"invalid_config","errors":[{"field":"poll.interval_sec","code":"invalid_config","message":"minimum is 60 s (the server rate-limits eager polling)"}]}`. | Поле стало красным, серверный текст ошибки показан; значение не сохранено. См. [снимок](assets/15-invalid-interval.png). | **Подтверждено: отказ и отображение ошибки работают.** |
| Login folders: Check synthetic empty dir; добавить; удалить; Cancel | Check: `POST /api/folders/probe` → `200`, UI: `no .credentials.json here`. Add/remove отправили partial PUT с `If-Match` → `200`; GET после add показывал две папки, после удаления — одну. | Список менялся после Save; отдельное удаление с последующим Cancel не записало изменение (конфиг при GET не менялся). | **Подтверждено: probe/add/remove/Cancel.** |
| LAN и Desktop widget | Контролы отображены disabled с объяснением; PUT не отправлялся | Невозможно изменить через эту панель. | **Проверено наличие disabled controls; поведение этих функций не применимо/не проверено.** |

### Частичный PUT и ответы

Сохранение нескольких config-настроек из UI фактически отправило:

```http
PUT /api/config
If-Match: <текущий ETag>
Content-Type: application/json

{"forecast":{"enabled":false},"thresholds":{"warning":65,"critical":85},"ui":{"hide_stale":true,"time_bar":false}}
```

Ответ был `200`; тело содержало конфигурацию с этими значениями и `applied.restart_required=true`. Сетевой CDP trace также зафиксировал отдельные folder PUT и `GET /api/config` с `200`; значения выше перепроверены GET после сохранения и после перезапуска. Адреса private-файлов, ETags и request IDs в репозиторий не включены.

## Независимость стенда и границы проверки

- Открыт `D:/Sources/nv-lang/claude-limits/target/claude-limits.exe` без пересборки. Изолированные stand/profiles: первая серия `17439`/Edge CDP `19339`, вторая `17459`/CDP `19359`; на обеих `refresh.enabled=false`.
- Отдельные `APPDATA`/`LOCALAPPDATA`, plain DB, config, logs и browser profiles располагались в private `$TEMP/opencode/claude-limits-task15-*`. В первой серии скопирована только синтетическая expired fixture; во второй credentials/folders отсутствовали. Все копии/temp удалены после остановки процессов; секреты и пользовательские пути в отчёте не приводятся.
- Health подтвердил `encrypted=false`, `key_store=none`, listeners только на собственных `17439` и `17459`. Обращений к рабочему серверу и реальным credentials не делалось; второй binary stand имел 0 accounts и 0 limits.
- В footer страницы на снимках отображён default `127.0.0.1:7391`, хотя адрес страницы/Settings panel и `/api/health` показывали только стенды `17439` или `17459`. Footer не использовался для адресации запросов; это отдельное расхождение отображения, не проверявшееся в рамках аудита настроек.
- Реальный бинарный snapshot имел 0 limits; поэтому backend forecast нельзя было наблюдать через настоящий binary live reading. Его first/next поведение проверено production-module harness на synthetic polls. `time_bar` проверен отдельно только renderer-путём на synthetic `resets_at`, с явным отличием от live API DTO. Визуальную реакцию bar colors на thresholds и OS notifications не проверяли.

## Проверено

```text
$ node scripts/test-settings.mjs
47 passed

$ node scripts/test-format.mjs
60 passed

$ node scripts/check-web.mjs
9 suites (268 tests) + 14 checkers
WEB CHECK: clean
```

```text
$ NOVA_MAIN_REPO=<sibling nova checkout> bash ./nova.sh test src/server/ui_settings_audit_test.nv
PASS           src/server/ui_settings_audit_test
PASS: 1  FAIL: 0
```

Backend audit test (`src/server/ui_settings_audit_test.nv`) использует production `feed.store_and_poll`, `feed.Rounds`, `feed.one_round`, `model.forecast_join.with_forecasts` и `model.snapshot` severity path. Dirs/Creds/Http effects локальные: в ответе только synthetic JSON, сокет не открывается; refresh выключен. Тест фиксирует: false-config first round — `ConfNow.forecast.enabled=true`/forecast present; next — false/null; control true/true — forecast present на обоих. На одинаковом usage 80% severity = warning при 70/90 и normal при 85/95; 95% при 70/90 = critical. Это исполнение реальных production modules/store с synthetic inputs; не выдаётся за poll настоящего бинаря или реальную БД/handler `forecast_round`.

Причина first-poll: `src/server/feed.nv:434-447` запускает первый `round` до обработки queued Store messages; `src/claude_limits.nv:1000-1022` уже поставил конфигурацию в очередь перед запуском loop, но первый round её ещё не прочёл. Forecast callback использует `ConfNow` каждого раунда (`src/claude_limits.nv:447-490`); `src/model/forecast_join.nv:228-231` возвращает `None` только когда rules реально пришли с `enabled=false`.

Дополнительно выполнен обратный probe: временно инвертировано ожидание first-round flag (`true`→`false`) → test стал красным (`assert failed: disabled_file.enabled[0] == false && disabled_file.forecast[0] == true`); ожидание восстановлено → `PASS: 1 FAIL: 0`. Product code не менялся.

Также вручную повторён UI-проход через Edge CDP: настоящий config GET/Save/PUT/ответ/reload на отдельном binary stand; для лимитной строки и SSE использованы только локальные `Fetch.fulfillRequest` synthetic fixtures. Live `/api/snapshot` на binary возвращал keys `fetched_at,next_poll_at,tz,restored,worst,accounts,limits` без `config`; без папок настоящий snapshot имел 0 accounts/0 limits. Synthetic fixture отдельно помечен и служил только созданию renderer-условий `resets_at`.

## Обратная проба

Radio reverse probe из первого прогона: клик `Cards` → ожидание `aria-checked=true` покраснело (`actual false`); Cancel/reload вернул baseline List → зелёный. Backend reverse probe: ожидание first poll false временно инвертировано → audit test красный; восстановлено → зелёный. Ни одна probe не меняла product code или не ослабляла тесты.

## Сводка шаблона исполнителя

- Сделано: независимая UI-проверка с изолированным браузером/сервером, сетевыми результатами и снимками; найдено неработающее переключение radio и неэффективный `hide_stale`.
- Отклонения от входов: только отчёт и скриншоты; продукт не изменён.
- Схема БД/API-контракт не менялись: чек-листы БД §17 и API §20 не применимы.
- Открытые вопросы: у настоящего binary stand не было live usage/limits (без внешнего read-only usage и credentials), поэтому forecast не наблюдался на настоящих значениях; first/next bug установлен production-module harness. UI не может применить `ui.time_bar=false`, потому что snapshot DTO не содержит `config.ui`. Backend thresholds реально меняют severity в harness; цвет страницы на limits настоящего API не снимался. OS notifications не проверены.
- Дефекты компилятора Nova: не проверялись/не требовались.
- Модель: GPT-6 Luna.
