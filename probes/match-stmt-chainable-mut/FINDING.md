# `match` в позиции оператора + цепочечный `mut @`-метод в ветвях → C не компилируется

**Приоритет:** К1 (принято чекером, отвергнуто C-компилятором — сборка невозможна).
**Найдено:** 2026-09-08, при написании `src/server/routes.nv` (claude-limits, T2.11).
**Номер реестра:** №TBD.

## Класс

`match`, использованный как **оператор** (значение не берётся), всё равно
материализует слот результата — и объявляет его **по значению**. Если ветви зовут
цепочечный метод `mut @` (`fn T mut @m(...) -> @`), тот в C возвращает **указатель**.
Слот и значение расходятся, и это видит только C-компилятор: `nova check` зелёный.

Класс — не «MethodRouter» и не «Polaris»: несущий признак — сочетание
*match-в-позиции-оператора* и *ветви типа `@`*. Любой цепочечный API (а `@`-возврат
— канон D409) под таким match даёт то же самое.

## Проба

```
cd <repos>/claude-limits
./nova.sh check probes/match-stmt-chainable-mut/src/match_stmt_chainable_mut.nv
NOVA_CACHE=0 ./nova.sh build probes/match-stmt-chainable-mut/src/match_stmt_chainable_mut.nv \
    -o probes/match-stmt-chainable-mut/probe.exe
```

`check` → `PASS: 1 FAIL: 0`. `build` → две ошибки C:

```
match_stmt_chainable_mut.c:5490:23: error: assigning to 'NovaValue_Box'
    from incompatible type 'NovaValue_Box *'; dereference with *
 5490 |         _nv_match_481 = Nova_Box_method_bump(&(b));
```

Тот же текст на настоящем коде (`src/server/routes_test.c:55448`), где ветви были
`mr.get(h)` / `mr.post(h)` на `MethodRouter` из Polaris:

```
error: assigning to 'NovaValue_MethodRouter' from incompatible type
    'NovaValue_MethodRouter *'; dereference with *
```

Сгенерированный C виден прямо:

```c
NovaValue_MethodRouter _nv_match_7185;                     /* слот ПО ЗНАЧЕНИЮ */
if (... tag == NOVA_TAG_HttpMethod_Get) {
    _nv_match_7185 = Nova_MethodRouter_method_get(&(mr), h);   /* вернул УКАЗАТЕЛЬ */
}
```

## Проба в обе стороны

В файле три контроля, каждый отличается от `failing` **ровно одним**:

| форма | отличие | результат |
|---|---|---|
| `failing` | — | **CC-FAIL**, 2 ошибки |
| `control_unit_arms` | ветви зовут `-> ()`-метод, не `-> @` | собралось, печатает `1` |
| `control_no_match` | тот же `-> @`-метод, но без match | собралось, печатает `1` |
| `control_if_chain` | тот же `-> @`-метод под `if`, не под match | собралось, печатает `1` |

Обратный прогон: убрал `failing` — сборка проходит, три контроля выполняются и дают
`1 1 1`. Значит краснота держится именно на сочетании, а не на одном из ингредиентов.

## Обход, применённый в claude-limits

`src/server/routes.nv`, `mount`: ветви match зовут unit-возвращающие обёртки вместо
цепочечных методов напрямую. Исчерпаемость по вариантам `HttpMethod` при этом
сохраняется — её проверяет компилятор, — а слот результата у match становится
единичным.

## Чего проба НЕ утверждает

Не проверено, зависит ли краснота от того, что `match` стоит внутри `for`. В обоих
наблюдениях он там и стоял, но контроль на это не ставился: `control_if_chain` меняет
match на `if`, а не выносит из цикла. Тому, кто будет чинить, стоит начать с места,
где для match в позиции оператора выбирается тип слота.
