"""
analysis/collector.py
セッション単位のリアルタイム評価データ収集

設計:
- 対話中はテキストのみ収集（レイテンシ影響なし）
- セッション終了時にembedding計算をバッチ実行
- API障害時はembeddingをスキップしテキストのみ保存（フェイルセーフ）
"""
import os
import json
import datetime
import uuid
from analysis.metrics import compute_worker_dispersion, compute_slot_contribution

EVAL_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "evaluation_data")


class SessionCollector:
    """1セッション（1回のグラフ実行）の評価データを収集する。"""

    def __init__(self, trigger_type="user", input_query=""):
        self.session_id = f"EVAL-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:6].upper()}"
        self.timestamp = datetime.datetime.now().isoformat()
        self.trigger_type = trigger_type
        self.input_query = input_query

        # ターンごとのデータ
        self.turns = []
        self._current_turn = {}
        self._current_turn_number = 0

        # Slot呼び出しデータ
        self.slot_invocations = []
        self._pending_pre_slot_master = None

        # セッション結果
        self.resolution_status = "UNKNOWN"
        self.audit_count = 0

    # ==========================================
    # テキスト収集（対話中に呼ばれる）
    # ==========================================
    def record_worker(self, worker_id, text):
        """Worker出力を記録する。worker_bが呼ばれるとき新しいターンが開始。"""
        if worker_id == "worker_b":
            # 前のターンを保存して新しいターンを開始
            if self._current_turn:
                self.turns.append(self._current_turn)
            self._current_turn_number += 1
            self._current_turn = {"turn": self._current_turn_number}

        self._current_turn[worker_id] = text

    def record_master_a(self, text, routing_decision):
        """Master A出力とルーティング決定を記録する。"""
        self._current_turn["master_a"] = text
        self._current_turn["routing_decision"] = routing_decision

        if routing_decision == "audit":
            self.audit_count += 1

        # Slot呼び出しの場合、pre-slot出力を保持
        if routing_decision in ("ask_claude", "ask_gemini"):
            self._pending_pre_slot_master = text

    def record_slot_response(self, target_agent, post_master_text):
        """Slot統合後のMaster A出力を記録する。"""
        if self._pending_pre_slot_master:
            self.slot_invocations.append({
                "target_agent": target_agent,
                "pre_slot_master_output": self._pending_pre_slot_master,
                "post_slot_master_output": post_master_text,
            })
            self._pending_pre_slot_master = None

    def record_resolution(self, status):
        """セッション終了ステータスを記録する（FINISH / UNRESOLVED）。"""
        self.resolution_status = status

    # ==========================================
    # Embedding計算とJSON保存（セッション終了時）
    # ==========================================
    async def finalize(self, embeddings_func):
        """セッション終了時にembeddingを計算し、JSONに保存する。

        Args:
            embeddings_func: テキストのリストを受け取りembeddingリストを返す関数
                             （infrastructure/vector_store.py の embeddings.embed_documents）
        """
        # 最後のターンを保存
        if self._current_turn:
            self.turns.append(self._current_turn)
            self._current_turn = {}

        # ターンがなければスキップ
        if not self.turns:
            print("📊 [Eval] 評価データなし（ターン0）。スキップします。")
            return

        # Embedding計算（フェイルセーフ）
        try:
            await self._compute_embeddings(embeddings_func)
        except Exception as e:
            print(f"⚠️ [Eval] Embedding計算エラー（テキストのみ保存します）: {e}")

        # JSON保存
        self._save_json()

    def _embed_single(self, embeddings_func, text):
        """1テキストのembeddingを計算する。
        VertexAIEmbeddingsのバッチ処理の不安定さを回避するため、
        常に1テキストずつ処理する。"""
        result = embeddings_func([text])
        if result and len(result) > 0:
            # result は [[float, float, ...]] の形式
            return result[0]
        return None

    async def _compute_embeddings(self, embeddings_func):
        """embeddingを1テキストずつ計算し、メトリクスを算出する。"""

        # ==========================================
        # Phase 1: Worker分散度の計算（ターンごと）
        # ==========================================
        for turn_idx, turn in enumerate(self.turns):
            try:
                worker_embeddings = {}
                for field in ["worker_b", "worker_c", "worker_d"]:
                    text = turn.get(field)
                    if text:
                        emb = self._embed_single(embeddings_func, text)
                        if emb:
                            worker_embeddings[field] = emb

                # 3つ揃っていなければスキップ
                if len(worker_embeddings) < 3:
                    print(f"⚠️ [Eval] Turn {turn_idx+1}: Worker embedding不足 ({len(worker_embeddings)}/3)")
                    continue

                # 分散度計算
                dispersion = compute_worker_dispersion(worker_embeddings)
                if dispersion:
                    turn["dispersion"] = dispersion
                    print(f"📊 [Eval] Turn {turn_idx+1} 分散度: mean_pairwise={dispersion['mean_pairwise_distance']:.4f}")

            except Exception as e:
                print(f"⚠️ [Eval] Turn {turn_idx+1} 分散度計算エラー: {e}")

        # ==========================================
        # Phase 2: 外部知性寄与度の計算
        # ==========================================
        for i, slot in enumerate(self.slot_invocations):
            try:
                pre_text = slot.get("pre_slot_master_output", "")
                post_text = slot.get("post_slot_master_output", "")

                if not pre_text or not post_text:
                    continue

                pre_emb = self._embed_single(embeddings_func, pre_text)
                post_emb = self._embed_single(embeddings_func, post_text)

                if not pre_emb or not post_emb:
                    print(f"⚠️ [Eval] Slot {i}: embedding取得失敗")
                    continue

                contribution = compute_slot_contribution(pre_emb, post_emb)
                if contribution:
                    slot["embedding_distance"] = contribution["embedding_distance"]
                    slot["cosine_similarity"] = contribution["cosine_similarity"]
                    print(f"📊 [Eval] Slot {slot.get('target_agent', '?')} 寄与度: distance={contribution['embedding_distance']:.4f}")

            except Exception as e:
                print(f"⚠️ [Eval] Slot {i} 寄与度計算エラー: {e}")

        print(f"📊 [Eval] メトリクス計算完了。")

    def _save_json(self):
        """セッションデータをJSONファイルに保存する。"""
        os.makedirs(EVAL_DATA_DIR, exist_ok=True)

        data = {
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "trigger_type": self.trigger_type,
            "input_query": self.input_query,
            "total_turns": len(self.turns),
            "resolution_status": self.resolution_status,
            "audit_count": self.audit_count,
            "turns": self.turns,
            "slot_invocations": self.slot_invocations,
        }

        # Slot前後のMaster A原文はJSONサイズ削減のため先頭500文字に制限
        for slot in data["slot_invocations"]:
            for key in ["pre_slot_master_output", "post_slot_master_output"]:
                if key in slot and len(slot[key]) > 500:
                    slot[key] = slot[key][:500] + "...(truncated)"

        filepath = os.path.join(EVAL_DATA_DIR, f"{self.session_id}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"📊 [Eval] 評価データ保存: {filepath}")
        return filepath


# ==========================================
# モジュールレベルのセッション管理
# ==========================================
_current_collector = None


def start_session(trigger_type="user", input_query=""):
    """新しい評価セッションを開始する。"""
    global _current_collector
    _current_collector = SessionCollector(trigger_type=trigger_type, input_query=input_query)
    return _current_collector


def get_collector():
    """現在のセッションコレクターを取得する。"""
    return _current_collector


async def finalize_session(embeddings_func):
    """現在のセッションを終了し、データを保存する。"""
    global _current_collector
    if _current_collector:
        await _current_collector.finalize(embeddings_func)
        _current_collector = None
