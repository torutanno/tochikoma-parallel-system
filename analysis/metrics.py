"""
analysis/metrics.py
評価メトリクスの計算関数（純粋な計算ロジック、外部依存なし）

Haptic Visuality実験手法を転用:
- Gemini Embedding 2によるベクトル化
- コサイン類似度/距離による概念間距離の定量化
"""
import math


def cosine_similarity(vec1, vec2):
    """2つのベクトル間のコサイン類似度を計算する。

    Returns:
        float: -1.0〜1.0（1.0が完全一致、0.0が直交、-1.0が正反対）
    """
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot_product / (norm1 * norm2)


def cosine_distance(vec1, vec2):
    """コサイン距離（1 - cosine_similarity）。0〜2の範囲。
    値が大きいほど概念的に離れている。"""
    return 1.0 - cosine_similarity(vec1, vec2)


def compute_worker_dispersion(embeddings_dict):
    """Worker B/C/D のembeddingから意見分散度を計算する。

    Args:
        embeddings_dict: {"worker_b": [...], "worker_c": [...], "worker_d": [...]}

    Returns:
        dict: {
            "bc_distance": float,
            "bd_distance": float,
            "cd_distance": float,
            "mean_pairwise_distance": float,
            "centroid_distance_mean": float
        }
    """
    b = embeddings_dict.get("worker_b")
    c = embeddings_dict.get("worker_c")
    d = embeddings_dict.get("worker_d")

    if not b or not c or not d:
        return None

    # ペアワイズ距離
    bc = cosine_distance(b, c)
    bd = cosine_distance(b, d)
    cd = cosine_distance(c, d)
    mean_pairwise = (bc + bd + cd) / 3.0

    # 重心からの平均距離
    dim = len(b)
    centroid = [(b[i] + c[i] + d[i]) / 3.0 for i in range(dim)]
    dist_b = cosine_distance(b, centroid)
    dist_c = cosine_distance(c, centroid)
    dist_d = cosine_distance(d, centroid)
    centroid_distance_mean = (dist_b + dist_c + dist_d) / 3.0

    return {
        "bc_distance": round(bc, 6),
        "bd_distance": round(bd, 6),
        "cd_distance": round(cd, 6),
        "mean_pairwise_distance": round(mean_pairwise, 6),
        "centroid_distance_mean": round(centroid_distance_mean, 6)
    }


def compute_slot_contribution(pre_embedding, post_embedding):
    """外部知性寄与度: Slot呼び出し前後のMaster A結論のembedding距離。

    Args:
        pre_embedding: Slot呼び出し前のMaster A出力のembedding
        post_embedding: Slot統合後のMaster A出力のembedding

    Returns:
        dict: {"embedding_distance": float, "cosine_similarity": float}
    """
    if not pre_embedding or not post_embedding:
        return None

    sim = cosine_similarity(pre_embedding, post_embedding)
    dist = 1.0 - sim

    return {
        "embedding_distance": round(dist, 6),
        "cosine_similarity": round(sim, 6)
    }
