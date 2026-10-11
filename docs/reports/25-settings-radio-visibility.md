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

Отдельный локальный preview на `127.0.0.1:19326` загрузил актуальный `src/web/app.css` в изолированный Edge профиль; settings-подобная разметка не содержала owner data. До клика List был выбран с computed background `rgb(42, 37, 66)` / border `rgb(59, 52, 88)`; после клика Cards немедленно получил эти selected colors, List стал прозрачным. Save preview записал `view=cards`, reload восстановил `aria-checked` только для Cards. Снимки:

- До клика: [25-settings-source-before.png](assets/25-settings-source-before.png)
- Сразу после click Cards: [25-settings-source-after-click.png](assets/25-settings-source-after-click.png)
- После Save + reload: [25-settings-source-after-reload.png](assets/25-settings-source-after-reload.png)

Preview доказывает стиль CSS и последовательность состояния в безопасной фикстуре; click handler на рабочей странице и его Save/reload подтверждены отдельным isolated CDP проходом выше. Сервер не перезапускался и не менялся; `/app.css` на :7391 остаётся старым.

Проверки по решению владельца: `browser radio choices apply and persist immediately without a config request` проверяет callback изменения `views.cards.hidden/list.hidden`, `body.dataset.barStyle=cells` + `layoutCells` callback, немедленные ключи `localStorage`, пустой `bodyOf(panel)` и `fetch` call count `0`; новый panel после close/Cancel восстанавливает оба checked значения и показывает текст о Cancel. Settings suite: `50 passed`; полный web gate: `9 suites (272 tests) + 14 checkers`, `WEB CHECK: clean`.

Обратная проба немедленного действия: временно отключил вызов `effects.view(value)`; suite покраснел на `browser radio choices apply and persist immediately without a config request` → `the cards page view appears on the same click` (`actual hidden=true`). Восстановил callback; suite зелёный. Ранее отдельно выполнена обратная проба CSS selected marker (описана ниже).

Попытался проверить текущие `app.js/settings.js/app.css` через CDP Fetch override на :7391 в новом профиле; из-за того, что панель не открылась на source-overridden загрузке, этот прогон не считаю доказательством интеграции и в результаты не включаю. Реальная рабочая страница остаётся старой сборкой без selected styling/instant-apply; изменённые source assets туда не публиковались.

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

Отклонения от входов: без схемы/API изменений; чек-листы БД §17 и API §20 не применимы. Save/reload :7391 ранее проверены в отдельном Edge localStorage profile на старых assets; callback нового source проверен unit regression и source-CSS preview, но не полноценным browser E2E с source `app.js`. Нет разрешения на deployment, поэтому served :7391 остаётся старым.

Открытые вопросы: для E2E проверки нового app.js на браузере требуется безопасный preview с mock API (или отдельный разрешённый deployment); рабочий сервер/профиль не трогались. Для просмотра fix на рабочей странице владельца нужен отдельный deployment/restart с актуальными assets.

Дефекты Nova: нет.
Модель: GPT-6 Luna.
