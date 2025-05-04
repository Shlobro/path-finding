import sys

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
    QToolBar, QPushButton, QSizePolicy
)
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QPolygonF
from PySide6.QtCore import Qt, QPointF


def _area2(a: QPointF, b: QPointF, c: QPointF) -> float:
    """Twice the signed area of triangle ABC."""
    return (b.x() - a.x()) * (c.y() - a.y()) - (b.y() - a.y()) * (c.x() - a.x())


def _is_convex(a: QPointF, b: QPointF, c: QPointF) -> bool:
    """True if angle ABC is convex assuming CCW winding."""
    return _area2(a, b, c) > 0


def _point_in_triangle(p: QPointF, a: QPointF, b: QPointF, c: QPointF) -> bool:
    """Barycentric / area‐sum test."""
    A = abs(_area2(a, b, c))
    A1 = abs(_area2(p, b, c))
    A2 = abs(_area2(a, p, c))
    A3 = abs(_area2(a, b, p))
    return abs((A1 + A2 + A3) - A) < 1e-6


def ear_clip(vertices: list[QPointF]) -> list[tuple[QPointF, QPointF, QPointF]]:
    """
    Simple ear‐clipping triangulation.
    Returns a list of triangles (each a 3-tuple of QPointF) covering the polygon.
    """
    pts = vertices.copy()
    n = len(pts)
    if n < 3:
        return []

    # ensure CCW winding
    area_sum = 0.0
    for i in range(n):
        j = (i + 1) % n
        area_sum += pts[i].x() * pts[j].y() - pts[j].x() * pts[i].y()
    if area_sum < 0:
        pts.reverse()

    result: list[tuple[QPointF, QPointF, QPointF]] = []
    V = pts.copy()
    while len(V) > 3:
        ear_found = False
        for i in range(len(V)):
            prev = V[(i - 1) % len(V)]
            curr = V[i]
            nxt = V[(i + 1) % len(V)]
            if not _is_convex(prev, curr, nxt):
                continue
            # check no other vertex lies inside this triangle
            if any(
                p is not prev and p is not curr and p is not nxt
                and _point_in_triangle(p, prev, curr, nxt)
                for p in V
            ):
                continue
            # found an ear
            result.append((prev, curr, nxt))
            del V[i]
            ear_found = True
            break
        if not ear_found:
            # polygon might be self‐intersecting or degenerate
            break

    # the final remaining triangle
    if len(V) == 3:
        result.append((V[0], V[1], V[2]))
    return result


class GraphicsView(QGraphicsView):
    def __init__(self, scene: QGraphicsScene):
        super().__init__(scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)

    def wheelEvent(self, ev):
        if ev.modifiers() & Qt.ControlModifier:
            factor = 1.25 if ev.angleDelta().y() > 0 else 0.8
            self.scale(factor, factor)
        else:
            super().wheelEvent(ev)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            pt = ev.position().toPoint()
            scene_pt = self.mapToScene(pt)
            self.window().add_point(scene_pt)
        else:
            super().mousePressEvent(ev)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Convex‐Decomposition Drawer")
        self.resize(800, 600)

        # Scene & View
        self.scene = QGraphicsScene(self)
        self.view = GraphicsView(self.scene)
        self.setCentralWidget(self.view)

        # State
        self.current_points: list[QPointF] = []
        self.last_polygon_points: list[QPointF] = []
        self.outline_pen = QPen(QColor("#0066CC"), 2)

        # Toolbar
        tb = self.addToolBar("Tools")
        tb.setMovable(False)

        btn_close = QPushButton("Close Shape")
        btn_close.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_close.clicked.connect(self.close_shape)
        tb.addWidget(btn_close)

        btn_split = QPushButton("Split into Convex Parts")
        btn_split.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_split.clicked.connect(self.decompose_shape)
        tb.addWidget(btn_split)

    def add_point(self, pos: QPointF):
        print(f"Added point ({pos.x():.1f}, {pos.y():.1f})")
        r = 4
        self.scene.addEllipse(
            pos.x() - r, pos.y() - r, r * 2, r * 2,
            QPen(Qt.NoPen), QBrush(QColor("#CC0000"))
        )
        if self.current_points:
            prev = self.current_points[-1]
            self.scene.addLine(prev.x(), prev.y(), pos.x(), pos.y(), self.outline_pen)
        self.current_points.append(pos)

    def close_shape(self):
        if len(self.current_points) < 3:
            print("Need ≥3 points to close.")
            return
        print("Shape closed.")
        first = self.current_points[0]
        last = self.current_points[-1]
        self.scene.addLine(last.x(), last.y(), first.x(), first.y(), self.outline_pen)
        # store and reset
        self.last_polygon_points = self.current_points.copy()
        self.current_points.clear()

    def decompose_shape(self):
        if not self.last_polygon_points:
            print("Draw and close a shape first.")
            return
        print("Decomposing into convex parts…")
        tris = ear_clip(self.last_polygon_points)
        print(f"  Produced {len(tris)} triangles.")

        # redraw: clear everything
        self.scene.clear()

        # 1) draw original outline
        n = len(self.last_polygon_points)
        for i in range(n):
            p1 = self.last_polygon_points[i]
            p2 = self.last_polygon_points[(i + 1) % n]
            self.scene.addLine(p1.x(), p1.y(), p2.x(), p2.y(), self.outline_pen)

        # 2) overlay each triangle
        for idx, (a, b, c) in enumerate(tris):
            poly = QPolygonF([a, b, c])
            color = QColor.fromHsv(int(360 * idx / len(tris)), 200, 200, 120)
            pen = QPen(color.darker(), 1)
            brush = QBrush(color)
            self.scene.addPolygon(poly, pen, brush)

    # no scene‐rect locking or fitInView: you can zoom in/out with Ctrl + wheel


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
