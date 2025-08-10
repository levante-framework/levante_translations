#!/usr/bin/env python3
import argparse
import csv
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd
from tqdm import tqdm


@dataclass
class Inputs:
    src: List[str]
    hyp: List[str]
    ref: Optional[List[str]]
    item_ids: List[str]


def load_csv_rows(csv_path: Path, lang: str) -> Tuple[List[str], List[str], List[str]]:
    df = pd.read_csv(csv_path)
    # Normalize column names
    cols = {c.strip(): c for c in df.columns}
    if 'item_id' not in cols:
        # try other variants
        candidates = [c for c in df.columns if c.lower() in ('id', 'identifier', 'item', 'itemid')]
        if not candidates:
            raise ValueError('CSV must include an item_id-like column')
        df = df.rename(columns={candidates[0]: 'item_id'})
    
    if 'en' not in df.columns:
        raise ValueError('CSV must include source column "en"')
    if lang not in df.columns:
        raise ValueError(f'CSV must include target column "{lang}"')

    item_ids = df['item_id'].astype(str).tolist()
    src = df['en'].astype(str).fillna('').tolist()
    hyp = df[lang].astype(str).fillna('').tolist()
    return item_ids, src, hyp


def write_parallel_texts(out_dir: Path, inputs: Inputs) -> Tuple[Path, Path, Optional[Path]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    src_path = out_dir / 'src.txt'
    hyp_path = out_dir / 'hyp.txt'
    ref_path = out_dir / 'ref.txt' if inputs.ref is not None else None

    src_path.write_text('\n'.join(inputs.src), encoding='utf-8')
    hyp_path.write_text('\n'.join(inputs.hyp), encoding='utf-8')
    if ref_path:
        ref_path.write_text('\n'.join(inputs.ref), encoding='utf-8')
    (out_dir / 'item_ids.txt').write_text('\n'.join(inputs.item_ids), encoding='utf-8')
    return src_path, hyp_path, ref_path


def run_cli(model: str, src: Path, hyp: Path, ref: Optional[Path], out_json: Path, use_gpu: bool):
    cmd = [
        'comet-score', '-s', str(src), '-t', str(hyp), '--model', model, '--to_json', str(out_json)
    ]
    if ref is not None:
        cmd.extend(['-r', str(ref)])
    # Best-effort GPU hint for CLI (may be ignored on older versions)
    if use_gpu:
        cmd.extend(['--gpus', '1'])
    print('Running:', ' '.join(cmd))
    subprocess.check_call(cmd)


def run_api(model: str, inputs: Inputs, out_json: Path, spans: bool, force_gpu: Optional[bool] = None):
    from comet import download_model, load_from_checkpoint
    model_path = download_model(model)
    comet_model = load_from_checkpoint(model_path)

    data = []
    for i in range(len(inputs.src)):
        sample = {
            'src': inputs.src[i],
            'mt': inputs.hyp[i],
        }
        
        if inputs.ref is not None:
            sample['ref'] = inputs.ref[i]
        data.append(sample)

    # Decide on GPU usage
    use_gpu = False
    if force_gpu is not None:
        use_gpu = force_gpu
    else:
        try:
            import torch
            use_gpu = torch.cuda.is_available()
        except Exception:
            use_gpu = False

    # Call predict using Lightning 2 style first, then fall back
    try:
        kwargs = {
            'batch_size': 8,
            'progress_bar': True
        }
        if use_gpu:
            kwargs.update({'accelerator': 'gpu', 'devices': 1})
        else:
            kwargs.update({'accelerator': 'cpu', 'devices': 1})
        predictions = comet_model.predict(data, **kwargs)
    except TypeError:
        # Older signature
        predictions = comet_model.predict(data, batch_size=8, gpus=(1 if use_gpu else 0), progress_bar=True)

    # Normalize output to always include per-segment entries
    system_score = predictions.get('system_score')
    segments_out = predictions.get('segments') or []
    scores_list = predictions.get('scores') or []

    if not segments_out and scores_list:
        # Build segments from our inputs and returned scores (QE case)
        segments_out = []
        n = min(len(scores_list), len(inputs.src), len(inputs.hyp))
        for i in range(n):
            seg = {
                'src': inputs.src[i],
                'mt': inputs.hyp[i],
                'score': scores_list[i]
            }
            if inputs.ref is not None and i < len(inputs.ref):
                seg['ref'] = inputs.ref[i]
            segments_out.append(seg)
        if system_score is None and n > 0:
            system_score = sum(scores_list[:n]) / float(n)

    result = {
        'system_score': system_score,
        'segments': segments_out
    }
    if spans:
        # Some COMET models provide error span metadata under 'metadata'
        # Keep entire object if available
        if 'metadata' in predictions:
            result['metadata'] = predictions.get('metadata')

    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')


def _load_segments(scores_json: Path) -> Tuple[float, List[dict]]:
    """Load segments flexibly from JSON (handles CLI and API formats)."""
    data = json.loads(scores_json.read_text(encoding='utf-8'))
    system_score = None
    segments = []
    if isinstance(data, dict):
        system_score = data.get('system_score')
        segments = data.get('segments') or data.get('scores') or []
    elif isinstance(data, list):
        segments = data
    return system_score, segments


def export_segments_table(item_ids: List[str], scores_json: Path, out_csv: Path, out_md: Path):
    system_score, segments = _load_segments(scores_json)

    rows = []
    for i, seg in enumerate(segments):
        row = {
            'item_id': item_ids[i] if i < len(item_ids) else str(i),
            'source': seg.get('src', ''),
            'translation': seg.get('mt', ''),
            'score': seg.get('score', None)
        }
        # Include ref if available
        if 'ref' in seg:
            row['reference'] = seg.get('ref', '')
        rows.append(row)

    # CSV
    pd.DataFrame(rows).to_csv(out_csv, index=False)

    # Markdown
    headers = ['item_id', 'source', 'translation', 'score'] + ([ 'reference' ] if any('reference' in r for r in rows) else [])
    lines = [
        '| ' + ' | '.join(headers) + ' |',
        '| ' + ' | '.join(['---'] * len(headers)) + ' |'
    ]
    for r in rows:
        lines.append('| ' + ' | '.join(str(r.get(h, '')).replace('\n', ' ').strip() for h in headers) + ' |')
    out_md.write_text('\n'.join(lines), encoding='utf-8')


def generate_report(item_ids: List[str], scores_json: Path, out_md: Path):
    data = json.loads(scores_json.read_text(encoding='utf-8'))
    segments = data.get('segments', [])
    system_score = data.get('system_score')

    # Map item_ids if available
    for i, seg in enumerate(segments):
        if i < len(item_ids):
            seg['item_id'] = item_ids[i]

    # Sort worst first
    worst = sorted(segments, key=lambda s: s.get('score', 0))[:25]

    lines = []
    lines.append(f"# XCOMET Report\n")
    lines.append(f"System score: {system_score}\n")
    lines.append("\n## Worst 25 segments\n")
    for s in worst:
        iid = s.get('item_id', f'idx:{segments.index(s)}')
        score = s.get('score')
        src = s.get('src', '')
        mt = s.get('mt', '')
        ref = s.get('ref', '')
        lines.append(f"- {iid} | score={score}\n  - src: {src}\n  - hyp: {mt}\n  - ref: {ref}\n")

    # Simple histogram bins
    bins = [(-1.0, 0.3), (0.3, 0.6), (0.6, 0.75), (0.75, 1.01)]
    labels = ['<0.3', '0.3-0.6', '0.6-0.75', '>=0.75']
    counts = [0] * len(bins)
    for s in segments:
        sc = s.get('score')
        if sc is None:
            continue
        for bi, (lo, hi) in enumerate(bins):
            if lo <= sc < hi:
                counts[bi] += 1
                break

    lines.append("\n## Score distribution\n")
    total = max(1, len(segments))
    for label, cnt in zip(labels, counts):
        pct = 100.0 * cnt / total
        bar = '█' * int(pct // 2)
        lines.append(f"- {label}: {cnt} ({pct:.1f}%) {bar}")

    out_md.write_text('\n'.join(lines), encoding='utf-8')


def main():
    p = argparse.ArgumentParser(description='Run XCOMET-XL on Levante translations and produce a report.')
    p.add_argument('--csv', type=Path, required=True, help='Path to Levante CSV (e.g., translation_master.csv)')
    p.add_argument('--lang', required=True, help='Target lang code column in CSV (e.g., es-CO)')
    p.add_argument('--out_dir', type=Path, required=True, help='Output directory')
    p.add_argument('--model', default='Unbabel/XCOMET-XL', help='Model name (default: Unbabel/XCOMET-XL)')
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--use_cli', action='store_true', help='Use comet-score CLI')
    g.add_argument('--use_api', action='store_true', help='Use Python API')
    p.add_argument('--spans', action='store_true', help='Export spans (Python API only, if available)')
    p.add_argument('--ref_csv', type=Path, help='Optional CSV providing references (must align with rows and contain <lang> column)')
    p.add_argument('--ref_txt', type=Path, help='Optional ref.txt parallel to src/hyp order')
    p.add_argument('--allow_qe_fallback', action='store_true', help='If no ref, allow fallback to QE model')
    p.add_argument('--gpu', action='store_true', help='Force GPU if available (Python API); CLI path adds --gpus 1')

    args = p.parse_args()

    item_ids, src, hyp = load_csv_rows(args.csv, args.lang)

    ref: Optional[List[str]] = None
    if args.ref_txt and args.ref_txt.exists():
        ref = args.ref_txt.read_text(encoding='utf-8').splitlines()
    elif args.ref_csv and args.ref_csv.exists():
        df_ref = pd.read_csv(args.ref_csv)
        if args.lang not in df_ref.columns:
            raise ValueError(f'Ref CSV missing {args.lang} column')
        ref = df_ref[args.lang].astype(str).fillna('').tolist()

    if ref is None and not args.allow_qe_fallback and args.model == 'Unbabel/XCOMET-XL':
        raise SystemExit('XCOMET-XL is reference-based. Provide --ref_csv/--ref_txt or use --allow_qe_fallback to switch to QE model.')

    model = args.model
    if ref is None and args.allow_qe_fallback:
        # Try gated wmt22 QE first, then public wmt21 QE as a fallback
        qe_candidates = ['Unbabel/wmt22-cometkiwi-da', 'Unbabel/wmt21-comet-qe-da']
        chosen = None
        for cand in qe_candidates:
            try:
                from comet import download_model
                print(f'Trying QE model: {cand}')
                download_model(cand)
                chosen = cand
                break
            except Exception as e:
                print(f'  -> Could not use {cand}: {e}')
                continue
        if not chosen:
            raise SystemExit('No QE model could be downloaded. Accept the model card on HF and `huggingface-cli login`, or provide references for XCOMET-XL.')
        model = chosen
        print(f'No references provided. Falling back to QE model: {model}')

    lang_dir = args.out_dir / args.lang
    lang_dir.mkdir(parents=True, exist_ok=True)

    inputs = Inputs(src=src, hyp=hyp, ref=ref, item_ids=item_ids)
    src_path, hyp_path, ref_path = write_parallel_texts(lang_dir, inputs)

    scores_json = lang_dir / 'scores.json'

    if args.use_cli:
        run_cli(model, src_path, hyp_path, ref_path, scores_json, use_gpu=args.gpu)
    else:
        run_api(model, inputs, scores_json, spans=args.spans, force_gpu=args.gpu)

    report_md = lang_dir / 'report.md'
    generate_report(item_ids, scores_json, report_md)

    # New: export per-segment tables (CSV and Markdown)
    table_csv = lang_dir / 'segment_scores.csv'
    table_md = lang_dir / 'segment_scores.md'
    export_segments_table(item_ids, scores_json, table_csv, table_md)

    print(f'Wrote: {scores_json}')
    print(f'Wrote: {report_md}')
    print(f'Wrote: {table_csv}')
    print(f'Wrote: {table_md}')


if __name__ == '__main__':
    main()
