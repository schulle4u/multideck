#!/usr/bin/env python
"""
Compile translation files (.po to .mo)
Requires msgfmt from gettext tools
"""

import os
import subprocess
from pathlib import Path


def compile_po_file(po_file: Path):
    """Compile a single .po file to .mo"""
    mo_file = po_file.with_suffix('.mo')

    try:
        # Use msgfmt to compile
        subprocess.run(['msgfmt', '-o', str(mo_file), str(po_file)], check=True)
        print(f"Compiled: {po_file} -> {mo_file}")
        return True
    except FileNotFoundError:
        print("Error: msgfmt not found. Please install gettext tools.")
        print("  Windows: Download from https://mlocati.github.io/articles/gettext-iconv-windows.html")
        print("  Linux: sudo apt-get install gettext")
        print("  macOS: brew install gettext")
        return False
    except subprocess.CalledProcessError as e:
        print(f"Error compiling {po_file}: {e}")
        return False


def main():
    """Compile all .po files in locale directory"""
    locale_dir = Path(__file__).parent / 'locale'

    if not locale_dir.exists():
        print(f"Error: locale directory not found: {locale_dir}")
        return 1

    # Find all .po files
    po_files = list(locale_dir.rglob('*.po'))

    if not po_files:
        print("No .po files found in locale directory")
        return 1

    print(f"Found {len(po_files)} translation file(s)")
    print()

    success_count = 0
    for po_file in po_files:
        if compile_po_file(po_file):
            success_count += 1

    print()
    print(f"Successfully compiled {success_count}/{len(po_files)} files")

    return 0 if success_count == len(po_files) else 1


if __name__ == '__main__':
    exit(main())
