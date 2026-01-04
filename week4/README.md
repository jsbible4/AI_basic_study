
# 전체 구조 개요

<img width="549" height="554" alt="image" src="https://github.com/user-attachments/assets/4041f0ea-1eef-4f82-bed1-226be1e7da25" />




# 핵심 구성 요소별 코드 분석

## 2.1 MCP Tool 호출 헬퍼
역할: MCP 서버의 도구를 호출하고 결과를 파싱
pythonasync def call_mcp_tool(session, name: str, args: Dict[str, Any]) -> Any:
    """MCP 도구 호출 헬퍼"""
    res = await session.call_tool(name, args)
    if hasattr(res, "content") and res.content:
        text = getattr(res.content[0], "text", None)
        if text:
            try:
                return json.loads(text)  # JSON 파싱 시도
            except:
                return {"text": text}     # 실패 시 텍스트 반환
    return {"raw": str(res)}
특징:

MCP 서버의 응답을 JSON으로 파싱
파싱 실패 시 원본 텍스트 반환
모든 MCP 호출의 공통 인터페이스




## 2.2 LangChain Tool 래퍼 생성
역할: MCP 도구를 LangChain Agent가 사용할 수 있는 형태로 변환
pythondef build_tools(session: ClientSession):
    """MCP tool들을 LangChain Tool로 래핑"""
    
    @tool
    async def list_files(dir_path: str) -> Any:
        """dir_path 경로의 파일/폴더 목록을 조회한다."""
        return await call_mcp_tool(session, "list_files", {"dir_path": dir_path})
    
    @tool
    async def read_csv_stats(file_path: str, max_rows_preview: int = 200) -> Dict[str, Any]:
        """
        CSV 파일을 읽고 통계/미리보기를 반환한다.
        - file_path: CSV 경로
        - max_rows_preview: preview에 포함할 최대 행 수
        """
        return await call_mcp_tool(session, "read_csv_stats", {
            "file_path": file_path,
            "max_rows_preview": max_rows_preview
        })
    
    # ... 나머지 도구들 ...
    
    return [list_files, read_csv_stats, read_text_file, 
            create_text_file, create_markdown_file]
핵심 포인트:

@tool 데코레이터: LangChain Tool로 자동 변환
docstring이 중요: LLM이 이 설명을 읽고 언제 도구를 사용할지 판단
각 도구는 call_mcp_tool()을 통해 실제 MCP 서버 호출


## 2.3 Agent Prompt 구성
역할: Agent의 행동 규칙과 사고 방식 정의
pythondef build_agent_prompt() -> ChatPromptTemplate:
    """Agent의 판단 규칙 정의"""
    return ChatPromptTemplate.from_messages([
        ("system",
         "너는 로컬 파일 분석 에이전트다.\n"
         "규칙:\n"
         "1) 파일 목록/파일 내용/CSV 값은 반드시 제공된 tool(MCP)로 조회한다. 추측 금지.\n"
         "2) 비교/필터링/정렬은 CSV preview를 근거로 수행한다.\n"
         "3) 산출물(txt, md)은 tool로 생성한 뒤 tool로 다시 읽어 저장이 되었는지 확인한다.\n"
         "4) 최종 답변에는 생성된 파일명과 핵심 결과를 포함한다.\n"
        ),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
구조:

system 메시지: Agent의 역할과 행동 규칙
human 메시지: 사용자 입력 ({input} 플레이스홀더)
agent_scratchpad: Agent의 사고 과정 (Thought, Action, Observation) 기록

"언제 MCP를 써야 하는지" 판단 방법:

System 메시지에서 명시적 규칙 제공
Tool의 docstring으로 도구 설명
ReAct 패턴으로 단계별 사고


## 2.4 메인 실행 함수
역할: MCP 연결 → Agent 구성 → 시나리오 실행
pythonasync def run_agent():
    # 1️⃣ MCP 서버 연결 설정
    py = os.path.join(os.getcwd(), ".venv", "bin", "python")
    script = os.path.join(os.getcwd(), "filesystem_mcp.py")
    root_dir = os.path.join(os.getcwd(), "sandbox")

    server_params = StdioServerParameters(
        command=py,
        args=[script],
        env={"MCP_ROOT_DIR": root_dir}
    )

    # 2️⃣ MCP 서버와 세션 시작
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # 3️⃣ LLM 초기화
            llm = ChatAnthropic(model="claude-3-5-haiku-latest", temperature=0.0)

            # 4️⃣ Tools + Prompt + Agent 생성
            tools = build_tools(session)
            prompt = build_agent_prompt()
            agent = create_react_agent(llm, tools, prompt=prompt)
            
            # 5️⃣ AgentExecutor로 래핑
            executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

            # 6️⃣ 시나리오 정의 및 실행
            scenario = """
            같은 디렉토리하에 있는 나의 투자 포트폴리오를 읽고,
            국민연금 해외주식 포트폴리오와 비교해라.
            
            해야 하는 일:
            1) 로컬 파일 list를 조회해 파일 개수를 확인한다.
            2) CSV들을 읽는다.
            3) 내 포트폴리오에만 있는 종목을 txt로 저장한다.
            4) NPS 2024에서 비중 >= 1% 인 종목 상위 10개를 출력한다.
            5) 2023 vs 2024 Top10 순위 변화를 마크다운으로 저장한다.
            """
            
            # 7️⃣ Agent 실행
            result = await executor.ainvoke({"input": scenario})
            print("\n=== FINAL OUTPUT ===")
            print(result["output"])
```

---

## 3. 데이터 흐름

<img width="316" height="537" alt="image" src="https://github.com/user-attachments/assets/c726559c-866e-4560-b871-1d891c26cce0" />

```

```

---

## 4. 핵심 개념 정리

### ReAct 패턴 (Reason + Act)
```
Thought: 지금 무엇을 해야 하는가?
Action: list_files
Action Input: {"dir_path": "."}
Observation: [파일 목록 결과]

Thought: 파일을 확인했으니 CSV를 읽어야겠다
Action: read_csv_stats
Action Input: {"file_path": "International_stock_portfolio.csv"}
Observation: [CSV 데이터]

... (계속 반복) ...

Thought: 모든 작업을 완료했다
Final Answer: [최종 결과]

Agent가 "언제 MCP를 써야 하는지" 판단하는 방법

System Prompt 규칙

python   "1) 파일 목록/파일 내용/CSV 값은 반드시 제공된 tool(MCP)로 조회한다. 추측 금지."
→ 파일 관련 작업은 무조건 Tool 사용

Tool Docstring

python   """dir_path 경로의 파일/폴더 목록을 조회한다."""
→ LLM이 이 설명을 보고 "아, 파일 목록이 필요하면 이 도구를 써야겠구나" 판단

ReAct 사고 과정

Thought에서 "파일 목록이 필요해"라고 생각
사용 가능한 도구 중 list_files의 설명을 확인
Action으로 list_files 선택
