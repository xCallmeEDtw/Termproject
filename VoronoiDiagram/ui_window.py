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
