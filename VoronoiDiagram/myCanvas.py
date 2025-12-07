

import tkinter as tk
from typing import Callable, Optional, Tuple, List
from myStructs import Point, Edge

class MyCanvas:
    """
    A canvas class that encapsulates a tkinter.Canvas and provides:
      - add_point(point)
      - add_edge(edge)
      - clear()
      - bind_click(callback)  # callback receives (x, y) in canvas coordinates
      - draw_from(voronoi)    # optional: expects object with .points and .edges lists
    """

    DEFAULT_SIZE = 600

    def __init__(self, parent, width: int = DEFAULT_SIZE, height: int = DEFAULT_SIZE,
                 bg: str = "white"):
        self.parent = parent
        self.width = max(width, self.DEFAULT_SIZE)
        self.height = max(height, self.DEFAULT_SIZE)
        self.bg = bg
        self._point_items = []   # list[tuple[Point, int]]  # (Point, canvas_item_id)
        self.canvas = tk.Canvas(parent, width=self.width, height=self.height, bg=self.bg)
        self.canvas.pack(fill="both", expand=False)

        self.canvas.create_rectangle(
            2, 2, self.width - 2, self.height - 2,
            outline="#888888", width=2
        )

        # tags for grouping
        self._point_tag = "vor_point"
        self._edge_tag = "vor_edge"
        self._hull_tag = "vor_hull"   # 新增：convex hull 用的虛線
        # visual parameters
        self.point_radius = 3
        self.point_fill = "red"
        self.edge_width = 1
        self.edge_color = "black"

        # store item ids if needed
        self._points_ids = []  # list of canvas item ids for points
        self._edges_ids = []   # list of canvas item ids for edges
        self._points = [] 
        self._edges = []   


    def add_point(self, p: Point):
        """Draw a point p on the canvas and record its canvas id."""
        x, y = p.as_tuple()
        r = self.point_radius
        item = self.canvas.create_oval(x - r, y - r, x + r, y + r,
                                       fill=self.point_fill, outline=self.point_fill,
                                       tags=(self._point_tag,))
        self._points_ids.append(item)
        self._points.append(p) 
        self._point_items.append((p, item))
        return item

    def add_edge(self, e: Edge):
        """
        Draw an edge on the canvas. If endpoints lie outside canvas bounds,
        clip the segment to canvas rectangle and draw the visible portion.
        """
        (x1, y1), (x2, y2) = e.as_tuple()
        clipped = self._clip_segment_to_rect(x1, y1, x2, y2,
                                             0.0, 0.0, float(self.width), float(self.height))
        if clipped is None:
            # nothing visible in canvas bounds; still optionally draw full line thin and grey?
            # For now, do nothing.
            return None
        cx1, cy1, cx2, cy2 = clipped
        item = self.canvas.create_line(cx1, cy1, cx2, cy2,
                                       fill=self.edge_color, width=self.edge_width,
                                       tags=(self._edge_tag,))
        self._edges_ids.append(item)
        self._edges.append(e)
        return item

    def clear(self):
        """Clear all points and edges from canvas (keeps canvas itself)."""
        self.canvas.delete(self._point_tag)
        self.canvas.delete(self._edge_tag)
        self.canvas.delete(self._hull_tag)   # 新增：清掉 hull 線
        self._points_ids.clear()
        self._edges_ids.clear()
        self._points.clear()   
        self._edges.clear()    



    def draw_from(self, voronoi):
        """
        Draw all points and edges from a container that exposes:
          - voronoi.points : iterable of Point
          - voronoi.edges  : iterable of Edge
        This method clears the canvas first.
        """
        self.clear()
        for p in getattr(voronoi, "points", []):
            self.add_point(p)
        for e in getattr(voronoi, "edges", []):
            self.add_edge(e)


    def bind_click(self, callback: Callable[[float, float], None], add: bool = False):
        """
        Bind left mouse click to callback which receives (x, y) canvas coordinates.
        If add=True, the callback will be added; otherwise it replaces existing binding.
        """
        def _on_click(event):
            x, y = event.x, event.y
            callback(x, y)

        if add:
            self.canvas.bind("<Button-1>", _on_click, add="+")
        else:
            self.canvas.bind("<Button-1>", _on_click)

    def _clip_segment_to_rect(self, x0, y0, x1, y1, xmin, ymin, xmax, ymax) -> Optional[Tuple[float, float, float, float]]:
        """
        Liang–Barsky algorithm to clip a line segment to an axis-aligned rectangle.
        Returns clipped segment (cx0, cy0, cx1, cy1) or None if fully outside.
        """
        dx = x1 - x0
        dy = y1 - y0

        p = [-dx, dx, -dy, dy]
        q = [x0 - xmin, xmax - x0, y0 - ymin, ymax - y0]

        u1 = 0.0
        u2 = 1.0

        for pi, qi in zip(p, q):
            if pi == 0:
                if qi < 0:
                    return None  # parallel and outside
                else:
                    continue
            t = qi / pi
            if pi < 0:
                # entering
                if t > u2:
                    return None
                if t > u1:
                    u1 = t
            else:
                # leaving
                if t < u1:
                    return None
                if t < u2:
                    u2 = t

        cx0 = x0 + u1 * dx
        cy0 = y0 + u1 * dy
        cx1 = x0 + u2 * dx
        cy1 = y0 + u2 * dy
        return (cx0, cy0, cx1, cy1)


    def widget(self):
        """Return the underlying tkinter.Canvas (for grid/pack/place control)."""
        return self.canvas

    def get_all_points(self):

        return self._points.copy()

    def get_all_edges(self):

        return self._edges.copy()

    def clear_edges(self):

        self.canvas.delete(self._edge_tag)
        self.canvas.delete(self._hull_tag)   
        self._edges.clear()

    def highlight_merge_points(
        self,
        left_points,
        right_points,
        left_color="#ff9900",
        right_color="#00ccff",
    ):
        """
        只把這一層 merge 的左右點上色：
          - 左半點：left_color
          - 右半點：right_color
        其他點顏色不動。
        用座標對應，避免 Point 物件不是同一個 instance 的問題。
        """
        if not hasattr(self, "_point_items"):
            return

        # 建一個 (x,y) → item_id 的查表
        def key(p):
            return (round(p.x, 6), round(p.y, 6))

        lookup = {}
        for p, item in self._point_items:
            lookup[key(p)] = item

        # 左半點上 left_color
        for p in (left_points or []):
            k = key(p)
            item = lookup.get(k)
            if item is not None:
                self.canvas.itemconfig(item, fill=left_color, outline=left_color)

        # 右半點上 right_color
        for p in (right_points or []):
            k = key(p)
            item = lookup.get(k)
            if item is not None:
                self.canvas.itemconfig(item, fill=right_color, outline=right_color)
    def draw_convex_hull(self, hull_points, color="black", dash=(4, 2)):
        """
        用虛線畫 convex hull：
          - 不存到 self._edges（避免存檔時把 hull 畫進 output）
          - 只在畫布上畫出一圈虛線
        """
        if not hull_points or len(hull_points) < 2:
            return

        n = len(hull_points)
        for i in range(n):
            p1 = hull_points[i]
            p2 = hull_points[(i + 1) % n]   # 收尾相接
            x1, y1 = p1.as_tuple()
            x2, y2 = p2.as_tuple()

            self.canvas.create_line(
                x1, y1, x2, y2,
                fill=color,
                width=self.edge_width,
                dash=dash,                 # 虛線
                tags=(self._hull_tag,),    # 用 hull 專用 tag
            )


if __name__ == "__main__":
    # simple demo
    root = tk.Tk()
    root.title("MyCanvas Demo")
    mc = MyCanvas(root, 700, 650)
    # demo points and edges
    pts = [Point(100, 100), Point(300, 50), Point(500, 500)]
    for p in pts:
        mc.add_point(p)
    edges = [
        Edge(Point(0, 34), Point(193, 161)),
        Edge(Point(0, 363), Point(193, 261)),
        Edge(Point(193, 161), Point(193, 261)),
        Edge(Point(193, 161), Point(437, 0)),
        Edge(Point(193, 261), Point(600, 476))
    ]
    for e in edges:
        mc.add_edge(e)

    def on_click(x, y):
        print("Clicked:", x, y)
        mc.add_point(Point(x, y))

    mc.bind_click(on_click)
    root.mainloop()
