"""
목적: name + description 만 있는 skill 3개를 Deep Agent에 물려서, 질문에 맞는 Skill을 실제로 골라 쓰고 있는지 확인한다.

"""


import os
from dotenv import load_dotenv
from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
from deepagents.backends.filesystem import FilesystemBackend


# True 로 바뀌면 '질문 > 도구 호출 > 답변' 과정 전체 흐름을 순서대로 출력한다.
# 처음에는 False로 두고, 최종 답변만 보고, 자세히 보고 싶을 때 True로 켠다. 
SHOW_FULL = False


# 도우미 함수
def get_text(msg) -> str: 

    """
    메시지 하나에서 사람이 읽을 텍스트만 뽑아낸다.

    LLM 메시지의 content는 str일 때도 있고, 여러 조각(dict)의 list일 때도 있어서 두 경우 모두 처리한다.

    """
    content = getattr(msg, "content", "")

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                parts.append(part.get("text",""))
            else:
                parts.append(str(part))
        return "".join(parts)

    return str(content)

def indent(text: str, prefix: str = "     ") -> str:
    """
    여러 줄 문자열을 들여쓰기한다.
    """
    return "\n".join(prefix + line for line in text.splitlines())

# 환경 변수 로드
load_dotenv()

# LLM 모델 설정
model = ChatOpenAI(
    model=os.environ["LLM_MODEL"],
    base_url=os.environ["LLM_API_ADDRESS"],
    api_key=os.environ.get("LLM_API_KEY") or "EMPTY",
)

# 1. SKILL 폴더 기준 경로 현재 폴더를 root_dir로 지정한다. 파일 시스템 백엔드 생성 
backend = FilesystemBackend(root_dir=".")

# 2. Agent 생성. system_prompt는 Agent의 역할을 정의한다. skills는 Agent가 사용할 수 있는 스킬 경로를 지정한다.
agent = create_deep_agent(
    model=model,
    system_prompt="너는 개발자를 돕는 조수야.",
    backend=backend,
    skills=["/skills"],
)

# 3. 테스트 케이스 정의
test_cases = [
    ("서울 지금 날씨 어때? 우산 챙겨야 해?", "weather-lookup"),
    ("10km는 몇 마일이야?", "unit-converter"),
    ("다음 세 글을 세 줄로 요약해줘: 딥 에이전트는 여러 스킬을 가지고 있는 에이전트야. 각 스킬은 특정한 기능을 수행할 수 있어. 예를 들어, 날씨를 조회하는 스킬, 단위를 변환하는 스킬 등이 있어.", "text-summarizer"),
]

# 4. 테스트 케이스 실행
for i, (question, expected) in enumerate(test_cases, start=1):
    print(f'\n[{i}] 질문: "{question}"\n 기대 skill: {expected}')

    result = agent.invoke(
        {"messages": [{"role": "user", "content": question}]},
        config = {"configurable": {"thread_id": f"test-{i}"}}
    )

    # (a) Skill이 "선택"되면 Agent는 그 Skill의 SKILL.md를 read_file 도구로 읽는지 추적한다. 
    # 그 흔적을 메시지 기록에서 찾아본다.
    read_skills = []
    for msg in result["messages"]:
        # tool_calls: Agent가 호출한 도구 목록 (없을 수도 있어서 기본값 [] 처리)
        for call in getattr(msg, "tool_calls", []) or []:
            if call.get("name") == "read_file":
                path = str(call.get("args", {}).get("file_path", ""))
                if "SKILL.md" in path:
                    read_skills.append(path)
 
    if read_skills:
        print(f"    → 실제로 읽은 Skill 파일: {read_skills}")

    else:
        print("    → 읽은 SKILL.md 없음 (Skill이 선택되지 않음)")

    print(f"*********** result 자체: {result}")
    # (b) LLM의 최종 답변 출력 (마지막 메시지가 최종 답변임)
    last_message = result["messages"][-1]
    print(f"  → LLM 최종 답변:\n{indent(get_text(last_message))}")

    # (c) SHOW_FULL이 True이면, 전체 대화 흐름을 순서대로 출력한다.
    if SHOW_FULL: 
        print("\n  → 전체 대화 흐름:")
        for msg in result["messages"]:
            role = type(msg).__name__          # HumanMessage / AIMessage / ToolMessage ...
            text = get_text(msg).strip()
            calls = [c.get("name") for c in getattr(msg, "tool_calls", []) or []]
            if calls:
                print(f"      [{role}] 도구 호출 → {calls}")
            if text:
                # 너무 길면 앞 300자만 (전체를 보고 싶으면 [:300] 을 지운다)
                print(f"      [{role}] {text[:300]}")



print(f"\n{'=' * 60}\n테스트 끝. 기대 Skill과 실제로 읽은 Skill이 맞는지 비교해보세요.")