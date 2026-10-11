# #25 — Видимость выбора настроек

Сделано: добавлен явный theme-consistent selected state для radio выбора Layout и Bar style, hover, keyboard focus и disabled state. `app.js` уже делал делегированный клик (`selectChoice`) и немедленно обновлял `aria-checked`; CSS не имел ни одного правила для `.choice-option[aria-checked="true"]`, поэтому native button выглядел белым и неизменным. Выбор сохраняется в `localStorage` только по Save; после сохранения renderer читает `view`/`bar_style`.

## Проверено

```text
$ node scripts/test-settings.mjs
49 passed

$ node scripts/check-web.mjs
9 suites (271 tests) + 14 checkers
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

## Краткая матрица остальных контролов

Сводка по текущему коду и аудиту `docs/reports/15-ui-settings-audit.md`; не все функции повторно проверялись в этой задаче:

| Контрол | Ожидаемое/известное поведение |
|---|---|
| Reset time / countdown | Browser-only localStorage, Save; применяется этому браузеру после перезагрузки, не серверная настройка. |
| Notifications | Флаг browser-only; фактическая доставка и разрешение ОС не проверены. «Allow notifications» отдельно вызывает запрос разрешения. |
| Hide expired logins | Сохраняется в config, но аудит #15 подтвердил, что expired login всё равно виден — текущий UI эффект не работает. |
| Time elapsed strip | Сохраняется; аудит #15: snapshot API не передаёт `config.ui`, поэтому false не отключает полосу в отрисованной странице. |
| Forecast | Сохраняется; restart-required, а аудит #15 обнаружил, что false игнорируется на первом poll и применяется на следующем. |
| Working days/hours/off-hours rate | Поля расписания сохраняются, но UI не показывает `forecast.working_hours` toggle, поэтому включить режим из панели нельзя. |
| Poll interval / thresholds | Сохраняются с `restart_required=true`; interval применяется после рестарта. |
| LAN / Desktop widget | Disabled с пояснением; это пока неактивные возможности. |

Обратная проба: временно заменил CSS selector выбранного варианта на `[aria-checked="false"]`; `node scripts/test-settings.mjs` стал красным: `FAIL choice options expose a visible selected, focused, and disabled state` («selected radio must use the theme active surface»). Вернул правильный selector `[aria-checked="true"]`; финальный settings suite — `49 passed`, общий web gate — `clean`.

Отклонения от входов: без схемы/API изменений; чек-листы БД §17 и API §20 не применимы. Save/reload на :7391 проверялись только в отдельном Edge localStorage profile; изменение browser-only preference не отправляло config PUT. Нет разрешения на deployment, поэтому served :7391 остаётся старым.

Открытые вопросы: чтобы увидеть fix на рабочей странице владельца, нужен отдельный deployment/restart с актуальными assets и повторный тест в её браузере; это вне разрешённых границ данной задачи.

Дефекты Nova: нет.
Модель: GPT-6 Luna.
