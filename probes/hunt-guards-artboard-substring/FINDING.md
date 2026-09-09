# check-artboard-labels.py: «подпись есть на странице» = её буквы встретились в стоге

**КЛЕТКА | check-artboard-labels.py | К6** (свойство «страница производит подпись»
выражено подстрокой в склейке всех `src/web/*`).
**Найдено:** охотником 2026-09-08, трек `guards`.
**Номер реестра:** №TBD.

## Обещание шапки — дословно

> `A label is accounted for when it is`
>
> `  * produced by the page: found in `src/web/*.{js,html}`, or`

(`scripts/check-artboard-labels.py:24-26`)

и назначение проверки (`:6-10`): три дефекта дня были «a label the design shows and
the page could not produce».

## Какую ФОРМУ судит страж

`scripts/check-artboard-labels.py:78-82`, `:109-111`, `:136`:

```python
def haystack(): parts.append(f.read_text(...)) for *.js, *.html, *.css ... "\n".join(parts)
def normalise(s): return re.sub(r"[\s·→–—.,:;()\[\]]+", " ", s).strip().lower()
if n in page_n: continue          # the page produces it
```

Проверяется вхождение нормализованной подстроки в один общий текст: без границ слов,
без различения кода, комментария и строкового литерала, поверх склейки всех файлов.

## Путь, который форму удовлетворяет, а требование нарушает

Подпись, буквы которой встретились в чужом контексте. Пробное дерево `gap/`: шесть
артбордов показывают семь подписей (`Fable`, `Rounded`, `Mo`…`Sa`), страница не
производит ни одной — в `src/web/app.js` нет ни строкового литерала, ни рендера,
только комментарий и обычные идентификаторы (`addEventListener`, `stops`, `month`,
`setTimeout & friends`). Страж чист.

**Носители в живом дереве** (печатает та же команда, раздел 3): подписи, принятые
как «производимые страницей», у которых **ни одна** строка исходников не содержит их
внутри строкового литерала:

- `Bar style` — совпало с комментарием `* Cell geometry for the "cells" bar style`
  и со свойством `bar.style.width` (`src/web/render.js:304`);
- `Rounded` — единственное совпадение: комментарий `in a rounded panel`
  (`src/web/render.js:229`);
- `Blocks` — комментарий `Only a 429 blocks it.` (`src/web/format.js:178`);
- `Layout` — идентификатор `layoutCells` (`src/web/app.js:15`).

Это четыре подписи одной группы настроек («Layout / Bar style: Rounded | Blocks»).

## Воспроизведение

```sh
sh probes/hunt-guards-artboard-substring/cmd.sh
```

Команда печатает sha256 копии стража рядом с оригиналом (копия нужна потому, что у
стража нет ни аргумента, ни переменной окружения: все пути он выводит из
`__file__`), затем оба состояния, затем разбор живого дерева.

**Зазор:**

```
artboards: 6, chrome labels unaccounted: 0, exceptions: 0 (0 in use)
ARTBOARD LABELS: clean
EXIT=0
```

**Контроль (то же дерево, из `app.js` убраны шумовые совпадения):**

```
artboards: 6, chrome labels unaccounted: 7, exceptions: 0 (0 in use)
ARTBOARD LABELS: FAILED
   StatsView.dc.html: `Fable` is shown by the design and produced by nothing. ...
   StatsView.dc.html: `Rounded` ...
   SettingsPanel.dc.html: `Mo` ... `Tu` ... `We` ... `Fr` ... `Sa` ...
EXIT=1
```

## Что этот разбор НЕ утверждает

Что перечисленные подписи страница не показывает. Часть из них строится
вычислением (`Mo`…`Su` — из `DAYS` в `src/web/settings.js:187-188`), часть приходит
данными (`Fable` есть в `fixtures/usage/normal.json`, и вторая ветвь стража,
`n in data_n`, приняла бы её законно). Утверждение только об основании: страж принял
их по шуму, и то же основание примет подпись, которой на странице нет.
