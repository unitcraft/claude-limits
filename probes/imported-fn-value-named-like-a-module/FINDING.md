<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# №1400 — импортированная функция `frame`, переданная значением, уходит в C голым именем

**Замер 2026-09-30 11:05–11:30**, окно claude-limits, бинарь `nova-integ` 10:55. Найдено при
`server/handlers/sse_loop_test.nv` (T2.13): тест передавал настоящий `frame` из `events.nv`
как `fn(Event) -> str`.

**Приоритет:** К2 — `check` принимает, сборка падает громко.

## Репро (внутри пакета claude-limits, файл рядом с `events.nv`)

```nova
module handlers.zz_frame_probe_test
import claude_limits.model.store.{Event}
import events.{frame}
fn ap(f fn(Event) -> str) -> str => f(Event.new(1, "a", "b"))
test "imported frame passed as a value" {
    assert(ap(frame).contains("id: 1"))
}
```

```
error: use of undeclared identifier 'frame'
```

В C (`--keep-artifacts`): `nova_fn_..._2ap(frame)` — голое `frame`, хотя функция объявлена
как `nova_fn_8handlers6events5frame` (и вызов `frame(e)` в том же модуле собирается).

## Оси

| случай | итог |
|---|---|
| `frames` из ТОГО ЖЕ `events`, значением | PASS |
| своя функция `frame` в тестовом модуле, значением | PASS |
| `quote` из `repo` значением, и по полному, и по соседнему импорту | PASS |
| **`frame` из `events` значением** | **CC-FAIL** |

Значит, дело в ИМЕНИ, а не в форме импорта.

## Минимизация 2026-09-30 11:40 (по просьбе интегратора: у него повтор не воспроизвёлся)

Копия `events.nv` под другим именем модуля, затем снятие по одному; каждый вариант — своя
единица трансляции, тест всегда один: `import zz_mX.{frame}` и `ap(frame)`.

| объявляющий модуль | итог |
|---|---|
| a: полная копия `events.nv` | **CC-FAIL** |
| b: только `frame`, без других импортов | PASS |
| c: только `frame` + `import polaris.{ServerResponse, StreamBody}` | **CC-FAIL** |
| d: только `frame` + `import claude_limits.server.routes.{…}` (routes импортирует polaris) | **CC-FAIL** |
| e: только `frame` + `import claude_limits.server.errors.{ApiError}` | PASS |
| f: только `frame`, тело интерполяцией, без импортов | PASS |
| g: только `frame` + `import polaris.{StatusCode}` — ОДНО постороннее имя | **CC-FAIL** |
| h: как c, но функция названа `framx` | PASS |

**Ось — конъюнкция двух условий:** (1) функция зовётся `frame`; (2) объявляющий её модуль
импортирует что угодно из polaris (прямо или транзитно). В polaris есть модуль
`ws/frame.nv`; у интегратора модуль-тёзка лежал в СВОЁМ пакете и не подтягивался импортом
объявляющего модуля — вероятно, поэтому зелёный. Что именно из polaris перехватывает имя
(модуль `ws.frame` или что-то ещё с этим именем) — не сужено дальше.

Минимальный набор: пакет с зависимостью polaris; модуль
`import claude_limits.model.store.{Event}` + `import polaris.{StatusCode}` +
`export fn frame(e Event) -> str { … }`; тест импортирует `frame` и передаёт значением.

Обход: локальная обёртка `fn real_frame(e Event) -> str => frame(e)` (применён в
`sse_loop_test.nv` с комментарием).
