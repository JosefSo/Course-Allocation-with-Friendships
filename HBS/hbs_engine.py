from __future__ import annotations

import math
import random

from .hbs_config import _RunConfig
from .hbs_domain import (
    ExtendedMetrics,
    IndividualPref,
    PairPref,
    PickLogRow,
    PostAllocLogRow,
    RunResult,
    RunSummary,
)
from .hbs_metrics import (
    compute_atkinson_index,
    compute_gini_index,
    compute_jain_index,
    compute_theil_index,
    compute_total_utility,
)


def _pos_u(position: int | None, k_courses: int) -> float:
    """
    Convert a 1-based preference rank into a [0..1] utility.

    Assumptions:
      - Lower position means higher preference (1 is best).
      - If there is only one course, position=1 maps to 1, others to 0.
    """

    if position is None:
        return 0.0
    if k_courses <= 1:
        return 1.0 if position == 1 else 0.0
    return (k_courses - position) / (k_courses - 1)


def _pos_u_friend(position: int | None, k_friends: int) -> float:
    """
    Convert a 1-based friend rank into a (0..1] utility.

    Assumptions:
      - Lower position means higher preference (1 is best).
      - For k_friends >= 1: rank 1 -> 1, rank k -> 1/k.
    """

    if position is None:
        return 0.0
    if k_friends <= 0:
        return 0.0
    return (k_friends + 1 - position) / k_friends


def _score_u(score: int | None, score_min: int, score_max: int) -> float:
    """
    Min-Max normalize a Table 2 friend score to [0, 1] with clamping.

    A degenerate scale (score_max <= score_min) maps any present score to 1.0.
    """

    if score is None:
        return 0.0
    if score_max <= score_min:
        return 1.0
    value = (score - score_min) / (score_max - score_min)
    return min(1.0, max(0.0, value))


class _HbsSocialDraftEngine:
    """
    Application service that performs the allocation and computes metrics.

    Responsibility:
      - Execute the snake draft allocation given preferences and capacities.
      - Maintain allocation state (list + set) for fast membership checks.
      - Produce a detailed pick log for analysis/debugging.
      - Compute run-level metrics in a single, well-defined place.
    """

    _MISSING_POSITION = 10**9
    _MISSING_SCORE = -(10**9)
    _DEFAULT_LAMBDA = 0.3

    def __init__(
        self,
        *,
        individual_prefs: list[IndividualPref],
        pair_prefs: list[PairPref],
        student_lambdas: dict[str, float] | None,
        config: _RunConfig,
    ) -> None:
        self._config = config

        # Build the student/course universes from both tables to avoid dropping IDs.
        students: set[str] = set()
        courses: set[str] = set()
        for r in individual_prefs:
            students.add(r.student_id)
            courses.add(r.course_id)
        for r in pair_prefs:
            students.add(r.student_id_a)
            students.add(r.student_id_b)
            courses.add(r.course_id)

        if not students:
            raise ValueError("Students not found (CSV A/B empty?)")
        if not courses:
            raise ValueError("Courses not found (CSV A/B empty?)")

        self._students = sorted(students)
        self._courses = sorted(courses)
        self._k_courses = len(self._courses)

        self._lambda_by_student = {s: self._DEFAULT_LAMBDA for s in self._students}
        if student_lambdas:
            for student_id, value in student_lambdas.items():
                if student_id in self._lambda_by_student:
                    self._lambda_by_student[student_id] = value

        self._rng = random.Random(config.seed)

        # Allocation state:
        # - list: preserves pick order (useful for reporting / debugging)
        # - set: fast membership checks during drafting
        self._alloc_list: dict[str, list[str]] = {s: [] for s in self._students}
        self._alloc_set: dict[str, set[str]] = {s: set() for s in self._students}
        self._capacity_left: dict[str, int] = {c: config.default_capacity for c in self._courses}

        # Index individual preferences for O(1) lookup.
        self._indiv_by_key: dict[tuple[str, str], IndividualPref] = {
            (r.student_id, r.course_id): r for r in individual_prefs
        }
        self._base_u_by_key: dict[tuple[str, str], float] = {
            (r.student_id, r.course_id): _pos_u(r.position, self._k_courses) for r in individual_prefs
        }

        # Index pair preferences for O(1) lookup and build the directed friend graph.
        self._pair_by_key: dict[tuple[str, str, str], PairPref] = {}
        self._friends: dict[str, set[str]] = {}
        for r in pair_prefs:
            self._pair_by_key[(r.student_id_a, r.student_id_b, r.course_id)] = r
            self._friends.setdefault(r.student_id_a, set()).add(r.student_id_b)

        # Reverse graph for deterministic and efficient "who depends on this friend's allocation" queries.
        self._followers: dict[str, set[str]] = {s: set() for s in self._students}
        for student_id_a, friends in self._friends.items():
            for friend_id in friends:
                self._followers.setdefault(friend_id, set()).add(student_id_a)

        # Pref(s,f,c): normalized ScoreB when present (Position is tie-break only);
        # fallback to the linear friend-rank mapping when ScoreB is missing.
        self._k_friend_rank = max(1, max((r.position for r in pair_prefs), default=3))
        present_scores = [r.score for r in pair_prefs if r.score is not None]
        self._has_friend_scores = bool(present_scores)
        score_min = min(present_scores) if present_scores else 0
        score_max = max(present_scores) if present_scores else 0
        self._pair_u_by_key: dict[tuple[str, str, str], float] = {}
        for r in pair_prefs:
            if r.score is not None:
                pref = _score_u(r.score, score_min, score_max)
            else:
                pref = _pos_u_friend(r.position, self._k_friend_rank)
            self._pair_u_by_key[(r.student_id_a, r.student_id_b, r.course_id)] = pref

        # F(s,c): top-K friends per (student, course); ties broken by ScoreB desc,
        # then PositionB asc, then friend id for determinism.
        rows_by_sc: dict[tuple[str, str], list[PairPref]] = {}
        for r in pair_prefs:
            rows_by_sc.setdefault((r.student_id_a, r.course_id), []).append(r)
        self._friends_by_sc: dict[tuple[str, str], tuple[str, ...]] = {}
        for sc_key, rows in rows_by_sc.items():
            rows.sort(
                key=lambda r: (
                    -(r.score if r.score is not None else self._MISSING_SCORE),
                    r.position,
                    r.student_id_b,
                )
            )
            self._friends_by_sc[sc_key] = tuple(
                r.student_id_b for r in rows[: self._k_friend_rank]
            )

        # Reverse index: who counts f among their top-K friends for course c.
        followers_by_fc: dict[tuple[str, str], list[str]] = {}
        for (student_id_a, course_id), friend_ids in self._friends_by_sc.items():
            for friend_id in friend_ids:
                followers_by_fc.setdefault((friend_id, course_id), []).append(student_id_a)
        self._followers_by_fc: dict[tuple[str, str], tuple[str, ...]] = {
            k: tuple(sorted(v)) for k, v in followers_by_fc.items()
        }

        # Normalization cap for the friend bonus (fixed top-K variant).
        # With scores, each Pref is in [0,1], so the max over K friends is K.
        # Without scores, the max is sum of the rank mapping: (K + 1) / 2.
        if self._has_friend_scores:
            self._max_friend_bonus = float(self._k_friend_rank)
        else:
            self._max_friend_bonus = (self._k_friend_rank + 1) / 2.0

        # Precompute sorted adjacency for deterministic iteration and faster deltas.
        self._friends_list: dict[str, tuple[str, ...]] = {
            s: tuple(sorted(self._friends.get(s, set()))) for s in self._students
        }
        self._followers_list: dict[str, tuple[str, ...]] = {
            s: tuple(sorted(self._followers.get(s, set()))) for s in self._students
        }

    # ---- Utility model -------------------------------------------------

    def _base_utility(self, student_id: str, course_id: str) -> float:
        """Compute Base(student, course) from Table 1 Position only."""

        return self._base_u_by_key.get((student_id, course_id), 0.0)

    def _position_a(self, student_id: str, course_id: str) -> int:
        """
        Return Table 1 rank position for tie-breaking.

        Missing preferences are treated as a very poor rank.
        """

        row = self._indiv_by_key.get((student_id, course_id))
        return row.position if row is not None else self._MISSING_POSITION

    def _score_a(self, student_id: str, course_id: str) -> int:
        """
        Return Table 1 raw score for tie-breaking.

        Missing preferences are treated as very low score.
        """

        row = self._indiv_by_key.get((student_id, course_id))
        return row.score if row is not None else self._MISSING_SCORE

    def _friend_preference_utility(self, student_id: str, friend_id: str, course_id: str) -> float:
        """
        Compute the directed friend preference utility from Table 2: A's preference for B in a course.
        """

        return self._pair_u_by_key.get((student_id, friend_id, course_id), 0.0)

    def _friend_bonus_reactive(self, student_id: str, course_id: str) -> float:
        """
        Reactive FriendBonus(student, course).

        Only rewards overlap with courses that friends have already been allocated.
        """

        total = 0.0
        for friend_id in self._friends_by_sc.get((student_id, course_id), ()):
            if course_id in self._alloc_set.get(friend_id, set()):
                total += self._friend_preference_utility(student_id, friend_id, course_id)
        return total

    def _friend_bonus_norm(self, friend_bonus: float) -> float:
        """Normalize a raw friend bonus into [0, 1] using the fixed top-K cap."""

        if self._max_friend_bonus <= 0.0:
            return 0.0
        return friend_bonus / self._max_friend_bonus

    def _utility_components(self, student_id: str, course_id: str) -> tuple[float, float, float]:
        """
        U(s,c) = (1 - lambda_s) * Base(s,c) + lambda_s * FriendBonusNorm(s,c)
        """

        base = self._base_utility(student_id, course_id)
        friend_bonus = self._friend_bonus_norm(self._friend_bonus_reactive(student_id, course_id))
        lambda_ = self._lambda_by_student.get(student_id, self._DEFAULT_LAMBDA)
        total = (1.0 - lambda_) * base + lambda_ * friend_bonus
        return total, base, friend_bonus

    def _social_gain(self, student_id: str, course_id: str) -> float:
        """
        Positive externality of student_id joining course_id: the welfare gain of
        followers already enrolled in course_id who list student_id among their
        top-K friends for that course.
        """

        gain = 0.0
        for x in self._followers_by_fc.get((student_id, course_id), ()):
            if x == student_id:
                continue
            if course_id in self._alloc_set[x]:
                lambda_x = self._lambda_by_student.get(x, self._DEFAULT_LAMBDA)
                gain += lambda_x * self._friend_bonus_norm(
                    self._friend_preference_utility(x, student_id, course_id)
                )
        return gain

    def _pick_value(self, student_id: str, course_id: str) -> tuple[float, float, float]:
        """
        Value used to rank candidate courses at pick time.

        pick_rule="personal": the student's own utility U(s,c).
        pick_rule="social":   marginal global welfare, U(s,c) + SocialGain(s,c),
                              i.e. the pick internalizes friendship externalities.
        """

        u, base, friend_bonus = self._utility_components(student_id, course_id)
        if self._config.pick_rule == "social":
            u += self._social_gain(student_id, course_id)
        return u, base, friend_bonus

    # ---- Improvement objective (order-independent) ---------------------

    def _student_welfare(self, student_id: str) -> float:
        """
        Order-independent welfare contribution for a single student based on the final allocation.

        W_s = Σ_{c ∈ Alloc(s)} [ (1 - λ) * Base(s,c) + λ * FriendBonusNorm(s,c) ]
        """

        lambda_ = self._lambda_by_student.get(student_id, self._DEFAULT_LAMBDA)
        base_sum, friend_sum = self._student_welfare_components(student_id)
        return (1.0 - lambda_) * base_sum + lambda_ * self._friend_bonus_norm(friend_sum)

    def _student_welfare_components(self, student_id: str) -> tuple[float, float]:
        """
        Return (base_sum, raw friend_overlap_sum) for the final allocation.
        """

        base_sum = 0.0
        friend_sum = 0.0
        for course_id in sorted(self._alloc_set[student_id]):
            base_sum += self._base_utility(student_id, course_id)
            for friend_id in self._friends_by_sc.get((student_id, course_id), ()):
                if course_id in self._alloc_set[friend_id]:
                    friend_sum += self._friend_preference_utility(student_id, friend_id, course_id)
        return base_sum, friend_sum

    def _global_welfare(self) -> float:
        """Global welfare W(allocation) as a sum of per-student welfare contributions."""

        return sum(self._student_welfare(student_id) for student_id in self._students)

    def _max_possible_base(self, student_id: str) -> float:
        values = [self._base_utility(student_id, course_id) for course_id in self._courses]
        values.sort(reverse=True)
        return sum(values[: self._config.max_courses])

    def _max_possible_total_upper(self, student_id: str) -> float:
        lambda_ = self._lambda_by_student.get(student_id, self._DEFAULT_LAMBDA)
        values: list[float] = []
        for course_id in self._courses:
            base = self._base_utility(student_id, course_id)
            friend_sum = 0.0
            for friend_id in self._friends_by_sc.get((student_id, course_id), ()):
                friend_sum += self._friend_preference_utility(student_id, friend_id, course_id)
            values.append(
                (1.0 - lambda_) * base + lambda_ * self._friend_bonus_norm(friend_sum)
            )
        values.sort(reverse=True)
        return sum(values[: self._config.max_courses])

    def _max_possible_friend_upper(self, student_id: str) -> float:
        values: list[float] = []
        for course_id in self._courses:
            friend_sum = 0.0
            for friend_id in self._friends_by_sc.get((student_id, course_id), ()):
                friend_sum += self._friend_preference_utility(student_id, friend_id, course_id)
            values.append(friend_sum)
        values.sort(reverse=True)
        return sum(values[: self._config.max_courses])

    def _max_possible_overlap_count(self, student_id: str) -> int:
        counts: list[int] = []
        for course_id in self._courses:
            counts.append(len(self._friends_by_sc.get((student_id, course_id), ())))
        counts.sort(reverse=True)
        return sum(counts[: self._config.max_courses])

    # ---- Improvement moves --------------------------------------------

    def _swap_courses(self, s1: str, c1: str, s2: str, c2: str) -> None:
        """
        Swap one allocated course between two students.

        Assumes feasibility (no duplicates will be introduced).
        """

        i1 = self._alloc_list[s1].index(c1)
        i2 = self._alloc_list[s2].index(c2)
        self._alloc_list[s1][i1] = c2
        self._alloc_list[s2][i2] = c1

        self._alloc_set[s1].remove(c1)
        self._alloc_set[s1].add(c2)
        self._alloc_set[s2].remove(c2)
        self._alloc_set[s2].add(c1)

    def _swap_delta(self, s1: str, c1: str, s2: str, c2: str) -> float:
        """
        Compute ΔW for swapping courses c1/c2 between students s1/s2.

        Uses an order-independent welfare delta computed only from affected terms:
          - s1 and s2 base and friend-overlap changes for the swapped courses
          - followers of s1/s2 whose overlap with s1/s2 changes due to the swapped courses

        This avoids recomputing full per-student welfare for large instances.
        """
        alloc_set = self._alloc_set

        def _has_after(student_id: str, course_id: str) -> bool:
            if student_id == s1:
                if course_id == c1:
                    return False
                if course_id == c2:
                    return True
                return course_id in alloc_set[s1]
            if student_id == s2:
                if course_id == c2:
                    return False
                if course_id == c1:
                    return True
                return course_id in alloc_set[s2]
            return course_id in alloc_set[student_id]

        # ---- Self utility deltas (s1, s2) -----------------------------------

        norm = self._max_friend_bonus if self._max_friend_bonus > 0.0 else 1.0
        delta = 0.0

        # Base terms change only for swapped courses for s1 and s2.
        lambda_s1 = self._lambda_by_student.get(s1, self._DEFAULT_LAMBDA)
        lambda_s2 = self._lambda_by_student.get(s2, self._DEFAULT_LAMBDA)
        delta += (1.0 - lambda_s1) * (self._base_utility(s1, c2) - self._base_utility(s1, c1))
        delta += (1.0 - lambda_s2) * (self._base_utility(s2, c1) - self._base_utility(s2, c2))

        # Friend overlap terms for s1 and s2 change only for swapped courses.
        if lambda_s1 != 0.0:
            # s1 loses c1
            removed = 0.0
            for f in self._friends_by_sc.get((s1, c1), ()):
                if c1 in alloc_set[f]:
                    removed += self._friend_preference_utility(s1, f, c1)
            # s1 gains c2
            added = 0.0
            for f in self._friends_by_sc.get((s1, c2), ()):
                if _has_after(f, c2):
                    added += self._friend_preference_utility(s1, f, c2)
            delta += lambda_s1 * (added - removed) / norm

        if lambda_s2 != 0.0:
            # s2 loses c2
            removed = 0.0
            for f in self._friends_by_sc.get((s2, c2), ()):
                if c2 in alloc_set[f]:
                    removed += self._friend_preference_utility(s2, f, c2)
            # s2 gains c1
            added = 0.0
            for f in self._friends_by_sc.get((s2, c1), ()):
                if _has_after(f, c1):
                    added += self._friend_preference_utility(s2, f, c1)
            delta += lambda_s2 * (added - removed) / norm

        # ---- Follower deltas (only overlap terms can change) -----------------

        for friend_id, lost_course, gained_course in ((s1, c1, c2), (s2, c2, c1)):
            for x in self._followers_by_fc.get((friend_id, lost_course), ()):
                if x == s1 or x == s2:
                    continue
                if lost_course in alloc_set[x]:
                    lambda_x = self._lambda_by_student.get(x, self._DEFAULT_LAMBDA)
                    delta -= lambda_x * self._friend_preference_utility(x, friend_id, lost_course) / norm
            for x in self._followers_by_fc.get((friend_id, gained_course), ()):
                if x == s1 or x == s2:
                    continue
                if gained_course in alloc_set[x]:
                    lambda_x = self._lambda_by_student.get(x, self._DEFAULT_LAMBDA)
                    delta += lambda_x * self._friend_preference_utility(x, friend_id, gained_course) / norm

        return delta

    # ---- Draft execution ----------------------------------------------

    def _notify(self, event: dict) -> None:
        """Send a progress event to the optional callback (web UI live view)."""

        cb = self._config.progress_cb
        if cb is not None:
            cb(event)

    def _welfare_stat(self) -> dict:
        """Snapshot of welfare for the live charts (total and worst student)."""

        values = [self._student_welfare(s) for s in self._students]
        return {
            "type": "stat",
            "w": round(sum(values), 3),
            "wmin": round(min(values), 3) if values else 0.0,
        }

    def _assert_student_state(self, student_id: str) -> None:
        alloc_list = self._alloc_list[student_id]
        alloc_set = self._alloc_set[student_id]
        if len(alloc_list) != len(alloc_set):
            raise AssertionError(f"Allocation list/set size mismatch for {student_id}")
        if set(alloc_list) != alloc_set:
            raise AssertionError(f"Allocation list/set mismatch for {student_id}")
        if len(alloc_list) != len(set(alloc_list)):
            raise AssertionError(f"Duplicate course in allocation for {student_id}")

    def _assert_course_capacity(self, course_id: str) -> None:
        assigned = sum(1 for s in self._students if course_id in self._alloc_set[s])
        capacity = self._config.default_capacity
        if assigned > capacity:
            raise AssertionError(f"Capacity exceeded for {course_id}: {assigned} > {capacity}")
        expected_left = capacity - assigned
        if self._capacity_left.get(course_id) != expected_left:
            raise AssertionError(
                f"Capacity left mismatch for {course_id}: "
                f"{self._capacity_left.get(course_id)} != {expected_left}"
            )

    def _assert_swap_invariants(self, s1: str, c1: str, s2: str, c2: str) -> None:
        self._assert_student_state(s1)
        self._assert_student_state(s2)
        if self._config.sanity_checks:
            self._assert_course_capacity(c1)
            self._assert_course_capacity(c2)

    def run(self) -> RunResult:
        """
        Execute the snake draft and compute metrics.

        Flow:
          1) Create a deterministic student order (shuffle with seed).
          2) For each round, iterate in forward/reverse order depending on parity.
          3) For each student, select the best currently feasible course.
          4) Record pick details for auditing.
          5) After the draft, compute summary metrics.
        """
        draft_rounds = self._config.draft_rounds
        improvement_iters = self._config.post_iters

        if self._config.progress:
            print(
                f"Progress: total_iters={self._config.total_iters} "
                f"(draft_rounds={draft_rounds}, improvement_iters={improvement_iters})",
                flush=True,
            )

        pick_log = self._run_initial_draft(draft_rounds)
        if self._config.improve_mode == "swap":
            post_log = self._run_iterative_improvement(
                improvement_iters,
                start_iteration=draft_rounds + 1,
            )
        elif self._config.improve_mode == "add-drop":
            post_log = self._run_add_drop_improvement(
                improvement_iters,
                start_iteration=draft_rounds + 1,
            )
        elif self._config.improve_mode == "hybrid":
            post_log = self._run_hybrid_improvement(
                improvement_iters,
                start_iteration=draft_rounds + 1,
            )
        else:
            raise ValueError(f"Unknown improve_mode: {self._config.improve_mode}")

        summary, metrics_extended = self._compute_metrics()

        return RunResult(
            alloc=self._alloc_list,
            pick_log=pick_log,
            post_log=post_log,
            summary=summary,
            metrics_extended=metrics_extended,
        )

    # ---- HBS algorithm -------------------------------------------------------
    def _turn_order(self, order: list[str], round_index: int) -> list[str]:
        """
        Picking sequence for a given round (1-based), in fair-division terminology:

          - "round-robin":  1..n every round.
          - "snake":        balanced alternation, 1..n then n..1 alternating.
          - "n-first":      1..n in round 1, then n..1 in EVERY later round, so the
                            agent who picked last in round 1 picks first afterwards
                            (best MMS guarantee per Celine/Suksompong/Yuen, AAMAS 2026).
        """

        sequence = self._config.sequence
        if round_index == 1 or sequence == "round-robin":
            return order
        if sequence == "n-first":
            return list(reversed(order))
        # Default: snake / balanced alternation.
        return order if round_index % 2 == 1 else list(reversed(order))

    def _run_initial_draft(self, rounds: int) -> list[PickLogRow]:
        """
        Phase A: HBS-style draft allocation with a configurable picking sequence.
        """

        order = self._students[:]
        self._rng.shuffle(order)

        self._notify({
            "stage": "draft",
            "iter": 0,
            "viz": {
                "type": "init",
                "courses": list(self._courses),
                "cap": self._config.default_capacity,
                "order": list(order),
                "rounds": rounds,
                "sequence": self._config.sequence,
            },
        })

        pick_log: list[PickLogRow] = []

        for round_index in range(1, rounds + 1):
            if self._config.progress:
                print(f"Iter {round_index}/{self._config.total_iters}: DRAFT", flush=True)
            self._notify({
                "stage": "draft",
                "iter": round_index,
                "viz": {"type": "round", "round": round_index},
            })
            turn_order = self._turn_order(order, round_index)

            for student_id in turn_order:
                candidates = [
                    course_id
                    for course_id in self._courses
                    if self._capacity_left[course_id] > 0 and course_id not in self._alloc_set[student_id]
                ]
                if not candidates:
                    continue

                # We want deterministic but tie-breakable picks:
                #   1) max utility (bucketed to treat "similar utility" as ties)
                #   2) min rank position (Position from table A; smaller is better)
                #   3) max raw score (Score from table A)
                #   4) seeded random (break remaining ties)
                #   5) stable course id (as a final deterministic tie-breaker)
                scored: list[tuple[float, int, int, float, str, float, float, float]] = []
                for course_id in candidates:
                    u, base, friend_bonus = self._pick_value(student_id, course_id)
                    u_bucket = round(u, 9)
                    scored.append(
                        (
                            u_bucket,
                            self._position_a(student_id, course_id),
                            self._score_a(student_id, course_id),
                            self._rng.random(),
                            course_id,
                            u,
                            base,
                            friend_bonus,
                        )
                    )

                _u_bucket, _pos, _score, _rnd, course_id_star, u, base, friend_bonus = max(
                    scored,
                    key=lambda t: (t[0], -t[1], t[2], t[3], t[4]),
                )

                self._alloc_list[student_id].append(course_id_star)
                self._alloc_set[student_id].add(course_id_star)
                self._capacity_left[course_id_star] -= 1

                self._notify({
                    "stage": "draft",
                    "iter": round_index,
                    "viz": {
                        "type": "pick",
                        "s": student_id,
                        "c": course_id_star,
                        "u": round(u, 3),
                    },
                })

                pick_log.append(
                    PickLogRow(
                        student_id=student_id,
                        course_id=course_id_star,
                        round_picked=round_index,
                        utility_at_pick=u,
                        base_at_pick=base,
                        friend_bonus_at_pick=friend_bonus,
                    )
                )

            if self._config.progress_cb is not None:
                self._notify({"stage": "draft", "iter": round_index, "viz": self._welfare_stat()})

        return pick_log

    # ---- swap moves phase (optional) -------------------------------------------------------
    def _run_iterative_improvement(self, n: int, *, start_iteration: int) -> list[PostAllocLogRow]:
        """
        Phase B: deterministic local search for exactly n iterations.

        Each iteration performs one improvement attempt cycle:
          - enumerate feasible swap moves in a deterministic order
          - compute ΔW = W(after) - W(before)
          - apply the best move if it strictly improves global welfare
          - otherwise keep the allocation unchanged and continue
        """

        if n <= 0:
            return []

        improvement_log: list[PostAllocLogRow] = []
        swap_count = 0

        for offset in range(n):
            iteration = start_iteration + offset
            found = self._find_best_swap()
            if found is not None:
                best_delta, best_move = found
                swap_count = self._apply_swap_and_log(
                    best_delta, best_move, iteration, improvement_log, swap_count
                )
                _tag, s1, s2, c1, c2 = best_move
                self._notify({
                    "stage": "swap", "iter": iteration,
                    "event": f"{s1}:{c1} ⇄ {s2}:{c2}", "delta": best_delta,
                    "viz": {
                        "type": "swap", "s1": s1, "c1": c1, "s2": s2, "c2": c2,
                        "d": round(best_delta, 4),
                    },
                })
            else:
                if self._config.progress:
                    print(f"Iter {iteration}/{self._config.total_iters}: IMPROVE no-op", flush=True)
                improvement_log.append(self._no_op_log_row(iteration))
                self._notify({
                    "stage": "swap", "iter": iteration, "event": None,
                    "viz": {"type": "noop"},
                })
            if self._config.progress_cb is not None:
                self._notify({"iter": iteration, "viz": self._welfare_stat()})

        return improvement_log

    def _find_best_swap(self) -> tuple[float, tuple[str, str, str, str, str]] | None:
        """
        Enumerate all feasible pairwise swaps and return (delta, move) for the best
        strictly improving one, or None if no swap improves global welfare.
        """

        eps = 1e-12
        best_delta = 0.0
        best_move: tuple[str, str, str, str, str] | None = None

        for i, s1 in enumerate(self._students):
            alloc1 = sorted(self._alloc_set[s1])
            if not alloc1:
                continue
            for s2 in self._students[i + 1 :]:
                alloc2 = sorted(self._alloc_set[s2])
                if not alloc2:
                    continue
                for c1 in alloc1:
                    for c2 in alloc2:
                        if c1 == c2:
                            continue
                        if c2 in self._alloc_set[s1]:
                            continue
                        if c1 in self._alloc_set[s2]:
                            continue

                        delta = self._swap_delta(s1, c1, s2, c2)
                        move_key = ("swap", s1, s2, c1, c2)

                        if delta > best_delta + eps:
                            best_delta = delta
                            best_move = move_key
                        elif abs(delta - best_delta) <= eps and best_move is not None and move_key < best_move:
                            best_move = move_key

        if best_move is not None and best_delta > eps:
            return best_delta, best_move
        return None

    def _apply_swap_and_log(
        self,
        best_delta: float,
        best_move: tuple[str, str, str, str, str],
        iteration: int,
        improvement_log: list[PostAllocLogRow],
        swap_count: int,
    ) -> int:
        """Apply a chosen swap move (with optional delta validation) and log it."""

        _tag, s1, s2, c1, c2 = best_move
        check_delta = (
            self._config.delta_check_every > 0
            and (swap_count + 1) % self._config.delta_check_every == 0
        )
        if check_delta:
            before = self._global_welfare()
            self._swap_courses(s1, c1, s2, c2)
            after = self._global_welfare()
            actual_delta = after - before
            if abs(actual_delta - best_delta) > 1e-8:
                raise AssertionError(
                    f"Swap delta mismatch: expected {best_delta:.12f}, got {actual_delta:.12f}"
                )
        else:
            self._swap_courses(s1, c1, s2, c2)
        swap_count += 1
        self._assert_swap_invariants(s1, c1, s2, c2)
        if self._config.progress:
            print(
                f"Iter {iteration}/{self._config.total_iters}: IMPROVE swap "
                f"({s1}:{c1}) <-> ({s2}:{c2}) Δ={best_delta:.6f}",
                flush=True,
            )
        improvement_log.append(
            PostAllocLogRow(
                iteration=iteration,
                event_type="SWAP",
                student_id=None,
                dropped_courses=None,
                added_courses=None,
                swap_student_1=s1,
                swap_course_1=c1,
                swap_student_2=s2,
                swap_course_2=c2,
                delta_utility=best_delta,
            )
        )
        return swap_count

    def _no_op_log_row(self, iteration: int) -> PostAllocLogRow:
        return PostAllocLogRow(
            iteration=iteration,
            event_type="",
            student_id=None,
            dropped_courses=None,
            added_courses=None,
            swap_student_1=None,
            swap_course_1=None,
            swap_student_2=None,
            swap_course_2=None,
            delta_utility=None,
        )

    # ---- HYBRID phase (add-drop pass + best swap per iteration) ----------------
    def _run_hybrid_improvement(self, n: int, *, start_iteration: int) -> list[PostAllocLogRow]:
        """
        Phase B (hybrid): each iteration first runs one add-drop pass (uses spare
        capacity) and then, if the pass changed nothing, applies the single best
        welfare-improving swap. Converges when neither move type improves.
        """

        if n <= 0:
            return []

        post_log: list[PostAllocLogRow] = []
        swap_count = 0

        for offset in range(n):
            iteration = start_iteration + offset
            changed = self._add_drop_pass(iteration, post_log)
            if changed:
                self._notify({
                    "stage": "hybrid", "iter": iteration, "event": "add-drop пас",
                    "viz": {"type": "pass"},
                })
            else:
                found = self._find_best_swap()
                if found is not None:
                    best_delta, best_move = found
                    swap_count = self._apply_swap_and_log(
                        best_delta, best_move, iteration, post_log, swap_count
                    )
                    _tag, s1, s2, c1, c2 = best_move
                    self._notify({
                        "stage": "hybrid", "iter": iteration,
                        "event": f"{s1}:{c1} ⇄ {s2}:{c2}", "delta": best_delta,
                        "viz": {
                            "type": "swap", "s1": s1, "c1": c1, "s2": s2, "c2": c2,
                            "d": round(best_delta, 4),
                        },
                    })
                else:
                    if self._config.progress:
                        print(f"Iter {iteration}/{self._config.total_iters}: HYBRID no-op", flush=True)
                    post_log.append(self._no_op_log_row(iteration))
                    self._notify({
                        "stage": "hybrid", "iter": iteration, "event": None,
                        "viz": {"type": "noop"},
                    })
            if self._config.progress_cb is not None:
                self._notify({"iter": iteration, "viz": self._welfare_stat()})

        return post_log
    
    # ---- ADD/DROP phase -------------------------------------------------------
    def _run_add_drop_improvement(self, n: int, *, start_iteration: int) -> list[PostAllocLogRow]:
        """
        Phase B (HBS-style): add/drop passes over students using only courses with spare capacity.

        Each iteration is a single pass over students in a new random order.
        """

        if n <= 0:
            return []

        post_log: list[PostAllocLogRow] = []

        for offset in range(n):
            iteration = start_iteration + offset
            changed_in_pass = self._add_drop_pass(iteration, post_log)
            self._notify({
                "stage": "add-drop", "iter": iteration,
                "event": ("пас с изменениями" if changed_in_pass else None),
                "viz": ({"type": "pass"} if changed_in_pass else {"type": "noop"}),
            })
            if self._config.progress_cb is not None:
                self._notify({"iter": iteration, "viz": self._welfare_stat()})

            if not changed_in_pass:
                if self._config.progress:
                    print(f"Iter {iteration}/{self._config.total_iters}: ADD_DROP no-op", flush=True)
                post_log.append(self._no_op_log_row(iteration))

        return post_log

    def _add_drop_pass(self, iteration: int, post_log: list[PostAllocLogRow]) -> bool:
        """
        One add-drop pass over all students (random order): each student re-picks
        their best `b` courses among current courses + courses with spare capacity.

        Returns True if any student changed their allocation.
        """

        if self._config.progress:
            print(f"Iter {iteration}/{self._config.total_iters}: ADD_DROP pass", flush=True)

        order = self._students[:]
        self._rng.shuffle(order)
        changed_in_pass = False

        for student_id in order:
                current_set = self._alloc_set[student_id]
                candidates: set[str] = set(current_set)
                for course_id in self._courses:
                    if self._capacity_left[course_id] > 0:
                        candidates.add(course_id)
                if not candidates:
                    continue

                scored: list[tuple[float, int, int, float, str]] = []
                for course_id in candidates:
                    u, _base, _friend_bonus = self._utility_components(student_id, course_id)
                    u_bucket = round(u, 9)
                    scored.append(
                        (
                            u_bucket,
                            self._position_a(student_id, course_id),
                            self._score_a(student_id, course_id),
                            self._rng.random(),
                            course_id,
                        )
                    )
                scored.sort(key=lambda t: (t[0], -t[1], t[2], t[3], t[4]), reverse=True)

                k = min(self._config.max_courses, len(scored))
                desired_list = [item[4] for item in scored[:k]]
                desired_set = set(desired_list)

                dropped = sorted(current_set - desired_set)
                added = sorted(desired_set - current_set)
                if not dropped and not added:
                    continue

                for course_id in added:
                    if self._capacity_left[course_id] <= 0:
                        raise AssertionError(f"Add/drop capacity exhausted for {course_id}")

                for course_id in dropped:
                    self._capacity_left[course_id] += 1
                for course_id in added:
                    self._capacity_left[course_id] -= 1

                old_list = self._alloc_list[student_id]
                kept = [c for c in old_list if c in desired_set]
                added_in_order = [c for c in desired_list if c not in old_list]
                self._alloc_list[student_id] = kept + added_in_order
                self._alloc_set[student_id] = desired_set

                self._assert_student_state(student_id)
                if self._config.sanity_checks:
                    for course_id in dropped + added:
                        self._assert_course_capacity(course_id)

                changed_in_pass = True
                self._notify({
                    "iter": iteration,
                    "viz": {
                        "type": "ad",
                        "s": student_id,
                        "drop": list(dropped),
                        "add": list(added),
                    },
                })
                post_log.append(
                    PostAllocLogRow(
                        iteration=iteration,
                        event_type="ADD_DROP",
                        student_id=student_id,
                        dropped_courses=tuple(dropped),
                        added_courses=tuple(added),
                        swap_student_1=None,
                        swap_course_1=None,
                        swap_student_2=None,
                        swap_course_2=None,
                        delta_utility=None,
                    )
                )

        return changed_in_pass

    # ---- Metrics -------------------------------------------------------

    def _envy_ef1_metrics(self) -> dict[str, float]:
        """
        Envy and EF1 (envy-free up to one item) shares under three envy notions:

          - base:   courses only, u_s(B) = Σ Base(s,c)
          - friend: friends only, u_s(B) = Σ FriendOverlap(s,c) (raw)
          - total:  (1-λ)*base + λ*overlap/MaxFriendBonus per course

        Counterfactual convention for externalities: when student s evaluates
        student t's bundle, everyone else's allocation (including t's) is kept
        fixed, so friend overlap is computed against the current allocation.

        Reported per notion:
          - envy_pairs_share_*:    share of ordered pairs (s,t) with u_s(A_t) > u_s(A_s)
          - ef1_violation_share_*: share of students that envy someone even after
                                   removing the best single course from the envied bundle
        """

        eps = 1e-9
        students = self._students
        n = len(students)

        # Per-student per-course value components under the current allocation.
        base_val: dict[str, dict[str, float]] = {}
        overlap_val: dict[str, dict[str, float]] = {}
        for s in students:
            bv: dict[str, float] = {}
            ov: dict[str, float] = {}
            for c in self._courses:
                bv[c] = self._base_utility(s, c)
                overlap = 0.0
                for f in self._friends_by_sc.get((s, c), ()):
                    if c in self._alloc_set[f]:
                        overlap += self._friend_preference_utility(s, f, c)
                ov[c] = overlap
            base_val[s] = bv
            overlap_val[s] = ov

        notions = ("base", "friend", "total")
        envy_pairs = {k: 0 for k in notions}
        ef1_violating_students = {k: 0 for k in notions}
        total_pairs = n * (n - 1) if n > 1 else 0

        def _course_value(s: str, c: str, notion: str) -> float:
            if notion == "base":
                return base_val[s][c]
            if notion == "friend":
                return overlap_val[s][c]
            lambda_ = self._lambda_by_student.get(s, self._DEFAULT_LAMBDA)
            return (1.0 - lambda_) * base_val[s][c] + lambda_ * self._friend_bonus_norm(
                overlap_val[s][c]
            )

        for s in students:
            has_ef1_violation = {k: False for k in notions}
            own_value = {
                k: sum(_course_value(s, c, k) for c in self._alloc_set[s]) for k in notions
            }
            for t in students:
                if t == s:
                    continue
                bundle_t = self._alloc_set[t]
                if not bundle_t:
                    continue
                for notion in notions:
                    values_t = [_course_value(s, c, notion) for c in bundle_t]
                    other = sum(values_t)
                    if other > own_value[notion] + eps:
                        envy_pairs[notion] += 1
                        # Additive valuations: EF1 holds iff removing the single
                        # most valuable course of the envied bundle removes envy.
                        if other - max(values_t) > own_value[notion] + eps:
                            has_ef1_violation[notion] = True
            for notion in notions:
                if has_ef1_violation[notion]:
                    ef1_violating_students[notion] += 1

        result: dict[str, float] = {}
        for notion in notions:
            result[f"envy_pairs_share_{notion}"] = (
                envy_pairs[notion] / total_pairs if total_pairs else 0.0
            )
            result[f"ef1_violation_share_{notion}"] = (
                ef1_violating_students[notion] / n if n else 0.0
            )
        return result

    def _compute_metrics(self) -> tuple[RunSummary, ExtendedMetrics]:
        """Compute summary + extended metrics from the final allocation."""

        per_student_total: list[float] = []
        per_student_base: list[float] = []
        per_student_friend: list[float] = []
        per_student_max_base: list[float] = []
        per_student_max_total: list[float] = []
        per_student_max_friend: list[float] = []
        per_student_max_overlaps: list[int] = []

        for student_id in self._students:
            base_sum, friend_sum = self._student_welfare_components(student_id)
            lambda_ = self._lambda_by_student.get(student_id, self._DEFAULT_LAMBDA)
            total = (1.0 - lambda_) * base_sum + lambda_ * self._friend_bonus_norm(friend_sum)
            per_student_base.append(base_sum)
            per_student_friend.append(friend_sum)
            per_student_total.append(total)
            per_student_max_base.append(self._max_possible_base(student_id))
            per_student_max_total.append(self._max_possible_total_upper(student_id))
            per_student_max_friend.append(self._max_possible_friend_upper(student_id))
            per_student_max_overlaps.append(self._max_possible_overlap_count(student_id))

        per_student_base_norm = [
            (u / max_b if max_b > 0.0 else 0.0)
            for u, max_b in zip(per_student_base, per_student_max_base)
        ]
        per_student_total_norm = [
            (u / max_t if max_t > 0.0 else 0.0)
            for u, max_t in zip(per_student_total, per_student_max_total)
        ]

        total_utility = compute_total_utility(per_student_total)
        gini_total_norm = compute_gini_index(per_student_total_norm)
        gini_base_norm = compute_gini_index(per_student_base_norm)
        total_utility_max = sum(per_student_max_total)
        summary = RunSummary(
            total_utility=total_utility,
            gini_total_norm=gini_total_norm,
            gini_base_norm=gini_base_norm,
            total_utility_max=total_utility_max,
            gini_total_norm_max=1.0,
            gini_base_norm_max=1.0,
        )

        metrics = self._compute_extended_metrics(
            per_student_total=per_student_total,
            per_student_base=per_student_base,
            per_student_friend=per_student_friend,
            per_student_total_norm=per_student_total_norm,
            per_student_base_norm=per_student_base_norm,
            per_student_max_total=per_student_max_total,
            per_student_max_base=per_student_max_base,
            per_student_max_friend=per_student_max_friend,
            per_student_max_overlaps=per_student_max_overlaps,
        )
        return summary, metrics

    def _compute_extended_metrics(
        self,
        *,
        per_student_total: list[float],
        per_student_base: list[float],
        per_student_friend: list[float],
        per_student_total_norm: list[float],
        per_student_base_norm: list[float],
        per_student_max_total: list[float],
        per_student_max_base: list[float],
        per_student_max_friend: list[float],
        per_student_max_overlaps: list[int],
    ) -> ExtendedMetrics:
        n_students = len(self._students)
        total_base = sum(per_student_base)
        total_friend = sum(per_student_friend)
        total_max_base = sum(per_student_max_base)
        total_max_total = sum(per_student_max_total)
        total_max_friend = sum(per_student_max_friend)

        avg_courses = sum(len(self._alloc_set[s]) for s in self._students) / n_students
        full_alloc = sum(1 for s in self._students if len(self._alloc_set[s]) >= self._config.max_courses)
        students_full_alloc_rate = full_alloc / n_students if n_students else 0.0

        unfilled_seats = sum(self._capacity_left.values())
        fill_rates = [
            (self._config.default_capacity - self._capacity_left[c]) / self._config.default_capacity
            for c in self._courses
        ]
        course_fill_rate_mean = sum(fill_rates) / len(fill_rates) if fill_rates else 0.0

        positions: list[int] = []
        top1 = 0
        top3 = 0
        for student_id in self._students:
            for course_id in self._alloc_set[student_id]:
                row = self._indiv_by_key.get((student_id, course_id))
                if row is None:
                    continue
                positions.append(row.position)
                if row.position <= 1:
                    top1 += 1
                if row.position <= 3:
                    top3 += 1
        avg_position = sum(positions) / len(positions) if positions else 0.0
        positions_sorted = sorted(positions)
        median_position = positions_sorted[len(positions_sorted) // 2] if positions_sorted else 0.0
        share_top1 = top1 / len(positions) if positions else 0.0
        share_top3 = top3 / len(positions) if positions else 0.0

        overlaps_total = 0
        students_with_overlap = 0
        for student_id in self._students:
            friends = self._friends_list.get(student_id, ())
            if not friends:
                continue
            student_overlaps = 0
            for course_id in self._alloc_set[student_id]:
                for friend_id in friends:
                    if (student_id, friend_id, course_id) not in self._pair_by_key:
                        continue
                    if course_id in self._alloc_set[friend_id]:
                        student_overlaps += 1
                        overlaps_total += 1
            if student_overlaps > 0:
                students_with_overlap += 1
        avg_friend_overlaps = overlaps_total / n_students if n_students else 0.0
        share_students_with_overlap = students_with_overlap / n_students if n_students else 0.0

        total_utility = compute_total_utility(per_student_total)
        avg_utility = total_utility / n_students if n_students else 0.0

        sorted_total = sorted(per_student_total)

        def _percentile(p: float) -> float:
            if not sorted_total:
                return 0.0
            idx = int(round((len(sorted_total) - 1) * p))
            return sorted_total[min(max(idx, 0), len(sorted_total) - 1)]

        def _geomean(values: list[float]) -> float:
            if not values or any(v <= 0.0 for v in values):
                return 0.0
            return math.exp(sum(math.log(v) for v in values) / len(values))

        envy_metrics = self._envy_ef1_metrics()

        metrics = {
            "total_utility": total_utility,
            "total_base_utility": total_base,
            "total_friend_utility": total_friend,
            "avg_utility_per_student": avg_utility,
            # Fair-division welfare objectives.
            "egalitarian_welfare": (min(per_student_total) if per_student_total else 0.0),
            "egalitarian_welfare_norm": (
                min(per_student_total_norm) if per_student_total_norm else 0.0
            ),
            "nash_welfare_geomean": _geomean(per_student_total),
            **envy_metrics,
            "avg_courses_per_student": avg_courses,
            "students_full_alloc_rate": students_full_alloc_rate,
            "unfilled_seats_total": float(unfilled_seats),
            "course_fill_rate_mean": course_fill_rate_mean,
            "avg_position": avg_position,
            "median_position": float(median_position),
            "share_top1": share_top1,
            "share_top3": share_top3,
            "avg_friend_overlaps_per_student": avg_friend_overlaps,
            "share_students_with_any_friend_overlap": share_students_with_overlap,
            "gini_total_norm": compute_gini_index(per_student_total_norm),
            "gini_base_norm": compute_gini_index(per_student_base_norm),
            "jain_index": compute_jain_index(per_student_total),
            "theil_index": compute_theil_index(per_student_total),
            "atkinson_index_e0_5": compute_atkinson_index(per_student_total, epsilon=0.5),
            "utility_min": min(sorted_total) if sorted_total else 0.0,
            "utility_p10": _percentile(0.10),
            "utility_p25": _percentile(0.25),
            "utility_p50": _percentile(0.50),
            "utility_p75": _percentile(0.75),
            "utility_p90": _percentile(0.90),
        }
        max_total_per_student = max(per_student_max_total) if per_student_max_total else 0.0
        max_overlaps_total = sum(per_student_max_overlaps)
        avg_overlaps_max = max_overlaps_total / n_students if n_students else 0.0
        students_with_friend_prefs = sum(1 for v in per_student_max_overlaps if v > 0)
        share_possible_overlap = (
            students_with_friend_prefs / n_students if n_students else 0.0
        )
        max_course_rank = float(len(self._courses)) if self._courses else 0.0
        total_seats = float(len(self._courses) * self._config.default_capacity)

        maxima = {
            "total_utility": total_max_total,
            "total_base_utility": total_max_base,
            "total_friend_utility": total_max_friend,
            "avg_utility_per_student": (total_max_total / n_students if n_students else 0.0),
            "egalitarian_welfare": (min(per_student_max_total) if per_student_max_total else 0.0),
            "egalitarian_welfare_norm": 1.0,
            "nash_welfare_geomean": _geomean(per_student_max_total),
            "envy_pairs_share_base": 1.0,
            "ef1_violation_share_base": 1.0,
            "envy_pairs_share_friend": 1.0,
            "ef1_violation_share_friend": 1.0,
            "envy_pairs_share_total": 1.0,
            "ef1_violation_share_total": 1.0,
            "avg_courses_per_student": float(self._config.max_courses),
            "students_full_alloc_rate": 1.0,
            "unfilled_seats_total": total_seats,
            "course_fill_rate_mean": 1.0,
            "avg_position": max_course_rank,
            "median_position": max_course_rank,
            "share_top1": 1.0,
            "share_top3": 1.0,
            "avg_friend_overlaps_per_student": avg_overlaps_max,
            "share_students_with_any_friend_overlap": share_possible_overlap,
            "gini_total_norm": 1.0,
            "gini_base_norm": 1.0,
            "jain_index": 1.0,
            "theil_index": (math.log(n_students) if n_students > 0 else 0.0),
            "atkinson_index_e0_5": 1.0,
            "utility_min": max_total_per_student,
            "utility_p10": max_total_per_student,
            "utility_p25": max_total_per_student,
            "utility_p50": max_total_per_student,
            "utility_p75": max_total_per_student,
            "utility_p90": max_total_per_student,
        }
        return ExtendedMetrics(values=metrics, maxima=maxima)
