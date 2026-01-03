from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp import ClientSession

load_dotenv()

# CSV 상수
USER_PORTFOLIO = "International_stock_portfolio.csv"
NPS_2024 = "NPS_International_stock_portfolio_2024.csv"
NPS_2023 = "NPS_International_stock_portfolio_2023.csv"
COL_RANK = "번호"
COL_NAME = "종목명"
COL_WEIGHT = "자산군 내 비중 (%)"

# CSV helper 함수들
def extract_names(rows):
    """Extract stock names from CSV rows."""
    names = []
    for r in rows:
        name = r.get(COL_NAME)
        if name:
            s = str(name).strip()
            if s:
                names.append(s)
    return names

def get_top10_by_rank(rows):
    """Get top 10 stocks by rank."""
    tmp = []
    for r in rows:
        try:
            rk = int(r.get(COL_RANK, 0))
            if 1 <= rk <= 10:
                name = str(r.get(COL_NAME, "")).strip()
                if name:
                    tmp.append((rk, name))
        except:
            pass
    tmp.sort()
    return [name for _, name in tmp]

def parse_weight(value):
    """Parse weight percentage to float."""
    if value is None:
        return None
    try:
        s = str(value).replace("%", "").replace(" ", "").strip()
        if s:
            return float(s)
    except:
        pass
    return None

async def call_mcp_tool(session, name: str, args: Dict[str, Any]) -> Any:
    """MCP 도구 호출 헬퍼"""
    res = await session.call_tool(name, args)
    
    if hasattr(res, "content") and res.content:
        text = getattr(res.content[0], "text", None)
        if text:
            try:
                return json.loads(text)
            except:
                return {"text": text}
    return {"raw": str(res)}

async def run_scenario():
    """메인 시나리오 - stdio_client를 제대로 사용"""
    
    py = os.path.join(os.getcwd(), ".venv", "bin", "python")
    script = os.path.join(os.getcwd(), "filesystem_mcp.py")
    root_dir = os.path.join(os.getcwd(), "sandbox")
    
    print(f"[agent] MCP Server: {script}")
    print(f"[agent] ROOT_DIR: {root_dir}")
    
    server_params = StdioServerParameters(
        command=py,
        args=[script],
        env={"MCP_ROOT_DIR": root_dir}
    )
    
    # stdio_client는 async generator이므로 이렇게 사용
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # 초기화
            await session.initialize()
            print("[agent] ✅ MCP 서버 연결 성공!")
            
            # LLM 초기화
            llm = ChatAnthropic(
    model="claude-3-5-haiku-latest",
    temperature=0.0
)

            
            # === 시나리오 시작 ===
            
            print("\n=== [1] 파일 목록 확인 ===")
            files = await call_mcp_tool(session, "list_files", {"dir_path": "."})
            print(f"파일 개수: {len(files)}")
            
            print("\n=== [2] CSV 읽기 ===")
            my_csv = await call_mcp_tool(session, "read_csv_stats", {
                "file_path": USER_PORTFOLIO,
                "max_rows_preview": 200
            })
            nps24_csv = await call_mcp_tool(session, "read_csv_stats", {
                "file_path": NPS_2024,
                "max_rows_preview": 200
            })
            
            my_names = set(extract_names(my_csv["preview"]))
            nps_names = set(extract_names(nps24_csv["preview"]))
            print(f"내 포트폴리오: {len(my_names)}개 종목")
            print(f"NPS 2024: {len(nps_names)}개 종목")
            
            print("\n=== [3] 차이점 분석 및 저장 ===")
            only_mine = sorted(my_names - nps_names)
            txt_content = "\n".join(only_mine) if only_mine else "(없음)"
            await call_mcp_tool(session, "create_text_file", {
                "file_path": "only_in_my_portfolio.txt",
                "content": txt_content,
                "overwrite": True
            })
            print(f"내 포트폴리오에만 있는 종목: {len(only_mine)}개")
            
            # txt 파일 읽기
            read_result = await call_mcp_tool(session, "read_text_file", {
                "file_path": "only_in_my_portfolio.txt"
            })
            print(f"저장된 내용 확인: {len(read_result['content'])} bytes")
            
            print("\n=== [4] NPS_2024 비중 1% 이상 종목 분석 ===")
            heavy = []
            for r in nps24_csv["preview"]:
                w = parse_weight(r.get(COL_WEIGHT))
                name = str(r.get(COL_NAME, "")).strip()
                if w and w >= 1.0 and name:
                    heavy.append((w, name))
            heavy.sort(reverse=True)
            print(f"비중 1% 이상: {len(heavy)}개 종목")
            for w, name in heavy[:10]: ##--------
                print(f"  - {name}: {w:.2f}%")
            
            print("\n=== [5] Top10 변화 분석 ===")
            nps23_csv = await call_mcp_tool(session, "read_csv_stats", {
                "file_path": NPS_2023,
                "max_rows_preview": 200
            })
            
            top10_23 = get_top10_by_rank(nps23_csv["preview"])
            top10_24 = get_top10_by_rank(nps24_csv["preview"])
            
            r23 = {name: i+1 for i, name in enumerate(top10_23)}
            r24 = {name: i+1 for i, name in enumerate(top10_24)}
            
            entered = [n for n in top10_24 if n not in r23]
            exited = [n for n in top10_23 if n not in r24]
            
            moved = []
            for n in top10_24:
                if n in r23:
                    delta = r23[n] - r24[n]
                    if delta != 0:
                        moved.append((delta, n, r23[n], r24[n]))
            moved.sort(reverse=True)
            
            print(f"신규 진입: {len(entered)}개")
            for name in entered:
                print(f"  - {name}")
            print(f"이탈: {len(exited)}개")
            for name in exited:
                print(f"  - {name}")
            print(f"순위 변동: {len(moved)}개")
            
            print("\n=== [6] LLM 분석 ===")
            prompt = f"""NPS 해외주식 Top10 변화를 1줄로 요약해라.

2023 Top10: {', '.join(top10_23)}
2024 Top10: {', '.join(top10_24)}
신규 진입: {', '.join(entered) if entered else '없음'}
이탈: {', '.join(exited) if exited else '없음'}

출력 형식: "이유: <1줄 요약>"
"""
            
            reason = (await llm.ainvoke([HumanMessage(content=prompt)])).content.strip()
            print(f"{reason}")
            
            print("\n=== [7] 마크다운 생성 ===")
            md = ["# NPS 해외주식 Top10 변화 요약 (2023 → 2024)\n"]
            md.append(f"## 핵심 변화\n{reason}\n")
            md.append("\n## Top10 신규 진입")
            if entered:
                md.extend([f"- {x}" for x in entered])
            else:
                md.append("- 없음")
            
            md.append("\n\n## Top10 이탈")
            if exited:
                md.extend([f"- {x}" for x in exited])
            else:
                md.append("- 없음")
            
            md.append("\n\n## 순위 변동")
            if moved:
                for delta, name, a, b in moved:
                    arrow = "↑" if delta > 0 else "↓"
                    md.append(f"- {name}: {a}위 → {b}위 ({arrow}{abs(delta)})")
            else:
                md.append("- 없음")
            
            await call_mcp_tool(session, "create_markdown_file", {
                "file_path": "nps_top10_change_2023_to_2024.md",
                "content": "\n".join(md),
                "overwrite": True
            })
            
            # 마크다운 파일 읽기
            md_result = await call_mcp_tool(session, "read_text_file", {
                "file_path": "nps_top10_change_2023_to_2024.md"
            })
            print(f"저장된 마크다운: {len(md_result['content'])} bytes")
            
            print("\n" + "="*60)
            print("✅ 모든 작업 완료!")
            print("="*60)
            print("생성된 파일:")
            print("  1. only_in_my_portfolio.txt")
            print("  2. nps_top10_change_2023_to_2024.md")

if __name__ == "__main__":
    asyncio.run(run_scenario())