#!/usr/bin/env python3
"""
CookiX — The Topological Memory Database (All-in-One)
"Stop measuring distances. Start understanding adjacency."

Run:  pip install numpy networkx scipy PyQt5 PyOpenGL
Then: python cookix_app.py
"""

import sys
import os
import math
import threading
import numpy as np
import networkx as nx
from enum import Enum
from typing import List, Tuple, Optional, Dict, Any, Set, Callable
from dataclasses import dataclass, field
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QSpinBox, QGroupBox, QTextEdit,
    QSplitter, QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QOpenGLWidget, QTabWidget, QTreeWidget, QTreeWidgetItem,
    QDialog, QDialogButtonBox, QMessageBox, QListWidget, QFrame,
    QCheckBox,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor
from OpenGL.GL import *
from OpenGL.GLU import *


# ═══════════════════════════════════════════════════════════
#  CORE: Distance Metrics & Vector DB
# ═══════════════════════════════════════════════════════════

class DistanceMetric(Enum):
    EUCLIDEAN = "euclidean"
    COSINE = "cosine"
    MANHATTAN = "manhattan"
    CHEBYSHEV = "chebyshev"
    MINKOWSKI = "minkowski"
    CANBERRA = "canberra"
    BRAYCURTIS = "braycurtis"
    CUSTOM_ADAPTIVE = "custom_adaptive"


@dataclass
class VectorEntry:
    id: str
    vector: np.ndarray
    metadata: Dict[str, Any]
    timestamp: datetime


class DistanceCalculator:
    @staticmethod
    def euclidean(v1, v2): return float(np.sqrt(np.sum((v1 - v2) ** 2)))
    @staticmethod
    def cosine(v1, v2):
        d = np.dot(v1, v2); n = np.linalg.norm(v1) * np.linalg.norm(v2)
        return 0.0 if n == 0 else float(1.0 - d / n)
    @staticmethod
    def manhattan(v1, v2): return float(np.sum(np.abs(v1 - v2)))
    @staticmethod
    def chebyshev(v1, v2): return float(np.max(np.abs(v1 - v2)))
    @staticmethod
    def minkowski(v1, v2, p=3): return float(np.power(np.sum(np.power(np.abs(v1 - v2), p)), 1/p))
    @staticmethod
    def canberra(v1, v2):
        n = np.abs(v1 - v2); d = np.abs(v1) + np.abs(v2); m = d != 0
        return float(np.sum(n[m] / d[m]))
    @staticmethod
    def braycurtis(v1, v2):
        n = np.sum(np.abs(v1 - v2)); d = np.sum(np.abs(v1 + v2))
        return 0.0 if d == 0 else float(n / d)
    @staticmethod
    def custom_adaptive(v1, v2):
        e = DistanceCalculator.euclidean(v1, v2)
        c = DistanceCalculator.cosine(v1, v2)
        m = DistanceCalculator.manhattan(v1, v2)
        m1, m2 = np.linalg.norm(v1), np.linalg.norm(v2)
        r = min(m1, m2) / max(m1, m2) if max(m1, m2) > 0 else 1.0
        return float(0.4 * e + 0.3 * c + 0.2 * m + 0.1 * (1 - r))


class VectorDB:
    def __init__(self, dimension=3, metric=DistanceMetric.EUCLIDEAN):
        self.dimension = dimension
        self.metric = metric
        self.vectors: List[VectorEntry] = []
        self.index_map: Dict[str, int] = {}
        self.lock = threading.Lock()
        self.stats = {'total_vectors': 0, 'total_queries': 0}

    def add_vector(self, vid, vector, metadata=None):
        if len(vector) != self.dimension:
            raise ValueError(f"Dimension mismatch: {len(vector)} vs {self.dimension}")
        with self.lock:
            if vid in self.index_map: return False
            self.vectors.append(VectorEntry(vid, np.array(vector, dtype=np.float32), metadata or {}, datetime.now()))
            self.index_map[vid] = len(self.vectors) - 1
            self.stats['total_vectors'] += 1
            return True

    def _calc_dist(self, v1, v2, metric=None):
        metric = metric or self.metric
        funcs = {
            DistanceMetric.EUCLIDEAN: DistanceCalculator.euclidean,
            DistanceMetric.COSINE: DistanceCalculator.cosine,
            DistanceMetric.MANHATTAN: DistanceCalculator.manhattan,
            DistanceMetric.CHEBYSHEV: DistanceCalculator.chebyshev,
            DistanceMetric.MINKOWSKI: DistanceCalculator.minkowski,
            DistanceMetric.CANBERRA: DistanceCalculator.canberra,
            DistanceMetric.BRAYCURTIS: DistanceCalculator.braycurtis,
            DistanceMetric.CUSTOM_ADAPTIVE: DistanceCalculator.custom_adaptive,
        }
        return funcs[metric](v1, v2)

    def query(self, qv, k=5, metric=None):
        qv = np.array(qv, dtype=np.float32)
        with self.lock:
            dists = [(e, self._calc_dist(qv, e.vector, metric)) for e in self.vectors]
            dists.sort(key=lambda x: x[1])
            self.stats['total_queries'] += 1
            return dists[:k]

    def get_all_vectors(self): return self.vectors.copy()
    def get_stats(self): return self.stats.copy()
    def __len__(self): return len(self.vectors)


# ═══════════════════════════════════════════════════════════
#  CORE: Topological Engine (CookiX)
# ═══════════════════════════════════════════════════════════

class EdgeType(Enum):
    IS_A = "is_a"; PART_OF = "part_of"; HAS_PART = "has_part"
    CAUSES = "causes"; PREVENTS = "prevents"; ENABLES = "enables"
    REQUIRES = "requires"; CONTRADICTS = "contradicts"; IMPLIES = "implies"
    SIMILAR_TO = "similar_to"; DIFFERENT_FROM = "different_from"
    COMPATIBLE_WITH = "compatible_with"; REPLACES = "replaces"
    EXAMPLE_OF = "example_of"; USED_IN = "used_in"
    PRECEDES = "precedes"; FOLLOWS = "follows"


# Edge type → color mapping for visualization
EDGE_COLORS = {
    EdgeType.IS_A:           (0.3, 0.8, 1.0),   # cyan
    EdgeType.PART_OF:        (0.3, 0.8, 1.0),
    EdgeType.HAS_PART:       (0.3, 0.8, 1.0),
    EdgeType.CAUSES:         (1.0, 0.5, 0.2),   # orange
    EdgeType.PREVENTS:       (1.0, 0.2, 0.2),   # red
    EdgeType.ENABLES:        (0.2, 1.0, 0.4),   # green
    EdgeType.REQUIRES:       (1.0, 0.8, 0.2),   # yellow
    EdgeType.CONTRADICTS:    (1.0, 0.1, 0.5),   # magenta
    EdgeType.IMPLIES:        (0.6, 0.6, 1.0),
    EdgeType.SIMILAR_TO:     (0.4, 1.0, 0.4),   # lime
    EdgeType.DIFFERENT_FROM: (0.8, 0.4, 0.1),
    EdgeType.COMPATIBLE_WITH:(0.2, 1.0, 0.8),   # teal
    EdgeType.REPLACES:       (0.9, 0.6, 0.9),
    EdgeType.EXAMPLE_OF:     (0.6, 0.8, 0.3),
    EdgeType.USED_IN:        (0.5, 0.5, 1.0),
    EdgeType.PRECEDES:       (0.7, 0.7, 0.3),
    EdgeType.FOLLOWS:        (0.3, 0.7, 0.7),
}

# Node color palette (distinct bright colors per node)
NODE_COLORS = [
    (0.2, 0.6, 1.0),   # blue
    (1.0, 0.4, 0.3),   # red-orange
    (0.3, 0.9, 0.4),   # green
    (1.0, 0.8, 0.1),   # gold
    (0.8, 0.3, 1.0),   # purple
    (0.1, 0.9, 0.9),   # cyan
    (1.0, 0.5, 0.7),   # pink
    (0.6, 1.0, 0.3),   # lime
    (1.0, 0.6, 0.1),   # orange
    (0.4, 0.4, 1.0),   # indigo
    (0.9, 0.9, 0.2),   # yellow
    (0.2, 0.7, 0.6),   # teal
]


@dataclass
class EdgeDef:
    target_id: str; edge_type: EdgeType; weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    bidirectional: bool = False


@dataclass
class KnowledgeObject:
    id: str; content: str = ""
    edges: List[EdgeDef] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReasoningStep:
    from_id: str; to_id: str; edge_type: EdgeType; weight: float
    def __repr__(self): return f"{self.from_id} --[{self.edge_type.value}]--> {self.to_id}"


@dataclass
class QueryResult:
    query: str; target_id: str; path: List[ReasoningStep]
    total_distance: float; confidence: float; explanation: str
    @property
    def path_string(self):
        if not self.path: return "(direct)"
        parts = [self.path[0].from_id]
        for s in self.path: parts += [f"--[{s.edge_type.value}]-->", s.to_id]
        return " ".join(parts)


class TopologicalEngine:
    def __init__(self, alpha=0.6, beta=0.4):
        self.objects: Dict[str, KnowledgeObject] = {}
        self.graph = nx.DiGraph()
        self.alpha = alpha; self.beta = beta
        # 3D positions for visualization
        self.positions: Dict[str, np.ndarray] = {}

    def add_object(self, obj: KnowledgeObject):
        if obj.id in self.objects: return False
        self.objects[obj.id] = obj
        self.graph.add_node(obj.id, content=obj.content, metadata=obj.metadata)
        for e in obj.edges:
            self.graph.add_edge(obj.id, e.target_id, edge_type=e.edge_type.value,
                                weight=e.weight, metadata=e.metadata, etype=e.edge_type)
            if e.bidirectional:
                self.graph.add_edge(e.target_id, obj.id, edge_type=e.edge_type.value,
                                    weight=e.weight, metadata=e.metadata, etype=e.edge_type)
        return True

    def compute_layout(self, scale=5.0):
        """Compute 3D positions using spring layout"""
        if not self.objects:
            self.positions = {}
            return
        # Use networkx spring layout in 3D
        pos_2d = nx.spring_layout(self.graph.to_undirected(), dim=3, k=2.0,
                                   iterations=100, seed=42)
        self.positions = {}
        for nid, coords in pos_2d.items():
            self.positions[nid] = np.array(coords) * scale

    def query_direct(self, src, etype):
        obj = self.objects.get(src)
        if not obj: return []
        return [(e.target_id, e) for e in obj.edges if e.edge_type == etype]

    def query_path(self, src, tgt, max_hops=5):
        if src not in self.objects or tgt not in self.objects: return None
        visited = {src}; queue = [(src, [], 0.0)]
        while queue:
            cur, path, dist = queue.pop(0)
            if cur == tgt:
                return QueryResult(f"{src}->{tgt}", tgt, path, dist, 1.0/(1+dist), self._explain(path))
            if len(path) >= max_hops: continue
            obj = self.objects.get(cur)
            if not obj: continue
            for e in obj.edges:
                if e.target_id not in visited:
                    visited.add(e.target_id)
                    step = ReasoningStep(cur, e.target_id, e.edge_type, e.weight)
                    queue.append((e.target_id, path + [step], dist + e.weight))
        return None

    def query_neighborhood(self, src, max_hops=2, etypes=None):
        results = {}; visited = {src}; queue = [(src, [], 0.0)]
        while queue:
            cur, path, dist = queue.pop(0)
            if cur != src:
                results[cur] = QueryResult(f"N({src})", cur, path, dist, 1.0/(1+dist), self._explain(path))
            if len(path) >= max_hops: continue
            obj = self.objects.get(cur)
            if not obj: continue
            for e in obj.edges:
                if e.target_id not in visited and (etypes is None or e.edge_type in etypes):
                    visited.add(e.target_id)
                    queue.append((e.target_id, path + [ReasoningStep(cur, e.target_id, e.edge_type, e.weight)], dist + e.weight))
        return results

    def query_reasoning(self, src, intent, target_etype, max_hops=3):
        results = []
        direct = self.query_direct(src, target_etype)
        for tid, e in direct:
            step = ReasoningStep(src, tid, e.edge_type, e.weight)
            results.append(QueryResult(intent, tid, [step], e.weight, 1.0, f"Direct {target_etype.value} found."))
        if results: return sorted(results, key=lambda r: r.total_distance)
        expand_types = {EdgeType.SIMILAR_TO, EdgeType.IS_A, EdgeType.PART_OF}
        nbrs = self.query_neighborhood(src, max_hops, expand_types)
        for nid, nr in nbrs.items():
            for ftid, fe in self.query_direct(nid, target_etype):
                fp = nr.path + [ReasoningStep(nid, ftid, fe.edge_type, fe.weight)]
                td = nr.total_distance + fe.weight
                expl = f"No direct {target_etype.value}. Found via {len(fp)}-hop path."
                results.append(QueryResult(intent, ftid, fp, td, 1.0/(1+td), expl))
        return sorted(results, key=lambda r: r.total_distance)

    def geodesic(self, a, b):
        try: return float(nx.shortest_path_length(self.graph, a, b, weight='weight'))
        except: return float('inf')

    def get_stats(self):
        s = {'objects': len(self.objects), 'edges': self.graph.number_of_edges()}
        if self.graph.number_of_nodes() > 0:
            degs = [d for _, d in self.graph.degree()]
            s['avg_degree'] = f"{np.mean(degs):.1f}"
            s['density'] = f"{nx.density(self.graph):.3f}"
            et = {}
            for u, v, d in self.graph.edges(data=True):
                t = d.get('edge_type', '?'); et[t] = et.get(t, 0) + 1
            s['edge_types'] = et
        return s

    def _explain(self, path):
        if not path: return "Direct match."
        return " → ".join(f"'{s.from_id}' --[{s.edge_type.value}]--> '{s.to_id}'" for s in path)

    def __len__(self): return len(self.objects)


# ═══════════════════════════════════════════════════════════
#  DEMO SCENARIOS
# ═══════════════════════════════════════════════════════════

def build_umbrella_scenario():
    engine = TopologicalEngine()
    engine.add_object(KnowledgeObject("rain", "Rain — precipitation from clouds", edges=[
        EdgeDef("storm", EdgeType.PART_OF), EdgeDef("water", EdgeType.IS_A),
        EdgeDef("rain_coat", EdgeType.CAUSES, 0.8, {"effect": "gets wet"}),
    ]))
    engine.add_object(KnowledgeObject("umbrella", "Umbrella — portable rain protection", edges=[
        EdgeDef("rain", EdgeType.PREVENTS, 0.5, {"mechanism": "canopy shield"}),
        EdgeDef("rain_coat", EdgeType.COMPATIBLE_WITH),
    ]))
    engine.add_object(KnowledgeObject("rain_coat", "Rain coat — waterproof outerwear", edges=[
        EdgeDef("rain", EdgeType.PREVENTS, 0.6, {"mechanism": "waterproof fabric"}),
        EdgeDef("umbrella", EdgeType.COMPATIBLE_WITH),
    ]))
    engine.add_object(KnowledgeObject("storm", "Storm — severe weather event", edges=[
        EdgeDef("rain", EdgeType.HAS_PART),
        EdgeDef("umbrella", EdgeType.CONTRADICTS, metadata={"reason": "too windy"}),
    ]))
    engine.add_object(KnowledgeObject("water", "Water — H2O in liquid form"))
    engine.add_object(KnowledgeObject("sunshine", "Sunshine — direct sunlight", edges=[
        EdgeDef("rain", EdgeType.CONTRADICTS),
    ]))
    engine.compute_layout(scale=5.0)
    return engine


def build_pipe_scenario():
    engine = TopologicalEngine()
    engine.add_object(KnowledgeObject("pipe_120mm", "120mm steel pipe, Sch 40", edges=[
        EdgeDef("pipe_130mm", EdgeType.SIMILAR_TO, 0.3, {"tolerance": "10mm"}),
        EdgeDef("steel_pipe", EdgeType.IS_A),
        EdgeDef("adapter_ring", EdgeType.REQUIRES),
    ], metadata={"diameter": 120}))
    engine.add_object(KnowledgeObject("pipe_130mm", "130mm steel pipe, Sch 40", edges=[
        EdgeDef("pipe_120mm", EdgeType.SIMILAR_TO, 0.3),
        EdgeDef("fitting_B", EdgeType.COMPATIBLE_WITH, 0.2, {"spec": "ISO-4422"}),
        EdgeDef("steel_pipe", EdgeType.IS_A),
    ], metadata={"diameter": 130}))
    engine.add_object(KnowledgeObject("fitting_B", "Type B flanged fitting 130mm", edges=[
        EdgeDef("pipe_130mm", EdgeType.COMPATIBLE_WITH, 0.2),
        EdgeDef("iso_4422", EdgeType.USED_IN),
    ], metadata={"nominal_size": 130}))
    engine.add_object(KnowledgeObject("steel_pipe", "Steel pipe — general category"))
    engine.add_object(KnowledgeObject("adapter_ring", "Adapter ring 120→130mm", edges=[
        EdgeDef("pipe_120mm", EdgeType.COMPATIBLE_WITH),
        EdgeDef("pipe_130mm", EdgeType.COMPATIBLE_WITH),
    ]))
    engine.add_object(KnowledgeObject("iso_4422", "ISO 4422 — Pipe fitting standard"))
    engine.compute_layout(scale=5.0)
    return engine


# ═══════════════════════════════════════════════════════════
#  UI: OpenGL 3D Widget — Topological Visualization
# ═══════════════════════════════════════════════════════════

class GLWidget(QOpenGLWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Topo visualization data
        self.nodes = []          # [(pos3d, color, label, id)]
        self.edges_data = []     # [(pos_from, pos_to, color, label)]
        self.highlight_path = [] # list of node IDs to highlight
        self.highlight_edges = [] # list of (from_id, to_id) to highlight

        # Vector DB overlay
        self.vec_points = []     # [(pos3d, color, label)]
        self.vec_query = None
        self.vec_neighbors = []

        # Camera
        self.rotation_x = 20; self.rotation_y = -30
        self.zoom = -18; self.last_pos = None; self.is_dragging = False

        # Display options
        self.show_edges = True; self.show_labels = True
        self.show_vec_overlay = True; self.show_grid = True

        # Animation
        self.animate = False; self.anim_angle = 0

        # Hover/select
        self.selected_node = None
        self.on_node_selected = None

    def initializeGL(self):
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING); glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL); glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glLightfv(GL_LIGHT0, GL_POSITION, [10, 10, 10, 1])
        glLightfv(GL_LIGHT0, GL_AMBIENT, [0.25, 0.25, 0.30, 1])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.85, 0.85, 0.90, 1])
        glLightfv(GL_LIGHT0, GL_SPECULAR, [0.5, 0.5, 0.5, 1])
        glClearColor(0.04, 0.04, 0.08, 1.0)

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h); glMatrixMode(GL_PROJECTION); glLoadIdentity()
        gluPerspective(45, w/h if h else 1, 0.1, 200.0); glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT); glLoadIdentity()
        glTranslatef(0, 0, self.zoom)
        glRotatef(self.rotation_x, 1, 0, 0)
        glRotatef(self.rotation_y + (self.anim_angle if self.animate else 0), 0, 1, 0)
        if self.animate: self.anim_angle = (self.anim_angle + 0.4) % 360

        if self.show_grid: self._draw_grid()
        self._draw_axes()
        if self.show_edges: self._draw_edges()
        self._draw_nodes()
        self._draw_highlight_path()
        if self.show_vec_overlay: self._draw_vec_overlay()

    def _draw_grid(self):
        glDisable(GL_LIGHTING); glLineWidth(0.5)
        glColor4f(0.12, 0.12, 0.18, 0.5)
        glBegin(GL_LINES)
        for i in range(-10, 11, 2):
            glVertex3f(i, -0.5, -10); glVertex3f(i, -0.5, 10)
            glVertex3f(-10, -0.5, i); glVertex3f(10, -0.5, i)
        glEnd()
        glEnable(GL_LIGHTING); glLineWidth(1)

    def _draw_axes(self):
        glDisable(GL_LIGHTING); glLineWidth(1.5)
        for c, e in [((0.5,0.15,0.15),(8,0,0)),((0.15,0.5,0.15),(0,8,0)),((0.15,0.15,0.5),(0,0,8))]:
            glColor3f(*c); glBegin(GL_LINES); glVertex3f(0,0,0); glVertex3f(*e); glEnd()
        glEnable(GL_LIGHTING); glLineWidth(1)

    def _draw_nodes(self):
        """Draw Knowledge Objects as lit spheres"""
        for i, (pos, color, label, nid) in enumerate(self.nodes):
            is_selected = (nid == self.selected_node)
            is_highlighted = (nid in self.highlight_path)

            if is_selected:
                r, g, b = 1.0, 1.0, 1.0
                radius = 0.55
            elif is_highlighted:
                r, g, b = color
                r = min(1.0, r + 0.3); g = min(1.0, g + 0.3); b = min(1.0, b + 0.3)
                radius = 0.50
            else:
                r, g, b = color
                radius = 0.40

            glPushMatrix()
            glTranslatef(pos[0], pos[1], pos[2])

            # Main sphere
            glColor3f(r, g, b)
            q = gluNewQuadric()
            gluQuadricNormals(q, GLU_SMOOTH)
            gluSphere(q, radius, 32, 32)
            gluDeleteQuadric(q)

            # Glow ring for selected
            if is_selected or is_highlighted:
                glDisable(GL_LIGHTING)
                gc = (0, 1, 1) if is_selected else (1, 1, 0.5)
                glColor3f(*gc); glLineWidth(3.0)
                ring_r = radius + 0.15
                glBegin(GL_LINE_LOOP)
                for a in range(0, 360, 5):
                    rad = a * math.pi / 180
                    glVertex3f(ring_r * math.cos(rad), ring_r * math.sin(rad), 0)
                glEnd()
                # Second ring rotated
                glBegin(GL_LINE_LOOP)
                for a in range(0, 360, 5):
                    rad = a * math.pi / 180
                    glVertex3f(0, ring_r * math.cos(rad), ring_r * math.sin(rad))
                glEnd()
                glLineWidth(1); glEnable(GL_LIGHTING)

            # Inner glow (slightly transparent shell)
            glEnable(GL_BLEND)
            glColor4f(r, g, b, 0.15)
            q2 = gluNewQuadric()
            gluSphere(q2, radius + 0.12, 16, 16)
            gluDeleteQuadric(q2)
            glDisable(GL_BLEND)

            glPopMatrix()

    def _draw_edges(self):
        """Draw typed edges as colored lines with arrows"""
        glDisable(GL_LIGHTING)

        for pos_from, pos_to, color, label in self.edges_data:
            is_hl = False
            # Check if this edge is in the highlight path
            for (hf, ht) in self.highlight_edges:
                f_pos = self._get_node_pos(hf)
                t_pos = self._get_node_pos(ht)
                if f_pos is not None and t_pos is not None:
                    if (np.allclose(pos_from, f_pos, atol=0.01) and np.allclose(pos_to, t_pos, atol=0.01)):
                        is_hl = True; break

            if is_hl:
                glColor3f(1.0, 1.0, 0.0)
                glLineWidth(4.0)
            else:
                glColor4f(color[0], color[1], color[2], 0.7)
                glLineWidth(2.0)

            # Main line
            glBegin(GL_LINES)
            glVertex3f(*pos_from); glVertex3f(*pos_to)
            glEnd()

            # Arrowhead (small triangle at 80% along the edge)
            direction = np.array(pos_to) - np.array(pos_from)
            length = np.linalg.norm(direction)
            if length > 0.01:
                d = direction / length
                arrow_pos = np.array(pos_from) + d * length * 0.75
                # Two perpendicular vectors for the arrowhead
                if abs(d[1]) < 0.9:
                    perp1 = np.cross(d, [0, 1, 0])
                else:
                    perp1 = np.cross(d, [1, 0, 0])
                perp1 = perp1 / (np.linalg.norm(perp1) + 1e-10)
                arrow_size = 0.15 if not is_hl else 0.22

                glBegin(GL_TRIANGLES)
                tip = arrow_pos + d * arrow_size * 2
                left = arrow_pos + perp1 * arrow_size
                right = arrow_pos - perp1 * arrow_size
                glVertex3f(*tip); glVertex3f(*left); glVertex3f(*right)
                glEnd()

        glLineWidth(1); glEnable(GL_LIGHTING)

    def _draw_highlight_path(self):
        """Draw highlighted reasoning path with thick glowing lines"""
        if not self.highlight_edges: return
        glDisable(GL_LIGHTING)

        for (hf, ht) in self.highlight_edges:
            f_pos = self._get_node_pos(hf)
            t_pos = self._get_node_pos(ht)
            if f_pos is None or t_pos is None: continue

            # Outer glow
            glColor4f(1.0, 0.9, 0.0, 0.25); glLineWidth(10.0)
            glBegin(GL_LINES); glVertex3f(*f_pos); glVertex3f(*t_pos); glEnd()

            # Inner bright line
            glColor3f(1.0, 1.0, 0.3); glLineWidth(4.0)
            glBegin(GL_LINES); glVertex3f(*f_pos); glVertex3f(*t_pos); glEnd()

        glLineWidth(1); glEnable(GL_LIGHTING)

    def _draw_vec_overlay(self):
        """Draw vector DB points as small dots"""
        if not self.vec_points: return

        for pos, color, label in self.vec_points:
            if len(pos) < 3: continue
            glPushMatrix(); glTranslatef(pos[0], pos[1], pos[2])
            glColor3f(*color)
            q = gluNewQuadric(); gluSphere(q, 0.08, 8, 8); gluDeleteQuadric(q)
            glPopMatrix()

        # Query point and connections
        if self.vec_query is not None and len(self.vec_query) >= 3:
            qx, qy, qz = self.vec_query[:3]
            glPushMatrix(); glTranslatef(qx, qy, qz)
            glColor3f(1, 1, 1)
            q = gluNewQuadric(); gluSphere(q, 0.15, 12, 12); gluDeleteQuadric(q)
            glPopMatrix()

            glDisable(GL_LIGHTING); glColor3f(1, 0.9, 0.2); glLineWidth(1.5)
            glBegin(GL_LINES)
            for idx in self.vec_neighbors:
                if idx < len(self.vec_points):
                    vp = self.vec_points[idx][0]
                    if len(vp) >= 3:
                        glVertex3f(qx, qy, qz); glVertex3f(vp[0], vp[1], vp[2])
            glEnd()
            glEnable(GL_LIGHTING); glLineWidth(1)

    def _get_node_pos(self, nid):
        for pos, color, label, node_id in self.nodes:
            if node_id == nid: return pos
        return None

    # ─── Data setters ───

    def load_topo_engine(self, engine: TopologicalEngine):
        """Load a topological engine and build visualization data"""
        self.nodes = []
        self.edges_data = []
        node_ids = list(engine.objects.keys())

        for i, (nid, obj) in enumerate(engine.objects.items()):
            pos = engine.positions.get(nid, np.array([0, 0, 0]))
            color = NODE_COLORS[i % len(NODE_COLORS)]
            self.nodes.append((pos.copy(), color, nid, nid))

        for u, v, data in engine.graph.edges(data=True):
            pos_u = engine.positions.get(u, np.zeros(3))
            pos_v = engine.positions.get(v, np.zeros(3))
            etype = data.get('etype', EdgeType.IS_A)
            ecolor = EDGE_COLORS.get(etype, (0.5, 0.5, 0.5))
            elabel = data.get('edge_type', '?')
            self.edges_data.append((pos_u.copy(), pos_v.copy(), ecolor, elabel))

        self.highlight_path = []
        self.highlight_edges = []
        self.update()

    def set_highlight(self, node_ids, edge_pairs):
        """Highlight a reasoning path"""
        self.highlight_path = node_ids or []
        self.highlight_edges = edge_pairs or []
        self.update()

    def clear_highlight(self):
        self.highlight_path = []; self.highlight_edges = []
        self.selected_node = None; self.update()

    def set_vec_points(self, data):
        self.vec_points = data; self.update()

    def set_vec_query(self, qv, nbrs):
        self.vec_query = qv; self.vec_neighbors = nbrs; self.update()

    def clear_vec_query(self):
        self.vec_query = None; self.vec_neighbors = []; self.update()

    # ─── Mouse ───

    def mousePressEvent(self, e):
        self.last_pos = e.pos(); self.is_dragging = False
        if e.button() == Qt.LeftButton: self._pick_node(e.x(), e.y())

    def _pick_node(self, mx, my):
        try:
            self.makeCurrent()
            vp = [0, 0, self.width(), self.height()]
            ay = (self.rotation_y + (self.anim_angle if self.animate else 0)) * np.pi / 180
            cy, sy = np.cos(ay), np.sin(ay)
            ry = np.array([[cy,0,sy,0],[0,1,0,0],[-sy,0,cy,0],[0,0,0,1]], dtype=np.float64)
            ax = self.rotation_x * np.pi / 180; cx, sx = np.cos(ax), np.sin(ax)
            rx = np.array([[1,0,0,0],[0,cx,-sx,0],[0,sx,cx,0],[0,0,0,1]], dtype=np.float64)
            tr = np.array([[1,0,0,0],[0,1,0,0],[0,0,1,self.zoom],[0,0,0,1]], dtype=np.float64)
            mv = tr @ rx @ ry; pr = glGetDoublev(GL_PROJECTION_MATRIX); wy = vp[3] - my
            np_ = gluUnProject(mx, wy, 0.0, mv, pr, vp)
            fp = gluUnProject(mx, wy, 1.0, mv, pr, vp)
            rd = np.array([fp[i]-np_[i] for i in range(3)]); rd = rd/np.linalg.norm(rd)
            ro = np.array(np_)

            best_d, best_nid = float('inf'), None
            for pos, color, label, nid in self.nodes:
                vo = np.array(pos) - ro; pl = np.dot(vo, rd)
                if pl > 0:
                    d = np.linalg.norm(np.array(pos) - (ro + pl * rd))
                    if d < 0.8 and d < best_d: best_d = d; best_nid = nid

            self.selected_node = best_nid
            self.update()
            if self.on_node_selected:
                if best_nid:
                    pos = self._get_node_pos(best_nid)
                    self.on_node_selected(best_nid, pos)
                else:
                    self.on_node_selected(None, None)
        except: pass

    def mouseMoveEvent(self, e):
        if self.last_pos:
            dx, dy = e.x()-self.last_pos.x(), e.y()-self.last_pos.y()
            if abs(dx) > 2 or abs(dy) > 2: self.is_dragging = True
            if e.buttons() & Qt.LeftButton and self.is_dragging:
                self.rotation_y += dx*0.5; self.rotation_x += dy*0.5; self.update()
            self.last_pos = e.pos()

    def mouseReleaseEvent(self, e): self.is_dragging = False
    def wheelEvent(self, e):
        self.zoom += e.angleDelta().y() * 0.015
        self.zoom = max(-60, min(-3, self.zoom)); self.update()


# ═══════════════════════════════════════════════════════════
#  UI: Main Application
# ═══════════════════════════════════════════════════════════

DARK_STYLE = """
QMainWindow, QWidget { background-color: #0f0f1a; color: #e0e0e0; font-family: "Segoe UI", Arial; }
QGroupBox { border: 1px solid #2a2a4e; border-radius: 6px; margin-top: 12px; padding-top: 18px; font-weight: bold; color: #80b0ff; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px; }
QPushButton { background-color: #1e1e3a; color: #e0e0e0; border: 1px solid #3a3a6e; border-radius: 5px; padding: 7px 14px; font-weight: bold; }
QPushButton:hover { background-color: #2e2e5a; border-color: #5a5aae; }
QPushButton:pressed { background-color: #3e3e6a; }
QComboBox, QSpinBox, QLineEdit { background-color: #1a1a30; color: #e0e0e0; border: 1px solid #3a3a5e; border-radius: 4px; padding: 5px; }
QTextEdit { background-color: #0a0a18; color: #a0e8a0; border: 1px solid #2a2a4e; border-radius: 4px; font-family: "Cascadia Code", "Consolas", monospace; font-size: 9pt; }
QTableWidget { background-color: #0a0a18; color: #e0e0e0; border: 1px solid #2a2a4e; gridline-color: #1e1e3a; }
QHeaderView::section { background-color: #1e1e3a; color: #80b0ff; border: 1px solid #2a2a4e; padding: 5px; font-weight: bold; }
QTabWidget::pane { border: 1px solid #2a2a4e; background: #0f0f1a; }
QTabBar::tab { background-color: #1a1a30; color: #8080b0; padding: 8px 18px; border: 1px solid #2a2a4e; border-bottom: none; border-top-left-radius: 5px; border-top-right-radius: 5px; margin-right: 2px; }
QTabBar::tab:selected { background-color: #2a2a5a; color: #ffffff; }
QTreeWidget { background-color: #0a0a18; color: #e0e0e0; border: 1px solid #2a2a4e; }
QSplitter::handle { background-color: #2a2a4e; width: 3px; }
QLabel { color: #b0b0d0; }
QCheckBox { color: #b0b0d0; }
QCheckBox::indicator { width: 16px; height: 16px; }
"""


class CookiXApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = None
        self.topo_engine = None
        self.timer = QTimer(); self.timer.timeout.connect(self._tick)
        self._init_ui()
        self._new_db()
        self._generate_vectors(60)
        self._load_scenario("umbrella")

    def _init_ui(self):
        self.setWindowTitle("CookiX — The Topological Memory Database")
        self.setGeometry(60, 60, 1550, 950)
        self.setStyleSheet(DARK_STYLE)

        central = QWidget(); self.setCentralWidget(central)
        root = QHBoxLayout(central); root.setContentsMargins(4,4,4,4)
        splitter = QSplitter(Qt.Horizontal)

        # ─── LEFT PANEL ───
        left = QWidget(); ll = QVBoxLayout(left); ll.setSpacing(4)
        t = QLabel("🍪 CookiX Lab"); t.setFont(QFont("Segoe UI", 16, QFont.Bold))
        t.setAlignment(Qt.AlignCenter); t.setStyleSheet("color:#ff9f43; padding:8px 0;"); ll.addWidget(t)

        # Topo Engine controls (primary)
        g2 = QGroupBox("Topological Engine"); g2l = QVBoxLayout(); g2l.setSpacing(4)
        self.scenario_cb = QComboBox(); self.scenario_cb.addItems(["umbrella", "pipe"])
        h4 = QHBoxLayout(); h4.addWidget(QLabel("Scenario:")); h4.addWidget(self.scenario_cb)
        b5 = QPushButton("📂 Load"); b5.clicked.connect(lambda: self._load_scenario(self.scenario_cb.currentText())); h4.addWidget(b5)
        g2l.addLayout(h4)

        g2l.addWidget(self._sep())
        g2l.addWidget(QLabel("🔍 Path Query:"))
        self.topo_query_src = QLineEdit(); self.topo_query_src.setPlaceholderText("Source (e.g. umbrella)")
        self.topo_query_tgt = QLineEdit(); self.topo_query_tgt.setPlaceholderText("Target (e.g. storm)")
        g2l.addWidget(self.topo_query_src); g2l.addWidget(self.topo_query_tgt)
        b6 = QPushButton("🧠 Find Path"); b6.clicked.connect(self._topo_path_query)
        b6.setStyleSheet("QPushButton{background:#1a3a6a; border-color:#3a6aae;} QPushButton:hover{background:#2a4a8a;}")
        g2l.addWidget(b6)

        g2l.addWidget(self._sep())
        g2l.addWidget(QLabel("⚡ Reasoning Query:"))
        self.topo_reason_src = QLineEdit(); self.topo_reason_src.setPlaceholderText("Source (e.g. pipe_120mm)")
        self.topo_reason_etype = QComboBox()
        for et in EdgeType: self.topo_reason_etype.addItem(et.value)
        self.topo_reason_etype.setCurrentText("compatible_with")
        g2l.addWidget(self.topo_reason_src)
        h5 = QHBoxLayout(); h5.addWidget(QLabel("Edge:")); h5.addWidget(self.topo_reason_etype); g2l.addLayout(h5)
        b7 = QPushButton("⚡ Reason"); b7.clicked.connect(self._topo_reasoning)
        b7.setStyleSheet("QPushButton{background:#3a1a5a; border-color:#6a3aae;} QPushButton:hover{background:#4a2a7a;}")
        g2l.addWidget(b7)

        bc = QPushButton("✖ Clear Highlights"); bc.clicked.connect(self._clear_highlights); g2l.addWidget(bc)
        g2.setLayout(g2l); ll.addWidget(g2)

        # Vector DB controls (secondary)
        g1 = QGroupBox("Vector DB Overlay"); g1l = QVBoxLayout(); g1l.setSpacing(4)
        h = QHBoxLayout(); h.addWidget(QLabel("Dims:")); self.dim_spin = QSpinBox(); self.dim_spin.setRange(2,10); self.dim_spin.setValue(3); h.addWidget(self.dim_spin)
        h.addWidget(QLabel("Metric:")); self.metric_cb = QComboBox()
        for m in DistanceMetric: self.metric_cb.addItem(m.value)
        h.addWidget(self.metric_cb); g1l.addLayout(h)

        h2 = QHBoxLayout()
        h2.addWidget(QLabel("N:")); self.n_spin = QSpinBox(); self.n_spin.setRange(1,500); self.n_spin.setValue(60); h2.addWidget(self.n_spin)
        b2 = QPushButton("➕ Gen"); b2.clicked.connect(lambda: self._generate_vectors(self.n_spin.value())); h2.addWidget(b2)
        h2.addWidget(QLabel("K:")); self.k_spin = QSpinBox(); self.k_spin.setRange(1,20); self.k_spin.setValue(5); h2.addWidget(self.k_spin)
        b3 = QPushButton("🔍 Q"); b3.clicked.connect(self._query_random); h2.addWidget(b3)
        g1l.addLayout(h2)

        self.vec_overlay_cb = QCheckBox("Show vector overlay"); self.vec_overlay_cb.setChecked(True)
        self.vec_overlay_cb.stateChanged.connect(lambda s: setattr(self.gl, 'show_vec_overlay', bool(s)) or self.gl.update())
        g1l.addWidget(self.vec_overlay_cb)
        g1.setLayout(g1l); ll.addWidget(g1)

        # View
        g3 = QGroupBox("View"); g3l = QHBoxLayout()
        b8 = QPushButton("🔄 Animate"); b8.clicked.connect(self._toggle_anim); g3l.addWidget(b8)
        b9 = QPushButton("🎯 Reset"); b9.clicked.connect(self._reset_cam); g3l.addWidget(b9)
        g3.setLayout(g3l); ll.addWidget(g3)

        self.stats_label = QLabel(""); self.stats_label.setWordWrap(True)
        self.stats_label.setStyleSheet("color:#60a0a0; font-size:9pt; padding:4px;")
        ll.addWidget(self.stats_label)
        ll.addStretch()
        splitter.addWidget(left)

        # ─── CENTER: 3D View ───
        center = QWidget(); cl = QVBoxLayout(center); cl.setContentsMargins(0,0,0,0)
        self.gl = GLWidget(); self.gl.on_node_selected = self._on_node_selected; cl.addWidget(self.gl)
        self.info_bar = QLabel("🖱  Drag to rotate  •  Scroll to zoom  •  Click nodes to inspect")
        self.info_bar.setStyleSheet("background:#0a0a1a; color:#00c8ff; padding:10px; font-weight:bold; font-size:10pt;")
        self.info_bar.setWordWrap(True); cl.addWidget(self.info_bar)
        splitter.addWidget(center)

        # ─── RIGHT PANEL ───
        right = QWidget(); rl = QVBoxLayout(right)
        self.tabs = QTabWidget()

        # Tab 1: Topo results
        t2 = QWidget(); t2l = QVBoxLayout(t2)
        self.topo_output = QTextEdit(); self.topo_output.setReadOnly(True); t2l.addWidget(self.topo_output)
        self.tabs.addTab(t2, "🧠 Reasoning")

        # Tab 2: Graph tree view
        t3 = QWidget(); t3l = QVBoxLayout(t3)
        self.graph_tree = QTreeWidget(); self.graph_tree.setHeaderLabels(["Node / Edge", "Type", "Details"])
        self.graph_tree.setColumnWidth(0, 160); t3l.addWidget(self.graph_tree)
        self.tabs.addTab(t3, "🌐 Graph")

        # Tab 3: Vector results
        t1 = QWidget(); t1l = QVBoxLayout(t1)
        self.results_table = QTableWidget(); self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(["#", "ID", "Distance", "Vector"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        t1l.addWidget(self.results_table)
        self.tabs.addTab(t1, "📊 Vectors")

        rl.addWidget(self.tabs)
        rl.addWidget(QLabel("Activity Log:"))
        self.log_text = QTextEdit(); self.log_text.setReadOnly(True); self.log_text.setMaximumHeight(140)
        rl.addWidget(self.log_text)
        splitter.addWidget(right)

        splitter.setSizes([310, 780, 380])
        root.addWidget(splitter)

    def _sep(self):
        f = QFrame(); f.setFrameShape(QFrame.HLine); f.setStyleSheet("color:#2a2a4e;"); return f

    # ─── Topo Engine ───

    def _load_scenario(self, name):
        if name == "umbrella":
            self.topo_engine = build_umbrella_scenario()
            self.topo_query_src.setText("umbrella"); self.topo_query_tgt.setText("storm")
            self.topo_reason_src.setText("umbrella"); self.topo_reason_etype.setCurrentText("compatible_with")
        else:
            self.topo_engine = build_pipe_scenario()
            self.topo_query_src.setText("pipe_120mm"); self.topo_query_tgt.setText("fitting_B")
            self.topo_reason_src.setText("pipe_120mm"); self.topo_reason_etype.setCurrentText("compatible_with")
        self.gl.load_topo_engine(self.topo_engine)
        self._refresh_graph_tree()
        self._update_stats()
        self._log(f"Loaded '{name}': {len(self.topo_engine)} Knowledge Objects on manifold")

    def _topo_path_query(self):
        if not self.topo_engine: return
        src = self.topo_query_src.text().strip(); tgt = self.topo_query_tgt.text().strip()
        if not src or not tgt: return

        result = self.topo_engine.query_path(src, tgt, max_hops=5)
        out = f"🔍 PATH QUERY: {src} → {tgt}\n{'═'*50}\n\n"

        if result:
            out += f"✅ Path found!\n\n"
            out += f"  Path:       {result.path_string}\n"
            out += f"  Distance:   {result.total_distance:.2f}\n"
            out += f"  Confidence: {result.confidence:.2%}\n\n"
            out += f"  Steps:\n"
            hl_nodes = [result.path[0].from_id] if result.path else []
            hl_edges = []
            for i, s in enumerate(result.path, 1):
                out += f"    {i}. {s.from_id}  ──[{s.edge_type.value}]──▶  {s.to_id}  (w={s.weight:.1f})\n"
                hl_nodes.append(s.to_id)
                hl_edges.append((s.from_id, s.to_id))
            self.gl.set_highlight(hl_nodes, hl_edges)
        else:
            out += f"❌ No path found between '{src}' and '{tgt}'.\n"
            self.gl.clear_highlight()

        out += f"\n{'═'*50}\n📍 NEIGHBORHOOD of '{src}' (2 hops):\n\n"
        nbrs = self.topo_engine.query_neighborhood(src, max_hops=2)
        for nid, nr in sorted(nbrs.items(), key=lambda x: x[1].total_distance):
            out += f"  {nid:18s}  dist={nr.total_distance:.2f}  via {nr.path_string}\n"

        self.topo_output.setText(out); self.tabs.setCurrentIndex(0)
        self._log(f"Path: {src} → {tgt}: {'FOUND' if result else 'none'}")

    def _topo_reasoning(self):
        if not self.topo_engine: return
        src = self.topo_reason_src.text().strip()
        etype_str = self.topo_reason_etype.currentText()
        if not src: return
        etype = EdgeType(etype_str)

        results = self.topo_engine.query_reasoning(src, f"{src} {etype_str}?", etype, max_hops=3)
        out = f"⚡ REASONING RETRIEVAL\n{'═'*50}\n"
        out += f"  Source:  {src}\n  Seeking: [{etype_str}]\n\n"

        direct = self.topo_engine.query_direct(src, etype)
        out += f"  Step 1 — Direct lookup: {'FOUND ' + str(len(direct)) + ' edges' if direct else 'NULL'}\n"
        out += f"  Step 2 — Topological expansion:\n\n"

        if results:
            best = results[0]
            hl_nodes = [best.path[0].from_id] if best.path else []
            hl_edges = []
            for i, r in enumerate(results, 1):
                out += f"  Result {i}:\n"
                out += f"    Target:     {r.target_id}\n"
                out += f"    Path:       {r.path_string}\n"
                out += f"    Distance:   {r.total_distance:.2f}\n"
                out += f"    Confidence: {r.confidence:.2%}\n"
                out += f"    {r.explanation}\n\n"
            for s in best.path:
                hl_nodes.append(s.to_id); hl_edges.append((s.from_id, s.to_id))
            self.gl.set_highlight(hl_nodes, hl_edges)
        else:
            out += "  No reasoning paths found.\n"
            self.gl.clear_highlight()

        out += f"\n{'═'*50}\n📐 Geodesic distances from '{src}':\n\n"
        for oid in self.topo_engine.objects:
            if oid != src:
                d = self.topo_engine.geodesic(src, oid)
                sym = f"{d:.2f}" if d != float('inf') else "∞"
                out += f"  → {oid:18s}  D = {sym}\n"

        self.topo_output.setText(out); self.tabs.setCurrentIndex(0)
        self._log(f"Reasoning: {src} [{etype_str}] → {len(results)} results")

    def _clear_highlights(self):
        self.gl.clear_highlight(); self._log("Highlights cleared")

    def _refresh_graph_tree(self):
        self.graph_tree.clear()
        if not self.topo_engine: return
        for i, (oid, obj) in enumerate(self.topo_engine.objects.items()):
            color = NODE_COLORS[i % len(NODE_COLORS)]
            qc = QColor(int(color[0]*255), int(color[1]*255), int(color[2]*255))
            node_item = QTreeWidgetItem([f"● {oid}", "Knowledge Object", obj.content[:50]])
            node_item.setForeground(0, qc); node_item.setForeground(1, QColor("#80cbc4"))
            for e in obj.edges:
                ec = EDGE_COLORS.get(e.edge_type, (0.5,0.5,0.5))
                eqc = QColor(int(ec[0]*255), int(ec[1]*255), int(ec[2]*255))
                meta = ', '.join(f'{k}={v}' for k,v in e.metadata.items()) if e.metadata else ''
                edge_item = QTreeWidgetItem([f"  → {e.target_id}", e.edge_type.value, f"w={e.weight:.1f}  {meta}"])
                edge_item.setForeground(0, QColor("#ffab91"))
                edge_item.setForeground(1, eqc)
                node_item.addChild(edge_item)
            self.graph_tree.addTopLevelItem(node_item)
        self.graph_tree.expandAll()

    # ─── Vector DB ───

    def _new_db(self):
        self.db = VectorDB(self.dim_spin.value(), DistanceMetric(self.metric_cb.currentText()))
        self._update_stats()

    def _generate_vectors(self, n):
        if not self.db: self._new_db()
        for i in range(n):
            v = np.random.uniform(-5, 5, self.db.dimension)
            c = tuple(np.random.random(3) * 0.5 + 0.3)
            self.db.add_vector(f"v{len(self.db)+i}", v, {'color': c})
        data = [(e.vector, e.metadata.get('color', (0.5,0.5,0.5)), e.id) for e in self.db.get_all_vectors()]
        self.gl.set_vec_points(data)
        self._update_stats()
        self._log(f"Generated {n} vectors in DB")

    def _query_random(self):
        if not self.db or len(self.db) == 0: return
        qv = np.random.uniform(-5, 5, self.db.dimension)
        results = self.db.query(qv, self.k_spin.value())
        all_v = self.db.get_all_vectors()
        nbr_idx = []
        for e, _ in results:
            for i, v in enumerate(all_v):
                if v.id == e.id: nbr_idx.append(i); break
        self.gl.set_vec_query(qv, nbr_idx)
        self.results_table.setRowCount(len(results))
        for i, (e, d) in enumerate(results):
            self.results_table.setItem(i, 0, QTableWidgetItem(str(i+1)))
            self.results_table.setItem(i, 1, QTableWidgetItem(e.id))
            self.results_table.setItem(i, 2, QTableWidgetItem(f"{d:.4f}"))
            self.results_table.setItem(i, 3, QTableWidgetItem(str(np.round(e.vector[:3], 2))))
        self.tabs.setCurrentIndex(2)
        self._log(f"Vector query: {len(results)} neighbors ({self.db.metric.value})")

    # ─── View ───

    def _toggle_anim(self):
        self.gl.animate = not self.gl.animate
        if self.gl.animate: self.timer.start(16)
        else: self.timer.stop()

    def _reset_cam(self):
        self.gl.rotation_x = 20; self.gl.rotation_y = -30; self.gl.zoom = -18; self.gl.update()

    def _tick(self):
        if self.gl.animate: self.gl.update()

    def _update_stats(self):
        parts = []
        if self.topo_engine:
            s = self.topo_engine.get_stats()
            parts.append(f"Manifold: {s['objects']} objects, {s['edges']} edges")
            if 'edge_types' in s:
                parts.append("Edges: " + ", ".join(f"{k}({v})" for k,v in s['edge_types'].items()))
        if self.db:
            parts.append(f"VectorDB: {self.db.stats['total_vectors']} pts, {self.db.metric.value}")
        self.stats_label.setText("\n".join(parts))

    def _on_node_selected(self, nid, pos):
        if nid is None:
            self.info_bar.setText("🖱  Drag to rotate  •  Scroll to zoom  •  Click nodes to inspect")
            self.info_bar.setStyleSheet("background:#0a0a1a; color:#00c8ff; padding:10px; font-weight:bold; font-size:10pt;")
        else:
            obj = self.topo_engine.objects.get(nid) if self.topo_engine else None
            content = obj.content if obj else ""
            n_edges = len(obj.edges) if obj else 0
            edges_str = ", ".join(f"{e.edge_type.value}→{e.target_id}" for e in obj.edges) if obj else ""
            self.info_bar.setText(f"🎯 {nid}  —  {content}\n    Edges ({n_edges}): {edges_str}")
            self.info_bar.setStyleSheet("background:#0a1a0a; color:#00ff88; padding:10px; font-weight:bold; font-size:10pt;")
            self._log(f"Selected: {nid}")

    def _log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{ts}] {msg}")


# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = CookiXApp()
    window.show()
    sys.exit(app.exec_())
