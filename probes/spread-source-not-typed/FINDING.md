# Codegen cannot type a spread whose source is a CALL. A block source is fine.

Run 2026-09-14 23:43. `nova build` per file, each form carrying its own `main`.
`nova check` run separately on the two failing forms.

| form | source of the spread | `nova check` | `nova build` |
|---|---|---|---|
| `from_binding` (**control**) | a plain binding `base` | PASS | **PASS** |
| `from_block` | a block `{ ro tmp = make(); tmp }` | PASS | **PASS** |
| `from_call` | a free function call `make()` | **PASS** | **FAIL** |
| `from_method` | a method call `base.grown()` | **PASS** | **FAIL** |

```
codegen error: cannot determine type for spread
  `{...nova_fn_29probe_spread_source_not_typed5shape4make()}` -- add explicit type annotation
codegen error: cannot determine type for spread
  `{...Nova_Shape_method_grown(base)}` -- add explicit type annotation
```

## The axis, named before the run and confirmed by it

**The source being a CALL is what breaks it** -- free function and method alike, which
settles the question the integrator asked: the carrier I met in T2.4 (a free function)
is not the class, and the class is not "anything that is not a binding" either. The
block form passes, and a block is no more a plain binding than a call is. What both
failing forms have in common is that the type of the spread source is only knowable by
resolving a callee.

**The frontend accepts all four.** `nova check` is green on the two that die in codegen,
so this is the same shape as registry #1090: the checker knows the type, and codegen
works it out again from the expression instead of being told. A defect that `check`
cannot see is a defect that every per-module acceptance passes.

## Two corrections the run forced, both found by the control

1. **The first control failed on someone else's defect.** `Shape` was declared `value`,
   and the control died with `initializing 'NovaValue_Shape' with an expression of
   incompatible type 'NovaValue_Shape *'` -- that is registry **#1036** (spread on a
   value-record emits a pointer assigned into a value), a different mechanism. With it
   in the way the probe could not have measured mine at all: every form would have
   failed, and I would have called the class far wider than it is. Dropping `value`
   separated them.
2. **Building a library file links no `main`** (`undefined symbol: nova_fn_main_impl`).
   Each form now carries its own, so one `nova build <file>` is a whole verdict.

Both were caught because the control ran FIRST and was expected to pass. A probe whose
control is run last, or not at all, reports the first failure it meets as its finding.

## The workaround, and what it costs

A binding: `ro base = make()` then `{ ...base, size: 9 }`. It is what `claude-limits`
does today. The diagnostic's own advice ("add explicit type annotation") does not apply
in return position, where the carrier lived.
