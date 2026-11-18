#ifndef CLAUDE_LIMITS_ZCODE_KEYRING_H
#define CLAUDE_LIMITS_ZCODE_KEYRING_H
#include <stdint.h>
/* Returns a private 43-byte base64url key, or NULL. No writes to the keyring. */
uint8_t *cl_zcode_os_key(const uint8_t *path, int64_t path_len, int64_t *out_len);
void cl_zcode_free_key(uint8_t *key);
#endif
