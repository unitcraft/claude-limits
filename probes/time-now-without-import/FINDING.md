# `Time.now()` в модуле без импорта из `std.time` — внутренняя паника кодогена

**Замер 2026-10-01, 17:08.** Реестр 221.1 **№1537** (номер дал интегратор 17:04). Найдено
при T2.15, `server/start.nv` (`history_env_now`): чтение часов на каждый запрос.

## Как запускать

Каталог — пакет `hcap`: переименовать `nova.toml.txt` → `nova.toml`, `t1_no_import.nv.txt` →
`t1_no_import.nv` (и t2 так же), затем из этого каталога
`nova build t1_no_import.nv -o t1.exe && ./t1.exe`. Имя модуля (`hcap.t1_no_import`)
совпадает с путём файла внутри пакета — иначе `E_D78_MODULE_PATH_MISMATCH`.

## Замер

| проба | что | nova-integ 8900d9a61 | nova main (exe 2026-10-01) |
|---|---|---|---|
| `t1_no_import` | `fn stamp() Time -> int => Time.now().unix_millis() as int`, модуль ничего не импортирует | **`codegen error: [INTERNAL-PANIC] [E_CODEGEN_TYPE_UNKNOWN] Path call return type unknown for method=now`** | то же |
| `t2_with_import` (контроль) | то же + `import std.time.duration.{Timestamp}` | `t2 true true` | `t2 true true` |

Ось — импорт из `std.time`: тип `Timestamp`, который возвращает `Time.now()`, не попадает в
единицу трансляции, и вместо диагностики «не импортировано» кодоген паникует.

## Обход в claude-limits

`server/start.nv` импортирует `std.time.duration.{Timestamp}`.
