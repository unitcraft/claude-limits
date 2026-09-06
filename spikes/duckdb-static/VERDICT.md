# Спайк: DuckDB статически в бинаре Nova — вердикт 2026-09-06

**Вопрос** (подплан 01.2, §0а): можно ли вместо SQLite взять DuckDB ради настоящих типов
(`TIMESTAMP`, `BOOLEAN`, `ENUM`, `DECIMAL`), и что это стоит — размер бинаря, холодный старт,
конфликт CRT при статической линковке C++ с рантаймом Nova.

**Стенд.** DuckDB v1.5.5, амальгамация `libduckdb-src.zip` (4,97 МБ; `duckdb.cpp` 655 591 строк).
Windows 11: clang 22.1.5 (clang-cl + lld-link), MSVC 14.44 через `vcvars64`, Nova CLI 0.1.0
(`nova build --mode release`, рантайм `/MT`). Linux: WSL2 Ubuntu, clang 21.1.8, 10 vCPU, 9,9 ГБ.

## Числа

| | Windows | Linux (WSL) |
|---|---|---|
| компиляция `duckdb.cpp -O2` | 661 с, пик RSS 3,5 ГБ | 1196 с, пик RSS 4,8 ГБ |
| статическая библиотека | `duckdb_static.lib` 118,9 МБ (obj 104,5 МБ) | `libduckdb_static.a` 62,1 МБ |
| C-тест `spike.exe` | 36,43 МБ | `-static-libstdc++` 36,8 МБ; полностью `-static` 37,4 МБ; strip → 30,1 МБ |
| Nova-бинарь `duckspike.exe` | **36,82 МБ** (hello world на Nova — 0,56 МБ) | не собирали (Nova в WSL нет) |
| импорты Nova-бинаря | ADVAPI32, WS2_32, IPHLPAPI, USERENV, bcrypt, RstrtMgr, USER32, dbghelp, ole32, SHELL32, KERNEL32 — **CRT-DLL нет**, CRT статический | `ldd`: not a dynamic executable |
| холодный старт процесса Nova-бинаря | 661–873 мс первый запуск; 244–259 мс далее (hello: 214–272 мс) | — |
| `duckdb_open` + `connect` | 18–51 мс (первый запуск 277 мс) | 7–22 мс |
| 10 000 `INSERT` по одной, prepared, одна транзакция | 19,5–21,4 с (≈2 мс/строка) | 25,8–26,2 с |
| 10 000 строк через Appender | 8,7–12,0 мс | 11,5–12,0 мс |
| выборка по диапазону дня с группировкой | 1,5–2,6 мс | 2,0–6,7 мс |
| `INSERT 'not a time'` в `TIMESTAMP` | ошибка типа (строгость есть) | то же |
| файл БД после 20 000 строк | 1,51 МБ | 1,51 МБ |

## Что вскрылось

1. **Заголовки Windows ломают сборку без `WIN32_LEAN_AND_MEAN` и `NOMINMAX`** — `windows.h`
   определяет макрос `interface`, а DuckDB использует это слово как идентификатор. С флагами
   собирается.
2. **Амальгамация не содержит `core_functions` и `icu`.** `make_timestamp`, `date_trunc`,
   `time_bucket`, `epoch_ms` и вся арифметика `TIMESTAMPTZ` — в расширениях, которых в
   `libduckdb-src.zip` нет (`CoreFunctionsExtension` в исходнике отсутствует). При первом вызове
   такой функции DuckDB **идёт в интернет за расширением** и держит запрос ~22 с, потом падает.
   Обход в спайке: `SET autoinstall_known_extensions=false; SET autoload_known_extensions=false`,
   привязка `TIMESTAMP` через C-API (`duckdb_bind_timestamp`), литералы `TIMESTAMP '…'`, без
   `date_trunc`. Для продукта это означает полную CMake-сборку из репозитория DuckDB с
   `-DBUILD_EXTENSIONS="core_functions;icu"` и статической линковкой расширений — существенно
   тяжелее амальгамации.
3. **Зависимости на Windows**: `rstrtmgr.lib` (Restart Manager), `ws2_32`, `bcrypt`. В пакете
   Nova они подтягиваются `#pragma comment(lib, …)` из C-шима, `[ffi] libs` для них не нужен.
4. **Шим должен определять `DUCKDB_STATIC_BUILD`** до `#include "duckdb.h"`, иначе функции
   объявлены `__declspec(dllimport)` и lld-link не берёт их из статической библиотеки.
5. **Построчная запись** ≈2 мс на `INSERT` — колоночный движок не для OLTP. Наш тик — десятки
   строк, то есть 50–100 мс, плюс точечные `UPDATE`. Терпимо, но на порядки медленнее SQLite.
6. **`at` — зарезервированное слово** в DuckDB, колонка переименована в `sampled_at`.

## Вердикт

- Конфликта CRT **нет**: `nova build` с `[ffi] libs = ["duckdb_static"]` линкуется, бинарь работает,
  CRT статический, как у рантайма Nova.
- Холодный старт **не страдает**: разница с hello-бинарём в пределах шума после первого запуска.
- Цена: **+36 МБ** к бинарю на каждой ОС, 11–20 минут компиляции библиотеки на чистом CI, а
  ради `date_trunc` и часовых поясов — полная сборка репозитория DuckDB вместо амальгамации.
- Типы настоящие: `TIMESTAMP`, `BOOLEAN`, `ENUM`, `DECIMAL`, строгость на входе.

Решение о хранилище — за владельцем (подплан 01.2 §0а). Файлы: `spike.c`, `build_win.ps1`,
`build_linux.sh`, `novapkg/` (nova.toml с `[ffi]`, `native/duck_shim.c`, `spike.nv`).
