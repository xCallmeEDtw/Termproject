from typing import Optional
from math import isclose


class Point:

    def __init__(self, x: float, y: float):
        self.x = float(x)
        self.y = float(y)

    def __repr__(self):

        return f"P({self.x:.3f}, {self.y:.3f})"

    def __eq__(self, other):

        if not isinstance(other, Point):
            return NotImplemented
        return self.x == other.x and self.y == other.y

    def __lt__(self, other):
        """
        Lexical order
        """
        if not isinstance(other, Point):
            return NotImplemented
        if self.x != other.x:
            return self.x < other.x
        return self.y < other.y

    def distance_to(self, other):
        """計算與另一點的距離"""
        if not isinstance(other, Point):
            raise TypeError("distance_to() 需要 Point 類別作為參數")
        dx = self.x - other.x
        dy = self.y - other.y
        return (dx * dx + dy * dy) ** 0.5

    def as_tuple(self):
        """return (x, y) tuple"""
        return (self.x, self.y)


class Edge:

    def __init__(self,
                 start: Point,
                 end: Point,
                 left_polygon: Optional[int] = None,
                 right_polygon: Optional[int] = None):
        self.start = start
        self.end = end
        self.left_polygon = left_polygon
        self.right_polygon = right_polygon

    def __repr__(self):

        return f"E({self.start.x:.3f},{self.start.y:.3f} → {self.end.x:.3f},{self.end.y:.3f})"

    def __eq__(self, other):

        if not isinstance(other, Edge):
            return NotImplemented
        return (self.start == other.start and self.end == other.end) or \
               (self.start == other.end and self.end == other.start)

    def __lt__(self, other):
        """
        Lexical order ：
         (x1, y1, x2, y2)
         x1≦x2 or x1=x2, y1≦y2
        """
        if not isinstance(other, Edge):
            return NotImplemented
        s1, e1 = (self.start, self.end)
        s2, e2 = (other.start, other.end)
        if s1 != s2:
            return s1 < s2
        return e1 < e2

    def as_tuple(self):
        """回傳 ((x1, y1), (x2, y2))，方便輸出或繪圖"""
        return (self.start.as_tuple(), self.end.as_tuple())

    def length(self):
        """計算線段長度"""
        return self.start.distance_to(self.end)

    def is_ray(self, boundary_limit=600):
        """
        檢查是否延伸至畫布邊界的射線。
        若端點在 [0, boundary_limit] 範圍外則視為射線。
        """
        return not (0 <= self.start.x <= boundary_limit and
                    0 <= self.start.y <= boundary_limit and
                    0 <= self.end.x <= boundary_limit and
                    0 <= self.end.y <= boundary_limit)

    def has_point(self, p: Point, eps=1e-6):

        cross = (p.y - self.start.y) * (self.end.x - self.start.x) - \
                (p.x - self.start.x) * (self.end.y - self.start.y)
        if not isclose(cross, 0.0, abs_tol=eps):
            return False
        dot = (p.x - self.start.x) * (self.end.x - self.start.x) + \
              (p.y - self.start.y) * (self.end.y - self.start.y)
        if dot < 0:
            return False
        squared_len = (self.end.x - self.start.x) ** 2 + (self.end.y - self.start.y) ** 2
        return dot <= squared_len + eps