# CS 422 Assignment 1

This repository contains the code and report for the first CS 422 assignment on ping, traceroute, and network latency.

## Setup

Linux, Python 3.10 or later, `ping`, `traceroute`, and Typst are required. On Ubuntu:

```bash
sudo apt-get install python3-venv iputils-ping traceroute
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

[Typst](https://github.com/typst/typst#installation) must also be installed and available as `typst`.

## Run

From the repository root:

```bash
.venv/bin/python assignment1.py listed_iperf3_servers.json
```

## Files

```text
assignment1.py                  main script
network.py                      network measurements
plots.py                        plot generation
listed_iperf3_servers.json      input downloaded from iperf3serverlist.net
report.typ                      report source
requirements.txt                Python dependencies
results/                        generated plots, report data, and report
```

The script creates these results:

```text
results/
  q1-distance-vs-rtt.pdf
  q2-per-hop-latency-breakdown.pdf
  q2-hop-count-vs-rtt.pdf
  report-data.json
  assignment-1-report.pdf
```

`report-data.json` supplies values to the [Typst report](results/assignment-1-report.pdf).
