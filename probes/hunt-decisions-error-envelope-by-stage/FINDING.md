# Код ошибки выбирается по СТАДИИ разбора, а не по причине — и два обработчика выбирают по-разному

Охота 2026-09-08, трек `oracle`. Запускать из корня репозитория: `sh cmd.sh`.

## КЛАСС

**Внутри `errors[]` причина уже названа точно (`unknown_field`, `wrong_type`,
`not_supported`), а конверт — `code` и `title`, единственное, по чему ветвится клиент —
выбирается по тому, КАКОЙ ПРОХОД нашёл ошибку.** Свойство: две разные неисправности,
найденные одним проходом, получают один `code`; одна и та же неисправность, найденная
в двух обработчиках, получает разные `code`. Информация для правильного выбора есть и
отбрасывается.

Конвенция, `docs/conventions/api.md` §6, строка про `code`:
«машинный код `snake_case` из закрытого каталога продукта; **клиент ветвится только по нему**».

## ДВЕРИ НЕТ: сопоставление «причина поля -> конверт» не живёт нигде

`apply()` возвращает плоский список причин:

    src/server/handlers/config.nv:201-204
        export type Merge value {
            cfg Config
            errors []FieldError
        }
    src/server/handlers/config.nv:493   export fn apply(current Config, body JsonObject) -> Merge

и кладёт в него три разных кода:

    src/server/handlers/config.nv:195   fn unknown(path str) -> FieldError => FieldError.of(path, CODE_UNKNOWN, ...)   // "unknown_field"
    src/server/handlers/config.nv:197   fn wrong_type(path str, want str) -> FieldError => FieldError.of(path, "wrong_type", ...)
    src/server/handlers/config.nv:473   errs.push(FieldError.of("folders[${i}].id", "not_supported", ...))

Конверт выбирается ОДНОЙ строкой, одинаковой для всех трёх:

    src/server/handlers/config.nv:634-636
        if merged.errors.len() > 0 {
            return problem(ApiError.extra_forbidden(merged.errors), ctx.request_id, ctx.instance)
        }

`extra_forbidden` — это `422` с заголовком `"Unknown field"`
(`src/server/errors.nv:198-202`).

## ЧТО ЭТО ДАЁТ

`PUT /api/config` с телом `{"poll":{"interval_sec":"120"}}` — ключ существует, тип
значения неверен — отвечает `code: "extra_forbidden"`, `title: "Unknown field"`.

План различает эти два случая явно, `docs/plans/01.3-api.md:458-459` (§3.8):

    - `422 extra_forbidden` — ключ, которого нет в дереве настроек (`errors[].field` в точечной
      нотации: `poll.intervalSec`); `422 invalid_config` — значение вне правил, `errors[]` по одному на

Тест это НЕ ловит — он смотрит внутрь `errors[]`, а не на конверт:

    src/server/handlers/config_test.nv:271-278
        test "a value of the wrong type is refused with the field named" {
            ro b = body_of(serve(st, put_req(st.etag, "{\"poll\":{\"interval_sec\":\"120\"}}")))
            assert(b.contains("\"field\":\"poll.interval_sec\""))
            assert(b.contains("\"code\":\"wrong_type\""))
        }

Оба ассерта проходят и на верном, и на неверном конверте: в теле есть ДВА поля `code` —
корневое (`errors.nv:258`) и внутри `errors[]` (`errors.nv:267`), — а `contains` не
различает, какое из них совпало.

## ДВА МЕСТА ОТВЕЧАЮТ ПО-РАЗНОМУ НА ОДИН ВОПРОС

Вопрос: «поле известно, но его тип неверен — какой это конверт?»

`refresh` отвечает `invalid_request`:

    src/server/handlers/refresh.nv:92-95
        if extra.len() > 0 { return Ask.Bad(ApiError.extra_forbidden(extra)) }
        if wrong_type {
            return Ask.Bad(ApiError.invalid_request([FieldError.of(ONLY_FIELD, "not_a_string", "account_id must be a string")]))
        }

`config` отвечает `extra_forbidden`:

    src/server/handlers/config.nv:634-636   (выше)

Те же две ветки, разведённые в `refresh` (92/94), в `token`
(`src/server/handlers/token.nv:90/92`) и в `folders`
(`src/server/handlers/folders.nv:88/90`), в `config` слиты в одну.

## ПОЧЕМУ НЕ ЧИНИТСЯ У НОСИТЕЛЯ

Поправить строку 635 — значит принять решение в четвёртый раз. Соответствие «код поля →
конверт» нигде не записано: ни `errors.nv`, где живёт закрытая таблица кодов
(`all_codes()`, errors.nv:216), ни `FieldError` (errors.nv:66) о конверте ничего не
знают. Пятый разборщик тела (история, сессия — §3.6, §3.13) выберет конверт заново,
потому что больше выбирать не по чему.
