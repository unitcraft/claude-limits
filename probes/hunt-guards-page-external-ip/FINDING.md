# check-page.py: внешний ресурс по IP-адресу — «external references: 0»

**КЛЕТКА | check-page.py | К6** (энфорс на перечислении форм: хост обязан
оканчиваться буквенным доменом).
**Найдено:** охотником 2026-09-08, трек `guards`.
**Номер реестра:** №TBD.

## Обещание шапки — дословно

> `Guard for the page frame: no external resources, no inline code, tokens defined.`
>
> `  * an external URL — forbidden by 01.1 §0 and blocked by the CSP, and the artboard`
> `    this page is modelled on DOES pull fonts from Google, so copying is a live risk;`

(`scripts/check-page.py:1`, `:4-5`)

## Какую ФОРМУ судит страж

`scripts/check-page.py:20`:

```python
EXTERNAL = re.compile(r"""(?:https?:)?//(?!\s)[A-Za-z0-9.-]+\.[A-Za-z]{2,}""")
```

Хост обязан кончаться точкой и **буквами** — то есть доменным именем. Вторая
половина класса (`:49-55`, «локальная ссылка обязана существовать») внешние адреса
пропускает сама: `if ref.startswith(("http:", "https:", "//", ...)): continue`.

## Путь, который форму удовлетворяет, а требование нарушает

Адрес по IP: у точечной четвёрки нет буквенного домена, поэтому регулярка не
совпадает, а проверка существования файла такие ссылки не смотрит. В `web-gap`:

- `<script src="http://93.184.216.34/tracker.js"></script>` — страница грузит
  сторонний скрипт;
- `<link rel="preconnect" href="https://198.51.100.7:8443/">`;
- в `app.css`: `src: url(http://203.0.113.9/inter.woff2)` — тот самый шрифт со
  стороны, ради которого правило написано. (Отдельно: `url(...)` в CSS не смотрит
  и проверка локальных ссылок — она читает только `href|src` в разметке.)

## Воспроизведение

```sh
sh probes/hunt-guards-page-external-ip/cmd.sh
```

**Зазор:**

```
tokens defined: 2, tokens used: 2
external references: 0
PAGE GUARD: clean
EXIT=0
```

Строка `external references: 0` напечатана над страницей с тремя внешними
обращениями.

**Контроль (тот же скрипт с именованного хоста) — правило живо:**

```
external references: 1
PAGE GUARD: FAILED
   index.html:13: external reference http://cdn.example.com
EXIT=1
```
