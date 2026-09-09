# check-web.mjs: набор, не выполнивший ни одного теста, получает `ok`

**КЛЕТКА | check-web.mjs | К7** (пустой замер в одежде успеха: «0 tests» и
`WEB CHECK: clean`).
**Найдено:** охотником 2026-09-08, трек `guards`.
**Номер реестра:** №TBD.

## Обещание шапки — дословно

> `if (!suites.length) {`
> `  // Not "nothing to do": the runner is in the wrong place, or the naming changed.`
> `  console.log('FAILED: no test-*.mjs suites found in scripts/ -- a runner that finds');`
> `  console.log('        nothing must not report success.');`

(`scripts/check-web.mjs:31-35`)

## Какую ФОРМУ судит страж

Правило «нашёл ноль — не рапортуй успех» применено ровно к одному числу: к длине
списка ФАЙЛОВ наборов (`suites.length`, `:27-36`). Число выполненных ТЕСТОВ страж
считает — `total` (`:50-51`) — и печатает, но ни с чем не сравнивает:

```js
console.log(`\n${suites.length} suites (${total} tests) + ${CHECKERS.length} checkers`);
console.log(failed ? `WEB CHECK: FAILED (${failed})` : 'WEB CHECK: clean');
```

(`scripts/check-web.mjs:99-100`)

## Путь, который форму удовлетворяет, а требование нарушает

Набор, который берёт случаи из каталога (переименованные фикстуры, фильтр, не
совпавший ни с чем, glob, переставший что-либо находить): цикл не выполняется ни
разу, `passed` остаётся нулём, код возврата — ноль. Файл набора на месте, значит
`suites.length` не ноль, и защита не срабатывает. `gap/scripts/test-empty.mjs`
именно таков.

## Воспроизведение

```sh
sh probes/hunt-guards-runner-zero-tests/cmd.sh
```

**Зазор:**

```
  ok     test-empty.mjs           0 passed
  ...
1 suites (0 tests) + 8 checkers
WEB CHECK: clean
EXIT=0
```

**Контроль (тот же набор, файл переименован в `suite-empty.mjs`):**

```
FAILED: no test-*.mjs suites found in scripts/ -- a runner that finds
        nothing must not report success.
EXIT=1
```

То есть отсутствие ФАЙЛА краснеет, а отсутствие ТЕСТОВ — нет.
