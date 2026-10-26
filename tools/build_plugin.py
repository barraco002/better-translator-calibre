"""Build a deterministic, installable Calibre ZIP from an explicit allowlist."""
import argparse
import ast
import hashlib
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def version():
    tree = ast.parse((ROOT / '__init__.py').read_text(encoding='utf-8'))
    plugin = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                  and node.name == 'EbookTranslator')
    assignment = next(node for node in plugin.body if isinstance(node, ast.Assign)
                      and any(isinstance(target, ast.Name) and target.id == 'version'
                              for target in node.targets))
    return '.'.join(map(str, ast.literal_eval(assignment.value)))


def build(destination=None):
    destination = Path(destination or ROOT / 'dist')
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / ('Better-Translator-v%s.zip' % version())
    files = list(ROOT.glob('*.py')) + list(ROOT.glob('README*.md'))
    files += [ROOT / 'LICENSE', ROOT / 'CHANGELOG.md',
              ROOT / 'plugin-import-name-better_translator.txt']
    for directory in ('components', 'engines', 'lib', 'vendor', 'images', 'translations'):
        files.extend(path for path in (ROOT / directory).rglob('*')
                     if path.is_file() and '__pycache__' not in path.parts
                     and path.suffix not in ('.pyc', '.pyo'))
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for path in sorted(set(files)):
            name = path.relative_to(ROOT).as_posix()
            data = path.read_bytes()
            if path.suffix in ('.py', '.md', '.txt', '.po') or path.name == 'LICENSE':
                data = data.replace(b'\r\n', b'\n')
            if path.suffix == '.py':
                compile(data, name, 'exec')
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            output.writestr(info, data)
    with zipfile.ZipFile(archive) as result:
        assert result.testzip() is None
        assert '__init__.py' in result.namelist()
        assert result.read('plugin-import-name-better_translator.txt') == b''
        assert not any(name.startswith(('tests/', 'tools/', '.git', 'work/'))
                       for name in result.namelist())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (destination / 'SHA256SUMS.txt').write_text(
        '%s  %s\n' % (digest, archive.name), encoding='utf-8')
    print('%s | %s bytes | SHA256 %s' % (archive, archive.stat().st_size, digest))
    return archive


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    build(parser.parse_args().output)
