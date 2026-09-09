# Форма идентификатора решается пофайлово: три фикстуры по конвенции, четвёртая — своя, и никто не смотрит

**Трек:** oracle-формы (охота по конвенциям). **КЛЕТКА:** страница и инструменты × конвенция
по API §11, конвенция по БД §3.3. **Найдено 2026-09-08 охотником.** Вид находки —
«конвенция требует, механизма нет».

## КЛАСС

**Правило о форме идентификатора не имеет ни одного держателя на стороне данных страницы.**
Свойство: то, что конвенция называет одной формой для одного понятия, в дереве решается тем,
кто пишет очередной файл. Сегодняшний носитель — фикстура, но класс не про неё: под тем же
правилом ходят фикстуры каталогов, примеры в планах, будущие фикстуры экспорта и всё, что
кто-нибудь наберёт руками, — и ни один страж набора не знает слова UUID применительно к данным.

## Норма, дословно

`docs/conventions/api.md:511` (§11 «Форматы значений»):

> | идентификатор | UUID v7 строкой | `"0192a7f0-3c4d-7e21-8a55-0b9c1d2e3f40"` |

`docs/conventions/database.md:120-121` (§3.3 «В API»):

> Идентификатор передаётся строкой UUID в каноническом виде: строчные буквы, дефисы. Версия
> проверяется только у **наших** ключей…

## Замер

```
identifier shapes in the page fixtures:
  fixtures/api/config.json              10 ids   all UUID v7
  fixtures/api/history-7d.json           3 ids   all UUID v7
  fixtures/api/history-folders.json      6 ids   all UUID v7
  fixtures/api/snapshot-mixed.json       9 ids   9 NOT UUID v7: ['acc-0001', 'acc-0002', ...]

who would notice? every checker of the web set, run as check-web.mjs runs it:
  check-fixtures.py        exit=0  'uuid' in its source: False  in its output: False
  check-page.py            exit=0  'uuid' in its source: False  in its output: False
  check-config-fixture.py  exit=0  'uuid' in its source: False  in its output: False
  check-dir-fixtures.py    exit=0  'uuid' in its source: False  in its output: False
  lint-openapi.py          exit=0  'uuid' in its source: True   in its output: False

who reads the fixture that disagrees:
  scripts/test-render.mjs:33   const snap = JSON.parse(readFileSync(... snapshot-mixed.json))
  -> 27 tests of the list renderer run on ids of that shape;
     none of them asserts anything about the shape of an id.
```

Единственное упоминание UUID во всём наборе — `scripts/lint-openapi.py:48`, и это подсказка
`ID_HINTS` для правила про ПДн, а не проверка формы.

## ДВЕРЬ

**Двери нет.** Три места, где форма идентификатора решается независимо:

1. `scripts/make-history-fixture.py:36-38` — `ID_MAIN = "0192a7f0-0000-7000-8000-000000000001"`
   и соседние: генератор выбрал UUID v7 сам, потому что автор так решил;
2. `fixtures/api/snapshot-mixed.json:18` — `"id": "acc-0001"`: файл написан руками, и рука
   решила иначе;
3. `docs/conventions/api.md:511` — норма, у которой в этом дереве нет исполнителя для данных.

Кандидат на дверь существует и уже принимает каталог аргументом — `scripts/check-fixtures.py`
(он и так читает все `*.json` под `fixtures/`), — но правило формы идентификатора в нём не
объявлено.

## ПОЧЕМУ НЕ ЧИНИТСЯ У НОСИТЕЛЯ

Переписать девять идентификаторов в `snapshot-mixed.json` — правка одного файла; следующая
фикстура (для `POST /api/history/search`, которого ещё нет, — `docs/handoff.md:64-66`) будет
написана так же руками и так же ничем не проверена. И обратная сторона, ради которой класс
стоит назвать целиком: `acc-0001` короче и читается глазами, поэтому рука будет выбирать его
снова; пока нет механизма, «починка» держится на памяти автора — а именно это в проекте
считается не приёмкой.

## Воспроизведение

```
sh probes/hunt-conventions-id-shape/cmd.sh
```

Проба только читает: сканирует `fixtures/api/*.json`, запускает пять стражей набора как есть и
печатает, кто из них вообще знает слово UUID. Ничего не пишет.
