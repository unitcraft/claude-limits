# Task reports

One file per task, `<id>.md` (for example `T0.0.md`), holding the verbatim output
of the commands from that task's "готово, когда" line — the form is in the
[executor brief](../executor-brief.md) §6. A report that paraphrases a verdict
instead of quoting it is not a report.

The report ships in the same commit as the work, so it does not carry that
commit's own hash; `git log -- docs/reports/<id>.md` gives it.

Two files here are deliberately NOT task reports and are named accordingly.

[F2-acceptance-audit.md](F2-acceptance-audit.md) sorts the eleven acceptance
lines of subplan 01.1 §11 into "already answerable by machine" and "needs the
backend", so that T2.26 is a run rather than a hunt for the criteria. It quotes
its own run verbatim like any report, but it does not close a task, and the
acceptance itself will arrive as `F2-acceptance.md`. Naming it `T2.26.md` would
have claimed a task that is not done.

[registry-rows-1033-1036-1037.md](registry-rows-1033-1036-1037.md) holds the
provenance of three rows of the `nova` registry 221.1 that were measured here:
what each was measured with, and which probe in this repository backs it. It is
NOT a copy of the registry — the registry is the single source and edits go
there; if the two disagree, the registry wins. It lives here because the probes
do, and the rows point at them by path.
