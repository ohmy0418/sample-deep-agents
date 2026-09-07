import os
from dotenv import load_dotenv
import requests
from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI

load_dotenv()

def get_repo_info(owner: str, repo: str) -> dict:
    """GitHub 공개 저장소 정보를 가져온다. 저장소의 별 수·언어 등을 조회할 때 사용."""
    url = f"https://api.github.com/repos/{owner}/{repo}"

    try:
        response = requests.get(url, timeout=10)
    except requests.RequestException as e:
        return {"성공": False, "이유": f"요청 실패: {e}"}

    if response.status_code != 200:
        return {"성공": False, "상태코드": response.status_code, "이유": f"요청 실패: {response.text}"}

    data = response.json()
    return {
        "성공": True,
        "이름": data["full_name"],
        "별": data["stargazers_count"],
        "주언어": data["language"],
    }


model = ChatOpenAI(
    model=os.environ["LLM_MODEL"],
    base_url=os.environ["LLM_API_ADDRESS"],
    api_key=os.environ.get("LLM_API_KEY") or "EMPTY",
)

agent = create_deep_agent(
    model=model,
    tools=[get_repo_info],
    system_prompt="너는 개발자를 돕는 조수야.",
)

result = agent.invoke({"messages": [{"role": "user", "content": "langchain-ai/deepagents 저장소 별 몇 개야?"}]})

print(result["messages"][-1].content)