import os
import yaml
import json
import re
from collections import defaultdict

input_path = "../data/openapi01.06.2025.json"
output_dir = "../data"

mirrors = [
    "https://api-reference-data.twelvedata.com/",
    "https://api-time-series.twelvedata.com/",
    "https://api-mutual-funds.twelvedata.com/",
    "https://api-etfs.twelvedata.com/",
    "https://api-fundamental.twelvedata.com/",
    "https://api-analysis.twelvedata.com/",
    "https://api-regulator.twelvedata.com/",
    "https://api-ti-overlap-studies.twelvedata.com/",
    "https://api-ti-volume-indicators.twelvedata.com/",
    "https://api-ti-price-transform.twelvedata.com/",
    "https://api-ti-cycle-indicators.twelvedata.com/",
    "https://api-ti-statistics-functions.twelvedata.com/"
]

allowed_endpoints = [
    # Reference Data
    "/stocks",
    "/forex_pairs",
    "/cryptocurrencies",
    "/funds",
    "/bonds",
    "/etfs",
    "/commodities",
    "/cross_listings",
    "/exchanges",
    "/exchange_schedule",
    "/cryptocurrency_exchanges",
    "/market_state",
    "/instrument_type",
    "/countries",
    "/earliest_timestamp",
    "/symbol_search",
    "/intervals",

    # Core Data
    "/time_series",
    "/time_series/cross",
    "/exchange_rate",
    "/currency_conversion",
    "/quote",
    "/price",
    "/eod",
    "/market_movers/{market}",

    # Mutual Funds
    "/mutual_funds/list",
    "/mutual_funds/family",
    "/mutual_funds/type",
    "/mutual_funds/world",
    "/mutual_funds/world/summary",
    "/mutual_funds/world/performance",
    "/mutual_funds/world/risk",
    "/mutual_funds/world/ratings",
    "/mutual_funds/world/composition",
    "/mutual_funds/world/purchase_info",
    "/mutual_funds/world/sustainability",

    # ETFs
    "/etfs/list",
    "/etfs/family",
    "/etfs/type",
    "/etfs/world",
    "/etfs/world/summary",
    "/etfs/world/performance",
    "/etfs/world/risk",
    "/etfs/world/composition",

    # Fundamentals
    "/balance_sheet",
    "/balance_sheet/consolidated",
    "/cash_flow",
    "/cash_flow/consolidated",
    "/dividends",
    "/dividends_calendar",
    "/earnings",
    "/income_statement",
    "/income_statement/consolidated",
    "/ipo_calendar",
    "/key_executives",
    "/last_change/{endpoint}",
    "/logo",
    "/market_cap",
    "/profile",
    "/splits",
    "/splits_calendar",
    "/statistics",

    # Analysis
    "/analyst_ratings/light",
    "/analyst_ratings/us_equities",
    "/earnings_estimate",
    "/revenue_estimate",
    "/eps_trend",
    "/eps_revisions",
    "/growth_estimates",
    "/price_target",
    "/recommendations",
    "/earnings_calendar",

    # Regulatory
    "/tax_info",
    "/edgar_filings/archive",
    "/insider_transactions",
    "/direct_holders",
    "/fund_holders",
    "/institutional_holders",
    "/sanctions/{source}",
]

added_endpoints = []


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


def split_paths(keys, chunk_size=25):
    for i in range(0, len(keys), chunk_size):
        yield keys[i:i + chunk_size]


def filter_paths(all_paths, allowed_list):
    """
    Возвращает список только тех путей из all_paths, которые присутствуют в allowed_list.
    Кроме того, печатает пути, которые есть в allowed_list, но не найдены в all_paths.
    """
    f_paths = [path for path in all_paths if path in allowed_list]
    missing_paths = [path for path in allowed_list if path not in f_paths]
    if missing_paths:
        print("Paths in allowed_list but not found in all_paths:", missing_paths)
    return f_paths


def prune_components(full_components, used_refs):
    pattern = re.compile(r'^#/components/([^/]+)/(.+)$')
    used = defaultdict(set)

    # Помечаем прямые ссылки
    for ref in used_refs:
        m = pattern.match(ref)
        if m:
            comp_type, comp_name = m.group(1), m.group(2)
            used[comp_type].add(comp_name)

    # Рекурсивно включаем вложенные
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

    # Сборка ограниченного набора
    pruned = {}
    for comp_type, defs in full_components.items():
        if comp_type in used:
            kept = {n: defs[n] for n in defs if n in used[comp_type]}
            if kept:
                pruned[comp_type] = kept
    return pruned


def trim_fields(obj):
    """
    Рекурсивно обрезает строки в полях:
    - 'description' до 300 символов
    - 'example' до 700 символов
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "description" and isinstance(v, str):
                if len(v) > 300:
                    obj[k] = v[:300]
            elif k == "example" and isinstance(v, str):
                if len(v) > 700:
                    obj[k] = v[:700]
            else:
                trim_fields(v)
    elif isinstance(obj, list):
        for item in obj:
            trim_fields(item)


def add_empty_properties(obj):
    """
    Рекурсивно ищет все вхождения ключа 'schema'. Если его значение — dict,
    и в этом dict нет 'properties', добавляет 'properties': {}.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "schema" and isinstance(v, dict):
                if "properties" not in v:
                    v["properties"] = {}
                # Продолжаем углубленный обход внутри найденной схемы
                add_empty_properties(v)
            else:
                add_empty_properties(v)
    elif isinstance(obj, list):
        for item in obj:
            add_empty_properties(item)


def main():
    os.makedirs(output_dir, exist_ok=True)

    spec = load_spec(input_path)
    all_paths = list(spec.get('paths', {}).keys())
    f_paths = filter_paths(all_paths, allowed_endpoints)
    chunks = list(split_paths(f_paths))

    for idx, paths_chunk in enumerate(chunks, start=1):
        # Собираем новую часть спецификации
        new_spec = {
            'openapi': spec.get('openapi'),
            'info': spec.get('info'),
            'servers': (
                [{'url': mirrors[idx - 1]}]
                if idx - 1 < len(mirrors)
                else spec.get('servers', [])
            ),
            'paths': {k: spec['paths'][k] for k in paths_chunk}
        }

        # Обрезаем длинные поля и добавляем отсутствующие 'properties'
        add_empty_properties(new_spec)
        trim_fields(new_spec)

        # Прореживаем компоненты
        used_refs = find_refs(new_spec['paths'])
        pruned = prune_components(spec.get('components', {}), used_refs)
        if pruned:
            new_spec['components'] = pruned

        # Считаем метрики и сохраняем файл
        new_paths_count = len(new_spec['paths'])
        new_components_count = sum(
            len(v) for v in new_spec.get('components', {}).values()
        )
        out_file = os.path.join(
            output_dir,
            f"{os.path.splitext(os.path.basename(input_path))[0]}"
            f"_part{idx}{os.path.splitext(input_path)[1]}"
        )
        dump_spec(new_spec, out_file)
        print(
            f"Part {idx}: {new_paths_count} paths, "
            f"{new_components_count} components -> {out_file}"
        )


if __name__ == "__main__":
    main()

