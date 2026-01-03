from __future__ import annotations

import os
import sys
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from mcp.server.fastmcp import FastMCP

# Logging (완전 비활성화 - MCP 프로토콜 보호)
logger = logging.getLogger("week4-mcp")
logger.setLevel(logging.CRITICAL)  # 모든 로그 비활성화
logger.addHandler(logging.NullHandler())
logger.propagate = False

# Root dir
ROOT_DIR = Path(os.environ.get("MCP_ROOT_DIR", "./sandbox")).resolve()
ROOT_DIR.mkdir(parents=True, exist_ok=True)

def _safe_path(rel_path: str) -> Path:
    """Prevent path traversal."""
    p = (ROOT_DIR / rel_path).resolve()
    if ROOT_DIR not in p.parents and p != ROOT_DIR:
        raise ValueError("Path traversal detected.")
    return p

def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")

def _write_text(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")

mcp = FastMCP("week4-filesystem-agent")

@mcp.tool()
def list_files(dir_path: str = ".", recursive: bool = False) -> List[Dict[str, Any]]:
    """List files under ROOT_DIR."""
    d = _safe_path(dir_path)
    if not d.exists():
        raise FileNotFoundError(f"Directory not found: {dir_path}")
    if not d.is_dir():
        raise NotADirectoryError(f"Not a directory: {dir_path}")
    
    items = d.rglob("*") if recursive else d.iterdir()
    results = []
    for it in sorted(items, key=lambda x: str(x).lower()):
        try:
            size = it.stat().st_size if it.is_file() else 0
        except:
            size = 0
        results.append({
            "path": str(it.relative_to(ROOT_DIR)),
            "is_dir": it.is_dir(),
            "size_bytes": size
        })
    return results

@mcp.tool()
def read_text_file(file_path: str) -> Dict[str, Any]:
    """Read UTF-8 text file."""
    p = _safe_path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if p.is_dir():
        raise IsADirectoryError(f"Is a directory: {file_path}")
    return {
        "path": str(p.relative_to(ROOT_DIR)),
        "content": _read_text(p)
    }

@mcp.tool()
def create_text_file(file_path: str, content: str, overwrite: bool = False) -> Dict[str, Any]:
    """Create plain text file."""
    p = _safe_path(file_path)
    if p.exists() and not overwrite:
        raise FileExistsError(f"File exists: {file_path}")
    _write_text(p, content)
    return {
        "path": str(p.relative_to(ROOT_DIR)),
        "bytes_written": len(content.encode("utf-8"))
    }

@mcp.tool()
def create_markdown_file(file_path: str, content: str, overwrite: bool = False) -> Dict[str, Any]:
    """Create markdown file."""
    p = _safe_path(file_path)
    if p.exists() and not overwrite:
        raise FileExistsError(f"File exists: {file_path}")
    _write_text(p, content)
    return {
        "path": str(p.relative_to(ROOT_DIR)),
        "bytes_written": len(content.encode("utf-8"))
    }

@mcp.tool()
def read_csv_stats(file_path: str, max_rows_preview: int = 50) -> Dict[str, Any]:
    """Read CSV with stats and preview."""
    p = _safe_path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if p.is_dir():
        raise IsADirectoryError(f"Is a directory: {file_path}")
    
    df = pd.read_csv(p)
    preview = df.head(max_rows_preview).to_dict(orient="records")
    
    numeric_stats = {}
    for col in df.select_dtypes(include="number").columns:
        s = df[col].dropna()
        if len(s) > 0:
            numeric_stats[col] = {
                "count": int(s.count()),
                "mean": float(s.mean()),
                "min": float(s.min()),
                "max": float(s.max()),
            }
    
    return {
        "path": str(p.relative_to(ROOT_DIR)),
        "columns": df.columns.tolist(),
        "row_count": int(len(df)),
        "numeric_stats": numeric_stats,
        "preview": preview,
    }

if __name__ == "__main__":
    mcp.run()