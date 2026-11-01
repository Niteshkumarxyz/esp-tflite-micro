# Benchmark patch plan
# Add a CLI command: benchmark <measured_runs>
# Use 10 warm-up runs, rotate through 10 bundled images,
# suppress per-run output during benchmark, collect Invoke timings,
# and print summary statistics at the end.
# This is a plan only; source files are not modified by this script.
