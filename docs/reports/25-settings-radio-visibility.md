# #25 — Видимость выбора настроек

Сделано: добавлены theme-consistent selected/hover/keyboard-focus/disabled состояния для radio Layout и Bar style. Выбранное значение применяется на click: Layout меняет показанную страницу через `showView`, Bar style обновляет `body[data-bar-style]` и вызывает `layoutCells`, оба сразу пишут только browser preference в localStorage; config PUT не выполняется. Save остаётся для server config и прочих browser settings. Подпись View поясняет немедленное сохранение и что Cancel не отменяет эти изменения.

## Проверено

```text
$ node scripts/test-settings.mjs
50 passed

$ node scripts/check-web.mjs
9 suites (272 tests) + 14 checkers
WEB CHECK: clean

$ git diff --check
clean (только предупреждения Git о LF→CRLF при следующей записи)
```

Source/served asset probe (read-only):

```text
GET http://127.0.0.1:7391/app.css → HTTP 200, 28846 bytes
served has .choice-option[aria-checked="true"]: false
served has .toggle[aria-checked="true"]: true
current src/web/app.css has .choice-option[aria-checked="true"]: true
current main (be614): app.js handles .choice-option click; app.css has no selected radio marker
```

Проверка в отдельном headless Edge профиле `--user-data-dir=...edge-task25`, `--disable-sync`, `--no-first-run`, CDP 19325. Профиль владельца не открывался. На настоящем UI :7391 (read-only server, никакого config PUT): исходно `view=list`/`bar_style` отсутствовал; клик Cards немедленно выставил `aria-checked=true`, но вычисленный background List и Cards оставался одинаковым `rgb(240, 240, 240)` (браузерная кнопка по умолчанию), border обоих чёрный. Снимок подтвердил визуально неразличимые radio. После Save изолированный профиль получил `localStorage.view=cards`, `bar_style=rounded`; после reload Settings снова показал Cards `aria-checked=true`, значения сохранились. Это подтверждает: click и Save/reload работают на served UI, а визуальный CSS marker в served assets отсутствует. Скриншот рабочей страницы не добавлен в репозиторий, так как за Settings видны личные аккаунты; просмотрен только локально.

Отдельный CSS-only preview на `127.0.0.1:19326` загрузил актуальный `src/web/app.css` в изолированный Edge профиль; он проверял только selected styling, не приложение и не настоящий Save flow. До клика List был выбран с computed background `rgb(42, 37, 66)` / border `rgb(59, 52, 88)`; после клика Cards немедленно получил эти selected colors, List стал прозрачным. Его снимки:

- До клика: [25-settings-source-before.png](assets/25-settings-source-before.png)
- Сразу после click Cards: [25-settings-source-after-click.png](assets/25-settings-source-after-click.png)
- После Save + reload: [25-settings-source-after-reload.png](assets/25-settings-source-after-reload.png)

CSS-only preview доказывает только selected style. Ниже добавлен отдельный end-to-end source preview с настоящими файлами приложения и mock API.

Проверки по решению владельца: `browser radio choices apply and persist immediately without a config request` проверяет callback изменения `views.cards.hidden/list.hidden`, `body.dataset.barStyle=cells` + `layoutCells` callback, немедленные ключи `localStorage`, пустой `bodyOf(panel)` и `fetch` call count `0`; новый panel после close/Cancel восстанавливает оба checked значения и показывает текст о Cancel. Settings suite: `50 passed`; полный web gate: `9 suites (272 tests) + 14 checkers`, `WEB CHECK: clean`.

Обратная проба немедленного действия: временно отключил вызов `effects.view(value)`; suite покраснел на `browser radio choices apply and persist immediately without a config request` → `the cards page view appears on the same click` (`actual hidden=true`). Восстановил callback; suite зелёный. Ранее отдельно выполнена обратная проба CSS selected marker (описана ниже).

### Isolated preview текущего приложения + mock API

Запущен приватный временный Node HTTP server `127.0.0.1:19331` из Temp: статические файлы читались напрямую из `src/web/` текущего worktree, mock API отдавал только synthetic `fixtures/api/config.json` и `snapshot-mixed.json`, health и пустой SSE. Свежий Edge profile без Sync (`--disable-sync`, `--no-first-run`), CDP `19332`; :7391/профиль владельца не использовались. Server фиксировал method/path; CDP `Network.responseReceived` + `Network.getResponseBody` использовались для хеш-проверки asset responses. Статические response bytes SHA-256 совпали с bytes текущих файлов worktree; исходники в git HEAD `4d09fb0` семантически совпадают после нормализации CRLF (`git diff --exit-code 4d09fb0 HEAD -- src/web/...` — exit 0).

| HTTP/CDP source asset | SHA-256(response bytes) = worktree file bytes |
|---|---|
| `index.html` | `b182bc02b1920d45827206f4c3b5fd545a2f971674a7286c6f14f69d87fc61c4` |
| `app.js` | `a523f96cac1416b099cffabbb37bf9dcd67725efabbd472abeeafa323241dc34` |
| `settings.js` | `f3984e778d0a15b6f3e71a064721a05123061428baeec3b9c98bdd9252c21d24` |
| `render.js` | `8ce2a26bbb19738de9043d3024c154e995f4c1ce9041c2a2c2feb70878c2db3b` |
| `format.js` | `5b6373342caa570b85f6771036507d56829901af05a77901c8a85802a3802e53` |
| `app.css` | `1236b79175e06e146c28c77adf876cf91a7a8588f250561e4013b304200cb27c` |

CDP сценарий открыл Settings и проверил:

```text
before: localStorage view absent, bar_style absent; List/Rounded selected; list view visible
click Cards: aria [false,true], localStorage view=cards, list.hidden=true, cards.hidden=false (before Save)
click Blocks: aria [false,true], localStorage bar_style=blocks, body.dataset.barStyle=cells;
             visible .bar border-radius=0px, width=448px (before Save)
click List then Rounded: aria [true,false] for each group, localStorage view=list/bar_style=rounded,
             list view visible, body style reset, visible .bar radius=3px (before Save)
Cancel: panel closed; List/Rounded and their page effects remain applied
reopen: List and Rounded aria-checked=true
Save with no config edits: panel closed; no non-GET /api/config request
reload: localStorage view=list, bar_style=rounded; List view visible, body style reset,
        visible .bar radius=3px; reopened Settings still selects List and Rounded
CDP API requests: GET only (config/snapshot/health/events); zero non-GET requests
mock API request log: zero PUT/POST
```

Скриншоты текущего source приложения, с полностью synthetic example accounts:

- Перед click: [25-node-source-before.png](assets/25-node-source-before.png)
- Сразу после Cards click: [25-node-source-after-cards.png](assets/25-node-source-after-cards.png)
- Сразу после Blocks click (segmented bars уже применены): [25-node-source-after-blocks.png](assets/25-node-source-after-blocks.png)
- Сразу после List + Rounded click (обратное переключение до Save): [25-node-source-after-list-rounded.png](assets/25-node-source-after-list-rounded.png)
- После Cancel и повторного открытия: [25-node-source-after-cancel-reopen.png](assets/25-node-source-after-cancel-reopen.png)
- После reload: [25-node-source-after-reload.png](assets/25-node-source-after-reload.png)

Рабочая страница :7391 остаётся старой сборкой без selected styling/instant-apply; изменённые assets туда не публиковались. Сервер не перезапускался и не менялся.

## Краткая матрица остальных контролов

Сводка по текущему коду и аудиту `docs/reports/15-ui-settings-audit.md`; не все функции повторно проверялись в этой задаче:

| Контрол | Ожидаемое/известное поведение |
|---|---|
| Reset time / countdown | Browser-only localStorage через Save; применяется этому браузеру после перезагрузки, не серверная настройка. |
| Notifications | Флаг browser-only; фактическая доставка и разрешение ОС не проверены. «Allow notifications» отдельно вызывает запрос разрешения. |
| Hide expired logins | Сохраняется в config, но аудит #15 подтвердил, что expired login всё равно виден — текущий UI эффект не работает. |
| Time elapsed strip | Сохраняется; аудит #15: snapshot API не передаёт `config.ui`, поэтому false не отключает полосу в отрисованной странице. |
| Forecast | Сохраняется; restart-required, а аудит #15 обнаружил, что false игнорируется на первом poll и применяется на следующем. |
| Working days/hours/off-hours rate | Поля расписания сохраняются, но UI не показывает `forecast.working_hours` toggle, поэтому включить режим из панели нельзя. |
| Poll interval / thresholds | Сохраняются с `restart_required=true`; interval применяется после рестарта. |
| LAN / Desktop widget | Disabled с пояснением; это пока неактивные возможности. |

Обратная проба selected CSS: временно заменил selector выбранного варианта на `[aria-checked="false"]`; тест покраснел («selected radio must use the theme active surface»); вернул `[aria-checked="true"]`. Обратная проба немедленного применения: временно отключил `effects.view(value)`; тест покраснел на `the cards page view appears on the same click`; восстановил callback. Финальные результаты — settings `50 passed`, общий web gate `272 tests + 14 checkers`, clean.

Отклонения от входов: без схемы/API изменений; чек-листы БД §17 и API §20 не применимы. Save/reload ранее также проверялись на :7391 в отдельном Edge profile со старыми assets. Новый source app.js/settings.js/app.css теперь полноценно проверен в isolated Edge с mock API. Нет разрешения на deployment, поэтому served :7391 остаётся старым.

Открытые вопросы: для просмотра fix на рабочей странице владельца нужен отдельный deployment/restart с актуальными assets; в рамках задачи он не разрешён.

Дефекты Nova: нет.
Модель: GPT-6 Luna.
