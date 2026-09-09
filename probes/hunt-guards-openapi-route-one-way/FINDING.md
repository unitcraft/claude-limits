# lint-openapi.py: обещаны обе стороны сверки маршрутов, проверяется одна

**КЛЕТКА | lint-openapi.py | К5** (правило объявлено прозой шапки; энфорс знает
только одно направление).
**Найдено:** охотником 2026-09-08, трек `guards`.
**Номер реестра:** №TBD.

## Обещание шапки — дословно

> `WHERE THE ROUTE LIST COMES FROM. Not from a copy kept here: the table in`
> `` `docs/plans/01.3-api.md` section 2 is parsed, so a route added to the contract ``
> `without being added to the spec -- or the reverse -- is what the check is FOR, and a`
> `second list in this file would just drift away from the first.`

(`scripts/lint-openapi.py:13-16`)

## Какую ФОРМУ судит страж

`scripts/lint-openapi.py:210-213` — единственная сверка направлена в одну сторону:

```python
for route in sorted(planned - PHASE_6):
    method, path = route.split(" ", 1)
    if f"{method} {norm(path)}" not in described:
        bad.append(f"{route}: in 01.3 section 2, absent from the contract")
```

Множество `described - planned` не вычисляется нигде.

## Путь, который форму удовлетворяет, а требование нарушает

Маршрут, который есть в контракте и которого нет ни в одной строке таблицы §2:
`GET /api/debug/dump` в `gap/spec.json` (описание — «dumps the whole store,
including tokens»). Он структурно корректен, ссылается на `Problem` в ошибке — и
не упомянут ни в одном плане.

Печатаемая строка при этом сама показывает расхождение и не делает из него вывода:
`described: 15` при 14 неотложенных маршрутах таблицы.

## Воспроизведение

```sh
sh probes/hunt-guards-openapi-route-one-way/cmd.sh
```

**Зазор:**

```
routes in 01.3 section 2: 18 (4 deferred to phase 6), described: 15
OPENAPI LINT: clean
EXIT=0
```

**Контроль (направление, которое реализовано, — из контракта убран `GET /api/export`):**

```
routes in 01.3 section 2: 18 (4 deferred to phase 6), described: 13
OPENAPI LINT: FAILED
   GET /api/export: in 01.3 section 2, absent from the contract
EXIT=1
```

## Смежный зазор, названный без носителя

Список маршрутов строится регуляркой `^\|\s*`(GET|POST|…) ([^`]+)`\s*\|`
(`scripts/lint-openapi.py:55`): бэктик обязан сразу закрываться и упираться в `|`.
Строка таблицы с пометкой в той же ячейке (`` | `GET /api/events` (SSE) | ``) или
маршрут, разложенный по двум колонкам, в список не попадёт — и его отсутствие в
контракте не будет проверено; частичная потеря строк ничем не сверяется (защита
`if not planned` ловит только ПОЛНЫЙ ноль). Сегодня в §2 все 18 строк совпадают с
регуляркой, носителя в дереве нет.
