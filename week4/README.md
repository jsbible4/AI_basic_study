# Local Document–Based AI Workflow Automation Agent

https://blog.naver.com/unpatched_winner/224133946973

This project implements an AI agent that autonomously explores, analyzes, compares, and summarizes **local documents** to generate **meaningful investment insights and structured outputs**.

The system combines:
- an **MCP (Model Context Protocol) server** for secure local file access, and
- a **LangChain-based agent** powered by **Claude LLM**, which decides **when and how to use file-system tools**.

---


---

## Required Features

### 1. MCP Server

The MCP server provides controlled access to the local file system and implements the following features:

- List files in a specified directory  
- Read text files  
- Create new Markdown files  
- Summarize file contents and overwrite existing files  
- Read CSV files and generate statistical summaries  

All file I/O and CSV parsing logic resides **entirely in the MCP server**.

---

### 2. LangChain Agent

The agent is implemented using LangChain and includes:

- **Claude LLM** as the reasoning engine  
- **MCP Client** connection for tool-based file access  
- Clearly defined tool descriptions (docstrings act as tool documentation)  
- An agent design where the LLM **decides when MCP tools should be used**, instead of relying on a fixed execution script  

---

## Agent Usage Scenario

### Goal

Enable the agent to autonomously explore, analyze, compare, and summarize local files in order to generate **investment insights and reusable artifacts**.

---

### Scenario Workflow

1. The agent reads a personal investment portfolio:
   - `International_stock_portfolio.csv`

2. The agent reads National Pension Service (NPS) overseas equity portfolios:
   - `NPS_International_stock_portfolio_2023.csv`
   - `NPS_International_stock_portfolio_2024.csv`

3. The agent lists all files in the target directory and reports the total number of files.

4. From `International_stock_portfolio.csv`, the agent extracts stock names (`종목명`) that **do not appear** in the 2024 NPS portfolio and saves them to:

5. From the 2024 NPS portfolio, the agent analyzes the column:
and identifies the **top 10 investment holdings** with a weight of **1% or higher**.

6. The agent compares the top 10 ranked stocks (rank 1–10) between 2023 and 2024:
- New entries
- Exited stocks
- Rank movements

7. The agent generates a Markdown report containing:
- A one-line explanation of the key reason behind portfolio changes
- A structured summary of ranking changes  


# 전체 시스템 

<img width="517" height="278" alt="image" src="https://github.com/user-attachments/assets/59d323dd-3f03-4935-bd9d-f77f58b2f7f5" />


# 전체 구조 개요

agent.py

<img width="549" height="554" alt="image" src="https://github.com/user-attachments/assets/4041f0ea-1eef-4f82-bed1-226be1e7da25" />

filesystem_mcp.py

<img width="462" height="376" alt="image" src="https://github.com/user-attachments/assets/fa9022dd-8496-4bb6-8b82-a55114a4a6f7" />



# 핵심 구성 요소별 코드 분석 1 (agent.py)

## 2.1 MCP Tool 호출 헬퍼
역할: MCP 서버의 도구를 호출하고 결과를 파싱
```
async def call_mcp_tool(session, name: str, args: Dict[str, Any]) -> Any:
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
```
특징:

MCP 서버의 응답을 JSON으로 파싱
파싱 실패 시 원본 텍스트 반환
모든 MCP 호출의 공통 인터페이스




## 2.2 LangChain Tool 래퍼 생성
역할: MCP 도구를 LangChain Agent가 사용할 수 있는 형태로 변환
```
def build_tools(session: ClientSession):
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
```
핵심 포인트:

@tool 데코레이터: LangChain Tool로 자동 변환
docstring이 중요: LLM이 이 설명을 읽고 언제 도구를 사용할지 판단
각 도구는 call_mcp_tool()을 통해 실제 MCP 서버 호출


## 2.3 Agent Prompt 구성
역할: Agent의 행동 규칙과 사고 방식 정의
```
def build_agent_prompt() -> ChatPromptTemplate:
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
```
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
```
async def run_agent():
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

```

## Agent가 "언제 MCP를 써야 하는지" 판단하는 방법

### System Prompt 규칙
```
 "1) 파일 목록/파일 내용/CSV 값은 반드시 제공된 tool(MCP)로 조회한다. 추측 금지."
```
→ 파일 관련 작업은 무조건 Tool 사용

### Tool Docstring
```
 """dir_path 경로의 파일/폴더 목록을 조회한다."""
```
→ LLM이 이 설명을 보고 "아, 파일 목록이 필요하면 이 도구를 써야겠구나" 판단

### ReAct 사고 과정

- Thought에서 "파일 목록이 필요해"라고 생각
- 사용 가능한 도구 중 list_files의 설명을 확인
- Action으로 list_files 선택


# 핵심 구성 요소별 코드 분석 2 (filesystem_mcp.py)

## 2. 초기화 및 설정 부분
### 2.1 Logging 비활성화
```
# Logging (완전 비활성화 - MCP 프로토콜 보호)
logger = logging.getLogger("week4-mcp")
logger.setLevel(logging.CRITICAL)  # 모든 로그 비활성화
logger.addHandler(logging.NullHandler())
logger.propagate = False
```
목적:

MCP는 stdin/stdout으로 JSON-RPC 프로토콜 통신
어떤 로그도 stdout에 출력되면 프로토콜 오염 발생
따라서 모든 로깅을 완전히 차단
(python 3.13은 안됨. 3.11로 다운그레이드하여 진행)

### 2.2 ROOT_DIR 설정
```
ROOT_DIR = Path(os.environ.get("MCP_ROOT_DIR", "./sandbox")).resolve()
ROOT_DIR.mkdir(parents=True, exist_ok=True)
```
역할:

환경변수 MCP_ROOT_DIR에서 작업 디렉토리 경로 가져오기
없으면 기본값 ./sandbox 사용
.resolve(): 절대 경로로 변환
디렉토리가 없으면 자동 생성


### 2.3 FastMCP 인스턴스 생성
```
mcp = FastMCP("week4-filesystem-agent")
```
역할:

MCP 서버 객체 생성
"week4-filesystem-agent": 서버 식별 이름


## 3. Helper 함수들
### 3.1 경로 보안 검증
```
def _safe_path(rel_path: str) -> Path:
    """Prevent path traversal."""
    p = (ROOT_DIR / rel_path).resolve()
    if ROOT_DIR not in p.parents and p != ROOT_DIR:
        raise ValueError("Path traversal detected.")
    return p
```
목적: Path Traversal 공격 방지
동작:
```

# 안전한 경로
_safe_path("data.csv")           # ✅ ROOT_DIR/data.csv
_safe_path("folder/file.txt")    # ✅ ROOT_DIR/folder/file.txt

# 위험한 경로 차단
_safe_path("../../../etc/passwd") # ❌ ValueError
_safe_path("/etc/passwd")         # ❌ ValueError
```
검증 로직:

ROOT_DIR / rel_path: 상대 경로를 ROOT_DIR 기준으로 결합
.resolve(): 심볼릭 링크 해제 및 절대 경로 변환
ROOT_DIR not in p.parents: 최종 경로가 ROOT_DIR 밖이면 에러


3.2 파일 읽기/쓰기
```
def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")

def _write_text(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)  # 부모 디렉토리 자동 생성
    p.write_text(content, encoding="utf-8")
```
특징:

UTF-8 인코딩 고정
쓰기 시 부모 디렉토리 자동 생성


## 4. MCP Tools (5개)
### 4.1 list_files - 파일 목록 조회

```
@mcp.tool()
def list_files(dir_path: str = ".", recursive: bool = False) -> List[Dict[str, Any]]:
    """List files under ROOT_DIR."""
  ~~
```


### 4.2 read_text_file - 텍스트 파일 읽기

```
@mcp.tool()
def read_text_file(file_path: str) -> Dict[str, Any]:
    """Read UTF-8 text file."""
    
    ~~~
```


### 4.3 create_text_file - 텍스트 파일 생성

```@mcp.tool()
def create_text_file(file_path: str, content: str, overwrite: bool = False) -> Dict[str, Any]:
    """Create plain text file."""
    p = _safe_path(file_path)
    ~~~
```
파라미터:

overwrite=False: 기존 파일 보호
overwrite=True: 기존 파일 덮어쓰기


### 4.4 create_markdown_file - 마크다운 파일 생성

```@mcp.tool()
def create_markdown_file(file_path: str, content: str, overwrite: bool = False) -> Dict[str, Any]:
    """Create markdown file."""
    ~~~
```
목적:

기능적으로는 create_text_file과 동일
의미적으로 마크다운 파일임을 명시
Agent가 "마크다운 생성" 작업 시 적절한 도구 선택 가능


### 4.5 read_csv_stats - CSV 읽기 + 통계

```
@mcp.tool()
def read_csv_stats(file_path: str, max_rows_preview: int = 50) -> Dict[str, Any]:
    """Read CSV with stats and preview."""
    ~~~
    }
```

## 5. 실행 부분

```if __name__ == "__main__":
    mcp.run()
```

<img width="469" height="258" alt="image" src="https://github.com/user-attachments/assets/2b13fb98-fd51-4c06-bdf8-f836098a4cbb" />


