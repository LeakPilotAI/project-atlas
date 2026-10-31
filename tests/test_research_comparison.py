import json
from pathlib import Path

import pytest
from test_research_replay_export import run, setup

from scripts.observation_runtime import research_comparison as comparison
from scripts.observation_runtime.research_replay import encoded


def pair(tmp_path,change=None):
    roots=[];results=[]
    for side in ('left','right'):
        root=tmp_path/side;root.mkdir();request,out=setup(root)
        if side=='right' and change:
            change(root,request)
        roots.append(out);results.append(run(root,out))
    return {side+'_'+field:value for side,root,result in zip(('left','right'),roots,results,strict=True)
            for field,value in [('root',root),('manifest',result['manifest']),('pin',result['manifest'][:-5])]}


def repin(root,request,key,value):
    import hashlib
    raw=encoded(value);(root/(key+'.json')).write_bytes(raw)
    request['expected_'+key+'_sha256']=hashlib.sha256(raw).hexdigest()
    (root/'request.json').write_bytes(encoded(request))


def test_same_replays_keep_refused_denominator_and_null_metrics(tmp_path):
    report=comparison.compare_exports(**pair(tmp_path))
    assert report['planned_pair_n']==3 and report['both_descriptive_n']==1
    assert report['same_evidence_n']==3 and report['not_both_descriptive_n']==2
    assert report['status_pair_counts']['REFUSED']['REFUSED']==2
    assert report['pairs'][0]['metrics']['observed_change_percent']['right_minus_left'] is None
    assert report['pairs'][1]['metrics']['observed_change_percent']['right_minus_left']==0
    assert report['pairs'][1]['metrics']['relative_volume']['availability']=='BOTH_OBSERVED'
    assert report['predictive_skill_established'] is False and report['trading_authorized'] is False


def test_missing_reference_does_not_drop_pairs(tmp_path):
    def change(root,request):repin(root,request,'references',[])
    report=comparison.compare_exports(**pair(tmp_path,change))
    assert report['planned_pair_n']==3 and report['both_descriptive_n']==0
    assert report['status_pair_counts']['DESCRIPTIVE_RESEARCH_ONLY']['INSUFFICIENT_REFERENCE']==1
    assert all(not row['same_evidence'] for row in report['pairs'])


def test_changed_available_reference_is_descriptive_not_skill(tmp_path):
    def change(root,request):
        refs=json.loads((root/'references.json').read_bytes());refs[0]['previous_close']=80
        repin(root,request,'references',refs)
    report=comparison.compare_exports(**pair(tmp_path,change))
    assert report['planned_pair_n']==3 and report['both_descriptive_n']==1
    row=report['pairs'][1]
    assert not row['same_evidence']
    assert row['metrics']['observed_change_percent']['right_minus_left']!=0


def test_missing_baseline_stays_unknown_instead_of_zero_difference(tmp_path):
    def change(root,request):
        archive=json.loads((root/'archive.json').read_bytes())
        archive['rows']=[row for row in archive['rows'] if row['timestamp'].startswith('2026-10-20')]
        repin(root,request,'archive',archive)
    report=comparison.compare_exports(**pair(tmp_path,change))
    metric=report['pairs'][1]['metrics']['relative_volume']
    assert metric['availability']=='LEFT_ONLY' and metric['right'] is None
    assert metric['right_minus_left'] is None
    fixture=Path(__file__).parent/'fixtures/market-replay-v1/research-comparison.json'
    assert comparison.browser_comparison(report).encode()==fixture.read_bytes()


@pytest.mark.parametrize('fault',['clock','wrong_pin','missing_source','corrupt_report'])
def test_unaligned_or_unverified_sources_are_refused(tmp_path,fault):
    def change(root,request):
        request['decisions']=request['decisions'][1:];(root/'request.json').write_bytes(encoded(request))
    args=pair(tmp_path,change if fault=='clock' else None)
    if fault=='wrong_pin':args['right_pin']='0'*64
    if fault in ('missing_source','corrupt_report'):
        manifest=json.loads((args['right_root']/args['right_manifest']).read_bytes())
        target=args['right_root']/(manifest['archive_chunks'][0]['artifact'] if fault=='missing_source' else manifest['report'])
        target.write_bytes(b'{}')
    with pytest.raises(ValueError):comparison.compare_exports(**args)


def test_cli_publishes_idempotent_artifacts_without_changing_sources(tmp_path,capsys):
    args=pair(tmp_path);before={p:p.read_bytes() for root in (args['left_root'],args['right_root']) for p in root.iterdir()}
    output=tmp_path/'comparison';output.mkdir()
    argv=[item for key,value in args.items() for item in ('--'+key.replace('_','-'),str(value))]+['--output-root',str(output)]
    assert comparison.main(argv)==0
    result=json.loads(capsys.readouterr().out)
    raw=(output/result['report']).read_bytes();html=(output/result['dashboard']).read_text()
    assert json.loads(raw)['planned_pair_n']==3 and 'Refusals are not dropped' in html
    assert comparison.main(argv)==0 and (output/result['report']).read_bytes()==raw
    assert before=={p:p.read_bytes() for root in (args['left_root'],args['right_root']) for p in root.iterdir()}


def test_partial_publication_preserves_evidence_without_success(tmp_path,monkeypatch,capsys):
    args=pair(tmp_path);output=tmp_path/'comparison';output.mkdir();original=comparison.publish_research_text
    def fail_second(root,text,extension):
        if extension=='.html':raise OSError('synthetic full disk')
        return original(root,text,extension=extension)
    monkeypatch.setattr(comparison,'publish_research_text',fail_second)
    argv=[item for key,value in args.items() for item in ('--'+key.replace('_','-'),str(value))]+['--output-root',str(output)]
    assert comparison.main(argv)==2 and json.loads(capsys.readouterr().out)['status']=='REFUSED'
    assert len(list(output.iterdir()))==1
