import ast
import asyncio
import os
import re
import subprocess
import threading
import time
import unicodedata
from pathlib import Path
from typing import Any, Optional
import uuid

try:
    import litellm
except ImportError:
    pass

from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from code_helper.tools._context import get_project_root
from code_helper.tools._paths import safe_resolve, PathSecurityError
from code_helper.rag.secrets_mask import mask_secrets
from code_helper.rag.scanner import scan_python_files
from google.adk.runners import Runner, RunConfig
from google.adk.sessions import InMemorySessionService
from google.genai import types
from code_helper.agent import root_agent

app = FastAPI(title="CodeLore API", version="1.0.0")

# ---------------------------------------------------------
# CORS Security
# ---------------------------------------------------------
frontend_origins = os.getenv("FRONTEND_ORIGINS", "http://localhost:5173")
allow_origins = [o.strip() for o in frontend_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# In-memory Rate Limiting: 8 requests per 10 minutes per IP
# ---------------------------------------------------------
RATE_LIMIT_WINDOW = 600.0  # 10 minutes
MAX_REQUESTS_PER_WINDOW = 8
_ip_history: dict[str, list[float]] = {}
_ip_lock = threading.Lock()


def check_rate_limit(client_ip: str) -> bool:
    now = time.time()
    with _ip_lock:
        timestamps = _ip_history.get(client_ip, [])
        valid_timestamps = [t for t in timestamps if now - t < RATE_LIMIT_WINDOW]
        if len(valid_timestamps) >= MAX_REQUESTS_PER_WINDOW:
            _ip_history[client_ip] = valid_timestamps
            return False
        valid_timestamps.append(now)
        _ip_history[client_ip] = valid_timestamps
        return True


def reset_rate_limits():
    """Helper for testing."""
    with _ip_lock:
        _ip_history.clear()


# ---------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------
class AskRequest(BaseModel):
    question: str
    session_id: Optional[str] = None


# ---------------------------------------------------------
# Sensitive file blacklist
# ---------------------------------------------------------
FORBIDDEN_FILE_PATTERNS = [
    re.compile(r"^\.env(?:\..+)?$", re.IGNORECASE),
    re.compile(r"^.*\.key$", re.IGNORECASE),
    re.compile(r"^.*\.pem$", re.IGNORECASE),
]


def is_forbidden_file(filename: str) -> bool:
    for pat in FORBIDDEN_FILE_PATTERNS:
        if pat.match(filename):
            return True
    return False


# ---------------------------------------------------------
# 1. Health Endpoint
# ---------------------------------------------------------
@app.get("/api/health")
def get_health():
    return {"ok": True}


# ---------------------------------------------------------
# 2. Project Overview & File List Endpoint
# ---------------------------------------------------------
@app.get("/api/project")
def get_project():
    root = get_project_root()
    commit = os.getenv("TARGET_COMMIT")
    if not commit:
        try:
            res = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if res.returncode == 0 and res.stdout.strip():
                commit = res.stdout.strip()
            else:
                commit = None
        except Exception:
            commit = None

    file_entries = []
    ignored_dirs = {".git", ".venv", "__pycache__", ".pytest_cache", "node_modules", "eval_runs"}

    for p in root.rglob("*"):
        if p.is_file():
            # Check ignored directories in parents
            rel_parts = p.relative_to(root).parts
            if any(part in ignored_dirs for part in rel_parts):
                continue
            if is_forbidden_file(p.name):
                continue

            rel_str = str(p.relative_to(root)).replace("\\", "/")
            suffix = p.suffix.lower()

            if suffix == ".py":
                kind = "py"
            elif suffix == ".md":
                kind = "md"
            elif suffix == ".txt" and not rel_str.startswith("data/"):
                kind = "txt"
            else:
                kind = "data"

            lines_count = 0
            try:
                content = p.read_text(encoding="utf-8")
                lines_count = len(content.splitlines())
            except Exception:
                try:
                    lines_count = len(p.read_bytes().decode("utf-8", errors="replace").splitlines())
                except Exception:
                    lines_count = 0

            file_entries.append({
                "path": rel_str,
                "lines": lines_count,
                "kind": kind,
            })

    # Sort files: py first, then alphabetical
    file_entries.sort(key=lambda x: (0 if x["kind"] == "py" else 1, x["path"]))

    total_py_lines = sum(f["lines"] for f in file_entries if f["kind"] == "py")

    return {
        "name": root.name,
        "commit": commit,
        "files": file_entries,
        "total_py_lines": total_py_lines,
    }


# ---------------------------------------------------------
# 3. File Content Endpoint
# ---------------------------------------------------------
@app.get("/api/file")
def get_file(path: str = Query(..., description="Relative path to file inside project root")):
    if not path or not path.strip():
        raise HTTPException(status_code=400, detail="Path cannot be empty.")

    # Reject traversal or absolute path strings immediately
    if ".." in path or path.startswith("/") or path.startswith("\\") or (len(path) > 1 and path[1] == ":"):
        raise HTTPException(status_code=400, detail="Parent traversal or absolute paths are forbidden.")

    # Check forbidden filenames
    p_name = Path(path).name
    if is_forbidden_file(p_name):
        raise HTTPException(status_code=403, detail="Access to sensitive key or environment files is forbidden.")

    root = get_project_root()
    try:
        resolved = safe_resolve(root, path)
    except PathSecurityError as e:
        raise HTTPException(status_code=400, detail=f"Path security violation: {e}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid path: {e}")

    if not resolved.exists() or resolved.is_dir():
        raise HTTPException(status_code=404, detail="File not found.")

    # Check size limit: max 300 KB
    size_bytes = resolved.stat().st_size
    if size_bytes > 300 * 1024:
        raise HTTPException(status_code=413, detail=f"File exceeds 300 KB size limit ({size_bytes} bytes).")

    try:
        content = resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = resolved.read_bytes().decode("utf-8", errors="replace")

    masked_content, _ = mask_secrets(content)
    rel_path = str(resolved.relative_to(root.resolve())).replace("\\", "/")

    return {
        "path": rel_path,
        "lines": masked_content.splitlines(),
    }


# ---------------------------------------------------------
# 4. AST File Outline Endpoint
# ---------------------------------------------------------
def parse_ast_outline(path: str) -> list[dict[str, Any]]:
    root = get_project_root()
    resolved = safe_resolve(root, path)
    if not resolved.exists() or resolved.is_dir():
        raise HTTPException(status_code=404, detail=f"File '{path}' not found.")
    if resolved.suffix != ".py":
        raise HTTPException(status_code=400, detail=f"Only Python (.py) files can be outlined.")

    try:
        content = resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = resolved.read_bytes().decode("utf-8", errors="replace")

    try:
        tree = ast.parse(content, filename=path)
    except SyntaxError as e:
        raise HTTPException(status_code=400, detail=f"Syntax error parsing Python file: {e}")

    items: list[dict[str, Any]] = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            c_doc = (ast.get_docstring(node) or "").strip()
            c_doc_first = c_doc.splitlines()[0] if c_doc else ""
            c_start = node.decorator_list[0].lineno if node.decorator_list else node.lineno
            c_end = getattr(node, "end_lineno", node.lineno)
            bases_str = ", ".join(ast.unparse(b) for b in node.bases)

            items.append({
                "name": node.name,
                "kind": "class",
                "params": bases_str,
                "start": c_start,
                "end": c_end,
                "doc": c_doc_first,
            })

            for m in node.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    m_doc = (ast.get_docstring(m) or "").strip()
                    m_doc_first = m_doc.splitlines()[0] if m_doc else ""
                    m_start = m.decorator_list[0].lineno if m.decorator_list else m.lineno
                    m_end = getattr(m, "end_lineno", m.lineno)
                    m_params = ast.unparse(m.args)
                    items.append({
                        "name": f"{node.name}.{m.name}",
                        "kind": "method",
                        "params": m_params,
                        "start": m_start,
                        "end": m_end,
                        "doc": m_doc_first,
                    })

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            f_doc = (ast.get_docstring(node) or "").strip()
            f_doc_first = f_doc.splitlines()[0] if f_doc else ""
            f_start = node.decorator_list[0].lineno if node.decorator_list else node.lineno
            f_end = getattr(node, "end_lineno", node.lineno)
            f_params = ast.unparse(node.args)
            items.append({
                "name": node.name,
                "kind": "function",
                "params": f_params,
                "start": f_start,
                "end": f_end,
                "doc": f_doc_first,
            })

    return items


@app.get("/api/outline")
def get_outline(path: str = Query(..., description="Relative path to Python file")):
    if not path or not path.strip():
        raise HTTPException(status_code=400, detail="Path cannot be empty.")
    if ".." in path or path.startswith("/") or path.startswith("\\"):
        raise HTTPException(status_code=400, detail="Parent traversal or absolute paths are forbidden.")

    try:
        items = parse_ast_outline(path)
        return {
            "path": path,
            "items": items,
        }
    except HTTPException:
        raise
    except PathSecurityError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate outline: {e}")


# ---------------------------------------------------------
# 5. AST Import Graph Endpoint
# ---------------------------------------------------------
@app.get("/api/graph")
def get_graph():
    root = get_project_root()
    scan_res = scan_python_files(root)

    nodes = []
    for f in sorted(scan_res.files):
        p = root / f
        lines_count = 0
        try:
            lines_count = len(p.read_text(encoding="utf-8").splitlines())
        except Exception:
            try:
                lines_count = len(p.read_bytes().decode("utf-8", errors="replace").splitlines())
            except Exception:
                lines_count = 0
        nodes.append({"id": f, "lines": lines_count})

    edges = []

    internal_mod_to_file: dict[str, str] = {}
    for f in scan_res.files:
        stem = Path(f).stem
        internal_mod_to_file[stem] = f
        rel_mod = f.replace("/", ".").replace("\\", ".")
        if rel_mod.endswith(".py"):
            rel_mod = rel_mod[:-3]
        internal_mod_to_file[rel_mod] = f

    for src_file in scan_res.files:
        full_path = root / src_file
        try:
            content = full_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = full_path.read_bytes().decode("utf-8", errors="replace")

        try:
            tree = ast.parse(content, filename=src_file)
        except SyntaxError:
            continue

        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_name = alias.name.split(".")[0]
                    target_file = internal_mod_to_file.get(alias.name) or internal_mod_to_file.get(top_name)
                    if target_file and target_file != src_file:
                        edges.append({
                            "from": src_file,
                            "to": target_file,
                            "line": node.lineno,
                            "symbols": [alias.name],
                        })
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                top_name = mod.split(".")[0] if mod else ""
                target_file = internal_mod_to_file.get(mod) or internal_mod_to_file.get(top_name)
                if target_file and target_file != src_file:
                    symbols = [a.name for a in node.names]
                    edges.append({
                        "from": src_file,
                        "to": target_file,
                        "line": node.lineno,
                        "symbols": symbols,
                    })

    return {
        "nodes": nodes,
        "edges": edges,
    }


# ---------------------------------------------------------
# 6. Structured Overview Endpoint
# ---------------------------------------------------------
@app.get("/api/overview")
def get_overview():
    root = get_project_root()
    scan_res = scan_python_files(root)

    entry_candidates_both = []
    entry_candidates_main_guard = []
    cli_flags: list[dict[str, Any]] = []

    for rel_path in scan_res.files:
        p = root / rel_path
        try:
            content = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = p.read_bytes().decode("utf-8", errors="replace")
        try:
            tree = ast.parse(content, filename=rel_path)
        except SyntaxError:
            continue

        has_main_guard = False
        has_argparse = False

        for node in tree.body:
            if isinstance(node, ast.If):
                test = node.test
                if isinstance(test, ast.Compare):
                    left = test.left
                    if isinstance(left, ast.Name) and left.id == "__name__":
                        for comp in test.comparators:
                            if isinstance(comp, ast.Constant) and comp.value == "__main__":
                                has_main_guard = True
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "argparse":
                        has_argparse = True
            elif isinstance(node, ast.ImportFrom) and node.module == "argparse":
                has_argparse = True

        if has_main_guard:
            entry_candidates_main_guard.append(rel_path)

        for subnode in ast.walk(tree):
            if isinstance(subnode, ast.Call):
                func = subnode.func
                if isinstance(func, ast.Attribute) and func.attr == "add_argument":
                    has_argparse = True
                    flag_args = []
                    for arg in subnode.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            flag_args.append(arg.value)
                    help_text = ""
                    for kw in subnode.keywords:
                        if kw.arg == "help" and isinstance(kw.value, ast.Constant):
                            help_text = str(kw.value.value)
                    if flag_args:
                        cli_flags.append({
                            "file": rel_path,
                            "line": subnode.lineno,
                            "flags": flag_args,
                            "help": help_text,
                        })

        if has_main_guard and has_argparse:
            entry_candidates_both.append(rel_path)

    chosen_entry = "main.py" if "main.py" in entry_candidates_both else (entry_candidates_both[0] if entry_candidates_both else ("main.py" if "main.py" in entry_candidates_main_guard else (entry_candidates_main_guard[0] if entry_candidates_main_guard else None)))
    also_runnable = [ep for ep in entry_candidates_main_guard if ep != chosen_entry]

    # Extract stages
    stages: list[str] = []
    if chosen_entry and (root / chosen_entry).exists():
        try:
            m_text = (root / chosen_entry).read_text(encoding="utf-8")
        except Exception:
            m_text = (root / chosen_entry).read_bytes().decode("utf-8", errors="replace")
        for line in m_text.splitlines():
            if "[Stage " in line:
                for part in line.split("[Stage "):
                    if "]" in part:
                        st_num, rest = part.split("]", 1)
                        st_name = rest.split("-->")[0].split("\\n")[0].split('")')[0].split("')")[0].strip()
                        if st_num.strip().isdigit() and st_name:
                            stages.append(f"Stage {st_num.strip()}: {st_name}")

    # Build reading order
    reading_order = []
    if "config.py" in scan_res.files:
        reading_order.append("config.py")
    for f in scan_res.files:
        if f not in reading_order and f != chosen_entry:
            reading_order.append(f)
    if chosen_entry and chosen_entry not in reading_order and chosen_entry in scan_res.files:
        reading_order.append(chosen_entry)

    # Data files
    data_dir = root / "data"
    data_files: list[str] = []
    if data_dir.exists() and data_dir.is_dir():
        for p in sorted(data_dir.rglob("*")):
            if p.is_file():
                data_files.append(p.relative_to(root).as_posix())

    # Dependency files
    dep_candidates = ["requirements.txt", "requirements-dev.txt", "pyproject.toml", "setup.cfg", "setup.py", "Pipfile"]
    dependency_files = [c for c in dep_candidates if (root / c).is_file()]

    # Documentation files
    docs = [p.relative_to(root).as_posix() for p in sorted(root.glob("*.md")) if p.is_file()]

    # Commands
    target_flags = [fl for fl in cli_flags if fl["file"] == chosen_entry] if chosen_entry else cli_flags
    commands: list[str] = []
    if chosen_entry:
        for fl in target_flags:
            long_flag = next((f for f in fl["flags"] if f.startswith("--")), fl["flags"][0])
            if any(q in long_flag.lower() for q in ["query", "question"]) or (fl.get("help") and "question" in fl["help"].lower()):
                cmd = f'python {chosen_entry} {long_flag} "your question"'
            else:
                cmd = f"python {chosen_entry} {long_flag}"
            if cmd not in commands:
                commands.append(cmd)
    if not commands and chosen_entry:
        commands.append(f"python {chosen_entry}")

    reading_order_list = []
    for f in reading_order:
        doc_str = ""
        full_f = root / f
        try:
            f_content = full_f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            f_content = full_f.read_bytes().decode("utf-8", errors="replace")
        try:
            f_tree = ast.parse(f_content, filename=f)
            mod_doc = ast.get_docstring(f_tree)
            if mod_doc:
                first_non_empty = next((l.strip() for l in mod_doc.splitlines() if l.strip()), "")
                if first_non_empty:
                    base_name = Path(f).name
                    for prefix_cand in (f"{f} — ", f"{base_name} — ", f"{f} - ", f"{base_name} - ", f"{f} – ", f"{base_name} – "):
                        if first_non_empty.startswith(prefix_cand):
                            first_non_empty = first_non_empty[len(prefix_cand):].strip()
                            break
                    doc_str = first_non_empty[:120]
        except Exception:
            pass
        reading_order_list.append({"path": f, "doc": doc_str})

    return {
        "entry_point": chosen_entry,
        "also_runnable": also_runnable,
        "commands": commands,
        "stages": stages,
        "reading_order": reading_order_list,
        "data_files": data_files,
        "dependency_files": dependency_files,
        "docs": docs,
    }


# ---------------------------------------------------------
# 7. Ask Endpoint (Server-Sent Events)
# ---------------------------------------------------------
AGENT_DISPLAY_NAMES = {
    "root_agent": "Boss",
    "boss": "Boss",
    "code_searcher": "Code Searcher",
    "code_explainer": "Code Explainer",
    "architecture_mapper": "Architecture Mapper",
    "onboarding_guide": "Onboarding Guide",
}


def extract_citations(text: str, root: Path) -> list[dict[str, Any]]:
    """
    Regex for file.py:start-end or file.py:line.
    Keeps only citations whose file exists inside target root and whose line numbers are within file bounds.
    """
    pattern = re.compile(r"\b([a-zA-Z0-9_\-./\\]+\.py):(\d+)(?:-(\d+))?\b")
    seen = set()
    valid_citations = []

    for match in pattern.finditer(text):
        rel_path = match.group(1).replace("\\", "/")
        start = int(match.group(2))
        end = int(match.group(3)) if match.group(3) else start
        if start > end:
            start, end = end, start

        key = (rel_path, start, end)
        if key in seen:
            continue
        seen.add(key)

        try:
            resolved = safe_resolve(root, rel_path)
            if resolved.is_file():
                try:
                    num_lines = len(resolved.read_text(encoding="utf-8").splitlines())
                except UnicodeDecodeError:
                    num_lines = len(resolved.read_bytes().decode("utf-8", errors="replace").splitlines())
                if 1 <= start <= num_lines and 1 <= end <= num_lines:
                    valid_citations.append({"path": rel_path, "start": start, "end": end})
        except Exception:
            continue

    return valid_citations


_session_service = InMemorySessionService()


def create_adk_runner():
    """Factory to create an ADK Runner instance."""
    return Runner(
        agent=root_agent,
        session_service=_session_service,
        app_name="code_helper",
        auto_create_session=True,
    )


@app.post("/api/ask")
async def ask_question(request: Request, body: AskRequest):
    # 1. Rate Limit
    client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if not client_ip:
        client_ip = request.client.host if request.client else "127.0.0.1"

    if not check_rate_limit(client_ip):
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many case requests. Please wait a few minutes before opening a new case.", "code": 429},
        )

    # 2. Demo Code Header
    demo_code_env = os.getenv("DEMO_CODE")
    if demo_code_env:
        header_code = request.headers.get("x-demo-code", "").strip()
        if header_code != demo_code_env.strip():
            return JSONResponse(
                status_code=403,
                content={"detail": "Invalid or missing X-Demo-Code header."},
            )

    # 3. Clean and validate question
    raw_q = body.question or ""
    # Strip control characters (except newline and tab)
    cleaned_q = "".join(ch for ch in raw_q if ch in ("\n", "\t") or (ch.isprintable()))
    cleaned_q = cleaned_q.strip()

    if not cleaned_q:
        raise HTTPException(status_code=400, detail="Question cannot be empty or contain only control characters.")
    if len(cleaned_q) > 500:
        raise HTTPException(status_code=400, detail="Question exceeds maximum allowed length of 500 characters.")

    turn_id = str(uuid.uuid4())
    session_id = body.session_id or f"session_{int(time.time() * 1000)}"
    root = get_project_root()

    async def event_generator():
        import json
        t_start = time.time()
        final_answer = ""
        routed_agents = set()
        current_invocation_id = None
        captured_struct = None

        try:
            # Emit session event first
            yield {
                "event": "session",
                "data": json.dumps({"turn_id": turn_id, "session_id": session_id}),
            }

            runner = create_adk_runner()
            last_author = "Boss"

            async def get_events():
                if hasattr(runner, "run_async"):
                    async for ev in runner.run_async(
                        user_id="user",
                        session_id=session_id,
                        new_message=types.Content(parts=[types.Part.from_text(text=cleaned_q)]),
                        run_config=RunConfig(max_llm_calls=8),
                    ):
                        yield ev
                else:
                    for ev in runner.run(
                        user_id="user",
                        session_id=session_id,
                        new_message=types.Content(parts=[types.Part.from_text(text=cleaned_q)]),
                        run_config=RunConfig(max_llm_calls=8),
                    ):
                        yield ev

            # Stream events directly from runner
            async for ev in get_events():
                inv_id = getattr(ev, "invocation_id", None)
                if current_invocation_id is None and inv_id:
                    current_invocation_id = inv_id
                if current_invocation_id and inv_id and inv_id != current_invocation_id:
                    # Skip events of a previous or different invocation
                    continue

                if hasattr(ev, "actions") and ev.actions and ev.actions.state_delta:
                    if "temp:final_struct" in ev.actions.state_delta:
                        captured_struct = ev.actions.state_delta["temp:final_struct"]

                raw_author = getattr(ev, "author", "") or ""
                display_author = AGENT_DISPLAY_NAMES.get(raw_author, raw_author or "Boss")
                if display_author != "user":
                    last_author = display_author

                # Emit routed event once per agent
                if raw_author and raw_author != "user" and raw_author not in routed_agents:
                    routed_agents.add(raw_author)
                    yield {
                        "event": "routed",
                        "data": json.dumps({"turn_id": turn_id, "agent": display_author}),
                    }

                # Emit tool calls
                fc_list = ev.get_function_calls() if hasattr(ev, "get_function_calls") else []
                for fc in fc_list:
                    fc_name = getattr(fc, "name", "")
                    raw_args = getattr(fc, "args", {}) or {}
                    safe_args = {}
                    if isinstance(raw_args, dict):
                        for k, v in raw_args.items():
                            if not any(sec in k.lower() for sec in ["key", "secret", "password", "token"]):
                                safe_args[k] = str(v)[:100]
                    yield {
                        "event": "tool_call",
                        "data": json.dumps({"turn_id": turn_id, "agent": display_author, "tool": fc_name, "args": safe_args}),
                    }

                # Emit tool done
                fr_list = ev.get_function_responses() if hasattr(ev, "get_function_responses") else []
                for fr in fr_list:
                    fr_name = getattr(fr, "name", "")
                    yield {
                        "event": "tool_done",
                        "data": json.dumps({"turn_id": turn_id, "agent": display_author, "tool": fr_name}),
                    }

                # Handle text output / streaming chunks
                has_text = False
                if hasattr(ev, "content") and ev.content and hasattr(ev.content, "parts"):
                    for p in ev.content.parts:
                        if hasattr(p, "text") and p.text:
                            final_answer += p.text
                            has_text = True

                if has_text and final_answer.strip():
                    clean_text = final_answer
                    if "could not find" in clean_text.lower():
                        clean_text = re.sub(r"^\s*Verified from code:\s*", "", clean_text, flags=re.IGNORECASE).strip()
                    yield {
                        "event": "answer",
                        "data": json.dumps({"turn_id": turn_id, "agent": last_author, "text": clean_text}),
                    }

            # Final answer check
            if final_answer.strip():
                clean_text = final_answer
                if "could not find" in clean_text.lower():
                    clean_text = re.sub(r"^\s*Verified from code:\s*", "", clean_text, flags=re.IGNORECASE).strip()
                yield {
                    "event": "answer",
                    "data": json.dumps({"turn_id": turn_id, "agent": last_author, "text": clean_text}),
                }

            # Citations
            citations = extract_citations(final_answer, root)

            # Determine verdict
            from code_helper.tools._final_struct_registry import get_and_clear_final_struct
            sess_obj = await _session_service.get_session(app_name="code_helper", user_id="user", session_id=session_id)
            if not captured_struct and sess_obj and hasattr(sess_obj, "state") and sess_obj.state:
                captured_struct = sess_obj.state.pop("temp:final_struct", None)
                sess_obj.state.pop("temp:final_text", None)
            if not captured_struct:
                captured_struct = get_and_clear_final_struct(session_id)

            if captured_struct and isinstance(captured_struct, dict) and "kind" in captured_struct:
                verdict_kind = captured_struct["kind"]
                yield {
                    "event": "verdict",
                    "data": json.dumps({
                        "turn_id": turn_id,
                        "agent": last_author,
                        "kind": verdict_kind,
                        "data": captured_struct,
                    }),
                }
            elif "could not find" in final_answer.lower() or "not found" in final_answer.lower():
                searches_tried = []
                searches_match = re.search(r"searches tried:\s*(.*)", final_answer, flags=re.IGNORECASE | re.DOTALL)
                clean_msg = final_answer
                if searches_match:
                    clean_msg = final_answer[:searches_match.start()].strip()
                    raw_searches = searches_match.group(1).strip()
                    searches_tried = [s.strip(" -•*") for s in raw_searches.splitlines() if s.strip()]
                clean_msg = re.sub(r"^\s*Verified from code:\s*", "", clean_msg, flags=re.IGNORECASE).strip()
                yield {
                    "event": "verdict",
                    "data": json.dumps({
                        "turn_id": turn_id,
                        "agent": last_author,
                        "kind": "not_found",
                        "data": {
                            "message": clean_msg,
                            "searches_tried": searches_tried,
                        },
                    }),
                }
            else:
                sources_list = []
                clean_text = final_answer
                src_match = re.search(r"\n*Sources(?:\s*\(from tool results\))?:\s*(.*)", final_answer, flags=re.IGNORECASE | re.DOTALL)
                if src_match:
                    clean_text = final_answer[:src_match.start()].strip()
                    raw_sources = src_match.group(1).strip()
                    sources_list = [s.strip(" -•*") for s in raw_sources.splitlines() if s.strip()]
                clean_text = re.sub(r"^\s*Verified from code:\s*", "", clean_text, flags=re.IGNORECASE).strip()
                yield {
                    "event": "verdict",
                    "data": json.dumps({
                        "turn_id": turn_id,
                        "agent": last_author,
                        "kind": "text",
                        "data": {
                            "text": clean_text,
                            "citations": citations,
                            "sources": sources_list,
                        },
                        "text": clean_text,
                        "citations": citations,
                        "sources": sources_list,
                    }),
                }

            yield {
                "event": "citations",
                "data": json.dumps({"turn_id": turn_id, "items": citations}),
            }

            # Done
            elapsed = round(time.time() - t_start, 2)
            yield {
                "event": "done",
                "data": json.dumps({"turn_id": turn_id, "seconds": elapsed}),
            }

        except Exception as ex:
            print("Error in ask_question event_generator:", ex)
            yield {
                "event": "error",
                "data": json.dumps({"turn_id": turn_id, "message": "The AI service is slow or busy. Try again.", "code": "busy"}),
            }

    return EventSourceResponse(event_generator())
