"""Explicit byte-level source archives for offline AFI reproducibility.

This verifies supplied source consistency, not signatures, provider rights,
executed-memory attestation or protection against privileged replacement.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.backtest.forecast_dataset import _fields, _hash, _json
from app.backtest.forecast_evaluation import ForecastEvidenceRefused, _identity

REQUIRED_FILES = frozenset({
    'app/backtest/forecast_source.py', 'app/backtest/forecast_baselines.py',
    'app/backtest/forecast_dataset.py', 'app/backtest/forecast_evaluation.py',
    'app/backtest/forecast_replay.py', 'app/backtest/forecast_uncertainty.py',
    'app/backtest/forecast_artifacts.py', 'app/backtest/forecast_comparison.py',
    'app/backtest/forecast_dashboard.py', 'app/backtest/forecast_cli.py',
    'app/investment/market_hours.py', 'app/core/durable_io.py',
})
OPTIONAL_FILES = frozenset({'app/backtest/forecast_outcomes.py', 'app/backtest/forecast_report.py'})


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


@dataclass(frozen=True)
class SourceReview:
    manifest_bytes: bytes
    source_files: tuple[tuple[str, bytes], ...]
    release_sha256: str
    externally_authenticated: bool = False
    running_memory_attested: bool = False
    production_approved: bool = False


def review_source(manifest_bytes, source_files):
    """Validate exactly enumerated source bytes; refuse substitutions and omissions."""
    manifest = _json(manifest_bytes)
    _fields(manifest, 'schema release_id scope files')
    if manifest['schema'] != 'AFI_RELEASE_SOURCE_V1' or manifest['scope'] != 'OFFLINE_SYNTHETIC_ONLY':
        raise ForecastEvidenceRefused('Unsupported source release scope')
    _identity(manifest['release_id'])
    if type(source_files) is not dict or not REQUIRED_FILES <= set(source_files) <= REQUIRED_FILES | OPTIONAL_FILES:
        raise ForecastEvidenceRefused('Exact reviewed source graph required')
    if type(manifest['files']) is not list or not len(REQUIRED_FILES) <= len(manifest['files']) <= 14:
        raise ForecastEvidenceRefused('Bounded source manifest required')
    rows, total = {}, 0
    for row in manifest['files']:
        _fields(row, 'path sha256 bytes')
        name = row['path']
        if type(name) is not str or name not in source_files or name in rows:
            raise ForecastEvidenceRefused('Unknown or repeated release source path')
        raw = source_files[name]
        if type(raw) is not bytes or not 1 <= len(raw) <= 1_000_000:
            raise ForecastEvidenceRefused('Bounded source bytes required')
        _hash(row['sha256'])
        if type(row['bytes']) is not int or row['bytes'] != len(raw) or hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ForecastEvidenceRefused('Release source hash/length mismatch')
        rows[name] = raw
        total += len(raw)
    if set(rows) != set(source_files) or total > 10_000_000:
        raise ForecastEvidenceRefused('Incomplete or oversized source archive')
    if manifest_bytes != _canonical(manifest):
        raise ForecastEvidenceRefused('Canonical source manifest bytes required')
    return SourceReview(manifest_bytes, tuple(sorted(rows.items())), hashlib.sha256(manifest_bytes).hexdigest())


def create_source_review(source_files, *, release_id):
    if type(source_files) is not dict or any(type(k) is not str or type(v) is not bytes for k,v in source_files.items()):
        raise ForecastEvidenceRefused('Exact source byte mapping required')
    manifest = {'schema':'AFI_RELEASE_SOURCE_V1', 'release_id':release_id, 'scope':'OFFLINE_SYNTHETIC_ONLY',
                'files':[{'path':k,'sha256':hashlib.sha256(v).hexdigest(),'bytes':len(v)} for k,v in sorted(source_files.items())]}
    return review_source(_canonical(manifest), source_files)


def validate_source(review):
    if type(review) is not SourceReview:
        raise ForecastEvidenceRefused('Exact source review required')
    if review != review_source(review.manifest_bytes, dict(review.source_files)):
        raise ForecastEvidenceRefused('Substituted release-source review')
    return review.release_sha256


def source_archive_bytes(review):
    validate_source(review)
    result={'schema':'AFI_SOURCE_ARCHIVE_V1','manifest_json':review.manifest_bytes.decode('utf-8'),
            'files':[{'path':name,'source_utf8':raw.decode('utf-8')} for name,raw in review.source_files]}
    raw=_canonical(result)
    if len(raw)>2_000_000:
        raise ForecastEvidenceRefused('Source archive exceeds publication limit')
    return raw


def review_source_archive(raw):
    data=_json(raw);_fields(data,'schema manifest_json files')
    if data['schema']!='AFI_SOURCE_ARCHIVE_V1' or type(data['manifest_json']) is not str or type(data['files']) is not list or len(data['files'])>14:
        raise ForecastEvidenceRefused('Malformed source archive')
    files={}
    for row in data['files']:
        _fields(row,'path source_utf8')
        if type(row['path']) is not str or row['path'] in files or type(row['source_utf8']) is not str:
            raise ForecastEvidenceRefused('Duplicate or malformed source archive entry')
        files[row['path']]=row['source_utf8'].encode('utf-8')
    review=review_source(data['manifest_json'].encode('utf-8'),files)
    if source_archive_bytes(review)!=raw:
        raise ForecastEvidenceRefused('Noncanonical source archive')
    return review


def package_source(source_root,output_root,*,release_id,include=()):
    """Capture only explicit approved code paths; never import/execute the archive."""
    from pathlib import Path

    from app.backtest.forecast_artifacts import publish_research_text
    root=Path(source_root).absolute()
    if not root.is_dir() or any(p.is_symlink() or p.is_junction() for p in (root,*root.parents)):
        raise ForecastEvidenceRefused('Existing unlinked source root required')
    if not isinstance(include,(list,tuple)) or any(p not in OPTIONAL_FILES for p in include) or len(set(include))!=len(include):
        raise ForecastEvidenceRefused('Explicit approved optional source paths required')
    files={};total=0
    for name in sorted(REQUIRED_FILES | set(include)):
        path=root/name
        if any(p.is_symlink() or p.is_junction() for p in (path,*path.parents)) or not path.is_file():
            raise ForecastEvidenceRefused('Source capture path missing or linked')
        with path.open('rb') as handle:raw=handle.read(1_000_001)
        total+=len(raw)
        if len(raw)>1_000_000 or total>10_000_000:
            raise ForecastEvidenceRefused('Source capture budget exhausted')
        files[name]=raw
    review=create_source_review(files,release_id=release_id)
    archive=source_archive_bytes(review)
    manifest_path=publish_research_text(output_root,review.manifest_bytes.decode('utf-8'),extension='.json')
    archive_path=publish_research_text(output_root,archive.decode('utf-8'),extension='.json')
    if manifest_path.read_bytes()!=review.manifest_bytes or archive_path.read_bytes()!=archive:
        raise ForecastEvidenceRefused('Source package read-back failed')
    return {'status':'OFFLINE_SOURCE_ARCHIVE_COMPLETE','manifest':manifest_path.name,'archive':archive_path.name,
            'release_source_sha256':review.release_sha256,'externally_authenticated':False,'running_memory_attested':False,
            'production_approved':False}


def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser(description='Capture explicit offline source bytes; never executes or deploys an archive')
    parser.add_argument('--source-root',required=True);parser.add_argument('--output-root',required=True);parser.add_argument('--release-id',required=True)
    parser.add_argument('--include',action='append',default=[],choices=sorted(OPTIONAL_FILES))
    args=parser.parse_args(argv)
    try:result=package_source(args.source_root,args.output_root,release_id=args.release_id,include=args.include)
    except (ValueError,OSError,UnicodeError) as error:
        print(json.dumps({'status':'REFUSED','error_type':type(error).__name__,'production_approved':False}));return 2
    print(json.dumps(result,sort_keys=True));return 0


if __name__=='__main__':
    raise SystemExit(main())
