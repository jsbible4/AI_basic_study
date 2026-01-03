import sys
from dotenv import load_dotenv

load_dotenv()

from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import PromptTemplate
# | runnable 형식 사용, LLMChain import 필요 X

def main():
    # 1) 입력 처리 (CLI)
    text = input("반말 문장 입력: ").strip()
    if not text:
        return

    # tone 입력 (없으면 기본)
    tone = input("톤 선택(기본/면접용/비즈니스 이메일) [기본]: ").strip()
    if not tone:
        tone = "기본"

    # 2) LLM (Claude)
    llm = ChatAnthropic(
        model="claude-3-haiku-20240307",
        temperature=0.0,
    )

    # 3) PromptTemplate
    prompt = PromptTemplate(
        input_variables=["text", "tone"],
        template=(
            "너는 한국어 문체 변환기다.\n"
            "\n"
            "규칙:\n"
            "1) 입력 문장을 반말 → 존댓말로 변환한다.\n"
            "2) 의미는 유지하고 말투만 바꾼다.\n"
            "3) 톤은 아래 설정을 따른다.\n"
            "4) 출력은 변환된 문장만 출력한다. 설명/부연/따옴표/머리말 금지.\n"
            "\n"
            "톤 설정:\n"
            "- 면접용: 매우 정중, 간결, 과장 없음\n"
            "- 비즈니스 이메일: 정중, 공손한 표현 사용\n"
            "- 기본: 일반적인 존댓말\n"
            "\n"
            "선택된 톤: {tone}\n"
            "\n"
            "입력 문장:\n"
            "{text}\n"
        ),
    )

    # 4) Runnable chain (Prompt | LLM)
    chain = prompt | llm

    # 5) 실행
    result = chain.invoke({"text": text, "tone": tone})

    # 6) 출력 (변환된 문장만)
    sys.stdout.write(result.content.strip())


if __name__ == "__main__":
    main()
