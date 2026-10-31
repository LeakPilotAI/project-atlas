"""Full synthetic fixture inventory; no authority, financial IO or deletion."""
import os
import stat
import time


def fixture_budget(root, *, started, extra=0, max_entries=2048, max_bytes=32*1024*1024,
                   max_seconds=180, clock=time.monotonic):
    if (type(extra) is not int or extra < 0 or type(max_entries) is not int or max_entries < 1
            or type(max_bytes) is not int or max_bytes < 1):
        raise ValueError('TEST_RESOURCE_LIMIT_ARGUMENTS')
    count, size, pending = 0, 0, [os.fspath(root)]
    while pending:
        directory = pending.pop()
        info = os.stat(directory, follow_symlinks=False)
        if (not stat.S_ISDIR(info.st_mode)
                or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise ValueError('TEST_LINK_REFUSED')
        if clock()-started > max_seconds:
            raise ValueError('TEST_RESOURCE_LIMIT')
        with os.scandir(directory) as entries:
            for entry in entries:
                # Windows DirEntry retains FindFirst/Next metadata. One cached
                # non-following stat checks type, reparse attributes and size;
                # it does not issue three separate path queries for every file.
                info = entry.stat(follow_symlinks=False)
                if getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                    raise ValueError('TEST_LINK_REFUSED')
                count += 1
                if stat.S_ISDIR(info.st_mode):
                    pending.append(entry.path)
                elif stat.S_ISREG(info.st_mode):
                    size += info.st_size
                else:
                    raise ValueError('TEST_LINK_REFUSED')
                if count >= max_entries or size+extra > max_bytes:
                    raise ValueError('TEST_RESOURCE_LIMIT')
    if size+extra > max_bytes or clock()-started > max_seconds:
        raise ValueError('TEST_RESOURCE_LIMIT')
    return count, size
