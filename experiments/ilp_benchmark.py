#!/usr/bin/env python3
"""
ILP benchmark for the course allocation with friendships problem.

Solves the allocation to proven optimality with CBC (via PuLP), using exactly the
same utility model as the draft engine:

    W = sum_s [ (1 - lambda_s) * sum_c Base(s,c) * x[s,c]
                + (lambda_s / MaxFriendBonus) * sum_{f in F(s,c)} Pref(s,f,c) * y[s,f,c] ]

The quadratic friendship term x[s,c] * x[f,c] is linearized with overlap variables:

    y[s,f,c] <= x[s,c],   y[s,f,c] <= x[f,c]

Objectives:
    utilitarian - maximize total welfare W (upper bound / optimality gap for heuristics)
    egalitarian - maximize the welfare of the worst-off student (max-min)

Requires: pip install pulp
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pulp

from HBS.hbs_config import _RunConfig
from HBS.hbs_engine import _HbsSocialDraftEngine
from HBS.hbs_io import _read_table_1, _read_table_2, _read_table_lambda


def _build_engine(args: argparse.Namespace) -> _HbsSocialDraftEngine:
    """Build the draft engine only to reuse its precomputed utility model."""

    rows_a = _read_table_1(args.csv_a)
    rows_b = _read_table_2(args.csv_b)
    student_lambdas = None
    if args.csv_lambda is not None:
        student_lambdas = {
            r.student_id: r.lambda_friend for r in _read_table_lambda(args.csv_lambda)
        }
    config = _RunConfig(
        default_capacity=args.cap_default,
        max_courses=args.b,
        draft_rounds=0,
        post_iters=0,
        total_iters=0,
        improve_mode="swap",
        progress=False,
        seed=0,
        sanity_checks=False,
        delta_check_every=0,
    )
    return _HbsSocialDraftEngine(
        individual_prefs=rows_a,
        pair_prefs=rows_b,
        student_lambdas=student_lambdas,
        config=config,
    )


def solve(args: argparse.Namespace) -> int:
    engine = _build_engine(args)
    students = engine._students
    courses = engine._courses
    cap = args.cap_default
    b = args.b
    norm = engine._max_friend_bonus if engine._max_friend_bonus > 0 else 1.0

    problem = pulp.LpProblem("course_allocation_friendships", pulp.LpMaximize)

    x = {
        (s, c): pulp.LpVariable(f"x_{s}_{c}", cat="Binary")
        for s in students
        for c in courses
    }
    # Overlap variables only for listed (s, f, c) friend preferences.
    y: dict[tuple[str, str, str], pulp.LpVariable] = {}
    for (s, c), friends in engine._friends_by_sc.items():
        for f in friends:
            y[(s, f, c)] = pulp.LpVariable(f"y_{s}_{f}_{c}", lowBound=0.0, upBound=1.0)

    # Per-student welfare expression.
    welfare = {}
    for s in students:
        lambda_s = engine._lambda_by_student[s]
        terms = []
        for c in courses:
            base = engine._base_utility(s, c)
            if base != 0.0:
                terms.append((1.0 - lambda_s) * base * x[(s, c)])
            for f in engine._friends_by_sc.get((s, c), ()):
                pref = engine._friend_preference_utility(s, f, c)
                if pref != 0.0:
                    terms.append((lambda_s / norm) * pref * y[(s, f, c)])
        welfare[s] = pulp.lpSum(terms)

    # Constraints.
    for s in students:
        problem += pulp.lpSum(x[(s, c)] for c in courses) <= b, f"courses_per_student_{s}"
    for c in courses:
        problem += pulp.lpSum(x[(s, c)] for s in students) <= cap, f"capacity_{c}"
    for (s, f, c), var in y.items():
        problem += var <= x[(s, c)], f"y_le_self_{s}_{f}_{c}"
        problem += var <= x[(f, c)], f"y_le_friend_{s}_{f}_{c}"

    if args.objective == "utilitarian":
        problem += pulp.lpSum(welfare[s] for s in students)
    else:  # egalitarian (max-min)
        z = pulp.LpVariable("min_welfare", lowBound=0.0)
        for s in students:
            problem += welfare[s] >= z, f"minw_{s}"
        problem += z

    t0 = time.time()
    status = problem.solve(pulp.PULP_CBC_CMD(msg=args.verbose, timeLimit=args.time_limit))
    elapsed = time.time() - t0

    per_student = [pulp.value(welfare[s]) or 0.0 for s in students]
    total = sum(per_student)
    print(f"status:        {pulp.LpStatus[status]}")
    print(f"objective:     {args.objective}")
    print(f"solve_time_s:  {elapsed:.1f}")
    print(f"total_utility: {total:.4f}")
    print(f"egalitarian:   {min(per_student):.4f}")
    if args.out_csv:
        import csv

        with open(args.out_csv, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["StudentID", "CourseID"])
            for s in students:
                for c in courses:
                    if (pulp.value(x[(s, c)]) or 0.0) > 0.5:
                        writer.writerow([s, c])
        print(f"allocation csv: {args.out_csv}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--csv-a", type=Path, required=True)
    p.add_argument("--csv-b", type=Path, required=True)
    p.add_argument("--csv-lambda", type=Path, default=None)
    p.add_argument("--cap-default", type=int, required=True)
    p.add_argument("--b", type=int, required=True)
    p.add_argument("--objective", choices=["utilitarian", "egalitarian"], default="utilitarian")
    p.add_argument("--time-limit", type=int, default=300, help="CBC time limit, seconds")
    p.add_argument("--out-csv", type=Path, default=None, help="Write optimal allocation CSV")
    p.add_argument("--verbose", action="store_true")
    return solve(p.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
