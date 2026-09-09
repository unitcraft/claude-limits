# Закрытый список query-параметров: двери нет, две копии парсера уже разошлись

Охота 2026-09-08, трек `oracle`. Запускать из корня репозитория: `sh cmd.sh`.

## КЛАСС

**Правило «список query-параметров у каждого маршрута ЗАКРЫТ» исполняется каждым
обработчиком по отдельности — а у большинства не исполняется вовсе.** Свойство:
запрос с неизвестным или повторённым не-массивным параметром обязан получить
`400 invalid_parameter` НА ЛЮБОМ маршруте. Синтаксисы, в которых это свойство
сегодня выражено: (1) собственный `check_query` у снимка, (2) собственный
`parse_ask` у выгрузки. Синтаксис «нигде» — у остальных пяти.

Требование дословно, `docs/plans/01.3-api.md:49`:

    Почты и пути живут только в телах. Список query-параметров у каждого маршрута закрыт;
    неизвестный или повторённый не-массивный параметр — `400 invalid_parameter`.

Конвенция, `docs/conventions/api.md` §5.2: «Лишний query-параметр `400 invalid_parameter` (§2.5)».

## ДВЕРИ НЕТ

Кадр, через который проходит каждый запрос, про query не знает:

    src/server/routes.nv:193-199
        fn precheck(req ServerRequest) -> Option[ApiError] {
            if req.body_bytes().len() > MAX_BODY_BYTES { return Some(ApiError.body_too_large()) }
            if req.body_bytes().len() > 0 && !is_json_body(req) {
                return Some(ApiError.unsupported_media_type())
            }
            None
        }

Размер и тип тела — да; закрытый список — нет. При этом `Route` (routes.nv:120) уже
хранит путь и методы, то есть место, где мог бы жить разрешённый набор параметров,
существует и не используется.

Вместо двери — ДВЕ ДОСЛОВНЫЕ КОПИИ разборщика:

    src/server/handlers/snapshot.nv:50-66     fn query_pairs(req ServerRequest) -> [](str, str)
    src/server/handlers/exporter.nv:134-150   fn query_pairs(req ServerRequest) -> [](str, str)

семнадцать строк, совпадающих посимвольно (`diff` в `cmd.sh` даёт пустоту).

## ОНИ УЖЕ ОТВЕЧАЮТ ПО-РАЗНОМУ

Вопрос: «повторённый не-массивный параметр — это отказ?»

Снимок — да, для любого параметра:

    src/server/handlers/snapshot.nv:84-87
        seen += 1
        if seen > 1 {
            return Some(ApiError.invalid_parameter("parameter '${k}' may not repeat"))
        }

Выгрузка — только для трёх из шести, счётчики заведены поимённо:

    src/server/handlers/exporter.nv:181-201
        mut seen_format = 0
        mut seen_unmasked = 0
        mut seen_range = 0
        ...
        } else if k == "range" {
            seen_range += 1

Следствие без запуска компилятора: `GET /api/export?from=A&from=B` и
`GET /api/export?to=A&to=B` проходят молча. `from` и `to` — не массивы
(`docs/plans/01.3-api.md:336`: «`from`, `to` | ISO 8601 `Z`; …»), массивным объявлен
только `login_dir_id` (`:338`). Правило §0 нарушено, стража на это нет.

## ПЯТЬ МАРШРУТОВ НЕ СМОТРЯТ НА QUERY ВООБЩЕ

    src/server/handlers/health.nv:127     fn run(src HealthSource, ctx Ctx)   -- ctx не читается
    src/server/handlers/events.nv:151     fn run(src EventsSource, ctx Ctx)   -- только Last-Event-ID
    src/server/handlers/config.nv:581     fn run_get(src ConfigSource, ctx Ctx)
    src/server/handlers/config.nv:622     fn run_put(src ConfigSource, ctx Ctx)
    src/server/handlers/folders.nv:160    fn run(src ProbeSource, ctx Ctx)
    src/server/handlers/token.nv:151      fn run(src TokenSource, ctx Ctx)

Для `/api/events` план говорит прямо, `docs/plans/01.3-api.md:298`:
«Query-параметров нет». Ноль разрешённых — и ноль проверок; `GET /api/events?email=x`
открывает поток.

## ПОЧЕМУ НЕ ЧИНИТСЯ У НОСИТЕЛЯ

Добавить `check_query` в `health.nv` — значит завести ТРЕТЬЮ копию разбора и третий
поимённый список. Правило по своей природе принадлежит таблице маршрутов (разрешённый
набор — свойство маршрута), а исполняется в теле обработчика; пока это так, каждый
новый маршрут начинается с необязательного решения, и «закрыт» держится вниманием.
Отдельно: именно этот механизм назван в плане защитой от ПДн в URL
(`src/server/handlers/snapshot.nv:76-77`: «it is refused for being unknown, which is
also what protects the rule that no personal data travels in a URL (§0)») — то есть
защита ПДн на пяти маршрутах отсутствует по той же причине.
