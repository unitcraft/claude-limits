# A condition CAN wrap. The claim is withdrawn, and no registry row is filed.

Run 2026-09-14 23:41, `nova.sh check` per file, one file per run.

| form | what it is | verdict |
|---|---|---|
| control | `if a > 0 && b > 0 {` on one line | **PASS** |
| A | operator at the END of the first line | **PASS** |
| B | operator at the START of the second line | **PASS** |
| C | wrapped inside `(...)` | **PASS** |
| E | the same wrap in a `while` | **PASS** |
| D | wrapped condition + `{` on its own line | **FAIL** `expected {, got newline` |
| F | **control for D:** short condition + `{` on its own line | **FAIL**, identically |

## What this settles

**There is no defect, and I was the one who was wrong.** I carried "a condition may not
wrap onto a second line" out of task T2.4 as a fact about the compiler. Form A says
otherwise, and A is exactly the form `spec/syntax.ru.md:142-155` promises (rule 1,
newline ignored after a dangling binary operator).

**D fails, and F is why it is not a defect either.** The brace on its own line fails
with the SAME diagnostic at the SAME column whether the condition wrapped or not, so
what D measures is not wrapping — it is that `{` must follow the condition on its line.
That is the language as designed (D43: `)` and `{` on one line). Without F, D would have
looked like a wrap defect, and I would have filed a row against the spec.

**B passing is worth a line, because it looks like it contradicts the spec.** The
rejected form in D49 is the UNARY/BINARY ambiguity — `a` ⏎ `+ b`, where `+b` is a
legal unary expression. `&&` has no unary reading, so there is nothing to disambiguate
and the parser can only continue. The spec's prohibition is about a class of operators,
not about the position as such; the example it gives (`+`) is the whole of the danger.

## Cost of having been wrong

The integrator had instructed me to file a registry row for this ("это не опция"). The
row would have claimed a compiler defect that does not exist, against a spec that says
the opposite, and it would have been believed: a registry row is what the project trusts
when memory and code disagree. It was stopped by reading the spec before writing the
row, and then by writing the expected outcomes down BEFORE the run (`RUN.md`) — the
table there already said "no row if B is the failing form", so there was nothing left to
argue with once the numbers came in.

The integrator withdrew the instruction himself once shown the spec lines.
