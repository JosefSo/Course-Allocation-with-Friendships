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

## Mathematical model and formulas
This section matches the exact computation implemented in `HBS/` and breaks it into small pieces.

### Sets and inputs
- Students: `S`, courses: `C`.
- For each student `s` and course `c`, Table 1 provides `Score(s,c)` and `PositionA(s,c)`.
- For each directed pair `(s, f)` and course `c`, Table 2 provides `PositionB(s,f,c)` (s's friend rank for f in c).
- Per-student social weight `lambda_s` comes from Table 3 (default 0.5 if missing).
- Course capacity is uniform: `cap(c) = cap_default` for all `c`.

### Rank-to-utility mapping
We convert a 1-based rank position into a utility in [0, 1]:

$$
posU(p, K) =
\begin{cases}
0, & p \text{ is missing} \\
1, & K \le 1 \land p = 1 \\
0, & K \le 1 \land p \ne 1 \\
\frac{K - p}{K - 1}, & K > 1
\end{cases}
$$

In code, missing `PositionA` yields `Base = 0`, and missing `Score`/`PositionA` are treated as worst-case for tie-breaking.

### Utility components (per student and course)
Base utility from Table 1:

$$
Base(s, c) = posU(PositionA(s,c), |C|)
$$

Directed friend preference from Table 2 (ranked among friends):

$$
Pref(s, f, c) = posU(PositionB(s,f,c), K_{friend})
$$

Reactive friend bonus (only already allocated friends count):

$$
FriendBonus(s, c) = \sum_{f \in F(s)} \mathbb{1}[c \in A_f] \cdot Pref(s,f,c)
$$

Total per-pick utility:

$$
U(s, c) = Base(s,c) + \lambda_s \cdot FriendBonus(s,c)
$$

### Feasible choices and pick rule
At a pick, the feasible set is:

$$
C_s = \{ c \in C \mid cap\_left(c) > 0 \ \land \ c \notin A_s \}
$$

The chosen course is the lexicographic maximum of a tie-break tuple:

$$
c^\* = \arg\max_{c \in C_s}
\Big(
\text{round}(U(s,c), 9),
\ -PositionA(s,c),
\ Score(s,c),
\ rnd(s,c),
\ CourseID(c)
\Big)
$$

Where `rnd(s,c)` is a seeded random number used only for remaining ties, and `CourseID` is a stable final tie-breaker. This is equivalent to:
1) maximize utility (bucketed to 1e-9),
2) then prefer smaller `PositionA`,
3) then higher `Score`,
4) then seeded random,
5) then stable `CourseID`.

### Draft order (snake)
Let `pi` be a random permutation of students (seeded). For round `r`:
- if `r` is odd: order is `pi`
- if `r` is even: order is `reverse(pi)`

### Post-phase objective (swap or add-drop)
After the draft, the algorithm can improve the allocation for `post_iters` iterations.

Per-student welfare (final allocation):

$$
W_s = \sum_{c \in A_s}
\left[
Base(s,c) + \lambda_s \cdot \sum_{f \in F(s)} \mathbb{1}[c \in A_f] \cdot Pref(s,f,c)
\right]
$$

Global welfare:

$$
W = \sum_{s \in S} W_s
$$

Swap mode:
- for each iteration, find the feasible swap with the best positive `DeltaW = W_{after} - W_{before}`,
- apply it if `DeltaW > 0`, otherwise no-op.

Add-drop mode (HBS-style):
- for each student, build a candidate set: current allocation plus any course with remaining capacity,
- score candidates by `U(s,c)` and keep the top `b` courses (max courses per student).

### Normalization for fairness
Let `b` be max courses per student.

Per-student sums on the final allocation:

$$
BaseSum_s = \sum_{c \in A_s} Base(s,c)
$$

$$
FriendSum_s = \sum_{c \in A_s} \sum_{f \in F(s)} \mathbb{1}[c \in A_f] \cdot Pref(s,f,c)
$$

$$
Total_s = BaseSum_s + \lambda_s \cdot FriendSum_s
$$

Upper bounds for normalization:

$$
MaxBase_s = \sum_{c \in Top_b} Base(s,c)
$$

$$
MaxTotalUpper_s = \sum_{c \in Top_b} \Big(Base(s,c) + \lambda_s \cdot \sum_{f \in F(s)} Pref(s,f,c)\Big)
$$

Where `Top_b` selects the `b` courses with largest values in the respective expression (ignoring capacity and reactivity for the upper bound).

Normalized utilities used for inequality metrics:

$$
BaseNorm_s =
\begin{cases}
\frac{BaseSum_s}{MaxBase_s}, & MaxBase_s > 0 \\
0, & \text{otherwise}
\end{cases}
$$

$$
TotalNorm_s =
\begin{cases}
\frac{Total_s}{MaxTotalUpper_s}, & MaxTotalUpper_s > 0 \\
0, & \text{otherwise}
\end{cases}
$$

### Inequality and summary metrics (including Gini)
Let `x_i` be a list of non-negative values (the code clamps negatives to 0), sorted in non-decreasing order. Let `n = |x|`.

Total utility:

$$
TotalUtility = \sum_{i=1}^{n} x_i
$$

Gini index (used for `TotalNorm` and `BaseNorm`):

$$
Gini(x) =
\begin{cases}
0, & \sum_i x_i = 0 \\
\frac{\sum_{i=1}^{n} (2i - n - 1) x_i}{n \cdot \sum_{i=1}^{n} x_i}, & \text{otherwise}
\end{cases}
$$

Jain index:

$$
Jain(x) =
\begin{cases}
0, & \sum_i x_i = 0 \\
\frac{(\sum_i x_i)^2}{n \cdot \sum_i x_i^2}, & \text{otherwise}
\end{cases}
$$

Theil index:

$$
Theil(x) =
\frac{1}{n} \sum_{i: x_i > 0} \frac{x_i}{\mu} \cdot \log\left(\frac{x_i}{\mu}\right),
\quad \mu = \frac{1}{n}\sum_i x_i
$$

Atkinson index (epsilon = 0.5 in this project):

$$
Atkinson(x; \epsilon) =
1 - \frac{\left(\frac{1}{n}\sum_i x_i^{1-\epsilon}\right)^{\frac{1}{1-\epsilon}}}{\mu}
$$

### Additional computed statistics
These are also reported in `metrics_extended.csv`:
- Average courses per student: `avg_courses = (1/|S|) * sum_s |A_s|`.
- Full allocation rate: `share(|A_s| >= b)`.
- Unfilled seats: `sum_c cap_left(c)`.
- Course fill mean: `mean_c ((cap_default - cap_left(c)) / cap_default)`.
- Position stats over allocated courses with Table 1 rows:
  `avg_position`, `median_position`, `share_top1`, `share_top3`.
- Friend overlap stats:
  `avg_friend_overlaps_per_student` and share of students with any overlap.
- Utility percentiles over `Total_s` using the index rule:
  `idx = round((n - 1) * p)`, for `p` in {0.10, 0.25, 0.50, 0.75, 0.90}.

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
