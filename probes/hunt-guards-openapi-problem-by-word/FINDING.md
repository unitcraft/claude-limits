# lint-openapi.py: «ошибка отвечает Problem» проверяется наличием СЛОВА «Problem»

**КЛЕТКА | lint-openapi.py | К6** (свойство «тело ошибки — RFC 9457» выражено
подстрокой в сериализованном узле).
**Найдено:** охотником 2026-09-08, трек `guards`.
**Номер реестра:** №TBD.

## Обещание — дословно

Текст самого отказа (`scripts/lint-openapi.py:181-182`):

> `bad.append(f"{method.upper()} {path} {code}: does not reference Problem "`
> `           f"(RFC 9457 is the only error shape this API has)")`

и заголовок правила (`:174`): `# --- 3. every error answers with a Problem ---`.

## Какую ФОРМУ судит страж

`scripts/lint-openapi.py:179-180`:

```python
blob = json.dumps(resolve(body, spec)) + json.dumps(body)
if "Problem" not in blob:
```

Подстрока `Problem` в JSON-дампе всего узла ответа — включая `description`, `title`,
`summary` и любой другой текст.

## Путь, который форму удовлетворяет, а требование нарушает

Ответ с кодом 5xx/4xx, у которого тело — не RFC 9457, но слово в тексте есть.
В `gap/spec.json` два носителя на `GET /api/health`:

- `503`: `"description": "Problem: the poller is down (this sentence is the only
  Problem here)"`, тело — `text/plain`, схема `{"type": "string"}`;
- `429`: тело — инлайн-объект `{"message", "retry"}` с `"title": "ProblemLike"`.

## Воспроизведение

```sh
sh probes/hunt-guards-openapi-problem-by-word/cmd.sh
```

**Зазор:**

```
routes in 01.3 section 2: 18 (4 deferred to phase 6), described: 14
OPENAPI LINT: clean
EXIT=0
```

**Контроль (тот же не-RFC-9457 ответ 503, слово убрано из описания):**

```
OPENAPI LINT: FAILED
   GET /api/health 503: does not reference Problem (RFC 9457 is the only error shape this API has)
EXIT=1
```
