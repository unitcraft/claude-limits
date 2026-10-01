# Ранний `return Err(…)` в блоке-арме делает тип всего `match` равным `()`

**Замер 2026-10-01, 22:11.** Реестр 221.1 **№1572** (номер дал интегратор 22:12; подозреваемый
по его слову — №1517). Регрессия nova main
0fed40d0d (exe 21:32): на integ 8900d9a61 то же собирается. Носитель — nova-duckdb
`src/duckdb.nv:211` (`QueryResult @value`): все модули пакета и `storage/schema_test`
claude-limits — CODEGEN-FAIL; держит подъём `NOVA_REF` в CI claude-limits.

## Как запускать

Каталог — пакет `hcap`: `nova.toml.txt` → `nova.toml`, `*.nv.txt` → `*.nv`, затем из
каталога `nova build m1_match_block_arm.nv -o m1.exe && ./m1.exe` (и `m2_no_return` так же).

## Замер

| проба | что | nova-integ 8900d9a61 | nova main 0fed40d0d (exe 21:32) |
|---|---|---|---|
| `m1_match_block_arm` | `fn read(k int) -> Result[Val, str]` = `Ok(match k { 0 => { mut v = 1; v = v + 1; if v < 0 { return Err("negative") }; Val.Flag(v != 0) } _ => Val.Num(k) })` | `m1 flag true` | **`E7301 cannot return value of type Result[(), str] from a function declared -> Result[Val, str]`** (позиция — `Ok(`) |
| `m2_no_return` (контроль) | тот же блок-арм без раннего `return Err` | `m2 flag true` | `m2 flag true` |

Ось — ранний `return Err(...)` внутри блока-арма: с ним тип всего `match` выводится как
`()`, без него — `Val`.
