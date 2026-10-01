# Отказ git при разрешении зависимостей: `nova build` не говорит причину

**Замер 2026-10-02, 01:05, nova main bacdefa12.** Найдено приёмкой T4.4: свежий клон с
пустым кэшем пакетов в глубоком каталоге не собрался, и сообщение не дало ни одной зацепки.
Реестр 221.1 **№1592**, К3 (номер дал интегратор 01:16).

## Что видит пользователь

```
error: dependency resolution (nova.lock.toml): резолв версий git-зависимостей:
  checkout commit `c4c387fd…` git-зависимости `https://github.com/nv-lang/nova-compress`
```

И всё. Сам git сказал `error: unable to create file scripts/guards/selftest/test-check-invariant-discipline.sh: Filename too long`
(повторено руками той же командой `git worktree add` в той же базе кэша). Этот текст до
пользователя не доходит.

## Почему

`run_git` (`compiler-codegen/src/git_cache.rs:127-133`) кладёт stderr git в ошибку
верно. Теряется он при ПЕРЕУПАКОВКЕ: `lockfile.rs:815`
`.map_err(|e| anyhow!("резолв версий git-зависимостей:\n  {}", e))` и затем
`nova-cli/src/main.rs:5027`/`:5031` `.map_err(|e| anyhow!("dependency resolution (nova.lock.toml): {}", e))`.
`{}` у `anyhow::Error` печатает только ВЕРХНИЙ контекст (`checkout commit …`, добавленный
`with_context` у `git_cache.rs:482`), а цепочку причин отбрасывает; `{:#}` печатал бы её.

**Класс — К-диагностика: обёртка ошибки форматом `{}` молча режет цепочку причин.** Грубый
счёт `anyhow!("…{}", e)` по `nova-cli/src` — 83 места в 15 файлах; это ВЕРХНЯЯ граница, не
носители: там, где `e` не `anyhow::Error` (например, `io::Error`), цепочки нет и резать
нечего. Разбор по местам — работа фикса, не пробы.

## Проба и контроль

`python probes/dep-error-drops-git-cause/run.py.txt scripts/nova_run.py` (из корня
claude-limits) — пакет из одного файла с единственной зависимостью nova-compress 0.1, пустой
`NOVA_HOME` длиной 130 (каталог checkout 209 + самый длинный файл compress 58 > 260),
`core.longpaths=false`:

| прогон | результат |
|---|---|
| проба | `CAUSE DROPPED` — сборка упала, «too long» в выводе нет |
| `… control` (`core.longpaths=true`) | `CONTROL: dependency resolution PASSED` — значит причина отказа именно длина пути |

Дальше контрольная сборка падает в MSVC на том же глубоком пути (`C1083` на относительном
include brotli) — это следующий предел той же глубины, к находке не относится: контроль судит
только шаг разрешения.

## Вес для claude-limits

Малый. У владельца кэш по умолчанию `~\.nova`, путь checkout около сотни символов — до
предела далеко. Задевает того, у кого `NOVA_HOME` глубоко (CI-раннеры, песочницы), и бьёт
именно тем, что не называет причину: понять «путь длинный» по выводу нельзя.
