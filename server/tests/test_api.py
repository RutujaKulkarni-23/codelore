import json
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from server.app import app, reset_rate_limits


@pytest.fixture
def client():
    reset_rate_limits()
    return TestClient(app)


# ---------------------------------------------------------
# Health tests
# ---------------------------------------------------------
def test_health_exact_shape(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert set(data.keys()) == {"ok"}
    assert data["ok"] is True


# ---------------------------------------------------------
# Project Overview tests
# ---------------------------------------------------------
def test_project_exact_shape(client):
    res = client.get("/api/project")
    assert res.status_code == 200
    data = res.json()
    assert set(data.keys()) == {"name", "commit", "files", "total_py_lines"}
    assert isinstance(data["name"], str)
    assert data["commit"] is None or isinstance(data["commit"], str)
    assert isinstance(data["files"], list)
    assert isinstance(data["total_py_lines"], int)
    assert data["total_py_lines"] > 0

    first_file = data["files"][0]
    assert set(first_file.keys()) == {"path", "lines", "kind"}
    assert first_file["kind"] in ("py", "md", "txt", "data")


# ---------------------------------------------------------
# File Content & Security tests
# ---------------------------------------------------------
def test_file_exact_shape_and_security(client):
    # Valid file
    res = client.get("/api/file?path=vector_store.py")
    assert res.status_code == 200
    data = res.json()
    assert set(data.keys()) == {"path", "lines"}
    assert data["path"] == "vector_store.py"
    assert isinstance(data["lines"], list)
    assert len(data["lines"]) >= 200

    # Parent traversal rejects with 400
    res_traversal = client.get("/api/file?path=../secret.py")
    assert res_traversal.status_code == 400

    # Absolute path rejects with 400
    res_abs = client.get("/api/file?path=/etc/passwd")
    assert res_abs.status_code == 400

    # .env rejects
    res_env = client.get("/api/file?path=.env")
    assert res_env.status_code in (400, 403)

    res_env_local = client.get("/api/file?path=.env.local")
    assert res_env_local.status_code in (400, 403)

    # Missing file returns 404
    res_missing = client.get("/api/file?path=nonexistent_file.py")
    assert res_missing.status_code == 404


# ---------------------------------------------------------
# Outline tests
# ---------------------------------------------------------
def test_outline_exact_shape_and_query_pipeline_ranges(client):
    res = client.get("/api/outline?path=query_pipeline.py")
    assert res.status_code == 200
    data = res.json()
    assert set(data.keys()) == {"path", "items"}
    assert data["path"] == "query_pipeline.py"
    items = data["items"]

    # Verify query_pipeline.py has 6 functions with exact ranges
    assert len(items) == 6
    expected_ranges = [
        ("embed_query", 27, 86),
        ("retrieve_top_k", 89, 126),
        ("build_prompt_with_context", 129, 176),
        ("generate_answer", 179, 240),
        ("generate_answer_without_rag", 243, 309),
        ("run_query_pipeline", 312, 358),
    ]

    for (name, start, end), item in zip(expected_ranges, items):
        assert item["name"] == name
        assert item["kind"] == "function"
        assert item["start"] == start
        assert item["end"] == end
        assert set(item.keys()) == {"name", "kind", "params", "start", "end", "doc"}


# ---------------------------------------------------------
# Graph tests
# ---------------------------------------------------------
def test_graph_exact_shape_and_edge(client):
    res = client.get("/api/graph")
    assert res.status_code == 200
    data = res.json()
    assert set(data.keys()) == {"nodes", "edges"}

    # Nodes
    for n in data["nodes"]:
        assert set(n.keys()) == {"id", "lines"}
        assert isinstance(n["lines"], int)
        assert n["lines"] > 0

    # Edge: indexer.py -> vector_store.py line 27 with symbol upsert_to_vector_db
    edge = next(
        (e for e in data["edges"] if e["from"] == "indexer.py" and e["to"] == "vector_store.py" and e["line"] == 27),
        None,
    )
    assert edge is not None, f"Expected edge indexer.py -> vector_store.py at line 27 not found: {data['edges']}"
    assert "upsert_to_vector_db" in edge["symbols"]


# ---------------------------------------------------------
# Overview tests
# ---------------------------------------------------------
def test_overview_exact_shape(client):
    res = client.get("/api/overview")
    assert res.status_code == 200
    data = res.json()
    assert set(data.keys()) == {
        "entry_point",
        "also_runnable",
        "commands",
        "stages",
        "reading_order",
        "data_files",
        "dependency_files",
        "docs",
    }
    assert data["entry_point"] == "main.py"
    assert isinstance(data["also_runnable"], list)
    assert isinstance(data["commands"], list)
    assert len(data["commands"]) == 4
    assert isinstance(data["stages"], list)
    assert len(data["stages"]) >= 8

    # Reading order has {"path", "doc"}
    for item in data["reading_order"]:
        assert set(item.keys()) == {"path", "doc"}

    assert isinstance(data["data_files"], list)
    assert isinstance(data["dependency_files"], list)
    assert isinstance(data["docs"], list)


# ---------------------------------------------------------
# Fake runner & SSE Ask stream test
# ---------------------------------------------------------
class FakeRunner:
    def __init__(self, events):
        self.events = events

    def run(self, *args, **kwargs):
        for ev in self.events:
            yield ev


def test_ask_stream_emits_session_routed_answer_done_in_order(client):
    ev1 = SimpleNamespace(
        author="code_searcher",
        get_function_calls=lambda: [],
        get_function_responses=lambda: [],
        is_final_response=lambda: False,
        content=None,
    )
    ev2 = SimpleNamespace(
        author="code_searcher",
        get_function_calls=lambda: [SimpleNamespace(name="find_symbol", args={"symbol": "embed_query"})],
        get_function_responses=lambda: [],
        is_final_response=lambda: False,
        content=None,
    )
    ev3 = SimpleNamespace(
        author="code_searcher",
        get_function_calls=lambda: [],
        get_function_responses=lambda: [SimpleNamespace(name="find_symbol", response="ok")],
        is_final_response=lambda: False,
        content=None,
    )
    ev4 = SimpleNamespace(
        author="code_searcher",
        get_function_calls=lambda: [],
        get_function_responses=lambda: [],
        is_final_response=lambda: True,
        content=SimpleNamespace(
            parts=[
                SimpleNamespace(
                    text="Verified from code: Found embed_query at query_pipeline.py:27-86."
                )
            ]
        ),
    )

    fake_runner = FakeRunner([ev1, ev2, ev3, ev4])

    with patch("server.app.create_adk_runner", return_value=fake_runner):
        res = client.post("/api/ask", json={"question": "Where is embed_query defined?", "session_id": "test_sess_1"})
        assert res.status_code == 200

        text = res.text
        events = []
        current_event = None
        for line in text.splitlines():
            if line.startswith("event: "):
                current_event = line.replace("event: ", "").strip()
            elif line.startswith("data: ") and current_event:
                data_val = json.loads(line.replace("data: ", "").strip())
                events.append((current_event, data_val))
                current_event = None

        event_names = [e[0] for e in events]

        # Verify session, routed, answer, done are emitted in that relative order
        assert "session" in event_names
        assert "routed" in event_names
        assert "answer" in event_names
        assert "done" in event_names

        idx_session = event_names.index("session")
        idx_routed = event_names.index("routed")
        idx_answer = event_names.index("answer")
        idx_done = event_names.index("done")

        assert idx_session < idx_routed < idx_answer < idx_done

        # Verify session id matches
        session_ev = next(e[1] for e in events if e[0] == "session")
        assert session_ev["session_id"] == "test_sess_1"


# ---------------------------------------------------------
# Rate limiting tests
# ---------------------------------------------------------
def test_rate_limit_returns_429_on_9th_call(client):
    reset_rate_limits()

    fake_runner = FakeRunner([
        SimpleNamespace(
            author="code_searcher",
            get_function_calls=lambda: [],
            get_function_responses=lambda: [],
            is_final_response=lambda: True,
            content=SimpleNamespace(parts=[SimpleNamespace(text="Quick answer")]),
        )
    ])

    with patch("server.app.create_adk_runner", return_value=fake_runner):
        for i in range(8):
            res = client.post("/api/ask", json={"question": f"Question {i+1}?"})
            assert res.status_code == 200, f"Request {i+1} failed with {res.status_code}"

        # 9th call must be blocked with 429
        res_9 = client.post("/api/ask", json={"question": "Question 9?"})
        assert res_9.status_code == 429
        assert "Too many case requests" in res_9.json()["detail"]
