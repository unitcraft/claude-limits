# How to run

The environment `nova.ps1` sets (NOVA_STD_PATH, NOVA_RT_DIR, NOVA_CG_INCLUDE, and the
GC/include dirs) is needed for `build`.

## The minimal case (the verdict)

    cd probes/unannotated-let-breaks-far-for-in
    nova check src/gap_silent_bool.nv                          # passes
    nova build src/gap_silent_bool.nv -o <scratch>/g.exe       # passes
    <scratch>/g.exe x y                                        # prints: true   (must be 13)

    nova build src/control_silent_bool_annotated.nv -o <scratch>/c.exe
    <scratch>/c.exe x y                                        # prints: 13

The control makes the cause impossible by giving `all` its type; nothing else differs.

## The loud forms

`gap_with_direct`, `gap_with_no_if`, `gap_with_lib_text`, `gap_mod_named_parse_with`
fail `build` with "for-in: cannot resolve iterator type for expression of C-type ''";
`control_with_one_parse` (only one `parse` imported) builds. A fix is done when every
`gap_*` builds AND `gap_silent_bool` prints 13.

## The older forms

`gap_for`, `gap_pass`, `gap_closure`, `gap_result_field`, `gap_captured_field`,
`gap_use_in_arm`, `gap_with`, `gap_xmod_with`, `gap_two_parse`, `gap_silent` all build
and print the right value: they are the axes that were excluded on the way.
