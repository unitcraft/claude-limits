<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# №TBD — импортированная функция `frame`, переданная значением, уходит в C голым именем

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

Значит, дело в ИМЕНИ, а не в форме импорта. **Гипотеза, не доказанная:** в программе есть
МОДУЛЬ с тем же именем — `ws/frame.nv` в polaris (зависимость пакета), — и ссылка-значение на
импортированную функцию разрешается как что-то иное, чем функция, и не оборачивается в
замыкание. Доказать можно переименованием модуля в копии polaris; не делалось.

Обход: локальная обёртка `fn real_frame(e Event) -> str => frame(e)` (применён в
`sse_loop_test.nv` с комментарием).
