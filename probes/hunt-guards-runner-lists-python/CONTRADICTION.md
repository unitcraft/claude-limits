# check-web.mjs говорит о себе две противоположные вещи в одном файле

**Это НЕ находка, а противоречие двух мест.** Выбирать между ними — не дело
охотника; каталог существует ради того, чтобы окно видело, какое из двух
утверждений реализовано в коде.

## Место 1 — шапка, `scripts/check-web.mjs:11-15`

> `// TWO PROPERTIES IT HAS TO HAVE, both learned the hard way today:`
> `//`
> `//   * It discovers suites, never lists them. A runner with a hand-written list`
> `//     silently measures less every time a suite is added -- it stays green while`
> `//     covering fewer files, which is worse than not running at all.`

## Место 2 — комментарий к `CHECKERS`, `scripts/check-web.mjs:67-71`

> `// The python checkers, judged the same way as the suites: by EXIT CODE, never by`
> `// the verdict they print. Listed rather than globbed on purpose -- scripts/ also`
> `` // holds `claude_limits.py`, `diff_with_probe.py` and three `make-*.py` generators, ``
> `// which are not checks and would fail as ones. The cost of the list is that a new`
> `// checker has to be added here; that is a real step and it is not hidden.`

## Что реализовано в коде — замер

`gap/` — дерево, в `scripts/` которого лежит **красный** `check-newguard.py`
(печатает `NEW GUARD: FAILED`, выходит с кодом 1). `control/` — тот же отказ,
записанный как `test-newguard.mjs`.

```sh
sh probes/hunt-guards-runner-lists-python/cmd.sh
```

```
--- GAP: a failing check-*.py sits in scripts/ ---
1 suites (2 tests) + 8 checkers
WEB CHECK: clean
EXIT=0
--- CONTROL: the same failure named test-*.mjs ---
  FAIL   test-newguard.mjs        0 passed, SOME FAILED
2 suites (2 tests) + 8 checkers
WEB CHECK: FAILED (1)
EXIT=1
```

То есть реализовано место 2 для python-половины и место 1 для `.mjs`-половины.
За время этой охоты список `CHECKERS` был дополнен руками дважды (сначала
`check-citations.py`, затем четыре ранее не запускавшихся `check-*.py`), что и
показывает цену, о которой говорит место 2.
