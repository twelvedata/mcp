import subprocess
from pathlib import Path

openapi_path = '../extra/openapi_clean.json'
output_path = '../data/response_models.py'

cmd = [
    'datamodel-codegen',
    '--input', str(openapi_path),
    '--input-file-type', 'openapi',
    '--output', str(output_path),
    '--output-model-type', 'pydantic_v2.BaseModel',
    '--reuse-model',
    '--use-title-as-name',
    '--disable-timestamp',
    '--field-constraints',
    '--use-double-quotes',
]

subprocess.run(cmd, check=True)

# Append aliases
alias_lines = [
    '',
    '# Aliases for response models',
    'GetMarketMovers200Response = MarketMoversResponseBody',
    'GetTimeSeriesPercent_B200Response = GetTimeSeriesPercentB200Response',
    ''
]

with open(output_path, 'a', encoding='utf-8') as f:
    f.write('\n'.join(alias_lines))

print(f"[SUCCESS] Models generated using CLI and aliases added: {output_path}")
