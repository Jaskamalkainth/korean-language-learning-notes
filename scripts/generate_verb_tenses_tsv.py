#!/usr/bin/env python3
"""
Generate a TSV directly from your notes:
Verb (dict.)    English meaning    Present    Past    Future

Inputs:
- All *.txt files in the repo (e.g., level1/, level2/, Korean-Language-Summary.txt, etc.)

Extraction:
- Looks for vocab-style lines with a Hangul head ending in '다' (dictionary form),
  optionally followed by romanization in []/() and/or an English gloss (→ / ->).

Conjugation target (해요체):
- Present polite: -(아/어)요
- Past polite: -(았/었)어요
- Future polite: -(으)ㄹ 거예요

Notes:
- For multi-word phrases, conjugates the final token (assumed verb/adjective).
- Handles a small set of common irregulars (하다, 르, ㅂ, ㄷ) plus key contractions.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple


BASE = 0xAC00

# Hangul Jungseong (vowel) indices
JUNG_A = {0, 2, 8, 9, 10, 11, 12}  # ㅏ,ㅑ,ㅗ,ㅘ,ㅙ,ㅚ,ㅛ -> use 아

# Irregulars/exceptions (minimal set relevant to beginner notes)
D_IRREGULAR = {"듣다", "걷다", "묻다"}
B_IRREGULAR_EXCEPT = {"입다"}  # ㅂ-batchim but NOT ㅂ-irregular
LEXICAL_IDA = {"보이다"}  # verbs that end with '이다' but are not copula
STOP_NOT_VERB = {"바다", "다"}  # common non-verb '...다' tokens found in notes

# Fallback meanings for common verbs that often appear in notes without an explicit English gloss.
# (Used only when we fail to extract a meaning from the notes.)
FALLBACK_ENGLISH: Dict[str, str] = {
    "건너다": "to cross",
    "나가다": "to go out",
    "나오다": "to come out",
    "내려가다": "to go down",
    "내려오다": "to come down",
    "들어가다": "to go in / enter",
    "들어오다": "to come in / enter",
    "올라가다": "to go up",
    "올라오다": "to come up",
    "지나다": "to pass",
}


def is_hangul_syllable(ch: str) -> bool:
    o = ord(ch)
    return 0xAC00 <= o <= 0xD7A3


def decompose_syllable(ch: str) -> Tuple[int, int, int]:
    """Return (cho, jung, jong) indices for a Hangul syllable."""
    code = ord(ch) - BASE
    cho = code // 588
    jung = (code % 588) // 28
    jong = code % 28
    return cho, jung, jong


def compose_syllable(cho: int, jung: int, jong: int) -> str:
    return chr(BASE + (cho * 588) + (jung * 28) + jong)


def last_hangul_syllable(s: str) -> Optional[Tuple[int, str]]:
    for i in range(len(s) - 1, -1, -1):
        if is_hangul_syllable(s[i]):
            return i, s[i]
    return None


def replace_last_syllable(s: str, new_ch: str) -> str:
    lh = last_hangul_syllable(s)
    if lh is None:
        return s
    idx, _ = lh
    return s[:idx] + new_ch + s[idx + 1 :]


def add_batchim_to_last_syllable(s: str, jong: int) -> str:
    lh = last_hangul_syllable(s)
    if lh is None:
        return s
    idx, ch = lh
    cho, jung, _jong = decompose_syllable(ch)
    return s[:idx] + compose_syllable(cho, jung, jong) + s[idx + 1 :]


def get_last_vowel_index(stem: str) -> Optional[int]:
    lh = last_hangul_syllable(stem)
    if lh is None:
        return None
    _, ch = lh
    _, jung, _ = decompose_syllable(ch)
    return jung


def get_prev_vowel_index(stem: str) -> Optional[int]:
    # Get vowel from the second-to-last Hangul syllable (for ㅡ irregular).
    count = 0
    for i in range(len(stem) - 1, -1, -1):
        if is_hangul_syllable(stem[i]):
            count += 1
            if count == 2:
                _, jung, _ = decompose_syllable(stem[i])
                return jung
    return None


def english_clean(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    # Prefer first segment before pipe.
    s = s.split("|", 1)[0].strip()
    # If it looks like "가요 (gayo) - go", keep the tail "go".
    if " - " in s:
        s = s.rsplit(" - ", 1)[-1].strip()
    return s


def expand_slashes(phrase: str) -> List[str]:
    phrase = phrase.strip()
    if "/" not in phrase:
        return [phrase]
    if " / " in phrase:
        return [p.strip() for p in phrase.split(" / ") if p.strip()]
    tokens = phrase.split()
    for idx, t in enumerate(tokens):
        if "/" in t:
            alts = [a.strip() for a in t.split("/") if a.strip()]
            out = []
            for a in alts:
                nt = tokens.copy()
                nt[idx] = a
                out.append(" ".join(nt).strip())
            return out
    return [p.strip() for p in phrase.split("/") if p.strip()]


def split_phrase_last_token(phrase: str) -> Tuple[str, str]:
    """
    Returns (prefix_with_space_or_empty, last_token)
    Example: "비가 오다" -> ("비가 ", "오다")
    """
    phrase = phrase.strip()
    if " " not in phrase:
        return ("", phrase)
    parts = phrase.split()
    last = parts[-1]
    prefix = " ".join(parts[:-1]).strip()
    return ((prefix + " ") if prefix else "", last)


def batchim_of_last_syllable(stem: str) -> Optional[int]:
    lh = last_hangul_syllable(stem)
    if lh is None:
        return None
    _, ch = lh
    _, _, jong = decompose_syllable(ch)
    return jong


def ao_form(dict_verb: str) -> Optional[str]:
    """
    Returns the 아/어 connective form (without 요), e.g.:
    가다 -> 가
    먹다 -> 먹어
    덥다 -> 더워
    하다 -> 해
    모르다 -> 몰라
    """
    dict_verb = dict_verb.strip()
    if not dict_verb.endswith("다"):
        return None

    # Copula: ...이다 (but exclude lexical verbs like 보이다)
    if dict_verb.endswith("이다") and dict_verb not in LEXICAL_IDA:
        noun = dict_verb[: -2]  # remove '이다'
        # Present copula is handled separately; ao_form not used.
        return None

    # 하다 / ...하다
    if dict_verb.endswith("하다"):
        stem = dict_verb[:-1]  # remove '다' -> "...하"
        # replace trailing '하' with '해'
        if stem.endswith("하"):
            return stem[:-1] + "해"
        return stem + "해"

    # Special: 그렇다
    if dict_verb == "그렇다":
        return "그래"

    stem = dict_verb[:-1]  # remove '다'

    # 르 irregular: ...르다
    if dict_verb.endswith("르다") and len(stem) >= 2:
        base = stem[:-1]  # drop '르'
        prev_v = get_last_vowel_index(base)
        use_a = prev_v in JUNG_A if prev_v is not None else False
        base_with_l = add_batchim_to_last_syllable(base, 8)  # ㄹ batchim
        return base_with_l + ("라" if use_a else "러")

    # ㄷ irregular (limited whitelist)
    if dict_verb in D_IRREGULAR:
        lh = last_hangul_syllable(stem)
        if lh:
            idx, ch = lh
            cho, jung, jong = decompose_syllable(ch)
            if jong == 7:  # ㄷ
                stem = stem[:idx] + compose_syllable(cho, jung, 8) + stem[idx + 1 :]  # ㄹ

    # ㅂ irregular
    if dict_verb not in B_IRREGULAR_EXCEPT:
        lh = last_hangul_syllable(stem)
        if lh:
            idx, ch = lh
            cho, jung, jong = decompose_syllable(ch)
            if jong == 17:  # ㅂ
                # Remove ㅂ and add 워/와
                stem_wo_b = stem[:idx] + compose_syllable(cho, jung, 0) + stem[idx + 1 :]
                use_wa = jung in {8, 9, 10, 11, 12}  # ㅗ-family
                return stem_wo_b + ("와" if use_wa else "워")

    # Regular: decide based on batchim/vowel with common contractions.
    last_v = get_last_vowel_index(stem)
    if last_v is None:
        return None
    jong = batchim_of_last_syllable(stem) or 0

    # If no batchim, apply contractions.
    if jong == 0:
        lh = last_hangul_syllable(stem)
        assert lh is not None
        idx, ch = lh
        cho, jung, _ = decompose_syllable(ch)

        # ㅏ, ㅓ, ㅐ, ㅔ: just stem (가 + 아 -> 가, 서 + 어 -> 서, 보내 + 어 -> 보내)
        if jung in {0, 4, 1, 5}:
            return stem

        # ㅗ -> ㅘ (보 -> 봐)
        if jung == 8:
            return stem[:idx] + compose_syllable(cho, 9, 0) + stem[idx + 1 :]  # ㅘ

        # ㅜ -> ㅝ (주 -> 줘)
        if jung == 13:
            return stem[:idx] + compose_syllable(cho, 14, 0) + stem[idx + 1 :]  # ㅝ

        # ㅣ -> ㅕ (마시 -> 마셔, 치 -> 쳐)
        if jung == 20:
            return stem[:idx] + compose_syllable(cho, 6, 0) + stem[idx + 1 :]  # ㅕ

        # ㅡ irregular: drop ㅡ and use previous vowel to choose 아/어
        if jung == 18:
            prev_v = get_prev_vowel_index(stem)
            use_a = prev_v in JUNG_A if prev_v is not None else False
            new_jung = 0 if use_a else 4  # ㅏ or ㅓ
            return stem[:idx] + compose_syllable(cho, new_jung, 0) + stem[idx + 1 :]

        # ㅟ (쉬다 -> 쉬어요): add 어 (no contraction to ㅕ/ㅝ)
        if jung == 15:
            return stem + "어"

        # Other vowels: just stem
        return stem

    # With batchim: append 아/어
    use_a = last_v in JUNG_A
    return stem + ("아" if use_a else "어")


def present_past_future(dict_phrase: str) -> Tuple[str, str, str]:
    """
    Returns (present, past, future) in polite style. Empty strings if unknown.
    """
    prefix, last = split_phrase_last_token(dict_phrase)
    if not last.endswith("다"):
        return ("", "", "")

    # Copula: N이다
    if last.endswith("이다") and last not in LEXICAL_IDA:
        noun = last[: -2]
        # Choose 이에요/예요 based on noun ending batchim.
        jong = batchim_of_last_syllable(noun) or 0
        present = prefix + (noun + ("이에요" if jong != 0 else "예요"))
        past = prefix + (noun + ("이었어요" if jong != 0 else "였어요"))
        future = prefix + (noun + "일 거예요")
        return (present, past, future)

    ao = ao_form(last)
    if not ao:
        return ("", "", "")
    present = prefix + (ao + "요")
    past = prefix + (add_batchim_to_last_syllable(ao, 20) + "어요")  # ㅆ batchim + 어요

    # Future:
    # - Use original final consonant of the stem to decide (으)ㄹ vs ㄹ.
    # - Apply ㄷ/ㅂ irregular changes before appending.
    stem = last[:-1]  # remove '다'
    orig_jong = batchim_of_last_syllable(stem) or 0

    # ㄷ irregular: ㄷ -> ㄹ before vowel (affects future '...을').
    if last in D_IRREGULAR and orig_jong == 7:
        lh = last_hangul_syllable(stem)
        if lh:
            idx, ch = lh
            cho, jung, jong = decompose_syllable(ch)
            stem = stem[:idx] + compose_syllable(cho, jung, 8) + stem[idx + 1 :]  # ㄹ

    # ㅂ irregular: remove ㅂ and add 우/오, then treat as vowel-ending + ㄹ.
    if last not in B_IRREGULAR_EXCEPT and orig_jong == 17:
        lh = last_hangul_syllable(stem)
        if lh:
            idx, ch = lh
            cho, jung, jong = decompose_syllable(ch)
            stem_wo_b = stem[:idx] + compose_syllable(cho, jung, 0) + stem[idx + 1 :]
            use_o = jung in {8, 9, 10, 11, 12}  # ㅗ-family
            stem = stem_wo_b + ("오" if use_o else "우")
            future_stem = add_batchim_to_last_syllable(stem, 8)
            future = prefix + (future_stem + " 거예요")
            return (present, past, future)

    if orig_jong == 0:
        future_stem = add_batchim_to_last_syllable(stem, 8)
        future = prefix + (future_stem + " 거예요")
    elif orig_jong == 8:  # ㄹ
        future = prefix + (stem + " 거예요")
    else:
        # Consonant-ending stem: add '을 거예요' (after irregular adjustment if any).
        future = prefix + (stem + "을 거예요")
    return (present, past, future)

RE_HANGUL_ONLY = re.compile(r"^[가-힣\s·/]+$")
RE_ROMAN_SQUARE = re.compile(r"\[([^\]]+)\]")
RE_ROMAN_PAREN = re.compile(r"\(([^)]+)\)")
RE_GLOSS_ARROW = re.compile(r"(?:→|->)\s*(.+)\s*$")
RE_BULLET_PREFIX = re.compile(r"^\s*(?:[-*]|\d+\.)\s*")
RE_DASH_MEANING_AFTER_ROMAN = re.compile(r"(?:\]|\))\s*[-–—]\s*([^|]+)")
# Inline extraction is intentionally limited to *single-word* romanization tokens (no spaces),
# to avoid mistakenly mapping meanings from multi-word phrases onto the final verb token.
RE_INLINE_BRACKET_ARROW = re.compile(r"([가-힣]+다)\s*\[[^\s\]]+\]\s*(?:→|->)\s*([^|\n]+)")
RE_INLINE_PAREN_DASH = re.compile(r"([가-힣]+다)\s*\([^\s)]+\)\s*[-–—]\s*([^|\n]+)")
RE_INLINE_PAREN_ARROW = re.compile(r"([가-힣]+다)\s*\([^\s)]+\)\s*(?:→|->)\s*([^|\n]+)")


@dataclass
class Entry:
    korean: str
    english: str = ""
    sources: Set[str] = None

    def __post_init__(self) -> None:
        if self.sources is None:
            self.sources = set()


def iter_note_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*.txt"):
        parts = {part.lower() for part in p.parts}
        if ".git" in parts or "node_modules" in parts:
            continue
        yield p


def normalize_korean_head(head: str) -> str:
    head = head.strip()
    head = re.sub(r"\s+", " ", head)
    head = head.strip(" \t-–—:;,.!?\"'“”‘’")
    return head


def extract_candidate_from_line(line: str) -> Tuple[str, str]:
    """
    Returns (korean_head, english) or ('','') if no candidate.
    """
    raw = line.rstrip("\n")
    if not raw.strip():
        return ("", "")

    raw_wo_bullet = RE_BULLET_PREFIX.sub("", raw).strip()

    english = ""
    m_gloss = RE_GLOSS_ARROW.search(raw_wo_bullet)
    if m_gloss:
        english = english_clean(m_gloss.group(1))
    if not english:
        m_dash = RE_DASH_MEANING_AFTER_ROMAN.search(raw_wo_bullet)
        if m_dash:
            english = english_clean(m_dash.group(1))

    # Prefer Hangul head before romanization, else before arrow, else whole line.
    if "[" in raw_wo_bullet:
        head = raw_wo_bullet.split("[", 1)[0]
    elif "(" in raw_wo_bullet:
        head = raw_wo_bullet.split("(", 1)[0]
    elif "→" in raw_wo_bullet:
        head = raw_wo_bullet.split("→", 1)[0]
    elif "->" in raw_wo_bullet:
        head = raw_wo_bullet.split("->", 1)[0]
    else:
        head = raw_wo_bullet

    head = normalize_korean_head(head)

    # Keep only Hangul heads that end with 다, drop formal endings and long sentences.
    if not head or not head.endswith("다"):
        return ("", "")
    if head.endswith(("니다", "습니다")):
        return ("", "")
    if not RE_HANGUL_ONLY.match(head):
        return ("", "")
    if len(head) < 2:
        return ("", "")
    if len(head.split()) > 5:
        return ("", "")
    if head in STOP_NOT_VERB:
        return ("", "")
    # Exclude common non-dictionary polite/propositive forms ending in -시다 (e.g., 갑시다/합시다),
    # but keep the adjective '시다' (sour).
    if head != "시다" and head.endswith("시다"):
        return ("", "")
    return (head, english)

def extract_inline_pairs_from_line(line: str) -> List[Tuple[str, str]]:
    """
    Extract (verb, english) pairs that appear inside a larger line, e.g.:
    "... | 늦다 [neutda] → to be late | ..."
    """
    raw = line.rstrip("\n")
    if not raw.strip():
        return []

    raw_wo_bullet = RE_BULLET_PREFIX.sub("", raw).strip()
    pairs: List[Tuple[str, str]] = []

    for m in RE_INLINE_BRACKET_ARROW.finditer(raw_wo_bullet):
        v = m.group(1).strip()
        e = english_clean(m.group(2))
        if v != "시다" and v.endswith("시다"):
            continue
        if v and e:
            pairs.append((v, e))

    for m in RE_INLINE_PAREN_ARROW.finditer(raw_wo_bullet):
        v = m.group(1).strip()
        e = english_clean(m.group(2))
        if v != "시다" and v.endswith("시다"):
            continue
        if v and e:
            pairs.append((v, e))

    for m in RE_INLINE_PAREN_DASH.finditer(raw_wo_bullet):
        v = m.group(1).strip()
        e = english_clean(m.group(2))
        if v != "시다" and v.endswith("시다"):
            continue
        if v and e:
            pairs.append((v, e))

    return pairs


def extract_entries_from_notes(root: Path) -> Dict[str, Entry]:
    entries: Dict[str, Entry] = {}
    for file_path in sorted(iter_note_files(root)):
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = file_path.read_text(encoding="utf-8", errors="replace")

        for i, line in enumerate(text.splitlines(), start=1):
            # Inline pairs first (capture meanings even if the verb is not at line start)
            for korean, english in extract_inline_pairs_from_line(line):
                if korean in STOP_NOT_VERB:
                    continue
                ent = entries.get(korean)
                if ent is None:
                    ent = Entry(korean=korean)
                    entries[korean] = ent
                if not ent.english and english:
                    ent.english = english
                ent.sources.add(f"{file_path.as_posix()}:{i}")

            # Head-style extraction (common in your notes)
            korean, english = extract_candidate_from_line(line)
            if not korean:
                continue
            ent = entries.get(korean)
            if ent is None:
                ent = Entry(korean=korean)
                entries[korean] = ent
            if not ent.english and english:
                ent.english = english
            ent.sources.add(f"{file_path.as_posix()}:{i}")
    return entries


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    out_path = root / "verbs_tenses.tsv"

    entries = extract_entries_from_notes(root)

    # Expand slash-variants into separate rows (stable ordering).
    seen: Set[str] = set()
    ordered: List[Tuple[str, str]] = []  # (verb, english)
    for key in sorted(entries.keys()):
        eng = entries[key].english or FALLBACK_ENGLISH.get(key, "")
        for expanded in expand_slashes(key):
            if expanded in STOP_NOT_VERB:
                continue
            # Keep only single-word verbs/adjectives (no phrases).
            if (" " in expanded) or ("/" in expanded) or ("·" in expanded):
                continue
            eng2 = eng or FALLBACK_ENGLISH.get(expanded, "")
            if expanded not in seen:
                seen.add(expanded)
                ordered.append((expanded, eng2))

    rows: List[List[str]] = []
    for phrase, eng in ordered:
        present, past, future = present_past_future(phrase)
        rows.append([phrase, eng, present, past, future])

    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["Verb (dict.)", "English meaning", "Present", "Past", "Future"])
        w.writerows(rows)

    print(f"Wrote {len(rows)} rows to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


