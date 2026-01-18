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

### Rank-to-utility mapping (Table 1)
Function type: affine Min-Max linear scaling of rank to [0, 1].

We convert a 1-based course rank into a utility in [0, 1]:

$$
posU(p, K) =
\begin{cases}
0, & p \text{ is missing} \\
1, & K \le 1 \land p = 1 \\
0, & K \le 1 \land p \ne 1 \\
\frac{K - p}{K - 1}, & K > 1
\end{cases}
$$

Example: if K=4, then posU(1,4)=1, posU(2,4)=2/3, posU(4,4)=0; missing p gives 0.

In code, missing `PositionA` yields `Base = 0`, and missing `Score`/`PositionA` are treated as worst-case for tie-breaking.

### Friend-rank mapping (Table 2, linear without zero)
Function type: affine linear scaling with a strictly positive minimum for ranked friends.

For friends we use a separate linear mapping so that the lowest rank is still positive:

$$
posU_{friend}(p, K) =
\begin{cases}
0, & p \text{ is missing} \\
0, & K \le 0 \\
\frac{K + 1 - p}{K}, & K > 0
\end{cases}
$$

Example: if K=3, then posU_friend(1,3)=1, posU_friend(2,3)=2/3, posU_friend(3,3)=1/3.

This formula is used only for Table 2 (friend ranks).

### Utility components (per student and course)
Base utility from Table 1:
Function type: composition of rank-to-utility (affine Min-Max) with the PositionA lookup.

$$
Base(s, c) = posU(PositionA(s,c), |C|)
$$

Example: |C|=4 and PositionA(s,c)=2 gives Base(s,c)=2/3.

Directed friend preference from Table 2 (ranked among friends):
Function type: composition of friend-rank linear scaling with the PositionB lookup.

$$
Pref(s, f, c) = posU_{friend}(PositionB(s,f,c), K_{friend})
$$

Equivalently (when K_friend > 0):

$$
Pref(s, f, c) = \frac{K_{friend} + 1 - PositionB(s,f,c)}{K_{friend}}
$$

Example: K_friend=3, PositionB=1 gives Pref=1; PositionB=3 gives Pref=1/3.

Reactive friend bonus (only already allocated friends count):
Function type: weighted sum over a directed friend set with an indicator (reactive overlap).

$$
FriendBonus(s, c) = \sum_{f \in F(s)} \mathbb{1}[c \in A_f] \cdot Pref(s,f,c)
$$

Example: F(s)={f1,f2}, only f1 already has c, Pref(s,f1,c)=1, Pref(s,f2,c)=0.5 -> FriendBonus=1.

Total per-pick utility:
Function type: linear combination of base and friend bonus with weight lambda_s.

$$
U(s, c) = Base(s,c) + \lambda_s \cdot FriendBonus(s,c)
$$

Example: Base=0.6, lambda_s=0.4, FriendBonus=0.5 -> U=0.6+0.4*0.5=0.8.

### Feasible choices and pick rule
At a pick, the feasible set is:

$$
C_s = \{ c \in C \mid cap\_left(c) > 0 \ \land \ c \notin A_s \}
$$

Example: C={C1,C2,C3}, cap_left(C2)=0, A_s={C1} -> C_s={C3}.

The chosen course is the lexicographic maximum of a tie-break tuple:
Function type: lexicographic argmax (utility first, then deterministic tie-breaks).

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

Example: if U is tied and PositionA(C1)=2, PositionA(C2)=1, then C2 wins; if positions equal, higher Score wins, then rnd, then CourseID.

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

Example: pi=[S2,S1,S3] -> round1: S2,S1,S3; round2: S3,S1,S2.

### Post-phase objective (swap or add-drop)
After the draft, the algorithm can improve the allocation for `post_iters` iterations.

Per-student welfare (final allocation):
Function type: additive sum of per-course utilities over the final allocation.

$$
W_s = \sum_{c \in A_s}
\left[
Base(s,c) + \lambda_s \cdot \sum_{f \in F(s)} \mathbb{1}[c \in A_f] \cdot Pref(s,f,c)
\right]
$$

Example: A_s={C1,C2}, Base(s,C1)=1, Base(s,C2)=0.5, lambda_s=0.4, and only C1 overlaps with friends with sum Pref=1 -> W_s=(1+0.4*1)+(0.5+0)=1.9.

Global welfare:
Function type: aggregate sum over students.

$$
W = \sum_{s \in S} W_s
$$

Example: if W_s1=1.9 and W_s2=1.1, then W=3.0.

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

Example: A_s={C1,C2}, Base(s,C1)=1, Base(s,C2)=0.5 -> BaseSum_s=1.5.

$$
FriendSum_s = \sum_{c \in A_s} \sum_{f \in F(s)} \mathbb{1}[c \in A_f] \cdot Pref(s,f,c)
$$

Example: if overlaps sum to 1.0 on C1 and 0.2 on C2, then FriendSum_s=1.2.

$$
Total_s = BaseSum_s + \lambda_s \cdot FriendSum_s
$$

Example: BaseSum_s=1.5, FriendSum_s=1.2, lambda_s=0.4 -> Total_s=1.5+0.48=1.98.

Upper bounds for normalization:

$$
MaxBase_s = \sum_{c \in Top_b} Base(s,c)
$$

Example: b=2 and Base values across courses are [1.0, 0.6, 0.2] -> MaxBase_s=1.6.

$$
MaxTotalUpper_s = \sum_{c \in Top_b} \Big(Base(s,c) + \lambda_s \cdot \sum_{f \in F(s)} Pref(s,f,c)\Big)
$$

Example: b=2 and (Base + lambda*friend_sum) per course is [1.2, 0.9, 0.4] -> MaxTotalUpper_s=2.1.

Where `Top_b` selects the `b` courses with largest values in the respective expression (ignoring capacity and reactivity for the upper bound).

Normalized utilities used for inequality metrics:

$$
BaseNorm_s =
\begin{cases}
\frac{BaseSum_s}{MaxBase_s}, & MaxBase_s > 0 \\
0, & \text{otherwise}
\end{cases}
$$

Example: BaseSum_s=1.2 and MaxBase_s=1.6 -> BaseNorm_s=0.75.

$$
TotalNorm_s =
\begin{cases}
\frac{Total_s}{MaxTotalUpper_s}, & MaxTotalUpper_s > 0 \\
0, & \text{otherwise}
\end{cases}
$$

Example: Total_s=1.98 and MaxTotalUpper_s=2.1 -> TotalNorm_s≈0.943.

### Inequality and summary metrics (including Gini)
Let `x_i` be a list of non-negative values (the code clamps negatives to 0), sorted in non-decreasing order. Let `n = |x|`.

Total utility:
Function type: sum (L1 aggregate) over a list of values.

$$
TotalUtility = \sum_{i=1}^{n} x_i
$$

Example: x=[0.75, 0.25, 1.0] -> TotalUtility=2.0.

Gini index (used for `TotalNorm` and `BaseNorm`):
Function type: normalized Gini coefficient over non-negative values.

$$
Gini(x) =
\begin{cases}
0, & \sum_i x_i = 0 \\
\frac{\sum_{i=1}^{n} (2i - n - 1) x_i}{n \cdot \sum_{i=1}^{n} x_i}, & \text{otherwise}
\end{cases}
$$

Example: x=[0, 1] -> Gini=0.5; x=[1, 1, 1] -> Gini=0.

Jain index:
Function type: Jain's fairness index (quadratic mean ratio).

$$
Jain(x) =
\begin{cases}
0, & \sum_i x_i = 0 \\
\frac{(\sum_i x_i)^2}{n \cdot \sum_i x_i^2}, & \text{otherwise}
\end{cases}
$$

Example: x=[1, 1] -> Jain=1.0; x=[0, 1] -> Jain=0.5.

Theil index:
Function type: Theil entropy index of inequality.

$$
Theil(x) =
\frac{1}{n} \sum_{i: x_i > 0} \frac{x_i}{\mu} \cdot \log\left(\frac{x_i}{\mu}\right),
\quad \mu = \frac{1}{n}\sum_i x_i
$$

Example: x=[1, 1] -> Theil=0 (perfect equality).

Atkinson index (epsilon = 0.5 in this project):
Function type: Atkinson inequality index with epsilon = 0.5.

$$
Atkinson(x; \epsilon) =
1 - \frac{\left(\frac{1}{n}\sum_i x_i^{1-\epsilon}\right)^{\frac{1}{1-\epsilon}}}{\mu}
$$

Example: x=[1, 1] -> Atkinson=0 (perfect equality).

### Additional computed statistics
These are also reported in `metrics_extended.csv`:
- Average courses per student: `avg_courses = (1/|S|) * sum_s |A_s|`. Example: |S|=3 and |A_s|=[2,3,1] -> avg_courses=2.0.
- Full allocation rate: `share(|A_s| >= b)`. Example: b=3 and |A_s|=[3,2,3] -> 2/3.
- Unfilled seats: `sum_c cap_left(c)`. Example: cap_left=[0,1] -> unfilled=1.
- Course fill mean: `mean_c ((cap_default - cap_left(c)) / cap_default)`. Example: cap_default=2, cap_left=[0,1] -> fill rates [1.0,0.5], mean=0.75.
- Position stats over allocated courses with Table 1 rows:
  `avg_position`, `median_position`, `share_top1`, `share_top3`. Example: positions=[1,2,4] -> avg=7/3, median=2, share_top1=1/3, share_top3=2/3.
- Friend overlap stats:
  `avg_friend_overlaps_per_student` and share of students with any overlap. Example: overlaps per student [0,2,1] -> avg=1.0, share=2/3.
- Utility percentiles over `Total_s` using the index rule:
  `idx = round((n - 1) * p)`, for `p` in {0.10, 0.25, 0.50, 0.75, 0.90}. Example: totals=[0.2,0.5,0.9,1.1], p=0.50 -> idx=2 -> percentile=0.9.

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
python3 hbs_social.py \
  --csv-a tables/table1_200x8.csv \
  --csv-b tables/table2_200x8.csv \
  --csv-lambda tables/table3_lambda_200x8.csv \
  --cap-default 80 \
  --b 3 \
  --draft-rounds 3 \
  --post-iters 10 \
  --improve-mode add-drop \
  --seed 42 \
  --out-allocation results/allocation.csv \
  --out-adddrop results/post_allocation.csv \
  --out-summary results/summary.csv \
  --out-metrics-extended results/metrics_extended.csv
```

Useful optional flags: `--progress`, `--sanity-checks`, `--delta-check-every`, `--log-level`.

Run tests:

```bash
python tests/run_all_tests.py
```
