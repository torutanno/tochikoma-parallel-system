"""
analysis/report_generator.py
蓄積された評価JSONからバッチ分析を行い、Markdownレポートを生成する。

使用方法:
    python -m analysis.report_generator
    python -m analysis.report_generator --output reports/report.md
"""
import os
import json
import datetime
import math
import argparse

EVAL_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "evaluation_data")
DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")


def load_all_sessions():
    """evaluation_data/ から全JSONを読み込む。"""
    sessions = []
    if not os.path.exists(EVAL_DATA_DIR):
        return sessions

    for filename in sorted(os.listdir(EVAL_DATA_DIR)):
        if filename.endswith(".json"):
            filepath = os.path.join(EVAL_DATA_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    sessions.append(json.load(f))
            except Exception as e:
                print(f"⚠️ 読み込みエラー: {filepath}: {e}")

    return sessions


def compute_statistics(sessions):
    """全セッションから統計を計算する。"""
    if not sessions:
        return None

    stats = {
        "total_sessions": len(sessions),
        "period_start": sessions[0].get("timestamp", "N/A"),
        "period_end": sessions[-1].get("timestamp", "N/A"),
    }

    # --- Metric 2: [UNRESOLVED]率 ---
    resolutions = [s.get("resolution_status", "UNKNOWN") for s in sessions]
    unresolved_count = resolutions.count("UNRESOLVED")
    finish_count = resolutions.count("FINISH")
    stats["unresolved_rate"] = unresolved_count / len(sessions) if sessions else 0
    stats["unresolved_count"] = unresolved_count
    stats["finish_count"] = finish_count

    # トリガー種別ごとの内訳
    trigger_breakdown = {}
    for s in sessions:
        trigger = s.get("trigger_type", "unknown")
        if trigger not in trigger_breakdown:
            trigger_breakdown[trigger] = {"total": 0, "unresolved": 0, "finish": 0}
        trigger_breakdown[trigger]["total"] += 1
        status = s.get("resolution_status", "UNKNOWN")
        if status == "UNRESOLVED":
            trigger_breakdown[trigger]["unresolved"] += 1
        elif status == "FINISH":
            trigger_breakdown[trigger]["finish"] += 1
    stats["trigger_breakdown"] = trigger_breakdown

    # --- Metric 1: 外部知性寄与度 ---
    slot_distances = []
    slot_by_agent = {}
    for s in sessions:
        for slot in s.get("slot_invocations", []):
            dist = slot.get("embedding_distance")
            if dist is not None:
                slot_distances.append(dist)
                agent = slot.get("target_agent", "unknown")
                if agent not in slot_by_agent:
                    slot_by_agent[agent] = []
                slot_by_agent[agent].append(dist)

    if slot_distances:
        stats["slot_contribution"] = {
            "total_invocations": len(slot_distances),
            "mean_distance": _mean(slot_distances),
            "std_distance": _std(slot_distances),
            "min_distance": min(slot_distances),
            "max_distance": max(slot_distances),
            "by_agent": {
                agent: {
                    "count": len(dists),
                    "mean_distance": _mean(dists),
                    "std_distance": _std(dists),
                }
                for agent, dists in slot_by_agent.items()
            }
        }
    else:
        stats["slot_contribution"] = None

    # --- Metric 3: Worker間意見分散度 ---
    dispersions = []
    for s in sessions:
        for turn in s.get("turns", []):
            disp = turn.get("dispersion")
            if disp:
                dispersions.append(disp)

    if dispersions:
        mean_pairwise_values = [d["mean_pairwise_distance"] for d in dispersions]
        centroid_values = [d["centroid_distance_mean"] for d in dispersions]
        stats["worker_dispersion"] = {
            "total_turns_measured": len(dispersions),
            "mean_pairwise_distance": {
                "mean": _mean(mean_pairwise_values),
                "std": _std(mean_pairwise_values),
                "min": min(mean_pairwise_values),
                "max": max(mean_pairwise_values),
            },
            "centroid_distance_mean": {
                "mean": _mean(centroid_values),
                "std": _std(centroid_values),
                "min": min(centroid_values),
                "max": max(centroid_values),
            }
        }
    else:
        stats["worker_dispersion"] = None

    # --- 付加統計 ---
    total_turns = [s.get("total_turns", 0) for s in sessions]
    audit_counts = [s.get("audit_count", 0) for s in sessions]
    stats["turns"] = {
        "mean": _mean(total_turns),
        "max": max(total_turns) if total_turns else 0,
    }
    stats["audits"] = {
        "total": sum(audit_counts),
        "sessions_with_audit": sum(1 for a in audit_counts if a > 0),
    }

    return stats


def generate_markdown_report(stats):
    """統計データからMarkdownレポートを生成する。"""
    if not stats:
        return "# Tochikoma Evaluation Report\n\nNo evaluation data found.\n"

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"# Tochikoma Evaluation Report",
        f"",
        f"Generated: {now}",
        f"Period: {stats['period_start']} — {stats['period_end']}",
        f"Total Sessions: {stats['total_sessions']}",
        f"",
        f"---",
        f"",
        f"## Metric 1: External Intelligence Contribution (外部知性寄与度)",
        f"",
    ]

    sc = stats.get("slot_contribution")
    if sc:
        lines += [
            f"Total Slot Invocations: {sc['total_invocations']}",
            f"",
            f"| Statistic | Embedding Distance |",
            f"|-----------|-------------------|",
            f"| Mean      | {sc['mean_distance']:.6f} |",
            f"| Std Dev   | {sc['std_distance']:.6f} |",
            f"| Min       | {sc['min_distance']:.6f} |",
            f"| Max       | {sc['max_distance']:.6f} |",
            f"",
        ]
        if sc.get("by_agent"):
            lines.append("### By Agent")
            lines.append("")
            lines.append("| Agent | Count | Mean Distance | Std Dev |")
            lines.append("|-------|-------|--------------|---------|")
            for agent, data in sc["by_agent"].items():
                lines.append(f"| {agent} | {data['count']} | {data['mean_distance']:.6f} | {data['std_distance']:.6f} |")
            lines.append("")
    else:
        lines.append("No slot invocations with embedding data found.")
        lines.append("")

    lines += [
        f"---",
        f"",
        f"## Metric 2: [UNRESOLVED] Rate (認知限界開示率)",
        f"",
        f"| Status | Count | Rate |",
        f"|--------|-------|------|",
        f"| FINISH | {stats['finish_count']} | {(stats['finish_count']/stats['total_sessions']*100):.1f}% |",
        f"| UNRESOLVED | {stats['unresolved_count']} | {(stats['unresolved_rate']*100):.1f}% |",
        f"",
        f"### By Trigger Type",
        f"",
        f"| Trigger | Total | FINISH | UNRESOLVED | UNRESOLVED Rate |",
        f"|---------|-------|--------|------------|-----------------|",
    ]
    for trigger, data in stats.get("trigger_breakdown", {}).items():
        rate = (data['unresolved'] / data['total'] * 100) if data['total'] > 0 else 0
        lines.append(f"| {trigger} | {data['total']} | {data['finish']} | {data['unresolved']} | {rate:.1f}% |")

    lines += ["", "---", "", "## Metric 3: Worker Opinion Dispersion (Worker間意見分散度)", ""]

    wd = stats.get("worker_dispersion")
    if wd:
        mp = wd["mean_pairwise_distance"]
        cd = wd["centroid_distance_mean"]
        lines += [
            f"Total Turns Measured: {wd['total_turns_measured']}",
            f"",
            f"### Mean Pairwise Distance (B↔C, B↔D, C↔D の平均)",
            f"",
            f"| Statistic | Value |",
            f"|-----------|-------|",
            f"| Mean      | {mp['mean']:.6f} |",
            f"| Std Dev   | {mp['std']:.6f} |",
            f"| Min       | {mp['min']:.6f} |",
            f"| Max       | {mp['max']:.6f} |",
            f"",
            f"### Centroid Distance Mean (重心からの平均距離)",
            f"",
            f"| Statistic | Value |",
            f"|-----------|-------|",
            f"| Mean      | {cd['mean']:.6f} |",
            f"| Std Dev   | {cd['std']:.6f} |",
            f"| Min       | {cd['min']:.6f} |",
            f"| Max       | {cd['max']:.6f} |",
            f"",
        ]
    else:
        lines.append("No worker dispersion data found.")
        lines.append("")

    lines += [
        "---",
        "",
        "## Additional Statistics",
        "",
        f"Mean Turns per Session: {stats['turns']['mean']:.1f}",
        f"Max Turns in a Session: {stats['turns']['max']}",
        f"Total Audit Requests: {stats['audits']['total']}",
        f"Sessions with Audit: {stats['audits']['sessions_with_audit']}",
        "",
    ]

    return "\n".join(lines)


# ==========================================
# ヘルパー関数
# ==========================================
def _mean(values):
    if not values:
        return 0.0
    return sum(values) / len(values)


def _std(values):
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    variance = sum((x - m) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance)


# ==========================================
# CLI
# ==========================================
def main():
    parser = argparse.ArgumentParser(description="Tochikoma Evaluation Report Generator")
    parser.add_argument("--output", "-o", default=None, help="Output Markdown file path")
    parser.add_argument("--json", action="store_true", help="Also output raw statistics as JSON")
    args = parser.parse_args()

    print("📊 Tochikoma Evaluation Report Generator")
    print(f"📁 Data directory: {EVAL_DATA_DIR}")

    sessions = load_all_sessions()
    print(f"📋 Loaded {len(sessions)} session(s)")

    if not sessions:
        print("⚠️ No evaluation data found. Run some conversations first.")
        return

    stats = compute_statistics(sessions)

    # Markdown出力
    report = generate_markdown_report(stats)

    if args.output:
        output_path = args.output
    else:
        os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(DEFAULT_OUTPUT_DIR, f"eval_report_{timestamp}.md")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"✅ Markdown report saved: {output_path}")

    # JSON出力（オプション）
    if args.json:
        json_path = output_path.replace(".md", ".json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        print(f"✅ JSON statistics saved: {json_path}")

    # ターミナルプレビュー
    print("\n" + "=" * 50)
    print(report)


if __name__ == "__main__":
    main()
