import io
import pickle
import pickletools
import re
import unittest
import zlib
from pathlib import Path

import bridge


class InstalledGameTests(unittest.TestCase):
    def test_verified_navigation_labels_exist_in_packaged_compiled_scripts(self):
        scripts = bridge.RECOMMENDED_GAME_DIR / 'game/scripts.rpa'
        if not scripts.is_file():
            self.skipTest('private DDLC package is not installed')
        data = scripts.read_bytes()
        header, _body = data.split(b'\n', 1)
        match = re.fullmatch(rb'RPA-3\.0 ([0-9a-fA-F]{16}) ([0-9a-fA-F]{8})', header)
        self.assertIsNotNone(match, 'expected the inspected Ren\'Py RPA-3.0 script archive')
        index_offset = int(match.group(1), 16)
        key = int(match.group(2), 16)
        index_data = zlib.decompress(data[index_offset:])
        forbidden = {'GLOBAL', 'STACK_GLOBAL', 'REDUCE', 'BUILD', 'INST', 'OBJ', 'PERSID', 'BINPERSID', 'EXT1', 'EXT2', 'EXT4', 'NEWOBJ', 'NEWOBJ_EX'}
        self.assertFalse(any(op.name in forbidden for op, _arg, _pos in pickletools.genops(index_data)))

        class RestrictedUnpickler(pickle.Unpickler):
            def find_class(self, _module, _name):
                raise ValueError('global references are disabled')

            def persistent_load(self, _persistent_id):
                raise ValueError('persistent references are disabled')

        index = RestrictedUnpickler(io.BytesIO(index_data), fix_imports=False, encoding='bytes').load()
        script_bytes = []
        for filename, pieces in index.items():
            name = filename.encode() if isinstance(filename, str) else filename
            if not name.endswith(b'.rpyc'):
                continue
            compiled = b''.join(prefix + data[(offset ^ key):(offset ^ key) + (length ^ key)] for offset, length, prefix in pieces)
            for offset in range(20, min(len(compiled), 100)):
                if compiled[offset:offset + 2] == b'\x78\xda':
                    try:
                        script_bytes.append(zlib.decompress(compiled[offset:]))
                    except zlib.error:
                        pass
                    break
        all_script_bytes = b'\n'.join(script_bytes)
        self.assertTrue(script_bytes, 'compiled Ren\'Py scripts were indexed')
        for label in bridge.ACT_LABELS.values():
            self.assertIn(label.encode('ascii'), all_script_bytes, label)
        for label in ('ch0_kill', 'sayori_confess', 'ch3_start_natsuki', 'yuri_kill'):
            self.assertIn(label.encode('ascii'), all_script_bytes, label)


if __name__ == '__main__':
    unittest.main()
