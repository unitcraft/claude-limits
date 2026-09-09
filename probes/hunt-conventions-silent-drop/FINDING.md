# Панель настроек молча выбрасывает значение — и «какое выбросить» решается по имени листа

**Трек:** oracle-формы (охота по конвенциям). **КЛЕТКА:** страница и инструменты × конвенция
по API §0.5 и §5.2. **Найдено 2026-09-08 охотником.**

## КЛАСС

**Значение, которое человек изменил в панели, может исчезнуть по дороге, и ни одно место об
этом не говорит.** Свойство шире найденного случая: у панели есть контролы, чьё «куда это
попадёт» решается фильтром на выходе, а не тем, откуда контрол построен. Фильтр сравнивает
**последний сегмент** пути со списком имён, поэтому класс не ограничен теми пятью
настройками, что перечислены сегодня.

Три формы, в которых свойство уже присутствует, — все три показаны пробой:

* контрол есть, значение не попадает **никуда** (`ui.countdown`);
* контрол подписан «хранится в браузере», а значение уходит **в файл** (`ui.hide_stale`);
* контрол с совершенно другой настройкой исчезает, потому что **совпало имя листа**
  (`widget.view`).

## Норма, дословно

`docs/conventions/api.md:26` (§0 «Принципы», п. 5):

> **Молчаливых исходов нет.** Лишнее поле, обрезанный лимит, проигнорированный параметр,
> невалидный ключ идемпотентности: всё это громкие ошибки, а не тихая подстановка.

`docs/conventions/api.md:235` (§5 «Валидация», п. 2):

> **Схема запроса закрыта.** Лишнее поле `422 extra_forbidden`, не игнорирование: опечатка в
> имени поля иначе превращается в документ без значения, найденный через месяц.

И решение страницы, дословно, `src/web/settings.js:11-13`:

> `BROWSER_ONLY` — layout, bar style and the countdown live in localStorage and are
> not config keys at all (§5.1). Putting one in the body earns a `422 extra_forbidden`, and
> the panel would blame the wrong field.

То есть громкий отказ, который конвенция назначает именно этому случаю, заменён тихим
выбрасыванием на клиенте — и заменён осознанно, это записано в шапке.

## Замер

```
BROWSER_ONLY = ["view","bar_style","countdown","stats_range","stats_group"]

A. the "Reset time / show countdown" toggle (settings.js:169-170)
   present in the panel : true
   flipped, now         : aria-checked=true
   body of the PUT      : {}
   isEmptyDiff -> Save closes the panel without a request: true
   every localStorage key the page touches:
     app.js: localStorage.setItem('view') / ('stats_range') / ('stats_group')
     app.js: localStorage.getItem('stats_range') / ('stats_group') / ('view')
   any of them "countdown"? false

B. the same section is captioned (settings.js:168):
   "kept in this browser, not in the config file"
   flipping "Hide logins with an expired token" gives a body of
   {"ui":{"hide_stale":true}}   <- into the config FILE

C. a control at path `widget.view` (leaf `view` is in BROWSER_ONLY):
   collect() returns widget = {"enabled":false,"always_on_top":true}
```

Случай A целиком: тумблер строится из ветки конфига (`src/web/settings.js:170`,
`cfg.ui && cfg.ui.countdown`), которой в конфиге нет (`fixtures/api/config.json`, ветка `ui`
несёт `accounts_order`, `hidden_accounts`, `hide_stale`, `time_bar`), фильтр выбрасывает его
из тела, а `localStorage.countdown` не пишет никто. Человек нажимает Save — панель
закрывается, запроса нет, сообщения нет, при следующем открытии тумблер снова выключен.

Случай B: подпись секции и список `BROWSER_ONLY` — **два разных объявления одного факта**, и
они уже разошлись. По `docs/plans/01.1-browser-page-spec.md:301` `hide_stale` — настройка
конфига, значит врёт подпись; по подписи — врёт список. Выбирать не мне.

## ДВЕРЬ

`src/web/settings.js:293-299` — единственное место, где решается, что уходит в тело:

> `const put = (path, value) => { const parts = path.split('.'); if
> (BROWSER_ONLY.includes(parts[parts.length - 1])) return; … }`

Дверь есть, но правило, которое она исполняет, объявлено ещё в двух местах, и **ни одно из
трёх не сверяется с двумя другими**:

1. `src/web/settings.js:17` — список `BROWSER_ONLY`;
2. `src/web/settings.js:168` — подпись секции «kept in this browser, not in the config file»;
3. `docs/plans/01.1-browser-page-spec.md:296-301` — таблица, где у каждой настройки написано,
   `localStorage` она или конфиг.

## ПОЧЕМУ НЕ ЧИНИТСЯ У НОСИТЕЛЯ

Дописать запись `localStorage.countdown` — починка одного контрола. Свойство останется:
`put` по-прежнему сравнивает **имя листа**, а не путь, поэтому первый же `widget.view`,
`chart.bar_style` или `folders.stats_range` исчезнет так же тихо (случай C показывает это на
уже собранной панели). И подпись секции по-прежнему останется вторым, немашинным объявлением
того же правила — тем самым, которое уже разошлось на `hide_stale`.

Отдельно: `src/web/settings.js:290-292` признаёт, что до 2026-09-08 список никто не
консультировал, а тест на него был зелёным, «потому что защищать было не от чего». Сегодня
тест (`scripts/test-settings.mjs:58-64`) проверяет, что имён из `BROWSER_ONLY` нет в теле, —
он зелёный и в случае A (значение выброшено), и был бы зелёным, если бы контрола не было
вовсе. Того, что значение при этом **никуда не записалось**, он не видит.

## Воспроизведение

```
sh probes/hunt-conventions-silent-drop/cmd.sh
```

Проба поднимает DOM-заглушку проекта (`scripts/dom-stub.mjs`), строит панель из
`fixtures/api/config.json`, ничего не пишет и сети не трогает.
