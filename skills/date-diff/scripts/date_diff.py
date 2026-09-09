"""
날짜 차이 계산 스크립트
=======================
사용법: python date_diff.py <시작날짜> <종료날짜>   (형식: YYYY-MM-DD)
출력  : DAYS=<정수>      (종료날짜 - 시작날짜, 음수면 종료날짜가 과거)
        WEEKDAY=<요일>   (종료날짜의 요일)

이 스크립트는 skill 이 실행하는 '실제 코드'다.
LLM 이 어림짐작으로 답하지 않고 이 코드를 돌려서 나온 결과를 쓰는지 확인하는 용도.
"""

import sys
from datetime import date

# date.weekday() 는 월요일=0 ... 일요일=6 을 돌려주므로, 그 순서에 맞춰 이름을 나열한다.
WEEKDAY_NAMES = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]


def parse_date(text: str) -> date:
    """'YYYY-MM-DD' 형식의 문자열을 date 객체로 바꾼다."""
    # fromisoformat 은 형식이 틀리면 ValueError 를 낸다. (호출한 쪽에서 처리)
    return date.fromisoformat(text)


def diff_days(start: date, end: date) -> int:
    """두 날짜의 차이를 일수로 돌려준다. 종료날짜가 과거면 음수가 된다."""
    return (end - start).days


def weekday_name(target: date) -> str:
    """날짜의 요일 이름(월요일~일요일)을 돌려준다."""
    return WEEKDAY_NAMES[target.weekday()]


if __name__ == "__main__":
    # 날짜 두 개가 필요하므로 인자가 2개 미만이면 사용법을 알리고 종료한다.
    if len(sys.argv) < 3:
        print("ERROR: 날짜 두 개를 인자로 넣어주세요. 예) python date_diff.py 2026-01-01 2026-09-09")
        sys.exit(1)

    try:
        start_date = parse_date(sys.argv[1])
        end_date = parse_date(sys.argv[2])
    except ValueError:
        print("ERROR: 날짜는 YYYY-MM-DD 형식으로 넣어주세요. 예) 2026-09-09")
        sys.exit(1)

    # 결과를 DAYS=<값>, WEEKDAY=<값> 형태로 명확히 출력 (skill 이 이 값을 읽는다)
    print(f"DAYS={diff_days(start_date, end_date)}")
    print(f"WEEKDAY={weekday_name(end_date)}")
