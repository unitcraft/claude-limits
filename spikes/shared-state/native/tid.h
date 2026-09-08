/* One function: the OS thread this fiber is running on, right now.
 *
 * The runtime already has `_nova_p259_diag_tid()` in fibers.h, but it is
 * `static inline` in a single cross-platform TU and therefore not linkable from
 * outside. Rather than reach into the runtime, the spike carries its own copy --
 * four lines, and it cannot drift into anything else.
 *
 * Force-included, like every shim in this project (see nova-compress's note): a
 * TU that calls the extern without the prototype in ITS OWN translation unit
 * falls back to implicit-int and truncates a 64-bit handle. */
#ifndef SPIKE_TID_H
#define SPIKE_TID_H
long spike_os_thread_id(void);
#endif
