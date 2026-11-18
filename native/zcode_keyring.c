#include "zcode_keyring.h"
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#include <wincred.h>
#include <bcrypt.h>
#pragma comment(lib, "advapi32.lib")
#pragma comment(lib, "bcrypt.lib")

uint8_t *cl_zcode_os_key(const uint8_t *path, int64_t path_len, int64_t *out_len) {
    *out_len = 0;
    if (!path || path_len <= 0 || path_len > 32767) return NULL;
    wchar_t wide[32768], absolute[32768], target[100];
    int len = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS,
                                 (const char *)path, (int)path_len, wide, 32767);
    if (!len) return NULL;
    wide[len] = 0;
    DWORD count = GetFullPathNameW(wide, 32768, absolute, NULL);
    if (!count || count >= 32768) return NULL;
    int bytes = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS,
                                   absolute, (int)count, NULL, 0, NULL, NULL);
    if (!bytes) return NULL;
    char *utf8 = malloc((size_t)bytes);
    if (!utf8) return NULL;
    if (WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, absolute, (int)count,
                            utf8, bytes, NULL, NULL) != bytes) { free(utf8); return NULL; }
    BCRYPT_ALG_HANDLE alg = NULL;
    unsigned char hash[32];
    NTSTATUS status = BCryptOpenAlgorithmProvider(&alg, BCRYPT_SHA256_ALGORITHM, NULL, 0);
    if (status >= 0) {
        status = BCryptHash(alg, NULL, 0, (PUCHAR)utf8, (ULONG)bytes, hash, 32);
        BCryptCloseAlgorithmProvider(alg, 0);
    }
    free(utf8);
    if (status < 0) return NULL;
    const wchar_t *hex = L"0123456789abcdef";
    for (int i = 0; i < 32; ++i) {
        target[2*i] = hex[hash[i] >> 4];
        target[2*i+1] = hex[hash[i] & 15];
    }
    wcscpy(target + 64, L".ZCode Credential Encryption");
    PCREDENTIALW entry = NULL;
    if (!CredReadW(target, CRED_TYPE_GENERIC, 0, &entry)) return NULL;
    uint8_t *out = NULL;
    if (entry->CredentialBlobSize == 86) {
        const wchar_t *password = (const wchar_t *)entry->CredentialBlob;
        out = malloc(43);
        if (out) {
            for (int i = 0; i < 43; ++i) {
                wchar_t ch = password[i];
                if (!((ch >= L'A' && ch <= L'Z') || (ch >= L'a' && ch <= L'z') ||
                      (ch >= L'0' && ch <= L'9') || ch == L'_' || ch == L'-')) {
                    SecureZeroMemory(out, 43); free(out); out = NULL; break;
                }
                out[i] = (uint8_t)ch;
            }
        }
    }
    SecureZeroMemory(entry->CredentialBlob, entry->CredentialBlobSize);
    CredFree(entry);
    if (out) *out_len = 43;
    return out;
}
#else
uint8_t *cl_zcode_os_key(const uint8_t *path, int64_t path_len, int64_t *out_len) {
    *out_len = 0;
    (void)path; (void)path_len; return NULL;
}
#endif

void cl_zcode_free_key(uint8_t *key) {
    if (!key) return;
    volatile uint8_t *p = key;
    for (int i = 0; i < 43; ++i) p[i] = 0;
    free(key);
}
