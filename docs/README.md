# Documentation Assets

This directory contains supporting assets for project documentation.

## Structure

```
docs/
└── images/
    └── architecture/        # Architecture diagrams
        ├── *.png           # PNG exports (2400x1600px)
        ├── *.mmd           # Mermaid source files
        └── README.md       # Diagram documentation
```

## Architecture Diagrams

High-resolution PNG diagrams generated from Mermaid source code:

- **Format**: PNG (2400x1600px, white background)
- **Source**: `architecture-diagrams.md` in project root
- **Generator**: `generate-diagrams.py` + `@mermaid-js/mermaid-cli`

### Available Diagrams

1. High-Level Architecture (three-layer system)
2. Data Flow (complete purchase transaction)
3. Agent Relationships (buyer+seller pattern)
4. Economic Flow (token circulation)
5. Security Architecture (AWS Secrets Manager)
6. Network Architecture (endpoints and communication)
7. Component Stack (technology visualization)
8. Agent Discovery Flow (A2A protocol)
9. System Status (deployment status)

See [`images/architecture/README.md`](./images/architecture/README.md) for details.

## Regenerating Diagrams

```bash
# From project root
python scripts/generate-diagrams.py

# Convert all to PNG (Windows)
scripts\convert-diagrams.bat

# Or manually convert each file
cd docs/images/architecture
npx -y @mermaid-js/mermaid-cli -i <file.mmd> -o <file.png> -w 2400 -H 1600 -b white
```

## Usage

PNG diagrams can be used in:
- Presentations (PowerPoint, Google Slides)
- Documentation (PDF, DOCX)
- Blog posts and articles  
- Social media
- Printed materials

## License

Same as main project (MIT License)

