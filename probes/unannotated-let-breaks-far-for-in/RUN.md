# How to run

The environment `nova.ps1` sets (NOVA_STD_PATH, NOVA_RT_DIR, NOVA_CG_INCLUDE, and the
GC/include dirs) is needed for `build`.

## The real reproduction (the only red one)

In `src/claude_limits.nv`, drop the `[]str` from `ro argv []str = if ...` in `main`,
then from the repository root:

    nova build src/claude_limits.nv -o <scratch>/cl.exe

Expected today: `codegen error: for-in: cannot resolve iterator type for expression
of C-type ''`. Put the `[]str` back afterwards.

## The isolated forms (all green -- excluded axes)

    cd probes/unannotated-let-breaks-far-for-in
    nova check src/<form>.nv
    nova build src/<form>.nv -o <scratch>/p.exe && <scratch>/p.exe x y

Every `gap_*` has `control_*` twins (annotated, or without the `if`). A `gap_*` that
starts FAILING while its control builds is the isolation this probe is missing.
