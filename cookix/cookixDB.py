"""
SheafDB - Proof of Concept Implementation
==========================================
Demonstrates the core mathematical primitives:
1. Product manifold (Hyperbolic × Spherical × Euclidean)
2. Distributional representations (Gaussian on manifold)
3. Wasserstein distance vs cosine similarity
4. Context-aware sheaf retrieval
5. Sheaf cohomology anomaly detection

Requirements: pip install numpy scipy
"""

import numpy as np
from scipy.spatial.distance import cdist
from scipy.optimize import linear_sum_assignment
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import time


# ============================================================================
# 1. PRODUCT MANIFOLD: H^d × S^d × E^d
# ============================================================================

class HyperbolicSpace:
    """Lorentz model of hyperbolic space H^d with curvature κ < 0."""
    
    def __init__(self, dim: int, curvature: float = -1.0):
        self.dim = dim
        self.kappa = curvature  # negative
        self.c = abs(curvature)
    
    def project(self, x: np.ndarray) -> np.ndarray:
        """Project from Euclidean to Lorentz model.
        Lorentz point: (x_0, x_1, ..., x_d) where x_0 = sqrt(1/c + ||x||^2)
        """
        spatial = x[:self.dim]
        x0 = np.sqrt(1.0/self.c + np.dot(spatial, spatial))
        return np.concatenate([[x0], spatial])
    
    def lorentz_inner(self, x: np.ndarray, y: np.ndarray) -> float:
        """Minkowski inner product: -x_0*y_0 + x_1*y_1 + ... + x_d*y_d"""
        return -x[0]*y[0] + np.dot(x[1:], y[1:])
    
    def distance(self, x: np.ndarray, y: np.ndarray) -> float:
        """Geodesic distance on H^d."""
        inner = self.lorentz_inner(x, y)
        # Clamp for numerical stability
        inner = np.clip(inner, -np.inf, -1.0/self.c)
        return (1.0/np.sqrt(self.c)) * np.arccosh(-self.c * inner)


class SphericalSpace:
    """Unit sphere S^d with curvature κ > 0."""
    
    def __init__(self, dim: int, curvature: float = 1.0):
        self.dim = dim
        self.kappa = curvature
    
    def project(self, x: np.ndarray) -> np.ndarray:
        """Project to unit sphere."""
        spatial = x[:self.dim]
        norm = np.linalg.norm(spatial)
        if norm < 1e-10:
            result = np.zeros(self.dim)
            result[0] = 1.0
            return result
        return spatial / norm
    
    def distance(self, x: np.ndarray, y: np.ndarray) -> float:
        """Great circle distance on S^d."""
        dot = np.clip(np.dot(x, y), -1.0, 1.0)
        return (1.0/np.sqrt(self.kappa)) * np.arccos(dot)


class EuclideanSpace:
    """Standard Euclidean space E^d."""
    
    def __init__(self, dim: int):
        self.dim = dim
    
    def project(self, x: np.ndarray) -> np.ndarray:
        return x[:self.dim].copy()
    
    def distance(self, x: np.ndarray, y: np.ndarray) -> float:
        return np.linalg.norm(x - y)


class ProductManifold:
    """
    Product manifold M = H^d1_κ1 × S^d2_κ2 × E^d3
    
    The key insight: different semantic dimensions live in
    different geometries. Hierarchies → hyperbolic, 
    cycles → spherical, linear scales → Euclidean.
    """
    
    def __init__(self, h_dim: int = 4, s_dim: int = 3, e_dim: int = 5,
                 h_curvature: float = -1.0, s_curvature: float = 1.0):
        self.H = HyperbolicSpace(h_dim, h_curvature)
        self.S = SphericalSpace(s_dim, s_curvature)
        self.E = EuclideanSpace(e_dim)
        self.total_input_dim = h_dim + s_dim + e_dim
        self.signature = f"H^{h_dim}({h_curvature}) × S^{s_dim}({s_curvature}) × E^{e_dim}"
    
    def project(self, x: np.ndarray) -> dict:
        """Project a flat vector into the product manifold."""
        # Split input across components
        h_part = x[:self.H.dim]
        s_part = x[self.H.dim:self.H.dim + self.S.dim]
        e_part = x[self.H.dim + self.S.dim:self.H.dim + self.S.dim + self.E.dim]
        
        return {
            'H': self.H.project(h_part),
            'S': self.S.project(s_part),
            'E': self.E.project(e_part)
        }
    
    def distance(self, p: dict, q: dict) -> float:
        """
        Product metric: d(p,q)² = d_H(p_H, q_H)² + d_S(p_S, q_S)² + d_E(p_E, q_E)²
        """
        d_h = self.H.distance(p['H'], q['H'])
        d_s = self.S.distance(p['S'], q['S'])
        d_e = self.E.distance(p['E'], q['E'])
        return np.sqrt(d_h**2 + d_s**2 + d_e**2)


# ============================================================================
# 2. DISTRIBUTIONAL REPRESENTATION
# ============================================================================

@dataclass
class ManifoldDistribution:
    """
    A Gaussian distribution on the product manifold.
    Instead of a point, each semantic entity is a DISTRIBUTION.
    
    mean: point on the product manifold
    covariance_diag: diagonal covariance (uncertainty per dimension)
    
    This captures: "bank" is not a point, it's a CLOUD of possible meanings
    """
    mean: dict                          # Product manifold point
    covariance_diag: np.ndarray         # Uncertainty (simplified: diagonal)
    context: str = "default"            # Which context this is for
    
    def sample(self, n: int = 10) -> List[dict]:
        """Sample points from this distribution (in tangent space, simplified)."""
        samples = []
        for _ in range(n):
            noise_h = np.random.randn(len(self.mean['H'])) * np.sqrt(self.covariance_diag[:len(self.mean['H'])])
            noise_s = np.random.randn(len(self.mean['S'])) * np.sqrt(self.covariance_diag[len(self.mean['H']):len(self.mean['H'])+len(self.mean['S'])])
            noise_e = np.random.randn(len(self.mean['E'])) * np.sqrt(self.covariance_diag[-len(self.mean['E']):])
            
            samples.append({
                'H': self.mean['H'] + noise_h * 0.1,  # Small perturbation
                'S': self.mean['S'] + noise_s * 0.1,
                'E': self.mean['E'] + noise_e * 0.1
            })
        return samples


# ============================================================================
# 3. WASSERSTEIN DISTANCE (Simplified EMD)
# ============================================================================

def wasserstein_distance_1d(p: np.ndarray, q: np.ndarray) -> float:
    """1D Wasserstein distance (exact, O(n log n))."""
    return np.mean(np.abs(np.sort(p) - np.sort(q)))


def wasserstein_distance_manifold(
    dist_a: ManifoldDistribution, 
    dist_b: ManifoldDistribution,
    manifold: ProductManifold,
    n_samples: int = 50
) -> float:
    """
    Approximate Wasserstein distance between two distributions
    on the product manifold via sampling + assignment.
    
    This is the KEY advantage over cosine similarity:
    we compare DISTRIBUTIONS, not points.
    """
    samples_a = dist_a.sample(n_samples)
    samples_b = dist_b.sample(n_samples)
    
    # Compute pairwise manifold distances
    cost_matrix = np.zeros((n_samples, n_samples))
    for i, sa in enumerate(samples_a):
        for j, sb in enumerate(samples_b):
            cost_matrix[i, j] = manifold.distance(sa, sb)
    
    # Optimal assignment (Hungarian algorithm)
    row_ind, col_ind = linear_sum_assignment(cost_matrix)
    return cost_matrix[row_ind, col_ind].mean()


def gaussian_wasserstein_2(
    dist_a: ManifoldDistribution, 
    dist_b: ManifoldDistribution,
    manifold: ProductManifold
) -> float:
    """
    Closed-form W2 between Gaussians (Bures-Wasserstein distance).
    Much faster than sampling-based approach.
    
    W2² = ||μ₁ - μ₂||² + Tr(Σ₁ + Σ₂ - 2(Σ₁^½ Σ₂ Σ₁^½)^½)
    
    For diagonal covariances: simplified to element-wise computation
    """
    # Mean distance on product manifold
    mean_dist = manifold.distance(dist_a.mean, dist_b.mean)
    
    # Bures metric for diagonal covariances
    s1 = dist_a.covariance_diag
    s2 = dist_b.covariance_diag
    # For diagonal case: Tr(Σ₁ + Σ₂ - 2√(Σ₁Σ₂)) = Σ(√σ₁ᵢ - √σ₂ᵢ)²
    bures = np.sum((np.sqrt(s1) - np.sqrt(s2))**2)
    
    return np.sqrt(mean_dist**2 + bures)


# ============================================================================
# 4. SHEAF DATA STRUCTURES
# ============================================================================

@dataclass
class SheafEntry:
    """
    A database entry in SheafDB.
    
    Unlike VectorDB (one point per entry), SheafDB stores:
    - Multiple context-dependent distributions (stalks)
    - Metadata for the base space
    """
    id: str
    text: str
    contexts: List[str]
    stalks: Dict[str, ManifoldDistribution]  # context → distribution
    metadata: Dict = field(default_factory=dict)


class BaseSpace:
    """
    The topological base space T.
    Nodes = contexts/topics, edges = overlapping contexts.
    
    This determines HOW entries are localized and retrieved.
    """
    
    def __init__(self, contexts: List[str], overlaps: List[Tuple[str, str]]):
        self.contexts = contexts
        self.overlaps = overlaps
        self._overlap_set = set((a,b) for a,b in overlaps) | set((b,a) for a,b in overlaps)
    
    def do_overlap(self, ctx_a: str, ctx_b: str) -> bool:
        return (ctx_a, ctx_b) in self._overlap_set
    
    def localize(self, text: str, keywords: Dict[str, List[str]]) -> List[str]:
        """
        Determine which contexts a text belongs to.
        (Simplified: keyword-based. Real version: learned classifier)
        """
        text_lower = text.lower()
        matched = []
        for ctx, kws in keywords.items():
            if any(kw in text_lower for kw in kws):
                matched.append(ctx)
        return matched if matched else [self.contexts[0]]  # default context


class RestrictionMap:
    """
    Maps between overlapping context stalks.
    ρ_{U,V}: F(U) → F(V)
    
    Encodes how meaning transforms across contexts.
    E.g., "credit" in banking → "credit" in music production
    """
    
    def __init__(self, source_ctx: str, target_ctx: str, transform: np.ndarray):
        self.source = source_ctx
        self.target = target_ctx
        self.transform = transform  # Linear map (simplified)


# ============================================================================
# 5. SheafDB — THE DATABASE
# ============================================================================

class SheafDB:
    """
    SheafDB: A Sheaf-Theoretic Database for Contextual Semantic Retrieval.
    
    Core idea: Store data as sections of a sheaf over a structured 
    topological space, using distributional representations on a 
    mixed-curvature product manifold.
    """
    
    def __init__(self, 
                 manifold: ProductManifold,
                 base_space: BaseSpace,
                 context_keywords: Dict[str, List[str]]):
        self.manifold = manifold
        self.base_space = base_space
        self.context_keywords = context_keywords
        self.entries: Dict[str, SheafEntry] = {}
        self.restriction_maps: Dict[Tuple[str,str], RestrictionMap] = {}
        self._counter = 0
    
    def insert(self, text: str, embedding: np.ndarray, 
               metadata: Dict = None) -> SheafEntry:
        """
        Insert a document into SheafDB.
        
        Unlike VectorDB.insert(embedding), we:
        1. Localize to contexts
        2. Create distributional representations per context
        3. Store as a sheaf section
        """
        self._counter += 1
        entry_id = f"entry_{self._counter}"
        
        # 1. Localize: which contexts does this belong to?
        contexts = self.base_space.localize(text, self.context_keywords)
        
        # 2. Create distributional stalks per context
        stalks = {}
        for ctx in contexts:
            # Project to product manifold with context-dependent offset
            ctx_offset = hash(ctx) % 100 / 100.0  # Simplified context modulation
            modified_emb = embedding.copy()
            modified_emb[:3] += ctx_offset * 0.1
            
            manifold_point = self.manifold.project(modified_emb)
            
            # Estimate uncertainty (higher for polysemous words)
            base_uncertainty = 0.1
            polysemy_factor = len(contexts)  # More contexts = more uncertain
            covariance = np.ones(len(embedding)) * base_uncertainty * polysemy_factor
            
            stalks[ctx] = ManifoldDistribution(
                mean=manifold_point,
                covariance_diag=covariance,
                context=ctx
            )
        
        entry = SheafEntry(
            id=entry_id, text=text, contexts=contexts,
            stalks=stalks, metadata=metadata or {}
        )
        self.entries[entry_id] = entry
        return entry
    
    def query(self, text: str, embedding: np.ndarray, k: int = 5) -> List[Tuple[SheafEntry, float]]:
        """
        Sheaf-theoretic query:
        1. Localize query to contexts
        2. Build query section (distribution per context)
        3. Per-context Wasserstein matching
        4. Glue results across contexts
        5. Rank by global consistency
        """
        # 1. Localize
        q_contexts = self.base_space.localize(text, self.context_keywords)
        
        # 2. Build query distributions
        q_stalks = {}
        for ctx in q_contexts:
            ctx_offset = hash(ctx) % 100 / 100.0
            modified_emb = embedding.copy()
            modified_emb[:3] += ctx_offset * 0.1
            
            manifold_point = self.manifold.project(modified_emb)
            covariance = np.ones(len(embedding)) * 0.05  # Lower uncertainty for query
            
            q_stalks[ctx] = ManifoldDistribution(
                mean=manifold_point,
                covariance_diag=covariance,
                context=ctx
            )
        
        # 3. Score all entries
        results = []
        for entry_id, entry in self.entries.items():
            # Find shared contexts between query and entry
            shared_contexts = set(q_contexts) & set(entry.contexts)
            
            if not shared_contexts:
                # No shared context — use default distance (penalized)
                default_ctx = q_contexts[0]
                if default_ctx in entry.stalks:
                    dist = gaussian_wasserstein_2(
                        q_stalks[default_ctx], entry.stalks[default_ctx], self.manifold
                    )
                    results.append((entry, dist + 1.0))  # Penalty for no context match
                continue
            
            # 4. Wasserstein distance per shared context
            context_distances = []
            for ctx in shared_contexts:
                if ctx in q_stalks and ctx in entry.stalks:
                    d = gaussian_wasserstein_2(
                        q_stalks[ctx], entry.stalks[ctx], self.manifold
                    )
                    context_distances.append(d)
            
            if context_distances:
                # Average distance across contexts
                avg_dist = np.mean(context_distances)
                
                # 5. Consistency bonus: more shared contexts = better
                consistency_bonus = -0.1 * len(shared_contexts)
                
                final_score = avg_dist + consistency_bonus
                results.append((entry, final_score))
        
        # Sort by score (lower = better)
        results.sort(key=lambda x: x[1])
        return results[:k]
    
    def compute_cohomology_h1(self) -> List[Dict]:
        """
        Compute H¹ sheaf cohomology to detect semantic inconsistencies.
        
        H¹ ≠ 0 means there exist local sections that CANNOT be glued
        into a globally consistent section → semantic contradictions.
        """
        anomalies = []
        
        for ctx_a, ctx_b in self.base_space.overlaps:
            # For each pair of overlapping contexts, check if entries
            # that appear in both contexts are consistent
            for entry_id, entry in self.entries.items():
                if ctx_a in entry.stalks and ctx_b in entry.stalks:
                    stalk_a = entry.stalks[ctx_a]
                    stalk_b = entry.stalks[ctx_b]
                    
                    # Measure inconsistency: how different are the stalks?
                    inconsistency = gaussian_wasserstein_2(
                        stalk_a, stalk_b, self.manifold
                    )
                    
                    # Threshold for anomaly
                    if inconsistency > 1.5:
                        anomalies.append({
                            'entry': entry.id,
                            'text': entry.text,
                            'contexts': (ctx_a, ctx_b),
                            'inconsistency': inconsistency,
                            'interpretation': f"'{entry.text}' has contradictory "
                                            f"meanings in '{ctx_a}' vs '{ctx_b}'"
                        })
        
        return anomalies


# ============================================================================
# 6. DEMONSTRATION
# ============================================================================

def demo():
    print("=" * 70)
    print("   SheafDB — Proof of Concept Demonstration")
    print("   A Sheaf-Theoretic Database for Contextual Semantic Retrieval")
    print("=" * 70)
    
    # ---- Setup manifold ----
    print("\n[1] Creating product manifold: H⁴(-1.0) × S³(1.0) × E⁵")
    manifold = ProductManifold(h_dim=4, s_dim=3, e_dim=5)
    print(f"    Signature: {manifold.signature}")
    
    # ---- Setup base space (topology) ----
    print("\n[2] Building base topological space (semantic contexts)")
    contexts = ["finance", "technology", "nature", "legal"]
    overlaps = [
        ("finance", "technology"),  # fintech
        ("finance", "legal"),       # financial law
        ("technology", "nature"),   # environmental tech
    ]
    base_space = BaseSpace(contexts, overlaps)
    print(f"    Contexts: {contexts}")
    print(f"    Overlaps: {overlaps}")
    
    # ---- Context keywords (simplified localization) ----
    context_keywords = {
        "finance": ["bank", "credit", "payment", "loan", "invest", "stock", "money", "swift", "pacs"],
        "technology": ["algorithm", "software", "code", "data", "compute", "digital", "ai", "model"],
        "nature": ["river", "tree", "bank", "forest", "water", "mountain", "earth", "flow"],
        "legal": ["contract", "law", "regulation", "compliance", "court", "rights", "credit"],
    }
    
    # ---- Create SheafDB ----
    print("\n[3] Initializing SheafDB")
    db = SheafDB(manifold, base_space, context_keywords)
    
    # ---- Insert documents ----
    print("\n[4] Inserting documents (with distributional representations)")
    np.random.seed(42)
    
    documents = [
        ("SWIFT payment processing via pacs.008 message", 
         np.random.randn(12) * 0.3 + np.array([1,0,0,0, 0.5,0.5,0, 0,0,0,0,0])),
        ("Bank loan credit scoring algorithm",
         np.random.randn(12) * 0.3 + np.array([0.8,0.2,0,0, 0.3,0.5,0, 0.1,0,0,0,0])),
        ("River bank erosion and water flow patterns",
         np.random.randn(12) * 0.3 + np.array([0,0,0.8,0, 0,0,0.9, 0,0.5,0,0,0])),
        ("Credit score compliance with financial regulations",
         np.random.randn(12) * 0.3 + np.array([0.9,0,0,0.5, 0.4,0.5,0, 0,0,0,0,0.3])),
        ("Machine learning model for stock prediction",
         np.random.randn(12) * 0.3 + np.array([0.5,0.5,0,0, 0.3,0.6,0, 0.2,0,0,0,0])),
        ("Digital payment gateway software integration",
         np.random.randn(12) * 0.3 + np.array([0.7,0.4,0,0, 0.4,0.5,0, 0.1,0,0,0,0])),
        ("Forest river bank ecosystem conservation law",
         np.random.randn(12) * 0.3 + np.array([0,0,0.6,0.4, 0,0,0.8, 0,0.3,0,0,0.2])),
        ("ISO 20022 SWIFT message format specification",
         np.random.randn(12) * 0.3 + np.array([0.9,0.1,0,0, 0.5,0.5,0, 0,0,0,0,0])),
    ]
    
    for text, emb in documents:
        entry = db.insert(text, emb)
        contexts_str = ", ".join(entry.contexts)
        stalks_info = ", ".join(f"{ctx}(σ={entry.stalks[ctx].covariance_diag.mean():.2f})" 
                                for ctx in entry.contexts)
        print(f"    ✓ [{entry.id}] \"{text[:50]}...\"")
        print(f"      Contexts: [{contexts_str}]")
        print(f"      Stalks: [{stalks_info}]")
    
    # ---- Query: Demonstrate context-aware retrieval ----
    print("\n" + "=" * 70)
    print("   QUERY DEMONSTRATIONS")
    print("=" * 70)
    
    # Query 1: Finance context — "bank" should prefer financial meanings
    print("\n[Query 1] \"bank payment processing\" (finance context)")
    q_emb = np.random.randn(12) * 0.2 + np.array([0.85,0.15,0,0, 0.5,0.5,0, 0,0,0,0,0])
    results = db.query("bank payment processing", q_emb, k=5)
    for entry, score in results:
        print(f"    Score: {score:.4f} | Contexts: {entry.contexts} | \"{entry.text[:60]}\"")
    
    # Query 2: Nature context — "bank" should prefer river meanings
    print("\n[Query 2] \"river bank water flow\" (nature context)")
    q_emb = np.random.randn(12) * 0.2 + np.array([0,0,0.7,0, 0,0,0.8, 0,0.4,0,0,0])
    results = db.query("river bank water flow", q_emb, k=5)
    for entry, score in results:
        print(f"    Score: {score:.4f} | Contexts: {entry.contexts} | \"{entry.text[:60]}\"")
    
    # Query 3: Cross-context — "credit regulation" spans finance + legal
    print("\n[Query 3] \"credit regulation compliance\" (finance + legal context)")
    q_emb = np.random.randn(12) * 0.2 + np.array([0.8,0,0,0.3, 0.4,0.5,0, 0,0,0,0,0.2])
    results = db.query("credit regulation compliance", q_emb, k=5)
    for entry, score in results:
        ctx_match = len(set(entry.contexts) & {"finance", "legal"})
        print(f"    Score: {score:.4f} | Contexts: {entry.contexts} | "
              f"Cross-ctx match: {ctx_match} | \"{entry.text[:55]}\"")
    
    # ---- Cohomology: Detect semantic anomalies ----
    print("\n" + "=" * 70)
    print("   SHEAF COHOMOLOGY — Anomaly Detection (H¹)")
    print("=" * 70)
    
    anomalies = db.compute_cohomology_h1()
    if anomalies:
        print(f"\n    Found {len(anomalies)} semantic inconsistencies:")
        for a in anomalies:
            print(f"    ⚠ [{a['entry']}] {a['interpretation']}")
            print(f"      Inconsistency score: {a['inconsistency']:.4f}")
    else:
        print("\n    ✓ No semantic inconsistencies detected (H¹ = 0)")
    
    # ---- Comparison: SheafDB vs VectorDB ----
    print("\n" + "=" * 70)
    print("   COMPARISON: SheafDB vs VectorDB (Cosine Similarity)")
    print("=" * 70)
    
    print("\n   Query: \"bank\" — a polysemous word")
    print("   In VectorDB, a single cosine search returns mixed results.")
    print("   In SheafDB, context-aware retrieval separates senses.\n")
    
    # Simulate VectorDB: just cosine similarity on flat embeddings
    all_embeddings = np.array([emb for _, emb in documents])
    all_texts = [text for text, _ in documents]
    
    # "bank" query — ambiguous
    q_bank = np.random.randn(12) * 0.2 + np.array([0.5,0,0.3,0, 0.3,0.3,0.3, 0,0.2,0,0,0])
    
    # VectorDB: cosine similarity
    from numpy.linalg import norm
    cosine_scores = []
    for i, emb in enumerate(all_embeddings):
        cos_sim = np.dot(q_bank, emb) / (norm(q_bank) * norm(emb) + 1e-10)
        cosine_scores.append((all_texts[i], cos_sim))
    cosine_scores.sort(key=lambda x: -x[1])
    
    print("   VectorDB (cosine similarity) — no context awareness:")
    for text, score in cosine_scores[:5]:
        print(f"    {score:.4f} | \"{text[:60]}\"")
    
    # SheafDB: finance context
    print("\n   SheafDB — FINANCE context (\"bank\" = financial institution):")
    results_fin = db.query("bank financial services", q_bank, k=5)
    for entry, score in results_fin[:5]:
        marker = "✓" if "finance" in entry.contexts else " "
        print(f"    {marker} {score:.4f} | [{','.join(entry.contexts)}] \"{entry.text[:55]}\"")
    
    # SheafDB: nature context
    print("\n   SheafDB — NATURE context (\"bank\" = river bank):")
    q_bank_nature = np.random.randn(12) * 0.2 + np.array([0,0,0.7,0, 0,0,0.8, 0,0.4,0,0,0])
    results_nat = db.query("bank river erosion water", q_bank_nature, k=5)
    for entry, score in results_nat[:5]:
        marker = "✓" if "nature" in entry.contexts else " "
        print(f"    {marker} {score:.4f} | [{','.join(entry.contexts)}] \"{entry.text[:55]}\"")
    
    # ---- Performance note ----
    print("\n" + "=" * 70)
    print("   KEY TAKEAWAYS")
    print("=" * 70)
    print("""
    1. DISTRIBUTIONAL: Entries are distributions, not points
       → Captures uncertainty and polysemy naturally
    
    2. CONTEXT-AWARE: Sheaf sections separate different senses
       → "bank" in finance ≠ "bank" in nature
    
    3. MIXED CURVATURE: H × S × E matches data structure
       → Hierarchies, cycles, and linear scales coexist
    
    4. WASSERSTEIN DISTANCE: Principled metric for distributions
       → No more arbitrary cosine vs Euclidean choice
    
    5. COHOMOLOGY: Built-in anomaly detection via H¹
       → Automatically finds semantic contradictions
    
    6. COMPOSITIONALITY: Cross-context queries via gluing
       → "credit regulation" naturally spans finance + legal
    """)
    
    print("=" * 70)
    print("   SheafDB v0.1 — Proof of Concept Complete")
    print("   \"The geometry of thought is not flat.\"")
    print("=" * 70)


if __name__ == "__main__":
    demo()
