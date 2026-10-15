import ast
import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Chunk:
    id: str
    path: str
    symbol: str
    kind: str  # "module", "function", "class", "method", "window"
    start_line: int  # 1-based, inclusive
    end_line: int  # 1-based, inclusive
    text: str
    content_hash: str
    chunk_config_id: str


def _generate_chunk_id(path: str, start_line: int, end_line: int, chunk_config_id: str) -> str:
    key = f"{path}:{start_line}:{end_line}:{chunk_config_id}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


def _format_chunk_text(path: str, symbol: str, start_line: int, end_line: int, body: str) -> str:
    header = f"# file: {path} | symbol: {symbol} | lines {start_line}-{end_line}"
    return f"{header}\n{body}"


def _split_lines_into_windows(
    lines: list[str],
    base_start_line: int,
    path: str,
    symbol: str,
    kind: str,
    max_chunk_lines: int,
    chunk_overlap_lines: int,
    max_chunk_chars: int,
    chunk_config_id: str,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    total_lines = len(lines)
    if total_lines == 0:
        return chunks

    step = max(1, max_chunk_lines - chunk_overlap_lines)
    idx = 0
    while idx < total_lines:
        window_lines = lines[idx: idx + max_chunk_lines]
        actual_start = base_start_line + idx
        actual_end = base_start_line + idx + len(window_lines) - 1
        raw_body = "".join(window_lines)

        # Check max_chunk_chars: if exceeded, further slice by character windows
        if len(raw_body) > max_chunk_chars and len(window_lines) > 1:
            # Bisect lines to fit character constraints
            half = len(window_lines) // 2
            sub_chunks = _split_lines_into_windows(
                lines[idx: idx + half],
                actual_start,
                path,
                symbol,
                kind,
                half,
                0,
                max_chunk_chars,
                chunk_config_id,
            )
            chunks.extend(sub_chunks)
            sub_chunks_2 = _split_lines_into_windows(
                lines[idx + half: idx + len(window_lines)],
                actual_start + half,
                path,
                symbol,
                kind,
                len(window_lines) - half,
                0,
                max_chunk_chars,
                chunk_config_id,
            )
            chunks.extend(sub_chunks_2)
            idx += step
            continue

        chunk_id = _generate_chunk_id(path, actual_start, actual_end, chunk_config_id)
        content_hash = hashlib.sha256(raw_body.encode("utf-8")).hexdigest()[:32]
        formatted_text = _format_chunk_text(path, symbol, actual_start, actual_end, raw_body)

        chunks.append(
            Chunk(
                id=chunk_id,
                path=path,
                symbol=symbol,
                kind=kind,
                start_line=actual_start,
                end_line=actual_end,
                text=formatted_text,
                content_hash=content_hash,
                chunk_config_id=chunk_config_id,
            )
        )
        idx += step

    return chunks


def _get_node_start_line(node: ast.AST) -> int:
    """Get the true start line of an AST node including any decorators."""
    if hasattr(node, "decorator_list") and node.decorator_list:
        return node.decorator_list[0].lineno
    return getattr(node, "lineno", 1)


def chunk_file_ast_hybrid(
    source_text: str,
    path: str,
    max_chunk_lines: int = 60,
    chunk_overlap_lines: int = 8,
    max_chunk_chars: int = 3000,
    chunk_config_id: str = "ast_hybrid_v1",
) -> list[Chunk]:
    """
    AST-aware hybrid chunking:
    - Top-level functions -> 1 chunk each (or windowed if oversized)
    - Classes -> 1 chunk if within limit; otherwise class header + 1 chunk per method
    - Top-level statements (imports, constants, execution blocks) -> '<module>' chunks
    - SyntaxError fallback -> window chunking across entire file
    """
    source_lines = source_text.splitlines(keepends=True)
    total_lines = len(source_lines)
    if total_lines == 0:
        return []

    try:
        tree = ast.parse(source_text, filename=path)
    except SyntaxError:
        # Fallback to line windowing
        return _split_lines_into_windows(
            lines=source_lines,
            base_start_line=1,
            path=path,
            symbol="<syntax_error_fallback>",
            kind="window",
            max_chunk_lines=max_chunk_lines,
            chunk_overlap_lines=chunk_overlap_lines,
            max_chunk_chars=max_chunk_chars,
            chunk_config_id=f"{chunk_config_id}_fallback",
        )

    chunks: list[Chunk] = []
    # Track lines consumed by functions and classes to collect remaining module-level code
    consumed_line_ranges: list[tuple[int, int]] = []

    # Identify structural units in body
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            s_line = _get_node_start_line(node)
            e_line = getattr(node, "end_lineno", s_line)
            consumed_line_ranges.append((s_line, e_line))
            unit_lines = source_lines[s_line - 1: e_line]

            if (e_line - s_line + 1) > max_chunk_lines or sum(len(l) for l in unit_lines) > max_chunk_chars:
                func_chunks = _split_lines_into_windows(
                    lines=unit_lines,
                    base_start_line=s_line,
                    path=path,
                    symbol=node.name,
                    kind="function",
                    max_chunk_lines=max_chunk_lines,
                    chunk_overlap_lines=chunk_overlap_lines,
                    max_chunk_chars=max_chunk_chars,
                    chunk_config_id=chunk_config_id,
                )
                chunks.extend(func_chunks)
            else:
                raw_body = "".join(unit_lines)
                c_id = _generate_chunk_id(path, s_line, e_line, chunk_config_id)
                c_hash = hashlib.sha256(raw_body.encode("utf-8")).hexdigest()[:32]
                text = _format_chunk_text(path, node.name, s_line, e_line, raw_body)
                chunks.append(
                    Chunk(
                        id=c_id,
                        path=path,
                        symbol=node.name,
                        kind="function",
                        start_line=s_line,
                        end_line=e_line,
                        text=text,
                        content_hash=c_hash,
                        chunk_config_id=chunk_config_id,
                    )
                )

        elif isinstance(node, ast.ClassDef):
            c_s_line = _get_node_start_line(node)
            c_e_line = getattr(node, "end_lineno", c_s_line)
            consumed_line_ranges.append((c_s_line, c_e_line))
            class_lines = source_lines[c_s_line - 1: c_e_line]

            # If class fits in limit, emit single class chunk
            if (c_e_line - c_s_line + 1) <= max_chunk_lines and sum(len(l) for l in class_lines) <= max_chunk_chars:
                raw_body = "".join(class_lines)
                c_id = _generate_chunk_id(path, c_s_line, c_e_line, chunk_config_id)
                c_hash = hashlib.sha256(raw_body.encode("utf-8")).hexdigest()[:32]
                text = _format_chunk_text(path, node.name, c_s_line, c_e_line, raw_body)
                chunks.append(
                    Chunk(
                        id=c_id,
                        path=path,
                        symbol=node.name,
                        kind="class",
                        start_line=c_s_line,
                        end_line=c_e_line,
                        text=text,
                        content_hash=c_hash,
                        chunk_config_id=chunk_config_id,
                    )
                )
            else:
                # Split class: emit class header + docstring first, then methods
                first_method_line = c_e_line
                methods = [
                    item for item in node.body
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                if methods:
                    first_method_line = _get_node_start_line(methods[0])

                header_end = min(first_method_line - 1, c_e_line)
                if header_end >= c_s_line:
                    header_lines = source_lines[c_s_line - 1: header_end]
                    raw_header = "".join(header_lines)
                    c_id = _generate_chunk_id(path, c_s_line, header_end, chunk_config_id)
                    c_hash = hashlib.sha256(raw_header.encode("utf-8")).hexdigest()[:32]
                    text = _format_chunk_text(path, f"{node.name}__header", c_s_line, header_end, raw_header)
                    chunks.append(
                        Chunk(
                            id=c_id,
                            path=path,
                            symbol=f"{node.name}.<header>",
                            kind="class",
                            start_line=c_s_line,
                            end_line=header_end,
                            text=text,
                            content_hash=c_hash,
                            chunk_config_id=chunk_config_id,
                        )
                    )

                # Process individual methods
                for m in methods:
                    m_s_line = _get_node_start_line(m)
                    m_e_line = getattr(m, "end_lineno", m_s_line)
                    m_lines = source_lines[m_s_line - 1: m_e_line]
                    m_sym = f"{node.name}.{m.name}"

                    if (m_e_line - m_s_line + 1) > max_chunk_lines or sum(len(l) for l in m_lines) > max_chunk_chars:
                        m_chunks = _split_lines_into_windows(
                            lines=m_lines,
                            base_start_line=m_s_line,
                            path=path,
                            symbol=m_sym,
                            kind="method",
                            max_chunk_lines=max_chunk_lines,
                            chunk_overlap_lines=chunk_overlap_lines,
                            max_chunk_chars=max_chunk_chars,
                            chunk_config_id=chunk_config_id,
                        )
                        chunks.extend(m_chunks)
                    else:
                        raw_body = "".join(m_lines)
                        c_id = _generate_chunk_id(path, m_s_line, m_e_line, chunk_config_id)
                        c_hash = hashlib.sha256(raw_body.encode("utf-8")).hexdigest()[:32]
                        text = _format_chunk_text(path, m_sym, m_s_line, m_e_line, raw_body)
                        chunks.append(
                            Chunk(
                                id=c_id,
                                path=path,
                                symbol=m_sym,
                                kind="method",
                                start_line=m_s_line,
                                end_line=m_e_line,
                                text=text,
                                content_hash=c_hash,
                                chunk_config_id=chunk_config_id,
                            )
                        )

    # Collect module-level segments outside function and class ranges
    consumed_line_ranges.sort(key=lambda r: r[0])
    module_segments: list[tuple[int, int]] = []
    current_cursor = 1

    for start_r, end_r in consumed_line_ranges:
        if start_r > current_cursor:
            module_segments.append((current_cursor, start_r - 1))
        current_cursor = max(current_cursor, end_r + 1)

    if current_cursor <= total_lines:
        module_segments.append((current_cursor, total_lines))

    for mod_start, mod_end in module_segments:
        segment_lines = source_lines[mod_start - 1: mod_end]
        # Ignore empty or blank-only module blocks
        if not "".join(segment_lines).strip():
            continue

        if (mod_end - mod_start + 1) > max_chunk_lines or sum(len(l) for l in segment_lines) > max_chunk_chars:
            mod_chunks = _split_lines_into_windows(
                lines=segment_lines,
                base_start_line=mod_start,
                path=path,
                symbol="<module>",
                kind="module",
                max_chunk_lines=max_chunk_lines,
                chunk_overlap_lines=chunk_overlap_lines,
                max_chunk_chars=max_chunk_chars,
                chunk_config_id=chunk_config_id,
            )
            chunks.extend(mod_chunks)
        else:
            raw_body = "".join(segment_lines)
            c_id = _generate_chunk_id(path, mod_start, mod_end, chunk_config_id)
            c_hash = hashlib.sha256(raw_body.encode("utf-8")).hexdigest()[:32]
            text = _format_chunk_text(path, "<module>", mod_start, mod_end, raw_body)
            chunks.append(
                Chunk(
                    id=c_id,
                    path=path,
                    symbol="<module>",
                    kind="module",
                    start_line=mod_start,
                    end_line=mod_end,
                    text=text,
                    content_hash=c_hash,
                    chunk_config_id=chunk_config_id,
                )
            )

    # Sort chunks deterministically by start_line
    chunks.sort(key=lambda c: (c.start_line, c.end_line))
    return chunks


def chunk_file_fixed_window(
    source_text: str,
    path: str,
    window_chars: int = 500,
    overlap_chars: int = 100,
    chunk_config_id: str = "fixed_window_v1",
) -> list[Chunk]:
    """
    Fixed-character sliding window chunking (size=500, overlap=100)
    replicating the starter strategy, while mapping character offsets to 1-based line ranges.
    """
    if not source_text:
        return []

    chunks: list[Chunk] = []
    text_len = len(source_text)
    step = max(1, window_chars - overlap_chars)
    cursor = 0

    # Build line start offsets
    line_offsets = [0]
    for idx, char in enumerate(source_text):
        if char == "\n":
            line_offsets.append(idx + 1)

    def _char_to_line(char_idx: int) -> int:
        # Binary search or scan
        import bisect
        line_num = bisect.bisect_right(line_offsets, char_idx)
        return max(1, line_num)

    while cursor < text_len:
        slice_end = min(cursor + window_chars, text_len)
        chunk_body = source_text[cursor:slice_end]
        start_line = _char_to_line(cursor)
        end_line = _char_to_line(max(cursor, slice_end - 1))

        chunk_id = _generate_chunk_id(path, start_line, end_line, f"{chunk_config_id}_{cursor}")
        content_hash = hashlib.sha256(chunk_body.encode("utf-8")).hexdigest()[:32]
        formatted_text = _format_chunk_text(path, "<window>", start_line, end_line, chunk_body)

        chunks.append(
            Chunk(
                id=chunk_id,
                path=path,
                symbol="<window>",
                kind="window",
                start_line=start_line,
                end_line=end_line,
                text=formatted_text,
                content_hash=content_hash,
                chunk_config_id=chunk_config_id,
            )
        )

        if slice_end >= text_len:
            break
        cursor += step

    return chunks


def chunk_source_file(
    source_text: str,
    path: str,
    strategy: str = "ast_hybrid",
    max_chunk_lines: int = 60,
    chunk_overlap_lines: int = 8,
    max_chunk_chars: int = 3000,
) -> list[Chunk]:
    """Top-level dispatch based on configured strategy."""
    if strategy == "fixed_window":
        return chunk_file_fixed_window(source_text=source_text, path=path)
    return chunk_file_ast_hybrid(
        source_text=source_text,
        path=path,
        max_chunk_lines=max_chunk_lines,
        chunk_overlap_lines=chunk_overlap_lines,
        max_chunk_chars=max_chunk_chars,
    )
