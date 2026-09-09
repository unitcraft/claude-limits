# check-page.py: точка остаётся ЗЕЛЁНОЙ во всех состояниях — страж чист

**КЛЕТКА | check-page.py | К6** (правило о ЦВЕТЕ проверяется наличием селектора,
а не цветом).
**Найдено:** охотником 2026-09-08, трек `guards`.
**Номер реестра:** №TBD.

## Обещание шапки — дословно

> `# "with the server stopped the dot is grey ... once it starts, green". test-live.mjs`
> `# holds the WORD the dot says; this holds the COLOUR, because a green dot over a dead`
> `# backend is the most misleading state this page has, and no js test can see a stylesheet.`

(`scripts/check-page.py:86-88`)

## Какую ФОРМУ судит страж

`scripts/check-page.py:89-98` — три текстовых проверки:

```python
dot = re.search(r"\.live-dot\s*\{([^}]*)\}", css)      # правило есть
elif "var(--live)" not in dot.group(1):                # красится через var(--live)
    re.search(r'\.live\[data-state="%s"\][^{]*\.live-dot' % mode, css)  # селектор есть
```

Ни одна не смотрит, **какой цвет** назначает найденное правило и переживает ли оно
каскад.

## Путь, который форму удовлетворяет, а требование нарушает

`web-gap/app.css`: селекторы `polling` и `connecting` присутствуют — и красят точку
`var(--live)`, то есть зелёным. Плюс более специфичное правило
`body .live .live-dot { background: var(--live) !important; }` перебивает любое из
них. Страница показывает зелёную точку над мёртвым бэкендом — состояние, которое
сама шапка называет «the most misleading state this page has».

## Воспроизведение

```sh
sh probes/hunt-guards-page-dot-stays-green/cmd.sh
```

**Зазор:**

```
tokens defined: 2, tokens used: 1
external references: 0
PAGE GUARD: clean
EXIT=0
```

**Контроль (правило `polling` удалено) — проверка жива, и её текст описывает ровно
то, что в зазоре и происходит:**

```
PAGE GUARD: FAILED
   app.css: nothing repaints the dot for data-state="polling" -- it would stay green while the backend is unreachable
EXIT=1
```
