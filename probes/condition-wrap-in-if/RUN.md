# How to run this probe

Each file separately — one failing file would otherwise hide the rest behind the first
error:

    cd probes/condition-wrap-in-if
    ../../nova.sh check src/control_one_line.nv    # must PASS, or nothing else counts
    ../../nova.sh check src/form_a_trailing_op.nv  # the question
    ../../nova.sh check src/form_b_leading_op.nv   # expected to FAIL, by design
    ../../nova.sh check src/form_c_parens.nv       # the workaround

`check` IS the verdict here, unlike the spread probe: this is a parser question, and a
parse error surfaces in `check`.

## What each outcome means

| control | A | B | C | reading |
|---|---|---|---|---|
| PASS | PASS | FAIL | PASS | no defect. What I hit in T2.4 was form B, which the spec rejects on purpose. NO ROW. |
| PASS | FAIL | FAIL | PASS | DEFECT: the compiler is narrower than `syntax.ru.md` rule 1. Row, with C as the workaround. |
| PASS | FAIL | FAIL | FAIL | wider defect: no wrapping of a condition works at all, including inside parens. |
| FAIL | * | * | * | REFUSE to judge — the probe is broken, not the compiler. |
