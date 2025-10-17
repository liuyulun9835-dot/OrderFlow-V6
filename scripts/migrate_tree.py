from __future__ import annotations
import os, re, csv, json, shutil, argparse, pathlib

ROOT = pathlib.Path('.')
MIG_DIR = ROOT / 'docs/migrations'
MIG_DIR.mkdir(parents=True, exist_ok=True)

# -------- Mapping rules (old card id → new layer/prefix) --------
def map_card(old_id: int) -> tuple[str, str]:
    # return (layer, new_prefix)
    if 0 <= old_id <= 49:
        return ('K', 'K')
    if 100 <= old_id <= 199:
        return ('D', 'D')
    if 200 <= old_id <= 399:
        return ('M', 'M')
    if 500 <= old_id <= 649:
        return ('J', 'J')
    if 650 <= old_id <= 749:
        return ('E', 'E')
    if 400 <= old_id <= 499 or 750 <= old_id <= 799 or 800 <= old_id <= 829 or 860 <= old_id <= 899:
        return ('QA', 'QA')
    return ('UNK', 'UNK')

# Optional: seed explicit examples (可补充你在迁移清单中列的样例)
SEED: dict[int, tuple[str, str, str]] = {
    0: ('K', 'K001', '仓库初始化与README Quickstart'),
    1: ('K', 'K002', '目录与命名规范'),
    2: ('K', 'K010', 'SCHEMA/Manifest 契约与签名'),
    101: ('D', 'D101', 'ATAS 指标导出 DLL'),
    102: ('D', 'D102', 'ATAS 回放配置与导出流水'),
    107: ('D', 'D107', 'ATAS Bar 连续性/缺口自检'),
    108: ('D', 'D108', 'ATAS Tick 质量评估'),
    109: ('D', 'D109', '分层分区 raw→staged→processed'),
    110: ('D', 'D110', 'manifest & watermark'),
    111: ('D', 'D111', 'ATAS Bar 聚合'),
    112: ('D', 'D112', 'ATAS 真 Tick 连续抓取'),
    113: ('D', 'D113', 'Binance OHLCV + aggTrades'),
    115: ('D', 'D115', '对齐索引 alignment_index'),
    116: ('D', 'D116', 'minute↔tick 映射与分布校准'),
    117: ('M', 'M117', '状态置信度/驻留分布校准'),
    118: ('E', 'E118', '成本鲁棒与成交可达性预检'),
    205: ('M', 'M205', 'MSI/MFI/KLI 指标族与签名'),
    305: ('M', 'M305', 'HMM/TVTP 训练与推断'),
    505: ('J', 'J505', '规则互斥/一致性测试'),
    601: ('J', 'J601', '解析/评分/冲突/决策日志'),
    607: ('E', 'E607', 'AB 双源热切换与回滚'),
    701: ('E', 'E701', '下单/会话恢复/风控'),
    751: ('QA', 'QA751', '回测与 Paper 交易'),
    801: ('QA', 'QA801', '观测面板 / 数据质量日报'),
    861: ('QA', 'QA861', 'README/ARCHITECTURE/VALIDATION'),
}


def allocate_new_id(old_id: int, counters: dict[str, int]) -> tuple[str, str]:
    if old_id in SEED:
        return SEED[old_id][0], SEED[old_id][1]
    layer, prefix = map_card(old_id)
    key = f'{prefix}'
    counters.setdefault(key, 0)
    counters[key] += 1
    if prefix == 'QA':
        return layer, f'QA{old_id}'  # QA 段保持原号，便于审计
    if prefix == 'UNK':
        return layer, f'UNK{old_id}'
    return layer, f'{prefix}{counters[key]:03d}'


def discover_old_cards(todo_path: pathlib.Path) -> list[int]:
    ids: set[int] = set()
    if todo_path.exists():
        for line in todo_path.read_text(encoding='utf-8', errors='ignore').splitlines():
            m = re.search(r'(^|\D)(\d{3})(\D|$)', line)
            if m:
                ids.add(int(m.group(2)))
    # 基础兜底：覆盖 000-899 范围里常用段位
    for r in [(0, 49), (100, 199), (200, 399), (400, 499), (500, 649), (650, 749), (750, 799), (800, 829), (860, 899)]:
        for i in range(r[0], r[1] + 1):
            ids.add(i)
    return sorted(ids)


def write_mapping(out_csv: pathlib.Path, ids: list[int]):
    counters: dict[str, int] = {}
    rows: list[dict[str, str | int]] = []
    for oid in ids:
        layer, nid = allocate_new_id(oid, counters)
        title = SEED.get(oid, (None, None, f'迁移自旧卡片 {oid}'))[2]
        rows.append({'old_id': oid, 'new_layer': layer, 'new_id': nid, 'title': title})
    with out_csv.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['old_id', 'new_layer', 'new_id', 'title'])
        w.writeheader()
        w.writerows(rows)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--todo', default='order_flow_v_6_todo.md')
    args = ap.parse_args()

    ids = discover_old_cards(ROOT / args.todo)
    rows = write_mapping(MIG_DIR / 'card_mapping.csv', ids)

    # 文件移动规划（模式化，根据常见目录命名推断；只写 CSV 供人工确认）
    moves: list[dict[str, str]] = []
    guess = [
        ('preprocessing', 'data'),
        ('atas', 'data/atas_integration'),
        ('atas_integration', 'data/atas_integration'),
        ('binance', 'data'),
        ('features', 'data'),
        ('models', 'model'),
        ('orderflow_v6/factors', 'model/factors'),
        ('strategy_core', 'decision'),
        ('rules', 'decision'),
        ('execution', 'execution'),
        ('router', 'execution'),
        ('validation', 'QA_validation'),
        ('results', 'REPORT_results'),
        ('docs', 'docs'),
    ]
    for src, dst in guess:
        if (ROOT / src).exists():
            moves.append({'src': src, 'dst': dst})
    with (MIG_DIR / 'file_moves.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['src', 'dst'])
        w.writeheader()
        w.writerows(moves)

    if args.dry_run:
        print('Dry-run complete: wrote mapping and planned moves.')
        return

    # 真正移动：仅移动存在的目录；创建目标
    for m in moves:
        s = ROOT / m['src']
        d = ROOT / m['dst']
        d.mkdir(parents=True, exist_ok=True)
        if s.resolve() == d.resolve():
            # 跳过同路径移动，保留审计记录即可
            continue
        if s.exists():
            # 按目录整体搬运
            for p in s.iterdir():
                target = d / p.name
                if p.name == '.gitkeep' and target.exists():
                    continue
                if target.exists():
                    # 保留已存在内容，跳过冲突项
                    continue
                shutil.move(str(p), str(d))
            # 保留原空目录避免破坏相对路径的脚本（视情况删除）
            try:
                s.rmdir()
            except Exception:
                pass

    print('Migration done.')


if __name__ == '__main__':
    main()
