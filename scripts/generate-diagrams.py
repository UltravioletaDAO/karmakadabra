#!/usr/bin/env python3
"""Extract Mermaid diagrams from architecture-diagrams.md and create individual .mmd files."""

import re
from pathlib import Path

# Read the markdown file (from project root)
project_root = Path(__file__).parent.parent
with open(project_root / 'architecture-diagrams.md', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract all mermaid code blocks with their section titles
# Pattern to match: ## Section Title\n\n### Subsection\n\n```mermaid\ncode\n```
pattern = r'## ([^\n]+)\n\n### ([^\n]+)\n\n```mermaid\n(.*?)```'

matches = re.findall(pattern, content, re.DOTALL)

print(f"Found {len(matches)} diagrams")

# Create output directory (from project root)
output_dir = project_root / 'docs' / 'images' / 'architecture'
output_dir.mkdir(parents=True, exist_ok=True)

# Generate .mmd files for each diagram
diagram_names = []
for i, (section, subsection, diagram_code) in enumerate(matches):
    # Create a filename from section and subsection
    section_clean = re.sub(r'[^\w\s-]', '', section).strip().replace(' ', '-').lower()
    subsection_clean = re.sub(r'[^\w\s-]', '', subsection).strip().replace(' ', '-').lower()
    filename = f"{section_clean}-{subsection_clean}.mmd"
    
    # Save the diagram
    mmd_file = output_dir / filename
    with open(mmd_file, 'w', encoding='utf-8') as f:
        f.write(diagram_code.strip())
    
    diagram_names.append({
        'index': i + 1,
        'filename': filename,
        'section': section,
        'subsection': subsection
    })
    
    print(f"[OK] Created {mmd_file}")

print(f"\nCreated {len(matches)} diagram files")
print("\nTo convert to PNG, run:")
print("npx -y @mermaid-js/mermaid-cli -i <file.mmd> -o <file.png>")

# Also create a script to convert all
script_content = """@echo off
echo Converting Mermaid diagrams to PNG...
cd docs\\images\\architecture
for %%f in (*.mmd) do (
    echo Converting %%f...
    npx -y @mermaid-js/mermaid-cli -i %%f -o %%~nf.png -w 2400 -H 1600 -b white
)
echo Done!
"""
with open('convert-diagrams.bat', 'w') as f:
    f.write(script_content)
print("\nCreated convert-diagrams.bat for batch conversion")
