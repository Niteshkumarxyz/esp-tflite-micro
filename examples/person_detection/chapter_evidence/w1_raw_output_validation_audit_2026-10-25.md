# W1 Raw-Output Validation Audit

Audit date: 2026-10-25

## Original validation CSV

File: examples/person_detection/w1_raw_output_validation_2026-10-20.csv

SHA-256:
8E17466FD47840712D8AB67ED3024EA5599DF66B1593AF8EF6D4F685BD8004B9

Total data rows: 21

Round coverage:
- Round 1: 10 rows; images 0-9
- Round 2: 10 rows; images 0-9
- Round 3: 1 row; image 0 only

Assessment: The available CSV does not establish a complete
30-record, three-round validation. Nine expected Round 3 records
are absent from the available file.

## Duplicate-copy check

The copy in Downloads\w1_source_evidence_2026-10-25 has the same
SHA-256 as the repository CSV. It is an identical copy, not an
independent source and does not supply additional records.

## Separate validation files

Reference-kernel validation:
- Rows: 10
- Round 1 images: 0-9
- SHA-256: 67E91065DA4EB9CACDE6AC2BD8932B24D03007E818644CB0D056567D21C761BA

ESP-NN retest validation:
- Rows: 10
- Round 1 images: 0-9
- SHA-256: 196AEE3334D9ED19679DF58E84951DF9CCAE4F1AEAEF54BEC47326F1062EA03D

These are separately named validation datasets and must not be
merged into the original CSV to fill its missing Round 3 records.

## Recovery status

The searches performed so far did not identify a source log that
recovers the nine missing Round 3 records. This does not prove that
no such log exists elsewhere.

## Reporting decision

- Report the original validation as 21 available records.
- Explicitly identify Round 3 as incomplete.
- Do not claim 30 successful records for this validation.
- Do not fabricate or infer missing measurements.
- Keep later repeatability tests and benchmarks as separate evidence.
