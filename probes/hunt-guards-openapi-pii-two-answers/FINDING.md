# lint-openapi.py: на вопрос «это персональные данные?» файл отвечает дважды и по-разному

**КЛЕТКА | lint-openapi.py | К4** (два вычисления одного суждения в одном файле).
**Найдено:** охотником 2026-09-08, трек `guards`.
**Номер реестра:** №TBD.

## Два адреса, отвечающие на один вопрос

**Адрес 1 — правило 4, «нет PII и секретов в URL»** (`scripts/lint-openapi.py:43`,
`:189`):

```python
FORBIDDEN_PARAM_NAMES = ("email", "path", "token", "account_id")
...
if where in ("query", "path") and name.lower() in FORBIDDEN_PARAM_NAMES:
```

— точное совпадение с четырьмя именами.

**Адрес 2 — правило 6, «персональные данные помечены»** (`scripts/lint-openapi.py:47`,
`:222`):

```python
PII_HINTS = ("email", "mail", "path", "dir", "folder")
...
if scalar and any(h in leaf for h in PII_HINTS) and not any(h == leaf for h in ID_HINTS):
```

— **подстрока** из пяти подсказок.

Одно и то же имя поля получает два разных ответа в зависимости от того, где оно
встретилось, — и более строгий ответ достаётся телу ответа, а не URL, хотя
комментарий правила 4 объясняет, что URL опаснее: «URLs are logged, cached by
proxies and pasted into chats, so PII in one leaks in every copy»
(`scripts/lint-openapi.py:41-42`).

## Путь, который форму удовлетворяет, а требование нарушает

`gap/spec.json`: у `GET /api/history` появляются три query-параметра
`folder_path`, `user_email`, `access_token`, и те же три имени — свойствами схемы
`components.schemas.Probe`. Один прогон печатает оба ответа сразу.

Отдельно: `access_token` не виден **ни одному** из двух правил — в списке правила 4
только голое `token`, а в `PII_HINTS` слова `token` нет вовсе.

## Воспроизведение

```sh
sh probes/hunt-guards-openapi-pii-two-answers/cmd.sh
```

**Зазор (те же имена, два ответа):**

```
OPENAPI LINT: FAILED
   components.schemas.Probe.folder_path: looks like personal data and carries no x-data-class: pii
   components.schemas.Probe.user_email: looks like personal data and carries no x-data-class: pii
EXIT=1
```

— о `folder_path`, `user_email` и `access_token` **в строке запроса** не сказано
ничего.

**Контроль (те же значения в URL под голыми именами) — правило 4 живо:**

```
OPENAPI LINT: FAILED
   GET /api/history: parameter `path` in query -- URLs are logged, cached and pasted
   GET /api/history: parameter `email` in query -- URLs are logged, cached and pasted
   GET /api/history: parameter `token` in query -- URLs are logged, cached and pasted
EXIT=1
```
