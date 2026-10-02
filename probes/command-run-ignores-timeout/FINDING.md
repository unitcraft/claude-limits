# `Command.run` не прерывается `supervised(timeout:)`, хотя документация это обещает

**Замер 2026-10-02 05:23.** Реестр 221.1 **№1615**, К2 (номер дал интегратор 05:25). Чем
мерил, точно: рантайм (`nova_rt`) и std — из ЛОКАЛЬНОГО дерева интегратора `D:/Sources/nv-lang/nova`
на HEAD `10b4a0146` (ещё не опубликован; опубликованный `main` тогда — `2488a47be`); бинарь
компилятора — сборка того же дерева от 02:51, через копию `./nova.sh`. Найдено при П5 плана 01.6: обновлению Claude-логина нужен
таймаут на запуск `claude`, иначе зависший процесс останавливает раунд опроса.

## Что обещано

`std/src/os/os.nv`, `Command @run`: «`Err` means the process never RAN at all (bad
`program`, permission denied, **or the call was interrupted by an enclosing
`supervised(timeout:)`/`(cancel:)` — `ErrorKind.Interrupted`**)».

## Что происходит

| проба | ожидание | получено |
|---|---|---|
| `q_cmd_timeout` — `ping -n 30` (~29 с) под `supervised(timeout: 2 s)` | `Err(Interrupted)` через ~2 с | **`returned after 29321 ms: exit 0`** — таймаут не заметил вызов, ждал до конца |
| `q_sleep_control` — `Time.sleep(10 s)` под тем же `supervised(timeout: 2 s)` (КОНТРОЛЬ) | прерывание через ~2 с | `nova: unhandled Fail: supervised-timeout: scope deadline exceeded` — механизм работает |

Механизм дедлайна исправен (контроль), не прерывается именно `Command.run`: вызов,
по-видимому, блокирует поток ожиданием процесса и не наблюдает отмену. Дочерний `ping` после
окончания пробы не остаётся (`tasklist`: 0) — но лишь потому, что он доработал сам.

## Как запускать

Каталог-пакет `hcap`: `nova.toml.txt` → `nova.toml`, `q_cmd_timeout.nv.txt` →
`q_cmd_timeout.nv`, `q_sleep_control.nv.txt` → `q_sleep_control.nv`; `nova build <файл> -o
<exe>`, запустить оба.

## Вес для claude-limits

Обход есть и он в коде П5: таймаут на запуск `claude` держит не `supervised`, а обёртка
процесса. Дефект бьёт любого, кто положился на обещание документации: процесс, который не
завершается, держит вызывающий файбер навсегда.
