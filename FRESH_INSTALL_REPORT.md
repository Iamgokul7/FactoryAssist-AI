# Fresh Installation Report — FactoryAssist AI

## 1. Purpose

Verify that FactoryAssist AI can install its dependencies and initialize successfully using `requirements.txt`, without relying on the existing project virtual environment, IDE state, or previously installed project dependencies.

**Overall result: PASS**

A clean virtual environment was created outside the project directory. All pinned dependencies installed successfully, the application imported, Python compilation passed, all 19 tests in the original validation snapshot passed, and selected API routes responded successfully through FastAPI's `TestClient`.

The original fresh-install validation covered 19 tests. The test suite subsequently expanded to 92 passing tests in a separate, later validation. The 92-test result must not be interpreted as a fresh-environment test run.

---

## 2. Environment

| Item | Value |
|---|---|
| Validation date | 10 November 2026 |
| Virtual environment | `%TEMP%\fab_fresh_venv` |
| Environment location | Outside the project directory |
| Python interpreter | Python 3.14.6 |
| pip version | 26.1.2 |
| Dependency source | `requirements.txt` |
| Installation exit code | `0` |
| Packages installed | 102 |
| Installation duration | Approximately 3.7 minutes |
| Existing project `.venv` | Left untouched |

**Python version note:** The project's documented target is Python 3.12. The fresh-install validation was performed using Python 3.14.6 because it was the system's unversioned Python interpreter at the time. This demonstrates successful dependency installation in that environment; it does not change the project's documented Python target or establish equivalent validation on Python 3.12.

---

## 3. Commands Executed

The following commands were executed in Windows Command Prompt:

```bat
python -m venv %TEMP%\fab_fresh_venv

%TEMP%\fab_fresh_venv\Scripts\python.exe -m pip install -r requirements.txt

%TEMP%\fab_fresh_venv\Scripts\python.exe -m compileall -q backend tests

%TEMP%\fab_fresh_venv\Scripts\python.exe -m unittest discover -s tests -t .

%TEMP%\fab_fresh_venv\Scripts\python.exe -m pip check
```

---

## 4. Validation Results

| Check | Result | Evidence |
|---|---|---|
| Virtual environment creation | PASS | Clean environment created outside the project directory |
| Dependency installation | PASS | 102 packages installed; pip exit code `0` |
| Key dependency imports | PASS | FastAPI, Uvicorn, ChromaDB, PyMuPDF, Google Gen AI SDK, Pydantic Settings and PyMuPDF4LLM |
| Application import | PASS | `from backend.main import app` completed successfully; 8 routes registered |
| Python compilation | PASS | `compileall -q backend tests` completed successfully |
| Original automated test suite | PASS | 19 tests passed in the fresh environment |
| Dependency consistency | PASS | `pip check` reported `No broken requirements found` |
| Health endpoint | PASS | `GET /health` returned HTTP `200` with `{"status":"healthy"}` |
| Root endpoint | PASS | `GET /` returned HTTP `200` |
| OpenAPI schema | PASS | 4 paths exposed through the OpenAPI schema |

### 4.1 Selected Installed Package Versions

| Package | Installed version |
|---|---|
| `google-genai` | 2.34.0 |
| `chromadb` | 1.5.9 |
| `pymupdf` | 2.1 |
| `fastapi` | 0.162.2 |
| `uvicorn` | 0.54.0 |
| `pydantic-settings` | 2.16.2 |
| `python-dotenv` | 1.2.4 |

---

## 5. Relationship to Latest Project Validation

The fresh-install test was performed before the Stage 7 document-management and access-control expansion.

The subsequent project validation reported:

| Validation | Result |
|---|---|
| Original fresh-environment test suite | 19 passed |
| Latest expanded automated test suite | 92 passed |
| Latest Python compilation check | Passed |
| Latest dependency consistency check | Passed |
| Latest JavaScript syntax check | Passed |

The 92-test result includes the expanded document-management and access-control coverage. It was obtained separately and does not replace the original fresh-install result.

For the expanded test results, refer to:

- `DOCUMENT_UPLOAD_TEST_REPORT.md`
- `DOCUMENT_MANAGEMENT_IMPLEMENTATION_REPORT.md`

---

## 6. Scope and Limitations

The following points define what this validation did and did not cover:

- **Server execution:** This validation did not start a separate long-running application server. API checks used FastAPI's `TestClient`. Live question-answering tests were performed separately against the existing application running on port 8000.
- **Gemini API:** No Gemini API calls were made during the fresh-install test run. The 19 automated tests were offline.
- **API coverage:** The `TestClient` checks covered the health endpoint, root endpoint and OpenAPI schema. They were not a complete end-to-end application test.
- **Environment configuration:** The fresh virtual environment did not receive a separate copy of `.env`. The tests ran with the project directory as the working directory, where the existing local configuration was available. No secret values were printed or included in this report.
- **Latest test suite:** The later 92-test validation is documented separately and should not be confused with the original 19-test fresh-install result.
- **Python compatibility:** The fresh-install test used Python 3.14.6. A separate fresh-install run using the documented Python 3.12 target is not established by this report.

---

## 7. Temporary Environment Cleanup

The temporary virtual environment was retained after validation for inspection.

It can be removed using the following Windows Command Prompt command when no longer needed:

```bat
rmdir /s /q %TEMP%\fab_fresh_venv
```

---

## 8. Conclusion

The fresh-install validation passed. Project dependencies installed successfully from `requirements.txt` in a clean Python environment, the application imported, compilation completed, the original 19 automated tests passed, and the selected API routes responded successfully.

This provides evidence of dependency-installation and basic application-initialization compatibility in the tested Python 3.14.6 environment.

It does not establish complete production readiness, full end-to-end functionality in a fresh environment, or fresh-install validation of the later 92-test suite.