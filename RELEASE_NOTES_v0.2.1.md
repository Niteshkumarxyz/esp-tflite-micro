# Release v0.2.1 (1 November 2026)

Corrections to release v0.2.0. No measured data, log, firmware image or evidence package changed.

| File | Change |
|---|---|
| examples/rq3_layout_iram_2026-11-01/README.md | The editor's e-mail that asked for these experiments is dated 30 October 2026, not 1 November. The experiments ran on 1 November. |
| examples/rq3_layout_iram_2026-11-01/run_editor_experiments_2026-11-01.py | The same date correction in the first line of the docstring. No code changed. |
| examples/person_detection/chapter_evidence/skip_nudge_requantize_analysis_2026-11-01/README.md | The same date correction. SHA256SUMS.txt in that folder is updated for this file only. |
| examples/person_detection/chapter_evidence/chapter_figures_v21/scripts/figs21.py and fig02_bench.py | They now read their inputs and write their outputs relative to their own folder, so they run from a fresh clone. The plotting code is unchanged. |
| examples/person_detection/chapter_evidence/chapter_figures_v21/README.md | Describes the new paths and the reproduction check below. |

Reproduction check: from a fresh copy of this release, `figs21.py`, `fig02_bench.py` and `make_figs.py` redraw figures 2, 4, 5, 6, 7, 9, 10, 11, 12, 13 and 14 pixel for pixel identical to the files in `chapter_figures_v21/figures/` (Python 3, matplotlib 3.11.2).

Everything else is as described in RELEASE_NOTES_v0.2.0.md. SHA256SUMS_v0.2.0.txt keeps the hashes of release v0.2.0; for the files changed here, use SHA256SUMS_v0.2.1.txt. `release_v0.2.1_files.txt` lists the files committed in this release.
