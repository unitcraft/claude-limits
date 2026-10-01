# Литерал записи телом лямбды: проверка требует одно написание, кодоген — другое

**Замер 2026-10-01, 16:50.** Реестр 221.1 **№1536** (номер дал интегратор 16:49; маршрут —
оракул, кодоген). Найдено при T2.15
(`storage/startup.nv`, `read_history_rows`): `.map(fn(r HistRows) -> HistFolderRows => …)`.

## Как запускать

Переименовать `nova.toml.txt` → `nova.toml`, `r1_anon_in_lambda.nv.txt` →
`r1_anon_in_lambda.nv` (и r2, r3 так же), затем `nova build r1_anon_in_lambda.nv -o r1.exe`.

## Замер

| проба | тело лямбды `fn(x int) -> Pair => …` | nova-integ 8900d9a61 | nova main (exe 2026-10-01) |
|---|---|---|---|
| `r1_anon_in_lambda` | `{ a: x, b: 2 }` | **codegen: `anonymous record literal without spread not supported in codegen`** | то же |
| `r2_typed_in_lambda` | `Pair{ a: x, b: 2 }` | **check: `redundant type prefix on record literal — the return type -> Pair already declares it; write => { ... }`** | то же |
| `r3_named_fn` (контроль) | `pair_of(x)`, где `fn pair_of(x int) -> Pair => { a: x, b: 2 }` | `r3 1 2` | `r3 1 2` |

Ось — где стоит литерал: в теле лямбды законного написания НЕТ (проверка отвергает
типизированное и советует анонимное, кодоген отвергает анонимное), в теле именованной
функции анонимное работает. Совет проверки ведёт прямо в отказ кодогена.

## Обход в claude-limits

`startup.accounts_only` — именованная функция, лямбда её только зовёт.
