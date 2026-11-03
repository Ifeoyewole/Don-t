from pathlib import Path

path = Path('src/App.tsx')
text = path.read_text(encoding='utf-8')
blocks = [
    """      if (route.key === 'results' || route.key === 'upload-inspection') {\n      }\n\n""",
    """        if (route.key === 'results') {\n        }\n""",
]
for block in blocks:
    if block not in text:
        raise RuntimeError(f'Expected empty debug wrapper not found: {block!r}')
    text = text.replace(block, '', 1)
path.write_text(text, encoding='utf-8')
print('empty debug wrappers removed')
