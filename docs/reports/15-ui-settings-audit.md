# #15 — Независимый аудит настроек через UI

## Результат

Проверен настоящий UI Edge на собственном стенде одобренного бинаря `claude-limits.exe`, отдельном профиле браузера, `127.0.0.1:17439`, private config/data/log dirs и копии синтетической фикстуры `fixtures/dirs/expired`. Конфиг стенда явно содержит `refresh.enabled=false`; наружу через Claude CLI/refresh не ходили. Порт `7391`, пользовательские конфиги/БД и рабочие процессы не тронуты.

Итог по спорным находкам: `Cards`/`Blocks` действительно не переключаются; `countdown` сохраняется только в localStorage и переживает reload; `hide_stale=true` не скрывает просроченный login. `time_bar=false` сохраняется, и код страницы проверяет флаг при отрисовке, но визуальный эффект здесь **не проверен**: искусственно expired login не имеет пригодного `resets_at`. Polling и thresholds сохраняются с `restart_required=true`; интервал 120 с вступил в силу после перезапуска своего стенда. Forecast и расписание персистируются, но прогноз на первом/следующем опросе не проверен: единственный login намеренно expired, refresh выключен, валидных измерений для прогноза нет.

## Сценарии и результаты

| Настройка / действие в UI | HTTP / сохранённое значение | Наблюдение после Save / Cancel / reload / restart | Вердикт |
|---|---|---|---|
| Layout → клик `Cards`; Bar style → клик `Blocks`; Save и reload | UI-only: PUT нет; `localStorage.view="list"`, `bar_style="rounded"` | ARIA остаётся `Cards=false`, `Blocks=false`; после reload выбраны `list` и `rounded`. См. [снимок radio controls](assets/15-settings-top-radio-controls.png). | **Подтверждено: не работает.** Кодовая причина: `src/web/app.js:546-570`, `onPanelClick` обслуживает toggle/day и action, но не `.choice-option`; поэтому aria не меняется и collector сохраняет прежний выбор. `src/web/settings.js:191-203` создаёт radio-кнопки, но обработчика выбора нет. |
| Reset time / countdown: toggle off → Save → reload; затем toggle on → Cancel | PUT отсутствует; после Save `localStorage.countdown="false"` | При повторном открытии после reload `aria-checked=false`; Cancel не меняет сохранённое `false`. | **Подтверждено: работает** (настройка этого браузера, не сервера). Причина: `src/web/settings.js:395-400,412-421`, `src/web/app.js:621-629` отдельно сохраняет browser-only prefs до проверки пустого config diff. |
| Notifications flag / системное разрешение | Не отправлял запрос на разрешение ОС и не считал сохранённый browser-флаг доказательством | Permission prompt и фактическая доставка уведомления не проверялись. | **Не проверено.** |
| `ui.hide_stale=true` на искусственной expired учётке; Save | В частичном PUT ниже; GET `/api/config` подтверждает `true` | Несмотря на `hide_stale=true`, страница продолжила показывать искусственно просроченный login и «token expired». Снимок [сохранённого состояния](assets/15-expired-login-visible-with-hide-stale.png). Поиск `src/web` на чтение `hide_stale` находит настройку только в `settings.js`, не renderer. | **Подтверждено: не действует в UI.** |
| `ui.time_bar=false`; Save | GET `/api/config` вернул `false` | Эффект полосы глазами не проверен: expired-fixture не даёт подходящего `resets_at`. Код имеет явный reader/guard: `src/web/app.js:365-370`, `src/web/render.js:108`. | **Сохранение подтверждено; визуальный эффект не проверен.** Предварительное «не работает» по этому прогону не подтверждено. |
| `forecast.enabled=false`; Save | GET `/api/config` вернул `false`; в ответе сохранения `restart_required=true` | Нельзя оценить первый и следующий расчёт: стенд не получил валидных usage readings, а refresh специально отключён. | **Персистирование подтверждено; поведение первого/следующего опроса не проверено.** |
| Рабочие дни/часы: выбрать Saturday, `08:30–17:30`, off-hours rate `5`; Save при `working_hours=false` | GET `/api/config` вернул эти значения и `working_hours=false` | Панель содержит дни/часы/rate, но переключателя `forecast.working_hours` в ней нет (`src/web/settings.js:275-295`). Расписание не может включить рабочий график; эффект при выключенном флаге не измерялся. | **Сохранение полей подтверждено; включить расписание из UI нельзя.** |
| Polling `60→120`, thresholds `65/85→66/86`; Save | Частичный PUT получил `200`; ответ включал `applied.restart_required=true`; GET подтвердил оба новых значения | После перезапуска только PID своего стенда `/api/health` показал `interval_sec=120`, listener `17439`; последующий health: `last_at=14:03:37Z`, `next_at=14:05:37Z`. Перезапуск и последующий опрос видны в private логе стенда; обновлённые пороги сохранены, но цветовой переход на пригодном usage-векторе не проверялся. | **Polling подтверждён после restart и следующего тика; thresholds подтверждены как сохранённые, визуальная реакция не проверена.** |
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

- Открыт `D:/Sources/nv-lang/claude-limits/target/claude-limits.exe` без пересборки. Отдельный Edge `--headless=new` запущен с собственным `user-data-dir` и CDP-портом `19339`; UI открыт на `17439`.
- Отдельный `APPDATA`/`LOCALAPPDATA`, plain DB, config, logs, temporary folders и browser profile располагались в private каталоге `$TEMP/opencode/claude-limits-task15-own`. Для проверки expired login скопирована только синтетическая фикстура `fixtures/dirs/expired`; токен/секреты и пользовательские пути в отчёте не приводятся.
- Health подтвердил `encrypted=false`, `key_store=none`, listener `127.0.0.1:17439`; config стенда — `refresh.enabled=false`. Обращений к рабочему серверу и реальным credentials не делалось.
- В footer страницы на снимке отображён default `127.0.0.1:7391`, хотя адрес страницы, Settings panel и `/api/health` показывали стенд `17439`. Footer не использовался для адресации запросов; это отдельное расхождение отображения, не проверявшееся в рамках аудита настроек.
- Forecast при первом/следующем цикле, отображение time bar на настоящем `resets_at`, визуальные пороги с данными и OS notifications требуют пригодных данных/разрешения и остаются **не проверены**, а не считаются успешными по одному сохранённому флагу.

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

Также вручную повторён UI-проход через Edge CDP: GET конфигурации → действия в settings panel → фактические request/response → GET/рендер после сохранения; для restart-required — остановлен только PID собственного стенда, он запущен заново, затем проверены health и следующий poll tick. Скриншоты собственного прогона приложены выше.

## Обратная проба

Проверка, которая должна пройти при исправном radio-control: клик `Cards` → `aria-checked=true`. Фактически клик оставил `false`, поэтому ожидаемая UI-проверка покраснела: `RED: expected Cards=true after click, actual false`. После Cancel и reload исходное состояние восстановлено; baseline assertion `List aria-checked=true` прошёл: `GREEN: restored List baseline selected`. Проба не редактировала и не «чинила» продукт; тесты не ослаблялись.

## Сводка шаблона исполнителя

- Сделано: независимая UI-проверка с изолированным браузером/сервером, сетевыми результатами и снимками; найдено неработающее переключение radio и неэффективный `hide_stale`.
- Отклонения от входов: только отчёт и скриншоты; продукт не изменён.
- Схема БД/API-контракт не менялись: чек-листы БД §17 и API §20 не применимы.
- Открытые вопросы: first/next forecast poll, видимая time bar, реальное цветовое действие thresholds, системные notifications — не проверены из-за отсутствия валидного usage на безопасной expired fixture и/или OS permission.
- Дефекты компилятора Nova: не проверялись/не требовались.
- Модель: GPT-6 Luna.
