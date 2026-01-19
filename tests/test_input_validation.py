import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.append(str(Path(__file__).resolve().parents[1]))

from HBS.hbs_api import run_hbs_social


def _write_table_1(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        f.write("StudentID,CourseID,Score,Position\n")
        f.write("S1,C1,5,1\n")


def _write_table_2(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        f.write("StudentID_A,StudentID_B,CourseID,Position,Score\n")


def _write_table_lambda(path: Path, value: float) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        f.write("StudentID,LambdaFriend\n")
        f.write(f"S1,{value}\n")


class TestInputValidation(unittest.TestCase):
    def test_draft_rounds_exceed_b(self) -> None:
        with TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            csv_a = workdir / "table1.csv"
            csv_b = workdir / "table2.csv"
            _write_table_1(csv_a)
            _write_table_2(csv_b)

            with self.assertRaises(ValueError):
                run_hbs_social(
                    csv_a,
                    csv_b,
                    cap_default=1,
                    b=1,
                    seed=1,
                    draft_rounds=2,
                    post_iters=0,
                    improve_mode="swap",
                )

    def test_lambda_out_of_range(self) -> None:
        with TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            csv_a = workdir / "table1.csv"
            csv_b = workdir / "table2.csv"
            csv_lambda = workdir / "table3.csv"
            _write_table_1(csv_a)
            _write_table_2(csv_b)
            _write_table_lambda(csv_lambda, 1.5)

            with self.assertRaises(ValueError):
                run_hbs_social(
                    csv_a,
                    csv_b,
                    csv_lambda=csv_lambda,
                    cap_default=1,
                    b=1,
                    seed=1,
                    draft_rounds=1,
                    post_iters=0,
                    improve_mode="swap",
                )


if __name__ == "__main__":
    unittest.main()
