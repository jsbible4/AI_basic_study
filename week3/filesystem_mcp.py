from __future__ import annotations

import os
from pathlib import Path
from typing import List
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("HW3 Filesystem MCP")

def _resolve_safe(root: Path, rel: str) -> Path:
    root = root.resolve()
    p = (root / rel).resolve()

    # root 밖으로 탈출 방지
    if os.name == "nt":
        rs = str(root).lower()
        ps = str(p).lower()
        if not (ps == rs or ps.startswith(rs + os.sep)):
            raise ValueError("허용되지 않은 경로 접근(root 밖).")
    else:
        if not (p == root or root in p.parents):
            raise ValueError("허용되지 않은 경로 접근(root 밖).")
    return p

@mcp.tool()
def list_files(root_dir: str, sub_dir: str = ".", include_hidden: bool = False) -> List[str]:
    """특정 디렉토리 파일/폴더 목록"""
    root = Path(root_dir)
    d = _resolve_safe(root, sub_dir)
    if not d.exists() or not d.is_dir():
        raise ValueError("디렉토리가 존재하지 않습니다.")

    out = []
    for child in sorted(d.iterdir(), key=lambda x: x.name.lower()):
        name = child.name
        if not include_hidden and name.startswith("."):
            continue
        out.append(name + ("/" if child.is_dir() else ""))
    return out

@mcp.tool()
def read_file(root_dir: str, rel_path: str, max_bytes: int = 200_000) -> str:
    """파일 내용 읽기"""
    root = Path(root_dir)
    p = _resolve_safe(root, rel_path)
    if not p.exists() or not p.is_file():
        raise ValueError("파일이 존재하지 않습니다.")

    data = p.read_bytes()
    if len(data) > max_bytes:
        raise ValueError(f"파일이 너무 큽니다: {len(data)} bytes")
    return data.decode("utf-8", errors="replace")

@mcp.tool()
def create_file(root_dir: str, rel_path: str, content: str, overwrite: bool = False) -> str:
    """파일 생성/쓰기"""
    root = Path(root_dir)
    p = _resolve_safe(root, rel_path)

    if p.exists() and not overwrite:
        raise ValueError("이미 파일이 존재합니다. overwrite=True로 다시 시도하세요.")

    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"OK: wrote {p}"

def main():
    mcp.run()

if __name__ == "__main__":
    main()
