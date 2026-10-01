# Голый вариант enum в библиотеке связывается с одноимённым вариантом импортёра

**Замер 2026-10-01, 20:00.** Реестр 221.1 **№1555**, К2 (номер дал интегратор 20:00).
Регрессия nova main: на integ 8900d9a61 и на закреплённом в CI claude-limits
`97ab70f5` того же не было. Блокирует подъём `NOVA_REF` в claude-limits.

## Как запускать

Каталог — пакет `hcap`: переименовать `nova.toml.txt` → `nova.toml`, три `*.nv.txt` →
`*.nv`, затем из этого каталога `nova build v1_main.nv -o v1.exe && ./v1.exe` (и
`v2_control.nv` так же).

## Замер

| проба | что | nova-integ 8900d9a61 | nova main (exe 2026-10-01 18:42, дерево 65291fcd8) |
|---|---|---|---|
| `v1_main` | `v1_lib` — `Method enum Get \| Post \| Other(str)` и `Ok(match s { "GET" => Get, … })` в `-> Result[Method, str]`; `v1_main` импортирует его и объявляет СВОЙ `HttpMethod enum Get \| Post \| Put` | `v1 post` | **`v1_lib.nv:10:5: E7301 cannot return value of type Result[HttpMethod, str] from a function declared -> Result[Method, str]`** |
| `v2_control` | то же, но у второго enum варианты `Head \| Patch \| Put` | `v2 post` | `v2 post` |

Ось — совпадение ИМЁН вариантов в модуле-импортёре: голые `Get`/`Post` в библиотеке
разрешаются в варианты чужого enum, видимого лишь в модуле, который библиотеку
импортирует. Носитель в жизни — `nova-http src/method.nv:39` (`str @to_method`) рядом с
`server/routes.nv` `HttpMethod` claude-limits: все 25 модулей сервера падают E7301; с http
0.1.3 так же, то есть дело не в версии пакета.

## Обход в claude-limits

Нет — ждём фикса (интегратор: чинит помощник первым). `NOVA_REF` не поднимается.
