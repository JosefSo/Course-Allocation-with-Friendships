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


def _score_u(score: int | None, score_min: int | None, score_max: int | None) -> float:
    """
    Normalize a score into [0..1] using min-max scaling with clamping.

    If the score scale is degenerate, any present score maps to 1.0.
    """

    if score is None or score_min is None or score_max is None:
        return 0.0
    if score_max <= score_min:
        return 1.0
    value = (score - score_min) / (score_max - score_min)
    return max(0.0, min(1.0, float(value)))


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
        self._draft_order: list[str] | None = None

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

        # Friend preference weights:
        # - if scores are present, use min-max normalized scores
        # - otherwise fall back to a position-based mapping
        self._k_friend_rank = max(1, max((r.position for r in pair_prefs), default=3))
        score_values = [r.score for r in pair_prefs if r.score is not None]
        score_min = min(score_values) if score_values else None
        score_max = max(score_values) if score_values else None

        self._pair_u_by_key: dict[tuple[str, str, str], float] = {}
        self._friend_sum_by_student_course: dict[tuple[str, str], float] = {}
        for r in pair_prefs:
            if r.score is not None and score_min is not None and score_max is not None:
                weight = _score_u(r.score, score_min, score_max)
            else:
                weight = _pos_u_friend(r.position, self._k_friend_rank)
            key = (r.student_id_a, r.student_id_b, r.course_id)
            self._pair_u_by_key[key] = weight
            sc_key = (r.student_id_a, r.course_id)
            self._friend_sum_by_student_course[sc_key] = (
                self._friend_sum_by_student_course.get(sc_key, 0.0) + weight
            )

        # Precompute sorted adjacency for deterministic iteration and faster deltas.
        self._friends_list: dict[str, tuple[str, ...]] = {
            s: tuple(sorted(self._friends.get(s, set()))) for s in self._students
        }
        self._followers_list: dict[str, tuple[str, ...]] = {
            s: tuple(sorted(self._followers.get(s, set()))) for s in self._students
        }

        rows_by_sc: dict[tuple[str, str], list[PairPref]] = {}
        for row in pair_prefs:
            rows_by_sc.setdefault((row.student_id_a, row.course_id), []).append(row)
        self._friends_by_sc: dict[tuple[str, str], tuple[str, ...]] = {}
        for key, rows in rows_by_sc.items():
            rows.sort(
                key=lambda row: (
                    -(row.score if row.score is not None else self._MISSING_SCORE),
                    row.position,
                    row.student_id_b,
                )
            )
            self._friends_by_sc[key] = tuple(
                row.student_id_b for row in rows[: self._k_friend_rank]
            )

        followers_by_fc: dict[tuple[str, str], list[str]] = {}
        for (student_id, course_id), friend_ids in self._friends_by_sc.items():
            for friend_id in friend_ids:
                followers_by_fc.setdefault((friend_id, course_id), []).append(student_id)
        self._followers_by_fc = {
            key: tuple(sorted(values)) for key, values in followers_by_fc.items()
        }

        self._friend_sum_by_student_course = {
            (student_id, course_id): sum(
                self._friend_preference_utility(student_id, friend_id, course_id)
                for friend_id in friend_ids
            )
            for (student_id, course_id), friend_ids in self._friends_by_sc.items()
        }

        # Per-student normalization constant for reactive friend bonus.
        self._max_friend_bonus_by_student: dict[str, float] = {}
        for s in self._students:
            max_sum = 0.0
            for c in self._courses:
                max_sum = max(max_sum, self._friend_sum_by_student_course.get((s, c), 0.0))
            self._max_friend_bonus_by_student[s] = max_sum if max_sum > 0.0 else 1.0

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

    def _max_friend_bonus(self, student_id: str) -> float:
        return self._max_friend_bonus_by_student.get(student_id, 1.0)

    def _utility_components(self, student_id: str, course_id: str) -> tuple[float, float, float]:
        base = self._base_utility(student_id, course_id)
        friend_bonus = self._friend_bonus_reactive(student_id, course_id)
        lambda_ = self._lambda_by_student.get(student_id, self._DEFAULT_LAMBDA)
        friend_norm = friend_bonus / self._max_friend_bonus(student_id)
        total = (1.0 - lambda_) * base + lambda_ * friend_norm
        return total, base, friend_bonus

    def _social_gain(self, student_id: str, course_id: str) -> float:
        """Welfare externality created when a student joins a course."""

        gain = 0.0
        for follower_id in self._followers_by_fc.get((student_id, course_id), ()):
            if course_id not in self._alloc_set[follower_id]:
                continue
            lambda_ = self._lambda_by_student.get(follower_id, self._DEFAULT_LAMBDA)
            pref = self._friend_preference_utility(follower_id, student_id, course_id)
            gain += lambda_ * pref / self._max_friend_bonus(follower_id)
        return gain

    def _pick_value(self, student_id: str, course_id: str) -> tuple[float, float, float]:
        value, base, friend_bonus = self._utility_components(student_id, course_id)
        if self._config.pick_rule == "social":
            value += self._social_gain(student_id, course_id)
        return value, base, friend_bonus

    def _notify(self, event: dict) -> None:
        callback = self._config.progress_cb
        if callback is not None:
            callback(event)

    def _welfare_stat(self) -> dict:
        values = [self._student_welfare(student_id) for student_id in self._students]
        return {
            "type": "stat",
            "w": round(sum(values), 3),
            "wmin": round(min(values), 3) if values else 0.0,
        }

    # ---- Improvement objective (order-independent) ---------------------

    def _student_welfare(self, student_id: str) -> float:
        """
        Order-independent welfare contribution for a single student based on the final allocation.

        W_s = Σ_{c ∈ Alloc(s)} [(1 - λ_s) * Base(s,c) + λ_s * FriendOverlapNorm(s,c)]
        """

        friends = self._friends_list.get(student_id, ())
        lambda_ = self._lambda_by_student.get(student_id, self._DEFAULT_LAMBDA)
        friend_max = self._max_friend_bonus(student_id)
        total = 0.0
        student_courses = self._alloc_set[student_id]
        for course_id in sorted(student_courses):
            base = self._base_utility(student_id, course_id)
            friend_sum = 0.0
            for friend_id in friends:
                if course_id in self._alloc_set[friend_id]:
                    friend_sum += self._friend_preference_utility(student_id, friend_id, course_id)
            friend_norm = friend_sum / friend_max
            total += (1.0 - lambda_) * base + lambda_ * friend_norm
        return total

    def _student_welfare_components(self, student_id: str) -> tuple[float, float]:
        """
        Return (base_sum, friend_overlap_sum) for the final allocation.
        """

        base_sum = 0.0
        friend_sum = 0.0
        friends = self._friends_list.get(student_id, ())
        for course_id in sorted(self._alloc_set[student_id]):
            base_sum += self._base_utility(student_id, course_id)
            for friend_id in friends:
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
        friend_max = self._max_friend_bonus(student_id)
        values: list[float] = []
        for course_id in self._courses:
            base = self._base_utility(student_id, course_id)
            friend_upper = self._friend_sum_by_student_course.get((student_id, course_id), 0.0)
            friend_norm_upper = friend_upper / friend_max
            values.append((1.0 - lambda_) * base + lambda_ * friend_norm_upper)
        values.sort(reverse=True)
        return sum(values[: self._config.max_courses])

    def _max_possible_friend_upper(self, student_id: str) -> float:
        values: list[float] = []
        for course_id in self._courses:
            values.append(self._friend_sum_by_student_course.get((student_id, course_id), 0.0))
        values.sort(reverse=True)
        return sum(values[: self._config.max_courses])

    def _max_possible_overlap_count(self, student_id: str) -> int:
        friends = self._friends_list.get(student_id, ())
        if not friends:
            return 0
        counts: list[int] = []
        for course_id in self._courses:
            count = 0
            for friend_id in friends:
                if (student_id, friend_id, course_id) in self._pair_by_key:
                    count += 1
            counts.append(count)
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

    def _replace_course(self, student_id: str, drop_course: str, add_course: str) -> None:
        """
        Replace one course for a single student (1-for-1 add/drop).

        Assumes add_course has free capacity and drop_course is currently allocated.
        """

        idx = self._alloc_list[student_id].index(drop_course)
        self._alloc_list[student_id][idx] = add_course
        self._alloc_set[student_id].remove(drop_course)
        self._alloc_set[student_id].add(add_course)
        self._capacity_left[drop_course] += 1
        self._capacity_left[add_course] -= 1

    def _compose_event_type(
        self,
        move_type: str,
        objective_scope: str,
        *,
        submove: str | None = None,
    ) -> str:
        prefix = f"{move_type}_{objective_scope}".upper().replace("-", "_")
        if submove is None:
            return prefix
        return f"{prefix}_{submove.upper().replace('-', '_')}"

    def _measure_objective(self, objective_scope: str, student_id: str | None = None) -> float:
        if objective_scope == "global":
            return self._global_welfare()
        if objective_scope == "personal":
            if student_id is None:
                raise ValueError("student_id is required for personal objective")
            return self._student_welfare(student_id)
        raise ValueError(f"Unknown objective_scope: {objective_scope}")

    def _build_desired_rebuild_list(self, student_id: str) -> list[str]:
        current_set = self._alloc_set[student_id]
        candidates: set[str] = set(current_set)
        for course_id in self._courses:
            if self._capacity_left[course_id] > 0:
                candidates.add(course_id)
        if not candidates:
            return []

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
        return [item[4] for item in scored[:k]]

    def _apply_student_rebuild(self, student_id: str, desired_list: list[str]) -> tuple[list[str], list[str]]:
        desired_set = set(desired_list)
        current_set = self._alloc_set[student_id]
        dropped = sorted(current_set - desired_set)
        added = sorted(desired_set - current_set)
        if not dropped and not added:
            return (dropped, added)

        for course_id in added:
            if self._capacity_left[course_id] <= 0:
                raise AssertionError(f"Add/drop capacity exhausted for {course_id}")

        for course_id in dropped:
            self._capacity_left[course_id] += 1
        for course_id in added:
            self._capacity_left[course_id] -= 1

        old_list = self._alloc_list[student_id]
        kept = [course_id for course_id in old_list if course_id in desired_set]
        added_in_order = [course_id for course_id in desired_list if course_id not in old_list]
        self._alloc_list[student_id] = kept + added_in_order
        self._alloc_set[student_id] = desired_set

        self._assert_student_state(student_id)
        if self._config.sanity_checks:
            for course_id in dropped + added:
                self._assert_course_capacity(course_id)
        return (dropped, added)

    def _simulate_student_rebuild(
        self,
        student_id: str,
        desired_list: list[str],
        objective_scope: str,
    ) -> tuple[float, list[str], list[str]]:
        desired_set = set(desired_list)
        current_set = self._alloc_set[student_id]
        dropped = sorted(current_set - desired_set)
        added = sorted(desired_set - current_set)
        if not dropped and not added:
            return (0.0, dropped, added)

        affected_courses = set(current_set) | desired_set
        old_list = self._alloc_list[student_id][:]
        old_set = set(current_set)
        old_capacity = {course_id: self._capacity_left[course_id] for course_id in affected_courses}

        before = self._measure_objective(objective_scope, student_id)
        self._apply_student_rebuild(student_id, desired_list)
        after = self._measure_objective(objective_scope, student_id)

        self._alloc_list[student_id] = old_list
        self._alloc_set[student_id] = old_set
        for course_id, value in old_capacity.items():
            self._capacity_left[course_id] = value

        return (after - before, dropped, added)

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

        friends_s1 = self._friends_list.get(s1, ())
        friends_s2 = self._friends_list.get(s2, ())

        # ---- Self utility deltas (s1, s2) -----------------------------------

        delta = 0.0

        lambda_s1 = self._lambda_by_student.get(s1, self._DEFAULT_LAMBDA)
        lambda_s2 = self._lambda_by_student.get(s2, self._DEFAULT_LAMBDA)
        friend_scale_s1 = lambda_s1 / self._max_friend_bonus(s1)
        friend_scale_s2 = lambda_s2 / self._max_friend_bonus(s2)

        # Base terms change only for swapped courses for s1 and s2.
        delta += (1.0 - lambda_s1) * (self._base_utility(s1, c2) - self._base_utility(s1, c1))
        delta += (1.0 - lambda_s2) * (self._base_utility(s2, c1) - self._base_utility(s2, c2))

        # Friend overlap terms for s1 and s2 change only for swapped courses.
        if friend_scale_s1 != 0.0:
            removed = 0.0
            for f in friends_s1:
                if c1 in alloc_set[f]:
                    removed += self._friend_preference_utility(s1, f, c1)
            added = 0.0
            for f in friends_s1:
                if _has_after(f, c2):
                    added += self._friend_preference_utility(s1, f, c2)
            delta += friend_scale_s1 * (added - removed)

        if friend_scale_s2 != 0.0:
            removed = 0.0
            for f in friends_s2:
                if c2 in alloc_set[f]:
                    removed += self._friend_preference_utility(s2, f, c2)
            added = 0.0
            for f in friends_s2:
                if _has_after(f, c1):
                    added += self._friend_preference_utility(s2, f, c1)
            delta += friend_scale_s2 * (added - removed)

        # ---- Follower deltas (only overlap terms can change) -----------------

        followers_s1 = self._followers_list.get(s1, ())
        for x in followers_s1:
            if x == s1 or x == s2:
                continue
            alloc_x = alloc_set[x]
            lambda_x = self._lambda_by_student.get(x, self._DEFAULT_LAMBDA)
            follower_scale = lambda_x / self._max_friend_bonus(x)
            if c1 in alloc_x:
                delta -= follower_scale * self._friend_preference_utility(x, s1, c1)
            if c2 in alloc_x:
                delta += follower_scale * self._friend_preference_utility(x, s1, c2)

        followers_s2 = self._followers_list.get(s2, ())
        for x in followers_s2:
            if x == s1 or x == s2:
                continue
            alloc_x = alloc_set[x]
            lambda_x = self._lambda_by_student.get(x, self._DEFAULT_LAMBDA)
            follower_scale = lambda_x / self._max_friend_bonus(x)
            if c2 in alloc_x:
                delta -= follower_scale * self._friend_preference_utility(x, s2, c2)
            if c1 in alloc_x:
                delta += follower_scale * self._friend_preference_utility(x, s2, c1)

        return delta

    def _add_drop_delta(self, student_id: str, drop_course: str, add_course: str) -> float:
        """
        Compute ΔW for a 1-for-1 add/drop move for a single student.

        The delta accounts for:
          - the student's own base and friend-overlap changes
          - follower externalities from the student leaving/entering courses
        """

        alloc_set = self._alloc_set
        friends = self._friends_list.get(student_id, ())
        lambda_s = self._lambda_by_student.get(student_id, self._DEFAULT_LAMBDA)
        friend_scale_s = lambda_s / self._max_friend_bonus(student_id)

        delta = (1.0 - lambda_s) * (
            self._base_utility(student_id, add_course) - self._base_utility(student_id, drop_course)
        )

        if friend_scale_s != 0.0:
            removed = 0.0
            for f in friends:
                if drop_course in alloc_set[f]:
                    removed += self._friend_preference_utility(student_id, f, drop_course)
            added = 0.0
            for f in friends:
                if add_course in alloc_set[f]:
                    added += self._friend_preference_utility(student_id, f, add_course)
            delta += friend_scale_s * (added - removed)

        followers = self._followers_list.get(student_id, ())
        for x in followers:
            if x == student_id:
                continue
            lambda_x = self._lambda_by_student.get(x, self._DEFAULT_LAMBDA)
            follower_scale = lambda_x / self._max_friend_bonus(x)
            if follower_scale == 0.0:
                continue
            alloc_x = alloc_set[x]
            if drop_course in alloc_x:
                delta -= follower_scale * self._friend_preference_utility(x, student_id, drop_course)
            if add_course in alloc_x:
                delta += follower_scale * self._friend_preference_utility(x, student_id, add_course)

        return delta

    def _add_drop_delta_for_student(self, student_id: str, drop_course: str, add_course: str) -> float:
        """
        Compute ΔU(student) for a 1-for-1 add/drop move for a single student.

        This delta ignores follower externalities and only evaluates utility change
        for the initiating student.
        """

        alloc_set = self._alloc_set
        friends = self._friends_list.get(student_id, ())
        lambda_s = self._lambda_by_student.get(student_id, self._DEFAULT_LAMBDA)
        friend_scale_s = lambda_s / self._max_friend_bonus(student_id)

        delta = (1.0 - lambda_s) * (
            self._base_utility(student_id, add_course) - self._base_utility(student_id, drop_course)
        )

        if friend_scale_s != 0.0:
            removed = 0.0
            for f in friends:
                if drop_course in alloc_set[f]:
                    removed += self._friend_preference_utility(student_id, f, drop_course)
            added = 0.0
            for f in friends:
                if add_course in alloc_set[f]:
                    added += self._friend_preference_utility(student_id, f, add_course)
            delta += friend_scale_s * (added - removed)

        return delta

    def _swap_delta_for_student(
        self,
        student_id: str,
        drop_course: str,
        holder_id: str,
        target_course: str,
    ) -> float:
        """
        Compute ΔU(student) for swapping one course with a holder.

        This delta ignores utility changes for the holder and all followers.
        """

        alloc_set = self._alloc_set

        def _has_after(friend_id: str, course_id: str) -> bool:
            if friend_id == student_id:
                if course_id == drop_course:
                    return False
                if course_id == target_course:
                    return True
                return course_id in alloc_set[student_id]
            if friend_id == holder_id:
                if course_id == target_course:
                    return False
                if course_id == drop_course:
                    return True
                return course_id in alloc_set[holder_id]
            return course_id in alloc_set[friend_id]

        friends = self._friends_list.get(student_id, ())
        lambda_s = self._lambda_by_student.get(student_id, self._DEFAULT_LAMBDA)
        friend_scale_s = lambda_s / self._max_friend_bonus(student_id)

        delta = (1.0 - lambda_s) * (
            self._base_utility(student_id, target_course) - self._base_utility(student_id, drop_course)
        )

        if friend_scale_s != 0.0:
            removed = 0.0
            for friend_id in friends:
                if drop_course in alloc_set[friend_id]:
                    removed += self._friend_preference_utility(student_id, friend_id, drop_course)
            added = 0.0
            for friend_id in friends:
                if _has_after(friend_id, target_course):
                    added += self._friend_preference_utility(student_id, friend_id, target_course)
            delta += friend_scale_s * (added - removed)

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
        move_type = self._config.move_type
        objective_scope = self._config.objective_scope
        if move_type == "swap":
            post_log = self._run_swap_improvement(
                improvement_iters,
                start_iteration=draft_rounds + 1,
                objective=objective_scope,
            )
        elif move_type == "drop-add":
            post_log = self._run_drop_add_improvement(
                improvement_iters,
                start_iteration=draft_rounds + 1,
                objective=objective_scope,
            )
        elif move_type == "hybrid":
            post_log = self._run_hybrid_improvement(
                improvement_iters,
                start_iteration=draft_rounds + 1,
                objective=objective_scope,
            )
        else:
            raise ValueError(f"Unknown move_type: {move_type}")

        if self._config.progress_cb is not None:
            for row in post_log:
                event: dict = {
                    "stage": self._config.effective_improve_mode,
                    "iter": row.iteration,
                }
                if row.swap_student_1 and row.swap_student_2:
                    event["event"] = (
                        f"{row.swap_student_1}:{row.swap_course_1} ⇄ "
                        f"{row.swap_student_2}:{row.swap_course_2}"
                    )
                    event["delta"] = row.delta_utility
                    event["viz"] = {
                        "type": "swap",
                        "s1": row.swap_student_1,
                        "c1": row.swap_course_1,
                        "s2": row.swap_student_2,
                        "c2": row.swap_course_2,
                        "d": round(row.delta_utility or 0.0, 4),
                    }
                elif row.student_id and (row.dropped_courses or row.added_courses):
                    event["viz"] = {
                        "type": "ad",
                        "s": row.student_id,
                        "drop": list(row.dropped_courses or ()),
                        "add": list(row.added_courses or ()),
                    }
                else:
                    event["viz"] = {"type": "noop"}
                self._notify(event)
            self._notify({
                "stage": self._config.effective_improve_mode,
                "iter": draft_rounds + improvement_iters,
                "viz": self._welfare_stat(),
            })

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
        if round_index == 1 or self._config.sequence == "round-robin":
            return order
        if self._config.sequence == "n-first":
            return list(reversed(order))
        return order if round_index % 2 == 1 else list(reversed(order))

    def _run_initial_draft(self, rounds: int) -> list[PickLogRow]:
        """
        Phase A: standard HBS-style snake draft allocation (existing logic).
        """

        order = self._students[:]
        self._rng.shuffle(order)
        # Persist the seeded permutation so post-phase can reuse the same snake order.
        self._draft_order = order[:]

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
                #   2) max raw score (Score from table A)
                #   3) min rank position (Position from table A; smaller is better)
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
    def _run_swap_improvement(
        self,
        n: int,
        *,
        start_iteration: int,
        objective: str,
    ) -> list[PostAllocLogRow]:
        if n <= 0:
            return []
        if objective not in {"global", "personal"}:
            raise ValueError(f"Unknown swap objective: {objective}")

        eps = 1e-12
        event_type = self._compose_event_type("swap", objective)
        improvement_log: list[PostAllocLogRow] = []
        move_count = 0

        for offset in range(n):
            iteration = start_iteration + offset
            best_delta = 0.0
            best_move: tuple[str, str, str, str] | None = None
            best_tie_key: tuple[str, ...] | None = None

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

                            if objective == "global":
                                delta = self._swap_delta(s1, c1, s2, c2)
                                tie_key = (s1, s2, c1, c2)
                                candidate = (s1, c1, s2, c2)
                                if delta > best_delta + eps:
                                    best_delta = delta
                                    best_move = candidate
                                    best_tie_key = tie_key
                                elif (
                                    abs(delta - best_delta) <= eps
                                    and best_move is not None
                                    and best_tie_key is not None
                                    and tie_key < best_tie_key
                                ):
                                    best_move = candidate
                                    best_tie_key = tie_key
                                continue

                            delta_1 = self._swap_delta_for_student(s1, c1, s2, c2)
                            tie_key_1 = (s1, c2, s2, c1)
                            candidate_1 = (s1, c1, s2, c2)
                            if delta_1 > best_delta + eps:
                                best_delta = delta_1
                                best_move = candidate_1
                                best_tie_key = tie_key_1
                            elif (
                                abs(delta_1 - best_delta) <= eps
                                and best_move is not None
                                and best_tie_key is not None
                                and tie_key_1 < best_tie_key
                            ):
                                best_move = candidate_1
                                best_tie_key = tie_key_1

                            delta_2 = self._swap_delta_for_student(s2, c2, s1, c1)
                            tie_key_2 = (s2, c1, s1, c2)
                            candidate_2 = (s2, c2, s1, c1)
                            if delta_2 > best_delta + eps:
                                best_delta = delta_2
                                best_move = candidate_2
                                best_tie_key = tie_key_2
                            elif (
                                abs(delta_2 - best_delta) <= eps
                                and best_move is not None
                                and best_tie_key is not None
                                and tie_key_2 < best_tie_key
                            ):
                                best_move = candidate_2
                                best_tie_key = tie_key_2

            if best_move is not None and best_delta > eps:
                s1, c1, s2, c2 = best_move
                check_delta = (
                    self._config.delta_check_every > 0
                    and (move_count + 1) % self._config.delta_check_every == 0
                )
                if check_delta:
                    before = self._measure_objective(objective, s1)
                    self._swap_courses(s1, c1, s2, c2)
                    after = self._measure_objective(objective, s1)
                    actual_delta = after - before
                    if abs(actual_delta - best_delta) > 1e-8:
                        raise AssertionError(
                            f"Swap delta mismatch: expected {best_delta:.12f}, got {actual_delta:.12f}"
                        )
                else:
                    self._swap_courses(s1, c1, s2, c2)
                move_count += 1
                self._assert_swap_invariants(s1, c1, s2, c2)
                if self._config.progress:
                    print(
                        f"Iter {iteration}/{self._config.total_iters}: {event_type} "
                        f"({s1}:{c1}) <-> ({s2}:{c2}) Δ={best_delta:.6f}",
                        flush=True,
                    )
                improvement_log.append(
                    PostAllocLogRow(
                        iteration=iteration,
                        event_type=event_type,
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
                    print(f"Iter {iteration}/{self._config.total_iters}: {event_type} no-op", flush=True)
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
    def _run_drop_add_improvement(
        self,
        n: int,
        *,
        start_iteration: int,
        objective: str,
    ) -> list[PostAllocLogRow]:
        if n <= 0:
            return []
        if objective not in {"global", "personal"}:
            raise ValueError(f"Unknown drop-add objective: {objective}")

        eps = 1e-12
        event_type = self._compose_event_type("drop-add", objective)
        post_log: list[PostAllocLogRow] = []
        move_count = 0

        for offset in range(n):
            iteration = start_iteration + offset
            if self._config.progress:
                print(
                    f"Iter {iteration}/{self._config.total_iters}: {event_type} pass",
                    flush=True,
                )

            order = self._students[:]
            self._rng.shuffle(order)
            changed_in_pass = False

            for student_id in order:
                desired_list = self._build_desired_rebuild_list(student_id)
                if not desired_list:
                    continue

                delta, dropped, added = self._simulate_student_rebuild(
                    student_id,
                    desired_list,
                    objective,
                )
                if not dropped and not added:
                    continue
                if delta <= eps:
                    continue

                check_delta = (
                    self._config.delta_check_every > 0
                    and (move_count + 1) % self._config.delta_check_every == 0
                )
                if check_delta:
                    before = self._measure_objective(objective, student_id)
                    self._apply_student_rebuild(student_id, desired_list)
                    after = self._measure_objective(objective, student_id)
                    actual_delta = after - before
                    if abs(actual_delta - delta) > 1e-8:
                        raise AssertionError(
                            f"Drop-add delta mismatch: expected {delta:.12f}, got {actual_delta:.12f}"
                        )
                else:
                    self._apply_student_rebuild(student_id, desired_list)

                move_count += 1
                changed_in_pass = True
                post_log.append(
                    PostAllocLogRow(
                        iteration=iteration,
                        event_type=event_type,
                        student_id=student_id,
                        dropped_courses=tuple(dropped),
                        added_courses=tuple(added),
                        swap_student_1=None,
                        swap_course_1=None,
                        swap_student_2=None,
                        swap_course_2=None,
                        delta_utility=delta,
                    )
                )

            if not changed_in_pass:
                if self._config.progress:
                    print(f"Iter {iteration}/{self._config.total_iters}: {event_type} no-op", flush=True)
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

    # ---- Hybrid phase -------------------------------------------------------
    def _run_hybrid_improvement(
        self,
        n: int,
        *,
        start_iteration: int,
        objective: str,
    ) -> list[PostAllocLogRow]:
        """
        Hybrid post-phase:
          - snake-order passes using the same seeded permutation as the draft
          - for each student, try to pull toward any missing course
          - if target has capacity -> 1-for-1 add/drop
          - if target is full -> targeted swap with any holder
          - objective="global": accept only moves with ΔW_global > eps
          - objective="personal": accept only moves with ΔU(student) > eps
          - stop early if a full pass makes no changes
        """

        if n <= 0:
            return []
        if objective not in {"global", "personal"}:
            raise ValueError(f"Unknown hybrid objective: {objective}")

        if objective == "global":
            add_drop_delta_fn = self._add_drop_delta
            swap_delta_fn = self._swap_delta
            event_add = self._compose_event_type("hybrid", objective, submove="drop-add")
            event_swap = self._compose_event_type("hybrid", objective, submove="swap")
        else:
            add_drop_delta_fn = self._add_drop_delta_for_student
            swap_delta_fn = self._swap_delta_for_student
            event_add = self._compose_event_type("hybrid", objective, submove="drop-add")
            event_swap = self._compose_event_type("hybrid", objective, submove="swap")

        # Ensure we have a draft order to reuse.
        if self._draft_order is None:
            order = self._students[:]
            self._rng.shuffle(order)
            self._draft_order = order[:]

        eps = 1e-12
        move_count = 0
        post_log: list[PostAllocLogRow] = []
        # Iterate up to n passes.
        for offset in range(n):
            iteration = start_iteration + offset
            # Print progress header.
            if self._config.progress:
                print(
                    f"Iter {iteration}/{self._config.total_iters}: HYBRID({objective}) pass",
                    flush=True,
                )
            # Determine turn order for this pass.
            base_order = self._draft_order
            # Snake order based on offset parity.
            turn_order = base_order if offset % 2 == 0 else list(reversed(base_order))
            changed_in_pass = False

            # Iterate over students in turn order.
            for student_id in turn_order:
                # Gather current courses.
                current_courses = sorted(self._alloc_set[student_id])
                # Skip students with no courses.
                if not current_courses:
                    continue
                # Search for best move (add/drop or swap).
                best_delta = 0.0
                best_move: tuple[str, str, str, str, str] | None = None

                # Try each possible target course.
                for target_course in self._courses:
                    # Skip already-allocated courses.
                    if target_course in self._alloc_set[student_id]:
                        continue
                    # Try add/drop if capacity is available.
                    if self._capacity_left[target_course] > 0:
                        # Evaluate all possible drops.
                        for drop_course in current_courses:
                            delta = add_drop_delta_fn(student_id, drop_course, target_course)
                            move_key = ("add_drop", student_id, target_course, "", drop_course)
                            # Check for best move.
                            if delta > best_delta + eps:
                                best_delta = delta
                                best_move = move_key
                            # Tie-breaker for equal deltas.
                            elif (
                                abs(delta - best_delta) <= eps
                                and best_move is not None
                                and move_key < best_move
                            ):
                                best_move = move_key
                        continue

                    holders = [
                        t
                        for t in self._students
                        if t != student_id and target_course in self._alloc_set[t]
                    ]
                    holders.sort()
                    # Try swaps with each holder.
                    for holder_id in holders:
                        # Evaluate all possible drops.
                        for drop_course in current_courses:
                            # Skip if holder already has the drop_course.
                            if drop_course in self._alloc_set[holder_id]:
                                continue
                            # Evaluate swap delta.
                            delta = swap_delta_fn(student_id, drop_course, holder_id, target_course)
                            move_key = ("swap", student_id, target_course, holder_id, drop_course)
                            if delta > best_delta + eps:
                                best_delta = delta
                                best_move = move_key
                            elif (
                                abs(delta - best_delta) <= eps
                                and best_move is not None
                                and move_key < best_move
                            ):
                                best_move = move_key

                if best_move is None or best_delta <= eps:
                    continue

                move_type, s, target_course, holder_id, drop_course = best_move
                check_delta = (
                    self._config.delta_check_every > 0
                    and (move_count + 1) % self._config.delta_check_every == 0
                )
                if check_delta:
                    before = self._measure_objective(objective, s)
                else:
                    before = 0.0

                if move_type == "add_drop":
                    if self._capacity_left[target_course] <= 0:
                        raise AssertionError(f"Hybrid add/drop capacity exhausted for {target_course}")
                    self._replace_course(s, drop_course, target_course)
                    self._assert_student_state(s)
                    if self._config.sanity_checks:
                        self._assert_course_capacity(drop_course)
                        self._assert_course_capacity(target_course)
                    event_type = event_add
                    log_row = PostAllocLogRow(
                        iteration=iteration,
                        event_type=event_type,
                        student_id=s,
                        dropped_courses=(drop_course,),
                        added_courses=(target_course,),
                        swap_student_1=None,
                        swap_course_1=None,
                        swap_student_2=None,
                        swap_course_2=None,
                        delta_utility=best_delta,
                    )
                else:
                    if holder_id == "":
                        raise AssertionError("Hybrid swap missing holder_id")
                    self._swap_courses(s, drop_course, holder_id, target_course)
                    self._assert_swap_invariants(s, drop_course, holder_id, target_course)
                    event_type = event_swap
                    log_row = PostAllocLogRow(
                        iteration=iteration,
                        event_type=event_type,
                        student_id=None,
                        dropped_courses=None,
                        added_courses=None,
                        swap_student_1=s,
                        swap_course_1=drop_course,
                        swap_student_2=holder_id,
                        swap_course_2=target_course,
                        delta_utility=best_delta,
                    )

                if check_delta:
                    after = self._measure_objective(objective, s)
                    actual_delta = after - before
                    if abs(actual_delta - best_delta) > 1e-8:
                        raise AssertionError(
                            "Hybrid delta mismatch "
                            f"(objective={objective}): expected {best_delta:.12f}, "
                            f"got {actual_delta:.12f}"
                        )

                move_count += 1
                changed_in_pass = True

                if self._config.progress:
                    print(
                        f"Iter {iteration}/{self._config.total_iters}: HYBRID({objective}) {event_type} "
                        f"Δ={best_delta:.6f}",
                        flush=True,
                    )

                post_log.append(log_row)

            if not changed_in_pass:
                if self._config.progress:
                    print(
                        f"Iter {iteration}/{self._config.total_iters}: "
                        f"HYBRID({objective}) no-op (early stop)",
                        flush=True,
                    )
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
                break

        return post_log

    def _run_iterative_improvement(self, n: int, *, start_iteration: int) -> list[PostAllocLogRow]:
        return self._run_swap_improvement(n, start_iteration=start_iteration, objective="global")

    def _run_add_drop_improvement(self, n: int, *, start_iteration: int) -> list[PostAllocLogRow]:
        return self._run_drop_add_improvement(n, start_iteration=start_iteration, objective="global")

    def _run_adaptive_improvement(
        self,
        n: int,
        *,
        start_iteration: int,
        objective: str,
    ) -> list[PostAllocLogRow]:
        return self._run_hybrid_improvement(
            n,
            start_iteration=start_iteration,
            objective=objective,
        )

    # ---- Metrics -------------------------------------------------------

    def _envy_ef1_metrics(self) -> dict[str, float]:
        """Compute envy-pair and EF1-violation shares for base/friend/total values."""

        eps = 1e-9
        students = self._students
        n_students = len(students)
        total_pairs = n_students * (n_students - 1) if n_students > 1 else 0
        envy_pairs = {key: 0 for key in ("base", "friend", "total")}
        ef1_students = {key: 0 for key in ("base", "friend", "total")}

        def course_value(student_id: str, course_id: str, notion: str) -> float:
            base = self._base_utility(student_id, course_id)
            friend = 0.0
            for friend_id in self._friends_by_sc.get((student_id, course_id), ()):
                if course_id in self._alloc_set[friend_id]:
                    friend += self._friend_preference_utility(
                        student_id, friend_id, course_id
                    )
            if notion == "base":
                return base
            if notion == "friend":
                return friend
            lambda_ = self._lambda_by_student.get(student_id, self._DEFAULT_LAMBDA)
            return (
                (1.0 - lambda_) * base
                + lambda_ * friend / self._max_friend_bonus(student_id)
            )

        for student_id in students:
            has_violation = {key: False for key in envy_pairs}
            own = {
                notion: sum(
                    course_value(student_id, course_id, notion)
                    for course_id in self._alloc_set[student_id]
                )
                for notion in envy_pairs
            }
            for other_id in students:
                if other_id == student_id or not self._alloc_set[other_id]:
                    continue
                for notion in envy_pairs:
                    values = [
                        course_value(student_id, course_id, notion)
                        for course_id in self._alloc_set[other_id]
                    ]
                    other = sum(values)
                    if other > own[notion] + eps:
                        envy_pairs[notion] += 1
                        if other - max(values) > own[notion] + eps:
                            has_violation[notion] = True
            for notion, violated in has_violation.items():
                if violated:
                    ef1_students[notion] += 1

        result: dict[str, float] = {}
        for notion in envy_pairs:
            result[f"envy_pairs_share_{notion}"] = (
                envy_pairs[notion] / total_pairs if total_pairs else 0.0
            )
            result[f"ef1_violation_share_{notion}"] = (
                ef1_students[notion] / n_students if n_students else 0.0
            )
        return result

    def _compute_metrics(self) -> tuple[RunSummary, ExtendedMetrics]:
        """Compute summary + extended metrics from the final allocation."""

        per_student_total: list[float] = []
        per_student_base: list[float] = []
        per_student_friend: list[float] = []
        per_student_friend_norm: list[float] = []
        per_student_max_base: list[float] = []
        per_student_max_total: list[float] = []
        per_student_max_friend: list[float] = []
        per_student_max_friend_norm: list[float] = []
        per_student_max_overlaps: list[int] = []

        for student_id in self._students:
            base_sum, friend_sum = self._student_welfare_components(student_id)
            friend_norm_sum = 0.0
            friend_max = self._max_friend_bonus(student_id)
            for course_id in sorted(self._alloc_set[student_id]):
                course_friend_sum = 0.0
                for friend_id in self._friends_list.get(student_id, ()):
                    if course_id in self._alloc_set[friend_id]:
                        course_friend_sum += self._friend_preference_utility(
                            student_id,
                            friend_id,
                            course_id,
                        )
                friend_norm_sum += course_friend_sum / friend_max

            total = self._student_welfare(student_id)
            per_student_base.append(base_sum)
            per_student_friend.append(friend_sum)
            per_student_friend_norm.append(friend_norm_sum)
            per_student_total.append(total)
            per_student_max_base.append(self._max_possible_base(student_id))
            per_student_max_total.append(self._max_possible_total_upper(student_id))
            per_student_max_friend.append(self._max_possible_friend_upper(student_id))
            friend_norm_upper_values = [
                self._friend_sum_by_student_course.get((student_id, course_id), 0.0) / friend_max
                for course_id in self._courses
            ]
            friend_norm_upper_values.sort(reverse=True)
            per_student_max_friend_norm.append(
                sum(friend_norm_upper_values[: self._config.max_courses])
            )
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
            per_student_friend_norm=per_student_friend_norm,
            per_student_total_norm=per_student_total_norm,
            per_student_base_norm=per_student_base_norm,
            per_student_max_total=per_student_max_total,
            per_student_max_base=per_student_max_base,
            per_student_max_friend=per_student_max_friend,
            per_student_max_friend_norm=per_student_max_friend_norm,
            per_student_max_overlaps=per_student_max_overlaps,
        )
        return summary, metrics

    def _compute_extended_metrics(
        self,
        *,
        per_student_total: list[float],
        per_student_base: list[float],
        per_student_friend: list[float],
        per_student_friend_norm: list[float],
        per_student_total_norm: list[float],
        per_student_base_norm: list[float],
        per_student_max_total: list[float],
        per_student_max_base: list[float],
        per_student_max_friend: list[float],
        per_student_max_friend_norm: list[float],
        per_student_max_overlaps: list[int],
    ) -> ExtendedMetrics:
        n_students = len(self._students)
        total_base = sum(per_student_base)
        total_friend = sum(per_student_friend)
        total_friend_norm = sum(per_student_friend_norm)
        total_max_base = sum(per_student_max_base)
        total_max_total = sum(per_student_max_total)
        total_max_friend = sum(per_student_max_friend)
        total_max_friend_norm = sum(per_student_max_friend_norm)

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
        assigned_base_values: list[float] = []
        assigned_friend_norm_values: list[float] = []
        assigned_friend_norm_base_ratios: list[float] = []
        top1 = 0
        top3 = 0
        assignments_with_zero_friend_norm = 0
        for student_id in self._students:
            friend_max = self._max_friend_bonus(student_id)
            for course_id in self._alloc_set[student_id]:
                base = self._base_utility(student_id, course_id)
                friend_raw = 0.0
                for friend_id in self._friends_list.get(student_id, ()):
                    if course_id in self._alloc_set[friend_id]:
                        friend_raw += self._friend_preference_utility(student_id, friend_id, course_id)
                friend_norm = friend_raw / friend_max
                assigned_base_values.append(base)
                assigned_friend_norm_values.append(friend_norm)
                if base > 0.0:
                    assigned_friend_norm_base_ratios.append(friend_norm / base)
                if friend_norm <= 1e-12:
                    assignments_with_zero_friend_norm += 1

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
        assigned_base_sorted = sorted(assigned_base_values)
        assigned_friend_norm_sorted = sorted(assigned_friend_norm_values)
        assigned_ratio_sorted = sorted(assigned_friend_norm_base_ratios)
        assignments_count = len(assigned_base_values)

        def _median(values: list[float]) -> float:
            if not values:
                return 0.0
            mid = len(values) // 2
            if len(values) % 2 == 1:
                return values[mid]
            return (values[mid - 1] + values[mid]) / 2.0

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
        total_utility_norm = total_utility / total_max_total if total_max_total > 0.0 else 0.0
        per_student_friend_opportunity_norm = [
            (u / max_u if max_u > 0.0 else 1.0)
            for u, max_u in zip(per_student_friend_norm, per_student_max_friend_norm)
        ]
        students_no_friend_bonus_opportunity = sum(
            1 for max_u in per_student_max_friend_norm if max_u <= 0.0
        )
        students_no_observed_friend_bonus = sum(
            1 for u in per_student_friend_norm if u <= 1e-12
        )

        sorted_total = sorted(per_student_total)

        def _percentile(p: float) -> float:
            if not sorted_total:
                return 0.0
            idx = int(round((len(sorted_total) - 1) * p))
            return sorted_total[min(max(idx, 0), len(sorted_total) - 1)]

        def _geomean(values: list[float]) -> float:
            if not values or any(value <= 0.0 for value in values):
                return 0.0
            return math.exp(sum(math.log(value) for value in values) / len(values))

        envy_metrics = self._envy_ef1_metrics()

        metrics = {
            "total_utility": total_utility,
            "total_utility_norm": total_utility_norm,
            "total_base_utility": total_base,
            "total_friend_utility": total_friend,
            "total_friend_utility_raw": total_friend,
            "total_friend_utility_norm": total_friend_norm,
            "avg_utility_per_student": avg_utility,
            "egalitarian_welfare": min(per_student_total) if per_student_total else 0.0,
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
            "mean_base_assigned": (
                sum(assigned_base_values) / assignments_count if assignments_count else 0.0
            ),
            "median_base_assigned": _median(assigned_base_sorted),
            "min_base_assigned": min(assigned_base_values) if assigned_base_values else 0.0,
            "max_base_assigned": max(assigned_base_values) if assigned_base_values else 0.0,
            "mean_friend_norm_assigned": (
                sum(assigned_friend_norm_values) / assignments_count if assignments_count else 0.0
            ),
            "median_friend_norm_assigned": _median(assigned_friend_norm_sorted),
            "min_friend_norm_assigned": (
                min(assigned_friend_norm_values) if assigned_friend_norm_values else 0.0
            ),
            "max_friend_norm_assigned": (
                max(assigned_friend_norm_values) if assigned_friend_norm_values else 0.0
            ),
            "friend_norm_base_ratio_mean": (
                sum(assigned_friend_norm_base_ratios) / len(assigned_friend_norm_base_ratios)
                if assigned_friend_norm_base_ratios
                else 0.0
            ),
            "friend_norm_base_ratio_median": _median(assigned_ratio_sorted),
            "friend_norm_base_ratio_max": (
                max(assigned_friend_norm_base_ratios) if assigned_friend_norm_base_ratios else 0.0
            ),
            "share_assignments_friend_norm_zero": (
                assignments_with_zero_friend_norm / assignments_count if assignments_count else 0.0
            ),
            "share_students_no_friend_bonus_opportunity": (
                students_no_friend_bonus_opportunity / n_students if n_students else 0.0
            ),
            "share_students_no_observed_friend_bonus": (
                students_no_observed_friend_bonus / n_students if n_students else 0.0
            ),
            "avg_friend_overlaps_per_student": avg_friend_overlaps,
            "share_students_with_any_friend_overlap": share_students_with_overlap,
            "gini_total_raw": compute_gini_index(per_student_total),
            "gini_total_norm": compute_gini_index(per_student_total_norm),
            "gini_base_raw": compute_gini_index(per_student_base),
            "gini_base_norm": compute_gini_index(per_student_base_norm),
            "gini_friend_raw": compute_gini_index(per_student_friend),
            "gini_friend_norm": compute_gini_index(per_student_friend_norm),
            "gini_friend_opportunity_norm": compute_gini_index(per_student_friend_opportunity_norm),
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
        max_friend_norm_base_ratio = max(0.0, max_course_rank - 1.0)
        total_seats = float(len(self._courses) * self._config.default_capacity)

        maxima = {
            "total_utility": total_max_total,
            "total_utility_norm": 1.0,
            "total_base_utility": total_max_base,
            "total_friend_utility": total_max_friend,
            "total_friend_utility_raw": total_max_friend,
            "total_friend_utility_norm": total_max_friend_norm,
            "avg_utility_per_student": (total_max_total / n_students if n_students else 0.0),
            "egalitarian_welfare": (
                min(per_student_max_total) if per_student_max_total else 0.0
            ),
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
            "mean_base_assigned": 1.0,
            "median_base_assigned": 1.0,
            "min_base_assigned": 1.0,
            "max_base_assigned": 1.0,
            "mean_friend_norm_assigned": 1.0,
            "median_friend_norm_assigned": 1.0,
            "min_friend_norm_assigned": 1.0,
            "max_friend_norm_assigned": 1.0,
            "friend_norm_base_ratio_mean": max_friend_norm_base_ratio,
            "friend_norm_base_ratio_median": max_friend_norm_base_ratio,
            "friend_norm_base_ratio_max": max_friend_norm_base_ratio,
            "share_assignments_friend_norm_zero": 1.0,
            "share_students_no_friend_bonus_opportunity": 1.0,
            "share_students_no_observed_friend_bonus": 1.0,
            "avg_friend_overlaps_per_student": avg_overlaps_max,
            "share_students_with_any_friend_overlap": share_possible_overlap,
            "gini_total_raw": 1.0,
            "gini_total_norm": 1.0,
            "gini_base_raw": 1.0,
            "gini_base_norm": 1.0,
            "gini_friend_raw": 1.0,
            "gini_friend_norm": 1.0,
            "gini_friend_opportunity_norm": 1.0,
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
