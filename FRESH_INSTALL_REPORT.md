# Fresh installation report

Purpose: prove that the repository installs and runs from `requirements.txt`
alone, without the project's existing `.venv`, IDE state or cached artefacts.

**Result: PASS.** A clean virtual environment installed every pinned dependency,
imported the application, passed `compileall`, passed all 19 tests and served the
API routes. This was the stage-6 snapshot; the suite has since grown to 92 tests
and `pip check` still reports no broken requirements.

---

## Environment

| Item | Value |
| --- | --- |
| Date | 10 November 2026 |
| Location | `%TEMP%\fab_fresh_venv` (outside the project directory) |
| Interpreter | Python 3.14.6 (system `python` at venv creation) |
| pip | 26.1.2 |
| Install command | `fab_fresh_venv\Scripts\python.exe -m pip install -r requirements.txt` |
| Exit code | `0` |
| Packages installed | 102 |
| Duration | ≈ 3.7 minutes (venv created 16:13:15, install finished 16:16:56) |
| Existing `.venv` | untouched, still used by the running application |

Note: the documented target is Python 3.12 (see `README.md`); the machine's
unversioned `python` is 3.14, so this run also shows the pinned set installs and
passes on 3.14. That is a compatibility observation, not a change of supported
version.

## Commands executed

```bat
python -m venv %TEMP%\fab_fresh_venv
%TEMP%\fab_fresh_venv\Scripts\python.exe -m pip install -r requirements.txt
%TEMP%\fab_fresh_venv\Scripts\python.exe -m compileall -q backend tests
%TEMP%\fab_fresh_venv\Scripts\python.exe -m unittest discover -s tests -t .
%TEMP%\fab_fresh_venv\Scripts\python.exe -m pip check
```

## Results

| Check | Result | Evidence |
| --- | --- | --- |
| Dependency installation | **PASS** | `Successfully installed …`, `pip` exit `0` |
| Key imports | **PASS** | `fastapi`, `uvicorn`, `chromadb`, `pymupdf`, `google.genai`, `pydantic_settings`, `pymupdf4llm` |
| Application import | **PASS** | `from backend.main import app` → 8 routes |
| Compilation | **PASS** | `compileall backend tests` exit `0` |
| Automated tests | **PASS** | `Ran 19 tests … OK` (0.020 s) |
| Dependency consistency | **PASS** | `pip check` → `No broken requirements found` |
| App serves routes | **PASS** | `TestClient`: `GET /health` → `200 {"status":"healthy"}`, `GET /` → `200`, OpenAPI exposes 4 paths |

Pinned versions installed: `google-genai 2.34.0`, `chromadb 1.5.9`,
`pymupdf 2.1`, `fastapi 0.162.2`, `uvicorn 0.54.0`,
`pydantic-settings 2.16.2`, `python-dotenv 1.2.4`.

## What this run did not do

- It did not start a long-running server; the live question tests were executed
  against the existing application on port 8000 (see
  `FINAL_SUBMISSION_REPORT.md`).
- It made no Gemini API calls. The 19 tests are offline; the `TestClient` check
  only touched `/health`, `/` and the OpenAPI schema.
- It did not copy `.env`. Configuration was read from the project's `.env`
  because the tests ran with the project as the working directory; no key value
  was printed or stored by this run.
- The temporary environment was left in `%TEMP%` for inspection and can be
  deleted with `rmdir /s /q %TEMP%\fab_fresh_venv`.
