# An unannotated `let` in `main` breaks a for-in elsewhere in the same function

**Status: reproduced on the real file, NOT isolated.** Nothing here is filed in the
nova registry yet: a row needs a minimal case, and this probe does not have one.
Written down so the next attempt starts from the excluded axes instead of redoing them.

## What happened (2026-09-30)

The lint sweep replaced a copying loop in `src/claude_limits.nv` `main` with a view:

```nova
ro argv = if all.len() == 0 { all } else { all[1..] }
```

`nova check` passes. `nova build` fails:

    codegen error: for-in: cannot resolve iterator type for expression of C-type ''.

with no location. Adding the type makes it build and every test pass:

```nova
ro argv []str = if all.len() == 0 { all } else { all[1..] }
```

The annotated form is what the file now carries, with a comment saying the `[]str`
is load-bearing.

## Measured on the real file (one line changed at a time, same tree)

| line 144 | build |
|---|---|
| `ro argv []str = if all.len() == 0 { all } else { all[1..] }` | ok |
| `ro argv = if all.len() == 0 { all } else { all[1..] }` | **codegen error** |
| `ro argv []str = all` | ok |

`NOVA_DEBUG_IF_INFER=1` shows the `if` itself typed correctly by the codegen
(`then_ty=Nova_Vec____nova_str* else_ty=Nova_Vec____nova_str*`), so the loss is not
in the `if` expression; the failing for-in is somewhere else in `main`.

A polluted run (two edits at once, so weaker evidence) also failed with
`match parse(all)` -- `all` being the unannotated result of
`with Os = real_os() { args() }`. That points at "a binding the codegen has no
C-type for", not at slices or `if`.

## Excluded in isolation -- every form below builds and runs

Each has its control; all green, which is the point: none of these axes is the cause.

| form | axis |
|---|---|
| `gap_for` | unannotated `if` vec/slice, then for-in over it |
| `gap_pass` | the same value passed to a fn that iterates |
| `gap_closure` | a closure with a for-in in the same scope |
| `gap_result_field` | for-in over a field of `parse(v)`'s result |
| `gap_captured_field` | that field iterated inside a closure capturing `a` |
| `gap_use_in_arm` | `v.len()` used inside the `Ok(a)` arm, as line 190 does |
| `gap_with` | `all` from `with Os = real_os() { args() }` |
| `gap_xmod_with` | `parse` in ANOTHER module, fed the `with`-block value |
| (on the real file) | renaming `all`: the closure's own `mut all []str` is not it |

## Where to look next

The real `main` is ~150 lines with several closures (`with_real_disk(fn() ... {..})`,
`with_real_autostart(...)`) and a match with seven arms. The next attempt should
bisect the REAL function -- delete arms and closures until the error disappears --
rather than build up from a guess; nine guesses built up from nothing all missed.

Family, if it holds: registry 221.1 #1105 / #1106 -- the codegen working a type out
again from the shape of an expression the frontend already typed.
