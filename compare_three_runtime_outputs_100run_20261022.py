import csv
from pathlib import Path

BASE = Path("evidence/cycle_count")
OUT_DETAIL = BASE / "three_runtime_output_pairwise_100run_detail_20261022.csv"
OUT_SUMMARY = BASE / "three_runtime_output_pairwise_100run_summary_20261022.csv"

CONFIGS = {
    "R1_reference": "r1_cycle_benchmark_100_verified_samples_20261022.csv",
    "R2A_ANSI_C": "r2a_cycle_benchmark_100_retry1_samples_20261022.csv",
    "R2_ESP_NN_optimized": "cycle_benchmark_100_retry2_samples_20261022.csv",
}

if OUT_DETAIL.exists() or OUT_SUMMARY.exists():
    raise SystemExit("Output CSV already exists. Refusing to overwrite.")

def read_rows(label, filename):
    path = BASE / filename
    if not path.exists():
        raise SystemExit(f"{label}: missing CSV: {path}")

    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    required = {"run", "image", "raw_person", "raw_no_person", "ok"}
    if len(rows) != 100 or not rows or not required.issubset(rows[0]):
        raise SystemExit(f"{label}: unexpected CSV rows or columns")

    if [int(r["run"]) for r in rows] != list(range(1, 101)):
        raise SystemExit(f"{label}: run IDs missing or duplicated")

    return rows

all_rows = {name: read_rows(name, file) for name, file in CONFIGS.items()}

pairs = [
    ("R1_reference", "R2A_ANSI_C"),
    ("R2A_ANSI_C", "R2_ESP_NN_optimized"),
    ("R1_reference", "R2_ESP_NN_optimized"),
]

details, summaries = [], []

for left, right in pairs:
    matched = 0
    image_status = {}

    for a, b in zip(all_rows[left], all_rows[right]):
        differences = []

        for field in ("run", "image", "raw_person", "raw_no_person", "ok"):
            if int(a[field]) != int(b[field]):
                differences.append(field)

        status = "MATCH" if not differences else "MISMATCH"
        matched += status == "MATCH"

        image = int(a["image"])
        image_status.setdefault(image, []).append(status)

        details.append({
            "Pair": f"{left} vs {right}",
            "Run": int(a["run"]),
            "Left_Image": int(a["image"]),
            "Right_Image": int(b["image"]),
            "Left_Person": int(a["raw_person"]),
            "Right_Person": int(b["raw_person"]),
            "Left_NoPerson": int(a["raw_no_person"]),
            "Right_NoPerson": int(b["raw_no_person"]),
            "Left_OK": int(a["ok"]),
            "Right_OK": int(b["ok"]),
            "Mismatch_Fields": ";".join(differences),
            "Status": status,
        })

    image_matches = sum(
        all(status == "MATCH" for status in statuses)
        for statuses in image_status.values()
    )

    summaries.append({
        "Pair": f"{left} vs {right}",
        "Runs_Compared": 100,
        "Matched_Rows": matched,
        "Mismatched_Rows": 100 - matched,
        "Rows_Bit_Exact_Pct": matched,
        "Images_Represented": len(image_status),
        "Images_Matching_All_Repeats": image_matches,
        "Unique_Images_Matching_Pct": (
            round(100 * image_matches / len(image_status), 2)
            if image_status else 0
        ),
        "Result": "MATCH" if matched == 100 else "DIFFERENCES_FOUND",
        "Scope": "10 bundled images cycled; not unique-image validation",
    })

with OUT_DETAIL.open("x", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(details[0]))
    writer.writeheader()
    writer.writerows(details)

with OUT_SUMMARY.open("x", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(summaries[0]))
    writer.writeheader()
    writer.writerows(summaries)

print("\nPAIRWISE OUTPUT COMPARISON")
for item in summaries:
    print(
        f'{item["Pair"]}: {item["Matched_Rows"]}/100 rows matched; '
        f'{item["Images_Matching_All_Repeats"]}/'
        f'{item["Images_Represented"]} image IDs match across repeats; '
        f'{item["Result"]}'
    )

print("\nDetail CSV:", OUT_DETAIL)
print("Summary CSV:", OUT_SUMMARY)