import sys
import math
import random

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
    QToolBar, QPushButton, QSizePolicy
)
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QPolygonF
from PySide6.QtCore import Qt, QPointF


def _area2(a: QPointF, b: QPointF, c: QPointF) -> float:
    """Twice the signed area of triangle ABC."""
    return (b.x()-a.x())*(c.y()-a.y()) - (b.y()-a.y())*(c.x()-a.x())


def ear_clip(vertices: list[QPointF]) -> list[tuple[QPointF,QPointF,QPointF]]:
    """Simple ear-clipping triangulation (CCW)."""
    pts = vertices.copy()
    # ensure CCW
    area_sum = sum(pts[i].x()*pts[(i+1)%len(pts)].y()
                   - pts[(i+1)%len(pts)].x()*pts[i].y()
                   for i in range(len(pts)))
    if area_sum < 0:
        pts.reverse()

    def is_convex(a,b,c):
        return _area2(a,b,c) > 0

    def point_in_tri(p,a,b,c):
        A = abs(_area2(a,b,c))
        A1 = abs(_area2(p,b,c))
        A2 = abs(_area2(a,p,c))
        A3 = abs(_area2(a,b,p))
        return abs((A1+A2+A3)-A) < 1e-6

    V = pts.copy()
    result = []
    while len(V) > 3:
        for i in range(len(V)):
            prev, curr, nxt = V[i-1], V[i], V[(i+1)%len(V)]
            if not is_convex(prev,curr,nxt):
                continue
            if any(p not in (prev, curr, nxt) and point_in_tri(p,prev,curr,nxt)
                   for p in V):
                continue
            result.append((prev,curr,nxt))
            del V[i]
            break
        else:
            # no ear found → stop
            break
    if len(V)==3:
        result.append((V[0],V[1],V[2]))
    return result


def unique_points(pts: list[QPointF]) -> list[QPointF]:
    """Return a list of points without duplicates (exact match)."""
    unique = []
    for p in pts:
        if not any(p.x()==q.x() and p.y()==q.y() for q in unique):
            unique.append(p)
    return unique


def merge_convex(polygons: list[list[QPointF]]) -> list[list[QPointF]]:
    """
    Greedily merge any two polygons sharing an edge if their union is convex.
    """
    merged = True
    while merged:
        merged = False
        n = len(polygons)
        for i in range(n):
            for j in range(i+1, n):
                P, Q = polygons[i], polygons[j]
                # find shared edge endpoints
                shared = [p for p in P if any(p.x()==q.x() and p.y()==q.y() for q in Q)]
                if len(shared) != 2:
                    continue
                # union of vertices
                all_pts = unique_points(P + Q)
                # compute centroid
                cx = sum(p.x() for p in all_pts)/len(all_pts)
                cy = sum(p.y() for p in all_pts)/len(all_pts)
                # sort CCW around centroid
                all_pts.sort(key=lambda p: math.atan2(p.y()-cy, p.x()-cx))
                # test convexity
                is_conv = True
                m = len(all_pts)
                for k in range(m):
                    a,b,c = all_pts[k-1], all_pts[k], all_pts[(k+1)%m]
                    if _area2(a,b,c) <= 0:
                        is_conv = False
                        break
                if not is_conv:
                    continue
                # perform merge
                new_poly = all_pts
                # remove the two old polygons (pop higher index first)
                polygons.pop(j)
                polygons.pop(i)
                polygons.append(new_poly)
                merged = True
                break
            if merged:
                break
    return polygons


class GraphicsView(QGraphicsView):
    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setAlignment(Qt.AlignLeft|Qt.AlignTop)

    def wheelEvent(self, ev):
        if ev.modifiers() & Qt.ControlModifier:
            f = 1.25 if ev.angleDelta().y()>0 else 0.8
            self.scale(f,f)
        else:
            super().wheelEvent(ev)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            pt = ev.position().toPoint()
            self.window().add_point(self.mapToScene(pt))
        else:
            super().mousePressEvent(ev)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Largest Convex Decomposition")
        self.resize(800,600)

        self.scene = QGraphicsScene(self)
        self.view = GraphicsView(self.scene)
        self.setCentralWidget(self.view)

        self.current = []         # points being drawn
        self.last_closed = []     # last closed polygon
        self.out_pen = QPen(QColor("#0066CC"),2)

        tb = QToolBar()
        tb.setMovable(False)
        self.addToolBar(tb)

        btn_close = QPushButton("Close Shape")
        btn_close.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_close.clicked.connect(self.close_shape)
        tb.addWidget(btn_close)

        btn_split = QPushButton("Split into Largest Convex Shapes")
        btn_split.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_split.clicked.connect(self.decompose)
        tb.addWidget(btn_split)

    def add_point(self, p: QPointF):
        # add a vertex
        self.scene.addEllipse(p.x()-4, p.y()-4, 8, 8,
                              QPen(Qt.NoPen), QBrush(QColor("#CC0000")))
        if self.current:
            prev = self.current[-1]
            self.scene.addLine(prev.x(), prev.y(), p.x(), p.y(), self.out_pen)
        self.current.append(p)

    def close_shape(self):
        if len(self.current) < 3:
            return
        first, last = self.current[0], self.current[-1]
        self.scene.addLine(last.x(), last.y(), first.x(), first.y(), self.out_pen)
        self.last_closed = self.current.copy()
        self.current.clear()

    def decompose(self):
        if not self.last_closed:
            return
        # 1) triangulate
        tris = ear_clip(self.last_closed)
        polys = [list(tri) for tri in tris]
        # 2) merge greedily
        merged = merge_convex(polys)
        # 3) redraw everything
        self.scene.clear()
        # outline
        n = len(self.last_closed)
        for i in range(n):
            a = self.last_closed[i]
            b = self.last_closed[(i+1)%n]
            self.scene.addLine(a.x(), a.y(), b.x(), b.y(), self.out_pen)
        # draw merged pieces
        for idx, poly in enumerate(merged):
            qpoly = QPolygonF(poly)
            color = QColor.fromHsv(int(360*idx/len(merged)), 200,200,120)
            pen   = QPen(color.darker(),1)
            brush = QBrush(color)
            self.scene.addPolygon(qpoly, pen, brush)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())

