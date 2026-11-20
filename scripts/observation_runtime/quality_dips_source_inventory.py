"""Read-only inventory of existing QD native source custody, not source authority."""
from pathlib import Path

ROOT = Path('D:/AtlasCustody/QualityDips')

def inspect(*, root=ROOT):
    parent = Path(root)
    ordinary = lambda p: p.is_dir() and not p.is_symlink() and not p.is_junction()
    if not ordinary(parent):
        return {'schema':'ATLAS_QD_NATIVE_SOURCE_INVENTORY_V1',
                'source_parent_present':False,'ordinary_child_count':0,
                'children_with_direct_files':0,'ordinary_direct_file_count':0,
                'operational_publication_verified':False,
                'reason':'QD_SOURCE_CUSTODY_PARENT_UNAVAILABLE'}
    children = [p for p in parent.iterdir() if ordinary(p)]
    direct_files = sum(1 for p in parent.iterdir() if p.is_file() and not p.is_symlink())
    populated = sum(1 for child in children if any(p.is_file() and not p.is_symlink()
                   and not p.is_junction() for p in child.iterdir()))
    return {'schema':'ATLAS_QD_NATIVE_SOURCE_INVENTORY_V1',
            'source_parent_present':True,'ordinary_child_count':len(children),
            'children_with_direct_files':populated,'ordinary_direct_file_count':direct_files,
            'operational_publication_verified':False,
            'reason':'INDEPENDENT_ENROLLED_SCANNER_PUBLICATION_REQUIRED'}
