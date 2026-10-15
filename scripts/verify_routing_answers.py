"""
Automated verification module for CodeLore routing answers.
Strict AST-backed verification:
(a) Citation validity: path:start-end references a real target file.
    The line range MUST equal the full range of a real top-level function, class,
    method (with decorators), import statement, or module-level assignment.
    Sub-ranges inside a function fail as 'unverifiable sub-range'.
(b) Outline completeness: For outline/listing questions, all top-level functions
    and classes in the target file must appear in the answer.
(c) Tool grounding: checks whether cited files appeared in tool outputs.
(d) Not-found handling: verifies answers to not-found questions contain 'could not find'.
(e) Off-topic handling: verifies off-topic questions contain no invented code citations or target files.
"""
import ast
import re
from pathlib import Path
from typing import Dict, List, Any, Tuple


def get_ast_ranges(file_path: Path) -> Tuple[Dict[Tuple[int, int], str], List[str]]:
    """
    Extracts all verifiable line ranges from a Python source file using AST:
    - Full function definition ranges (including decorators)
    - Full class definition ranges (including decorators) and their methods
    - Import line ranges
    - Module-level assignment ranges
    Also returns a list of top-level function and class names.
    """
    if not file_path.exists():
        return {}, []
    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = file_path.read_text(encoding="latin-1")
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return {}, []

    valid_ranges = {}
    top_level_definitions = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = node.decorator_list[0].lineno if node.decorator_list else node.lineno
            end = node.end_lineno
            valid_ranges[(start, end)] = f"function:{node.name}"
            top_level_definitions.append(node.name)
        elif isinstance(node, ast.ClassDef):
            start = node.decorator_list[0].lineno if node.decorator_list else node.lineno
            end = node.end_lineno
            valid_ranges[(start, end)] = f"class:{node.name}"
            top_level_definitions.append(node.name)
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    m_start = item.decorator_list[0].lineno if item.decorator_list else item.lineno
                    m_end = item.end_lineno
                    valid_ranges[(m_start, m_end)] = f"method:{node.name}.{item.name}"
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            valid_ranges[(node.lineno, node.end_lineno)] = "import"
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            valid_ranges[(node.lineno, node.end_lineno)] = "assignment"

    return valid_ranges, top_level_definitions


def verify_routing_answer(
    question_id: str,
    question_text: str,
    category: str,
    answer_text: str,
    tool_outputs: List[str] = None,
    target_dir: Path = Path("D:/CodeLore/targets/Naive_RAG"),
) -> Dict[str, Any]:
    if tool_outputs is None:
        tool_outputs = []

    results = {
        "id": question_id,
        "valid_citations": [],
        "invalid_citations": [],
        "unsupported_files": [],
        "missing_outline_items": [],
        "not_found_valid": None,
        "off_topic_clean": None,
        "errors": [],
    }

    target_ast_cache = {}
    if target_dir.exists():
        for py_file in target_dir.glob("*.py"):
            target_ast_cache[py_file.name] = get_ast_ranges(py_file)

    # Match citations of form filename.py:start-end
    citations = re.findall(r"\b([a-zA-Z0-9_\-]+\.py):(\d+)(?:-(\d+))?\b", answer_text)

    is_not_found = "not found" in category.lower() or "not_found" in category.lower()
    is_off_topic = "off-topic" in category.lower() or "off_topic" in category.lower()

    if not citations and not is_not_found and not is_off_topic:
        results["errors"].append("No code citations found in answer")

    for match in citations:
        file_name, start_s, end_s = match
        start_line = int(start_s)
        end_line = int(end_s) if end_s else start_line
        citation_str = f"{file_name}:{start_line}-{end_line}"

        if file_name not in target_ast_cache:
            results["invalid_citations"].append(f"{citation_str} (file '{file_name}' does not exist in target)")
            results["errors"].append(f"Nonexistent file cited: {file_name}")
            continue

        valid_ranges, defs = target_ast_cache[file_name]
        if (start_line, end_line) in valid_ranges:
            results["valid_citations"].append(citation_str)
        else:
            # Check if citation is a sub-range inside an AST entity
            sub_range_match = None
            for (f_start, f_end), kind in valid_ranges.items():
                if f_start <= start_line and end_line <= f_end and (start_line != f_start or end_line != f_end):
                    sub_range_match = f"{kind} at {f_start}-{f_end}"
                    break
            if sub_range_match:
                err_msg = f"{citation_str}: unverifiable sub-range (inside {sub_range_match})"
            else:
                err_msg = f"{citation_str}: invalid range (does not match any full function, class, method, import, or assignment)"
            results["invalid_citations"].append(err_msg)
            results["errors"].append(err_msg)

    # Outline check: if question asks for outline or function/class list
    q_lower = question_text.lower()
    is_outline = "outline" in q_lower or "list functions" in q_lower or "list classes" in q_lower
    if is_outline:
        target_file_matches = [fname for fname in target_ast_cache if fname in q_lower]
        for fname in target_file_matches:
            _, expected_defs = target_ast_cache[fname]
            missing_defs = [d for d in expected_defs if d not in answer_text]
            if missing_defs:
                results["missing_outline_items"].extend([f"{fname}:{d}" for d in missing_defs])
                results["errors"].append(f"Outline missing top-level definitions in {fname}: {missing_defs}")

    # Grounding check
    all_tool_text = " ".join(tool_outputs)
    files_in_answer = set(re.findall(r"\b([a-zA-Z0-9_\-]+\.py)\b", answer_text))
    if tool_outputs:
        for f in files_in_answer:
            if f not in all_tool_text and f in target_ast_cache:
                results["unsupported_files"].append(f)
                if not is_off_topic:
                    results["errors"].append(f"File '{f}' mentioned in answer was never returned by any tool output")

    # Not-found check
    if is_not_found:
        if "could not find" in answer_text.lower():
            results["not_found_valid"] = True
        else:
            results["not_found_valid"] = False
            results["errors"].append("Not-found question answer missing 'could not find' phrase")

    # Off-topic check
    if is_off_topic:
        mentioned_target_files = files_in_answer.intersection(set(target_ast_cache.keys()))
        if results["valid_citations"] or mentioned_target_files:
            results["off_topic_clean"] = False
            results["errors"].append(f"Off-topic answer improperly cites target code facts: {mentioned_target_files}")
        else:
            results["off_topic_clean"] = True

    results["passed"] = len(results["errors"]) == 0
    return results
