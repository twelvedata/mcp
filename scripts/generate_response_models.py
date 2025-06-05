from datamodel_code_generator import InputFileType, generate, PythonVersion
from pathlib import Path

openapi_path = '../data/openapi_clean.json'   # путь к спецификации
output_path = '../data/response_models.py'        # куда сохранить

# Чтение исходного файла
with open(openapi_path, 'r', encoding='utf-8') as f:
    openapi_content = f.read()

# Генерация моделей
generate(
    input_=openapi_content,
    input_file_type=InputFileType.OpenAPI,
    output=Path(output_path),
    class_name=None,
    target_python_version=PythonVersion.PY_313,
)

print(f"Генерация завершена: {output_path}")
