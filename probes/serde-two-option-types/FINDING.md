# `if c { None } else { Some(s) }` as a record field: codegen typed it Option[int]

**Status: reproduced on the real file, NOT isolated (2026-09-30).** Recorded as a
named gap; not filed, because a registry row needs a minimal case.

## The real case

`src/server/errors.nv`, `to_json`, while moving problem+json to serde (T2.29):

```nova
ro p = Problem{
    ...
    detail: if e.detail == "" { None } else { Some(e.detail) },   // detail Option[str]
    ...
}
```

`nova check` passes; the C does not compile:

    NovaOpt_nova_int _nv_if_1079;
    if (...) { _nv_if_1079 = ((NovaOpt_nova_int){.tag = NOVA_TAG_Option_None}); }
    else     { _nv_if_1079 = ((NovaOpt_nova_str){.tag = NOVA_TAG_Option_Some, ...}); }
    error: assigning to 'NovaOpt_nova_int' from incompatible type 'NovaOpt_nova_str'

The `if` temporary is typed from its FIRST branch, and a bare `None` there became
`Option[int]` -- although the field is `Option[str]` and the other branch says so.
Writing `Some` first builds; that is what `errors.nv` carries, with a comment.

## Excluded in isolation -- all build and print the right value

| form | what it adds |
|---|---|
| `gap`, `gap_reversed`, `control_*` | two Option fields of different types, serde-derived |
| `gap_none_first` | the `None`-first `if` as a field value |
| `gap_none_first_two_opts` | ... plus a second `Option[int]` field |
| `gap_none_first_serde` | ... plus `#impl(Serialize)` and `json_encode` |
| `gap_after_int_fn` | ... plus a preceding fn calling `.is_none()` on an `Option[int]` |

The real record has nine fields, two of them filled by field-init shorthand
(`instance,` `request_id,`), in a module with twenty-four constructors of another
record that also holds an `Option[int]`. The next attempt should bisect the real
module, as the #1390 probe did, rather than add guesses.
