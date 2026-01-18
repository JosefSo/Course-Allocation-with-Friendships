# HBS Social Snake Draft (Reactive Friends)

This repository contains the code and experiments for my master's thesis project on course allocation with social preferences (friendships). The core implementation lives in `HBS/`, with a CLI wrapper at `hbs_social.py`.

## What the project does
- Simulates an HBS-style snake draft course allocation.
- Adds a reactive friend bonus to the utility function.
- Supports optional post-draft improvement (swap or add-drop).
- Exports audit logs and fairness/inequality metrics.

## Repository layout
- `hbs_social.py` - CLI entrypoint.
- `HBS/` - core engine, API, metrics, and IO.
- `generate/` - synthetic data generator for CSV inputs.
- `tests/` - unit tests.

## Input data
The allocator expects three CSV tables (Table 3 is optional):

Table 1: individual course preferences
- columns: `StudentID, CourseID, Score, Position`
- `Position` is a 1-based rank (1 = best) and defines base utility.
- `Score` is used only for deterministic tie-breaking.

Table 2: directed friend preferences per course
- columns: `StudentID_A, StudentID_B, CourseID, Position`
- represents "A prefers to be with B in course".
- `Position` is a 1-based rank among A's friends for that course (top-k).

Table 3: per-student social weight (optional)
- columns: `StudentID, LambdaFriend`
- `LambdaFriend` must be in [0, 1]. If omitted, all students default to 0.5.

Note: `tables/` is treated as local data and is not tracked on GitHub in this project. Use the generator below to create sample CSVs.

## Utility model (as implemented)
Let `posU(p, K) = (K - p) / (K - 1)` for `K > 1`, and 0 for missing.

- Base utility: `Base(s, c) = posU(PositionA(s,c), |C|)`
- Friend preference: `Pref(s, f, c) = posU(PositionB(s,f,c), K_friend)`
  where `K_friend` is the maximum rank observed in Table 2.
- Reactive friend bonus:
  `FriendBonus(s, c) = sum_{f in Friends(s)} 1[c in A_f] * Pref(s,f,c)`
- Total utility at pick time:
  `U(s, c) = Base(s,c) + Lambda_s * FriendBonus(s,c)`

The friend bonus is reactive: it only counts courses already chosen by friends.

## Draft and post-draft logic
1. Seeded random order of students.
2. Snake draft for `draft_rounds` rounds (odd rounds forward, even rounds reverse).
3. Each pick chooses the course with highest utility using deterministic tie-breaks:
   1) max utility (bucketed to 1e-9)
   2) best Position from Table 1 (smaller is better)
   3) highest Score from Table 1
   4) seeded random tie
   5) stable CourseID
4. Optional post-phase for `post_iters` iterations:
   - `swap`: best welfare-improving swap between two students per iteration.
   - `add-drop`: HBS-style pass using only courses with spare capacity.

## Outputs
- `allocation.csv` - draft picks only.
- `post_allocation.csv` - post-phase events (swap/add-drop).
- `summary.csv` - total utility and normalized Gini metrics.
- `metrics_extended.csv` - extended fairness and distribution metrics (Jain, Theil, Atkinson, percentiles, and more).

## Quick start
Requirements: Python 3.10+ (no external dependencies).

Generate sample data:

```bash
python generate/generate_tables.py --students 200 --courses 8 --seed 42
```

Run the allocator:

```bash
python hbs_social.py \
  --csv-a tables/table1_individual.csv \
  --csv-b tables/table2_pair.csv \
  --csv-lambda tables/table3_lambda.csv \
  --cap-default 80 \
  --b 3 \
  --draft-rounds 3 \
  --post-iters 2 \
  --improve-mode add-drop \
  --seed 42 \
  --out-allocation allocation.csv \
  --out-adddrop post_allocation.csv \
  --out-summary summary.csv \
  --out-metrics-extended metrics_extended.csv
```

Useful optional flags: `--progress`, `--sanity-checks`, `--delta-check-every`, `--log-level`.

Run tests:

```bash
python tests/run_all_tests.py
```
