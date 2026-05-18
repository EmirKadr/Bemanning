from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class SimpleTable:
    columns: list[str]
    rows: list[list[object]]

    @property
    def empty(self) -> bool:
        return len(self.rows) == 0

    def __len__(self) -> int:
        return len(self.rows)

    def preview_rows(self, limit: int) -> list[list[object]]:
        return self.rows[:limit]

    def column_values(self, index: int) -> list[object]:
        return [row[index] if index < len(row) else "" for row in self.rows]

    def write_csv(self, path: str | Path, *, include_header: bool = True) -> None:
        with Path(path).open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            if include_header:
                writer.writerow(self.columns)
            writer.writerows(self.rows)


def is_simple_table(value: object) -> bool:
    return isinstance(value, SimpleTable)


def rows_to_simple_table(columns: Iterable[str], rows: Iterable[Iterable[object]]) -> SimpleTable:
    return SimpleTable([str(column) for column in columns], [list(row) for row in rows])
