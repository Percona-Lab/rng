import json
import pandas as pd
import argparse
import requests
import re
from collections import defaultdict

parser = argparse.ArgumentParser(description="Convert JSON URL to markdown")
parser.add_argument("--url", help="URL to JSON file")
parser.add_argument("--exclude", type=str, help="Comma-separated list of patterns to exclude", default="")
parser.add_argument("--sort", type=str, help="Comma-separated list of group sort patterns", default="")
args = parser.parse_args()

response = requests.get(args.url)
response.raise_for_status()
data = response.json()

rows = []

image_entries = []
for category, versions in data["versions"][0]["matrix"].items():
    for version, details in versions.items():
        image_path = details["image_path"]
        image_hash = details.get("image_hash", "")
        image_entries.append((image_path, image_hash, version, category))
        if "image_hash_arm64" in details:
            image_entries.append((f"{image_path} (ARM64)", details["image_hash_arm64"], version, category))

def extract_version(version):
    return [int(part) if part.isdigit() else part for part in re.split(r'[-.]', version) if part]

exclude_patterns = [p.strip() for p in args.exclude.split(",")] if args.exclude else []
if exclude_patterns:
    image_entries = [entry for entry in image_entries if not any(re.search(pattern, entry[0]) for pattern in exclude_patterns)]

sort_patterns = [p.strip() for p in args.sort.split(",")] if args.sort else []

groups = defaultdict(list)
for entry in image_entries:
    image_path, digest, version, category = entry
    group_index = len(sort_patterns)
    for idx, pattern in enumerate(sort_patterns):
        if re.search(pattern, image_path):
            group_index = idx
            break
    groups[group_index].append(entry)

sorted_entries = []
for idx in sorted(groups.keys()):
    groups[idx].sort(key=lambda x: extract_version(x[2]), reverse=True)
    sorted_entries.extend(groups[idx])

if sorted_entries:
    rows.extend([(path, digest) for path, digest, _, _ in sorted_entries])
else:
    rows.append(["No matching images found.", ""])

df = pd.DataFrame(rows, columns=["Image", "Digest"])
print(df.to_markdown(index=False))
