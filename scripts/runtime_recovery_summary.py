"""Summarize local sampler output without touching Atlas data."""
import json
from pathlib import Path
import statistics
import sys


def summarize(path):
    rows = [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]
    requests = [r for row in rows for r in row['requests']]
    processes = [row['process'] for row in rows if 'process' in row]
    diagnostics = [row['diagnostics'] for row in rows if row.get('diagnostics')]
    metrics = [row['runtime_metrics'] for row in diagnostics]
    def distribution(values):
        ordered = sorted(values)
        return {'n': len(ordered), 'min': min(ordered), 'p50': statistics.median(ordered),
                'p95': ordered[min(len(ordered)-1, int(.95*len(ordered)))], 'max': max(ordered)} if ordered else {}
    memory = [p['private_mb'] for p in processes]
    threads = [p['threads'] for p in processes]
    summary = {
        'sampled_seconds': rows[-1]['elapsed_sec'], 'samples': len(rows),
        'http_failures': [r for r in requests if not r['ok']],
        'process_errors': [row.get('process_error') for row in rows if row.get('process_error')],
        'health_ms': distribution([r['ms'] for r in requests if r['path']=='/health' and r['ok']]),
        'endpoints_ms': {path: distribution([r['ms'] for r in requests if r['path']==path and r['ok']])
                         for path in sorted({r['path'] for r in requests})},
        'private_mb': {'start': memory[0], 'peak': max(memory), 'end': memory[-1]},
        'rss_mb': {'start': processes[0]['rss_mb'], 'peak': max(p['rss_mb'] for p in processes), 'end': processes[-1]['rss_mb']},
        'threads': {'start': threads[0], 'peak': max(threads), 'end': threads[-1]},
        'child_process_peak': max(p['child_processes'] for p in processes),
        'cpu_one_core_pct': distribution([row['cpu_one_core_pct'] for row in rows[1:] if 'cpu_one_core_pct' in row]),
        'cpu_one_core_average_pct': round(100*(processes[-1]['cpu_seconds']-processes[0]['cpu_seconds'])/max(1,rows[-1]['elapsed_sec']),2),
        'watchdog_stall_samples': max(m['stall_samples'] for m in metrics) if metrics else None,
        'max_heartbeat_age_ms': max(m['max_heartbeat_age_ms'] for m in metrics) if metrics else None,
        'tasks': {'start': metrics[0]['tasks'], 'peak': max(m['tasks'] for m in metrics), 'end': metrics[-1]['tasks']} if metrics else {},
        'executor_pending_peak': max(m['executor_pending'] for m in metrics) if metrics else None,
        'latest_read_models': diagnostics[-1].get('read_models') if diagnostics else {},
        'latest_indexes': diagnostics[-1].get('bounded_indexes') if diagnostics else {},
        'latest_paper': next((row['paper'] for row in reversed(rows) if row.get('paper')), {}),
        'scanner_timestamps': sorted({row['surface']['health'].get('last_cycle_at') for row in rows
                                      if row.get('surface', {}).get('health') and row['surface']['health'].get('last_cycle_at')}),
        'five_minute_windows': []}
    for start in range(0, int(rows[-1]['elapsed_sec'])+1, 300):
        batch = [row for row in rows if start <= row['elapsed_sec'] < start+300 and 'process' in row]
        if batch:
            summary['five_minute_windows'].append({'start_minute':start//60,'samples':len(batch),
                'private_mb_min':min(x['process']['private_mb'] for x in batch),
                'private_mb_max':max(x['process']['private_mb'] for x in batch),
                'private_mb_end':batch[-1]['process']['private_mb'],
                'cpu_mean_pct':round(statistics.mean(x['cpu_one_core_pct'] for x in batch),2),
                'threads_end':batch[-1]['process']['threads']})
    return summary


if __name__ == '__main__':
    print(json.dumps(summarize(sys.argv[1]), indent=2))
