"""Run all notebook cells with task logging and one consolidated notification."""
import json
from pathlib import Path
import sys
import nbformat
from nbclient import NotebookClient

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.observability import Observer
from src.observability.runtime import load_env


def execute(observer):
    path=ROOT/'notebooks/member_b_eda.ipynb'
    with observer.task('notebook_execution'):
        nb=nbformat.read(path,as_version=4)
        NotebookClient(nb,timeout=180,kernel_name='tennis-khdl',resources={'metadata':{'path':str(ROOT)}}).execute()
        code=[c for c in nb.cells if c.cell_type=='code']
        errors=[o for c in code for o in c.get('outputs',[]) if o.output_type=='error']
        assert not errors
        assert all(c.execution_count is not None for c in code)
    with observer.task('notebook_publish'):
        pending=path.with_suffix('.ipynb.tmp')
        nbformat.write(nb,pending);pending.replace(path)
        result={'notebook':str(path.relative_to(ROOT)),'code_cells':len(code),'executed_cells':len(code),'errors':len(errors),
            'image_outputs':sum(o.get('output_type')=='display_data' and 'image/png' in o.get('data',{}) for c in code for o in c.get('outputs',[]))}
        (ROOT/'reports/notebook_execution.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    return result


if __name__=='__main__':
    load_env(ROOT/'.env')
    observer=Observer(ROOT,'member_b_notebook')
    try: observer.finish(execute(observer))
    except BaseException as exc:
        observer.finish(error=exc);raise
    finally: observer.close()
