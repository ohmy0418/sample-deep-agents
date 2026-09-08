"""
소수 판별 스크립트
==================
사용법: python is_prime.py <정수>
출력  : PRIME (소수) 또는 NOT_PRIME (소수 아님)

이 스크립트는 skill 이 실행하는 '실제 코드'다.
LLM 이 암산으로 답하지 않고 이 코드를 돌려서 나온 결과를 쓰는지 확인하는 용도.
"""

import sys


def is_prime(n: int) -> bool:
    """n 이 소수이면 True, 아니면 False 를 돌려준다."""
    # 2보다 작은 수(1, 0, 음수)는 소수가 아니다
    if n < 2:
        return False
    # 2부터 n의 제곱근까지 나눠떨어지는 수가 있으면 소수가 아니다
    i = 2
    while i * i <= n:
        if n % i == 0:
            return False
        i += 1
    return True


if __name__ == "__main__":
    # 명령행에서 넘어온 인자(숫자)를 받는다. sys.argv[0]은 파일명이라 [1]이 숫자.
    if len(sys.argv) < 2:
        print("ERROR: 판별할 숫자를 인자로 넣어주세요. 예) python is_prime.py 97")
        sys.exit(1)

    try:
        number = int(sys.argv[1])
    except ValueError:
        print("ERROR: 정수만 넣을 수 있습니다.")
        sys.exit(1)

    # 결과를 PRIME / NOT_PRIME 로 명확히 출력 (skill 이 이 값을 읽는다)
    print("PRIME" if is_prime(number) else "NOT_PRIME")