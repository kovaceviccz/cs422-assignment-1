import ipaddress
import json
import math
import re
import socket
import statistics
import subprocess
from dataclasses import dataclass

import requests


ORIGIN_URL = "http://ip-api.com/json/"
BATCH_URL = "http://ip-api.com/batch"
GEO_FIELDS = "status,message,query,lat,lon,city,regionName,country"


class MeasurementError(RuntimeError):
    """A failure that prevents the measurement run from producing valid results."""


@dataclass
class Endpoint:
    target: str
    resolved_ip: str | None = None
    is_own_ip: bool = False


@dataclass
class PingResult:
    endpoint: Endpoint
    status: str
    rtt_min_ms: float | None
    rtt_avg_ms: float | None
    rtt_max_ms: float | None
    distance_km: float | None = None


@dataclass
class TraceHop:
    number: int
    rtt_ms: float | None
    is_destination: bool


@dataclass
class HopComponent:
    hop_range: str
    hidden_hops: int
    latency_ms: float
    clamped: bool


@dataclass
class TracerouteResult:
    endpoint: Endpoint
    status: str
    destination_hop: int | None
    final_rtt_ms: float | None
    components: list[HopComponent]


def read_endpoints(path):
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MeasurementError(f"Cannot read input JSON: {path}") from exc
    if not isinstance(rows, list) or not rows:
        raise MeasurementError("Input JSON must be a non-empty list")

    endpoints = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise MeasurementError(f"Input row {index} is not an object")
        target = str(row.get("IP/HOST", "")).strip()
        if not target:
            raise MeasurementError(f"Input row {index} has no IP/HOST value")
        endpoints.append(Endpoint(target))
    return endpoints


def resolve_ipv4(target):
    try:
        address = ipaddress.ip_address(target)
        return str(address) if address.version == 4 else None
    except ValueError:
        answers = socket.getaddrinfo(target, None, socket.AF_INET, socket.SOCK_DGRAM)
        return answers[0][4][0] if answers else None


def resolve_endpoints(endpoints):
    for endpoint in endpoints:
        try:
            endpoint.resolved_ip = resolve_ipv4(endpoint.target)
        except OSError:
            pass


def request_json(session, method, url, **kwargs):
    try:
        response = session.request(method, url, timeout=30, **kwargs)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        raise MeasurementError(f"Request failed for {url}: {exc}") from exc


def get_origin(session):
    data = request_json(
        session,
        "GET",
        ORIGIN_URL,
        params={"fields": GEO_FIELDS},
    )
    if not isinstance(data, dict) or data.get("status") != "success":
        message = data.get("message", "unknown error") if isinstance(data, dict) else data
        raise MeasurementError(f"Could not geolocate the current public IP: {message}")
    return data


def add_own_ip(endpoints, origin):
    public_ip = str(origin["query"])
    for endpoint in endpoints:
        if endpoint.resolved_ip == public_ip:
            endpoint.is_own_ip = True
            return
    endpoints.append(Endpoint(public_ip, resolved_ip=public_ip, is_own_ip=True))


def geolocate_ips(session, ips):
    locations = {}
    unique_ips = sorted(set(ips))
    # The batch endpoint accepts at most 100 IP addresses per request.
    for start in range(0, len(unique_ips), 100):
        batch = unique_ips[start : start + 100]
        data = request_json(
            session,
            "POST",
            BATCH_URL,
            params={"fields": GEO_FIELDS},
            json=batch,
        )
        if not isinstance(data, list) or len(data) != len(batch):
            raise MeasurementError("Geolocation response did not match the request")
        for item in data:
            if isinstance(item, dict) and item.get("query"):
                locations[str(item["query"])] = item
    return locations


def haversine_km(lat1, lon1, lat2, lon2):
    """Return the great-circle distance between two coordinates."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * 6371.0088 * math.asin(math.sqrt(a))


def add_distances(results, locations, origin):
    for result in results:
        location = locations.get(result.endpoint.resolved_ip or "")
        if not location or location.get("status") != "success":
            continue
        try:
            latitude = float(location["lat"])
            longitude = float(location["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        result.distance_km = haversine_km(
            float(origin["lat"]),
            float(origin["lon"]),
            latitude,
            longitude,
        )


PING_PACKETS = re.compile(
    r"(?P<sent>\d+)\s+packets transmitted,\s+"
    r"(?P<received>\d+)\s+(?:packets\s+)?received"
)
PING_RTT = re.compile(
    r"(?:rtt|round-trip) min/avg/max/(?:mdev|stddev)\s*=\s*"
    r"(?P<min>[\d.]+)/(?P<avg>[\d.]+)/(?P<max>[\d.]+)/[\d.]+\s*ms"
)
TRACE_LINE = re.compile(r"^\s*(?P<hop>\d+)\s+(?P<body>.*)$")
TRACE_RTT = re.compile(r"(?P<rtt>[\d.]+)\s*ms")
IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")


def parse_ping_output(output):
    packets = PING_PACKETS.search(output)
    summary = PING_RTT.search(output)
    return {
        "sent": int(packets.group("sent")) if packets else None,
        "received": int(packets.group("received")) if packets else None,
        "rtt_min_ms": float(summary.group("min")) if summary else None,
        "rtt_avg_ms": float(summary.group("avg")) if summary else None,
        "rtt_max_ms": float(summary.group("max")) if summary else None,
    }


def measure_ping(endpoint, count, interval, reply_timeout):
    if endpoint.resolved_ip is None:
        return PingResult(endpoint, "resolution_failed", None, None, None)

    command = [
        "ping",
        "-4",
        "-n",
        "-c",
        str(count),
        "-i",
        str(interval),
        "-W",
        str(reply_timeout),
        endpoint.resolved_ip,
    ]
    process_timeout = count * interval + reply_timeout + 8
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=process_timeout,
        )
    except subprocess.TimeoutExpired:
        return PingResult(endpoint, "timeout", None, None, None)

    values = parse_ping_output(completed.stdout + completed.stderr)
    if completed.returncode not in (0, 1) or values["received"] is None:
        status = "command_error"
    elif values["received"] == 0:
        status = "unresponsive"
    elif values["received"] < values["sent"]:
        status = "partial"
    else:
        status = "success"
    return PingResult(
        endpoint,
        status,
        values["rtt_min_ms"],
        values["rtt_avg_ms"],
        values["rtt_max_ms"],
    )


def parse_traceroute_output(output, destination_ip):
    hops = []
    for line in output.splitlines():
        match = TRACE_LINE.match(line)
        if not match:
            continue
        body = match.group("body")
        rtts = [float(item.group("rtt")) for item in TRACE_RTT.finditer(body)]
        hops.append(
            TraceHop(
                int(match.group("hop")),
                statistics.median(rtts) if rtts else None,
                destination_ip in IPV4.findall(body),
            )
        )
    return hops


def per_hop_components(hops, destination_hop):
    """Apply the subtraction, gap, and negative-value rules from Piazza @31."""
    components = []
    previous_hop, previous_rtt = 0, 0.0
    for hop in hops:
        if hop.number > destination_hop:
            break
        if hop.rtt_ms is None:
            continue
        start = previous_hop + 1
        hop_range = str(hop.number) if start == hop.number else f"{start}-{hop.number}"
        difference = hop.rtt_ms - previous_rtt
        components.append(
            HopComponent(
                hop_range,
                hidden_hops=max(0, hop.number - previous_hop - 1),
                latency_ms=max(0, difference),
                clamped=difference < 0,
            )
        )
        previous_hop, previous_rtt = hop.number, hop.rtt_ms
    return components


def measure_traceroute(endpoint, queries, wait_seconds, max_hops):
    if endpoint.resolved_ip is None:
        return TracerouteResult(endpoint, "resolution_failed", None, None, [])

    # Linux traceroute uses UDP probes by default and does not require root.
    command = [
        "traceroute",
        "-4",
        "-n",
        "-q",
        str(queries),
        "-w",
        str(wait_seconds),
        "-m",
        str(max_hops),
        endpoint.resolved_ip,
    ]
    process_timeout = max_hops * queries * wait_seconds + 15
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=process_timeout,
        )
        output = completed.stdout + completed.stderr
        fallback_status = "command_error" if completed.returncode else "unresponsive"
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        fallback_status = "timeout"

    hops = parse_traceroute_output(output, endpoint.resolved_ip)
    destination = next(
        (hop for hop in hops if hop.is_destination and hop.rtt_ms is not None),
        None,
    )
    if destination is None:
        return TracerouteResult(endpoint, fallback_status, None, None, [])
    return TracerouteResult(
        endpoint,
        "success",
        destination.number,
        destination.rtt_ms,
        per_hop_components(hops, destination.number),
    )
