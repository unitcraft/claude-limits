#include "tid.h"

#if defined(_WIN32)
#include <windows.h>
long spike_os_thread_id(void) { return (long)GetCurrentThreadId(); }
#else
#include <pthread.h>
long spike_os_thread_id(void) { return (long)(unsigned long)pthread_self(); }
#endif
