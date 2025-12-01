# -*- coding: utf-8 -*-
"""Общий вспомогательный класс пагинации для шаблонов Flask.

Интерфейс совместим с типичными шаблонами:
.page, .per_page, .total, .pages, .has_prev, .has_next, .prev_num, .next_num, .iter_pages(...)
"""
from math import ceil


class Pagination:
    __slots__ = ("page", "per_page", "total", "pages")

    def __init__(self, page: int, per_page: int, total: int) -> None:
        self.page = max(int(page or 1), 1)
        self.per_page = max(int(per_page or 10), 1)
        self.total = max(int(total or 0), 0)
        self.pages = int(ceil(self.total / float(self.per_page))) if self.per_page else 0

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    @property
    def prev_num(self) -> int:
        return self.page - 1 if self.has_prev else 1

    @property
    def next_num(self) -> int:
        return self.page + 1 if self.has_next else (self.pages or 1)

    def iter_pages(self, left_edge=2, right_edge=2, left_current=1, right_current=1):
        """Итератор номеров страниц (None означает многоточие)."""
        if self.pages == 0:
            return
        last = 0
        for num in range(1, self.pages + 1):
            if (
                num <= left_edge
                or (self.page - left_current - 1 < num < self.page + right_current + 1)
                or num > self.pages - right_edge
            ):
                if last + 1 != num:
                    yield None
                yield num
                last = num