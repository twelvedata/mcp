import os
import yaml
import json
import re
from collections import defaultdict

input_path = "../data/openapi31_no_ti.json"
output_dir = "../data"


def load_spec(path):
    with open(path, 'r', encoding='utf-8') as f:
        if path.lower().endswith(('.yaml', '.yml')):
            return yaml.safe_load(f)
        return json.load(f)


def dump_spec(spec, path):
    with open(path, 'w', encoding='utf-8') as f:
        if path.lower().endswith(('.yaml', '.yml')):
            yaml.safe_dump(spec, f, sort_keys=False, allow_unicode=True)
        else:
            json.dump(spec, f, ensure_ascii=False, indent=2)


def find_refs(obj):
    """Recursively collect all $ref strings."""
    refs = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == '$ref' and isinstance(v, str):
                refs.add(v)
            else:
                refs |= find_refs(v)
    elif isinstance(obj, list):
        for item in obj:
            refs |= find_refs(item)
    return refs


def split_paths(keys, chunk_size=30):
    """Split list of path keys into chunks of size chunk_size."""
    for i in range(0, len(keys), chunk_size):
        yield keys[i:i + chunk_size]


def prune_components(full_components, used_refs):
    """
    Keep only those components that are referenced in used_refs,
    including nested references.
    """
    pattern = re.compile(r'^#/components/([^/]+)/(.+)$')
    used = defaultdict(set)

    # Mark direct refs
    for ref in used_refs:
        m = pattern.match(ref)
        if m:
            comp_type, comp_name = m.group(1), m.group(2)
            used[comp_type].add(comp_name)

    # Recursively include nested
    changed = True
    while changed:
        changed = False
        for comp_type, names in list(used.items()):
            for name in list(names):
                definition = full_components.get(comp_type, {}).get(name)
                if definition:
                    for r in find_refs(definition):
                        m2 = pattern.match(r)
                        if m2:
                            ct, cn = m2.group(1), m2.group(2)
                            if cn not in used[ct]:
                                used[ct].add(cn)
                                changed = True

    # Build pruned subset
    pruned = {}
    for comp_type, defs in full_components.items():
        if comp_type in used:
            kept = {n: defs[n] for n in defs if n in used[comp_type]}
            if kept:
                pruned[comp_type] = kept
    return pruned


def main():
    os.makedirs(output_dir, exist_ok=True)

    # Load full spec
    spec = load_spec(input_path)
    all_paths = list(spec.get('paths', {}).keys())
    total_paths = len(all_paths)
    total_components = sum(len(v) for v in spec.get('components', {}).values())
    print(f"Original spec: {total_paths} paths, {total_components} component definitions")

    # Split paths
    chunks = list(split_paths(all_paths))

    for idx, paths_chunk in enumerate(chunks, start=1):
        new_spec = {
            'openapi': spec.get('openapi'),
            'info': spec.get('info'),
            'servers': spec.get('servers', []),
            'paths': {k: spec['paths'][k] for k in paths_chunk}
        }

        # Prune components
        used_refs = find_refs(new_spec['paths'])
        pruned = prune_components(spec.get('components', {}), used_refs)
        if pruned:
            new_spec['components'] = pruned

        # Counts for this part
        new_paths_count = len(new_spec['paths'])
        new_components_count = sum(len(v) for v in new_spec.get('components', {}).values())
        out_file = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(input_path))[0]}_part{idx}{os.path.splitext(input_path)[1]}")
        dump_spec(new_spec, out_file)
        print(f"Part {idx}: {new_paths_count} paths, {new_components_count} components -> {out_file}")


if __name__ == "__main__":
    main()
