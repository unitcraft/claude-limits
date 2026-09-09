# `instance` в теле отказа — конкретный присланный путь, а оба документа требуют шаблон

Охота 2026-09-08, трек `oracle`. Запускать из корня репозитория: `sh cmd.sh`.

## КЛАСС

**Строка, пришедшая от клиента, становится значением поля в теле ответа.** Свойство, а
не опечатка: правило записано СЕНТИНЕЛОМ (`instance == ""` означает «подставь то, что
попросили»), поэтому оно распространяется на любой будущий вызов `api("")`, а не только
на тот один, ради которого написано.

## ДВЕРЬ ЕСТЬ, И РЕШЕНИЕ В НЕЙ ПРОТИВОРЕЧИТ ОБОИМ ДОКУМЕНТАМ

    src/server/routes.nv:204-206
        fn run_api(instance str, h ApiHandler, req ServerRequest) Time Random -> ServerResponse {
            ro rid = request_id_of(req)
            ro inst = if instance == "" { req.path() } else { instance }

Одно место, через которое проходит каждый ответ; ровно здесь и решается, что попадёт в
`instance`. Носитель сегодня один — глобальный 404:

    src/server/routes.nv:286-288
        /// The global 404. Mounted through `api("")`, so its `instance` is the path that
        /// was actually asked for — there is no template for a route that does not exist.
        export fn not_found_handler() -> Handler => api("", fn(ctx Ctx) -> ServerResponse => refuse_unknown(ctx))

и он же — единственный ответ, который получает любой неизвестный путь под `/api/`
(`src/server/static.nv:110-111` направляет туда всё, что начинается на `/api/`).

## ЧТО ГОВОРЯТ ДОКУМЕНТЫ

`docs/plans/01.3-api.md:72` (§0):

    `code` — из закрытого списка §6, `type` — `urn:claude-limits:problem:` + `code` с дефисами,
    `instance` — шаблон пути (`/api/config`, `/api/history/search`), `request_id` — как в заголовке

`docs/conventions/api.md` §6, строка таблицы, вместе с причиной:

    | `instance` | всегда | **шаблон** пути операции (`/api/v1/issues/{id}`), не конкретный URL: конкретный путь мог бы содержать идентификатор, а тело ошибки показывается пользователю и уходит в поддержку |

Там же, §5.8: «клиентское значение не становится путём, заголовком, ключом объекта в
хранилище или частью `type` ошибки».

Код это знает и записывает как решение:

    src/server/routes.nv:86-90
        /// The path TEMPLATE (`/api/config`), which is what `instance` means in
        /// §0 — not the concrete path, so two requests to one route report one
        /// `instance`. For the 404 fallback there is no template, and the concrete
        /// path is used instead.

## ЧТО ЭТО ДАЁТ

`GET /api/ops@example.org` — путь не зарегистрирован, значит fallback, значит
`"instance":"/api/ops@example.org"` в теле problem+json, в том же теле, которое §6 прямо
называет показываемым пользователю и уходящим в поддержку. Правило §0
(`docs/plans/01.3-api.md:43-44`: «**В URL нет персональных данных**») связывает НАС, а не
клиента: клиент волен положить в URL что угодно, и сервер это перепечатывает.

Тест закрепляет текущее поведение, сверяя `instance` с присланным путём:

    src/server/routes_test.nv:100-113
        test "an unknown /api/x is 404 problem+json with type, code, request_id, instance" {

## ПОЧЕМУ НЕ ЧИНИТСЯ У НОСИТЕЛЯ

Носитель — не строка кода, а сентинел: `api("")` доступен любому монтированию, и
следующий, кому «нет шаблона» (маршрут-заглушка Ф.6, `/login`, ветка статики), получит
эхо молча и бесплатно. Отклонение в §9 плана 01.3 (таблица D1–D8) не записано, а
конвенция §19 требует записи для любого отклонения.

## ЧТО ЭТО НЕ

Не «инъекция»: `to_json` пропускает значение через `escape` (`errors.nv:256`,
`json.nv:51`), тело остаётся валидным JSON. Класс — про то, ЧТО отражено, а не про то,
как оно закодировано.
