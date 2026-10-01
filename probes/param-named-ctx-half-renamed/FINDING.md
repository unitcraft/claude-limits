# Параметр по имени `ctx` переименован в сигнатуре, но не в теле

**Замер 2026-10-01, 07:30.** Номер реестра — у интегратора (`№TBD`). Найдено при
сборке `claude-limits` (dfc7e5e) на nova main 9712b306f (exe 07:04): clang
`use of undeclared identifier 'ctx'` в `server/routes.nv` `refuse_method(allow str,
ctx Ctx)`. В выпущенном C сигнатура несёт `NovaValue_Ctx* nv_ctx`, а тело читает
`(*ctx).request_id`.

## Как запускать

Переименовать `nova.toml.txt` → `nova.toml`, `g1_param_ctx.nv.txt` → `g1_param_ctx.nv`
(и g2 так же), затем `nova build g1_param_ctx.nv -o g1.exe && ./g1.exe`.

## Замер

| проба | что | nova-integ 8900d9a61 | nova main 9712b306f (exe 07:04) |
|---|---|---|---|
| `g1_param_ctx` | value-запись параметром по имени `ctx`, поля читаются в теле | `g1 x-y` | **clang: `use of undeclared identifier 'ctx'`** |
| `g2_param_other` | то же, параметр назван `c` | `g2 x-y` | `g2 x-y` |

Ось — имя параметра. Подозрение (не проверено чтением): слияние №1440/№1446 («one door
for a Nova name -> C identifier») защищает имя `ctx` (его носят vtable эффектов,
`->ctx`), переименовывает параметр в `nv_ctx` и пропускает доступ к его полям через
указатель.
