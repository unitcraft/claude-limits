# #3 — файл журнала приложения
Сделано: `src/storage/applog.nv` — запись `<ISO-время UTC> <INFO|WARN|ERROR> claude-limits: <строка>` в `paths.log_file`, вращение 1 МБ × 3 файла (`.log`, `.log.1`, `.log.2`, лишние номера удаляются), `scrub` вычищает токены (`sk-ant-…`, JWT `eyJ…`, `Bearer …`, длинные сплошные буквенно-цифровые серии). `say` в `src/claude_limits.nv` печатает на консоль как раньше и дописывает в файл; `say_warn`/`say_err` дают уровни. `--serve` включает журнал в начале (две внутренние переменные окружения процесса: у `say` нет `Paths` под рукой, глобалей в Nova нет) и первой строкой называет путь. Путь не менялся: `paths.resolve` уже считал `log_file` (Windows: `<data>\logs\`, Linux: `$XDG_STATE_HOME`, портативный: `logs\` у бинаря, `--log`, `CLAUDE_LIMITS_DATA` двигает журнал с базой; `--config` журнал не двигает — как в 01.2 §1). README, строка «log» и абзац про журнал — поправлены. `/api/health` не менялся.
Проверено (всё через crew_watch machine:true, `NOVA_MAIN_REPO=…/nova ./nova.sh …`):
  $ ./nova.sh test src/storage/applog_test.nv
  PASS src/storage/applog_test — PASS: 1 FAIL: 0 (11 тестов: пути Windows/Linux/XDG/портативный/CLAUDE_LIMITS_DATA/--config/--log; формат строки; scrub «убирает» и «не трогает обычное»; секрет не попадает в файл; must_rotate; сдвиг файлов и удаление лишних; дозапись под лимитом)
  $ ./nova.sh test src/storage/paths_test.nv → PASS: 1 FAIL: 0
  $ ./nova.sh build --mode release src/claude_limits.nv -o target/claude-limits.exe → built (42.83s)
  Живая: `--serve --config <tmp>/t.toml`, порт 56063, CLAUDE_LIMITS_DATA=<tmp>/data, HOME/APPDATA подменены на временные (Claude-каталоги не тронуты). Файл `<tmp>/data/logs/claude-limits.log` создан, первая строка:
  2026-10-08T09:02:38.211Z INFO claude-limits: log file C:\...\cl3-live-wnjx6f4v\data\logs\claude-limits.log
  далее new database / settings / TLS roots / listening — те же строки, что на консоли. `/api/health` ответил, форма прежняя. Процесс остановлен (kill), 7391 не трогал.
  $ node scripts/check-web.mjs → 8 suites (248 tests) + 14 checkers, WEB CHECK: clean
  $ for f in scripts/check-*.py → все 17 exit 0 (включая check-guards-judge-this-tree)
Обратная проба: (1) правило `sk-ant-` выключено → красные «scrub: tokens go…» (applog_test.nv:95) и «a secret in a line never reaches the file» (:117) → вернул → зелёный. (2) `must_rotate` всегда false → красные «must_rotate…» (:131) и «crossing the limit shifts the files…» (:160) → вернул → зелёный. По ходу сам тест поймал дефект: токен с точкой в конце фразы (`…${token}.`) проходил (точка считалась частью серии) — исправлено в `judged`.
Отклонения от входов: вращение «1 МБ × 3» понято как живой файл + 2 старых. В плане 01.2/01.5 формат строки иной не зафиксирован. Время с миллисекундами (`…38.211Z`) — формат `to_rfc3339` проекта. Схема БД и API не тронуты — чек-листы §17/§20 не применимы.
Открытые вопросы: нет. Сбой записи журнала молча теряет файловую копию строки (консоль её имеет).
Дефекты Nova: нет.
Модель: sonnet
