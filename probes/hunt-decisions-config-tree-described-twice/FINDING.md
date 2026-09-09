# Дерево настроек описано дважды — рендерером и мержером — и они уже разошлись в трёх местах

Охота 2026-09-08, трек `oracle`. Запускать из корня репозитория: `sh cmd.sh`.

## КЛАСС

**Форма одного ресурса записана в коде два раза: один раз тем, что его ОТДАЁТ, второй —
тем, что его ПРИНИМАЕТ.** Свойство: никакой механизм не связывает две записи, поэтому
документ, полученный из `GET`, не обязан приниматься `PUT`-ом того же ресурса — и это
никак не проявляется, пока кто-нибудь не попробует.

Конвенция называет ровно это дефектом сервера, `docs/conventions/api.md` §18, первая
строка: «расхождение спецификации с поведением дефект сервера»; и §10.3 строит
идемпотентность `PUT` на том, что клиент читает ресурс и возвращает его обратно.

## ДВА ОПИСАНИЯ

    src/server/handlers/config.nv:176-188   export fn render_state(st ConfigState) -> str   // что отдаём
    src/server/handlers/config.nv:493-520   export fn apply(current Config, body JsonObject) -> Merge   // что принимаем

Между ними нет ни общего типа, ни общей таблицы имён: `render_config` перечисляет ключи
литералами (`config.nv:122-173`), `merge_*` перечисляет их своими литералами
(`config.nv:261-490`).

## ТРИ МЕСТА, ГДЕ ОНИ УЖЕ НЕ СОВПАДАЮТ

**1. `folders` лежит на разных уровнях.**

План, `docs/plans/01.3-api.md:412-413` — ветка внутри `config`:

      "config": {
        "folders": [ { "id": "…", "path": "C:/accounts", "kind": "parent", ...

`apply` читает её оттуда же — как ветку патча дерева `config`:

    src/server/handlers/config.nv:519-520
        if k == "folders" {
            merge_folders(c, v, errs)

`render_state` кладёт её РЯДОМ с `config`, на корень ответа:

    src/server/handlers/config.nv:181-187
        object([
            field_str("etag", st.etag),
            pii_path(st.disclosure, "path", st.path),
            field_bool("portable", st.portable),
            field_raw("folders", array(folders)),
            field_raw("config", render_config(st.disclosure, st.cfg)),
            field_raw("accounts_found", array(found)),

**2. `access_token_set` и `tls_key_set` отдаются и не принимаются.**

    src/server/handlers/config.nv:145-147   (render)
        field_bool("access_token_set", c.server.access_token != ""),
        field_str_or_null("tls_cert", c.server.tls_cert),
        field_bool("tls_key_set", c.server.tls_key != ""),

    src/server/handlers/config.nv:331-347   (merge принимает bind, port, allow_lan,
                                             access_token, tls_cert, tls_key)
        } else {
            errs.push(unknown("server.${k}"))
        }

Следствие, читаемое без запуска: клиент, сделавший `GET /api/config`, взявший поддерево
`config` и вернувший его `PUT`-ом (та самая последовательность, на которой конвенция
§10.3 строит идемпотентность), получает `422` с двумя `errors[]` —
`unknown setting 'server.access_token_set'` и `unknown setting 'server.tls_key_set'`.

**3. Имена полей `server` расходятся с планом ровно там же.**

`docs/plans/01.3-api.md:419` и `:430-431`:

    "server": { "bind": "127.0.0.1", "port": 7391, "allow_lan": false, "access_token_set": false, "tls_cert": null, "tls_key": null, "tls_fingerprint": null },
    ...
    `access_token` не отдаётся, только `access_token_set`; `tls_key` — только `true`/`null` наличия;
    `tls_fingerprint` — SHA-256 сертификата для сверки на телефоне.

Код отдаёт `tls_key_set` (булево с другим именем) и не отдаёт `tls_fingerprint` вовсе.
Ни один тест не сверяет набор ключей ответа с планом — `config_test.nv:120-135`
проверяет присутствие отдельных подстрок, а не состав.

## ПОЧЕМУ НЕ ЧИНИТСЯ У НОСИТЕЛЯ

Перенести `folders` внутрь `config` и переименовать `tls_key_set` — три правки, после
которых два описания снова совпадут НА СЕГОДНЯ и продолжат жить порознь. Следующее поле
настроек добавляется в `Config`, в `render_config` и в `merge_*` — три места, из которых
компилятор проверяет одно; пропуск любого из двух остальных даёт либо поле, которое
нельзя записать, либо поле, которое нельзя прочитать, и обнаруживается это у клиента.

Отдельно: механизм, который по замыслу ловил бы такое, назван в плане и не построен —
`openapi.json` генерируется Polaris по типизированным маршрутам
(`docs/plans/01.3-api.md:508-509`), а карточка T2.18
(`docs/plans/01.5-work-breakdown.md:506`) стоит «ЧАСТИЧНО … самого описания НЕТ».
Пока его нет, единственный судья формы ответа — рукописный рендерер.
