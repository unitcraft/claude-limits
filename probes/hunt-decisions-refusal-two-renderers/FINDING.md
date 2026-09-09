# Отказ превращается в ответ в двух местах, и объявленный инвариант отказа не стоит ни в одном

Охота 2026-09-08, трек `oracle`. Запускать из корня репозитория: `sh cmd.sh`.

## КЛАСС

**«Как выглядит отказ на проводе» решается более чем в одном месте, и правило,
написанное для этого решения исполнимым кодом, не вызывается на пути ответа ни разу.**
Свойство: любой `ServerResponse` со статусом 4xx/5xx, собранный не через одну функцию,
теряет всё, что та функция гарантирует, — и потеря молчалива, потому что тип у обоих
один.

## ПЕРВАЯ ПОЛОВИНА: ДВА РЕНДЕРЕРА

Дверь заявлена и хороша:

    src/server/routes.nv:140-154
        /// Render a refusal as `application/problem+json` (§0).
        ///
        /// The `Retry-After` header and the `retry_after` body field come from ONE value
        /// on the `ApiError`, so a 429 cannot advertise one number and carry another.
        /// Same for `Allow` on a 405.
        export fn problem(e ApiError, request_id str, instance str) -> ServerResponse {
            ro body = to_json(e, request_id, instance)
            mut resp = ServerResponse.bytes(e.status, "application/problem+json; charset=utf-8", body.bytes())
            match e.retry_after {
                Some(n) => { resp.header("Retry-After", "${n}") }
                None => {}
            }
            if e.allow != "" { resp.header("Allow", e.allow) }
            resp
        }

Второй рендерер собирает отказ сам, минуя её:

    src/server/handlers/config.nv:602-608
        fn stale(ctx Ctx, st ConfigState) -> ServerResponse {
            ro e = ApiError.precondition_failed()
            ro body = problem_with_current(e, ctx.request_id, ctx.instance, render_state(st))
            mut r = ServerResponse.bytes(412, "application/problem+json; charset=utf-8", body.bytes())
            r.header("ETag", st.etag)
            r
        }

Три вещи, которые он повторяет своими словами: статус (`412` числом, вместо
`e.status`), `Content-Type` (вторая копия строки), и — молчанием — обе ветки
`Retry-After`/`Allow`. Сегодня `precondition_failed` не несёт ни того, ни другого;
завтра любой отказ, которому понадобится `current` в теле, пойдёт этой же дорогой.

## ВТОРАЯ ПОЛОВИНА: ИНВАРИАНТ НАПИСАН И НЕ ВКЛЮЧЁН

    src/server/errors.nv:233-241
        /// Is this refusal well formed? A 422 without `errors[]` is a refusal the page cannot
        /// render beside a field, which is the only place a person can act on it. A 429 or a
        /// 503 without `Retry-After` fails §8 п. 11.
        export fn well_formed(e ApiError) -> bool {
            if e.status == 422 && e.fields.len() == 0 { return false }
            if (e.status == 429 || e.status == 503) && e.retry_after.is_none() { return false }
            if e.status == 405 && e.allow == "" { return false }
            true
        }

Единственные вызовы `well_formed` во всём дереве — в `src/server/errors_test.nv`
(строки 93, 101, 102, 114, 118, 123), и все — на объектах, собранных этим же тестом.
Ни `problem()`, ни `stale()`, ни `to_json()` его не зовут; `grep` в `cmd.sh` это
показывает одной командой.

Так что это не проверка ответа, а функция с именем проверки. §8 п. 11
(`docs/plans/01.3-api.md:681`: «у каждого `429` и `503` — `Retry-After`») держится
исключительно тем, что конструкторы 429/503 сами кладут секунды
(`errors.nv:133-169`) — то есть НЕ инвариантом, а привычкой пяти функций. Поле
`retry_after` записи `ApiError` (errors.nv:55) открыто на запись, что рядом же и
используется (`e.retry_after = Some(...)`).

## ПОЧЕМУ НЕ ЧИНИТСЯ У НОСИТЕЛЯ

Переписать `stale()` через `problem()` — убрать одного носителя; правило «всякий 4xx/5xx
рождается здесь» так и останется словом в комментарии, а `ServerResponse.bytes(...)`
доступен из любого хендлера и уже так использован. Позвать `well_formed` в `problem()` —
закрыть один из двух путей, оставив второй; а вызвать его в обоих значит признать, что
дверей две.

## ГДЕ ЗАПИСАНО ТРЕБОВАНИЕ

- `docs/plans/01.3-api.md:681` (§8 п. 11): «у каждого `429` и `503` — `Retry-After`»;
- `docs/plans/01.3-api.md:612` (§6): у `422` «`errors[]` обязателен»;
- `docs/conventions/api.md` §9.1: `Retry-After` «при `429` и `503` всегда».
