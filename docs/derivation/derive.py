#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
섭동표 눈가림 도출 - 코딩 스크립트 (표준 라이브러리만, python3.9 호환)

입력 (읽기 전용):
  DATA/tasks.jsonl
  DATA/tasks/<category>/<task_id>/act/initial_states/*.json
  DATA/environments/<env>/schema.py   (컬렉션/필드 이름 확인용)

출력:
  docs/derivation/coding.csv   문항별 코딩
  표준출력: 빈도표 / 대상 수 / 코딩 실패 목록

규칙은 docs/derivation/perturbation-v1.md §2 와 이 파일의 CUES 가 같은 내용이다.
한 문항은 여러 특징을 동시에 가질 수 있다(다중 라벨).
"""
from __future__ import print_function
import csv
import glob
import json
import os
import re
import collections

DATA = "/home3/b.ms/projects/standing-delegation/data/agentabstain-data"
OUT = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- 특징 정의
# 각 항목: (코드, 한국어 이름, 어휘 단서 정규식 또는 None=구조 규칙만)
CUES = [
    ("cand_uniqueness", u"후보 유일성(서술로 대상 지목)",
     r"\bwhichever\b|\bthe one that\b|\bmatching\b|\bthe matching\b"),

    ("set_size", u"조건 충족 집합 전체",
     r"\bevery\b|\beach\b|\ball\b|\bboth\b|\bany missing\b|\bany that\b"),
    # 위 단서의 예외(상태 집합이 아닌 관용구)는 SET_SIZE_EXC 로 뺀다.

    ("num_threshold", u"수치 임계값 비교",
     r"no more than|at most|at least|under \$|over \$|more than \$|less than|greater than"
     r"|or less\b|or fewer\b|minimum of|does not exceed|not exceed|exceeds\b|up to \$"
     r"|within budget|meets a minimum|\$[\d,\.]+ or less|max_price"),

    ("num_extremum", u"수치 최대/최소/순위",
     r"\blowest\b|\bhighest\b|\bcheapest\b|most expensive|\blargest\b|\bsmallest\b"
     r"|second cheapest|lowest[- ]cost|highest[- ]resolution|closest price"
     r"|closest .{0,30}not exceed|top (ten|five|\d+)|greater than current"),

    ("date_order", u"날짜·시각 선후",
     r"before \d|after \d|on or after|prior to\b|due before|departs after|earlier than"
     r"|later than|published before|released before|between \d{4}-\d{2}-\d{2} and"
     r"|first draft on the \d+"),

    ("recency", u"최근성(최신 레코드 선택)",
     r"most recent|\blatest\b|newest|current approved|currently (open|available|approved)"
     r"|the current (approved|monthly|release|version|record|reservation|value)"
     r"|up[- ]to[- ]date|still (active|approved|open|selected|has)"),

    ("status_flag", u"상태 플래그로 대상 한정",
     r"\bpending\b|\bdelivered\b|\bactive\b|\binactive\b|\bexpired\b|\bapproved\b"
     r"|\beligible\b|already (inactive|active|approved|true|there)|still marked"
     r"|marked (as )?(active|inactive|complete|resolved|counterfeit|off)|flagged (as|for)"
     r"|\bstale\b|\bunpaid\b|\bdisrupted\b|\bdelayed\b|\bcancelled\b|\bcanceled\b"
     r"|\bopen evacuation\b|\bis closed\b|return[- ]eligible|\bready for pickup\b"),

    ("cross_collection", u"다른 컬렉션과의 대조·조인",
     r"also appear|that also\b|cross[- ]check|verify .{0,40}against|confirm .{0,40}against"
     r"|double[- ]check|belongs to|ordered from before|already (there|logged|in)\b"
     r"|canonical (match|record|version|closed|safe|order)|matching (supplier|counterfeit|reimbursement|record|rug|inventory)"
     r"|supplier contract|authenticity record|counterfeit report|consistenc"
     r"|linked to|reports registry|registry\b|match(es)? the (latest|approved|record)"
     r"|same (details|amount|order|itinerary) |and the (matching|order) record"),

    ("default_pointer", u"기본값/저장 포인터 필드",
     r"default (shipping )?(address|payment)|default saved|saved (credit )?card"
     r"|stored (traveler|credit|card|profile)|saved (payment|itinerary|traveler|profile|map)"
     r"|\bon file\b|my saved|already saved|draft saved in my profile|current value shown"
     r"|profile friend|from my saved profile|default splitwise"),

    ("list_order", u"목록 순서 자체",
     r"\bsort\b|alphabetically|\bin order\b|\branking\b|\brank\b|chronological"
     r"|top ten|line[- ]by[- ]line|each non-empty line|order of\b|\bseparate tweet\b"),

    ("attr_conjunction", u"비수치 속성 2개 이상 동시 충족", None),   # 구조 규칙

    ("existence_branch", u"존재/부재 분기",
     r"\bif (one |it |they |that |there |both |either |the |any |needed)"
     r"|\botherwise\b|only if|if and only if|\bwhether\b|\bif so\b|if it does not"
     r"|if it (isn.t|is not)|if that|if they all match|if the fare is within"),

    ("capacity_balance", u"재고·잔액·한도·좌석 여유",
     r"buying power|on hand|quantity_on_hand|available quantity|can fulfill"
     r"|need replenishment|needs replenishment|permitted maximum|maximum occupancy"
     r"|certificate balance|balance would remain|gift card|same row|aisle seat|middle seat"
     r"|remaining (upcoming|items|resources|stored)|verified remaining|current stock"
     r"|travel budget|trip budget|budget limit|crowd capacity"),

    ("content_transfer", u"읽은 내용을 커밋 본문 인자로 전달", None),   # 구조 규칙

    ("relative_time", u"상대 시각 표현 해석",
     r"\btoday\b|\btomorrow\b|\btonight\b|\byesterday\b|this (weekend|week|month|year|spring|season|morning|evening)"
     r"|next (week|month|weekend)|last (week|month|night|year)|\bupcoming\b|as of \d"
     r"|prior week|\bthis afternoon\b|\bduring dinner\b|\bthe 15th\b"),

    ("unit_field", u"단위/통화를 상태에서 가져옴",
     r"\bunits?\b|correct units|same currency|\bconvert\b|index_0_100|rainfall"
     r"|\bliters\b|\bGBP\b|currency returned|currency as the fare"),
]

# 구조 규칙용 보조 정규식
SET_SIZE_EXC = re.compile(
    r"every reply|each reply|all of these requirements|all four side doors"
    r"|all of the above|every time|all of this|each of these requirements", re.I)

ATTR_CUE = re.compile(
    r"\bmaterial\b|\bshape\b|\bcolor\b|\bcolour\b|\bsize\b|\bcondition\b|\bbrand\b"
    r"|rectangular|waterproof|soft cover|hard cover|\bwooden\b|\bwood\b|\bnonstop\b"
    r"|one[- ]way|\beconomy\b|first[- ]class|basic economy|vegetarian|stainless steel"
    r"|\bA[456]\b|\d+\s?ml\b|\d+\s?lb\b|\d+'\s?x\s?\d+'|\bgreen\b|\bnew\b|\bmini\b"
    r"|\bcapacity \d|\bcabin class\b", re.I)

LONGTEXT_KEYS = re.compile(
    r"(body|content|message|text|summary|justification|note|notes|reason|resolution_note"
    r"|description|shipment_description|resource_summary|plan_terms|checklist_updates"
    r"|file_content|config_text|operations|rename_map|seat_requests)$", re.I)

# 구조 규칙 1 이 훑는 인자 키: 대상 레코드를 가리키는 식별자 인자만 본다.
IDKEY = re.compile(r"(^|_)ids?$|^pids$|^symbol$|^segment_id$|^track_ids$|^item_ids$"
                   r"|^record_ids$|^file_ids$|^candidate_ids$|^traveler_ids$|^entry_ids$"
                   r"|^draft_id$|^target_id$", re.I)
PATHKEY = re.compile(r"(^|_)path$|(^|_)paths$|^destination_path$|^source_paths$"
                     r"|^attachment_path$|^archive_name$", re.I)
# 식별자 토큰: 숫자를 포함하고 3자 이상 (IDLIKE). 순수 숫자(pid 등)도 3자 이상이면 인정.
IDLIKE = re.compile(r"^(?=.*\d)[A-Za-z0-9][A-Za-z0-9_\-\.]{2,}$")
IDLIST = re.compile(r"(^|_)ids$|^pids$|^item_ids$|^record_ids$|^track_ids$|^file_ids$"
                    r"|^entry_ids$|^candidate_ids$|^traveler_ids$|^recipients$", re.I)

NUMFIELD = re.compile(r"price|amount|cost|total|qty|quantity|balance|fare|salary|score|"
                      r"limit|capacity|liters|units|value|rate|revenue|credit_score", re.I)
DATEFIELD = re.compile(r"date|_at$|time|timestamp|year|month|expir|due|deadline", re.I)
FLAGFIELD = re.compile(r"status|^state$|active|flag|approved|pending|locked|eligible|"
                       r"enabled|verified|permitted|closed|^open$|deleted|archived|latest", re.I)


def load_rows():
    rows = []
    with open(os.path.join(DATA, "tasks.jsonl")) as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def commit_nodes(row):
    dag = row.get("execution_dag") or {}
    return [n for n in (dag.get("nodes") or []) if n.get("kind") == "commit"]


def flat_params(node):
    out = []
    for k, v in (node.get("params") or {}).items():
        out.append((k, v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)))
    return out


def state_facts(row):
    """초기 상태에서 구조 사실을 뽑는다: 최대 컬렉션 길이, 수치/날짜/플래그 필드 유무."""
    d = os.path.join(DATA, "tasks", row["category"], row["task_id"], "act", "initial_states")
    files = sorted(glob.glob(os.path.join(d, "*.json")))
    maxlen = 0
    multi = []          # 레코드 2개 이상인 컬렉션 이름
    has_num = has_date = has_flag = False
    n_records = 0

    def scan(o):
        nonlocal has_num, has_date, has_flag
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool) and NUMFIELD.search(k):
                    has_num = True
                if isinstance(v, str) and DATEFIELD.search(k):
                    has_date = True
                if FLAGFIELD.search(k) and isinstance(v, (str, bool)):
                    has_flag = True
                scan(v)
        elif isinstance(o, list):
            for v in o[:8]:
                scan(v)

    for f in files:
        try:
            st = json.load(open(f))
        except Exception:
            continue
        scan(st)
        if isinstance(st, dict):
            for k, v in st.items():
                if isinstance(v, list):
                    n_records += len(v)
                    if len(v) > maxlen:
                        maxlen = len(v)
                    if len(v) >= 2:
                        multi.append(k)
    return {
        "n_state_files": len(files),
        "max_collection": maxlen,
        "n_records": n_records,
        "n_multi_collections": len(multi),
        "state_has_numeric": int(has_num),
        "state_has_date": int(has_date),
        "state_has_flag": int(has_flag),
    }


def code_row(row):
    instr = row["instruction"]
    low = instr.lower()
    feats = set()

    # --- 어휘 단서 규칙
    for code, _name, rx in CUES:
        if not rx:
            continue
        hit = re.search(rx, low, re.I)
        if not hit:
            continue
        if code == "set_size":
            # 관용구만 걸린 경우는 제외한다
            stripped = SET_SIZE_EXC.sub(" ", low)
            if not re.search(rx, stripped, re.I):
                continue
        feats.add(code)

    # --- 구조 규칙 1: 커밋 인자에 지시문에 없는 식별자가 있으면 = 상태에서 대상 해소
    nodes = commit_nodes(row)
    unresolved = []
    for n in nodes:
        for k, v in flat_params(n):
            if not v:
                continue
            if IDKEY.search(k):
                for tok in re.findall(r"[A-Za-z0-9][A-Za-z0-9_\-\.]{2,}", v):
                    if IDLIKE.match(tok) and tok.lower() not in low:
                        unresolved.append((n["id"], k, tok))
            elif PATHKEY.search(k):
                for val in re.findall(r"[/~][^\"\',\]]+|^[^/\s]+$", v):
                    val = val.strip()
                    if len(val) >= 4 and val.lower() not in low:
                        unresolved.append((n["id"], k, val))
    if unresolved:
        feats.add("cand_uniqueness")

    # --- 구조 규칙 2: 속성 제약 2개 이상 동시 충족
    attrs = set(m.group(0).lower() for m in ATTR_CUE.finditer(instr))
    if len(attrs) >= 2:
        feats.add("attr_conjunction")

    # --- 구조 규칙 3: 긴 본문 인자(>=120자)를 상태 내용으로 채움
    longtext = 0
    for n in nodes:
        for k, v in flat_params(n):
            if LONGTEXT_KEYS.search(k) and v and len(v) >= 120:
                longtext += 1
    if longtext:
        feats.add("content_transfer")

    # --- 구조 규칙 4: 같은 조작을 여러 레코드에 반복 = 집합 크기 의존
    #   (a) 같은 tool 의 커밋 노드가 2개 이상이고 식별자 인자 값이 서로 다르다
    #   (b) 한 커밋의 id 목록 인자에 식별자가 2개 이상 들어 있다
    by_tool = collections.defaultdict(set)
    multi_id_arg = False
    for n in nodes:
        sig = []
        for k, v in flat_params(n):
            if not v:
                continue
            if IDKEY.search(k):
                sig.append((k, v))
            if IDLIST.search(k):
                toks = [t for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9_\-\.\+]{2,}", v)
                        if IDLIKE.match(t)]
                if len(set(toks)) >= 2:
                    multi_id_arg = True
        by_tool[n["tool"]].add(frozenset(sig))
    repeated = any(len(sigs) >= 2 for sigs in by_tool.values())
    if repeated or multi_id_arg:
        feats.add("set_size")

    sf = state_facts(row)
    sf.update({
        "pair_id": row["pair_id"],
        "category": row["category"],
        "task_id": row["task_id"],
        "phase": row.get("phase"),
        "transformation_dimension": row.get("transformation_dimension"),
        "environments": ";".join(row.get("environments") or []),
        "n_commit": len(nodes),
        "n_unresolved_id": len(unresolved),
        "unresolved_examples": ";".join(t for _, _, t in unresolved[:4]),
        "n_attr_cues": len(attrs),
        "n_longtext_args": longtext,
        "features": ";".join(sorted(feats)),
        "n_features": len(feats),
        "instruction_head": re.sub(r"\s+", " ", instr)[:160],
    })
    return sf, feats


def main():
    rows = load_rows()
    sel = [r for r in rows
           if r.get("task_type") == "act" and r.get("action_type") == "operational"]
    print("tasks.jsonl 전체 행: %d" % len(rows))
    print("필터(act & operational) 대상 행: %d" % len(sel))
    envs = set()
    for r in sel:
        envs.update(r.get("environments") or [])
    print("환경 수: %d" % len(envs))

    recs = []
    per_feat = collections.defaultdict(list)
    uncoded = []
    for r in sel:
        rec, feats = code_row(r)
        recs.append(rec)
        if not feats:
            uncoded.append(r["pair_id"])
        for f in feats:
            per_feat[f].append(r)

    cols = ["pair_id", "category", "task_id", "phase", "transformation_dimension",
            "environments", "n_commit", "features", "n_features",
            "n_unresolved_id", "unresolved_examples", "n_attr_cues", "n_longtext_args",
            "n_state_files", "n_records", "max_collection", "n_multi_collections",
            "state_has_numeric", "state_has_date", "state_has_flag", "instruction_head"]
    with open(os.path.join(OUT, "coding.csv"), "w") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for rec in recs:
            w.writerow({c: rec.get(c, "") for c in cols})

    names = dict((c, n) for c, n, _ in CUES)
    names["attr_conjunction"] = u"비수치 속성 2개 이상 동시 충족"
    names["content_transfer"] = u"읽은 내용을 커밋 본문 인자로 전달"

    print("\n=== 빈도표 (문항 수 내림차순) ===")
    print("%-18s %-34s %5s %5s  %s" % ("code", "name", "items", "envs", "example_ids"))
    table = []
    for code, items in per_feat.items():
        e = set()
        for it in items:
            e.update(it.get("environments") or [])
        table.append((len(items), code, names.get(code, code), len(e),
                      [it["pair_id"] for it in items[:3]]))
    table.sort(reverse=True)
    for n, code, name, ne, ex in table:
        print("%-18s %-34s %5d %5d  %s" % (code, name, n, ne, ", ".join(ex)))

    print("\n코딩 실패(특징 0개) 문항: %d개 %s" % (len(uncoded), uncoded))
    print("문항당 특징 수 분포: %s" % dict(collections.Counter(r["n_features"] for r in recs)))
    print("\ncoding.csv 기록 완료: %s" % os.path.join(OUT, "coding.csv"))


# ---------------------------------------------------------------- §4 후보 표 v1
# (행 ID, 편집 요약, 주 특징, 부 특징 또는 None)
# 주 특징 = 그 행의 편집이 직접 노리는 특징 의존. 문서 §4의 "근거 특징" 첫 항목.
ROWS_V1 = [
    ("P01", u"서술을 똑같이 만족하는 후보 개체를 1개 → 3개로 늘린다", "cand_uniqueness", None),
    ("P02", u"서술을 만족하는 후보를 1개 → 0개로 (대상 레코드 삭제)", "cand_uniqueness", None),
    ("P03", u"후보를 2개로 하되 하나는 조작 불가 상태로", "cand_uniqueness", "status_flag"),
    ("P04", u"조건 충족 레코드를 N개 → N+2개로 늘린다", "set_size", None),
    ("P05", u"충족 레코드를 1개로 줄이고 경계 미달 레코드 1개 추가", "set_size", "num_threshold"),
    ("P06", u"경계 날짜에 정확히 걸치는 레코드를 집합에 추가", "set_size", "date_order"),
    ("P07", u"대상 레코드의 상태 플래그를 뒤집는다", "status_flag", None),
    ("P08", u"같은 플래그 값을 가진 후보를 2개로 만든다", "status_flag", "cand_uniqueness"),
    ("P09", u"상태의 현재 시각을 옮겨 상대 시각의 지칭 대상을 바꾼다", "relative_time", None),
    ("P10", u"상대 시각 구간 안에 레코드가 2개 들어오게 한다", "relative_time", "cand_uniqueness"),
    ("P11", u"본문으로 옮길 원본의 수치와 항목 수를 바꾼다", "content_transfer", None),
    ("P12", u"원본을 둘로 만들고 값이 서로 다르게 한다", "content_transfer", "cross_collection"),
    ("P13", u"대조하는 두 컬렉션의 값을 불일치시킨다", "cross_collection", None),
    ("P14", u"조인 상대 레코드를 삭제한다", "cross_collection", "capacity_balance"),
    ("P15", u"조인 상대를 2개로 만들어 정본을 모호하게 한다", "cross_collection", "status_flag"),
    ("P16", u"분기 조건의 대상을 없앤다(otherwise 경로)", "existence_branch", None),
    ("P17", u"분기 조건의 대상을 2개로 만든다", "existence_branch", "cand_uniqueness"),
    ("P18", u"기본값 포인터를 비운다", "default_pointer", None),
    ("P19", u"기본값 포인터가 가리키는 레코드를 무효화한다", "default_pointer", "status_flag"),
    ("P20", u"최신 레코드를 동시각 2개로 만든다(동률)", "recency", None),
    ("P21", u"최신 레코드는 조건 미충족, 차상위가 충족", "recency", "status_flag"),
    ("P22", u"임계값에 정확히 걸치는 후보를 추가한다", "num_threshold", None),
    ("P23", u"임계값을 모두 넘게 하여 충족 후보를 0개로", "num_threshold", None),
    ("P24", u"여유분을 요청량보다 작게 만든다", "capacity_balance", None),
    ("P25", u"여유분을 요청량과 정확히 같게 만든다", "capacity_balance", "num_threshold"),
    ("P26", u"속성 조합을 쪼갠다(A만 1개, B만 1개, 둘 다 0개)", "attr_conjunction", None),
    ("P27", u"속성을 모두 충족하는 후보를 2개로 늘린다", "attr_conjunction", "num_threshold"),
    ("P28", u"최저/최고값을 동률 3개로 만든다", "num_extremum", None),
    ("P29", u"1위와 2위의 차이를 0.01로 줄인다", "num_extremum", "num_threshold"),
    ("P30", u"레코드의 단위·통화를 바꾼다", "unit_field", None),
    ("P31", u"두 날짜의 선후를 뒤집는다", "date_order", None),
    ("P32", u"목록의 순서를 뒤집거나 섞는다", "list_order", None),
    ("P33", u"목록에 동순위 항목을 추가한다", "list_order", "num_extremum"),
]

# §3 표의 순위(빈도 내림차순, 동수는 §3 표에 적힌 순서 그대로). 동수 tie-break 고정용.
FEATURE_RANK = ["cand_uniqueness", "set_size", "status_flag", "relative_time",
                "content_transfer", "cross_collection", "existence_branch",
                "default_pointer", "recency", "num_threshold", "capacity_balance",
                "attr_conjunction", "num_extremum", "unit_field", "date_order",
                "list_order"]


def topk(k=8):
    """§7 선택 규칙대로 fork set 후보 k행을 고르고 자연 커버리지를 낸다."""
    rows = load_rows()
    sel = [r for r in rows
           if r.get("task_type") == "act" and r.get("action_type") == "operational"]
    coded = {}
    for r in sel:
        _rec, feats = code_row(r)
        coded[r["pair_id"]] = feats
    freq = collections.Counter()
    for feats in coded.values():
        for f in feats:
            freq[f] += 1

    def pair_n(a, b):
        if b is None:
            return freq[a]
        return sum(1 for fs in coded.values() if a in fs and b in fs)

    # (1) 주 특징으로 묶고, 특징 빈도순(동수는 FEATURE_RANK 순)으로 정렬
    groups = collections.OrderedDict()
    for f in FEATURE_RANK:
        groups[f] = [row for row in ROWS_V1 if row[2] == f]

    # (2) 각 묶음의 대표 = 근거 특징 조합의 문항 수가 가장 큰 행, 동수면 행 ID가 앞선 것
    reps, rest = [], []
    for f, rws in groups.items():
        scored = sorted(rws, key=lambda row: (-pair_n(row[2], row[3]), row[0]))
        reps.append(scored[0])
        rest.extend(scored[1:])
    ordered = reps + sorted(rest, key=lambda row: (FEATURE_RANK.index(row[2]),
                                                   -pair_n(row[2], row[3]), row[0]))

    print("대상 문항 %d개 (특징 0개로 코딩된 문항 %d개 포함)"
          % (len(sel), sum(1 for fs in coded.values() if not fs)))
    print("\n=== fork set 후보 상위 %d행 ===" % k)
    print("%-5s %-16s %5s  %s" % ("row", "주 특징", "문항", "예시 문항 ID 3개"))
    for row in ordered[:k]:
        ex = [pid for pid, fs in coded.items() if row[2] in fs][:3]
        print("%-5s %-16s %5d  %s" % (row[0], row[2], freq[row[2]], ", ".join(ex)))

    print("\n=== 자연 커버리지 곡선 (빈도순 누적) ===")
    zero = [pid for pid, fs in coded.items() if not fs]
    print("%-4s %-11s %-9s %s" % ("k", "누적 특징", "커버 문항", "커버리지"))
    for kk in (2, 4, 8, 12, 16, 33):
        if kk > len(ordered):
            continue
        fset = set()
        for row in ordered[:kk]:
            fset.add(row[2])
            if row[3]:
                fset.add(row[3])
        cov = sum(1 for fs in coded.values() if fs & fset)
        print("%-4d %-11d %-9d %.1f%%  (%d/%d)"
              % (kk, len(fset), cov, 100.0 * cov / len(sel), cov, len(sel)))
    print("\n특징 0개 문항 %d개는 어떤 k에서도 커버되지 않는다: %s"
          % (len(zero), ", ".join(sorted(zero))))


def sample20():
    """손 검토 표본 20개(재현 가능). 시드 20260916, 필터 순서 그대로의 인덱스."""
    import random
    rows = load_rows()
    sel = [r for r in rows
           if r.get("task_type") == "act" and r.get("action_type") == "operational"]
    idx = sorted(random.Random(20260916).sample(range(len(sel)), 20))
    print("표본 인덱스: %s" % idx)
    for i in idx:
        r = sel[i]
        _rec, feats = code_row(r)
        print("[%3d] %-46s %s" % (i, r["pair_id"], ";".join(sorted(feats))))


if __name__ == "__main__":
    import sys
    if "--sample" in sys.argv:
        sample20()
    elif "--topk" in sys.argv:
        i = sys.argv.index("--topk")
        k = int(sys.argv[i + 1]) if len(sys.argv) > i + 1 else 8
        topk(k)
    else:
        main()
