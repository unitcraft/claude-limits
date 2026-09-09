# Уровень раскрытия решается вместе с данными, а не там, где виден запрос

Охота 2026-09-08, трек `oracle`, клетка «мои решения в `src/server/`».
Проба не программа: компилятор запрещён брифом. Проба — адреса и дословные цитаты.
Запускать из корня репозитория: `sh cmd.sh`.

## КЛАСС

**«Сколько данному клиенту позволено видеть» — свойство ЗАПРОСА, а решается как поле
записи состояния, которую поставляет источник ДАННЫХ.** Под класс подпадает не только
скрытие путей: тем же полем принимаются два ОТКАЗА В ДОСТУПЕ (`403 loopback_only`),
и любое будущее правило раскрытия унаследует ту же развязку.

Свойство одно. Синтаксисов у него уже два:

1. поле `disclosure Disclosure` в записи состояния — шесть штук;
2. параметр `d Disclosure`, протянутый в рендерер (`render_snapshot(v, d)`,
   `pii_path(d, …)`, `parse_ask(req, d)`).

Ни один из них не связан с соединением, адресом клиента или заголовком.

## ДВЕРИ НЕТ

Единственное место, через которое проходит КАЖДЫЙ запрос и которое видит `ServerRequest`, —
кадр `api()` и запись `Ctx`:

    src/server/routes.nv:83
        export type Ctx value {
            req ServerRequest
            request_id str
            instance str
        }

`Ctx` не несёт уровня раскрытия. Значит хендлер не может его вывести — и получает его
готовым от своего `*Source`:

    src/server/handlers/token.nv:48       disclosure Disclosure     (TokenState)
    src/server/handlers/exporter.nv:50    disclosure Disclosure     (ExportState)
    src/server/handlers/snapshot.nv:35    disclosure Disclosure     (SnapshotState)
    src/server/handlers/health.nv:51      disclosure Disclosure     (HealthState)
    src/server/handlers/config.nv:80      disclosure Disclosure     (ConfigState)
    src/server/handlers/folders.nv:42     disclosure Disclosure     (ProbeState)

Шесть независимых ответов на один вопрос. Седьмой — `RefreshState`
(`src/server/handlers/refresh.nv:27`) поля не имеет вовсе, и `accepted()` печатает почту
безусловно.

Что на этом поле висит НЕ редакция, а контроль доступа:

    src/server/handlers/token.nv:157-160
        match st.disclosure {
            Disclosure.Loopback => {}
            _ => return problem(ApiError.loopback_only(), ctx.request_id, ctx.instance)
        }

    src/server/handlers/exporter.nv:206-211
        if unmasked {
            match d {
                Disclosure.Loopback => {}
                _ => return Ask.Bad(ApiError.loopback_only())
            }
        }

Причём сам `dto.nv` знает, что ось — клиент, и пишет это прямо:

    src/server/dto.nv:40-42
        /// The axis is the CLIENT, not the route: the same `/api/health` answers a
        /// loopback caller with paths and a LAN caller without them (§3.2, §8 п. 8's
        /// "`/api/health` из LAN — без путей и версии").

Ось названа, а вычислителя оси в дереве нет: `grep -rn "Disclosure" src/ | grep -v _test`
не находит ни одной функции вида «запрос → Disclosure».

## ПОЧЕМУ НЕ ЧИНИТСЯ У НОСИТЕЛЯ

Починить один хендлер — значит научить ОДИН `*Source` смотреть на соединение; пять
остальных останутся вправе ответить иначе, а `refresh` — вообще без поля. И пока
значение приходит от источника ДАННЫХ, а не от кадра, корректный `pii_path` всё равно
напечатает путь LAN-клиенту, если провайдер снимка сказал `Loopback`.

## ЧТО ЭТО НЕ

Не «в Ф.6 будет auth». Ф.6 добавляет ПРОВЕРКУ учётных данных; развязка «кто спросил»
и «что отдать» уже принята сегодня, шестью записями, и Ф.6 её не отменяет, а наследует.

## ГДЕ ЗАПИСАНО ТРЕБОВАНИЕ

- `docs/plans/01.3-api.md:198-201` (§3.2, три уровня раскрытия);
- `docs/plans/01.3-api.md:550` (§4: «сериализация в LAN обнуляет поля класса pii-path»);
- `docs/conventions/api.md` §14.1 (абсолютные пути и имена пользователей ОС «допустимы
  только на loopback-интерфейсе локального инструмента»).
