"""
문자열 해시(SHA-256) 계산 스크립트
==================================
사용법: python hash_text.py <문자열>
출력  : SHA256=<64자리 16진수>

이 스크립트는 skill 이 실행하는 '실제 코드'다.
해시값은 LLM 이 추측으로 만들어낼 수 없으므로,
'스크립트를 진짜 실행했는지' 확인하는 데 가장 확실한 검증 수단이다.
"""

import hashlib
import sys


def sha256_of(text: str) -> str:
    """text 의 SHA-256 해시값을 64자리 16진수 문자열로 돌려준다."""
    # 문자열을 UTF-8 바이트로 바꾼 뒤 해시를 계산한다. (한글도 안전하게 처리됨)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    # 인자가 하나도 없으면 사용법을 알리고 종료한다.
    if len(sys.argv) < 2:
        print("ERROR: 해시를 계산할 문자열을 인자로 넣어주세요. 예) python hash_text.py hello")
        sys.exit(1)

    # 인자를 공백으로 이어붙인다.
    # 이렇게 하면 따옴표를 쓰든("hello world") 안 쓰든(hello world) 같은 결과가 나온다.
    text = " ".join(sys.argv[1:])

    # 결과를 SHA256=<값> 형태로 명확히 출력 (skill 이 이 값을 읽는다)
    print(f"SHA256={sha256_of(text)}")
