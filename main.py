"""
목적: name + description 만 있는 skill 3개를 Deep Agent에 물려서, 질문에 맞는 Skill을 실제로 골라 쓰고 있는지 확인한다.

"""


import os
from dotenv import load_dotenv
from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
from deepagents.backends.filesystem import FilesystemBackend

backend = FilesystemBackend(root_dir=".")

load_dotenv()

model = ChatOpenAI(
    model=os.environ["LLM_MODEL"],
    base_url=os.environ["LLM_API_ADDRESS"],
    api_key=os.environ.get("LLM_API_KEY") or "EMPTY",
)


agent = create_deep_agent(
    model=model,
    system_prompt="너는 개발자를 돕는 조수야.",
    backend=backend,
    skills=["/skills"],
)

test_cases = [
    ("서울 지금 날씨 어때? 우산 챙겨야 해?", "weather-lookup"),
    ("10km는 몇 마일이야?", "unit-converter"),
    ("다음 세 글을 세 줄로 요약해줘: 딥 에이전트는 여러 스킬을 가지고 있는 에이전트야. 각 스킬은 특정한 기능을 수행할 수 있어. 예를 들어, 날씨를 조회하는 스킬, 단위를 변환하는 스킬 등이 있어.", "text-summarizer"),
]

for i, (question, expected) in enumerate(test_cases, start=1):
    print(f'\n[{i}] 질문: "{question}"\n 기대 skill: {expected}')

    result = agent.invoke({"messages": [{"role": "user", "content": question}]},
                          config = {"configurable": {"thread_id": f"test-{i}"}}
                          )

        # Skill이 "선택"되면 Agent는 그 Skill의 SKILL.md를 read_file 도구로 읽는다.
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




print(f"\n{'=' * 60}\n테스트 끝. 기대 Skill과 실제로 읽은 Skill이 맞는지 비교해보세요.")