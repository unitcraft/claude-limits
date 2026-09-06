/* duck_shim.c — flat C shim over the DuckDB C API for the Nova link spike.
 * Nova `int` = intptr_t. Symbols are literal-name externs (D282). */
#include <stdint.h>
#include <string.h>
#define DUCKDB_STATIC_BUILD 1
#include "duckdb.h"
#ifdef _WIN32
#pragma comment(lib, "rstrtmgr.lib")   /* DuckDB uses the Restart Manager on Windows */
#pragma comment(lib, "ws2_32.lib")
#pragma comment(lib, "bcrypt.lib")
#endif

/* Round trip on an in-memory database with real types; returns the row count (3) or a negative step code. */
intptr_t duck_spike_roundtrip(void) {
    duckdb_database db; duckdb_connection con; duckdb_result res;
    if (duckdb_open(NULL, &db) != DuckDBSuccess) return -1;
    if (duckdb_connect(db, &con) != DuckDBSuccess) return -2;
    if (duckdb_query(con, "SET autoinstall_known_extensions=false; SET autoload_known_extensions=false;", &res) != DuckDBSuccess) { duckdb_destroy_result(&res); return -5; }
    duckdb_destroy_result(&res);
    if (duckdb_query(con,
        "CREATE TABLE s (sampled_at TIMESTAMP NOT NULL, percent TINYINT NOT NULL, locked BOOLEAN NOT NULL);"
        "INSERT INTO s VALUES (TIMESTAMP '2025-09-06 16:00:00', 9, false), (TIMESTAMP '2025-09-06 16:05:00', 22, false), (TIMESTAMP '2025-09-06 16:10:00', 100, true);",
        &res) != DuckDBSuccess) { duckdb_destroy_result(&res); return -3; }
    duckdb_destroy_result(&res);
    if (duckdb_query(con, "SELECT count(*) FROM s WHERE sampled_at >= TIMESTAMP '2025-09-06 16:00:00'", &res) != DuckDBSuccess) { duckdb_destroy_result(&res); return -4; }
    intptr_t n = (intptr_t)duckdb_value_int64(&res, 0, 0);
    duckdb_destroy_result(&res);
    duckdb_disconnect(&con);
    duckdb_close(&db);
    return n;
}

/* Length of the library version string, e.g. "v1.5.5" -> 6. */
intptr_t duck_spike_version_len(void) {
    return (intptr_t)strlen(duckdb_library_version());
}
