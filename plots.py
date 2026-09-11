import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from network import MeasurementError


def save_figure(figure, path_without_extension):
    figure.tight_layout()
    figure.savefig(path_without_extension.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(figure)


def plot_distance_vs_rtt(results, output):
    usable = [
        result
        for result in results
        if result.distance_km is not None
        and result.rtt_min_ms is not None
        and result.rtt_avg_ms is not None
        and result.rtt_max_ms is not None
    ]
    if not usable:
        raise MeasurementError("No usable ping/geolocation pairs are available")

    distance = [result.distance_km for result in usable]
    minimum = [result.rtt_min_ms for result in usable]
    average = [result.rtt_avg_ms for result in usable]
    maximum = [result.rtt_max_ms for result in usable]

    figure, axis = plt.subplots(figsize=(8, 5))
    axis.vlines(distance, minimum, maximum, color="0.75", linewidth=0.7, label="Min-max range")
    axis.scatter(distance, average, s=20, color="tab:blue", alpha=0.8, label="Average RTT")

    own = [result for result in usable if result.endpoint.is_own_ip]
    if own:
        axis.scatter(
            [result.distance_km for result in own],
            [result.rtt_avg_ms for result in own],
            s=50,
            color="tab:red",
            marker="x",
            label="Current public IP",
        )

    axis.set(
        title="Geographical distance versus ping RTT",
        xlabel="Great-circle distance (km)",
        ylabel="Round-trip time (ms)",
    )
    axis.grid(True, alpha=0.25)
    axis.legend(fontsize=8)
    save_figure(figure, output / "q1-distance-vs-rtt")


def plot_latency_breakdown(results, output):
    if not results:
        raise MeasurementError("No successful traceroutes are available")

    labels = [result.endpoint.resolved_ip for result in results]
    positions = list(range(len(results)))
    bottoms = [0.0] * len(results)
    component_count = max(len(result.components) for result in results)
    colors = plt.get_cmap("tab20").colors

    figure, axis = plt.subplots(figsize=(9, 5.5))
    for index in range(component_count):
        heights = [
            result.components[index].latency_ms if index < len(result.components) else 0
            for result in results
        ]
        bars = axis.bar(
            positions,
            heights,
            bottom=bottoms,
            color=colors[index % len(colors)],
            edgecolor="white",
            linewidth=0.3,
        )
        for result_index, bar in enumerate(bars):
            if heights[result_index] >= 4:
                axis.text(
                    bar.get_x() + bar.get_width() / 2,
                    bottoms[result_index] + heights[result_index] / 2,
                    results[result_index].components[index].hop_range,
                    ha="center",
                    va="center",
                    fontsize=7,
                )
        bottoms = [bottom + height for bottom, height in zip(bottoms, heights)]

    axis.set(
        title="Estimated per-hop latency breakdown",
        xlabel="Destination IP (segment labels show hop ranges)",
        ylabel="Non-negative RTT increment (ms)",
    )
    axis.set_xticks(positions, labels, rotation=20, ha="right")
    axis.grid(True, axis="y", alpha=0.25)
    save_figure(figure, output / "q2-per-hop-latency-breakdown")


def plot_hop_count_vs_rtt(results, output):
    if not results:
        raise MeasurementError("No successful traceroutes are available")

    figure, axis = plt.subplots(figsize=(7.5, 5))
    axis.scatter(
        [result.destination_hop for result in results],
        [result.final_rtt_ms for result in results],
        s=45,
        color="tab:blue",
    )
    for result in results:
        axis.annotate(
            result.endpoint.resolved_ip or result.endpoint.target,
            (result.destination_hop, result.final_rtt_ms),
            xytext=(4, 4),
            textcoords="offset points",
            fontsize=7,
        )
    axis.set(
        title="Traceroute hop count versus destination RTT",
        xlabel="Hop count",
        ylabel="Final-hop median RTT (ms)",
    )
    axis.grid(True, alpha=0.25)
    save_figure(figure, output / "q2-hop-count-vs-rtt")
