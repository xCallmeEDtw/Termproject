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


