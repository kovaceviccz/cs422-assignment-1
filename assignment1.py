import json
import random
import shutil
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from network import (
    MeasurementError,
    add_distances,
    add_own_ip,
    geolocate_ips,
    get_origin,
    measure_ping,
    measure_traceroute,
    read_endpoints,
    resolve_endpoints,
)
from plots import (
    plot_distance_vs_rtt,
    plot_hop_count_vs_rtt,
    plot_latency_breakdown,
)


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"

PING_COUNT = 10
PING_WORKERS = 8
PING_INTERVAL = 0.2
PING_REPLY_TIMEOUT = 2.0

TRACE_COUNT = 5
TRACE_QUERIES = 3
TRACE_WAIT = 1.0
TRACE_MAX_HOPS = 30


def require_tools():
    missing = [
        name
        for name in ("ping", "traceroute", "typst")
        if shutil.which(name) is None
    ]
    if missing:
        raise MeasurementError(f"Missing command(s): {', '.join(missing)}. See README.md.")


def build_report_data(pings, traces, attempted_traces):
    plotted = [
        result
        for result in pings
        if result.distance_km is not None
        and result.rtt_min_ms is not None
        and result.rtt_avg_ms is not None
        and result.rtt_max_ms is not None
    ]
    return {
        "metadata": {
            "ping_count": PING_COUNT,
            "traceroute_queries_per_hop": TRACE_QUERIES,
            "traceroute_wait_seconds": TRACE_WAIT,
            "traceroute_max_hops": TRACE_MAX_HOPS,
        },
        "q1": {
            "listed_endpoints": sum(not result.endpoint.is_own_ip for result in pings),
            "total_targets_including_own": len(pings),
            "own_ip_status": next(
                result.status for result in pings if result.endpoint.is_own_ip
            ),
            "ping_status_counts": dict(
                sorted(Counter(result.status for result in pings).items())
            ),
            "plotted_targets": len(plotted),
        },
        "q2": {
            "attempted_destinations": attempted_traces,
            "successful_destinations": len(traces),
            "selected": [
                {
                    "resolved_ip": result.endpoint.resolved_ip,
                    "destination_hop": result.destination_hop,
                    "final_rtt_ms": result.final_rtt_ms,
                    "hidden_hops": sum(part.hidden_hops for part in result.components),
                    "negative_increments_clamped": sum(
                        part.clamped for part in result.components
                    ),
                }
                for result in traces
            ],
        },
    }


def compile_report():
    completed = subprocess.run(
        [
            "typst",
            "compile",
            "--root",
            str(ROOT),
            str(ROOT / "report.typ"),
            str(RESULTS / "assignment-1-report.pdf"),
        ],
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        raise MeasurementError(f"Typst compilation failed:\n{completed.stderr}")


def run(input_path):
    require_tools()
    RESULTS.mkdir(exist_ok=True)

    print("[1/8] Reading targets and resolving hostnames", flush=True)
    endpoints = read_endpoints(input_path.resolve())
    resolve_endpoints(endpoints)

    with requests.Session() as session:
        print("[2/8] Locating this machine's public IP", flush=True)
        origin = get_origin(session)
        add_own_ip(endpoints, origin)

        print("[3/8] Locating destination IPs", flush=True)
        locations = geolocate_ips(
            session,
            [endpoint.resolved_ip for endpoint in endpoints if endpoint.resolved_ip],
        )

    print(f"[4/8] Pinging {len(endpoints)} targets", flush=True)
    with ThreadPoolExecutor(max_workers=PING_WORKERS) as executor:
        pings = list(
            executor.map(
                lambda endpoint: measure_ping(
                    endpoint,
                    PING_COUNT,
                    PING_INTERVAL,
                    PING_REPLY_TIMEOUT,
                ),
                endpoints,
            )
        )
    add_distances(pings, locations, origin)

    print("[5/8] Plotting distance versus RTT", flush=True)
    plot_distance_vs_rtt(pings, RESULTS)

    print("[6/8] Finding five responsive traceroute destinations", flush=True)
    candidates = [
        endpoint
        for endpoint in endpoints
        if endpoint.resolved_ip and not endpoint.is_own_ip
    ]
    random.shuffle(candidates)

    attempted = 0
    traces = []
    for attempted, endpoint in enumerate(candidates, start=1):
        result = measure_traceroute(
            endpoint,
            TRACE_QUERIES,
            TRACE_WAIT,
            TRACE_MAX_HOPS,
        )
        print(f"      {endpoint.target}: {result.status}", flush=True)
        if result.status == "success":
            traces.append(result)
        if len(traces) == TRACE_COUNT:
            break

    if len(traces) < TRACE_COUNT:
        raise MeasurementError(
            f"Only {len(traces)} traceroutes completed after {attempted} attempts"
        )

    print("[7/8] Plotting traceroute results", flush=True)
    plot_latency_breakdown(traces, RESULTS)
    plot_hop_count_vs_rtt(traces, RESULTS)
    report_data = build_report_data(
        pings,
        traces,
        attempted,
    )
    (RESULTS / "report-data.json").write_text(
        json.dumps(report_data, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[8/8] Compiling the Typst report", flush=True)
    compile_report()


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {Path(sys.argv[0]).name} INPUT.json", file=sys.stderr)
        return 2
    try:
        run(Path(sys.argv[1]))
    except (MeasurementError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Complete: {RESULTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
