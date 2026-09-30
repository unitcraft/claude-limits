# A record literal inside a closure takes the OUTER literal's type

**Status: isolated (2026-09-30).** `check` passes, the C does not compile -- and
the form that fails is the one the checker itself tells you to write.

## The case -- `src/gap.nv`

```nova
type Inner value { ro n int }
type Outer value { ro label str, ro inner Option[Inner] }

fn main() Io {
    ro x Option[int] = Some(7)
    ro o Outer = { label: "a", inner: x.map(fn(v int) -> Inner => { n: v }) }
    ...
}
```

    gap.c: error: no member named 'n' in 'struct NovaValue_Outer'
    gap.c: error: returning 'NovaValue_Outer' from a function with incompatible
           result type 'NovaValue_Inner'

The literal `{ n: v }` is the closure's result, declared `-> Inner`; the codegen
types it by the literal it sits inside (`Outer`).

| form | check | build |
|---|---|---|
| `gap` -- `fn(v int) -> Inner => { n: v }` | ok | **C error** |
| `control_named_fn` -- `=> wrap(v)`, `wrap` returns the literal | ok | ok, prints `a 7` |
| `control_explicit_type` -- `=> Inner{ n: v }` | **refused**: "redundant type prefix on record literal -- the return type `-> Inner` already declares it; write `=> { ... }`" | -- |

So inside a closure there is no form the user can write: the checker forbids the
explicit one and the codegen breaks the implicit one. Only moving the literal out
into a named function works.

## How it was found

T2.29, `server/dto.nv`: `worst: v.worst.map(fn(x WorstView) -> WireWorst => { ... })`
inside a `WireSnapshot` literal; the C said `no member named 'account_id' in
'struct NovaValue_WireSnapshot'`. dto.nv now calls a named `wire_worst`, with a
comment pointing here.
