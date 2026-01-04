from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

# LangChain Agent (버전에 따라 import 경로가 다를 수 있음)
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp import ClientSession

load_dotenv()

# 파일명 상수
USER_PORTFOLIO = "International_stock_portfolio.csv"
NPS_2024 = "NPS_International_stock_portfolio_2024.csv"
NPS_2023 = "NPS_International_stock_portfolio_2023.csv"

async def call_mcp_tool(session, name: str, args: Dict[str, Any]) -> Any:
    """MCP 도구 호출 헬퍼 (기존 그대로 유지)"""
    res = await session.call_tool(name, args)
    if hasattr(res, "content") and res.content:
        text = getattr(res.content[0], "text", None)
        if text:
            try:
                return json.loads(text)
            except:
                return {"text": text}
    return {"raw": str(res)}

def build_tools(session: ClientSession):
    """
    MCP tool들을 LangChain Tool로 래핑.
    docstring(설명)이 곧 LLM의 tool 사용 설명서임.
    """

    @tool
    async def list_files(dir_path: str) -> Any:
        """dir_path 경로의 파일/폴더 목록을 조회한다. (예: "." 또는 "sandbox")"""
        return await call_mcp_tool(session, "list_files", {"dir_path": dir_path})
    @tool
    async def read_csv_stats(file_path: str, max_rows_preview: int = 200) -> Dict[str, Any]:
        """
        CSV 파일을 읽고 통계/미리보기(preview)를 반환한다.
        - file_path: CSV 경로
        - max_rows_preview: preview에 포함할 최대 행 수
        반환 예시 key: columns, preview(list[dict]), row_count(구현에 따라 다를 수 있음)
        """
        return await call_mcp_tool(session, "read_csv_stats", {
            "file_path": file_path,
            "max_rows_preview": max_rows_preview
        })

    @tool
    async def read_text_file(file_path: str) -> Dict[str, Any]:
        """텍스트/마크다운 파일을 읽어 content를 반환한다."""
        return await call_mcp_tool(session, "read_text_file", {"file_path": file_path})

    @tool
    async def create_text_file(file_path: str, content: str, overwrite: bool = True) -> Dict[str, Any]:
        """
        텍스트 파일을 생성/저장한다.
        - overwrite=True면 동일 파일이 있으면 덮어쓴다.
        """
        return await call_mcp_tool(session, "create_text_file", {
            "file_path": file_path,
            "content": content,
            "overwrite": overwrite
        })

    @tool
    async def create_markdown_file(file_path: str, content: str, overwrite: bool = True) -> Dict[str, Any]:
        """
        마크다운 파일을 생성/저장한다.
        - overwrite=True면 동일 파일이 있으면 덮어쓴다.
        """
        return await call_mcp_tool(session, "create_markdown_file", {
            "file_path": file_path,
            "content": content,
            "overwrite": overwrite
        })

    return [list_files, read_csv_stats, read_text_file, create_text_file, create_markdown_file]

def build_agent_prompt() -> ChatPromptTemplate:
    """
    “언제 MCP를 써야 하는지” 판단 규칙을 Prompt에 박아넣는 게 핵심.
    """
    return ChatPromptTemplate.from_messages([
        ("system",
         "너는 로컬 파일 분석 에이전트다.\n"
         "규칙:\n"
         "1) 파일 목록/파일 내용/CSV 값은 반드시 제공된 tool(MCP)로 조회한다. 추측 금지.\n"
         "2) 비교/필터링/정렬은 CSV preview를 근거로 수행한다.\n"
         "3) 산출물(txt, md)은 tool로 생성한 뒤 tool로 다시 읽어 저장이 되었는지 확인한다.\n"
         "4) 최종 답변에는 생성된 파일명과 핵심 결과(Top10, only_in_my, 변화 요약)를 포함한다.\n"
        ),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

async def run_agent():
    # MCP 서버 실행 파라미터 (기존 run_scenario에서 가져온 그대로 유지)
    py = os.path.join(os.getcwd(), ".venv", "bin", "python")
    script = os.path.join(os.getcwd(), "filesystem_mcp.py")
    root_dir = os.path.join(os.getcwd(), "sandbox")

    server_params = StdioServerParameters(
        command=py,
        args=[script],
        env={"MCP_ROOT_DIR": root_dir}
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            llm = ChatAnthropic(model="claude-3-5-haiku-latest", temperature=0.0)

            tools = build_tools(session)
            prompt = build_agent_prompt()

            agent = create_react_agent(llm, tools, prompt=prompt)
            executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

            scenario = f"""
같은 디렉토리하에 있는 나의 투자 포트폴리오({USER_PORTFOLIO})를 읽고,
국민연금 해외주식 포트폴리오({NPS_2023}, {NPS_2024})와 비교해라.

해야 하는 일:
1) 로컬 파일 list를 조회해 파일 개수를 확인한다.
2) CSV들을 읽는다.
3) {USER_PORTFOLIO}의 '종목명' 중 {NPS_2024}에는 없는 종목을 뽑아 only_in_my_portfolio.txt로 저장한다.
4) {NPS_2024}에서 '자산군 내 비중 (%)' >= 1% 인 종목 상위 10개를 출력한다.
5) {NPS_2023} vs {NPS_2024} Top10(번호 1~10) 순위 변화를 분석하고,
   핵심 변화 이유 1줄과 함께 요약을 nps_top10_change_2023_to_2024.md로 저장한다.
"""
            result = await executor.ainvoke({"input": scenario})
            print("\n=== FINAL OUTPUT ===")
            print(result["output"])

if __name__ == "__main__":
    asyncio.run(run_agent())
