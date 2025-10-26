# [MIGRATED_FROM_V6] 2025-10-26: 原路径 scripts/reclassify_cards.py；本文件在 V7 中保持向后兼容
from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

ORDER = [
    "Data",
    "Model",
    "Decision",
    "Execution",
    "Validation",
    "Risk",
    "Backtest",
    "Monitoring",
    "Ops",
    "Docs",
    "Milestone",
]

# Regex patterns that map to a target layer. Evaluation order matters.
LAYER_RULES: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(p, re.I), layer)
    for p, layer in [
        (r"(数据|atas|manifest|preprocess|raw|alignment|features|calibration|watermark)", "Data"),
        (r"(指标|因子|hmm|tvtp|hsmm|模型|state|regime)", "Model"),
        (r"(决策|decision|scoring|规则|structureddecisiontree)", "Decision"),
        (r"(执行|execution|撮合|routing|router|下单|成交)", "Execution"),
        (r"(验证|validator|qc|precheck|显著|统计|验收)", "Validation"),
        (r"(风控|风险|risk|熔断|cooldown)", "Risk"),
        (r"(回测|backtest|模拟盘|paper)", "Backtest"),
        (r"(监控|告警|dashboard|健康度|monitor)", "Monitoring"),
        (r"(运维|工程基线|部署|docker|ci|环境|poetry)", "Ops"),
        (r"(文档|审计|readme|治理|governance|migrations)", "Docs"),
        (r"(里程碑|milestone|验收)", "Milestone"),
    ]
]

MODULE_MAP: Dict[str, str] = {
    "数据": "Data",
    "数据合并": "Data",
    "数据校准": "Data",
    "校准": "Data",
    "映射/校准": "Data",
    "指标": "Model",
    "指标研发": "Model",
    "状态建模": "Model",
    "模型": "Model",
    "Validator": "Validation",
    "验证": "Validation",
    "可执行性预检": "Validation",
    "规则": "Decision",
    "规则库": "Decision",
    "决策": "Decision",
    "执行": "Execution",
    "风控": "Risk",
    "风险管理": "Risk",
    "回测": "Backtest",
    "监控": "Monitoring",
    "部署与运维": "Ops",
    "工程基线": "Ops",
    "运维": "Ops",
    "文档与审计": "Docs",
    "文档": "Docs",
    "里程碑": "Milestone",
}

PATH_REPLACEMENTS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"strategy_core/decision_tree/"), "decision/engine/"),
    (re.compile(r"strategy_core/state_inference"), "model/hmm_tvpt_hsmm/state_inference"),
    (re.compile(r"strategy_core/scoring"), "decision/scoring"),
    (re.compile(r"(?<!model/)models/"), "model/artifacts/"),
    (re.compile(r"(?<!output/)results/"), "output/results/"),
    (re.compile(r"(?<!output/)qa/"), "output/qa/"),
    (re.compile(r"output/results/output"), "output/results"),
    (re.compile(r"data/\{raw,staged,processed\}"), "data/{raw,preprocessing,processed}"),
]

CARD_PATTERN = re.compile(
    r"(^### 卡片\s+(?P<cid>\d{3})[\s\S]*?)(?=\n### 卡片\s+\d{3}|\Z)",
    re.M,
)
MODULE_PATTERN = re.compile(r"(- \*\*模块\*\*：)(?P<value>.+)")


def extract_blocks(text: str) -> List[Tuple[int, str]]:
    blocks: List[Tuple[int, str]] = []
    for match in CARD_PATTERN.finditer(text):
        cid = int(match.group("cid"))
        block = match.group(0)
        blocks.append((cid, block))
    return blocks


def detect_layer(block: str, cid: int) -> str:
    if cid >= 900:
        return "Milestone"
    module_match = MODULE_PATTERN.search(block)
    if module_match:
        module_value = module_match.group("value").strip()
        for key, layer in MODULE_MAP.items():
            if key.lower() in module_value.lower():
                return layer
    lower = block.lower()
    for pattern, layer in LAYER_RULES:
        if pattern.search(lower):
            return layer
    return "Docs"


def standardise_module(block: str, layer: str) -> str:
    if "模块" not in block:
        return block

    def repl(match: re.Match[str]) -> str:
        return f"{match.group(1)}{layer}"

    return MODULE_PATTERN.sub(repl, block, count=1)


def rewrite_paths(block: str) -> str:
    updated = block
    for pattern, replacement in PATH_REPLACEMENTS:
        updated = pattern.sub(replacement, updated)
    return updated


def clean_block(block: str) -> str:
    lines = block.splitlines()
    cleaned: List[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped == "---":
            continue
        if re.match(r"^##\s+\d{3}", stripped):
            continue
        cleaned.append(line)
    while cleaned and cleaned[-1].strip() == "":
        cleaned.pop()
    if not cleaned:
        return ""
    return "\n".join(cleaned) + "\n"


def rebuild_document(original: str, items: Iterable[Tuple[str, int, str]]) -> str:
    if "\n---\n" in original:
        head, _tail = original.split("\n---\n", 1)
    else:
        head, _tail = original, ""
    by_layer: Dict[str, List[str]] = defaultdict(list)
    for layer, _cid, block in items:
        if block:
            by_layer[layer].append(block)

    parts: List[str] = [head.strip(), "---", "## 分层索引"]
    for layer in ORDER:
        blocks = by_layer.get(layer, [])
        if not blocks:
            continue
        ids = [re.search(r"### 卡片\s+(\d{3})", b).group(1) for b in blocks]
        parts.append(f"- **{layer}**：{', '.join(ids)}")

    for layer in ORDER:
        blocks = by_layer.get(layer, [])
        if not blocks:
            continue
        parts.append("")
        parts.append(f"## {layer}")
        parts.extend(blocks)
    return "\n\n".join(parts).strip() + "\n"


def write_mapping(mapping_path: Path, entries: List[Tuple[int, str, int]]) -> None:
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    with mapping_path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerow(["old_card", "layer", "new_order"])
        for cid, layer, new_order in entries:
            writer.writerow([f"{cid:03d}", layer, new_order])


def main(card_path: Path) -> None:
    text = card_path.read_text(encoding="utf-8")
    blocks = extract_blocks(text)
    if not blocks:
        raise SystemExit("No card blocks found")

    processed: List[Tuple[str, int, str]] = []
    for cid, block in blocks:
        layer = detect_layer(block, cid)
        updated_block = standardise_module(block, layer)
        updated_block = rewrite_paths(updated_block)
        updated_block = clean_block(updated_block)
        processed.append((layer, cid, updated_block))

    processed.sort(key=lambda item: (ORDER.index(item[0]) if item[0] in ORDER else len(ORDER), item[1]))

    mapping_entries: List[Tuple[int, str, int]] = []
    for index, (layer, cid, block) in enumerate(processed, start=1):
        if not block:
            continue
        mapping_entries.append((cid, layer, index))

    new_text = rebuild_document(text, processed)
    card_path.write_text(new_text, encoding="utf-8")

    mapping_path = Path("docs/migrations/card_mapping.csv")
    write_mapping(mapping_path, mapping_entries)

    print(f"Updated {card_path}")
    print(f"Wrote mapping to {mapping_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/reclassify_cards.py <card_file>")
    main(Path(sys.argv[1]))
