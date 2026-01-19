import csv
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.append(str(Path(__file__).resolve().parents[1]))

from HBS.hbs_api import run_hbs_social
from HBS.hbs_io import (
    _write_allocation_csv,
    _write_post_alloc_csv,
    _write_summary_csv,
)


def _write_table_1(path: Path) -> None:
    rows = [
        ("S1", "C1", 5, 1),
        ("S1", "C2", 1, 2),
        ("S2", "C1", 1, 2),
        ("S2", "C2", 5, 1),
        ("S3", "C1", 4, 1),
        ("S3", "C2", 2, 2),
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["StudentID", "CourseID", "Score", "Position"])
        writer.writerows(rows)


def _write_table_2(path: Path) -> None:
    rows = [
        ("S1", "S2", "C1", 1, 5),
        ("S1", "S2", "C2", 1, 5),
        ("S2", "S3", "C1", 1, 5),
        ("S2", "S3", "C2", 1, 5),
        ("S3", "S1", "C1", 1, 5),
        ("S3", "S1", "C2", 1, 5),
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["StudentID_A", "StudentID_B", "CourseID", "Position", "Score"])
        writer.writerows(rows)


def _run_once(workdir: Path) -> tuple[str, str]:
    csv_a = workdir / "table1.csv"
    csv_b = workdir / "table2.csv"
    allocation = workdir / "allocation.csv"
    post_alloc = workdir / "post_allocation.csv"
    summary = workdir / "summary.csv"

    _write_table_1(csv_a)
    _write_table_2(csv_b)

    result = run_hbs_social(
        csv_a,
        csv_b,
        cap_default=2,
        b=2,
        draft_rounds=2,
        post_iters=1,
        improve_mode="add-drop",
        seed=42,
    )

    _write_allocation_csv(allocation, pick_log=result.pick_log)
    _write_post_alloc_csv(post_alloc, post_log=result.post_log)
    _write_summary_csv(
        summary,
        seed=42,
        cap_default=2,
        b=2,
        draft_rounds=2,
        post_iters=1,
        summary=result.summary,
    )

    return allocation.read_text(encoding="utf-8"), summary.read_text(encoding="utf-8")


class TestReproducibility(unittest.TestCase):
    def test_same_seed_is_reproducible(self) -> None:
        with TemporaryDirectory() as d1, TemporaryDirectory() as d2:
            alloc1, summary1 = _run_once(Path(d1))
            alloc2, summary2 = _run_once(Path(d2))
        self.assertEqual(alloc1, alloc2)
        self.assertEqual(summary1, summary2)


if __name__ == "__main__":
    unittest.main()
