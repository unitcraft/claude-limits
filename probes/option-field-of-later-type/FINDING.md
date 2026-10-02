# Запись с полем `Option[T]`, где `T` объявлен НИЖЕ, не собирается в C

**Замер 2026-10-02 08:32.** Реестр 221.1 **№1625** (номер дал интегратор 08:36). Класс: К3 (громкий
отказ сборки на правильной программе). Чем мерил: компилятор — копия `./nova.sh` с `nova.exe`
локального дерева интегратора `D:/Sources/nv-lang/nova` (сборка 08:24, HEAD тогда `aee6ba600`).

## Что происходит

```nova
type Outer value {
    n int
    inner Option[Later]
}

type Later value {
    s str
}
```

`nova build` → `error: field has incomplete type 'NovaValue_Later'`: C-структура `Outer` (с
полезной нагрузкой `Option[Later]` по значению) выводится раньше `NovaValue_Later`. `check` и
сборка Nova этого не видят — отказывает компилятор C.

| проба | ожидание | получено |
|---|---|---|
| `q_option_field_of_later_type` | `inner x` | **CC-FAIL**: `field has incomplete type 'NovaValue_Later'` |
| `q_option_field_of_earlier_type` (КОНТРОЛЬ: тот же текст, `Later` объявлен выше) | `inner x` | `inner x` |

Порядок объявлений в Nova смысла не несёт — значит, вывод C должен упорядочить структуры по
зависимостям, как он, видимо, делает для поля `T` без `Option`.

## Где ударило (claude-limits)

`usage/parse.nv`: `Usage` получил поле `extra Option[ExtraUsage]` (Extra Usage у Kimi, план 01.6
П8), `ExtraUsage` был объявлен ниже — CC-FAIL во всех единицах, где есть `Usage`. Обход —
`ExtraUsage` объявлен выше, с комментарием-ссылкой сюда.

## Как запускать

Каталог-пакет: `nova.toml.txt` → `nova.toml`, `q_option_field_of_later_type.nv.txt` →
`q_option_field_of_later_type.nv`; `nova build q_option_field_of_later_type.nv -o q.exe`. Контроль
— так же, в отдельном каталоге.
