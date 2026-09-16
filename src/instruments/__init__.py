"""계측기 (프로그램). 표준 라이브러리만 쓴다.

계약은 `docs/SCHEMA.md` v1이다. 계측기는 러너가 쓴 rollout 레코드와
delegation-author가 쓴 위임·상태 파일만 읽는다.

결과는 언제나 `execution_log`의 `result`에서 읽는다. `MultiEnvironment.call_tool`의
반환값은 일부 도구에서 None이다 (v1 `AGENTABSTAIN.md` §11 첫 단락, `docs/LOGIC.md` L12).

모듈
- `normalize`   값·인자·commit 호출 정규화, 다중집합 일치 판정(정확/부분/초과)
- `provenance`  U/W/M, in_K, fabricated, 선택 채움
- `commits`     commit 호출 추출(시도 포함/제외 두 판), commit_target, 산출물 동일성
- `policy_reader` 정책표 판독기(D-013 새 규칙 + 옛 규칙 비교 모드)
- `exposure`    자리 노출 E_expose, 불일치 행 E_mismatch, 귀속=R, 분기점 가시성,
                쌍 레코드와 비율(`trigger_rate`·`conditional_exposure`·`exposure_rate`,
                귀속 규칙별·\\|V_D\\|별 층화)
- `gates`       게이트 전용(하네스 건전성, 판정기 신뢰도, 보고 누설 검사)

척도 하나에 함수 하나가 아니라 **사건 하나에 함수 하나**다. 촉발률과 불일치 행 비율은 사건이
같고 분모가 다르므로 `e_mismatch` 하나를 쓰고 분모만 갈아 끼운다(D-027 (3)). 자리 노출은
정책표와 B 예측 표에 같은 `e_expose`를 쓴다(D-011).
"""

__all__ = [
    "normalize",
    "provenance",
    "commits",
    "policy_reader",
    "exposure",
]
