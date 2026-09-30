# Two imported functions share a name: codegen types the call by the WRONG one

**Status: ISOLATED (2026-09-30). A silent miscompile -- `check` and `build` both pass,
and the program prints `true` where it must print `13`.** Filed as **registry 221.1
#1390 (K1)** by the integrator, who re-measured it (05:59: `true` vs `13`); this
window works only in claude-limits (owner's word 2026-09-21) and handed it over with
this directory as the evidence. The fix is the integrator's (oracle, resolve channel).

## The minimal case -- `src/gap_silent_bool.nv`

```nova
import std.os.{args, real_os}
import probe_far_for_in.lib_count.{parse}   // parse(xs []str) -> int
import probe_far_for_in.lib_flag.{parse}    // parse(body str) -> bool

fn main() Io {
    ro all = with Os = real_os() { args() }
    ro n = parse(all)            // the checker picks lib_count: `all` is []str
    println("${n + 10}")
}
```

Run with two arguments (three with the program name):

| form | check | build | prints |
|---|---|---|---|
| `control_silent_bool_annotated` (`ro all []str = with ...`) | ok | ok | `13` |
| `gap_silent_bool` (`ro all = with ...`) | ok | ok | **`true`** |

## What the codegen does

The CALL goes to the right function; the TYPE of its result is taken from the other
function of the same name. The real case in `src/claude_limits.nv` shows it in the C:

    NovaValue_Usage _nv_scr_2591 = nova_fn_3cli4args5parse(argv);

`cli.args.parse` is called (right), its `Result` is stored in a `Usage` temporary --
the return type of `usage.parse.parse` (wrong). There the C compiler happened to
refuse it; with `int` against `bool` C converts silently, and the value is corrupted.

**The trigger is an argument the codegen holds no C-type for** -- here the value of a
`with` block bound without an annotation. With a literal, or with any annotation, the
right overload's type is found:

| form | argument | result |
|---|---|---|
| `gap_two_parse` | vector literal | correct |
| `gap_mod_named_parse_lit` | literal, second `parse` in a module named `parse` | correct |
| `gap_mod_named_parse_with` | `with` block, through an unannotated `if` | codegen error |
| `gap_with_no_if` | `with` block, `ro v = all` | codegen error |
| `gap_with_direct` | `with` block, `parse(all)` directly | codegen error |
| `gap_with_lib_text` | as above, second module NOT named `parse` | codegen error |
| `control_with_one_parse` | `with` block, only ONE `parse` imported | correct |
| `gap_silent_bool` | `with` block, the two return types C-compatible | **wrong value** |

So: the module's name, `if`, slices -- none of it matters. Two same-named imports plus
an argument of unknown codegen type is enough.

## Class

K1 (silent wrong result). Family: registry 221.1 #1105 / #1106 -- the frontend knows
the answer (it resolved the call), and a second consumer works it out again, here by
NAME, and gets it wrong.

## How it was found, and what did NOT reproduce it

claude-limits `main` imports both `cli.args.{parse}` and `usage.parse.{parse}`. A lint
fix made `argv` an unannotated `if` over `all` (itself an unannotated `with` result),
and the build failed with "for-in: cannot resolve iterator type for expression of
C-type ''" and no location. Nine guesses built up from nothing missed (the older
`gap_*` forms with one `parse` in scope, all green, kept as excluded axes). The case
was found by bisecting the REAL function: emptying one match arm turned the vague
for-in error into the C type mismatch above, which named the second `parse`.

claude-limits keeps `ro argv []str = ...`; the comment at that line points here.
