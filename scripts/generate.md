LC_CTYPE=C tr -cd '\11\12\15\40-\176' < openapi01.06.2025.json > openapi_clean.json
datamodel-codegen --input openapi_clean.json --input-file-type openapi --output models.py