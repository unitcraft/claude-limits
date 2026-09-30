<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# №TBD — `.collect()` вектора записей, затем `sort_by`: процесс падает (0xC0000005)

**Замер 2026-09-30 12:45**, окно claude-limits, бинарь `nova-integ` 10:55. Найдено так:
линтер потребовал в `model/live.nv` заменить цикл `push` на канон `windows.collect()`
(`W_MANUAL_COLLECT`), и после замены тестовый прогон упал нарушением доступа.

**Приоритет:** К1 по последствию (процесс падает на исполнении), и линтер сам ведёт к
форме, которая падает. `check` и сборка — зелёные.

## Репро (`repro_test.nv.txt`, один модуль, четыре теста)

| случай | итог |
|---|---|
| A: `[]int` → `.collect()` | PASS |
| B: `[]int` → `.collect()` → `sort_by` | PASS |
| C: `[]Window` (запись: три `str`, два `int`) → `.collect()` | PASS |
| D: `[]Window` → `.collect()` → `sort_by` | **RUN-FAIL 0xC0000005** |
| контроль: `[]Window` → цикл `push` → тот же `sort_by` (`model/live.nv`) | PASS |

`Window` — `src/window.nv`: `kind str, model str, percent int, resets_at_ms int,
locked_reason str`.

## Обход

Цикл `push` с `nova:allow W_MANUAL_COLLECT` и ссылкой на эту пробу — `model/live.nv`,
`in_row_order`.

Механизм не читался. Первое, что стоит проверить: отдаёт ли `.collect()` на `Vec` новый
буфер или тот же, и с какой ёмкостью, — `sort_by` пишет в него на месте.
