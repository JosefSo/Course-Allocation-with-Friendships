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
) -> list[Table2Row]:
    """
    Генерирует Таблицу 2 как "топ-3 друзей" для каждого (StudentID_A, CourseID).

    Важно: в Таблице 2 нет Score — Position уже является приоритетом (рангом) выбора друга.

    Правила:
      - Для каждого (StudentID_A, CourseID) генерируем до top_k строк (ровно top_k, если хватает кандидатов).
      - StudentID_A != StudentID_B (self-pairs запрещены).
      - Внутри группы (StudentID_A, CourseID): Position уникален (1..top_k), StudentID_B уникален.
    """
    rows: list[Table2Row] = []
    for course_id in course_ids:
        for student_id_a in student_ids:
            candidates = [b for b in student_ids if b != student_id_a]
            if not candidates or top_k <= 0:
                continue
            chosen = rng.sample(candidates, k=min(top_k, len(candidates)))
            for position, student_id_b in enumerate(chosen, start=1):
                rows.append(
                    Table2Row(
                        student_id_a=student_id_a,
                        student_id_b=student_id_b,
                        course_id=course_id,
                        position=position,
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


def _write_csv_table_1(path: Path, rows: Sequence[Table1Row]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["StudentID", "CourseID", "Score", "Position"])
        for r in rows:
            writer.writerow([r.student_id, r.course_id, r.score, r.position])


def _write_csv_table_2(path: Path, rows: Sequence[Table2Row]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["StudentID_A", "StudentID_B", "CourseID", "Position"])
        for r in rows:
            writer.writerow([r.student_id_a, r.student_id_b, r.course_id, r.position])


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
            "2) Топ-3 друзей на курс (StudentID_A, StudentID_B, CourseID, Position=1..3)\n"
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
    )
    table3 = generate_table_3(
        student_ids,
        lambda_default=args.lambda_default,
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
