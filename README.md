# HBS Social: Course Allocation with Friendships

This repository contains a master's thesis implementation of course allocation with
social preferences. The current `new-ui-update` branch combines the full history and
experiment infrastructure from `post-iters-improvement` with the newer allocation
engine options and browser interface.

## Features

- HBS-style sequential course allocation with directed, course-specific friendships.
- Four sequential picking sequences plus a frozen-ranking `simultaneous-priority`
  architecture.
- `personal` and social-welfare-aware (`social`) draft pick rules.
- Six post-processing variants: three move types × two objectives.
- Local browser UI with live visualization, persistent SQLite history, and parallel
  comparison of all six post-processing modes.
- CLI and Python API using the same allocation implementation.
- Synthetic CSV generation, reproducible seeds, batch experiments, SQLite results,
  CSV reports, fairness metrics, and an optional ILP benchmark.

## Repository layout

- `hbs_social.py` — allocator CLI.
- `hbs_web.py` and `webui/index.html` — primary local web application.
- `hbs_experiments.py` — batch/sweep experiment CLI.
- `HBS/hbs_engine.py` — allocation and post-processing engine.
- `HBS/hbs_api.py` — public Python API and mode normalization.
- `HBS/hbs_web.py` — SQLite history, parallel comparison, and experiment services
  used by the primary web application.
- `HBS/hbs_experiments.py` — experiment persistence and aggregation.
- `generate/generate_tables.py` — synthetic input generator.
- `experiments/ilp_benchmark.py` — optional PuLP/CBC optimum benchmark.
- `tests/` — unit and integration tests.

Generated `tables/`, `results/`, `outputs/`, caches, and root-level result CSV files
are intentionally excluded from Git.

## Quick start: web UI

Requirements: Python 3.10+ and a modern browser. The main allocator and web server
use only the Python standard library.

```bash
python3 hbs_web.py
```

The server binds to `127.0.0.1` and opens `http://127.0.0.1:8765`.

```bash
python3 hbs_web.py --port 9000
python3 hbs_web.py --no-browser
```

The web UI can:

1. Generate or select the three input CSV tables.
2. Configure capacity, draft rounds, picking sequence, pick rule, post mode, and seed.
3. Run an allocation and visualize draft/post-processing events.
4. Inspect the final allocation and fairness metrics.
5. Retain run history in `results/hbs_social_web_history.sqlite3`.
6. Compare all six post-processing modes across a batch of seeds using up to six
   parallel workers.

## Input data

### Table 1: individual course preferences

Required columns:

```text
StudentID,CourseID,Score,Position
```

`Position` is a positive 1-based course rank. Lower is better. When candidate utility
is tied, `Score` is checked before `Position`.

### Table 2: directed friend preferences

Required columns:

```text
StudentID_A,StudentID_B,CourseID,Position
```

Optional column:

```text
Score
```

A row means that student A wants to attend the specified course with student B.
Self-friendship, duplicate rows/positions, unknown students, and unknown courses are
rejected.

### Table 3: per-student social weight (optional)

```text
StudentID,LambdaFriend
```

`LambdaFriend` must be in `[0, 1]`. Students without an explicit value use `0.5`.

## Utility model

For `K` courses, Table 1 rank is converted to base utility:

```text
Base(s,c) = (K - Position(s,c)) / (K - 1)     when K > 1
```

Table 2 scores are min-max normalized to `[0,1]`. If Score is missing, friend rank is
used:

```text
FriendWeight(s,f,c) = (K_friend + 1 - Position(s,f,c)) / K_friend
```

Only friends already allocated to the candidate course contribute to reactive friend
utility:

```text
FriendBonus(s,c) = Σ_f 1[c in Allocation(f)] * FriendWeight(s,f,c)
```

For each student, friend utility is normalized by that student's maximum available
friend-weight sum on any course. The personal utility of a course is:

```text
U(s,c) = (1 - lambda_s) * Base(s,c)
       + lambda_s * FriendBonusNorm(s,c)
```

## Draft configuration

### Picking sequences

- `snake`: `1..n`, `n..1`, `1..n`, ...
- `round-robin`: `1..n` in every round.
- `reverse-repeat`: `1..n` in round one and `n..1` in every later round.
- `last-first-static`: `1..n` in round one and `n,1,..,n-1` later.

The legacy names `n-first` and `last-first` remain aliases for `reverse-repeat` and
`last-first-static` respectively.

Set `--initial-method simultaneous-priority` to freeze every student's complete course
ranking at the start of a round and resolve conflicts with one seeded priority fixed for
the run. The default `sequential` method continues to evaluate reactive utility live.

The initial student permutation and all remaining random tie-breaks are seeded.

### Pick rules

```text
personal:    PickValue(s,c) = U(s,c)
utilitarian: PickValue(s,c) = U(s,c) + SocialGain(s,c)
```

`SocialGain` is the marginal friendship utility created for students already enrolled
in the course who list the picking student as a friend.
The former name `social` is a deprecated alias for `utilitarian`.

Candidate values are rounded to nine decimal places for near-tie bucketing. Ties are
resolved by:

1. higher Table 1 `Score`;
2. lower Table 1 `Position`;
3. seeded random value;
4. stable `CourseID`.

## Post-processing matrix

Post-processing is configured by `move_type` and `objective_scope`:

| Objective | `swap` | `drop-add` | `hybrid` |
| --- | --- | --- | --- |
| `global` | `swap-global` | `drop-add-global` | `hybrid-global` |
| `personal` | `swap-personal` | `drop-add-personal` | `hybrid-personal` |

- Global variants accept only strict increases in total system welfare.
- Personal variants accept strict utility increases for the current student and may
  trade off global welfare.
- `swap` exchanges courses between students.
- `drop-add` rebuilds a student's best feasible bundle using spare capacity.
- `hybrid` considers both spare-capacity replacements and swaps with current holders.
- Hybrid stops early after a complete pass with no accepted move.

Short aliases remain compatible:

- `swap` → `swap-global`
- `add-drop` / `drop-add` → `drop-add-global`
- `hybrid` → `hybrid-global`

## Generate sample data

```bash
python3 generate/generate_tables.py \
  --students 200 \
  --courses 8 \
  --seed 11 \
  --popularity-strength 0.7 \
  --lambda-default 0.3
```

The default filenames include dimensions and lambda configuration. Use `--out1`,
`--out2`, and `--out3` to choose explicit paths. Parent directories are created
automatically.

## Run from CLI

```bash
python3 hbs_social.py \
  --csv-a 'tables/table1_200×8.csv' \
  --csv-b 'tables/table2_200×8.csv' \
  --csv-lambda 'tables/table3_200×8_lambda-0.3.csv' \
  --cap-default 80 \
  --b 3 \
  --draft-rounds 3 \
  --sequence n-first \
  --pick-rule social \
  --post-iters 10 \
  --move-type hybrid \
  --objective-scope global \
  --seed 11 \
  --out-allocation results/allocation.csv \
  --out-adddrop results/post_allocation.csv \
  --out-summary results/summary.csv \
  --out-metrics-extended results/metrics_extended.csv
```

Equivalent combined mode:

```bash
python3 hbs_social.py ... --improve-mode hybrid-global
```

Run `python3 hbs_social.py --help` for the complete option list.

## Outputs and metrics

- `allocation.csv` — draft picks.
- `post_allocation.csv` — accepted post-processing moves and no-op/early-stop rows.
- `summary.csv` — total utility and normalized Gini metrics.
- `metrics_extended.csv` — base/friend/combined welfare, fill and rank statistics,
  Gini/Jain/Theil/Atkinson, egalitarian welfare, canonical Nash welfare with an explicit
  zero-utility share, zero-safe Nash, friend overlap rate, and ex-post envy/EF1 metrics.

EF1 is reported under three preregistered interpretations: `substitution` (primary),
`swap`, and classical `base-only`. New metric names include both the definition and the
utility representation. Legacy `ef1_violation_share_*` keys remain available for the UI
and map to substitution-based student violation shares.

The engine also reports unconstrained per-student upper bounds. These are diagnostic
normalization bounds, not a capacity-feasible optimum.

## Batch experiments and SQLite

The experiment runner evaluates scenarios over seeds, post-iteration grids, and all
six modes. It persists individual runs, post events, stability checks, aggregate CSVs,
and a Markdown report in SQLite-backed experiment directories.

```bash
python3 hbs_experiments.py \
  --seed-start 11 \
  --seed-count 10 \
  --post-grid 0,1,5,10,20 \
  --modes swap-global,swap-personal,drop-add-global,drop-add-personal,hybrid-global,hybrid-personal \
  --progress
```

Run `python3 hbs_experiments.py --help` for scenario and resume options.

## ILP benchmark

The optional benchmark uses PuLP/CBC:

```bash
python3 -m pip install pulp
python3 experiments/ilp_benchmark.py \
  --csv-a 'tables/table1_200×8.csv' \
  --csv-b 'tables/table2_200×8.csv' \
  --csv-lambda 'tables/table3_200×8_lambda-0.3.csv' \
  --cap-default 80 \
  --b 3 \
  --objective utilitarian \
  --time-limit 300 \
  --out-csv results/optimal_allocation.csv
```

Use `--objective egalitarian` for max-min welfare. An allocation is written only when
CBC reports an optimal solution; a timeout is not presented as a proven optimum.

## Tests

```bash
python3 tests/run_all_tests.py
```

The suite covers utility and normalization, input validation, reproducibility,
tie-breaking, all six post modes, global/personal objectives, SQLite history,
parallel comparisons, experiments, and the combined new UI options.
