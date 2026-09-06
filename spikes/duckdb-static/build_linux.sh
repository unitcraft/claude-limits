#!/bin/sh
# DuckDB static build + spike on Linux (WSL Ubuntu). Run from a copy of the amalgamation dir.
set -e
cd "$(dirname "$0")"
echo "== toolchain"; clang++ --version | head -1; nproc; free -m | sed -n 2p
echo "== compile duckdb.cpp (clang++ -O2, static)"
s=$(date +%s)
clang++ -O2 -std=c++17 -w -DNDEBUG -DDUCKDB_STATIC_BUILD -c duckdb.cpp -o duckdb.o
e=$(date +%s); echo "compile seconds=$((e-s))"
ar rcs libduckdb_static.a duckdb.o
ls -la duckdb.o libduckdb_static.a | awk '{printf "%s %.1f MB\n", $9, $5/1048576}'
echo "== spike.c: static libstdc++/libgcc"
clang -O2 -c spike.c -o spike.o -I.
clang++ -O2 spike.o libduckdb_static.a -static-libstdc++ -static-libgcc -lpthread -ldl -o spike_static_cxx
echo "== spike.c: fully static (glibc too)"
if clang++ -O2 spike.o libduckdb_static.a -static -lpthread -ldl -o spike_fully_static 2>static.err; then echo "fully static: ok"; else echo "fully static: FAILED (see static.err)"; head -5 static.err; fi
ls -la spike_static_cxx spike_fully_static 2>/dev/null | awk '{printf "%s %.1f MB\n", $9, $5/1048576}'
strip -o spike_static_cxx.stripped spike_static_cxx && ls -la spike_static_cxx.stripped | awk '{printf "%s (stripped) %.1f MB\n", $9, $5/1048576}'
echo "== ldd"; ldd spike_static_cxx || true
echo "== run cold (new file)"; rm -f spike.duckdb*; /usr/bin/time -f "process wall %e s, maxrss %M KB" ./spike_static_cxx spike.duckdb
echo "== run warm (existing file)"; /usr/bin/time -f "process wall %e s, maxrss %M KB" ./spike_static_cxx spike.duckdb
ls -la spike.duckdb* | awk '{printf "%s %.1f MB\n", $9, $5/1048576}'
