# Набор обязательных заголовков вычисляется дважды, и две копии уже разошлись

Охота 2026-09-08, трек `oracle`. Запускать из корня репозитория: `sh cmd.sh`.

## КЛАСС

**«Какие заголовки обязан нести ЛЮБОЙ ответ» решается в двух функциях с одним именем
и разными телами.** Свойство: ответ, ушедший не через ту дверь, теряет часть
обязательного набора — и заметить это можно только сравнив две функции глазами.
Класс не про `X-Request-Id`: он про то, что набор — не данные, а код, и его две копии.

## ДВЕ ДВЕРИ

    src/server/routes.nv:130
        fn stamp(mut resp ServerResponse, request_id str) -> ServerResponse {
            resp.header("X-Request-Id", request_id)
            resp.header("X-Api-Version", "${API_VERSION}")
            resp.header("Cache-Control", "no-store")
            resp.header("X-Content-Type-Options", "nosniff")
            resp.header("Referrer-Policy", "no-referrer")
            resp.header("X-Frame-Options", "DENY")
            resp
        }

    src/server/static.nv:71
        fn stamp(mut resp ServerResponse) -> ServerResponse {
            resp.header("X-Api-Version", "${API_VERSION}")
            resp.header("X-Content-Type-Options", "nosniff")
            resp.header("Referrer-Policy", "no-referrer")
            resp.header("X-Frame-Options", "DENY")
            resp
        }

Одно имя, один смысл, шесть заголовков против четырёх.

## ВОПРОС, НА КОТОРЫЙ ОНИ ОТВЕЧАЮТ ПО-РАЗНОМУ

«Несёт ли ответ на `GET /` заголовок `X-Request-Id`?»

Требование, `docs/plans/01.3-api.md:680` (§8 п. 11):

    11. Заголовки: у каждого ответа, включая `204`, `304` и ошибки, есть `X-Request-Id` (валидный UUID v7,
        входящий валидный переиспользован), `X-Api-Version`, `Cache-Control`;

Конвенция, `docs/conventions/api.md` §9.1, заголовок раздела и первая строка:

    ### 9.1. Обязательные заголовки каждого ответа

    Включая `204`, ошибки и **отдачу файлов**:

    | `X-Request-Id` | UUID v7 запроса |

Код отвечает «нет» и говорит, что это решение:

    src/server/static.nv:25-27
        // It also means a static response carries no `X-Request-Id`. That is deliberate:
        // the id exists so a person can quote it when an API call misbehaves, and a
        // stylesheet has nothing to quote.

Проверено тестом, который это ЗАКРЕПЛЯЕТ (четыре заголовка, `X-Request-Id` не спрошен):

    src/server/static_test.nv:102-110
        test "a static response carries the security headers and no Server" {
            ro w = serve("/")
            assert(hdr(w, "x-api-version") == "${API_VERSION}")
            assert(hdr(w, "x-content-type-options") == "nosniff")
            assert(hdr(w, "referrer-policy") == "no-referrer")
            assert(hdr(w, "x-frame-options") == "DENY")
            assert(!has_header(w, "server"))
        }

## ОТКЛОНЕНИЕ НЕ ЗАПИСАНО

`docs/plans/01.3-api.md` §9 — таблица отклонений от конвенции, восемь строк D1–D8;
`X-Request-Id` у статики в ней нет (`grep` в `cmd.sh` даёт ноль).
Конвенция, `docs/conventions/api.md` §19, последняя строка: «Отклонение без записи
блокер ревью». Карточка T2.19 (`docs/plans/01.5-work-breakdown.md:545-560`) записала
РАЗНИЦУ КЭША (`no-cache` против `no-store`) и об отсутствующем идентификаторе молчит.

## ПОЧЕМУ НЕ ЧИНИТСЯ У НОСИТЕЛЯ

Дописать `X-Request-Id` в `static.nv:71` — значит привести две копии к согласию НА
СЕГОДНЯ. Набор так и останется кодом в двух местах: третий путь ответа
(страница ошибки для `/` при внутренней ошибке — `docs/plans/01.3-api.md:76`, поток
SSE, `/login` фазы Ф.6) заведёт третью копию, и разойдётся она так же молча. Разница
между двумя копиями сегодня — не только идентификатор: `routes.stamp` жёстко ставит
`Cache-Control: no-store`, `static.stamp` не ставит его вовсе и полагается на
`Static.cache_control("no-cache")` (`src/server/static.nv:61-65`) — то есть один и тот
же обязательный заголовок в двух путях ставится двумя разными механизмами.
