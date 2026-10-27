"""Evidence-based index experiment; permitted only in a dedicated real-data database."""

import hashlib
import json
import os
import statistics
import time

from django.db import connection

from .models import DatasetSnapshot
from .reports import SQL_ROOT, fingerprint_dataset, ordered_result_hash, parameters, serializable

INDEX_NAME = "olist_bench_delivered_purchase_idx"
INDEX_SQL = (
    f"CREATE INDEX {INDEX_NAME} ON olist_order (purchased_at_source,source_order_id) "
    "INCLUDE (customer_id,snapshot_id) WHERE source_status='delivered'"
)
BENCHMARK_LOCK = (73019, 5)


def validate_target(expected_database):
    if os.environ.get("OLIST_BENCHMARK_ENABLED") != "1" or expected_database != "olist_benchmark":
        raise ValueError(
            "Benchmarking requires explicit enablement and expected database olist_benchmark."
        )
    if not connection.get_autocommit():
        raise ValueError("VACUUM and the index experiment require an autocommit connection.")
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database(),current_user")
        database, role = cursor.fetchone()
        if database != expected_database or role != "olist_owner":
            raise ValueError("Benchmark mutations require the isolated database and owner role.")
        cursor.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' "
            "AND (tablename LIKE 'accounts_%' OR tablename LIKE 'catalog_%' "
            "OR tablename LIKE 'inventory_%' OR tablename LIKE 'orders_%') ORDER BY tablename"
        )
        for (table,) in cursor.fetchall():
            cursor.execute(f"SELECT EXISTS(SELECT 1 FROM {connection.ops.quote_name(table)})")
            if cursor.fetchone()[0]:
                raise ValueError(
                    "The benchmark database must contain no simulated operational records."
                )
    snapshot = DatasetSnapshot.objects.get(publication_status="COMPLETE")
    manifest = json.loads((SQL_ROOT.parents[1] / "olist/source-manifest.json").read_text())
    if (
        snapshot.archive_sha256 != manifest["archive_sha256"]
        or snapshot.dataset_ref != manifest["dataset_ref"]
        or snapshot.member_manifest["files"] != manifest["files"]
    ):
        raise ValueError("Use the accepted locked Olist snapshot in the benchmark database.")


def query_rows(sql, params):
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        columns = [field[0] for field in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def run_experiment(*, expected_database, output, warmups=3, repetitions=7):
    if type(warmups) is not int or warmups < 2 or type(repetitions) is not int or repetitions < 7:
        raise ValueError("Use at least two warm-ups and seven measured runs per phase.")
    validate_target(expected_database)
    # Refuse to overwrite evidence before acquiring locks or issuing maintenance/DDL.
    output.mkdir(parents=True, exist_ok=False)
    report = {
        "status": "FAILED",
        "database": expected_database,
        "warmups_per_phase": warmups,
        "measured_runs_per_phase": repetitions,
        "phases": {},
        "cache_conditions": (
            "Warm PostgreSQL shared/OS caches. Fingerprinting, VACUUM, "
            "warm-ups and index creation read data. No cold-cache claim."
        ),
        "limitations": (
            "Sequential phases, EXPLAIN instrumentation, planner sampling history, "
            "background work and host scheduling limit generalization. "
            "No forced planner settings or synthetic sales."
        ),
    }
    locked = created = False
    old_prepare = None
    prepare_changed = False
    cleanup_error = None
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(%s,%s)", BENCHMARK_LOCK)
            locked = cursor.fetchone()[0]
            if not locked:
                raise ValueError("Another benchmark is already running.")
            cursor.execute("SELECT to_regclass(%s)", ["public." + INDEX_NAME])
            if cursor.fetchone()[0] is not None:
                raise ValueError(
                    "The candidate index name already exists; existing objects are never dropped."
                )
            cursor.execute(
                "SELECT indexname,indexdef FROM pg_indexes WHERE schemaname='public' "
                "AND tablename IN ('olist_order','olist_customer') ORDER BY tablename,indexname"
            )
            report["existing_indexes"] = [
                dict(zip(["name", "definition"], row, strict=True)) for row in cursor.fetchall()
            ]
            cursor.execute("SELECT version(),current_setting('TimeZone')")
            report["postgresql"], report["database_timezone"] = cursor.fetchone()
            cursor.execute(
                "SELECT pg_relation_size('olist_order'),pg_total_relation_size('olist_order'),"
                "pg_database_size(current_database())"
            )
            (
                report["order_heap_bytes"],
                report["order_total_bytes_before"],
                report["database_bytes_before"],
            ) = cursor.fetchone()
            cursor.execute(
                "SELECT name,setting,unit FROM pg_settings WHERE name IN "
                "('shared_buffers','effective_cache_size','work_mem','random_page_cost',"
                "'seq_page_cost','enable_seqscan','max_parallel_workers_per_gather','jit',"
                "'default_statistics_target','track_io_timing') ORDER BY name"
            )
            report["settings"] = [
                dict(zip(["name", "setting", "unit"], row, strict=True))
                for row in cursor.fetchall()
            ]
        connection.ensure_connection()
        old_prepare = connection.connection.prepare_threshold
        connection.connection.prepare_threshold = None
        prepare_changed = True
        report["driver_prepare_threshold"] = None
        report["dataset_before"] = fingerprint_dataset()
        sql = (SQL_ROOT / "benchmark_delivered_page.sql").read_text()
        params = parameters(start="2017-11-01 00:00:00", end="2017-12-01 00:00:00")
        params = {"start": params["start"], "end": params["end"], "row_limit": 100}
        report.update(
            {
                "sql": sql,
                "sql_sha256": hashlib.sha256(sql.encode()).hexdigest(),
                "parameters": params,
                "candidate_index_sql": INDEX_SQL,
            }
        )
        reference = query_rows(sql, params)
        if not reference:
            raise ValueError("The benchmark query must return real historical rows.")
        report["result_row_count"] = len(reference)
        report["ordered_result_sha256"] = ordered_result_hash(reference)
        with connection.cursor() as cursor:
            for table in ["olist_order", "olist_customer", "olist_dataset_snapshot"]:
                cursor.execute(f"VACUUM (ANALYZE) {table}")
        report["statistics_policy"] = (
            "VACUUM (ANALYZE) before all phases; unchanged table statistics reused after "
            "CREATE/DROP INDEX because no facts change."
        )
        for phase in ["baseline", "indexed", "control_baseline"]:
            if phase == "indexed":
                with connection.cursor() as cursor:
                    start = time.perf_counter()
                    cursor.execute(INDEX_SQL)
                    created = True
                    report["index_build_client_ms"] = (time.perf_counter() - start) * 1000
                    cursor.execute("SELECT pg_relation_size(%s::regclass)", [INDEX_NAME])
                    report["index_bytes"] = cursor.fetchone()[0]
            elif phase == "control_baseline":
                with connection.cursor() as cursor:
                    cursor.execute(f"DROP INDEX {INDEX_NAME}")
                    created = False
            rows = query_rows(sql, params)
            if ordered_result_hash(rows) != report["ordered_result_sha256"]:
                raise ValueError("Query results changed across experiment phases.")
            measurements = []
            for number in range(warmups + repetitions):
                start = time.perf_counter()
                with connection.cursor() as cursor:
                    cursor.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql, params)
                    plan = cursor.fetchone()[0]
                elapsed = (time.perf_counter() - start) * 1000
                label = "warmup" if number < warmups else "measured"
                sequence = number + 1 if label == "warmup" else number - warmups + 1
                filename = f"{phase}-{label}-{sequence:02d}.json"
                with (output / filename).open("x") as handle:
                    json.dump(plan, handle, indent=2, default=serializable)
                    handle.write("\n")
                if label == "measured":
                    root = plan[0]["Plan"]
                    measurements.append(
                        {
                            "plan_file": filename,
                            "execution_ms": plan[0]["Execution Time"],
                            "planning_ms": plan[0]["Planning Time"],
                            "client_ms": elapsed,
                            "shared_hit_blocks": root.get("Shared Hit Blocks", 0),
                            "shared_read_blocks": root.get("Shared Read Blocks", 0),
                            "temp_written_blocks": root.get("Temp Written Blocks", 0),
                            "root_node": root["Node Type"],
                        }
                    )
            report["phases"][phase] = {
                "measurements": measurements,
                "median_execution_ms": statistics.median(
                    row["execution_ms"] for row in measurements
                ),
                "median_planning_ms": statistics.median(row["planning_ms"] for row in measurements),
                "result_sha256": ordered_result_hash(rows),
            }
        report["final_ordered_result_sha256"] = ordered_result_hash(query_rows(sql, params))
        if report["final_ordered_result_sha256"] != report["ordered_result_sha256"]:
            raise ValueError("Final query results differ from the initial ordered result.")
        report["dataset_after"] = fingerprint_dataset()
        if report["dataset_before"] != report["dataset_after"]:
            raise ValueError("Historical data changed during the experiment.")
        report["results_equivalent"] = True
        report["data_unchanged"] = True
        report["status"] = "SUCCEEDED"
    except Exception:
        report["failure_code"] = "BENCHMARK_OPERATION_FAILED"
        raise
    finally:
        try:
            if created:
                with connection.cursor() as cursor:
                    cursor.execute(f"DROP INDEX {INDEX_NAME}")
                created = False
            report["candidate_created_by_run_remaining"] = created
            with connection.cursor() as cursor:
                cursor.execute("SELECT to_regclass(%s)", ["public." + INDEX_NAME])
                report["candidate_index_present_after"] = cursor.fetchone()[0] is not None
            if report["status"] == "SUCCEEDED" and report["candidate_index_present_after"]:
                raise RuntimeError("The experiment did not restore the candidate index state.")
        except Exception as error:
            report["status"] = "FAILED"
            report["failure_code"] = "BENCHMARK_CLEANUP_FAILED"
            report["candidate_created_by_run_remaining"] = created
            cleanup_error = error
        finally:
            try:
                if locked:
                    try:
                        with connection.cursor() as cursor:
                            cursor.execute("SELECT pg_advisory_unlock(%s,%s)", BENCHMARK_LOCK)
                    except Exception as error:
                        connection.close()
                        report["status"] = "FAILED"
                        report["failure_code"] = "BENCHMARK_LOCK_RELEASE_FAILED"
                        cleanup_error = error
                if prepare_changed and connection.connection is not None:
                    connection.connection.prepare_threshold = old_prepare
            finally:
                with (output / "summary.json").open("x") as handle:
                    json.dump(report, handle, indent=2, default=serializable)
                    handle.write("\n")
    if cleanup_error is not None:
        raise RuntimeError(
            "Benchmark cleanup failed; inspect retained evidence."
        ) from cleanup_error
    return report
