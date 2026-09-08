"""
2C-1 테스트 — script 가 있는 skill 이 실제로 실행되는지 확인
============================================================
목적: prime-check skill 이 SKILL.md 를 읽고, scripts/is_prime.py 를
      '진짜 실행'해서 그 결과로 답하는지 확인한다.

backend 는 LocalShellBackend (FilesystemBackend + 셸 실행).
DB 도 미들웨어도 아직 없다. "script 실행 자체"만 본다. (DB 전송은 2C-2)

── .env 에 넣을 값 (사내 게이트웨이 기준) ───────────────────
    LLM_MODEL=google/gemma-4-31B-it
    LLM_API_ADDRESS=https://사내-게이트웨이-주소/v1
    LLM_API_KEY=...            # 없으면 비워둬도 됨(코드에서 EMPTY 처리)
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend
from langchain_openai import ChatOpenAI
from langchain_core.messages import ToolMessage
from langgraph.checkpoint.memory import MemorySaver


SHOW_FULL = False

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")   # .env 에서 LLM_* 값을 불러온다

# ── LLM 모델 설정 (사내 게이트웨이를 OpenAI 호환 방식으로 연결) ──────
#    base_url : 사내 게이트웨이 주소
#    api_key  : 없으면 "EMPTY" 로 (일부 게이트웨이는 키가 필요 없음)
model = ChatOpenAI(
    model=os.environ["LLM_MODEL"],
    base_url=os.environ["LLM_API_ADDRESS"],
    api_key=os.environ.get("LLM_API_KEY") or "EMPTY",
)


def get_text(msg) -> str:
    """LLM 메시지에서 사람이 읽을 텍스트만 뽑아낸다."""
    content = getattr(msg, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
    return str(content)


def indent(text: str, prefix: str = "      ") -> str:
    """여러 줄 문자열의 각 줄 앞에 prefix 를 붙인다."""
    return "\n".join(prefix + line for line in text.splitlines())


# ── LocalShellBackend 생성 (셸 실행이 되는 backend) ──────────────────
backend = LocalShellBackend(root_dir=str(ROOT), virtual_mode=True, inherit_env=True)

agent = create_deep_agent(
    model=model,
    backend=backend,
    skills=["/skills/"],
    checkpointer=MemorySaver(),
)

test_cases = [
    ("97은 소수야?", "prime-check"),
    ("7919가 prime인지 알려줘", "prime-check"),
    ("100은 소수인지 판별해줘", "prime-check"),
]

for i, (question, expected) in enumerate(test_cases, start=1):
    print(f"\n{'=' * 60}\n[{i}] 질문: {question}\n    기대 Skill: {expected}")

    result = agent.invoke(
        {"messages": [{"role": "user", "content": question}]},
        config={"configurable": {"thread_id": f"test-{i}"}},
    )

    # ── 추적: ToolMessage(도구 실행 결과) 기준 ──
    #    (게이트웨이가 tool_calls 의 args 를 비우는 경우가 있어, 결과로 판단하는 게 안정적)
    skill_read = False
    script_ran = False
    script_output = ""

    for msg in result["messages"]:
        if isinstance(msg, ToolMessage):
            tool_name = getattr(msg, "name", "")
            tool_result = get_text(msg)
            if tool_name == "read_file" and "name: prime-check" in tool_result:
                skill_read = True
            if tool_name == "execute" and ("PRIME" in tool_result or "NOT_PRIME" in tool_result):
                script_ran = True
                script_output = tool_result.strip()

    print(f"    → Skill(SKILL.md) 읽음? : {'예' if skill_read else '아니오'}")
    print(f"    → script 실행됨?        : {'예 (' + script_output + ')' if script_ran else '아니오'}")

    last_message = result["messages"][-1]
    print(f"    → LLM 최종 답변:\n{indent(get_text(last_message))}")

    if SHOW_FULL:
        print("    ── 전체 대화 흐름 ──")
        for msg in result["messages"]:
            role = type(msg).__name__
            text = get_text(msg).strip()
            if text:
                print(f"      [{role}] {text[:200]}")

print(f"\n{'=' * 60}\n2C-1 끝. 'Skill 읽음? 예' 와 'script 실행됨? 예(PRIME/NOT_PRIME)' 이 둘 다 나오면 성공.")