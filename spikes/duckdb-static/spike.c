/* DuckDB static-link spike for claude-limits (plan 01.2 alternative check).
 * Measures: process start -> db open, schema with real types, 10 000 inserts one by one
 * (prepared statement) and 10 000 through the Appender, range query, close. Prints milliseconds.
 * Uses only the base library: in v1.5 make_timestamp/date_trunc/time_bucket live in the
 * core_functions extension, TIMESTAMPTZ arithmetic in icu — neither is in the amalgamation. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "duckdb.h"

#ifdef _WIN32
#include <windows.h>
static double now_ms(void) {
    static LARGE_INTEGER f; LARGE_INTEGER c;
    if (!f.QuadPart) QueryPerformanceFrequency(&f);
    QueryPerformanceCounter(&c);
    return (double)c.QuadPart * 1000.0 / (double)f.QuadPart;
}
#else
#include <time.h>
static double now_ms(void) {
    struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000.0 + ts.tv_nsec / 1e6;
}
#endif

static int fail(const char *what, duckdb_result *r) {
    fprintf(stderr, "FAIL %s: %s\n", what, r ? duckdb_result_error(r) : "");
    return 1;
}

int main(int argc, char **argv) {
    const char *path = argc > 1 ? argv[1] : "spike.duckdb";
    double t0 = now_ms();
    duckdb_database db; duckdb_connection con; duckdb_result res;
    if (duckdb_open(path, &db) != DuckDBSuccess) return fail("open", NULL);
    if (duckdb_connect(db, &con) != DuckDBSuccess) return fail("connect", NULL);
    if (duckdb_query(con, "SET autoinstall_known_extensions=false; SET autoload_known_extensions=false;", &res) != DuckDBSuccess) return fail("settings", &res);
    duckdb_destroy_result(&res);
    double t_open = now_ms();

    const char *ddl =
        "CREATE TYPE IF NOT EXISTS window_kind AS ENUM ('session','weekly_all','weekly_scoped');"
        "CREATE TABLE IF NOT EXISTS sample ("
        "  window_id INTEGER NOT NULL,"
        "  sampled_at TIMESTAMP NOT NULL,"
        "  kind window_kind NOT NULL,"
        "  percent TINYINT NOT NULL CHECK (percent BETWEEN 0 AND 100),"
        "  locked BOOLEAN NOT NULL DEFAULT false,"
        "  rate DECIMAL(6,3),"
        "  PRIMARY KEY (window_id, sampled_at));"
        "CREATE TABLE IF NOT EXISTS sample_app (window_id INTEGER NOT NULL, sampled_at TIMESTAMP NOT NULL, kind window_kind NOT NULL,"
        "  percent TINYINT NOT NULL, locked BOOLEAN NOT NULL, rate DECIMAL(6,3));"
        "DELETE FROM sample_app;";
    if (duckdb_query(con, ddl, &res) != DuckDBSuccess) return fail("ddl", &res);
    duckdb_destroy_result(&res);
    double t_ddl = now_ms();

    /* type strictness: a string into TIMESTAMP must be rejected */
    int strict_ok = 0;
    if (duckdb_query(con, "INSERT INTO sample VALUES (1, 'not a time', 'session', 5, false, 1.5)", &res) != DuckDBSuccess) strict_ok = 1;
    duckdb_destroy_result(&res);

    /* 10 000 rows one by one through a prepared statement, one transaction */
    int64_t base_us = 1757174400LL * 1000000LL; /* 2025-09-06T16:00:00Z in microseconds */
    duckdb_prepared_statement stmt;
    if (duckdb_query(con, "BEGIN", &res) != DuckDBSuccess) return fail("begin", &res);
    duckdb_destroy_result(&res);
    if (duckdb_prepare(con, "INSERT OR IGNORE INTO sample VALUES (?, ?, 'session', ?, ?, ?)", &stmt) != DuckDBSuccess) {
        fprintf(stderr, "FAIL prepare: %s\n", duckdb_prepare_error(stmt)); return 1;
    }
    for (int i = 0; i < 10000; i++) {
        duckdb_timestamp ts; ts.micros = base_us + (int64_t)i * 300LL * 1000000LL;
        duckdb_bind_int32(stmt, 1, (i % 4) + 1);
        duckdb_bind_timestamp(stmt, 2, ts);
        duckdb_bind_int8(stmt, 3, (int8_t)(i % 101));
        duckdb_bind_boolean(stmt, 4, (i % 101) == 100);
        duckdb_bind_double(stmt, 5, (i % 50) / 10.0);
        if (duckdb_execute_prepared(stmt, &res) != DuckDBSuccess) return fail("insert", &res);
        duckdb_destroy_result(&res);
    }
    duckdb_destroy_prepare(&stmt);
    if (duckdb_query(con, "COMMIT", &res) != DuckDBSuccess) return fail("commit", &res);
    duckdb_destroy_result(&res);
    double t_ins = now_ms();

    /* the same 10 000 rows through the Appender (DuckDB's bulk path) */
    duckdb_appender app;
    if (duckdb_appender_create(con, NULL, "sample_app", &app) != DuckDBSuccess) return fail("appender", NULL);
    for (int i = 0; i < 10000; i++) {
        duckdb_timestamp ts; ts.micros = base_us + (int64_t)i * 300LL * 1000000LL;
        duckdb_append_int32(app, (i % 4) + 1);
        duckdb_append_timestamp(app, ts);
        duckdb_append_varchar(app, "session");
        duckdb_append_int8(app, (int8_t)(i % 101));
        duckdb_append_bool(app, (i % 101) == 100);
        duckdb_append_double(app, (i % 50) / 10.0);
        duckdb_appender_end_row(app);
    }
    duckdb_appender_flush(app);
    duckdb_appender_destroy(&app);
    double t_app = now_ms();

    /* range query over a day, grouped per window */
    if (duckdb_query(con,
        "SELECT window_id, max(percent), count(*) FROM sample "
        "WHERE sampled_at BETWEEN TIMESTAMP '2025-09-06 16:00:00' AND TIMESTAMP '2025-09-07 16:00:00' "
        "GROUP BY 1 ORDER BY 1", &res) != DuckDBSuccess) return fail("select", &res);
    idx_t groups = duckdb_row_count(&res);
    duckdb_destroy_result(&res);
    if (duckdb_query(con, "SELECT count(*) FROM sample", &res) != DuckDBSuccess) return fail("count", &res);
    int64_t total = duckdb_value_int64(&res, 0, 0);
    duckdb_destroy_result(&res);
    double t_sel = now_ms();

    duckdb_disconnect(&con);
    duckdb_close(&db);
    double t_end = now_ms();

    printf("duckdb %s\n", duckdb_library_version());
    printf("open+connect %.1f ms | ddl %.1f ms | 10000 prepared inserts %.1f ms | 10000 appender rows %.1f ms | range query (%llu groups, %lld rows) %.1f ms | close %.1f ms | total %.1f ms\n",
           t_open - t0, t_ddl - t_open, t_ins - t_ddl, t_app - t_ins, (unsigned long long)groups, (long long)total, t_sel - t_app, t_end - t_sel, t_end - t0);
    printf("strict types: string into TIMESTAMP rejected = %s\n", strict_ok ? "yes" : "NO");
    return 0;
}
