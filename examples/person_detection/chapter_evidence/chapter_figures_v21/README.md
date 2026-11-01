# Figures of the chapter manuscript (version 21)

The 14 figures of "Same Model, Different Robot: Checking Int8 Runtimes Before the Robot Moves" (manuscript version 21, 30 October 2026), with the scripts and data that drew them.

`figures/` holds the PNG files exactly as placed in the manuscript. The scripts write PNG and 300 dpi TIF files. `figs21.py` and `fig02_bench.py` read `data/` and `../rq4_boot_kat_2026-10-29/` and write to `output/`; `make_figs.py` and `diagrams.py` read `data/` and write next to themselves in `scripts/`.

| Figure | File | Drawn by | Data |
|---|---|---|---|
| 1 | Figure01_int8_layer.png | concept diagram; drawing script not kept | none (no measured values) |
| 2 | Figure02_bench.png | scripts/fig02_bench.py | none (bench diagram) |
| 3 | Figure03_hello_world.png | drawing script not kept | examples/hello_world/cycle_count_measurements.csv, cycle_count_raw_log.txt, and evidence/cycle_count/ |
| 4 | Figure04_outputs_12_images.png | scripts/figs21.py | data/rq4_w1.json |
| 5 | Figure05_operator_level.png | scripts/figs21.py | data/w1_oplevel.json |
| 6 | Figure06_w2_open_loop.png | scripts/figs21.py | data/rq4_w2.json |
| 7 | Figure07_w2_closed_loop.png | scripts/figs21.py | data/w2_eval_per_*_summary.json, data/w2_stress_per_*.json, data/stress_opt_per_*.json |
| 8 | Figure08_acceptance_test.png | scripts/diagrams.py (kat) | none (design diagram) |
| 9 | Figure09_rq4_detection.png | scripts/figs21.py | data/rq4_w1.json, data/rq4_w2.json |
| 10 | Figure10_board_test.png | scripts/figs21.py | ../rq4_boot_kat_2026-10-29/rq4_boot_kat_summary_20261029_203054.csv and boot_r1sr_1_20261029_203054.txt |
| 11 | Figure11_latency_100run.png | scripts/make_figs.py (fig_latency) | data/r1_100.csv, data/r2a_100.csv, data/r2_100.csv |
| 12 | Figure12_kernel_share.png | scripts/make_figs.py (fig_kernels) | data/host_ops.csv |
| 13 | Figure13_ten_hour.png | scripts/make_figs.py (fig_drift) | data/drift_minutes.csv |
| 14 | Figure14_r2_latency_by_build.png | scripts/figs21.py | values typed from the benchmark logs, noted in the script |

Run on 1 November 2026 with Python 3 and matplotlib 3.11.2, `figs21.py`, `fig02_bench.py` and `make_figs.py` redrew figures 2, 4, 5, 6, 7, 9, 10, 11, 12, 13 and 14 pixel for pixel identical to the files in `figures/`. `diagrams.py` (figure 8) renders SVG through a headless browser and was not rerun.

The file `data/rq4_w1.json` and the other JSON inputs are also inside `../rq4_w2_analysis_archive_2026-10-29/rq4_w2_analysis_archive_2026-10-29.zip`, together with the analysis scripts that wrote them.
