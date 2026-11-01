"""Compare v0.1.0 optimized ESP-NN board traces (29 Oct) with the ESP32 R1 reference traces (25 Oct).

For every image that has a capture in chapter_evidence/rq1_trace_board_capture_2026-10-29/,
this script rebuilds each of the 31 operator outputs from its RQ1_RAW chunks, checks the
rebuilt bytes against the summary the board itself printed (n, min, max, sum, FNV-1a),
does the same for the matching R1 reference log, and compares the two byte for byte.

Inputs are only read. Outputs are new files in this script's own folder.
Usage (any Python 3):  python compare_v010_trace_vs_r1.py
"""
import csv
import hashlib
import json
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVID = HERE.parent                                   # chapter_evidence
PROJECT = EVID.parent                                # person_detection
CAPTURES = EVID / "rq1_trace_board_capture_2026-10-29"
ARM_ZIP = EVID / "arm_qemu_rq1_20261027" / "arm_qemu_rq1_20261027.zip"
BUILD = PROJECT / "build_rq1_trace_opt_20261029"
EXPECTED_OPS = 31

RAW_RE = re.compile(r"^RQ1_RAW,run=1,op=(\d+),tensor=(\d+),offset=(\d+),count=(\d+),hex=([0-9a-fA-F]+)$")
TRACE_RE = re.compile(r"^RQ1_TRACE,run=1,op=(\d+),tensor=(\d+),n=(\d+),min=(-?\d+),max=(-?\d+),sum=(-?\d+),fnv1a=([0-9a-fA-F]+)$")
RESULT_RE = re.compile(r"IMAGE_RESULT,image=(\d+),invoke_ok=1,person_raw_int8=(-?\d+),no_person_raw_int8=(-?\d+)")
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fnv1a(data):
    h = 0x811C9DC5
    for b in data:
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def to_int8(data):
    return [b - 256 if b > 127 else b for b in data]


def parse(path):
    """Return {op: {...}} with rebuilt bytes and self-consistency checks, plus extras."""
    text = Path(path).read_bytes().decode("utf-8", errors="replace").replace("\r", "")
    traces, chunks = {}, {}
    banner = {}
    result = None
    for line in text.split("\n"):
        line = ANSI_RE.sub("", line).strip()
        m = TRACE_RE.match(line)
        if m:
            op = int(m.group(1))
            traces[op] = dict(tensor=int(m.group(2)), n=int(m.group(3)), min=int(m.group(4)),
                              max=int(m.group(5)), sum=int(m.group(6)), fnv=int(m.group(7), 16))
            continue
        m = RAW_RE.match(line)
        if m:
            op, off, cnt, hx = int(m.group(1)), int(m.group(3)), int(m.group(4)), m.group(5)
            if len(hx) == 2 * cnt:
                chunks.setdefault(op, []).append((off, bytes.fromhex(hx)))
            continue
        m = RESULT_RE.search(line)
        if m:
            result = (int(m.group(2)), int(m.group(3)))
        for key in ("App version:", "ELF file SHA256:"):
            if key in line:
                banner[key] = line.split(key, 1)[1].strip()
    ops = {}
    for op, t in traces.items():
        buf = bytearray(t["n"])
        covered = bytearray(t["n"])
        conflict = False
        for off, data in chunks.get(op, []):
            end = off + len(data)
            if end > t["n"]:
                conflict = True
                continue
            seg = buf[off:end]
            if any(covered[off:end]) and any(c and s != d for c, s, d in zip(covered[off:end], seg, data)):
                conflict = True
            buf[off:end] = data
            for i in range(off, end):
                covered[i] = 1
        full = all(covered)
        vals = to_int8(buf)
        selfcheck = full and not conflict and (min(vals), max(vals), sum(vals), fnv1a(buf)) == (
            t["min"], t["max"], t["sum"], t["fnv"])
        ops[op] = dict(n=t["n"], tensor=t["tensor"], bytes=bytes(buf), complete=full,
                       conflict=conflict, selfcheck=selfcheck)
    return ops, result, banner


def main():
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    ref_map = json.loads(zipfile.ZipFile(ARM_ZIP).read("arm_qemu_rq1_20261027/compare_summary.json"))["esp_reference"]
    elf_sha = sha256(BUILD / "person_detection.elf") if (BUILD / "person_detection.elf").is_file() else ""
    bin_sha = sha256(BUILD / "person_detection.bin") if (BUILD / "person_detection.bin").is_file() else ""

    latest = {}
    for p in sorted(CAPTURES.glob("optimized_rq1_trace_image*_*.txt")):
        if p.name.endswith(".sha256.txt") or "_INCOMPLETE" in p.name:
            continue
        m = re.match(r"optimized_rq1_trace_image(\d+)_", p.name)
        if m:
            latest[int(m.group(1))] = p          # sorted names: last one per image wins

    rows, summary = [], []
    for image in sorted(latest):
        new_path = latest[image]
        ref = ref_map[str(image)]
        ref_path = PROJECT / ref["file"]
        ref_hash_ok = ref_path.is_file() and sha256(ref_path) == ref["sha256"]
        new_ops, new_out, banner = parse(new_path)
        ref_ops, _, _ = parse(ref_path)
        equal = 0
        first_div = None
        for op in range(EXPECTED_OPS):
            a, b = new_ops.get(op), ref_ops.get(op)
            if a is None or b is None:
                rows.append(dict(image=image, op=op, status="MISSING"))
                continue
            same = a["bytes"] == b["bytes"]
            diff_vals = sum(x != y for x, y in zip(a["bytes"], b["bytes"])) if a["n"] == b["n"] else a["n"]
            max_lsb = max((abs(x - y) for x, y in zip(to_int8(a["bytes"]), to_int8(b["bytes"]))), default=0)
            ok = same and a["selfcheck"] and b["selfcheck"]
            equal += ok
            if not same and first_div is None:
                first_div = op
            rows.append(dict(image=image, op=op, tensor=a["tensor"], n=a["n"],
                             board_complete=a["complete"], board_selfcheck=a["selfcheck"],
                             r1_complete=b["complete"], r1_selfcheck=b["selfcheck"],
                             bytes_equal=same, values_differing=diff_vals, max_lsb=max_lsb,
                             status="EQUAL" if ok else "DIFFERENT"))
        summary.append(dict(image=image, board_log=new_path.name, board_log_sha256=sha256(new_path),
                            r1_log=ref["file"], r1_log_sha256_matches_record=ref_hash_ok,
                            ops_equal=f"{equal}/{EXPECTED_OPS}", first_divergent_op=first_div,
                            board_output=new_out, r1_output=tuple(ref["out"]),
                            output_equal=new_out == tuple(ref["out"]),
                            app_version=banner.get("App version:", ""),
                            elf_banner=banner.get("ELF file SHA256:", "")))

    out_csv = HERE / f"v010_trace_vs_r1_per_operator_{run_id}.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        fields = ["image", "op", "tensor", "n", "board_complete", "board_selfcheck", "r1_complete",
                  "r1_selfcheck", "bytes_equal", "values_differing", "max_lsb", "status"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    total_equal = sum(int(s["ops_equal"].split("/")[0]) for s in summary)
    total = EXPECTED_OPS * len(summary)
    md = ["# v0.1.0 optimized ESP-NN board traces vs ESP32 R1 reference", "",
          f"- Run ID: {run_id}",
          f"- Board build: build_rq1_trace_opt_20261029 (commit 15dd18a, optimized ESP-NN, trace on)",
          f"- Board BIN SHA-256: {bin_sha.upper()}",
          f"- Board ELF SHA-256: {elf_sha.upper()}",
          "- Reference: ESP32 R1 (TFLM reference kernels) full-dump logs of 25 October, mapped by compare_summary.json",
          f"- Result: {total_equal}/{total} operator outputs byte-identical over {len(summary)} images", "",
          "| Image | Board log | R1 log (hash matches record) | Ops equal | First divergent op | Board output | R1 output | App version | ELF banner |",
          "|---|---|---|---|---|---|---|---|---|"]
    for s in summary:
        md.append(f"| {s['image']} | {s['board_log']} | {s['r1_log']} ({s['r1_log_sha256_matches_record']}) | "
                  f"{s['ops_equal']} | {s['first_divergent_op']} | {s['board_output']} | {s['r1_output']} | "
                  f"{s['app_version']} | {s['elf_banner']} |")
    md += ["", "Each tensor was rebuilt from its raw chunks and checked against the element count, min, max,",
           "sum and FNV-1a hash printed by the board in the same log, for both the board log and the R1 log.",
           "Equality here is for these images and this build; it is not a proof for all inputs.", ""]
    out_md = HERE / f"v010_trace_vs_r1_summary_{run_id}.md"
    out_md.write_text("\n".join(md), encoding="utf-8")
    for p in (out_csv, out_md):
        Path(str(p) + ".sha256.txt").write_text(f"{sha256(p).upper()}  {p.name}\n", encoding="ascii")
    print("\n".join(md))
    return 0 if total_equal == total else 1


if __name__ == "__main__":
    sys.exit(main())
