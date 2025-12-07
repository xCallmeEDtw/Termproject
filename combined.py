# ===== File: main.py =====

from ui_window import AppWindow
if __name__ == "__main__":
    AppWindow().run()

# ===== File: myCanvas.py =====



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


# ===== File: myStructs.py =====

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

# ===== File: ui_window.py =====

# ui_window.py
# $LAN=PYTHON$
# Author: B112040003 張景旭
# Desc: 最外層 Tk 視窗物件（僅視窗與菜單骨架；先不含畫布與I/O）

import tkinter as tk

from tkinter import filedialog, messagebox
from myCanvas import MyCanvas

import io


from voronoi_core import compute_voronoi, compute_voronoi_with_steps

from myStructs import Point, Edge

class FileInputManager:
    """
    以游標方式讀取測資檔，支援註解(#)與空行。
    使用流程：
      fim = FileInputManager("path/to/file")
      fim.open()           # 開檔並預備
      batch = fim.next_batch()  # 回傳 list[Point] 或 None (代表 EOF 或已停止)
      # 若 batch == [] 表示讀到 n==0 (停止信號)，可以關閉
    """
    def __init__(self, path: str):
        self.path = path
        self._fp = None
        self._eof = False

    def open(self):
        self._fp = open(self.path, "r", encoding="utf-8")
        self._eof = False

    def close(self):
        if self._fp:
            self._fp.close()
            self._fp = None
        self._eof = True

    def _read_next_noncomment_line(self):
        """回傳下一個非註解、非空行的字串，或 None 若 EOF"""
        if not self._fp:
            return None
        for raw in self._fp:
            s = raw.strip()
            if s == "" or s.startswith("#"):
                continue
            return s
        return None

    def next_batch(self):
        """
        讀取下一組 batch：
        格式：第一行是一個整數 n；接下來 n 行為 x y
        回傳：
          - None：已無更多有效資料（EOF 或已關閉）
          - []：讀到 n==0（呼叫端視為停止）
          - list_of_points：若讀到 n>0，回傳 list[Point]
        """
        if self._eof:
            return None
        if self._fp is None:
            # 尚未 open
            self.open()
        s = self._read_next_noncomment_line()
        if s is None:
            self.close()
            return None
        try:
            n = int(s.split()[0])
        except Exception:
            # 若格式不正確（理論上測資為 error-free），視為 EOF
            self.close()
            return None

        if n == 0:
            # 規定：當讀到 0 時代表停止測資
            return []

        pts = []
        for _ in range(n):
            s2 = self._read_next_noncomment_line()
            if s2 is None:
                # 檔案提前結束，回傳目前讀到的（雖理論上不會發生）
                break
            parts = s2.split()
            if len(parts) >= 2:
                x = float(parts[0])
                y = float(parts[1])
                # 使用你檔內的 Point class 建立物件
                pts.append(Point(x, y))
        return pts

class AppWindow:
    """負責建立主視窗與基本菜單骨架（之後再接 Canvas 與 I/O）"""

    def __init__(self, title: str = "Voronoi Diagram - 初測視窗"):
        self.root = tk.Tk()
        self.root.title(title)

        self.file_manager = None
        self.input_filepath = None

        # 規格要求：畫布至少 600x600；此處主視窗也先設≥600x600
        self.root.minsize(800, 700)
        self.root.geometry("800x700+100+80")

        # 關閉視窗行為
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # 預留：上方菜單（File / View / Help）
        self._build_menu()
        # === Canvas Container Frame ===
        self.canvas_frame = tk.Frame(self.root, bg="#DDDDDD")  # 背景淺灰，讓範圍更明顯
        # 加入外部 padding，並讓 frame 在上下左右都留空間
        self.canvas_frame.pack(fill="both", expand=True, padx=20, pady=(20, 8))

        # 將 Canvas 放在 Frame 中，並增加 padding
        self.canvas = MyCanvas(self.canvas_frame)
        self.canvas.widget().pack(padx=50, pady=30)   # <-- 這裡控制 Canvas 與 UI 邊緣距離

        self.coord_label = tk.Label(self.canvas_frame, text="", bg="#DDDDDD", font=("Arial", 9))
        self.coord_label.place(relx=0.98, rely=0.02, anchor="ne")  # 右上角，微微內縮
        self.canvas.widget().bind("<Motion>", self._on_canvas_motion)
        self.canvas.widget().bind("<Leave>", self._on_canvas_leave)


        # control frame INSIDE canvas_frame so buttons are always visible under the canvas
        self.control_frame = tk.Frame(self.canvas_frame, bg="#DDDDDD")
        # 放在 canvas_frame 的底部（內部），並給左右上下內距
        self.control_frame.pack(side="bottom", fill="x", pady=(6,12), padx=12)
        # Next Batch button (same as menu's Load Next Batch)
        # Next Batch button (same as menu's Load Next Batch)
        self.next_batch_btn = tk.Button(self.control_frame, text="Next Batch", command=self._load_next_batch)
        self.next_batch_btn.pack(side="left", padx=8)



        # Run button
        self.run_button = tk.Button(self.control_frame, text="Run", command=self._on_run_click)
        self.run_button.pack(side="left", padx=8)

        # Clear canvas button (next to Run)
        self.clear_btn = tk.Button(self.control_frame, text="Clear", command=self._clear_canvas)
        self.clear_btn.pack(side="left", padx=8)

        # small spacer to the right (optional) so buttons are not jammed to left
        self.control_spacer = tk.Label(self.control_frame, text="", bg="#DDDDDD")
        self.control_spacer.pack(side="left", padx=6)

        # Step-by-step 按鈕
        self.step_button = tk.Button(self.control_frame, text="Step", command=self._on_step_click)
        self.step_button.pack(side="left", padx=8)
        # Step to End 按鈕：直接跳到最後一個 merge step 的「合併後 hull + HP」
        self.step_to_end_button = tk.Button(
            self.control_frame,
            text="Step to End",
            command=self._on_step_to_end_click
        )
        self.step_to_end_button.pack(side="left", padx=8)

        self.reset_step_button = tk.Button(
            self.control_frame,
            text="Reset Step",
            command=self._on_step_reset_click
        )
        self.reset_step_button.pack(side="left", padx=8)

        # Step-by-step 狀態
        self.step_steps = None          # List[MergeStep] 或 None
        self.step_index = 0             # 目前走到第幾步
        self.step_final_edges = None    # 最後完整 VD 的 edges

        self._steps = None              # List[MergeStep] 或 None
        self._step_idx = 0              # 目前是第幾個 MergeStep
        self._sub_phase = 0             # 0: 左右 hull, 1: merged hull, 2: 下一次跳下一步        

                # 記錄「按下 Step 前」的畫面狀態（點 & 邊）
        self._pre_step_points = None
        self._pre_step_edges = None
        # 綁定滑鼠功能
        self.canvas.bind_click(self._on_canvas_click)
        # 預留：狀態列（之後可顯示座標或訊息）
        self.status_var = tk.StringVar(value="Ready")
        self._build_statusbar()

    # —— 之後要接的功能（讀檔/存檔/輸出）會掛在這個區塊 —— #
    def _build_menu(self):
        menubar = tk.Menu(self.root)



        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open Input File...", command=self._open_input_file)
        file_menu.add_command(label="Load Next Batch", command=self._load_next_batch)
        file_menu.add_separator()
        file_menu.add_command(label="Open Output File...", command=self._open_output_file)
        file_menu.add_separator()
        file_menu.add_command(label="Clear Canvas", command=self._clear_canvas)
        file_menu.add_separator()
        file_menu.add_command(label="Save Output...", command=self._save_output_file)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        menubar.add_command(label="Run", command=self._on_run_click)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

    def _build_statusbar(self):
        bar = tk.Label(self.root, textvariable=self.status_var,
                       anchor="w", relief="sunken", bd=1)
        bar.pack(side="bottom", fill="x")
    def _open_input_file(self):
        """讓使用者選擇測資檔並建立 FileInputManager"""
        path = filedialog.askopenfilename(title="Open Voronoi test data",
                                          filetypes=[("Text files", "*.txt *.in *.dat"), ("All files", "*.*")])
        if not path:
            return
        # 若已有 open 的 file manager，先關閉
        if self.file_manager:
            try:
                self.file_manager.close()
            except:
                pass
        self.input_filepath = path
        self.file_manager = FileInputManager(path)
        try:
            self.file_manager.open()
        except Exception as e:
            messagebox.showerror("Open Error", f"無法開啟檔案：{e}")
            self.file_manager = None
            self.input_filepath = None
            return
        messagebox.showinfo("File Opened", f"已開啟：{path}\n請按 'Load Next Batch' 讀入第一組測資。")

    def _load_next_batch(self):
        self._steps = None
        self._step_idx = 0
        self._sub_phase = 0
        self._pre_step_points = None
        self._pre_step_edges = None
        if not self.file_manager:
            messagebox.showwarning("No File", "尚未開啟輸入檔。請先選擇 Open Input File...")
            return

        pts = self.file_manager.next_batch()
        if pts is None:
            messagebox.showinfo("End", "已無更多測資（EOF）。")
            return

        if pts == []:
            messagebox.showinfo("Stopped", "讀入點數為零，檔案測試停止。")
            try:
                self.file_manager.close()
            except:
                pass
            self.file_manager = None
            return

        # --- 🔥 這裡是修改處：每批輸入都清空畫布 🔥 ---
        self.canvas.clear()

        # --- 加入本批測資 ---
        for p in pts:
            self.canvas.add_point(p)

        # 更新顯示訊息
        self.status_var.set(f"Loaded batch: {len(pts)} points from {self.input_filepath}")
    
    def _open_output_file(self):
        """讀入 output 檔案 (含 P / E)，並畫到 canvas"""
        path = filedialog.askopenfilename(
            title="Open Voronoi output file",
            filetypes=[("Text files", "*.txt *.out *.dat"), ("All files", "*.*")]
        )
        if not path:
            return

        self.canvas.clear()   # ← 清畫面（可以保留或移除，看你需求）

        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            from myStructs import Point, Edge

            for line in lines:
                s = line.strip()
                if not s or s.startswith("#"):    # 空行與註解略過
                    continue

                parts = s.split()

                if parts[0] == "P":
                    # P x y
                    x, y = float(parts[1]), float(parts[2])
                    p = Point(x, y)
                    self.canvas.add_point(p)

                elif parts[0] == "E":
                    # E x1 y1 x2 y2
                    x1, y1, x2, y2 = map(float, parts[1:5])
                    p1 = Point(x1, y1)
                    p2 = Point(x2, y2)
                    e = Edge(p1, p2)
                    self.canvas.add_edge(e)

            self.status_var.set(f"Loaded output file: {path}")

        except Exception as e:
            messagebox.showerror("File Error", f"Error reading file:\n{e}")

    def _save_output_file(self):
        """輸出目前 canvas 上的 點(P) 與 線段(E)，並依 lexical order 排序"""

        from myStructs import Point, Edge  # 確保 class 有被 import

        path = filedialog.asksaveasfilename(
            title="Save Voronoi Output",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not path:
            return

        # --- 抓 canvas 裡的點與線段 ---
        points = self.canvas.get_all_points()   # 你需要在 MyCanvas 補這個方法 (下一步我再給)
        edges  = self.canvas.get_all_edges()

        # --- lexical order ---
        # P: (x, y)
        points.sort(key=lambda p: (p.x, p.y))

        # E: (x1, y1, x2, y2)，並先保證 x1 ≤ x2 或 y1 ≤ y2
        sorted_edges = []
        for e in edges:
            p1 = e.start
            p2 = e.end
            # swap if violates rule
            if (p1.x > p2.x) or (p1.x == p2.x and p1.y > p2.y):
                p1, p2 = p2, p1
            sorted_edges.append((p1, p2))

        sorted_edges.sort(key=lambda pair: (pair[0].x, pair[0].y, pair[1].x, pair[1].y))


        with open(path, "w", encoding="utf-8") as f:
            for p in points:
                f.write(f"P {int(p.x)} {int(p.y)}\n")

            for p1, p2 in sorted_edges:
                f.write(f"E {int(p1.x)} {int(p1.y)} {int(p2.x)} {int(p2.y)}\n")

        messagebox.showinfo("Saved", f"Output saved to:\n{path}")

    def _on_run_click(self):
        """
        Run 按鈕處理：
          - 取得目前 canvas 上的點
          - 若點數 > 3，顯示警告並不執行
          - 否則呼叫 compute_voronoi(points, canvas_w, canvas_h)
          - 在畫布上先清除舊的邊（但保留點），再畫回傳的邊
        """
        from tkinter import messagebox
        self._steps = None
        self._step_idx = 0
        self._sub_phase = 0
        self._pre_step_points = None
        self._pre_step_edges = None

        pts = self.canvas.get_all_points()  # list[Point]
        n = len(pts)
        if n == 0:
            messagebox.showinfo("Run Voronoi", "畫布上沒有點。請先加入點。")
            return
        # if n > 3:
        #     messagebox.showwarning("Run Voronoi", f"目前點數為 {n}，超過初測上限 (≤3)。請移除至最多 3 個點。")
        #     return

        # 有 1~3 點：呼叫 voronoi 計算
        try:
            edges = compute_voronoi(pts, self.canvas.width, self.canvas.height)
        except Exception as e:
            messagebox.showerror("Voronoi Error", f"計算 Voronoi 發生錯誤：\n{e}")
            return

        # 先移除舊的邊（保留點）
        try:
            self.canvas.clear_edges()
        except Exception:
            # 若 clear_edges 尚未定義（保險），就清整個畫布然後重畫點
            all_pts = self.canvas.get_all_points()
            self.canvas.clear()
            for p in all_pts:
                self.canvas.add_point(p)

        # 畫回算好的邊
        for e in edges:
            self.canvas.add_edge(e)

        # 更新狀態列
        try:
            self.status_var.set(f"Ran Voronoi on {n} points, drew {len(edges)} edges")
        except Exception:
            pass

    def _on_canvas_motion(self, event):
        """
        Canvas 上滑鼠移動時顯示 (x, y) 座標。
        event.x & event.y 為相對於 canvas widget 的座標。
        """
        try:
            # 直接取整數顯示
            x = int(event.x)
            y = int(event.y)
            self.coord_label.config(text=f"({x}, {y})")
        except Exception:
            # 保險：若 widget 尚未建立或其他錯誤，忽略
            pass

    def _on_canvas_leave(self, event):
        """滑鼠離開 canvas 時清除座標顯示"""
        try:
            self.coord_label.config(text="")
        except Exception:
            pass

    def _on_step_click(self):
        """
        Step-by-step：
          同一個 merge step 用三次按鍵來看：
            1. 左右兩邊的 convex hull（虛線）
            2. 合併後的 convex hull（虛線）
            3. 跳到下一個 merge step 的左右 convex hull
        左邊 Voronoi：藍色
        右邊 Voronoi：綠色
        HP：紅色
        """
        from voronoi_core import compute_voronoi_with_steps

        pts = self.canvas.get_all_points()
        n = len(pts)
        if n == 0:
            messagebox.showinfo("Step", "畫布上沒有點。")
            return

        # 第一次按 Step → 計算所有 steps
        if self._steps is None:

            self._pre_step_points = self.canvas.get_all_points()
            self._pre_step_edges = self.canvas.get_all_edges()

            edges, steps = compute_voronoi_with_steps(
                pts, self.canvas.width, self.canvas.height
            )
            self._steps = steps
            self._step_idx = 0
            self._sub_phase = 0

            if not steps:
                messagebox.showinfo("Step", "點數太少，沒有 merge 步驟可以顯示。")
                return

        # 如果上一輪已經在 phase 2，這一輪先跳到下一個 merge step
        if self._sub_phase == 2:
            self._step_idx += 1
            self._sub_phase = 0

        if self._step_idx >= len(self._steps):
            messagebox.showinfo("Step", "所有 merge 步驟都完成了。")
            return

        step = self._steps[self._step_idx]

        # 先清掉舊線段與 hull，但保留點
        old_pts = self.canvas.get_all_points()
        self.canvas.clear()
        for p in old_pts:
            self.canvas.add_point(p)

        # 左邊 Voronoi → 藍色
        for e in step.left_edges:
            tag = self.canvas.add_edge(e)
            if tag is not None:
                self.canvas.widget().itemconfig(tag, fill="blue")

        # 右邊 Voronoi → 綠色
        for e in step.right_edges:
            tag = self.canvas.add_edge(e)
            if tag is not None:
                self.canvas.widget().itemconfig(tag, fill="green")

        # HP → 紅色
        for e in step.hyperplane_edges:
            tag = self.canvas.add_edge(e)
            if tag is not None:
                self.canvas.widget().itemconfig(tag, fill="red")

        # 把這一層 merge 相關的點上色（左藍右綠）
        self.canvas.highlight_merge_points(
            step.left_sites,
            step.right_sites,
            left_color="blue",
            right_color="green",
        )

        # 依 sub_phase 畫 convex hull（虛線）
        if self._sub_phase == 0:
            # (a) 合併前左右兩邊的 convex hull
            if step.left_hull:
                self.canvas.draw_convex_hull(step.left_hull, color="blue")
            if step.right_hull:
                self.canvas.draw_convex_hull(step.right_hull, color="green")

            self._sub_phase = 1
            phase_msg = "顯示本次 merge 的左右 convex hull。"

        elif self._sub_phase == 1:
            # (b) 合併後的 convex hull
            if step.merged_hull:
                # 用一個跟 HP 不同的顏色，例如紫色
                self.canvas.draw_convex_hull(step.merged_hull, color="#aa00aa")

            self._sub_phase = 2
            phase_msg = "顯示本次 merge 的合併後 convex hull。"

        else:
            # 理論上不會進來；保險處理
            self._sub_phase = 0
            phase_msg = "重設 Step 狀態。"

        self.status_var.set(
            f"Merge step {self._step_idx + 1}/{len(self._steps)}，{phase_msg}"
        )

    def _on_step_to_end_click(self):
        """
        一鍵直接跳到「最後一個 merge step 的 phase 1」：
          - 畫出最後一次 merge 的：
              * 左右 Voronoi（藍 / 綠）
              * HP（紅）
              * 合併後的 convex hull（紫色虛線）
              * 左右半邊的點顏色（藍 / 綠）
        相當於 Step 一路按到最後，並停在「顯示合併後 hull」那一步。
        """
        pts = self.canvas.get_all_points()
        if not pts:
            messagebox.showinfo("Step to End", "畫布上沒有點。")
            return

        # 如果還沒算過 steps，就先算一次
        if self._steps is None:
            edges, steps = compute_voronoi_with_steps(
                pts, self.canvas.width, self.canvas.height
            )
            if not steps:
                messagebox.showinfo("Step to End", "點數太少，沒有 merge 步驟可以顯示。")
                return
            self._steps = steps

        if not self._steps:
            messagebox.showinfo("Step to End", "沒有可顯示的 merge 步驟。")
            return

        # 直接跳到「最後一個 merge step」
        self._step_idx = len(self._steps) - 1
        self._sub_phase = 1   # Phase 1 = 顯示 merged hull

        step = self._steps[self._step_idx]

        # 先清掉舊線段與 hull，但保留點
        old_pts = self.canvas.get_all_points()
        self.canvas.clear()
        for p in old_pts:
            self.canvas.add_point(p)

        # 左邊 Voronoi → 藍色
        for e in step.left_edges:
            tag = self.canvas.add_edge(e)
            if tag is not None:
                self.canvas.widget().itemconfig(tag, fill="blue")

        # 右邊 Voronoi → 綠色
        for e in step.right_edges:
            tag = self.canvas.add_edge(e)
            if tag is not None:
                self.canvas.widget().itemconfig(tag, fill="green")

        # HP → 紅色
        for e in step.hyperplane_edges:
            tag = self.canvas.add_edge(e)
            if tag is not None:
                self.canvas.widget().itemconfig(tag, fill="red")

        # 把這一層 merge 相關的點上色（左藍右綠）
        self.canvas.highlight_merge_points(
            step.left_sites,
            step.right_sites,
            left_color="blue",
            right_color="green",
        )

        # 畫「合併後的 convex hull」（紫色虛線）
        if step.merged_hull:
            self.canvas.draw_convex_hull(step.merged_hull, color="#aa00aa")

        self.status_var.set(
            f"Step to End：直接顯示最後一個 merge step（{len(self._steps)}/{len(self._steps)}）的合併後 convex hull 與 HP。"
        )


    def _on_step_reset_click(self):
        """
        Reset Step：
          清掉所有由 Step / Step to End 顯示出來的線段與 hull，
          只保留目前畫布上的點，並且把 step 狀態歸零。
        """
        # 取得目前所有點
        points = self.canvas.get_all_points()

        # 清畫面
        self.canvas.clear()

        # 把點畫回來（不畫任何線）
        for p in points:
            self.canvas.add_point(p)

        # 清除 step 狀態
        self._steps = None
        self._step_idx = 0
        self._sub_phase = 0

        # 不再依賴備份
        self._pre_step_points = None
        self._pre_step_edges = None

        self.status_var.set("Step 已重置：只保留點，沒有任何線段。")


    def _todo(self):
        messagebox.showinfo("TODO", "此功能將於之後步驟實作。")

    def _about(self):
        messagebox.showinfo("About", "Voronoi Diagram 初測視窗\nTkinter OOP 結構")

    def _on_close(self):
        self.root.destroy()
    def _on_canvas_click(self, x, y):
        point = Point(x, y)
        self.canvas.add_point(point)

    def _clear_canvas(self):
        self.canvas.clear()
        self._steps = None
        self._step_idx = 0
        self._pre_step_points = None
        self._pre_step_edges = None
    def run(self):
        self.root.mainloop()





if __name__ == "__main__":
    AppWindow().run()


# ===== File: voronoi_core.py =====

# voronoi_core.py
# $LAN=PYTHON$

from typing import List, Tuple, Optional
from dataclasses import dataclass
import math

from myStructs import Point, Edge

EPS = 1e-9




@dataclass
class VoronoiDiagram:
    """
    用來包裝一次子問題的 Voronoi 結果。
    之後會加上 convex hull、其他 merge/hyperplane 需要的資訊。
    現在先只有 edges，保持對外介面單純。
    """
    edges: List[Edge]
    # 之後可以加:
    # hull: Optional[List[Point]] = None
    # 其他需要的欄位…
    hull: Optional[List[Point]] = None


@dataclass
class MergeStep:
    """
    用於 Step-by-step 的「merge 步驟」紀錄：
      - 左右子圖的邊 (left_edges, right_edges)
      - hyperplane HP 的邊 (hyperplane_edges)
      - 左右以及合併後的 convex hull（畫示意圖用）
      - median_x: 此次 merge 所用的 median 直線 x 座標（可畫出分割線）
      - left_sites / right_sites: 這一層 merge 涉及的左右點集合
    """
    left_edges: List[Edge]
    right_edges: List[Edge]
    hyperplane_edges: List[Edge]
    left_hull: Optional[List[Point]]
    right_hull: Optional[List[Point]]
    merged_hull: Optional[List[Point]]
    median_x: Optional[float] = None
    left_sites: Optional[List[Point]] = None
    right_sites: Optional[List[Point]] = None

def _unique_points(points: List[Point]) -> List[Point]:
    """
    依座標去掉重複點，只保留第一個出現的那個。
    用 (round(x,6), round(y,6)) 當 key，避免浮點誤差。
    """
    seen = set()
    out: List[Point] = []
    for p in points:
        key = (round(p.x, 6), round(p.y, 6))
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def compute_voronoi(points: List[Point], canvas_w: int, canvas_h: int) -> List[Edge]:
    """
    Run 用的 Voronoi 入口：
      n = 0 → 沒有邊
      n = 1 → 沒有邊
      n = 2 → 精確中垂線
      n = 3 → 精確三點 Voronoi
      n ≥ 4 → 使用「所有點對的中垂線 + 最近兩點裁切」的穩定演算法
    """
    uniq_pts = _unique_points(points)

    n = len(uniq_pts)
    if n == 0:
        return []

    # 統一先依 (x,y) 排序，讓輸出比較穩定
    sorted_pts = sorted(uniq_pts, key=lambda p: (p.x, p.y))

    if n == 1:
        return []

    if n == 2:
        return _voronoi_two_points(sorted_pts[0], sorted_pts[1], canvas_w, canvas_h)

    if n == 3:
        return _voronoi_three_points(sorted_pts, canvas_w, canvas_h)

    # n >= 4：改用「所有點對」的穩定版本
    diagram =_build_voronoi(sorted_pts, canvas_w, canvas_h, steps=None)

    return diagram.edges

def compute_voronoi_with_steps(points: List[Point],
                               canvas_w: int,
                               canvas_h: int) -> Tuple[List[Edge], List[MergeStep]]:
    """
    Step-by-step 版本：
      - 回傳 (edges, steps)
      - steps 裡每一個 MergeStep 對應一次「merge 左右子圖」的階段，
        UI 可以依序拿來畫：
          * 左邊 Voronoi
          * 右邊 Voronoi
          * hyperplane HP
          * median 直線
          * hull 等
    """

    uniq_pts = _unique_points(points)

    n = len(uniq_pts)
    if n == 0:
        return [], []

    sorted_pts = sorted(uniq_pts, key=lambda p: (p.x, p.y))

    steps: List[MergeStep] = []
    diagram = _build_voronoi(sorted_pts, canvas_w, canvas_h, steps=steps)

    return diagram.edges, steps


def _build_voronoi(points_sorted: List[Point],
                   w: int,
                   h: int,
                   steps: Optional[list] = None) -> VoronoiDiagram:
    n = len(points_sorted)

    # ---- Base case：n=1，只有一個點，沒有邊，凸包就是自己 ----
    if n == 1:
        return VoronoiDiagram(edges=[], hull=points_sorted[:])

    # ---- 只有在「非 Step-by-step」（steps is None）時，
    #      才啟用 n=2、n=3 的特製解法 ----
    if steps is None:
        if n == 2:
            # 兩點：直接用精確中垂線
            p1, p2 = points_sorted[0], points_sorted[1]
            edges = _voronoi_two_points(p1, p2, w, h)
            hull = sorted(points_sorted, key=lambda p: (p.x, p.y))
            return VoronoiDiagram(edges=edges, hull=hull)

        if n == 3:
            # 三點：直接用三點特製版本
            edges = _voronoi_three_points(points_sorted, w, h)
            hull = _convex_hull_simple(points_sorted)
            return VoronoiDiagram(edges=edges, hull=hull)

    # ---- 之後所有 n ≥ 2，都走一般的 D&C Step 2~4 ----

    # Step 2: median cut
    mid = n // 2
    left_points = points_sorted[:mid]
    right_points = points_sorted[mid:]

    median_x = (left_points[-1].x + right_points[0].x) / 2.0

    if steps is not None:
        # 之後若要記 DivideStep 可以在這裡補
        pass

    # Step 3: 遞迴構造左右 VD
    left_diagram = _build_voronoi(left_points, w, h, steps)
    right_diagram = _build_voronoi(right_points, w, h, steps)

    # Step 4: merge
    merged = _merge_diagrams(
        left_diagram,
        right_diagram,
        left_points,
        right_points,
        median_x,
        w,
        h,
        steps
    )

    return merged





def _merge_diagrams(left: VoronoiDiagram,
                    right: VoronoiDiagram,
                    left_points: List[Point],
                    right_points: List[Point],
                    median_x: float,
                    w: int,
                    h: int,
                    steps: Optional[list]) -> VoronoiDiagram:
    """
    Divide-and-conquer 的 Step 4：合併左右 Voronoi 子圖。

    版本說明：
      - hyperplane HP：用所有 (left_point, right_point) 的中垂線，
        再用 sampling + 最近點檢查，組成完整 HP。
      - 左右子圖：用「哪一側比較靠 left / right」來 trimming。
      - hull：直接對全部 sites 做一次凸包（給下一層 merge 用）。
    """

    all_sites = left_points + right_points

    # 1. 用所有 cross pair 建出 dividing hyperplane HP（多段線）
    hp_edges = _compute_dividing_chain(
        left_points,
        right_points,
        w,
        h,
        all_sites,
    )

    # 2. 用 HP 對左右子圖做 trimming：
    #   - 左圖保留「比較靠 left」的那一側
    #   - 右圖保留「比較靠 right」的那一側
    trimmed_left = _trim_edges_by_hp(
        left.edges,
        left_points,
        right_points,
        keep_left=True,   # 左邊保留 left 側
    )
    trimmed_right = _trim_edges_by_hp(
        right.edges,
        left_points,
        right_points,
        keep_left=False,  # 右邊保留 right 側
    )

    # 3. 合併邊集合
    combined_edges = trimmed_left + trimmed_right + hp_edges

    # 4. 重新算整體凸包（只看 sites，不看 edges）
    merged_hull = _convex_hull_simple(all_sites)

    # 5. 若要 Step-by-step，記錄這次 merge 的資訊
    if steps is not None:
        steps.append(
            MergeStep(
                left_edges=trimmed_left,
                right_edges=trimmed_right,
                hyperplane_edges=hp_edges,
                left_hull=left.hull,
                right_hull=right.hull,
                merged_hull=merged_hull,
                median_x=median_x,
                left_sites=left_points,
                right_sites=right_points,
            )
        )

    return VoronoiDiagram(edges=combined_edges, hull=merged_hull)










def _compute_dividing_chain(left_points: List[Point],
                            right_points: List[Point],
                            w: int,
                            h: int,
                            all_sites: List[Point]) -> List[Edge]:
    """
    建立 divide-and-conquer 所需的 dividing hyperplane HP。

    做法：
      - 對所有 (L ∈ S_L, R ∈ S_R) 點對：
          * 計算其中垂線與畫布矩形的交點
          * 用 sampling 檢查「在哪些小段上，最近兩個 site
            剛好就是 (L, R)」
        → 那些小段就是 HP 的一部分。

      - 把所有 cross pair 的有效小段組起來，就得到整條分隔鏈（HP）。
    """
    edges: List[Edge] = []

    if not left_points or not right_points:
        return edges

    for L in left_points:
        for R in right_points:
            segs = _compute_single_bisector_segment(L, R, all_sites, w, h)
            edges.extend(segs)

    return edges





def _compute_single_bisector_segment(pL: Point, pR: Point,
                                     all_sites: List[Point],
                                     w: int, h: int) -> List[Edge]:

    # 計算 pL、pR 的中垂線
    mid, dirv = _perp_bisector(pL, pR)

    inters = _intersect_line_with_rect(mid, dirv, w, h)
    if len(inters) < 2:
        return []

    # 取最大兩端
    if len(inters) > 2:
        inters = sorted(inters)
    A, B = inters[0], inters[-1]

    # 過濾出有效的區段（最近兩點剛好是 pL、pR）
    segs = _filter_segment_by_closest_pair(
        A, B, pL, pR, all_sites, samples=400
    )

    edges = []
    for (sx,sy),(ex,ey) in segs:
        edges.append(Edge(Point(sx,sy), Point(ex,ey)))

    return edges




# def _merge_hulls(left_hull: List[Point],
#                  right_hull: List[Point]) -> List[Point]:
#     """
#     合併左右凸包（均為 CCW 順序）成新的大凸包。
#     使用 upper tangent 與 lower tangent，複雜度 O(n)。

#     left_hull  與 right_hull 都是已經依 CCW 排好的凸包頂點序列。
#     回傳：合併後的大凸包（同為 CCW 序）。

#     注意：這是純幾何，不牽涉 Voronoi 邊，只處理 convex hull。
#     """

#     if not left_hull:
#         return right_hull[:]
#     if not right_hull:
#         return left_hull[:]

#     # 為了方便操作，把 hull points 取成 list
#     LH = left_hull
#     RH = right_hull

#     # 找 LH 中 x 最大的點（最右的點）
#     i = max(range(len(LH)), key=lambda k: LH[k].x)
#     # 找 RH 中 x 最小的點（最左的點）
#     j = min(range(len(RH)), key=lambda k: RH[k].x)

#     # ---------- upper tangent ----------
#     done = False
#     while not done:
#         done = True
#         # 往 LH 逆時針方向測試
#         while True:
#             ni = (i - 1) % len(LH)
#             # cross product > 0 表示 RH[j] 在向量 LH[i]→LH[ni] 的左側，需調整
#             cross_val = ((LH[ni].x - LH[i].x) * (RH[j].y - LH[i].y) -
#                          (LH[ni].y - LH[i].y) * (RH[j].x - LH[i].x))
#             if cross_val > 0:
#                 i = ni
#                 continue
#             break

#         # 往 RH 順時針方向測試
#         while True:
#             nj = (j + 1) % len(RH)
#             cross_val = ((RH[nj].x - RH[j].x) * (LH[i].y - RH[j].y) -
#                          (RH[nj].y - RH[j].y) * (LH[i].x - RH[j].x))
#             if cross_val < 0:
#                 j = nj
#                 done = False
#                 continue
#             break

#     upper_i, upper_j = i, j

#     # ---------- lower tangent ----------
#     i = max(range(len(LH)), key=lambda k: LH[k].x)
#     j = min(range(len(RH)), key=lambda k: RH[k].x)
#     done = False

#     while not done:
#         done = True
#         # LH 順時針
#         while True:
#             ni = (i + 1) % len(LH)
#             cross_val = ((LH[ni].x - LH[i].x) * (RH[j].y - LH[i].y) -
#                          (LH[ni].y - LH[i].y) * (RH[j].x - LH[i].x))
#             if cross_val < 0:
#                 i = ni
#                 continue
#             break

#         # RH 逆時針
#         while True:
#             nj = (j - 1) % len(RH)
#             cross_val = ((RH[nj].x - RH[j].x) * (LH[i].y - RH[j].y) -
#                          (RH[nj].y - RH[j].y) * (LH[i].x - RH[j].x))
#             if cross_val > 0:
#                 j = nj
#                 done = False
#                 continue
#             break

#     lower_i, lower_j = i, j

#     # ---------- 建立合併後的 hull (CCW) ----------
#     merged = []

#     # 從 LH 的 upper_i → lower_i
#     k = upper_i
#     merged.append(LH[k])
#     while k != lower_i:
#         k = (k + 1) % len(LH)
#         merged.append(LH[k])

#     # 從 RH 的 lower_j → upper_j
#     k = lower_j
#     merged.append(RH[k])
#     while k != upper_j:
#         k = (k + 1) % len(RH)
#         merged.append(RH[k])

#     return merged




def _intersect_line_with_rect(mid: Tuple[float,float], dirv: Tuple[float,float], w: int, h: int
                              ) -> List[Tuple[float,float]]:
    """
    Parametric line: P(t) = mid + t * dirv
    Return list of intersection points of the infinite line with rectangle [0,w]x[0,h].
    Result will contain 0..2 points (usually 2 unless line is degenerate).
    """
    (mx, my) = mid
    (dx, dy) = dirv
    pts = []

    # handle near-zero directions
    if abs(dx) < EPS:
        # Vertical-ish: intersect with y=0 and y=h via x=mx
        x = mx
        if 0 - EPS <= x <= w + EPS:
            pts.append((x, 0.0))
            pts.append((x, float(h)))
        return _unique_points_on_rect(pts, w, h)

    if abs(dy) < EPS:
        # Horizontal-ish: intersect with x=0 and x=w via y=my
        y = my
        if 0 - EPS <= y <= h + EPS:
            pts.append((0.0, y))
            pts.append((float(w), y))
        return _unique_points_on_rect(pts, w, h)

    # solve for t where x = 0, x = w, y = 0, y = h
    candidates = []
    # x = 0 -> t = (0 - mx) / dx
    t = (0.0 - mx) / dx
    candidates.append(t)
    # x = w
    t = (float(w) - mx) / dx
    candidates.append(t)
    # y = 0
    t = (0.0 - my) / dy
    candidates.append(t)
    # y = h
    t = (float(h) - my) / dy
    candidates.append(t)

    for t in candidates:
        x = mx + t * dx
        y = my + t * dy
        if -EPS <= x <= w + EPS and -EPS <= y <= h + EPS:
            pts.append((x, y))

    return _unique_points_on_rect(pts, w, h)

def _unique_points_on_rect(pts, w, h):
    # filter duplicates (within EPS) and clamp to exact edges
    out = []
    for (x,y) in pts:
        # clamp
        cx = 0.0 if abs(x - 0.0) < 1e-8 else (float(w) if abs(x - w) < 1e-8 else x)
        cy = 0.0 if abs(y - 0.0) < 1e-8 else (float(h) if abs(y - h) < 1e-8 else y)
        found = False
        for (xx,yy) in out:
            if abs(xx - cx) < 1e-7 and abs(yy - cy) < 1e-7:
                found = True
                break
        if not found:
            out.append((cx, cy))
    # usually sort for consistency
    out_sorted = sorted(out, key=lambda p: (p[0], p[1]))
    return out_sorted

def _perp_bisector(p1: Point, p2: Point) -> Tuple[Tuple[float,float], Tuple[float,float]]:
    """Return (midpoint, direction) for perpendicular bisector line of p1-p2"""
    x1,y1 = p1.x, p1.y
    x2,y2 = p2.x, p2.y
    mx = (x1 + x2) / 2.0
    my = (y1 + y2) / 2.0
    dx = x2 - x1
    dy = y2 - y1
    # perpendicular direction
    dirx = -dy
    diry = dx
    # normalize for stability (not required)
    norm = math.hypot(dirx, diry)
    if norm > EPS:
        dirx /= norm
        diry /= norm
    return ( (mx, my), (dirx, diry) )


def _dist_sq(p: Tuple[float,float], q: Tuple[float,float]) -> float:
    return (p[0]-q[0])**2 + (p[1]-q[1])**2



def _voronoi_two_points(p1: Point, p2: Point, w: int, h: int) -> List[Edge]:
    # 1. 兩點重疊：理論上 Voronoi 不會有「中垂線」，這裡直接不畫線
    if abs(p1.x - p2.x) < EPS and abs(p1.y - p2.y) < EPS:
        return []

    # 2. 一般情況：兩點的中垂線
    mid, dirv = _perp_bisector(p1, p2)
    inters = _intersect_line_with_rect(mid, dirv, w, h)
    if len(inters) < 2:
        # 理論上不太會發生，當成退化情況
        return []

    # pick two farthest points among intersections
    if len(inters) > 2:
        inters = sorted(inters, key=lambda t: (t[0], t[1]))
        A = inters[0]
        B = inters[-1]
    else:
        A, B = inters[0], inters[1]

    return [Edge(Point(A[0], A[1]), Point(B[0], B[1]))]


def _filter_segment_by_closest_pair(A: Tuple[float,float], B: Tuple[float,float],
                                    site_a: Point, site_b: Point, all_sites: List[Point],
                                    samples: int = 200) -> List[Tuple[Tuple[float,float], Tuple[float,float]]]:
    """
    在線段 AB 上取樣，找出「site_a 與 site_b 為最近兩點」的區間。
    修正：使用二分逼近法 (Binary Search) 來精確定位區間的起點與終點，
          解決採樣導致線段無法完美連接的問題。
    """
    ax, ay = A
    bx, by = B
    seg_len = math.hypot(bx-ax, by-ay)
    if seg_len < 1e-9:
        return []

    # 1. 定義檢查函式：給定參數 t (0~1)，回傳該點是否 valid
    # valid 條件：該點最近的兩個 site 必須是 site_a 和 site_b
    def is_valid(t: float) -> bool:
        x = ax + t*(bx-ax)
        y = ay + t*(by-ay)
        
        # 為了效能，先找出最近的前三個點
        dists = []
        for s in all_sites:
            d = (x - s.x)**2 + (y - s.y)**2
            dists.append((d, s))
        
        # 部分排序，只取前三名
        import heapq
        closest_3 = heapq.nsmallest(3, dists, key=lambda x: x[0])
        
        if len(closest_3) < 2: 
            return True # 只有不到兩點，視為 valid
            
        s0 = closest_3[0][1]
        s1 = closest_3[1][1]

        # 檢查最近兩點是否為目標 pair
        cond_pair = ((s0 is site_a and s1 is site_b) or (s0 is site_b and s1 is site_a))
        
        # 檢查是否嚴格小於第三近 (避免剛好落在 Voronoi Vertex 時浮點數誤差導致判定跳動)
        if len(closest_3) >= 3:
            # 若第一二名距離與第三名太近，我們通常視為邊界
            # 但此處只需判定 pair 正確性
             strictly_closer = (closest_3[0][0] < closest_3[2][0] - 1e-7)
        else:
             strictly_closer = True
             
        return cond_pair and strictly_closer

    # 2. 二分搜尋函式：在 t_in (valid) 與 t_out (invalid) 之間找邊界
    def find_boundary(t_in: float, t_out: float) -> float:
        low = t_in
        high = t_out
        for _ in range(20): # 2^20 精度已經足夠 pixel perfect
            mid = (low + high) * 0.5
            if is_valid(mid):
                low = mid
            else:
                high = mid
        return low # 回傳 valid 的那一側邊界

    # 3. 粗略採樣，找出狀態變換區間
    # 動態調整 samples 數量，避免短線段採樣不足
    samples = max(60, int(seg_len / 4.0)) 
    ts = [i/(samples-1) for i in range(samples)]
    
    mask = []
    for t in ts:
        mask.append(is_valid(t))

    segs = []
    in_seg = False
    seg_start_t = 0.0

    for i in range(samples):
        curr_valid = mask[i]
        curr_t = ts[i]

        if curr_valid and not in_seg:
            # 剛進入有效區段 (False -> True)
            in_seg = True
            if i == 0:
                seg_start_t = 0.0
            else:
                # 邊界在 ts[i-1] (False) 與 ts[i] (True) 之間
                # 我們要找的是 valid 的開始點 (靠近 ts[i-1] 的那側)
                # find_boundary 找的是 valid 的極限，這裡稍微反向思考：
                # 其實就是找 False/True 交界。
                # 我們定義一個 helper 找 True 的邊界
                
                # 在 [i-1, i] 之間二分
                # t_out = ts[i-1], t_in = ts[i]
                # find_boundary 會回傳靠近 t_out 但仍是 valid 的點 (不對，上面的 find_boundary 是逼近 valid)
                
                # 修正邏輯：
                # 我們要在 [ts[i-1], ts[i]] 找第一個變成 True 的點
                _low, _high = ts[i-1], ts[i]
                for _ in range(20):
                    _mid = (_low + _high) * 0.5
                    if is_valid(_mid):
                        _high = _mid # True，往左縮
                    else:
                        _low = _mid  # False，往右縮
                seg_start_t = _high # 取 True 的那側

        elif not curr_valid and in_seg:
            # 剛離開有效區段 (True -> False)
            in_seg = False
            # 邊界在 ts[i-1] (True) 與 ts[i] (False) 之間
            # 尋找 valid 的結束點
            seg_end_t = find_boundary(ts[i-1], ts[i])
            
            spt = (ax + seg_start_t*(bx-ax), ay + seg_start_t*(by-ay))
            ept = (ax + seg_end_t*(bx-ax), ay + seg_end_t*(by-ay))
            segs.append((spt, ept))

    # 若結束時仍在有效區段，終點就是 1.0
    if in_seg:
        spt = (ax + seg_start_t*(bx-ax), ay + seg_start_t*(by-ay))
        ept = (bx, by)
        segs.append((spt, ept))

    # 過濾極短線段
    final_segs = []
    for s, e in segs:
        if math.hypot(e[0]-s[0], e[1]-s[1]) > 1e-5:
            final_segs.append((s, e))
            
    return final_segs

# -------------------------------------------------------------------------


def _side_value(x: float,
                y: float,
                left_sites: List[Point],
                right_sites: List[Point]) -> float:
    """
    回傳 dR - dL：
      dL = 到所有 left_sites 中最近點的距離平方
      dR = 到所有 right_sites 中最近點的距離平方

    > 0 代表「比較靠左側」（離 left 比 right 近）
    < 0 代表「比較靠右側」
    約等於 0 代表落在 HP 附近。
    """
    dL = float("inf")
    for p in left_sites:
        d = (x - p.x) * (x - p.x) + (y - p.y) * (y - p.y)
        if d < dL:
            dL = d

    dR = float("inf")
    for p in right_sites:
        d = (x - p.x) * (x - p.x) + (y - p.y) * (y - p.y)
        if d < dR:
            dR = d

    return dR - dL


def _trim_edges_by_hp(edges: List[Edge],
                      left_sites: List[Point],
                      right_sites: List[Point],
                      keep_left: bool) -> List[Edge]:
    """
    利用「左右兩側點的最近距離」來判斷邊在 HP 的哪一側，並做 trimming。

    新版本：
      1. 沿著每條 edge 做取樣，計算 f(t) = dR - dL。
      2. 用 is_keep(f) 決定每個 sample 是否屬於保留側。
      3. 只要在 [t_i, t_{i+1}] 裡面發生 keep ↔ drop，就在該小區間裡
         用二分法找出 f=0 的邊界 t*，把 segment 端點對齊到這個 t*。
      這樣可以避免「交點附近因 sample 格點而產生的小洞」，同時保留
      前面修正掉整條邊被吃掉的問題。
    """
    if not edges:
        return []

    tol = 1e-6

    def side_value(x: float, y: float) -> float:
        return _side_value(x, y, left_sites, right_sites)

    def is_keep(val: float) -> bool:
        # keep_left=True  → 保留「左側或在 HP 附近」
        # keep_left=False → 保留「右側或在 HP 附近」
        if keep_left:
            return val >= -tol
        else:
            return val <= tol

    trimmed: List[Edge] = []

    for e in edges:
        ax, ay = e.start.x, e.start.y
        bx, by = e.end.x,   e.end.y

        # 根據邊長自動決定取樣數 ─ 長的邊多切幾段，短的邊少一點
        seg_len = math.hypot(bx - ax, by - ay)
        samples = max(60, int(seg_len / 8.0))   # 60 起跳，邊長越長取樣越密
        if samples < 3:
            samples = 3

        ts = [i / (samples - 1) for i in range(samples)]
        fs = []
        keep_flags = []

        for t in ts:
            x = ax + t * (bx - ax)
            y = ay + t * (by - ay)
            v = side_value(x, y)
            fs.append(v)
            keep_flags.append(is_keep(v))

        # helper: 在 [t_keep, t_drop] 之間二分搜尋 f=0 的邊界點（靠近 keep 側）
        def bisect_boundary(t_keep: float, t_drop: float) -> float:
            lo = t_keep
            hi = t_drop
            for _ in range(30):
                mid = 0.5 * (lo + hi)
                xm = ax + mid * (bx - ax)
                ym = ay + mid * (by - ay)
                fm = side_value(xm, ym)
                if is_keep(fm):
                    lo = mid
                else:
                    hi = mid
            return lo  # lo 位於保留側，且非常靠近 HP

        current_start_t: Optional[float] = None

        for i in range(samples - 1):
            t0, t1 = ts[i], ts[i + 1]
            k0, k1 = keep_flags[i], keep_flags[i + 1]

            # 若目前在 keep 區段開頭，記住起始 t
            if k0 and current_start_t is None:
                current_start_t = t0

            if k0 == k1:
                # 這一小段 [t0, t1] 裡沒有 keep/drop 切換，什麼都不用做
                continue

            # 發生 keep ↔ drop 的切換，需要在 [t0, t1] 裡找邊界 t*
            if k0 and (not k1):
                # True → False：離開保留區
                t_boundary = bisect_boundary(t_keep=t0, t_drop=t1)
                if current_start_t is None:
                    current_start_t = t0
                sx = ax + current_start_t * (bx - ax)
                sy = ay + current_start_t * (by - ay)
                ex = ax + t_boundary * (bx - ax)
                ey = ay + t_boundary * (by - ay)
                if math.hypot(ex - sx, ey - sy) > 1e-6:
                    trimmed.append(Edge(Point(sx, sy), Point(ex, ey)))
                current_start_t = None
            elif (not k0) and k1:
                # False → True：進入保留區
                t_boundary = bisect_boundary(t_keep=t1, t_drop=t0)
                current_start_t = t_boundary

        # 走完所有小區間後，如果還在保留區，就把最後一段補完到 t=1
        if current_start_t is not None and keep_flags[-1]:
            sx = ax + current_start_t * (bx - ax)
            sy = ay + current_start_t * (by - ay)
            ex = bx
            ey = by
            if math.hypot(ex - sx, ey - sy) > 1e-6:
                trimmed.append(Edge(Point(sx, sy), Point(ex, ey)))

    return trimmed




def _voronoi_three_points(points: List[Point], w: int, h: int) -> List[Edge]:
    """
    三個 site 的 Voronoi：
      - 一般情況：三條邊交於一個 circumcenter
      - 共線情況：退化成「三對 pair 的中垂線被裁剪」的組合
    """
    p1, p2, p3 = points[0], points[1], points[2]

    edges: List[Edge] = []

    # 嘗試找三角形的外心
    cc = _circumcenter(p1, p2, p3)

    # 如果共線（沒有有限外心）→ 使用「pair + sampling」版本
    if cc is None:
        site_list = [p1, p2, p3]
        pairs = [(p1,p2), (p1,p3), (p2,p3)]
        for a, b in pairs:
            mid, dirv = _perp_bisector(a, b)
            inters = _intersect_line_with_rect(mid, dirv, w, h)
            if len(inters) < 2:
                continue
            A, B = inters[0], inters[-1]
            segs = _filter_segment_by_closest_pair(A, B, a, b, site_list, samples=400)
            for (sx,sy), (ex,ey) in segs:
                edges.append(Edge(Point(sx,sy), Point(ex,ey)))
        return edges

    # 有外心：外心就是三條 Voronoi edge 的交點
    site_list = [p1, p2, p3]
    pairs = [(p1,p2), (p2,p3), (p3,p1)]

    for a, b in pairs:
        # 以外心為通過點，方向是 (a,b) 的中垂線方向
        mid_tmp, dirv = _perp_bisector(a, b)
        inters = _intersect_line_with_rect(cc, dirv, w, h)
        if len(inters) < 2:
            continue

        A, B = inters[0], inters[-1]

        # 過濾出「最近兩個 site 是 a,b」的那一段
        segs = _filter_segment_by_closest_pair(A, B, a, b, site_list, samples=400)
        for (sx,sy), (ex,ey) in segs:
            edges.append(Edge(Point(sx,sy), Point(ex,ey)))

    return edges
def _convex_hull_simple(pts: List[Point]) -> List[Point]:
    """
    給 n<=3 用的簡單凸包：用單調鏈 (monotone chain) 做一個小 hull。
    """
    if len(pts) <= 1:
        return pts[:]

    pts_sorted = sorted(pts, key=lambda p: (p.x, p.y))

    def cross(o: Point, a: Point, b: Point) -> float:
        return (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x)

    lower: List[Point] = []
    for p in pts_sorted:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    upper: List[Point] = []
    for p in reversed(pts_sorted):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    hull = lower[:-1] + upper[:-1]
    return hull
def _circumcenter(a: Point, b: Point, c: Point) -> Optional[Tuple[float,float]]:
    """
    Compute circumcenter of triangle abc. Return None if collinear.
    """
    x1,y1 = a.x, a.y
    x2,y2 = b.x, b.y
    x3,y3 = c.x, c.y
    d = 2 * (x1*(y2-y3) + x2*(y3-y1) + x3*(y1-y2))
    if abs(d) < EPS:
        return None
    ux = ((x1*x1 + y1*y1)*(y2-y3) + (x2*x2 + y2*y2)*(y3-y1) + (x3*x3 + y3*y3)*(y1-y2)) / d
    uy = ((x1*x1 + y1*y1)*(x3-x2) + (x2*x2 + y2*y2)*(x1-x3) + (x3*x3 + y3*y3)*(x2-x1)) / d
    return (ux, uy)

def _dist_sq(p: Tuple[float,float], q: Tuple[float,float]) -> float:
    return (p[0]-q[0])**2 + (p[1]-q[1])**2




