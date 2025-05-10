import sys
import math
import random

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
    QToolBar, QPushButton, QSizePolicy, QVBoxLayout, QHBoxLayout,
    QWidget, QLabel, QStatusBar, QComboBox, QDoubleSpinBox
)
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QPolygonF
from PySide6.QtCore import Qt, QPointF, QTimer, QSize, QLineF


def _area2(a: QPointF, b: QPointF, c: QPointF) -> float:
    """Twice the signed area of triangle ABC."""
    return (b.x() - a.x()) * (c.y() - a.y()) - (b.y() - a.y()) * (c.x() - a.x())


def ear_clip(vertices: list[QPointF]) -> list[tuple[QPointF, QPointF, QPointF]]:
    """Simple ear-clipping triangulation (CCW)."""
    if len(vertices) < 3:
        return []

    pts = vertices.copy()
    # ensure CCW
    area_sum = sum(pts[i].x() * pts[(i + 1) % len(pts)].y()
                   - pts[(i + 1) % len(pts)].x() * pts[i].y()
                   for i in range(len(pts)))
    if area_sum < 0:
        pts.reverse()

    def is_convex(a, b, c):
        return _area2(a, b, c) > 0

    def point_in_tri(p, a, b, c):
        """Check if point p is inside triangle abc."""
        A = abs(_area2(a, b, c))
        A1 = abs(_area2(p, b, c))
        A2 = abs(_area2(a, p, c))
        A3 = abs(_area2(a, b, p))
        return abs((A1 + A2 + A3) - A) < 1e-6

    V = pts.copy()
    result = []
    iterations = 0
    max_iterations = len(V) * 2  # Safety limit

    while len(V) > 3 and iterations < max_iterations:
        iterations += 1
        for i in range(len(V)):
            prev, curr, nxt = V[i - 1], V[i], V[(i + 1) % len(V)]
            if not is_convex(prev, curr, nxt):
                continue

            # Check if any other vertex is inside this ear
            is_ear = True
            for p in V:
                if p not in (prev, curr, nxt) and point_in_tri(p, prev, curr, nxt):
                    is_ear = False
                    break

            if is_ear:
                result.append((prev, curr, nxt))
                V.remove(curr)
                break
        else:
            # No ear found, avoid infinite loop
            break

    if len(V) == 3:
        result.append((V[0], V[1], V[2]))

    return result


def unique_points(pts: list[QPointF]) -> list[QPointF]:
    """Return a list of points without duplicates (with small epsilon)."""
    EPSILON = 1e-6
    unique = []
    for p in pts:
        if not any(abs(p.x() - q.x()) < EPSILON and abs(p.y() - q.y()) < EPSILON for q in unique):
            unique.append(p)
    return unique


def merge_convex(polygons: list[list[QPointF]]) -> list[list[QPointF]]:
    """
    Greedily merge any two polygons sharing an edge if their union is convex.
    """
    if not polygons:
        return []

    # Make a copy to avoid modifying the input
    polygons = [poly.copy() for poly in polygons]

    merged = True
    max_iterations = 100  # Safety limit
    iteration = 0

    while merged and iteration < max_iterations:
        iteration += 1
        merged = False
        n = len(polygons)

        for i in range(n):
            if merged:
                break

            for j in range(i + 1, n):
                P, Q = polygons[i], polygons[j]

                # Find shared edge endpoints (with small epsilon)
                EPSILON = 1e-6
                shared = []
                for p in P:
                    for q in Q:
                        if abs(p.x() - q.x()) < EPSILON and abs(p.y() - q.y()) < EPSILON:
                            if p not in shared:  # Avoid duplicates
                                shared.append(p)

                if len(shared) != 2:
                    continue

                # Check if shared points form an edge in both polygons
                def is_edge(points, a, b):
                    """Check if a-b is an edge in the polygon."""
                    n = len(points)
                    for i in range(n):
                        p1, p2 = points[i], points[(i + 1) % n]
                        if ((abs(p1.x() - a.x()) < EPSILON and abs(p1.y() - a.y()) < EPSILON and
                             abs(p2.x() - b.x()) < EPSILON and abs(p2.y() - b.y()) < EPSILON) or
                                (abs(p1.x() - b.x()) < EPSILON and abs(p1.y() - b.y()) < EPSILON and
                                 abs(p2.x() - a.x()) < EPSILON and abs(p2.y() - a.y()) < EPSILON)):
                            return True
                    return False

                if not (is_edge(P, shared[0], shared[1]) and is_edge(Q, shared[0], shared[1])):
                    continue

                # Union of vertices
                all_pts = unique_points(P + Q)

                # Compute centroid (for sorting vertices)
                cx = sum(p.x() for p in all_pts) / len(all_pts)
                cy = sum(p.y() for p in all_pts) / len(all_pts)

                # Sort CCW around centroid
                all_pts.sort(key=lambda p: math.atan2(p.y() - cy, p.x() - cx))

                # Test convexity
                is_conv = True
                m = len(all_pts)
                for k in range(m):
                    a, b, c = all_pts[k - 1], all_pts[k], all_pts[(k + 1) % m]
                    if _area2(a, b, c) <= 0:
                        is_conv = False
                        break

                if not is_conv:
                    continue

                # Perform merge
                new_poly = all_pts
                # Remove the two old polygons (pop higher index first)
                polygons.pop(j)
                polygons.pop(i)
                polygons.append(new_poly)
                merged = True
                break

    return polygons


class GraphicsView(QGraphicsView):
    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.scale(1, -1)  # Flip y-axis for mathematical coordinate system

        # Set scene rect to be large enough
        self.setSceneRect(-5000, -5000, 10000, 10000)

        # Track if Control key is pressed (for point placement vs. pan)
        self.ctrl_pressed = False

    def wheelEvent(self, ev):
        if ev.modifiers() & Qt.ControlModifier:
            # Zoom
            zoom_factor = 1.25 if ev.angleDelta().y() > 0 else 0.8
            self.scale(zoom_factor, zoom_factor)
        else:
            # Pan
            super().wheelEvent(ev)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Control:
            self.ctrl_pressed = True
            self.setDragMode(QGraphicsView.NoDrag)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Control:
            self.ctrl_pressed = False
            self.setDragMode(QGraphicsView.ScrollHandDrag)
        super().keyReleaseEvent(event)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and self.ctrl_pressed:
            pt = ev.position().toPoint()
            self.window().add_point(self.mapToScene(pt))
        else:
            super().mousePressEvent(ev)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Largest Convex Decomposition")
        self.resize(1000, 800)

        # Main widgets
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)

        # Set up the graphics view
        self.scene = QGraphicsScene(self)
        self.view = GraphicsView(self.scene)
        main_layout.addWidget(self.view)

        # Control panel
        control_panel = QWidget()
        control_layout = QHBoxLayout(control_panel)
        control_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(control_panel)

        # Colors and pens
        self.setup_colors()

        # Toolbar
        self.setup_toolbar()

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.point_count_label = QLabel("Points: 0")
        self.status_bar.addPermanentWidget(self.point_count_label)

        # Setup instructions
        self.display_instructions()

        # Data
        self.current = []  # points being drawn
        self.last_closed = []  # last closed polygon
        self.convex_pieces = []  # decomposed convex pieces

        # Grid
        self.draw_grid()

        self.setCentralWidget(central_widget)

    def setup_colors(self):
        # Define colors for UI elements
        self.grid_color = QColor(240, 240, 240)
        self.point_color = QColor(204, 0, 0)
        self.edge_color = QColor(0, 102, 204)
        self.outline_color = QColor(0, 0, 0)

        # Define pens and brushes
        self.grid_pen = QPen(self.grid_color, 1, Qt.DotLine)
        self.point_pen = QPen(Qt.NoPen)
        self.point_brush = QBrush(self.point_color)
        self.edge_pen = QPen(self.edge_color, 2)
        self.outline_pen = QPen(self.outline_color, 2.5)
        self.temp_edge_pen = QPen(QColor(100, 100, 100, 150), 1, Qt.DashLine)

    def setup_toolbar(self):
        tb = QToolBar()
        tb.setMovable(False)
        tb.setIconSize(QSize(32, 32))
        self.addToolBar(tb)

        # Close / Decompose / Clear / Undo
        btn_close = QPushButton("Close Shape")
        btn_close.setToolTip("Connect the last point to the first point")
        btn_close.clicked.connect(self.close_shape)
        tb.addWidget(btn_close)

        btn_decompose = QPushButton("Decompose")
        btn_decompose.setToolTip("Split into largest convex pieces")
        btn_decompose.clicked.connect(self.decompose)
        tb.addWidget(btn_decompose)

        btn_clear = QPushButton("Clear All")
        btn_clear.setToolTip("Clear all points and shapes")
        btn_clear.clicked.connect(self.clear_all)
        tb.addWidget(btn_clear)

        btn_undo = QPushButton("Undo Point")
        btn_undo.setToolTip("Remove the last placed point")
        btn_undo.clicked.connect(self.undo_point)
        tb.addWidget(btn_undo)

        tb.addSeparator()

        # Color selector
        color_label = QLabel("Color Scheme:")
        tb.addWidget(color_label)

        self.color_combo = QComboBox()
        self.color_combo.addItems(["Rainbow", "Blue", "Green", "Red", "Pastel"])
        self.color_combo.currentIndexChanged.connect(self.update_colors)
        tb.addWidget(self.color_combo)

        tb.addSeparator()

        # Help text
        help_label = QLabel("Ctrl+Click to add points | Drag to pan | Ctrl+Wheel to zoom")
        help_label.setStyleSheet("color: #666;")
        tb.addWidget(help_label)

        tb.addSeparator()

        # ─────── Path Generation Controls ───────
        spacing_label = QLabel("Spacing:")
        tb.addWidget(spacing_label)

        self.spacing_spin = QDoubleSpinBox()
        self.spacing_spin.setRange(1.0, 1000.0)
        self.spacing_spin.setValue(20.0)
        self.spacing_spin.setSuffix(" units")
        tb.addWidget(self.spacing_spin)

        btn_gen = QPushButton("Generate Path")
        btn_gen.setToolTip("Create lawnmower paths in each convex piece")
        btn_gen.clicked.connect(self.generate_paths)
        tb.addWidget(btn_gen)

    def generate_paths(self):
        """Generate a continuous lawnmower path through each convex piece."""
        if not self.convex_pieces:
            self.status_bar.showMessage("No convex pieces to path-plan", 3000)
            return

        # remove old path‐lines
        for item in list(self.scene.items()):
            if hasattr(item, 'isPathLine') and item.isPathLine:
                self.scene.removeItem(item)

        spacing = self.spacing_spin.value()
        pen = QPen(QColor(50, 50, 50, 200), 1, Qt.DashLine)

        for poly in self.convex_pieces:
            stripes = self.compute_lawnmower(poly, spacing)
            # ensure sorted bottom→top
            stripes.sort(key=lambda line: line.y1())

            prev_endpoint = None
            for idx, seg in enumerate(stripes):
                p_start = seg.p1()
                p_end = seg.p2()

                # alternate direction on each stripe
                if idx % 2 == 1:
                    p_start, p_end = p_end, p_start

                # connect from previous stripe
                if prev_endpoint is not None:
                    conn = QLineF(prev_endpoint, p_start)
                    gi = self.scene.addLine(conn, pen)
                    gi.isPathLine = True

                # draw the stripe
                stripe_line = QLineF(p_start, p_end)
                gi = self.scene.addLine(stripe_line, pen)
                gi.isPathLine = True

                prev_endpoint = p_end

        self.status_bar.showMessage("Lawnmower path generated", 3000)

    def draw_grid(self, size=50):
        """Draw a grid on the scene for visual reference."""
        # Clear existing grid items
        for item in self.scene.items():
            if hasattr(item, 'isGridItem') and item.isGridItem:
                self.scene.removeItem(item)

        # Draw grid lines
        rect = self.view.sceneRect()
        left = math.floor(rect.left() / size) * size
        right = math.ceil(rect.right() / size) * size
        top = math.floor(rect.top() / size) * size
        bottom = math.ceil(rect.bottom() / size) * size

        # Vertical lines
        for x in range(int(left), int(right) + size, size):
            line = self.scene.addLine(x, top, x, bottom, self.grid_pen)
            line.isGridItem = True

        # Horizontal lines
        for y in range(int(top), int(bottom) + size, size):
            line = self.scene.addLine(left, y, right, y, self.grid_pen)
            line.isGridItem = True

    def compute_lawnmower(self, poly: list[QPointF], spacing: float) -> list[QLineF]:
        """
        For a convex polygon (list of QPointF), return horizontal QLineF segments
        spaced by `spacing` vertically, with a margin of `spacing` from the
        bottom/top and inset by `spacing` from the left/right boundary at each stripe.
        """
        ys = [p.y() for p in poly]
        y_min, y_max = min(ys), max(ys)

        lines: list[QLineF] = []
        inset = spacing

        # Scan-lines start inset above bottom, end inset below top
        y = y_min + spacing
        while y <= y_max - spacing:
            xs: list[float] = []
            n = len(poly)

            # find intersections with this horizontal at y
            for i in range(n):
                a, b = poly[i], poly[(i + 1) % n]
                if (a.y() <= y < b.y()) or (b.y() <= y < a.y()):
                    t = (y - a.y()) / (b.y() - a.y())
                    x = a.x() + t * (b.x() - a.x())
                    xs.append(x)

            if len(xs) >= 2:
                xs.sort()
                # each pair (xs[0], xs[1]), (xs[2], xs[3]), … is inside
                for i in range(0, len(xs), 2):
                    if i + 1 < len(xs):
                        x0_raw, x1_raw = xs[i], xs[i + 1]
                        x0, x1 = x0_raw + inset, x1_raw - inset
                        # only draw if there's room
                        if x1 > x0:
                            lines.append(QLineF(x0, y, x1, y))

            y += spacing

        return lines

    def display_instructions(self):
        """Show initial instructions on the scene."""
        instructions = [
            "• Hold Ctrl and click to add points",
            "• Click and drag to pan the view",
            "• Hold Ctrl and use mouse wheel to zoom",
            "• Press 'Close Shape' when done adding points",
            "• Press 'Decompose' to split into convex pieces"
        ]

        y_pos = -100
        for instruction in instructions:
            text_item = self.scene.addText(instruction)
            text_item.setPos(-150, y_pos)
            text_item.setDefaultTextColor(QColor(100, 100, 100))
            y_pos += 30

    def add_point(self, p: QPointF):
        # Add a vertex
        radius = 8
        self.scene.addEllipse(p.x() - radius / 2, p.y() - radius / 2, radius, radius,
                              self.point_pen, self.point_brush)

        if self.current:
            prev = self.current[-1]
            self.scene.addLine(prev.x(), prev.y(), p.x(), p.y(), self.edge_pen)

            # Show potential closing edge
            if len(self.current) > 1:
                first = self.current[0]
                self.update_temp_closing_edge(p, first)

        self.current.append(p)

        # Update status bar
        self.point_count_label.setText(f"Points: {len(self.current)}")

    def update_temp_closing_edge(self, last_point, first_point):
        """Show a temporary dotted line indicating the closing edge."""
        # Remove any existing temp edges
        for item in self.scene.items():
            if hasattr(item, 'isClosingEdge') and item.isClosingEdge:
                self.scene.removeItem(item)

        if len(self.current) > 1:
            # Add new temp edge
            line = self.scene.addLine(
                last_point.x(), last_point.y(),
                first_point.x(), first_point.y(),
                self.temp_edge_pen
            )
            line.isClosingEdge = True

    def close_shape(self):
        if len(self.current) < 3:
            self.status_bar.showMessage("Need at least 3 points to form a polygon", 3000)
            return

        # Add closing edge
        first, last = self.current[0], self.current[-1]
        self.scene.addLine(last.x(), last.y(), first.x(), first.y(), self.edge_pen)

        # Store the closed polygon
        self.last_closed = self.current.copy()
        self.current.clear()

        # Remove temporary closing edge
        for item in self.scene.items():
            if hasattr(item, 'isClosingEdge') and item.isClosingEdge:
                self.scene.removeItem(item)

        # Update status
        self.status_bar.showMessage("Shape closed. Ready for decomposition.", 3000)
        self.point_count_label.setText("Points: 0")

    def decompose(self):
        if not self.last_closed:
            self.status_bar.showMessage("No closed shape to decompose", 3000)
            return

        # Clear previous decomposition
        self.clear_decomposition()

        # 1) triangulate
        tris = ear_clip(self.last_closed)
        if not tris:
            self.status_bar.showMessage("Triangulation failed", 3000)
            return

        # Create polygon list from triangles
        polys = [list(tri) for tri in tris]

        # 2) merge greedily
        self.convex_pieces = merge_convex(polys)

        # 3) redraw everything
        self.draw_decomposition()

        # Update status
        self.status_bar.showMessage(f"Decomposed into {len(self.convex_pieces)} convex pieces", 5000)

    def draw_decomposition(self):
        """Draw the decomposed convex pieces with colors."""
        if not self.convex_pieces:
            return

        # Draw original outline
        self.draw_outline()

        # Draw merged pieces
        color_scheme = self.color_combo.currentText()

        for idx, poly in enumerate(self.convex_pieces):
            qpoly = QPolygonF(poly)

            # Select color based on scheme
            if color_scheme == "Rainbow":
                hue = int(360 * idx / len(self.convex_pieces)) % 360
                color = QColor.fromHsv(hue, 200, 220, 180)
            elif color_scheme == "Blue":
                color = QColor(0, 100, 200, 180)
                color = color.lighter(100 + (idx * 20) % 100)
            elif color_scheme == "Green":
                color = QColor(0, 180, 100, 180)
                color = color.lighter(100 + (idx * 20) % 100)
            elif color_scheme == "Red":
                color = QColor(200, 50, 50, 180)
                color = color.lighter(100 + (idx * 20) % 100)
            else:  # Pastel
                hue = int(360 * idx / len(self.convex_pieces)) % 360
                color = QColor.fromHsv(hue, 120, 240, 180)

            pen = QPen(color.darker(), 1.5)
            brush = QBrush(color)
            self.scene.addPolygon(qpoly, pen, brush)

    def draw_outline(self):
        """Draw the outline of the original polygon."""
        if not self.last_closed:
            return

        n = len(self.last_closed)
        for i in range(n):
            a = self.last_closed[i]
            b = self.last_closed[(i + 1) % n]
            self.scene.addLine(a.x(), a.y(), b.x(), b.y(), self.outline_pen)

    def clear_all(self):
        """Clear all points and shapes."""
        self.scene.clear()
        self.current.clear()
        self.last_closed.clear()
        self.convex_pieces.clear()
        self.draw_grid()
        self.point_count_label.setText("Points: 0")
        self.status_bar.showMessage("All cleared", 2000)

    def clear_decomposition(self):
        """Clear only the decomposition, keeping the original shape."""
        self.convex_pieces.clear()
        self.scene.clear()
        self.draw_grid()

        # Redraw the original points and edges
        if self.last_closed:
            # Draw points
            radius = 8
            for p in self.last_closed:
                self.scene.addEllipse(p.x() - radius / 2, p.y() - radius / 2, radius, radius,
                                      self.point_pen, self.point_brush)

            # Draw edges
            n = len(self.last_closed)
            for i in range(n):
                a = self.last_closed[i]
                b = self.last_closed[(i + 1) % n]
                self.scene.addLine(a.x(), a.y(), b.x(), b.y(), self.edge_pen)

        # Redraw current points if any
        for i, p in enumerate(self.current):
            radius = 8
            self.scene.addEllipse(p.x() - radius / 2, p.y() - radius / 2, radius, radius,
                                  self.point_pen, self.point_brush)

            if i > 0:
                prev = self.current[i - 1]
                self.scene.addLine(prev.x(), prev.y(), p.x(), p.y(), self.edge_pen)

    def undo_point(self):
        """Remove the last placed point."""
        if not self.current:
            self.status_bar.showMessage("No points to undo", 2000)
            return

        self.current.pop()
        self.clear_decomposition()
        self.point_count_label.setText(f"Points: {len(self.current)}")

        if len(self.current) >= 2:
            # Update temporary closing edge
            self.update_temp_closing_edge(self.current[-1], self.current[0])

    def update_colors(self):
        """Update the colors when the color scheme changes."""
        if self.convex_pieces:
            self.clear_decomposition()
            self.draw_decomposition()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Set application style
    app.setStyle("Fusion")

    # Create and show the main window
    w = MainWindow()
    w.show()

    sys.exit(app.exec())