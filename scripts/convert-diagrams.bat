@echo off
echo Converting Mermaid diagrams to PNG...
cd ..\docs\images\architecture
for %%f in (*.mmd) do (
    echo Converting %%f...
    npx -y @mermaid-js/mermaid-cli -i %%f -o %%~nf.png -w 2400 -H 1600 -b white
)
cd ..\..\..
echo Done!
