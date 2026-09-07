# Task reports

One file per task, `<id>.md` (for example `T0.0.md`), holding the verbatim output
of the commands from that task's "готово, когда" line — the form is in the
[executor brief](../executor-brief.md) §6. A report that paraphrases a verdict
instead of quoting it is not a report.

The report ships in the same commit as the work, so it does not carry that
commit's own hash; `git log -- docs/reports/<id>.md` gives it.
