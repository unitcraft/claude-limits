# A user type named like a std generic parameter breaks `check` INSIDE std

**Status: isolated (2026-09-30); registry 221.1 #1391 (K2), filed and re-measured by the integrator.** Loud, not silent: `nova check` fails -- but it
fails pointing into the standard library, at code the user did not write.

## The case -- `src/gap_plain.nv`

```nova
type R value {
    ro a int
}

fn main() Io {
    ro r = R{ a: 1 }
    mut v []int = []
    v.push(r.a)
    println("${v.len()}")
}
```

    std/src/collections/vec/mutate.nv:123:11: error: [E_PREFIX_SHADOWS_NAMED_TYPE]
    `fn[R] ...` -- generic `R` shadows named type `R` in scope

`control_plain` -- the same program with the type named `Rx` -- passes.

## It is a class, not one name

| user type | where the error points |
|---|---|
| `R` | `std/src/collections/vec/mutate.nv:123` |
| `T` | `std/src/runtime/raw_mem.nv:110` |
| `K` | `std/src/collections/vec/access.nv:340` |
| `V` | `std/src/collections/vec_iter/core.nv:219` |
| `E` | `std/src/prelude/core.nv:163` |
| `U` | `std/src/prelude/core.nv:151` |

The shadowing check (E_PREFIX_SHADOWS_NAMED_TYPE) is judged against a scope that
contains the USER's types while it walks STD's generics. A rule meant to stop a
module from confusing itself stops every program from using six ordinary names.

## How it was found

Writing a probe for T2.29 with a record called `R`. The error named a std file,
which is the tell: nothing in the probe touched `mutate.nv`.
