"""Verify source/output bytes and reproduce all pipeline artifacts offline."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import os

ROOT=Path(__file__).resolve().parents[1]


def verify():
    manifest=json.loads((ROOT/'reports/run_manifest.json').read_text())
    for relative, expected in manifest['outputs_sha256'].items():
        actual=hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()
        assert actual==expected, f'Changed output: {relative}'
    for relative, expected in manifest['input_sha256'].items():
        assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==expected, relative
    for relative, expected in manifest['source_code_sha256'].items():
        assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==expected, f'Changed code: {relative}; rerun pipeline'
    with tempfile.TemporaryDirectory(prefix='tennis-repro-') as temp:
        child_env={**os.environ,'PIPELINE_ALERTS_DRY_RUN':'1','PIPELINE_PARENT_RUN_ID':os.environ.get('PIPELINE_OPERATION_ID','')}
        proc=subprocess.run([sys.executable,str(ROOT/'scripts/run_pipeline.py'),'--offline','--output-dir',temp],cwd=ROOT,capture_output=True,text=True,env=child_env)
        if proc.returncode:
            raise RuntimeError(proc.stdout+'\n'+proc.stderr)
        other=json.loads((Path(temp)/'reports/run_manifest.json').read_text())
        mismatches=[k for k,v in manifest['outputs_sha256'].items() if other['outputs_sha256'].get(k)!=v]
        assert not mismatches, f'Non-reproducible outputs: {mismatches}'
        assert manifest['source_code_sha256']==other['source_code_sha256']
    result={'offline_reproduction':True,'matched_artifacts':len(manifest['outputs_sha256']),
            'raw_files_verified':len(manifest['input_sha256']),'mismatches':0,
            'method':'Fresh output directory, same pinned cached source and code, byte-for-byte SHA256 comparison'}
    (ROOT/'reports/reproducibility.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    sys.path.insert(0,str(ROOT))
    from src.observability import Observer
    from src.observability.runtime import load_env
    load_env(ROOT/'.env')
    observer=Observer(ROOT,'reproducibility')
    os.environ['PIPELINE_OPERATION_ID']=observer.id
    try:
        with observer.task('verify_checksums_and_rebuild'): verify()
        observer.finish({'verification':'passed'})
    except BaseException as exc:
        observer.finish(error=exc);raise
    finally: observer.close()
