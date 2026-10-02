# `nova test`: polaris `serve_connection` получает `TcpStream` значением вместо указателя

**ИСПРАВЛЕНО исправлением №1616 (nova `29210c203`, опубликовано в `0dfec1135`); проверено 2026-10-02 09:58:** `nova test src/claude_limits.nv` — PASS. Причина была та же: соглашение о параметре бралось по имени функции (`run_request` в polaris и в nova-http). Запись снята из `KNOWN` в `scripts/ci-test-verdict.py`.

**Замер 2026-10-01, 23:44.** Реестр 221.1 **№1579** (номер дал интегратор 23:42; заводится
после поезда слияний). С 2026-09-30 это «известный CC-FAIL `src/claude_limits`»
(`scripts/ci-test-verdict.py`, план 01.5 T2.27, коммит f4a2d1d): только `nova test`, а
`nova build` того же файла собирается.

## Как запускать

Пробе нужны пакеты claude-limits (`polaris`, `http`), поэтому она кладётся в дерево
проекта: `e_http_imported.nv.txt` → `src/zz_tcp_probe.nv`, затем
`./nova.sh test src/zz_tcp_probe.nv` (и `./nova.sh build src/zz_tcp_probe.nv -o zz.exe` —
для сравнения). Остальные — так же, по одной. Файл после замера удалить.

## Замер (nova main bacdefa12, exe 22:50)

| проба | что рядом с `main`, который зовёт polaris `serve_router` за недостижимым `if` | `nova test` | `nova build` |
|---|---|---|---|
| `e_http_imported` | `import http.transport.{real_http}` и `import http.{Http}` — только ИМПОРТ | **CC-FAIL**: `passing 'NovaValue_TcpStream' to parameter of incompatible type 'NovaValue_TcpStream *'` | — |
| `a_http_used` | то же, и `with Http = real_http() { … }` вызывается | **CC-FAIL**, тот же текст | собирается |
| `f_no_http` (контроль) | без импорта nova-http | PASS | собирается |
| `b_no_polaris` (контроль) | nova-http используется, polaris НЕ импортирован | PASS | — |
| `d_std_tcpstream` (контроль) | polaris + `std.net.TcpStream.connect` вместо nova-http | PASS | — |

Ось — сочетание в ОДНОЙ тестовой сборке: polaris `serve_router` (его `serve_connection`
берёт `TcpStream`) и модуль `http.transport`, который тоже работает с `TcpStream`. Импорта
достаточно — вызов не нужен. Обычная сборка (`nova build`) того же текста зелёная: две
сборки одной программы по-разному решают, где лежит значение `TcpStream`. Класс, по слову
интегратора, — размещение значения (D488 R3/R5).

На integ 8900d9a61 проба не судит: polaris 0.2.1 там не собирается вовсе (алиас импорта,
№1419).
