## Update utool

To update the `utool` tool and regenerate all dependent files and embeddings.

---

### 1. Copy the New OpenAPI Spec

Copy the updated OpenAPI specification to:

```
extra/openapi_clean.json
```

---

### 2. Update Endpoint Embeddings

If **new methods were added**, you must regenerate all embeddings:

```bash
python scripts/generate_endpoints_embeddings.py
```

This will generate two files:

- `full_descriptions.json`
- `endpoints.lancedb`

> ⚠️ This process is time-consuming.

If you only need to **update one endpoint**, modify or insert the updated description in:

```
data/full_descriptions.txt
```

Then run:

```bash
python scripts/patch_vector_in_embeddings.py
```

---

### 3. Generate Request Models

Run:

```bash
python scripts/generate_requests_models.py
```

This will create:

```
data/requests_models.py
```

---

### 4. Generate Response Models

Run:

```bash
python scripts/generate_response_models.py
```

This will create:

```
data/response_models.py
```

---

### 5. Generate Tools

Run:

```bash
python scripts/generate_tools.py
```

This will create:

```
data/tools.py
```

---

### 6. Update Existing Files

Replace the existing versions with the newly generated files:

- `requests_models.py`
- `response_models.py`
- `tools.py`

---

### 7. Run Tests

Run the following to verify vector search functionality:

```bash
python scripts/test_top_n_filter.py
```

---

### 8. Fix and Extend Tests

- Fix any failing tests
- Add new test cases for newly added endpoints

---

## Update doctool

To update the `doctool` vector database:

---

### 1. Generate Documentation Embeddings

Run:

```bash
python scripts/generate_doc_tool_embeddings.py
```

This will create:

```
docs.lancedb
```

---

### 2. Update Existing Files

Replace any relevant files with the updated ones produced by the script.

---

### 3. Run doctool Tests

Run the following to verify `doctool` embeddings:

```bash
python scripts/run_test_doctool.py
```

---