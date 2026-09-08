# Ф.2 — аудит приёмки (НЕ приёмка), 2026-09-08

**Что это.** Разбор одиннадцати пунктов приёмки [01.1 §11](../plans/01.1-browser-page-spec.md)
на два класса: что **уже отвечается машиной сегодня**, без бэкенда, и что **строго
требует поднятого бинаря**. Сама приёмка Ф.2 — задача T2.26, и её отчёт будет
называться `F2-acceptance.md`. Этот файл её не заменяет и не предвосхищает: он
отвечает на вопрос «сколько из приёмки уже нельзя сломать незаметно», чтобы T2.26
свелась к прогону, а не к выяснению, что вообще проверять.

**Зачем отдельным файлом.** Правило `/next`: критерии, которые нельзя проверить
машиной, помечаются словами «приёмка глазами, потому что …», а не подразумеваются.
Пункты ниже, помеченные «нужен бэкенд», — это именно такие: они законны, но названы.

**Как проверить это сам:**

```sh
cd <repos>/claude-limits
node scripts/check-web.mjs
python scripts/check-fixtures.py
```

**Почему одна команда, а не цикл по списку наборов** (правка того же дня, вечером):
здесь стоял `for f in format render reorder chart stats folders settings` — рукописный
список, который МОЛЧА меряет меньше с каждым новым набором. Именно так
`test-live.mjs` остался бы незапущенным, а аудит — зелёным. `check-web.mjs` ищет
наборы сам и судит по коду возврата.

Вывод прогона 2026-09-08, дословно (индекс отчётов требует цитату, а не пересказ):

```
$ node scripts/check-web.mjs
ok     test-chart.mjs           20 passed
  ok     test-folders.mjs         18 passed
  ok     test-format.mjs          41 passed
  ok     test-live.mjs            15 passed
  ok     test-render.mjs          22 passed
  ok     test-reorder.mjs         14 passed
  ok     test-settings.mjs        36 passed
  ok     test-stats.mjs           25 passed
  ok     check-page.py            PAGE GUARD: clean
  ok     lint-openapi.py          OPENAPI LINT: clean (self-test on the fixture)

8 suites + the page guard, 191 tests
WEB CHECK: clean
$ python scripts/check-fixtures.py
fixtures found: 24 in <repos>\claude-limits\fixtures
  api/config.json                                      valid JSON, limits=n/a n/a
  api/history-7d.json                                  valid JSON, limits=n/a n/a
  api/history-folders.json                             valid JSON, limits=n/a n/a
  api/snapshot-mixed.json                              valid JSON, limits=5 ['weekly_scoped', 'session', 'weekly_all', 'session', 'weekly_all']
  dirs/config-dir-layout/work/.claude.json             valid JSON, limits=n/a n/a
  dirs/config-dir-layout/work/.credentials.json        valid JSON, limits=n/a n/a
  dirs/default-layout/.claude/.credentials.json        valid JSON, limits=n/a n/a
  dirs/default-layout/.claude.json                     valid JSON, limits=n/a n/a
  dirs/expired/.claude.json                            valid JSON, limits=n/a n/a
  dirs/expired/.credentials.json                       valid JSON, limits=n/a n/a
  dirs/two-dirs-one-account/same-email-a/.claude.json  valid JSON, limits=n/a n/a
  dirs/two-dirs-one-account/same-email-a/.credentials.json valid JSON, limits=n/a n/a
  dirs/two-dirs-one-account/same-email-b/.claude.json  valid JSON, limits=n/a n/a
  dirs/two-dirs-one-account/same-email-b/.credentials.json valid JSON, limits=n/a n/a
  openapi/sample.json                                  valid JSON, limits=n/a n/a
  transport/malformed-body.json                        valid JSON, limits=n/a n/a
  transport/rate-limited-no-header.json                valid JSON, limits=n/a n/a
  transport/rate-limited-with-retry-after.json         valid JSON, limits=n/a n/a
  transport/server-error.json                          valid JSON, limits=n/a n/a
  transport/unauthorized.json                          valid JSON, limits=n/a n/a
  usage/empty-limits-fallback.json                     valid JSON, limits=0 []
  usage/locked.json                                    valid JSON, limits=2 ['session', 'weekly_all']
  usage/normal.json                                    valid JSON, limits=3 ['session', 'weekly_all', 'weekly_scoped']
  usage/two-scoped-models.json                         valid JSON, limits=4 ['session', 'weekly_all', 'weekly_scoped', 'weekly_scoped']

SECRET SCAN: clean
```

Итого 191 тест в восьми наборах, три стража чисты (страница, фикстуры, контракт-линтер на своей фикстуре).

**Что изменилось с утра того же дня:** было 152 теста в семи наборах. Прибавились `test-live.mjs` (транспорт SSE, T2.21) и тесты политики повторов, кнопки после 429, конфликта при 412 и события `config`. Цифры выше взяты ПРОГОНОМ при правке этого файла, а не переписаны из памяти.

## Пункт за пунктом

| № | пункт §11 | класс | чем закрыт / чего не хватает |
|---|---|---|---|
| 1 | состояния §3.2 из фикстур; красная плашка при 100 % и `locked_reason`; `stale` без запроса | **частично машиной** | Отрисовка всех четырёх состояний и красная плашка — `test-render.mjs` («a non-ok account shows its message and NO rows», «a locked account is marked locked», «a locked window is critical at any percent»). **Нужен бэкенд:** «ноль вызовов `Http` для `stale`» — это утверждение о поллере, не о странице. |
| 2 | три колонки не переносятся при 720; при 560 время уходит под бар | **глазами, потому что** это раскладка CSS: правило `@media (max-width: 560px)` в `app.css` можно прочитать, но что колонка не переносится — вопрос к движку, а не к структуре. Проверяется в браузере. |
| 3 | кубики: при 300/338/400 px ни одной частичной ячейки; `floor((w+2)/10)`; тултип | **машиной** | `test-format.mjs`, тесты `cellGeometry`. Формула и запрет на обрезанную ячейку зафиксированы; тултип с числом ячеек ставит `layoutCells`. |
| 4 | полоса времени: `resets_at = now + 1h02m` у сессии → доля 79 % ± 1 | **машиной** | `test-format.mjs`, `elapsedShare`. |
| 5 | прогноз: тест-вектор даёт 103 % и `runs_out_at` = сброс − 30 мин | **нужен бэкенд** | Прогноз считает БЭКЕНД (01.1 §2.6–§2.7), страница только рисует присланное. Страница обязана нарисовать призрак ровно там, где сказано, — это `test-render.mjs` («the forecast ghost appears only where the forecast is ahead») и `test-chart.mjs`. |
| 6 | плашки: мышь и клавиатура меняют `accounts_order`; порядок общий для трёх видов; ошибка `PUT` откатывает | **машиной, кроме сети** | `test-reorder.mjs` (14 тестов: клавиатура, перетаскивание, откат, тост) и `test-render.mjs` («the SAME order applies to the list view»). **СТАЛО МАШИНОЙ 2026-09-08 (T2.22):** «порядок переживает перезагрузку» держится
тремя звеньями, и каждое покрыто отдельно: запись — `config_test.nv:341`, отдача —
`snapshot_test.nv:188`, запрос страницы с `If-Match` — `orderRequest` в `test-format.mjs`.
Среднего звена не было совсем — запрос собирался внутри `saveOrder`, куда тест не
заглядывает. **Остаётся бэкенду:** цепь ЦЕЛИКОМ на живом бинаре — три
зелёных звена не то же самое, что зелёная цепь, и это работа T2.26. |
| 7 | настройки: каждое поле → ключ конфига; `400` подсвечивает поле; смена `bind` без токена отвергнута | **машиной, кроме сети** | `test-settings.mjs` (24 теста: частичное тело, ссылки на папки, запрет браузерных ключей, подсветка по `errors[].field` текстом сервера, нераспознанная ошибка не проглатывается). **Нужен бэкенд:** отказ при смене `bind` и «интервал действует со следующего тика» — оба про сервер. |
| 8 | статистика: 2016 точек на окно за 7 д; вертикали сбросов, красные полосы `locked`, янтарные разрывов; одна вертикаль на три колонки | **машиной, кроме числа точек** | `test-chart.mjs` + `test-stats.mjs`: полосы, вертикали, обрыв линии на разрыве, общая вертикаль наведения. **Нужен бэкенд:** «2016 точек» — свойство ответа эндпоинта при `step=300`, а не страницы; фикстура намеренно использует `step=3600` (169 точек), потому что читаемость фикстуры важнее совпадения с прод-шагом. |
| 9 | папки: смена почты даёт новую запись занятости; линия обрывается на границе; подпись про ограничение есть | **машиной, кроме журнала** | `test-folders.mjs`: обрыв и перекраска линии на смене, серый хвост, подпись про ограничение на странице. **Нужен бэкенд:** что переписанный `.claude.json` РОЖДАЕТ запись занятости — это поведение обнаружения. |
| 10 | SSE: сеть выключить → серая точка и `polling`; включить → зелёная; числа без перезагрузки | **МАШИНОЙ с 2026-09-08, кроме живого соединения** | Здесь стояло «ни строки этого поведения не подтверждено прогоном» — это была правда и была дырой, которую закрыл T2.21. Транспорт вынесен в `src/web/live.js` с внедряемыми зависимостями, и `test-live.mjs` (15 тестов) ОСТАНАВЛИВАЕТ и ЗАПУСКАЕТ поддельный сервер: точка говорит `polling` при отказе и `live` после запуска, опрос идёт раз в 10 с и ровно ОДИН, переподключение через 30 с и ровно ОДНО. ЦВЕТ точки держит `check-page.py` — js-тест не видит таблицы стилей. По дороге выяснилось, что 30 с из спеки НЕ СОБЛЮДАЛИСЬ ничем: `EventSource` после обрыва идёт в CONNECTING, а не CLOSED, и старый таймер был закрыт условием, которое не наступало. **Остаётся бэкенду:** выключенная СЕТЬ и настоящий `EventSource` в браузере; поддельный поток воспроизводит автомат состояний по спеке HTML, а не браузер. |
| 11 | доступность: у всех баров `aria-valuetext`; клавиатурой достижимы шапка, вкладки, ручки, панель | **машиной** | `test-render.mjs` (`role="meter"`, `aria-valuenow`, `aria-valuetext`, `aria-hidden` у полосы времени и призрака), `test-stats.mjs` (кнопка `table` и скрытая таблица значений), `test-reorder.mjs` (клавиатурный перенос ручкой). |

## Что этот аудит нашёл в уже написанном коде

Не «всё готово, ждём бэкенд». Два **реальных нарушения §10**, которые пункт 11 ловит,
а я до аудита не сделал:

1. **У баров не было ни `role="meter"`, ни `aria-valuenow`, ни `aria-valuetext`.**
   Программа чтения с экрана видела пустой `div`: процент лежит в соседнем элементе,
   а полоса времени и призрак прогноза текста не несут вовсе. Исправлено; строка
   `aria-valuetext` СОБИРАЕТСЯ из трёх мест именно потому, что полоса и призрак
   помечены `aria-hidden` — иначе их смысл пропадает совсем.
2. **У карточек графиков не было кнопки `table`** со скрытой таблицей значений.
   График — `role="img"` с однострочной подписью: она говорит, ЧТО это, и ничего о
   том, что показано. Таблица — единственный путь к самим числам и единственный
   способ их скопировать, потому что SVG не выделяется мышью. Добавлена обоим видам,
   строится по требованию (неделя почасовых замеров — 168 строк на серию).

## Итог

Из одиннадцати пунктов: **три закрыты машиной полностью** (3, 4, 11), **пять — в той
части, что принадлежит странице** (1, 6, 7, 8, 9; за бэкендом там остались поллер,
сохранение порядка, отказ по `bind`, число точек и журнал занятости), **один глазами
по природе** (2), **два целиком за бэкендом** (5, 10). Остаток T2.26 — это прогон
против живого бинаря и отчёт, а не выяснение критериев.
