# check-fixtures.py: правило «real user path» не может сработать ни на одном файле,
# который страж читает

**КЛЕТКА | check-fixtures.py | К7** (правило перечислено, но недостижимо: выглядит
как замер, не меряет).
**Найдено:** охотником 2026-09-08, трек `guards`.
**Номер реестра:** №TBD.

## Обещание шапки — дословно

> `"""Fixture guard: every usage fixture parses, and none of them carries a secret.`

(`scripts/check-fixtures.py:1`)

И третья строка списка секретов (`scripts/check-fixtures.py:22`):

```python
(re.compile(r"[A-Za-z]:\\Users\\(?!me\b)[A-Za-z]"), "real user path"),
```

## Какую ФОРМУ судит страж

Регулярка ищет **один** обратный слэш между `C:` и `Users`, и применяется к
СЫРОМУ тексту файла (`raw = f.read_text(...)`, `:37`, `rx.search(raw)`, `:50`).

## Путь, который форму удовлетворяет, а требование нарушает

Внутри JSON путь Windows иначе не записывается: `C:\Users\Evgeniy` в файле выглядит
как `C:\\Users\\Evgeniy` — **два** слэша, и регулярка не совпадает. Вариант с
прямыми слэшами (`C:/Users/Evgeniy`) не совпадает тем более. Единственное
написание, которое регулярка ловит, — с одним слэшем — не является валидным JSON:
`json.loads` падает раньше, и файл попадает в отчёт как `INVALID JSON`, а не как
секрет.

То есть класс «реальный пользовательский путь» на множестве сканируемых файлов
(`*.json`, `.claude.json`, `.credentials.json`) недостижим. Носители в дереве:
`fixtures/dirs/**/.claude.json` — именно те файлы, где путь и живёт.

## Воспроизведение

```sh
sh probes/hunt-guards-fixture-windows-path/cmd.sh
```

**Зазор:**

```
fixtures found: 2 in .../gap
  usage/real-user-path-slashes.json                    valid JSON, limits=0 []
  usage/real-user-path.json                            valid JSON, limits=0 []

SECRET SCAN: clean
EXIT=0
```

**Контроль:**

```
SECRET SCAN: FAILED
   usage/live-token.json: live-looking token -> sk-ant-api03-ZmFrZWJ1dGx
   usage/single-backslash.json: INVALID JSON — Invalid \escape: line 3 column 20 (char 160)
EXIT=1
```

Контроль показывает обе половины: правило про токен живо, а единственное написание
пути, которое ловится, ловится не как секрет.
