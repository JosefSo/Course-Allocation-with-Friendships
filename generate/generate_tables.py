#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class Table1Row:
    student_id: str
    course_id: str
    score: int
    position: int


@dataclass(frozen=True)
class Table2Row:
    student_id_a: str
    student_id_b: str
    course_id: str
    position: int
    score: int


@dataclass(frozen=True)
class Table3Row:
    student_id: str
    lambda_friend: float


def _prompt_positive_int(prompt: str) -> int:
    while True:
        raw = input(prompt).strip()
        try:
            value = int(raw)
        except ValueError:
            print("Введите целое число.")
            continue
        if value <= 0:
            print("Число должно быть > 0.")
            continue
        return value


def _soft_score_weights(score_min: int, score_max: int) -> list[int]:
    """
    Делает распределение "мягким": больше вероятности у середины шкалы.
    Для шкалы 1..5 получится [1, 3, 5, 3, 1].
    """
    values = list(range(score_min, score_max + 1))
    mid = (score_min + score_max) / 2.0
    weights: list[int] = []
    for v in values:
        dist = abs(v - mid)
        # Чем ближе к середине, тем больше вес.
        # Добавляем 1, чтобы вес был хотя бы 1.
        weights.append(int(round((score_max - score_min) - dist)) + 1)
    # Подстраховка: если из-за округлений где-то вышел 0.
    return [max(1, w) for w in weights]


def _generate_scores(
    rng: random.Random,
    count: int,
    *,
    score_min: int,
    score_max: int,
) -> list[int]:
    values = list(range(score_min, score_max + 1))
    weights = _soft_score_weights(score_min, score_max)
    return [rng.choices(values, weights=weights, k=1)[0] for _ in range(count)]


def _rank_positions(
    rng: random.Random,
    scores: Sequence[int],
    *,
    swap_prob: float = 0.0,
) -> list[int]:
    """
    Способ A из how_to_random.txt:
    - сначала генерируем Score
    - потом получаем Position сортировкой (по убыванию)
    Тай-брейк: небольшой шум.
    Опционально (Способ B): с вероятностью swap_prob делаем swap соседей.
    """
    noise = [rng.random() * 0.01 for _ in scores]
    ranked_indices = sorted(
        range(len(scores)),
        key=lambda i: (scores[i], noise[i]),
        reverse=True,
    )

    if swap_prob > 0:
        i = 0
        while i < len(ranked_indices) - 1:
            if rng.random() < swap_prob:
                ranked_indices[i], ranked_indices[i + 1] = (
                    ranked_indices[i + 1],
                    ranked_indices[i],
                )
                i += 2
            else:
                i += 1

    positions = [0] * len(scores)
    for pos, idx in enumerate(ranked_indices, start=1):
        positions[idx] = pos
    return positions


def generate_table_1(
    student_ids: Sequence[str],
    course_ids: Sequence[str],
    rng: random.Random,
    *,
    score_min: int,
    score_max: int,
    swap_prob: float,
) -> list[Table1Row]:
    rows: list[Table1Row] = []
    for student_id in student_ids:
        scores = _generate_scores(
            rng,
            len(course_ids),
            score_min=score_min,
            score_max=score_max,
        )
        positions = _rank_positions(rng, scores, swap_prob=swap_prob)
        for course_id, score, position in zip(course_ids, scores, positions):
            rows.append(
                Table1Row(
                    student_id=student_id,
                    course_id=course_id,
                    score=score,
                    position=position,
                )
            )
    return rows


def generate_table_2(
    student_ids: Sequence[str],
    course_ids: Sequence[str],
    rng: random.Random,
    *,
    top_k: int = 3,
    score_min: int,
    score_max: int,
    score_mode: str = "score_first",
    swap_prob: float = 0.0,
) -> list[Table2Row]:
    """
    Генерирует Таблицу 2 как "топ-3 друзей" для каждого (StudentID_A, CourseID).

    Важно: в Таблице 2 есть Score (ties допустимы), а Position задается как строгий ранг.

    Правила:
      - Для каждого (StudentID_A, CourseID) генерируем до top_k строк (ровно top_k, если хватает кандидатов).
      - StudentID_A != StudentID_B (self-pairs запрещены).
      - Внутри группы (StudentID_A, CourseID): Position уникален (1..top_k), StudentID_B уникален.
      - Score в диапазоне [score_min, score_max].
    """
    rows: list[Table2Row] = []
    for course_id in course_ids:
        for student_id_a in student_ids:
            candidates = [b for b in student_ids if b != student_id_a]
            if not candidates or top_k <= 0:
                continue
            k = min(top_k, len(candidates))
            chosen = rng.sample(candidates, k=k)

            if score_mode == "score_first":
                scores = _generate_scores(
                    rng,
                    k,
                    score_min=score_min,
                    score_max=score_max,
                )
                positions = _rank_positions(rng, scores, swap_prob=swap_prob)
            elif score_mode == "position_first":
                scores = _generate_scores(
                    rng,
                    k,
                    score_min=score_min,
                    score_max=score_max,
                )
                scores = sorted(scores, reverse=True)
                positions = list(range(1, k + 1))
            else:
                raise ValueError(f"Unknown score_mode: {score_mode}")

            for student_id_b, score, position in zip(chosen, scores, positions):
                rows.append(
                    Table2Row(
                        student_id_a=student_id_a,
                        student_id_b=student_id_b,
                        course_id=course_id,
                        position=position,
                        score=score,
                    )
                )
    return rows


def generate_table_3(
    student_ids: Sequence[str],
    *,
    lambda_default: float = 0.5,
) -> list[Table3Row]:
    """
    Генерирует Таблицу 3 с per-student lambda (важность friend bonus).
    """
    return [
        Table3Row(student_id=student_id, lambda_friend=lambda_default)
        for student_id in student_ids
    ]


def _validate_table_1(
    rows: Sequence[Table1Row],
    *,
    n_courses: int,
    score_min: int,
    score_max: int,
) -> None:
    seen: set[tuple[str, str]] = set()
    positions_by_student: dict[str, set[int]] = {}
    for r in rows:
        key = (r.student_id, r.course_id)
        if key in seen:
            raise ValueError(f"Table1 duplicate key: {key}")
        seen.add(key)
        if not (score_min <= r.score <= score_max):
            raise ValueError(f"Table1 score out of range: {r.score} for {key}")
        positions_by_student.setdefault(r.student_id, set()).add(r.position)

    expected_positions = set(range(1, n_courses + 1))
    for student_id, positions in positions_by_student.items():
        if positions != expected_positions:
            raise ValueError(f"Table1 positions invalid for {student_id}: {sorted(positions)}")


def _validate_table_2(
    rows: Sequence[Table2Row],
    *,
    top_k: int,
    score_min: int,
    score_max: int,
) -> None:
    seen: set[tuple[str, str, str]] = set()
    group_counts: dict[tuple[str, str], int] = {}
    positions_by_group: dict[tuple[str, str], set[int]] = {}
    friends_by_group: dict[tuple[str, str], set[str]] = {}

    for r in rows:
        if r.student_id_a == r.student_id_b:
            raise ValueError(f"Table2 self-pair found: {r.student_id_a}")
        key = (r.student_id_a, r.student_id_b, r.course_id)
        if key in seen:
            raise ValueError(f"Table2 duplicate key: {key}")
        seen.add(key)
        if not (1 <= r.position <= top_k):
            raise ValueError(f"Table2 position out of range: {r.position} for {key}")
        if not (score_min <= r.score <= score_max):
            raise ValueError(f"Table2 score out of range: {r.score} for {key}")

        group = (r.student_id_a, r.course_id)
        group_counts[group] = group_counts.get(group, 0) + 1
        positions_by_group.setdefault(group, set()).add(r.position)
        friends_by_group.setdefault(group, set()).add(r.student_id_b)

    for group, count in group_counts.items():
        positions = positions_by_group.get(group, set())
        friends = friends_by_group.get(group, set())
        if count != len(positions):
            raise ValueError(f"Table2 duplicate positions in group: {group}")
        if count != len(friends):
            raise ValueError(f"Table2 duplicate friends in group: {group}")
        if positions:
            max_pos = max(positions)
            expected = set(range(1, max_pos + 1))
            if positions != expected:
                raise ValueError(f"Table2 positions not contiguous in group: {group}")


def _write_csv_table_1(path: Path, rows: Sequence[Table1Row]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["StudentID", "CourseID", "Score", "Position"])
        for r in rows:
            writer.writerow([r.student_id, r.course_id, r.score, r.position])


def _write_csv_table_2(path: Path, rows: Sequence[Table2Row]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["StudentID_A", "StudentID_B", "CourseID", "Position", "Score"])
        for r in rows:
            writer.writerow([r.student_id_a, r.student_id_b, r.course_id, r.position, r.score])


def _write_csv_table_3(path: Path, rows: Sequence[Table3Row]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["StudentID", "LambdaFriend"])
        for r in rows:
            writer.writerow([r.student_id, f"{r.lambda_friend:.3f}"])


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Генератор двух CSV таблиц:\n"
            "1) Индивидуальные предпочтения (StudentID, CourseID, Score, Position)\n"
            "2) Топ-K друзей на курс (StudentID_A, StudentID_B, CourseID, Position=1..K, Score)\n"
            "3) Per-student lambda (StudentID, LambdaFriend)\n"
        )
    )
    p.add_argument("--students", type=int, help="Количество студентов (N)")
    p.add_argument("--courses", type=int, help="Количество курсов (K)")
    p.add_argument("--seed", type=int, default=None, help="Seed для воспроизводимости")
    p.add_argument("--score-min", type=int, default=1, help="Минимальный Score (по умолчанию 1)")
    p.add_argument("--score-max", type=int, default=5, help="Максимальный Score (по умолчанию 5)")
    p.add_argument(
        "--swap-prob",
        type=float,
        default=0.0,
        help="Вероятность swap соседних позиций (0..1); 0 = Способ A, >0 = Способ B",
    )
    p.add_argument(
        "--friend-top-k",
        type=int,
        default=3,
        help="Размер списка друзей (top-K) в Таблице 2",
    )
    p.add_argument(
        "--friend-score-min",
        type=int,
        default=None,
        help="Минимальный Score для друзей (по умолчанию = --score-min)",
    )
    p.add_argument(
        "--friend-score-max",
        type=int,
        default=None,
        help="Максимальный Score для друзей (по умолчанию = --score-max)",
    )
    p.add_argument(
        "--friend-score-mode",
        choices=["score_first", "position_first"],
        default="score_first",
        help="Режим связки Score/Position для друзей",
    )
    p.add_argument(
        "--friend-swap-prob",
        type=float,
        default=0.0,
        help="Вероятность swap соседних позиций в friend-ранжировании (0..1)",
    )
    p.add_argument(
        "--out1",
        type=Path,
        default=Path("tables/table1_individual.csv"),
        help="Путь для CSV Таблицы 1",
    )
    p.add_argument(
        "--out2",
        type=Path,
        default=Path("tables/table2_pair.csv"),
        help="Путь для CSV Таблицы 2",
    )
    p.add_argument(
        "--lambda-default",
        type=float,
        default=0.5,
        help="Lambda по умолчанию для всех студентов (0..1)",
    )
    p.add_argument(
        "--out3",
        type=Path,
        default=Path("tables/table3_lambda.csv"),
        help="Путь для CSV Таблицы 3 (lambda)",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()

    n_students = args.students if args.students is not None else _prompt_positive_int("Количество студентов (N): ")
    n_courses = args.courses if args.courses is not None else _prompt_positive_int("Количество курсов (K): ")

    if args.score_min >= args.score_max:
        raise SystemExit("--score-min должен быть меньше --score-max")
    if not (0.0 <= args.swap_prob <= 1.0):
        raise SystemExit("--swap-prob должен быть в диапазоне 0..1")
    if not (0.0 <= args.lambda_default <= 1.0):
        raise SystemExit("--lambda-default должен быть в диапазоне 0..1")
    if args.friend_top_k <= 0:
        raise SystemExit("--friend-top-k должен быть > 0")
    friend_score_min = args.friend_score_min if args.friend_score_min is not None else args.score_min
    friend_score_max = args.friend_score_max if args.friend_score_max is not None else args.score_max
    if friend_score_min >= friend_score_max:
        raise SystemExit("--friend-score-min должен быть меньше --friend-score-max")
    if not (0.0 <= args.friend_swap_prob <= 1.0):
        raise SystemExit("--friend-swap-prob должен быть в диапазоне 0..1")

    student_ids = [f"S{i}" for i in range(1, n_students + 1)]
    course_ids = [f"C{i}" for i in range(1, n_courses + 1)]

    rng = random.Random(args.seed)

    table1 = generate_table_1(
        student_ids,
        course_ids,
        rng,
        score_min=args.score_min,
        score_max=args.score_max,
        swap_prob=args.swap_prob,
    )
    table2 = generate_table_2(
        student_ids,
        course_ids,
        rng,
        top_k=args.friend_top_k,
        score_min=friend_score_min,
        score_max=friend_score_max,
        score_mode=args.friend_score_mode,
        swap_prob=args.friend_swap_prob,
    )
    table3 = generate_table_3(
        student_ids,
        lambda_default=args.lambda_default,
    )

    _validate_table_1(
        table1,
        n_courses=len(course_ids),
        score_min=args.score_min,
        score_max=args.score_max,
    )
    _validate_table_2(
        table2,
        top_k=args.friend_top_k,
        score_min=friend_score_min,
        score_max=friend_score_max,
    )

    _write_csv_table_1(args.out1, table1)
    _write_csv_table_2(args.out2, table2)
    _write_csv_table_3(args.out3, table3)

    print(f"Готово: {args.out1} ({len(table1)} строк)")
    print(f"Готово: {args.out2} ({len(table2)} строк)")
    print(f"Готово: {args.out3} ({len(table3)} строк)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
