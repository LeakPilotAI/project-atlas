"""Existing-only local operator approval record. No writer or default enrollment."""
import importlib.util
import ntpath
from pathlib import Path

from app.services.paper_financial_replay import strict


class NativePersonalActivationReader:
    def __init__(self,*,root=None,native_root=None,binding=None):
        if (type(root) is not str or not ntpath.normcase(root).startswith('d:\\atlascustody\\personalpaper\\')
                or any(c in root[3:] for c in (':','%','\x00','/')) or ntpath.normpath(root)!=root or any(x in ('','..','.') for x in root[3:].split('\\'))
                or type(native_root) is not list or len(native_root)!=3
                or any(type(v) is not int or v<0 for v in native_root)
                or type(binding) is not dict or set(binding)!={'id','sha256'}
                or type(binding['id']) is not list or len(binding['id'])!=3
                or any(type(v) is not int or v<0 for v in binding['id'])
                or type(binding['sha256']) is not str or len(binding['sha256'])!=64
                or any(c not in '0123456789abcdef' for c in binding['sha256'])):
            raise ValueError('PERSONAL_INSTALLED_NATIVE_APPROVAL_REQUIRED')
        self.root,self.native_root,self.binding=root,list(native_root),{'id':list(binding['id']),'sha256':binding['sha256']}
    def read(self):
        # Import opens no resource. Actual root access is existing-only and bound.
        spec=importlib.util.spec_from_file_location('personal_approval_bound',Path(__file__).parents[1]/'volume_inspector/snapshot_store.py')
        native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
        with native.w.WindowsOutput(self.root) as out:
            if native.native.file_identity(out.root_handle)!=self.native_root:raise ValueError('PERSONAL_APPROVAL_ROOT_SUBSTITUTION')
            value=strict(native.read_bound(out,'activation.json',self.binding)[0].decode())
        if value.get('schema')!='ATLAS_PERSONAL_ACTIVATION_V1' or value.get('origin')!='LOCAL_OPERATOR':raise ValueError('PERSONAL_APPROVAL_NO_FIXTURE_OR_STRICT_SUBSTITUTION')
        return value
