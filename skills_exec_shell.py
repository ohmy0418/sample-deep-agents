"""
skills_exec_shell.py — 2C-2 (B 계획)
====================================================================
목적: DB(PostgresStore)에 저장된 script 를 before_agent 미들웨어가
      실행 공간(빈 디스크 폴더)으로 전송하고, Agent 가 셸(execute)로
      그 script 를 실행해 결과를 받아오는 것까지 확인한다.

지금까지는 아래 둘이 따로따로만 검증돼 있었다.
  - main.py     : DB 저장 + 읽기 skill (실행 없음)
  - test_2c1.py : 셸 실행 (DB 없음, 파일이 이미 디스크에 있었음)
이 파일은 그 둘을 처음으로 잇는다. (DB -> 디스크 -> 셸 실행)

── 성공 판정 3단계 ───────────────────────────────────────────────
  1) 실행 전 workspace 가 비어 있음      <- 이게 없으면 실험 자체가 무효
  2) before_agent 후 script 파일 생성됨   <- A 계획의 성공 기준
  3) Agent 가 execute 로 돌려 결과 반환   <- B 계획의 성공 기준
"""

import base64
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, LocalShellBackend, StoreBackend
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.postgres import PostgresStore

# ─────────────────────────────────────────────────────────────────
# 설정값
# ─────────────────────────────────────────────────────────────────

SHOW_FULL = False                       # True 면 전체 대화 흐름까지 출력
SKILLS_NAMESPACE = ("skills-test",)     # 콤마 필수! 없으면 tuple 이 아니라 str 이 된다
SKILLS_ROOT = "/skills/"                # DB(store)에 저장될 때 쓰는 키 접두사. main.py 와 동일
SEARCH_LIMIT = 100                      # store.search 기본값이 10 이라 늘려야 한다

# CompositeBackend 는 route 접두사를 '잘라내고' 하위 backend 에 넘긴다.
#   routes={"/skills/": store} 로 두면
#   read_file("/skills/a/SKILL.md") -> store 에는 "/a/SKILL.md" 로 전달되는데
#   DB 에 저장된 키는 "/skills/a/SKILL.md" 라서 서로 안 맞는다. (skill 을 못 찾음)
# 그래서 route 는 "/db/" 로 두고, skill 탐색 경로를 "/db/skills/" 로 잡는다.
#   read_file("/db/skills/a/SKILL.md") -> store 에는 "/skills/a/SKILL.md" 로 전달 -> 일치
# 이렇게 하면 main.py 가 쓰는 DB 키 체계를 그대로 두고 같은 데이터를 공유할 수 있다.
DB_ROUTE = "/db/"
SKILL_DISCOVERY_PATH = f"{DB_ROUTE.rstrip('/')}{SKILLS_ROOT}"   # "/db/skills/"

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


# ─────────────────────────────────────────────────────────────────
# 1. 공통 도우미
# ─────────────────────────────────────────────────────────────────

def get_conn_string() -> str:
    """.env 값으로 psycopg 키워드 형식 접속 문자열을 만든다.

    비밀번호에 특수문자가 있어도 안전한 형식이라 URL 형식 대신 이걸 쓴다.
    """
    return (
        f"host={os.environ['PG_HOST']} "
        f"port={os.environ['PG_PORT']} "
        f"dbname={os.environ['PG_DB']} "
        f"user={os.environ['PG_USER']} "
        f"password={os.environ['PG_PASSWORD']}"
    )


def get_text(msg) -> str:
    """LLM 메시지에서 사람이 읽을 텍스트만 뽑아낸다.

    content 는 str 일 때도 있고 여러 조각(dict)의 list 일 때도 있어서 둘 다 처리한다.
    """
    content = getattr(msg, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
    return str(content)


def indent(text: str, prefix: str = "      ") -> str:
    """여러 줄 문자열의 각 줄 앞에 prefix 를 붙인다."""
    return "\n".join(prefix + line for line in text.splitlines())


# ─────────────────────────────────────────────────────────────────
# 2. [0단계] 시딩 — 레포의 skills/ 폴더를 DB 에 올린다
#    ※ 이건 '검증 대상'이 아니라 '테스트 사전 준비'다.
#      main.py 의 시딩 로직과 같은 일을 하지만 LLM 호출이 없다.
# ─────────────────────────────────────────────────────────────────

def seed_skills_to_db(backend: StoreBackend, skills_dir: Path) -> None:
    """레포 skills/ 하위의 모든 파일(SKILL.md + script)을 DB 에 업로드한다.

    store.put() 이 upsert 라서 몇 번을 돌려도 중복 없이 내용만 갱신된다.
    """
    files_to_upload = []

    # SKILL.md 뿐 아니라 .py 같은 부속 파일까지 전부 올린다.
    for skill_file in skills_dir.rglob("*"):
        if not skill_file.is_file():
            continue

        # 실제 경로(/Users/.../skills/prime-check/SKILL.md)를
        # 가상 경로(/skills/prime-check/SKILL.md)로 바꾼다.
        # 실행 환경마다 달라지는 절대경로를 DB 에 넣지 않기 위한 정규화다.
        rel = skill_file.relative_to(skills_dir).as_posix()
        store_path = f"{SKILLS_ROOT}{rel}"

        content = skill_file.read_text(encoding="utf-8")
        files_to_upload.append((store_path, content.encode("utf-8")))

    backend.upload_files(files_to_upload)
    print(f"[0단계] DB 시딩 완료 — {len(files_to_upload)}개 파일")


# ─────────────────────────────────────────────────────────────────
# 3. 전송 로직 — DB 에서 script 를 읽어 실행 공간 경로로 바꾼다
#    ※ 여기 두 함수는 skills/ 디스크 폴더를 '절대' 참조하지 않는다.
#      그래야 workspace 에 파일이 생겼을 때 출처가 DB 뿐임이 증명된다.
# ─────────────────────────────────────────────────────────────────

def fetch_scripts_from_db(store, namespace: tuple) -> list[tuple[str, bytes]]:
    """DB 에서 .py 파일만 골라 [(가상경로, 내용 bytes)] 로 돌려준다.

    C 계획(Code Interpreter)에서도 그대로 재사용될 부분이다. 읽는 쪽은 안 바뀐다.
    """
    scripts = []

    # limit 를 안 주면 기본 10개만 나온다. skill 이 늘면 조용히 잘리므로 명시한다.
    for item in store.search(namespace, limit=SEARCH_LIMIT):
        if not item.key.endswith(".py"):
            continue

        # value 는 dict 이고, 파일 내용은 content 키에 들어 있다.
        # encoding 은 utf-8(텍스트) 또는 base64(바이너리)다.
        value = item.value
        content_str = value["content"]
        encoding = value.get("encoding", "utf-8")

        if encoding == "base64":
            content_bytes = base64.standard_b64decode(content_str)
        else:
            content_bytes = content_str.encode("utf-8")

        scripts.append((item.key, content_bytes))

    return scripts


def to_disk_path(workspace: Path, store_key: str) -> Path:
    """가상 경로를 workspace 안의 실제 파일 경로로 바꾼다.

        /skills/prime-check/scripts/is_prime.py
     -> <workspace>/skills/prime-check/scripts/is_prime.py

    앞 슬래시만 떼면 SKILL.md 가 지시하는 상대경로
    (python skills/prime-check/scripts/is_prime.py)와 정확히 맞아떨어진다.
    덕분에 SKILL.md 를 고칠 필요가 없다.

    C 계획에서는 이 함수가 교체된다. (디스크 경로 대신 Interpreter 페이로드)
    """
    return workspace / store_key.lstrip("/")


# ─────────────────────────────────────────────────────────────────
# 4. 미들웨어 — Agent 실행 '직전'에 전송을 수행한다
# ─────────────────────────────────────────────────────────────────

class ScriptTransferMiddleware(AgentMiddleware):
    """before_agent 훅에서 DB 의 script 를 workspace 로 복사하는 미들웨어.

    복사는 backend.upload_files() 가 아니라 Path.write_bytes() 로 직접 한다.
    CompositeBackend 는 route 에 걸리는 경로를 StoreBackend(DB)로 보내버리므로,
    upload_files 로 보내면 디스크가 아니라 DB 로 되돌아가기 때문이다.
    """

    # 재료 보관 - 미들웨어를 만들 때 3가지를 받아서 기억해둔다.
    def __init__(self, store, namespace: tuple, workspace: Path) -> None:
        super().__init__()
        self.store = store # DB 창구 
        self.namespace = namespace # DB의 어느 서랍인지
        self.workspace = workspace # 파일을 어디에 쓸지 

    # 실제로 하는 일 - agent.invoke() 직전에 자동 호출이 됨. (deepagents가 자동으로 먼저 부른다. 우리가 호출하지 않는다.)
    def before_agent(self, state, runtime) -> None:
        """Agent 가 돌기 직전에 한 번 호출된다."""
        scripts = fetch_scripts_from_db(self.store, self.namespace) # DB에서 .py 가져오기

        for store_key, content_bytes in scripts:
            disk_path = to_disk_path(self.workspace, store_key) # 어디에 쓸지 경로 계산
            disk_path.parent.mkdir(parents=True, exist_ok=True) # 폴더 없으면 만든다.
            disk_path.write_bytes(content_bytes) # 파일로 쓴다.

            print(f"  [전송] DB {store_key}  ->  {disk_path}")

        print(f"[2단계] 전송 완료 — script {len(scripts)}개")
        return None  # state 를 바꾸지 않으므로 None


# ─────────────────────────────────────────────────────────────────
# 5. backend 조립
# ─────────────────────────────────────────────────────────────────

def build_backend(store, workspace: Path) -> CompositeBackend:
    """읽기는 DB, 실행은 디스크로 가도록 두 backend 를 합친다.

      read_file("/db/skills/...")  -> 경로가 route 에 걸림 -> StoreBackend -> DB
      execute("python skills/...") -> 실행은 라우팅 대상이 아님 -> 항상 default

    execute 가 항상 default 로 가는 건 CompositeBackend 의 정해진 동작이다.
    ("execution is not path-routable — it always delegates to the default backend")
    """
    store_backend = StoreBackend(
        namespace=lambda _rt: SKILLS_NAMESPACE,
        store=store,
    )

    # root_dir 이 셸의 작업 디렉터리(cwd)가 된다.
    # 반드시 '빈 임시 폴더'여야 한다. 레포 루트로 두면 이미 파일이 있어서
    # 전송을 안 해도 실행이 성공해 버리고, 그러면 아무것도 증명하지 못한다.
    shell_backend = LocalShellBackend(
        root_dir=str(workspace),
        virtual_mode=True,
        inherit_env=True,
    )

    return CompositeBackend(
        default=shell_backend, # 아래에 안 걸리면 전부 이 곳에서 
        routes={DB_ROUTE: store_backend}, # /db/로 시작하면 DB로
    )


# ─────────────────────────────────────────────────────────────────
# 6. 테스트 실행 및 판정
# ─────────────────────────────────────────────────────────────────

# (질문, 기대 skill 이름, execute 결과에 나와야 할 문자열)
TEST_CASES = [
    ("97은 소수야?", "prime-check", "PRIME"),
    ("hello world 의 SHA-256 해시값 알려줘", "text-hash", "SHA256="),
    ("2026-01-01 부터 2026-09-09 까지 며칠이야?", "date-diff", "DAYS="),
]


def run_tests(agent) -> None:
    """질문을 하나씩 던지고, SKILL.md 를 읽었는지 / script 를 실행했는지 판정한다.

    판정은 tool_calls 가 아니라 ToolMessage(도구 실행 '결과')를 기준으로 한다.
    게이트웨이가 tool_calls 의 args 를 비워서 보내는 경우가 있어 결과로 보는 게 안정적이다.
    """
    for i, (question, expected_skill, expected_token) in enumerate(TEST_CASES, start=1):
        print(f"\n{'=' * 64}\n[{i}] 질문: {question}\n    기대 Skill: {expected_skill}")

        result = agent.invoke(
            {"messages": [{"role": "user", "content": question}]},
            config={"configurable": {"thread_id": f"exec-shell-{i}"}},
        )

        """
        agent.invoke()의 결과 result["messages"]에는 대화 기록 전체가 들어 있습니다.
        HumanMessage   ← 사람 질문 ("97은 소수야?")
        AIMessage      ← AI가 "read_file 도구 쓸게" 하고 요청
        ToolMessage    ← 도구가 실제로 실행된 '결과' (SKILL.md 본문)
        AIMessage      ← AI가 "execute 도구 쓸게" 하고 요청
        ToolMessage    ← 도구 실행 결과 ("PRIME")
        AIMessage      ← 최종 답변
        """

        skill_read = False      # SKILL.md 를 읽었는가 (= skill 이 선택됐는가)
        script_ran = False      # script 가 실제로 실행됐는가
        script_output = ""

        for msg in result["messages"]:
            if not isinstance(msg, ToolMessage): # Tool Message가 아니면 건너 뜀.
                continue

            tool_name = getattr(msg, "name", "")
            tool_result = get_text(msg)

            # SKILL.md 본문에는 'name: <skill 이름>' 프론트매터가 들어 있다.
            if tool_name == "read_file" and f"name: {expected_skill}" in tool_result:
                skill_read = True

            # execute 결과에 기대한 출력 토큰(PRIME / SHA256= / DAYS=)이 있는지 본다.
            if tool_name == "execute" and expected_token in tool_result:
                script_ran = True
                script_output = tool_result.strip()

        print(f"    → SKILL.md 읽음? : {'예' if skill_read else '아니오'}")
        print(f"    → script 실행됨?  : {'예' if script_ran else '아니오'}")
        if script_output:
            print(f"    → script 출력      : {script_output[:120]}")

        print(f"    → LLM 최종 답변:\n{indent(get_text(result['messages'][-1]))}")

        if SHOW_FULL:
            print("    ── 전체 대화 흐름 ──")
            for msg in result["messages"]:
                text = get_text(msg).strip()
                if text:
                    print(f"      [{type(msg).__name__}] {text[:200]}")


# ─────────────────────────────────────────────────────────────────
# 7. 실행부
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # ── [0-2단계] 빈 임시 폴더 생성 ──
    # 자동 삭제하지 않는다. 실패했을 때 안을 들여다봐야 하기 때문이다.
    workspace = Path(tempfile.mkdtemp(prefix="skills_exec_"))
    print(f"[0단계] workspace 생성: {workspace}")

    # 실험 유효성 확인: 시작 시점에 폴더가 비어 있어야 한다.
    before_files = list(workspace.rglob("*"))
    print(f"[1단계] 전송 전 workspace 파일 수: {len(before_files)}개 (0이어야 정상)")

    model = ChatOpenAI(
        model=os.environ["LLM_MODEL"],
        base_url=os.environ["LLM_API_ADDRESS"],
        api_key=os.environ.get("LLM_API_KEY") or "EMPTY",
    )

    with PostgresStore.from_conn_string(get_conn_string()) as store:
        store.setup()

        # ── [0-1단계] 레포 skills/ 를 DB 에 시딩 ──
        seed_backend = StoreBackend(namespace=lambda _rt: SKILLS_NAMESPACE, store=store)
        seed_skills_to_db(seed_backend, ROOT / "skills")

        # ── [1단계] backend 조립 (읽기=DB, 실행=디스크) ──
        backend = build_backend(store, workspace)

        # ── [2단계] 전송 미들웨어를 달아 Agent 생성 ──
        #    before_agent 는 agent.invoke() 직전에 자동으로 호출된다.
        agent = create_deep_agent(
            model=model,
            backend=backend,
            skills=[SKILL_DISCOVERY_PATH],
            middleware=[ScriptTransferMiddleware(store, SKILLS_NAMESPACE, workspace)],
            checkpointer=MemorySaver(),
        )

        # ── [3~4단계] 실행 및 판정 ──
        run_tests(agent)

    # ── 마무리: 전송 결과 확인 ──
    after_files = [p for p in workspace.rglob("*") if p.is_file()]
    print(f"\n{'=' * 64}")
    print(f"[최종] workspace 에 생성된 파일 {len(after_files)}개:")
    for p in sorted(after_files):
        print(f"  {p.relative_to(workspace)}")
    print(f"\nworkspace 경로(자동 삭제 안 함): {workspace}")