from __future__ import annotations

import random
from functools import cmp_to_key

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
    Normalize score into [0..1].

    If the scale is degenerate (score_max <= score_min), return 1.0 for any present score.
    """

    if score is None:
        return 0.0
    if score_max <= score_min:
        return 1.0
    value = (score - score_min) / (score_max - score_min)
    return max(0.0, min(1.0, value))


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
    _UTILITY_TAU = 1e-9  # Matches prior 1e-9 rounding to treat FP noise as ties.

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
        self._draft_order: tuple[str, ...] | None = None

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

        # Group pair preferences by (student, course) to enable deterministic top-K selection.
        pair_groups: dict[tuple[str, str], list[PairPref]] = {}
        for r in pair_prefs:
            pair_groups.setdefault((r.student_id_a, r.course_id), []).append(r)

        # Table 2 contains a friend rank Position (top-k) and an optional Score.
        # Score is the only numerical driver of Pref; Position is used only for tie-breaks.
        self._k_friend_rank = max(1, max((r.position for r in pair_prefs), default=3))

        def _friend_sort_key(row: PairPref) -> tuple[float, int, str]:
            score_key = row.score if row.score is not None else float("-inf")
            return (-score_key, row.position, row.student_id_b)

        self._friends_by_course: dict[tuple[str, str], tuple[str, ...]] = {}
        top_pairs: list[PairPref] = []
        for key, items in pair_groups.items():
            items_sorted = sorted(items, key=_friend_sort_key)
            if len(items_sorted) > self._k_friend_rank:
                items_sorted = items_sorted[: self._k_friend_rank]
            top_pairs.extend(items_sorted)
            self._friends_by_course[key] = tuple(r.student_id_b for r in items_sorted)

        # Index pair preferences for O(1) lookup and build the directed friend graph.
        self._pair_by_key: dict[tuple[str, str, str], PairPref] = {}
        self._friends: dict[str, set[str]] = {}
        for r in top_pairs:
            self._pair_by_key[(r.student_id_a, r.student_id_b, r.course_id)] = r
            self._friends.setdefault(r.student_id_a, set()).add(r.student_id_b)

        # Reverse graph for deterministic and efficient "who depends on this friend's allocation" queries.
        self._followers: dict[str, set[str]] = {s: set() for s in self._students}
        for student_id_a, friends in self._friends.items():
            for friend_id in friends:
                self._followers.setdefault(friend_id, set()).add(student_id_a)

        friend_scores = [r.score for r in top_pairs if r.score is not None]
        self._friend_score_min = min(friend_scores) if friend_scores else 0
        self._friend_score_max = max(friend_scores) if friend_scores else 0

        def _pair_weight(position: int, score: int | None) -> float:
            if score is None:
                return _pos_u_friend(position, self._k_friend_rank)
            return _score_u(score, self._friend_score_min, self._friend_score_max)

        self._friend_bonus_max_per_course = (
            float(self._k_friend_rank)
            if friend_scores
            else sum(
                _pos_u_friend(rank, self._k_friend_rank)
                for rank in range(1, self._k_friend_rank + 1)
            )
        )

        self._pair_u_by_key: dict[tuple[str, str, str], float] = {
            (r.student_id_a, r.student_id_b, r.course_id): _pair_weight(r.position, r.score)
            for r in top_pairs
        }

        # Precompute sorted adjacency for deterministic iteration and faster deltas.
        self._followers_list: dict[str, tuple[str, ...]] = {
            s: tuple(sorted(self._followers.get(s, set()))) for s in self._students
        }

    # ---- Utility model -------------------------------------------------

    def _sort_course_entries(self, entries: list[tuple]) -> list[tuple]:
        """
        Sort course entries by utility with a tau-based tie-break on PositionA.

        Entries must contain (u, position, score, rnd, course_id, ...).
        """

        def _cmp(a: tuple, b: tuple) -> int:
            u_a, pos_a, score_a, rnd_a, course_a = a[0], a[1], a[2], a[3], a[4]
            u_b, pos_b, score_b, rnd_b, course_b = b[0], b[1], b[2], b[3], b[4]
            if abs(u_a - u_b) > self._UTILITY_TAU:
                return -1 if u_a > u_b else 1
            if pos_a != pos_b:
                return -1 if pos_a < pos_b else 1
            if score_a != score_b:
                return -1 if score_a > score_b else 1
            if rnd_a != rnd_b:
                return -1 if rnd_a > rnd_b else 1
            if course_a != course_b:
                return -1 if course_a > course_b else 1
            return 0

        return sorted(entries, key=cmp_to_key(_cmp))

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
        for friend_id in self._friends_by_course.get((student_id, course_id), ()):
            if course_id in self._alloc_set.get(friend_id, set()):
                total += self._friend_preference_utility(student_id, friend_id, course_id)
        return total

    def _friend_bonus_norm(self, friend_bonus: float) -> float:
        if self._friend_bonus_max_per_course <= 0.0:
            return 0.0
        return friend_bonus / self._friend_bonus_max_per_course

    def _utility_components(self, student_id: str, course_id: str) -> tuple[float, float, float]:
        """
        Return (total_utility, base, friend_bonus).
        """

        base = self._base_utility(student_id, course_id)
        friend_bonus_raw = self._friend_bonus_reactive(student_id, course_id)
        friend_bonus = self._friend_bonus_norm(friend_bonus_raw)
        lambda_ = self._lambda_by_student.get(student_id, self._DEFAULT_LAMBDA)
        total = (1.0 - lambda_) * base + lambda_ * friend_bonus
        return total, base, friend_bonus

    # ---- Improvement objective (order-independent) ---------------------

    def _student_welfare(self, student_id: str) -> float:
        """
        Order-independent welfare contribution for a single student based on the final allocation.

        W_s = Σ_{c ∈ Alloc(s)} [ (1-λ) * Base(s,c) + λ * FriendBonusNorm(s,c) ]
        """

        lambda_ = self._lambda_by_student.get(student_id, self._DEFAULT_LAMBDA)
        total = 0.0
        student_courses = self._alloc_set[student_id]
        for course_id in sorted(student_courses):
            base = self._base_utility(student_id, course_id)
            friend_bonus_raw = 0.0
            for friend_id in self._friends_by_course.get((student_id, course_id), ()):
                if course_id in self._alloc_set[friend_id]:
                    friend_bonus_raw += self._friend_preference_utility(
                        student_id, friend_id, course_id
                    )
            friend_bonus = self._friend_bonus_norm(friend_bonus_raw)
            total += (1.0 - lambda_) * base + lambda_ * friend_bonus
        return total

    def _student_welfare_components(self, student_id: str) -> tuple[float, float]:
        """
        Return (base_sum, friend_bonus_norm_sum) for the final allocation.
        """

        base_sum = 0.0
        friend_sum_raw = 0.0
        for course_id in sorted(self._alloc_set[student_id]):
            base_sum += self._base_utility(student_id, course_id)
            for friend_id in self._friends_by_course.get((student_id, course_id), ()):
                if course_id in self._alloc_set[friend_id]:
                    friend_sum_raw += self._friend_preference_utility(student_id, friend_id, course_id)
        return base_sum, self._friend_bonus_norm(friend_sum_raw)

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
            for friend_id in self._friends_by_course.get((student_id, course_id), ()):
                friend_sum += self._friend_preference_utility(student_id, friend_id, course_id)
            friend_norm = self._friend_bonus_norm(friend_sum)
            values.append((1.0 - lambda_) * base + lambda_ * friend_norm)
        values.sort(reverse=True)
        return sum(values[: self._config.max_courses])

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

        friends_s1_c1 = self._friends_by_course.get((s1, c1), ())
        friends_s1_c2 = self._friends_by_course.get((s1, c2), ())
        friends_s2_c1 = self._friends_by_course.get((s2, c1), ())
        friends_s2_c2 = self._friends_by_course.get((s2, c2), ())

        # ---- Self utility deltas (s1, s2) -----------------------------------

        delta = 0.0

        # Base terms change only for swapped courses for s1 and s2.
        delta += self._base_utility(s1, c2) - self._base_utility(s1, c1)
        delta += self._base_utility(s2, c1) - self._base_utility(s2, c2)

        # Friend overlap terms for s1 and s2 change only for swapped courses.
        lambda_s1 = self._lambda_by_student.get(s1, self._DEFAULT_LAMBDA)
        lambda_s2 = self._lambda_by_student.get(s2, self._DEFAULT_LAMBDA)
        if lambda_s1 != 0.0:
            # s1 loses c1
            removed = 0.0
            for f in friends_s1_c1:
                if c1 in alloc_set[f]:
                    removed += self._friend_preference_utility(s1, f, c1)
            # s1 gains c2
            added = 0.0
            for f in friends_s1_c2:
                if _has_after(f, c2):
                    added += self._friend_preference_utility(s1, f, c2)
            delta += lambda_s1 * (added - removed)

            # s2 loses c2
            removed = 0.0
            for f in friends_s2_c2:
                if c2 in alloc_set[f]:
                    removed += self._friend_preference_utility(s2, f, c2)
            # s2 gains c1
            added = 0.0
            for f in friends_s2_c1:
                if _has_after(f, c1):
                    added += self._friend_preference_utility(s2, f, c1)
            delta += lambda_s2 * (added - removed)

        # ---- Follower deltas (only overlap terms can change) -----------------

        followers_s1 = self._followers_list.get(s1, ())
        for x in followers_s1:
            if x == s1 or x == s2:
                continue
            alloc_x = alloc_set[x]
            lambda_x = self._lambda_by_student.get(x, self._DEFAULT_LAMBDA)
            if c1 in alloc_x:
                delta -= lambda_x * self._friend_preference_utility(x, s1, c1)
            if c2 in alloc_x:
                delta += lambda_x * self._friend_preference_utility(x, s1, c2)

        followers_s2 = self._followers_list.get(s2, ())
        for x in followers_s2:
            if x == s1 or x == s2:
                continue
            alloc_x = alloc_set[x]
            lambda_x = self._lambda_by_student.get(x, self._DEFAULT_LAMBDA)
            if c2 in alloc_x:
                delta -= lambda_x * self._friend_preference_utility(x, s2, c2)
            if c1 in alloc_x:
                delta += lambda_x * self._friend_preference_utility(x, s2, c1)

        return delta

    # ---- Draft execution ----------------------------------------------

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
    def _run_initial_draft(self, rounds: int) -> list[PickLogRow]:
        """
        Phase A: standard HBS-style snake draft allocation (existing logic).
        """

        order = self._students[:]
        self._rng.shuffle(order)
        self._draft_order = tuple(order)

        pick_log: list[PickLogRow] = []

        for round_index in range(1, rounds + 1):
            if self._config.progress:
                print(f"Iter {round_index}/{self._config.total_iters}: DRAFT", flush=True)
            turn_order = order if round_index % 2 == 1 else list(reversed(order))

            for student_id in turn_order:
                candidates = [
                    course_id
                    for course_id in self._courses
                    if self._capacity_left[course_id] > 0 and course_id not in self._alloc_set[student_id]
                ]
                if not candidates:
                    continue

                # We want deterministic but tie-breakable picks:
                #   1) max utility (ties within _UTILITY_TAU are considered equal)
                #   2) min rank position (Position from table A; smaller is better)
                #   3) max raw score (Score from table A)
                #   4) seeded random (break remaining ties)
                #   5) stable course id (as a final deterministic tie-breaker)
                scored: list[tuple[float, int, int, float, str, float, float]] = []
                for course_id in candidates:
                    u, base, friend_bonus = self._utility_components(student_id, course_id)
                    scored.append(
                        (
                            u,
                            self._position_a(student_id, course_id),
                            self._score_a(student_id, course_id),
                            self._rng.random(),
                            course_id,
                            base,
                            friend_bonus,
                        )
                    )

                ranked = self._sort_course_entries(scored)
                u, _pos, _score, _rnd, course_id_star, base, friend_bonus = ranked[0]

                self._alloc_list[student_id].append(course_id_star)
                self._alloc_set[student_id].add(course_id_star)
                self._capacity_left[course_id_star] -= 1

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

        eps = 1e-12
        improvement_log: list[PostAllocLogRow] = []
        swap_count = 0

        for offset in range(n):
            iteration = start_iteration + offset
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
            else:
                if self._config.progress:
                    print(f"Iter {iteration}/{self._config.total_iters}: IMPROVE no-op", flush=True)
                improvement_log.append(
                    PostAllocLogRow(
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
                )

        return improvement_log
    
    # ---- ADD/DROP phase -------------------------------------------------------
    def _run_add_drop_improvement(self, n: int, *, start_iteration: int) -> list[PostAllocLogRow]:
        """
        Phase B (HBS-style): add/drop passes over students using only courses with spare capacity.

        Each iteration is a single pass over students in the draft order, using snake parity
        (odd iterations forward, even iterations reverse).
        """

        if n <= 0:
            return []

        post_log: list[PostAllocLogRow] = []

        for offset in range(n):
            iteration = start_iteration + offset
            if self._config.progress:
                print(f"Iter {iteration}/{self._config.total_iters}: ADD_DROP pass", flush=True)

            base_order = list(self._draft_order or self._students)
            order = base_order if iteration % 2 == 1 else list(reversed(base_order))
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
                for course_id in sorted(candidates):
                    u, _base, _friend_bonus = self._utility_components(student_id, course_id)
                    scored.append(
                        (
                            u,
                            self._position_a(student_id, course_id),
                            self._score_a(student_id, course_id),
                            self._rng.random(),
                            course_id,
                        )
                    )
                scored = self._sort_course_entries(scored)

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

            if not changed_in_pass:
                if self._config.progress:
                    print(f"Iter {iteration}/{self._config.total_iters}: ADD_DROP no-op", flush=True)
                post_log.append(
                    PostAllocLogRow(
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
                )

        return post_log

    # ---- Metrics -------------------------------------------------------

    def _compute_metrics(self) -> tuple[RunSummary, ExtendedMetrics]:
        """Compute summary + extended metrics from the final allocation."""

        per_student_total: list[float] = []
        per_student_base: list[float] = []
        per_student_friend: list[float] = []
        per_student_max_base: list[float] = []
        per_student_max_total: list[float] = []

        for student_id in self._students:
            base_sum, friend_sum = self._student_welfare_components(student_id)
            lambda_ = self._lambda_by_student.get(student_id, self._DEFAULT_LAMBDA)
            total = (1.0 - lambda_) * base_sum + lambda_ * friend_sum
            per_student_base.append(base_sum)
            per_student_friend.append(friend_sum)
            per_student_total.append(total)
            per_student_max_base.append(self._max_possible_base(student_id))
            per_student_max_total.append(self._max_possible_total_upper(student_id))

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
        summary = RunSummary(
            total_utility=total_utility,
            gini_total_norm=gini_total_norm,
            gini_base_norm=gini_base_norm,
        )

        metrics = self._compute_extended_metrics(
            per_student_total=per_student_total,
            per_student_base=per_student_base,
            per_student_friend=per_student_friend,
            per_student_total_norm=per_student_total_norm,
            per_student_base_norm=per_student_base_norm,
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
    ) -> ExtendedMetrics:
        n_students = len(self._students)
        total_base = sum(per_student_base)
        total_friend = sum(per_student_friend)

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
            student_overlaps = 0
            for course_id in self._alloc_set[student_id]:
                friends = self._friends_by_course.get((student_id, course_id), ())
                if not friends:
                    continue
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

        metrics = {
            "total_utility": total_utility,
            "total_base_utility": total_base,
            "total_friend_utility": total_friend,
            "avg_utility_per_student": avg_utility,
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
        return ExtendedMetrics(values=metrics)
