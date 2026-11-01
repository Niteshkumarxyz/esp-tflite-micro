import csv
import hashlib
import re
from pathlib import Path

EVIDENCE = Path(
    r"C:\Users\nk947\Downloads\robot-runtime-research\esp-tflite-micro\examples\person_detection\chapter_evidence"
)
DATE = "2026-10-27"

OPTIMIZED_FILES = {
    1: "optimized_r2_tensor_trace_image_1_2026-10-27.txt",
    2: "optimized_r2_tensor_trace_image_2_2026-10-27.txt",
    3: "optimized_r2_tensor_trace_image_3_retry_2026-10-27.txt",
    4: "optimized_r2_tensor_trace_image_4_retry_2026-10-27.txt",
    5: "optimized_r2_tensor_trace_image_5_retry2_2026-10-27.txt",
    6: "optimized_r2_tensor_trace_image_6_resetverified_2026-10-27.txt",
    7: "optimized_r2_tensor_trace_image_7_resetverified_v2_2026-10-27.txt",
    8: "optimized_r2_tensor_trace_image_8_resetverified_retry_2026-10-27.txt",
    9: "optimized_r2_tensor_trace_image_9_freshboot_retry2_2026-10-27.txt",
    10: "optimized_r2_tensor_trace_image_10_verified_2026-10-27.txt",
}

def locate(filename):
    direct = EVIDENCE / filename
    if direct.is_file():
        return direct

    matches = list(EVIDENCE.rglob(filename))
    return matches[0] if len(matches) == 1 else None

def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def parse_trace(path):
    content = path.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()

    summaries = {}
    raw_chunks = {}
    malformed_raw = 0

    for line in lines:
        if line.startswith("RQ1_TRACE,"):
            fields = dict(
                part.split("=", 1)
                for part in line.split(",")[1:]
                if "=" in part
            )
            if all(k in fields for k in ("op", "tensor", "n", "min",
                                         "max", "sum", "fnv1a")):
                key = (int(fields["op"]), int(fields["tensor"]))
                summaries[key] = (
                    int(fields["n"]), int(fields["min"]),
                    int(fields["max"]), int(fields["sum"]),
                    fields["fnv1a"].lower()
                )

        elif line.startswith("RQ1_RAW,"):
            fields = dict(
                part.split("=", 1)
                for part in line.split(",")[1:]
                if "=" in part
            )
            try:
                key = (
                    int(fields["op"]), int(fields["tensor"]),
                    int(fields["offset"]), int(fields["count"])
                )
                raw_chunks[key] = fields["hex"].lower()
            except (KeyError, ValueError):
                malformed_raw += 1

    result = next(
        (line for line in lines if line.startswith("IMAGE_RESULT,image=")),
        "MISSING"
    )

    return {
        "path": path,
        "sha256": file_hash(path),
        "bytes": path.stat().st_size,
        "result": result,
        "summaries": summaries,
        "raw": raw_chunks,
        "raw_line_count": sum(line.startswith("RQ1_RAW,") for line in lines),
        "trace_line_count": sum(line.startswith("RQ1_TRACE,") for line in lines),
        "malformed_raw": malformed_raw,
    }

def compare(a, b):
    if a is None or b is None:
        return {
            "status": "MISSING_FILE",
            "summary_diffs": "",
            "raw_chunk_diffs": "",
            "first_raw_diff_op": "",
        }

    sa, sb = a["summaries"], b["summaries"]
    ra, rb = a["raw"], b["raw"]

    summary_keys = set(sa) | set(sb)
    raw_keys = set(ra) | set(rb)

    summary_diff_keys = [
        key for key in summary_keys if sa.get(key) != sb.get(key)
    ]
    raw_diff_keys = [
        key for key in raw_keys if ra.get(key) != rb.get(key)
    ]

    comparable = (
        bool(sa) and bool(sb)
        and bool(ra) and bool(rb)
        and a["malformed_raw"] == 0
        and b["malformed_raw"] == 0
    )

    if not comparable:
        status = "INCOMPLETE_TRACE"
    elif not summary_diff_keys and not raw_diff_keys:
        status = "BYTE_EQUIVALENT"
    else:
        status = "DIFFERENCES_FOUND"

    differing_ops = sorted({key[0] for key in raw_diff_keys})

    return {
        "status": status,
        "summary_diffs": len(summary_diff_keys),
        "raw_chunk_diffs": len(raw_diff_keys),
        "first_raw_diff_op": differing_ops[0] if differing_ops else "",
    }

def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    audit_rows = []
    comparison_rows = []
    parsed = {}

    for image in range(1, 11):
        names = {
            "R1": f"r1_reference_trace_image{image}_{DATE}.txt",
            "R2A": (
                f"r2a_ansi_c_trace_image4_retry1_{DATE}.txt"
                if image == 4
                else f"r2a_ansi_c_trace_image{image}_{DATE}.txt"
            ),
            "R2_OPT": OPTIMIZED_FILES[image],
        }

        for build, filename in names.items():
            path = locate(filename)
            key = (image, build)
            parsed[key] = parse_trace(path) if path else None
            record = parsed[key]

            audit_rows.append({
                "image": image,
                "build": build,
                "file": str(path) if path else filename,
                "file_found": path is not None,
                "bytes": record["bytes"] if record else "",
                "sha256": record["sha256"] if record else "",
                "result": record["result"] if record else "",
                "trace_records": record["trace_line_count"] if record else "",
                "raw_records": record["raw_line_count"] if record else "",
                "parsed_raw_chunks": len(record["raw"]) if record else "",
                "parsed_summaries": len(record["summaries"]) if record else "",
                "malformed_raw": record["malformed_raw"] if record else "",
            })

        pairs = (
            ("R1", "R2A"),
            ("R1", "R2_OPT"),
            ("R2A", "R2_OPT"),
        )

        for left, right in pairs:
            outcome = compare(parsed[(image, left)], parsed[(image, right)])
            comparison_rows.append({
                "image": image,
                "comparison": f"{left}_vs_{right}",
                **outcome,
            })

    audit_path = EVIDENCE / "optimized_r2_10_image_trace_inventory_2026-10-27.csv"
    compare_path = EVIDENCE / "r1_r2a_optimized_r2_tensor_comparison_2026-10-27.csv"
    report_path = EVIDENCE / "r1_r2a_optimized_r2_tensor_audit_2026-10-27.md"

    for destination, rows in (
        (audit_path, audit_rows),
        (compare_path, comparison_rows),
    ):
        with destination.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    with report_path.open("w", encoding="utf-8") as f:
        f.write("# R1 / R2A / Optimized R2 Tensor Audit\n\n")
        f.write(f"Audit date: {DATE}\n\n")
        f.write("This report compares available saved traces. "
                "Missing or incomplete files are not treated as equivalent.\n\n")
        f.write("| Image | Comparison | Status | Summary differences | Raw chunk differences | First differing op |\n")
        f.write("|---:|---|---|---:|---:|---:|\n")
        for row in comparison_rows:
            f.write(
                f"| {row['image']} | {row['comparison']} | {row['status']} "
                f"| {row['summary_diffs']} | {row['raw_chunk_diffs']} "
                f"| {row['first_raw_diff_op']} |\n"
            )

        statuses = {}
        for row in comparison_rows:
            key = row["comparison"]
            statuses.setdefault(key, {}).setdefault(row["status"], 0)
            statuses[key][row["status"]] += 1

        f.write("\n## Status totals\n\n")
        for comparison, counts in statuses.items():
            f.write(f"- {comparison}: {counts}\n")

        f.write("\n## File SHA-256\n\n")
        for image in range(1, 11):
            for build in ("R1", "R2A", "R2_OPT"):
                item = parsed[(image, build)]
                f.write(
                    f"- Image {image}, {build}: "
                    f"{item['sha256'] if item else 'MISSING FILE'}\n"
                )

    print("=== TRACE INVENTORY ===")
    print(f"Inventory CSV: {audit_path}")
    print(f"Comparison CSV: {compare_path}")
    print(f"Markdown report: {report_path}")

    print("\n=== COMPARISON STATUS TOTALS ===")
    for comparison in ("R1_vs_R2A", "R1_vs_R2_OPT", "R2A_vs_R2_OPT"):
        rows = [r for r in comparison_rows if r["comparison"] == comparison]
        counts = {}
        for row in rows:
            counts[row["status"]] = counts.get(row["status"], 0) + 1
        print(f"{comparison}: {counts}")

    missing = [r for r in audit_rows if not r["file_found"]]
    incomplete = [
        r for r in audit_rows
        if r["file_found"] and (
            r["raw_records"] == 0
            or r["malformed_raw"] != 0
            or r["parsed_summaries"] == 0
        )
    ]

    print(f"\nMissing source trace files: {len(missing)}")
    print(f"Incomplete trace files: {len(incomplete)}")

    if missing:
        for row in missing:
            print(f"MISSING: image={row['image']} build={row['build']} file={row['file']}")

    if incomplete:
        for row in incomplete:
            print(f"INCOMPLETE: image={row['image']} build={row['build']} file={row['file']}")

if __name__ == "__main__":
    main()