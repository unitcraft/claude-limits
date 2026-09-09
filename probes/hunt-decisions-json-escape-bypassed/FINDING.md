# Экранирование JSON: дверь есть, обойти её ничего не мешает, и её уже обошли дважды

Охота 2026-09-08, трек `oracle`. Запускать из корня репозитория: `sh cmd.sh`.

## КЛАСС

**Строковое значение попадает в тело JSON, не пройдя через экранирование.** Свойство,
а не конструкция: выразимо любым `sb.append(<str>)` внутри собираемого тела, любым
`"\"${x}\""`, любым `field_raw(name, <str>)`. Тип по обе стороны двери — `str`, поэтому
экранированное и сырое значение для компилятора неразличимы, и проверить проход можно
только чтением.

Класс НЕ гипотетический: он уже случался в этом же файле-каркасе и был починен, о чём
`json.nv` пишет в собственной шапке —

    src/server/json.nv:8-13
        // WHY A FILE AT ALL, when a body is four fields and `"${x}"` writes it in one
        // line: because `"${x}"` writes the value RAW. A `detail` carrying a quote, a
        // backslash or a newline — and a detail is the one field built from a message
        // someone else wrote — closes the string early and hands the page a body its
        // parser rejects. The first version of `errors.nv` interpolated `detail`
        // straight into the body; this file is the fix, and `escape` is why it exists.

— и вернулся в двух других файлах той же фазы.

## ДВЕРЬ

    src/server/json.nv:51   export fn escape(s str) -> str
    src/server/json.nv:79   export fn quote(s str) -> str => "\"${escape(s)}\""

Все `field_*` идут через неё. Дверь одна, и она правильная.

## НОСИТЕЛИ — ДВА, В РАЗНЫХ МОДУЛЯХ

1. Выгрузка в JSON собрана целиком конкатенацией, мимо `json.nv`; модуль его даже
   не импортирует (`src/server/handlers/exporter.nv:27-30` — импортов `json` нет):

       src/server/handlers/exporter.nv:223-246
           fn rows_to_json(rows []Row, unmasked bool) -> str {
               ...
               sb.append("{\"at\":\"")
               sb.append(r.at)
               sb.append("\",\"account_id\":\"")
               sb.append(r.account_id)
               sb.append("\",\"email\":\"")
               sb.append(email)
               ...
               if r.model == "" { sb.append("null") } else { sb.append("\"${r.model}\"") }

   `r.model` приходит из чужого JSON — `scope.model.display_name` эндпоинта
   (`src/usage/parse.nv:77-95`), — то есть это не «наша строка», а внешний вход.
   `email` — из базы. Ни один не экранируется.

2. Список путей в DTO — там же, где живёт правило:

       src/server/dto.nv:68-77
           export fn pii_path_list(d Disclosure, name str, values []str) -> str {
               match d {
                   Disclosure.Loopback => {
                       mut items = []str.new()
                       for v in values { items.push("\"${v}\"") }

   Путь на Windows содержит `\` — ровно тот символ, ради которого `escape` написан
   (`json_test.nv:19`: `escape("C:\\Users") == "C:\\\\Users"`). Соседняя функция
   `pii_path` (dto.nv:57) через дверь идёт, эта — нет; обе в одном файле, в двадцати
   строках друг от друга. И `array_str` (json.nv:204), делающий ровно это правильно,
   уже существует.

## ПОЧЕМУ НЕ ЧИНИТСЯ У НОСИТЕЛЯ

Заменить два места на `quote` — вернуть дерево в состояние «сегодня чисто». Свойство
останется выразимым: `field_raw` (json.nv:117) по построению принимает сырую строку и
нужен для вложенных объектов, `StringBuilder` доступен везде, а тип `str` не помнит,
экранирован он или нет. Класс уже возвращался один раз после починки — по записи в
шапке `json.nv`, — и вернётся тем же способом.

## СЛЕДСТВИЕ, КОТОРОЕ ВИДНО БЕЗ КОМПИЛЯТОРА

`GET /api/export?format=json` c путём или моделью, содержащей `"` или `\`, отдаёт тело,
которое не разбирается как JSON. Приёмка §8 п. 10 (`docs/plans/01.3-api.md:677-679`)
проверяет CSV-выгрузку и число строк; JSON-ветку не проверяет никто —
`src/server/handlers/exporter_test.nv` зовёт `rows_to_json` только на ASCII-строках
без кавычек.
