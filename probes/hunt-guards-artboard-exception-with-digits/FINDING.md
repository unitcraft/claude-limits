# check-artboard-labels.py: подпись с цифрой нельзя внести в исключения — отказ с ложной причиной

**КЛЕТКА | check-artboard-labels.py | К7** (полуготовый механизм: «честная
половина» недоступна ровно для тех подписей, которые роняет фильтр цифр; отказ
сообщает причину, которая не соответствует действительности).
**Найдено:** охотником 2026-09-08, трек `guards`.
**Номер реестра:** №TBD.

## Обещание шапки — дословно

> `The cost of that filter, stated rather than hidden: a chrome label that CONTAINS a`
> `` number is invisible to this check. `samples every 5 min · kept 30 days` is exactly ``
> `such a label and exactly such a gap; it was found by hand and is in the exceptions`
> `file with that note.`

(`scripts/check-artboard-labels.py:18-21`)

и о самом файле исключений (`:34-36`):

> `The exceptions file is checked too. An entry that no longer matches any artboard`
> `label is stale, and a stale exception hides the next gap instead of naming one`

## Какую ФОРМУ судит страж

`scripts/check-artboard-labels.py:130-131` и `:148`:

```python
for label in labels_of(art):
    if re.search(r"\d", label):
        continue                       # rendered data, not chrome -- see the header
...
stale = [l for l in exceptions if l not in used_exceptions]
```

`used_exceptions` пополняется только внутри цикла, из которого подписи с цифрами
исключены раньше. Значит запись файла исключений, содержащая цифру, **никогда** не
попадёт в «использованные» — и всегда будет объявлена устаревшей.

## Путь, который форму удовлетворяет, а требование нарушает

Записать в файл исключений ровно ту подпись, которую шапка приводит как пример
осознанного пробела. В `gap/` артборд `StatsView.dc.html` показывает
`samples every 5 min · kept 30 days`, файл исключений содержит эту строку дословно
с причиной. Страж краснеет и называет причину, которой нет:

```
   artboard-exceptions.txt: `samples every 5 min · kept 30 days` matches no artboard label any more -- a stale exception hides the next gap instead of naming one
```

Подпись есть в артборде дословно; «matches no artboard label any more» — неверно.

В живом дереве этот пример поэтому и лежит в файле исключений **комментарием**
(`docs/design/artboard-exceptions.txt:58-63`, блок `// And one the checker CANNOT
see…`), а не записью: записью он бы красил гейт. То есть механизм «решение
записывается рядом с предметом» для подписей с цифрой не работает.

## Воспроизведение

```sh
sh probes/hunt-guards-artboard-exception-with-digits/cmd.sh
```

**Зазор:**

```
artboards: 6, chrome labels unaccounted: 0, exceptions: 1 (0 in use)
ARTBOARD LABELS: FAILED
   artboard-exceptions.txt: `samples every 5 min · kept 30 days` matches no artboard label any more -- ...
EXIT=1
```

**Контроль (те же два файла, из подписи убраны цифры):**

```
artboards: 6, chrome labels unaccounted: 0, exceptions: 1 (1 in use)
ARTBOARD LABELS: clean
EXIT=0
```
