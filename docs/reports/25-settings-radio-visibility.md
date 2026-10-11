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
```

Следствие: `/app.css` на :7391 — другая/старая сборка, без нового правила выбора. Сервер не перезапускался и не менялся. Сравнение непосредственно со «current main» через git не делалось: в этой ветке рабочий source включает radio click handler (app.js), а текущий history report #15 описывает более раннюю версию, поэтому тот отчёт не является достоверным подтверждением поведения нынешнего served UI. DOM unit test подтверждает ARIA переключение; проверка реального Save/reload/localStorage через изолированный браузер на этой сессии не выполнена. Значения localStorage/view/barStyle на :7391 не наблюдались.

Визуальный isolated-browser preview и screenshots до/после не получены: в окружении нет Playwright/Puppeteer, и подключение к пользовательскому профилю запрещено. CSS-проверка и DOM regression test выполнены; нельзя представлять их как проверку скриншотами или deployment.

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

Отклонения от входов: без схемы/API изменений; чек-листы БД §17 и API §20 не применимы. Не делался визуальный browser preview/screenshot, не проверялись Save/reload и localStorage в изолированном браузере. Нет разрешения на deployment, поэтому served :7391 остаётся старым.

Открытые вопросы: чтобы увидеть fix на рабочей странице, нужен отдельный deployment/restart с актуальными assets; это вне разрешённых границ данной задачи. Требуется isolated browser screenshot/Save-reload verification при доступном CDP/browser harness.

Дефекты Nova: нет.
Модель: GPT-6 Luna.
