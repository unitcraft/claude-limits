# check-fixtures.py: секрет в фикстуре, которая не `.json`, не открывается вовсе

**КЛЕТКА | check-fixtures.py | К6** (свойство «фикстура» выражено суффиксом файла;
11 из 35 файлов `fixtures/` не открываются).
**Найдено:** охотником 2026-09-08, трек `guards`.
**Номер реестра:** №TBD.

## Обещание шапки — дословно

> `"""Fixture guard: every usage fixture parses, and none of them carries a secret.`
>
> `FOUND BY ITS OWN REVERSE PROBE (2026-09-07): the first version answered "clean" and`
> `exit 0 when it found ZERO files — green on nothing measured. A check that passes on`
> `an empty set is not a check, so zero files is now a failure.`

(`scripts/check-fixtures.py:1`, `:5-7`)

## Какую ФОРМУ судит страж

`scripts/check-fixtures.py:27-30`:

```python
files = sorted(f for f in base.rglob("*") if f.is_file() and f.suffix == ".json")
files += sorted(f for f in base.rglob(".claude.json"))
files += sorted(f for f in base.rglob(".credentials.json"))
```

Защита «ноль файлов — красный» считает ноль по ЭТОМУ списку, а не по числу файлов в
каталоге: пока есть хоть один `.json`, набор непустой и замер считается состоявшимся.

## Путь, который форму удовлетворяет, а требование нарушает

Фикстура в любом другом формате. В `gap/` лежит один обычный `.json` (чтобы правило
про ноль файлов не срабатывало) и три носителя с одинаковыми секретами:

- `config/poisoned.toml` — той же породы, что пять живых `fixtures/config/*.toml`;
  в схеме конфига есть ключ `access_token` (`fixtures/config/full-valid.toml:29`);
- `dirs/no-login/README.txt` — той же породы, что живой
  `fixtures/dirs/no-login/README.txt`;
- `dirs/default-layout/.claude.json.bak` — имя, названное стражем, плюс один суффикс.

Инвентарь живого дерева (печатается той же командой): **35 файлов в `fixtures/`,
открывается 24**; вне скана — пять `config/*.toml`, пять `README.md`, один
`README.txt`.

## Воспроизведение

```sh
sh probes/hunt-guards-fixture-only-json/cmd.sh
```

**Зазор:**

```
fixtures found: 1 in .../gap
  usage/ordinary.json                                  valid JSON, limits=0 []

SECRET SCAN: clean
EXIT=0
```

**Контроль (те же секреты внутри `.json`):**

```
SECRET SCAN: FAILED
   usage/poisoned.json: live-looking token -> sk-ant-api03-ZmFrZWJ1dGx
   usage/poisoned.json: non-example e-mail -> someone@gmail.com
EXIT=1
```
