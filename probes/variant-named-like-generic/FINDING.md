# Вариант `DuckError.Query` тянет в тест `Query[T]` из тестового файла Polaris

**Замер 2026-10-01, 15:07.** Реестр 221.1 **№1527** (номер дал интегратор 15:42; родня по его строке —
08-runtime.md:9011, `NetError.IoError` против типа `IoError`, и регрессия с `Outcome` того же
дня). Первая запись называла это семейством №1040 — ошибка: №1040 про `nova test --filter`.
Найдено при T2.15: тест обработчика истории, импортирующий и Polaris, и модуль строк
истории (а через него `duckdb.errors`), не собирается.

## Как запускать

Пробе нужны зависимости claude-limits (`polaris`, `duckdb`), поэтому её кладут в дерево
проекта: `q1_errors.nv.txt` → `src/server/handlers/zz_probe_test.nv`, затем
`./nova.sh test src/server/handlers/zz_probe_test.nv`. Так же — `q2_types.nv.txt`.
Файл после замера удалить.

## Замер

| проба | что импортирует рядом с `polaris.{ServerRequest}` | nova-integ 8900d9a61 | nova main f0c5dbdd3 |
|---|---|---|---|
| `q1_errors` | `duckdb.errors.{DuckError}` | **CC-FAIL** | **CC-FAIL** |
| `q2_types` | `duckdb.types.{Value}` (контроль) | PASS | PASS |

Текст отказа clang (одинаков на обоих):
`passing 'NovaValue_ServerRequest' to parameter of incompatible type 'NovaValue_ServerRequest *'`
в строке `Nova_Query____NovaValue_SearchQuery_static_from_request((*req))`.

`SearchQuery` объявлен в `nova-polaris/src/extract_test.nv` — ТЕСТОВОМ файле Polaris
(`module polaris`), который claude-limits не упоминает. Ось — имя: у `DuckError` есть
вариант `Query(str)`, у Polaris — обобщённый `Query[T]`. `duckdb.types` такого варианта
не несёт, и с ним сборка зелёная.

В сборке приложения (`nova build src/claude_limits.nv`) оба пакета живут в одной единице
трансляции и собираются: тестовые файлы пакетов туда не входят. Значит, краснеет только
`nova test`.

## Обход в claude-limits

Типы строк истории — в `src/storage/history_rows.nv`, который duckdb не импортирует;
обработчик берёт типы оттуда, а читатель (`history_read.nv`) один тянет duckdb.
