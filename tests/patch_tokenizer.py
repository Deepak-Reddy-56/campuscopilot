"""Patch _extract_entities tokenizer to fix 's' being treated as punctuation."""
with open("app.py", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "maketrans" in line and "?.,!;:" in line and "extract" not in line:
        print(f"Found at line {i+1}: {repr(line.rstrip())}")
        # Replace with a clean version that only strips punctuation, not 's'
        indent = len(line) - len(line.lstrip())
        lines[i] = " " * indent + 'tokens = query.lower().translate(str.maketrans("", "", "?.,!;:\\"\'")).split()\n'
        print(f"Replaced with: {repr(lines[i].rstrip())}")
        break

with open("app.py", "w", encoding="utf-8") as f:
    f.writelines(lines)
print("Done.")
