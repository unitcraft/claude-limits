# check-page.py: опечатку в токене оправдывает КОММЕНТАРИЙ в app.js

**КЛЕТКА | check-page.py | К6** (свойство «токен кто-то реально задаёт» выражено
грепом по тексту `--имя:` во всём файле).
**Найдено:** охотником 2026-09-08, трек `guards`.
**Номер реестра:** №TBD.

## Обещание шапки — дословно

> `#    So: a var() is accepted when the name is a root token, or when some script`
> `#    actually sets it (`setProperty('--x'` / `--x: ` inside a style string). A name`
> `#    that is neither is still the typo this check exists for.`

(`scripts/check-page.py:68-70`)

## Какую ФОРМУ судит страж

`scripts/check-page.py:78-79`:

```python
set_by_script |= set(re.findall(r"setProperty\(\s*['\"](--[a-z0-9-]+)", text))
set_by_script |= set(re.findall(r"`?\s*(--[a-z0-9-]+)\s*:", text))
```

Вторая строка ищет `--имя:` **где угодно в файле** — в строке стиля, в
комментарии, в куске документации, в вырезанном коде.

## Путь, который форму удовлетворяет, а требование нарушает

`web-gap/app.css` использует `var(--acent)` — опечатка в `--accent`, свойство
молча красит ничем. `web-gap/app.js` не вызывает `setProperty` и не строит ни одной
строки стиля; в нём есть только фраза:

```
// the accent colour was --acent: #d29922 in the mock before the token was renamed.
```

Этого достаточно, чтобы имя попало в `set_by_script`.

Замер на живом дереве (для сведения окна): сегодня из трёх нерутовых имён
`--line` держится **только** этой второй регуляркой, но её носитель — настоящая
строка стиля `` `--line: ${band.color}` `` (`src/web/stats.js:120`), так что
ложного оправдания в дереве сейчас нет.

## Воспроизведение

```sh
sh probes/hunt-guards-page-token-by-comment/cmd.sh
```

**Зазор:**

```
tokens defined: 3, tokens used: 3
external references: 0
PAGE GUARD: clean
EXIT=0
```

**Контроль (та же вёрстка, фраза из комментария убрана):**

```
PAGE GUARD: FAILED
   app.css: var(--acent) used, not a :root token and set by no script
EXIT=1
```
