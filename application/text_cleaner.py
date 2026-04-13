"""
application/text_cleaner.py
LLM出力の浄化（思考プロセス漏洩対策）
"""
import re
import ast

def extract_clean_text(raw_content):
    """Geminiの思考プロセスやJSON構造を除去し、純粋なテキストを抽出する"""
    res_text = str(raw_content)
    if isinstance(raw_content, list):
        texts = [b.get("text", "") for b in raw_content if isinstance(b, dict) and "text" in b]
        res_text = texts[-1] if texts else res_text
    elif isinstance(raw_content, str) and ("thought_signature" in raw_content or "[{'type':" in raw_content):
        try:
            parsed = ast.literal_eval(raw_content)
            if isinstance(parsed, list):
                texts = [b.get("text", "") for b in parsed if isinstance(b, dict) and "text" in b]
                res_text = texts[-1] if texts else res_text
        except Exception:
            matches = re.findall(r"['\"]text['\"]\s*:\s*['\"](.*?)['\"]", raw_content, flags=re.DOTALL)
            if matches:
                res_text = matches[-1].replace("\\n", "\n").replace("\\'", "'").replace('\\"', '"')
    return res_text
