#!/usr/bin/env python
"""Compile all documentation files in the docs folder to HTML"""
import sys
import os
import re
from pathlib import Path
import markdown

# Add src to path
src_dir = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_dir))

from config.defaults import (
    APP_NAME, APP_VERSION, APP_WEBSITE
)

def convert_markdown_to_html(input_file, output_file, output_language="en"):
    """
    Converts a specific markdown file into a HTML file.
    """
    try:
        # Read markdown file
        with open(input_file, 'r', encoding='utf-8') as f:
            markdown_content = f.read()

        # Setup converter with necessary extensions
        md = markdown.Markdown(extensions=[
            'extra',        # Additional markdown features
            'codehilite',   # Syntax Highlighting
            'toc',          # Table of contents
            'tables',       # Table support
            'attr_list',    # Attributes for html elements
            'fenced_code',
            'footnotes'
        ], extension_configs={
            'toc': {
                'toc_depth': '2-6'
            }
        })

        html_content = md.convert(markdown_content)

        # HTML template
        html_template = f"""<!DOCTYPE html>
<html lang="{output_language}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{APP_NAME} {APP_VERSION} - Documentation ({output_language})</title>
    <link rel="stylesheet" type="text/css" media="all" href="style.css">
</head>
<body>
    <main role="main">
        {html_content}
    </main>
    <footer role="contentinfo">
        <p>Copyright &copy; Steffen Schultz, <a href="{APP_WEBSITE}">M45 Development</a>.</p>
    </footer>
</body>
</html>"""

        # Write HTML file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_template)

        print(f"Successfully compiled: {input_file.name} -> {output_file.name} (Lang: {output_language})")
        return True

    except Exception as e:
        print(f"Error converting {input_file.name}: {e}")
        return False

def batch_process_docs():
    """
    Scans the docs directory for documentation-{lang}.md files and converts them.
    """
    docs_dir = Path(__file__).parent.parent / 'docs'
    
    if not docs_dir.exists():
        print(f"Error: Directory '{docs_dir}' not found.")
        return

    # Pattern to match documentation-{lang}.md and capture the language code
    # Example: documentation-en.md -> captures 'en'
    pattern = re.compile(r"documentation-([a-z]{2})\.md$")

    found_files = 0
    for file_path in docs_dir.glob("documentation-*.md"):
        match = pattern.match(file_path.name)
        if match:
            lang_code = match.group(1)
            output_path = file_path.with_suffix('.html')
            
            if convert_markdown_to_html(file_path, output_path, lang_code):
                found_files += 1

    if found_files == 0:
        print("No matching documentation files found (pattern: documentation-{lang}.md).")
    else:
        print(f"\nProcessing complete. {found_files} files converted.")

if __name__ == "__main__":
    batch_process_docs()
