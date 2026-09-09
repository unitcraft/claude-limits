# check-page.py: встроенный код проходит в четырёх формах из пяти

**КЛЕТКА | check-page.py | К6** (энфорс на перечислении синтаксических форм).
**Найдено:** охотником 2026-09-08, трек `guards`.
**Номер реестра:** №TBD.

## Обещание шапки — дословно

> `* an inline <style> or <script> — the CSP refuses them and the page renders blank;`

(`scripts/check-page.py:6`)

## Какую ФОРМУ судит страж

`scripts/check-page.py:36-39`:

```python
if re.search(r"<style[\s>]", markup):
if re.search(r"<script(?![^>]*\bsrc=)[^>]*>", markup):
```

Две регулярки без `re.IGNORECASE`, и «у скрипта есть src» выражено как `\bsrc=`.

## Путь, который форму удовлетворяет, а требование нарушает

Четыре носителя в `web-gap/index.html`, все — встроенный код, который CSP
`script-src 'self'` отвергает:

1. `<script data-src="app.js">document.title = 'inline code ran';</script>` —
   в `data-src` перед `src` стоит `-`, то есть граница слова, поэтому
   `\bsrc=` срабатывает и негативный просмотр вперёд отменяет проверку;
2. `<SCRIPT>...</SCRIPT>` — имена тегов в HTML регистронезависимы, регулярка нет;
3. `<STYLE>...</STYLE>` — то же самое для стиля;
4. `<button onclick="...">` — встроенный обработчик; CSP отвергает его так же,
   как `<script>`, а страж про атрибуты-обработчики не знает вовсе.

## Воспроизведение

```sh
sh probes/hunt-guards-page-inline-script/cmd.sh
```

**Зазор (`web-gap`, четыре встроенных блока):**

```
tokens defined: 2, tokens used: 2
external references: 0
PAGE GUARD: clean
EXIT=0
```

**Контроль (`web-control`, тот же код в канонической форме) — правило живо:**

```
PAGE GUARD: FAILED
   index.html: inline <style> — the CSP refuses it
   index.html: inline <script> — the CSP refuses it
EXIT=1
```
