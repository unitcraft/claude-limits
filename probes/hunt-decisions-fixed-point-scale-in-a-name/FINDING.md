# Масштаб дробного числа живёт в суффиксе имени, суффиксы уже разошлись, переводчика между слоями нет

Охота 2026-09-08, трек `oracle`. Запускать из корня репозитория: `sh cmd.sh`.

## КЛАСС

**Решение «дроби считаются целыми в фиксированном масштабе» принято, а сам масштаб
записан суффиксом ИМЕНИ поля (`_x100`, `_milli`, `_bp`, `_x10000`) — то есть ничем, что
проверяется.** Свойство: два соседних слоя могут держать одну величину в разных
масштабах, присваивание между ними компилируется (обе стороны `int`), а ошибка выходит
на провод как число, отличающееся в десять или сто раз, под правильным именем поля.

Решение записано и обосновано — `src/server/json.nv:19-25`:

    // FIXED-PRECISION NUMBERS ARRIVED WITH T2.12, as this banner said they would, and
    // they take INTEGERS. `elapsed_share` and `rate_per_hour` (01.3 §0, 2–3 digits) are
    // written from hundredths and thousandths held as `int`: the model layer already
    // counts that way (`model/forecast.nv` works in ten-thousandths of a percent per
    // minute, because hundredths lost 0.42 and moved a forecast six points), and a
    // decimal assembled from integer division has no rounding mode to get wrong and no
    // platform-dependent float formatting to compare against in a test.

## ДВЕРЬ, КОТОРАЯ МАСШТАБ ЗНАЕТ, НО НЕ ТРЕБУЕТ

    src/server/json.nv:140-141
        export fn field_fixed2(name str, hundredths int) -> str =>
            "${quote(name)}:${decimal(hundredths, 2)}"

    src/server/json.nv:144-145
        export fn field_fixed3(name str, thousandths int) -> str =>
            "${quote(name)}:${decimal(thousandths, 3)}"

Параметр — `int`. Масштаб — в имени параметра, то есть в комментарии.

## ОДНА ВЕЛИЧИНА, ЧЕТЫРЕ МАСШТАБА, НИ ОДНОГО ПЕРЕВОДЧИКА

`rate_per_hour`, сверху вниз:

    src/model/forecast.nv:90         ro rate_x10000 = (used_percent * 10000) / window_min   // 1/10000 % в МИНУТУ
    src/model/forecast.nv:57         rate_per_hour_x100 int   // hundredths of a percent per hour
    src/model/forecast.nv:106        rate_per_hour_x100: (rate_x10000 * 60) / 100
    src/server/dto.nv:157-158        /// Thousandths of a percent per hour.
                                     rate_per_hour_milli int
    src/server/dto.nv:240            field_fixed3("rate_per_hour", f.rate_per_hour_milli)

Между `Forecast` (сотые) и `ForecastView` (тысячные) нужен множитель 10. Функции,
которая бы его применяла, в дереве нет: `grep -rn "ForecastView" src --include=*.nv`
вне тестов находит только объявление и рендер — конструктора из `Forecast` не написал
никто. Пример плана (`docs/plans/01.3-api.md:261`) ждёт `"rate_per_hour": 2.06`; прямое
присваивание `rate_per_hour_milli = f.rate_per_hour_x100` даст `0.206`, скомпилируется
и пройдёт любой тест, который сравнивает форму, а не значение.

То же ниже, между теми же слоями: `runs_out_in_min int` (forecast.nv:56, МИНУТЫ) против
`runs_out_at str` (dto.nv:155, МОМЕНТ) — переводчика тоже нет.

## СУФФИКС УЖЕ ЛЖЁТ

    src/server/dto.nv:193-194
        /// Hundredths of the window elapsed at `fetched_at`.
        elapsed_share_bp int

    src/server/dto.nv:267
        field_fixed2("elapsed_share", l.elapsed_share_bp),

`bp` — basis point, одна десятитысячная; доктрока и использование говорят «сотые».
Имя расходится с собственным описанием в сто раз, и это единственное место, где масштаб
вообще записан.

## ПОЧЕМУ НЕ ЧИНИТСЯ У НОСИТЕЛЯ

Переименовать `elapsed_share_bp` — поправить одно имя из четырёх; дописать `* 10` в
будущем конструкторе `ForecastView` — принять решение о масштабе в пятом месте. Пока
масштаб не тип (или хотя бы не одна константа рядом с величиной), каждое новое дробное
поле (`pace_per_hour`, `avg_session` из §3.6 — их ещё нет) заводит свой суффикс, и
согласие между слоями проверяется чтением имён.
