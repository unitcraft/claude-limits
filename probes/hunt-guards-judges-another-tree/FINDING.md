# check-page.py и check-fixtures.py: вердикт выносится о ДРУГОМ дереве

**КЛЕТКА | check-page.py + check-fixtures.py | К7** (полуготовый механизм: вход по
умолчанию — абсолютный путь одной машины; зелёный не о том дереве, из которого
запущен).
**Найдено:** охотником 2026-09-08, трек `guards`.
**Номер реестра:** №TBD.

## Обещание — дословно, два адреса

`scripts/check-page.py:11-12`:

```python
web = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                   else r"<repos>\claude-limits\src\web")
```

`scripts/check-fixtures.py:11-12`:

```python
base = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                    else r"<repos>\claude-limits\fixtures")
```

При этом `scripts/check-web.mjs:84` зовёт обоих **без аргумента**:

```js
const r = spawnSync('python', [path.join(here, name), ...args], { cwd: repo, encoding: 'utf8' });
```

— где `args` для `check-page.py` и `check-fixtures.py` пустой список, а `cwd: repo`
на выбор проверяемого дерева не влияет вообще.

## Путь, который форму удовлетворяет, а требование нарушает

Второй рабочий каталог (worktree, клон, копия перед рефакторингом, каталог с другим
именем). Внутри него `python scripts/check-page.py` читает
`<repos>\claude-limits\src\web` — то есть ПЕРВОЕ дерево, — и печатает
вердикт, который читается как вердикт о текущем. Ни одна строка вывода
`check-page.py` не называет каталог, который он смотрел.

`checkout/` в этой пробе — такая копия: в ней внешний шрифт Google, встроенный
`<script>`, ссылка на несуществующий `missing-icon.svg`, неопределённый токен
`--typo-not-defined` и фикстура с живым по форме токеном `sk-ant-api03-…` и почтой
`someone@gmail.com`.

## Воспроизведение

```sh
sh probes/hunt-guards-judges-another-tree/cmd.sh
```

**Зазор (запуск изнутри копии, без аргумента):**

```
tokens defined: 32, tokens used: 31
external references: 0
PAGE GUARD: clean
PAGE EXIT=0
SECRET SCAN: clean
FIXTURES EXIT=0
```

**Контроль (те же файлы, дерево названо явно):**

```
PAGE GUARD: FAILED
   index.html:6: external reference https://fonts.googleapis.com
   index.html: inline <script> — the CSP refuses it
   index.html:11: references missing-icon.svg, which does not exist
   app.css: var(--typo-not-defined) used, not a :root token and set by no script
PAGE EXIT=1

SECRET SCAN: FAILED
   usage/poisoned.json: live-looking token -> sk-ant-api03-ZmFrZWJ1dGx
   usage/poisoned.json: non-example e-mail -> someone@gmail.com
FIXTURES EXIT=1
```

Отличие двух стражей: `check-fixtures.py` хотя бы печатает базу
(`fixtures found: 24 in <repos>\claude-limits\fixtures`), `check-page.py`
не печатает ничего о том, что он смотрел.
