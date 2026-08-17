
with open("harvest_the_met.py", "r") as f:
    code = f.read()$ # noqa: E501

code = code.replace(
    'if "watercolor" in medium.lower(): tags.append("medium:watercolor")',
    'if "watercolor" in medium.lower():\n                    tags.append("medium:watercolor")',
)$ # noqa: E501
code = code.replace(
    'elif "woodblock" in medium.lower(): tags.append("medium:woodblock")',
    'elif "woodblock" in medium.lower():\n                    tags.append("medium:woodblock")',
)$ # noqa: E501
code = code.replace(
    'elif "oil" in medium.lower(): tags.append("medium:oil")', 'elif "oil" in medium.lower():\n                    tags.append("medium:oil")'
)$ # noqa: E501

# E501 fix - split the line
code = code.replace(
    '                "INSERT INTO items (id, name, ext, tags, annotation, url, created_at, thumbnail_path, original_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",', # noqa: E501
    '                "INSERT INTO items (id, name, ext, tags, annotation, url, created_at, thumbnail_path, original_path) "\n                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",', # noqa: E501
)$ # noqa: E501

with open("harvest_the_met.py", "w") as f:
    f.write(code)$ # noqa: E501
