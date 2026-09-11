#let data = json("/results/report-data.json")

#set page(
  paper: "us-letter",
  margin: (top: 0.85in, bottom: 0.85in, left: 1in, right: 1in),
  numbering: "1",
  number-align: center + bottom,
)
#set text(size: 10.5pt)
#set par(justify: true, leading: 0.65em)
#set heading(numbering: "1.")

#let number(value, digits: 2) = if value == none { "N/A" } else {
  let rounded = str(calc.round(value, digits: digits))
  if digits == 0 {
    rounded
  } else {
    let parts = rounded.split(".")
    let fraction = if parts.len() == 1 { "" } else { parts.last() }
    parts.first() + "." + fraction + "0" * (digits - fraction.len())
  }
}

#align(center)[
  #text(18pt, weight: "bold")[Network Latencies, Ping, and Traceroute]
  #v(0.35em)
  #text(11pt)[Assignment 1]

  #v(1.4em)
  #text(11pt, weight: "bold")[Marko Kovacevic]

  #v(1.2em)
  CS 42200: Computer Networks
  #linebreak()
  Purdue University · Fall 2026
  #linebreak()
  Instructor: Vamsi Addanki
  #linebreak()
  TAs: Youngsuk Kim, Xiao Luo, and Albert Vo

  #v(1.2em)
  September 8, 2026
]

#v(1.5em)

#text(13pt, weight: "bold")[Abstract]

Round-trip time (RTT) is influenced by the geographical separation between two hosts and by the network path between them. This report uses ping and traceroute measurements to examine how RTT changes with geographical distance, how measured RTT changes across the responding hops of a route, and whether paths with more hops have higher RTT. A Python script collected the measurements and generated all three plots in one run. RTT generally increased with geographical distance, but the five traceroutes showed no consistent increase in RTT with hop count. Latency was also not spread evenly across the hops.

= Introduction

Geographical distance affects how long a signal must travel, but packets do not necessarily follow the geographically shortest route. The first part of this report compares distance with the minimum, average, and maximum RTT measured by ping. The plot compares these values with distance and shows how RTT varied during the measurements.

The second part uses traceroute to examine the intermediate hops on five network paths. Estimated latency at each hop is shown in a stacked bar chart, and destination RTT is compared with the number of hops in each path. Together, these plots show how cumulative RTT changed between responding hops and whether a larger hop count corresponded to a larger RTT.

All measurements and plots were produced automatically by the script. Because routes and network conditions change, the results describe this run and may differ in another run.

#pagebreak()

= Methodology

== Targets and ping measurements

The input was the `listed_iperf3_servers.json` file downloaded from #link("https://iperf3serverlist.net/")[iperf3serverlist.net]. The script read the `IP/HOST` field from every entry, resolved hostnames to IPv4 addresses, found the machine's public IPv4 address, and added that address as another target. It used `ip-api.com` to look up the latitude and longitude of the source and each destination automatically.

Ping sent #data.metadata.ping_count Internet Control Message Protocol (ICMP) Echo Requests to each target and timed the corresponding Echo Replies, so each RTT covered both the forward and return network paths. For each target that responded, the script recorded the minimum, average, and maximum RTT reported by `ping`. A target with no valid RTT was marked as non-responsive instead of being given an incorrect value of zero.

== Geographical distance

The script used the Haversine formula to calculate the geographical distance between the source and each destination from their latitude and longitude. This estimates the great-circle distance over the Earth's surface; it does not measure the actual path taken by packets.

Each blue point in the distance plot shows one destination's average RTT. Its gray vertical line runs from the minimum RTT to the maximum RTT. This shows all three required RTT values without using three separate points for one destination.

== Traceroute measurements

The script tried destinations in random order until five traceroutes reached their destination. Linux traceroute sent #data.metadata.traceroute_queries_per_hop UDP probes with Time to Live (TTL) values beginning at one and increasing up to #data.metadata.traceroute_max_hops. Each router reduced the TTL by one; when it reached zero, the router discarded the probe and normally returned an ICMP Time Exceeded message, identifying the responding hop and the RTT to it. A probe reaching the destination's unused UDP port normally caused an ICMP Port Unreachable response. The script recognized completion when the destination's resolved IP address appeared with a valid RTT. An `*` meant no response arrived within the #number(data.metadata.traceroute_wait_seconds, digits: 0)-second wait, not that no router existed at that hop.

The script used the median RTT from the three probes for each responding hop. When all three probes responded, this was the middle RTT after sorting the measurements, so one unusually slow probe had less effect on the result.

Traceroute reports the RTT from the source to each hop, not the latency of the individual link leading to that hop. To estimate the latency added at each hop, the script subtracted the previous responding hop's RTT. If intermediate hops returned `*`, one estimate covered the whole gap between responding hops. Because traceroute uses separate probes, a later RTT can sometimes be smaller than an earlier one. Following the instructor's guidance in Piazza post 31, the script plotted these negative estimates as zero.

*Relevant code:* The complete workflow is in `assignment1.py`, lines 117–196. Ping measurement is in `network.py`, lines 206–248; traceroute measurement and per-hop calculation are in lines 269–339. Plot generation is in `plots.py`, lines 15–128.

== AI acknowledgment

Throughout this assignment, I used ChatGPT and Codex to help me understand the material and develop the solution. Before coding, I used them to clarify the requirements and understand the concepts and purpose behind each question. I also used them to help complete and debug parts of the code and improve the clarity and precision of the report. I questioned each suggestion rather than accepting it as given, examining the reasoning behind it and deciding whether it was relevant to the assignment. This helped me understand the purpose of each part of the final solution.

#pagebreak()

= Results and discussion

== Question 1: Distance versus RTT

The input file listed #data.q1.listed_endpoints endpoints. Adding the current public IP produced #data.q1.total_targets_including_own targets. Of these, #data.q1.plotted_targets returned all #data.metadata.ping_count ping replies and had usable geolocation, so they were plotted. Another #data.q1.ping_status_counts.at("unresponsive", default: 0) did not respond, and #data.q1.ping_status_counts.at("resolution_failed", default: 0) hostname did not resolve.

#if data.q1.own_ip_status == "unresponsive" [The current public IP was one of the non-responsive targets. It was included and pinged, but because it returned no RTT values, it could not be shown in the distance plot.]

#figure(
  image("/results/q1-distance-vs-rtt.pdf", width: 100%),
  caption: [Geographical distance versus average ping RTT. Gray vertical lines span each destination's observed minimum to maximum RTT.],
)

*Does distance relate to RTT?* Yes. The plot has a clear overall upward pattern: nearby targets generally had lower RTTs, while distant targets generally had higher RTTs. Greater distance increases propagation delay because the signal must travel farther. However, the plot uses the shortest geographical distance between two locations, while ping measures RTT over the complete forward and return network paths. Those paths may be longer, so geographical distance explains the overall trend but not the exact RTT.

*What do minimum and maximum RTT show?* Both generally increased with distance, as shown by the upward movement of the lower and upper ends of the gray lines. Minimum RTT is the lowest of the ten measurements and is the closest observed estimate of the path's baseline RTT because it is least affected by temporary waiting. A high minimum can reflect a long or indirect route or another persistent delay along the path. Maximum RTT includes that baseline plus the largest temporary delay observed. Since a destination's distance does not change during the ten pings, the difference between its minimum and maximum must come from changing network conditions rather than distance. Temporary queueing is a likely cause, although route changes or delayed handling of ping packets could also contribute. Ping alone cannot distinguish among these causes. The blue point is the arithmetic mean of all ten RTTs and does not have to lie at the midpoint of the gray line.

#pagebreak()

== Question 2: Latency at each hop

The script tried #data.q2.attempted_destinations destinations before #data.q2.successful_destinations traceroutes completed. In the table, *Hidden* is the number of intermediate hops that returned `*`. *Set to 0* is the number of negative latency estimates that were changed to zero under the instructor's rule.

#table(
  columns: (1.2fr, 0.6fr, 0.9fr, 0.7fr, 0.7fr),
  inset: 5pt,
  table.header([Resolved IP], [Hops], [Final RTT (ms)], [Hidden], [Set to 0]),
  ..data.q2.selected.map(item => (
    [#item.resolved_ip],
    [#item.destination_hop],
    [#number(item.final_rtt_ms)],
    [#item.hidden_hops],
    [#item.negative_increments_clamped],
  )).flatten(),
)

#figure(
  image("/results/q2-per-hop-latency-breakdown.pdf", width: 100%),
  caption: [Estimated latency at each responding hop. A segment label may cover a range when intermediate hops did not respond.],
)

*What does the latency breakdown show?* The estimated increases in RTT were not equal across the paths. A large segment means that the RTT at one responding hop was substantially higher than at the previous responding hop, but it does not identify the exact link or cause. A long physical link would add propagation delay, queueing would make a probe wait, and a router could delay its traceroute reply. If intermediate hops did not respond, one segment covers the entire gap, so the increase cannot be assigned to one hop. Some estimates were negative because each hop was measured with separate probes whose RTTs can vary. These values were set to zero as instructed, which means the stacked total can be greater than the final RTT.

#pagebreak()

== Question 2: Hop count versus RTT

#figure(
  image("/results/q2-hop-count-vs-rtt.pdf", width: 90%),
  caption: [Hop count versus the median RTT measured at the destination.],
)

*How does hop count relate to RTT?* Not consistently in these five paths. The 23-hop Phoenix destination was about 2,354 km away and had an RTT of 59.12 ms, whereas the 14-hop Denmark destination was about 6,729 km away and had an RTT of 122.70 ms. This directly shows that more visible hops did not always mean higher RTT. The 24-hop Hong Kong destination was both the farthest, at about 12,702 km, and the slowest, at 306.77 ms, so its high RTT cannot be attributed to hop count without considering its much greater distance. Hop count records visible routing steps, not the physical length or delay of each step. These five paths show that hop count alone did not explain destination RTT in this run. They are too few to establish a general relationship between hop count and RTT across the Internet.

= Limitations and reproducibility

IP geolocation is approximate. The calculated distance is the shortest distance over the Earth's surface between the source and destination coordinates. Packets instead travel through a sequence of routers and physical links, which may follow a longer route. The forward and return paths may also differ. Ping and traceroute results can change as routes and network load change. Five traceroutes are enough to compare the selected paths, but not to conclude how hop count and RTT relate across the Internet.

The code, input file, and instructions for repeating the measurements are available at #link("https://github.com/kovaceviccz/cs422-assignment-1")[github.com/kovaceviccz/cs422-assignment-1].

= Conclusion

Ping RTT generally increased with geographical distance. Minimum RTT showed the best observed performance to each destination, while the range up to the maximum showed how much latency varied across the ten ping requests. Traceroute showed that more visible hops did not necessarily mean higher RTT and that the estimated RTT increases were uneven across hops. Together, ping measured end-to-end latency, while traceroute showed how cumulative RTT changed across responding hops.
