"""
JARVIS v2 — router.py (Phase A upgrade)

Enhanced keyword router with:
- Fuzzy matching (typo tolerance)
- Phrase weighting (multi-word matches score higher)
- Category boost from classify()
- Alias expansion
- Beginner-friendly (short queries work)
"""
import json
import math
import re
import logging
from pathlib import Path
from collections import defaultdict

log = logging.getLogger(__name__)


def _tokenize(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s\-]', ' ', text)
    return [t for t in text.split() if len(t) > 1]


def _fuzzy_match(word: str, target: str, max_dist: int = 1) -> bool:
    """Simple Levenshtein distance check for typo tolerance."""
    if word == target:
        return True
    if abs(len(word) - len(target)) > max_dist:
        return False
    if len(word) < 3 or len(target) < 3:
        return False

    # Check if one is substring of other
    if word in target or target in word:
        return True

    # Simple edit distance (optimized for single edits)
    if len(word) == len(target):
        diffs = sum(1 for a, b in zip(word, target) if a != b)
        return diffs <= max_dist

    # Check transposition
    if len(word) == len(target):
        for i in range(len(word) - 1):
            swapped = list(word)
            swapped[i], swapped[i+1] = swapped[i+1], swapped[i]
            if "".join(swapped) == target:
                return True

    return False


class Router:
    THRESHOLD = 0.08  # Lower threshold for fuzzy matching

    def __init__(self, settings):
        self.settings = settings
        self.skills: list = []
        self.aliases: dict = self._load_aliases()
        self._idf: dict = {}
        self._docs: list = []
        self._skill_tokens_cache: list = []
        self._load()

    # ═════════════════════════════════════════════
    # LOADING
    # ═════════════════════════════════════════════

    def _load_aliases(self) -> dict:
        af = self.settings.ALIASES_FILE
        try:
            if Path(af).exists():
                return json.loads(Path(af).read_text())
        except Exception:
            pass
        return {}

    def _load(self):
        skills_dir = self.settings.SKILLS_DIR
        loaded = 0
        for mf in sorted(Path(skills_dir).rglob("manifest.json")):
            try:
                m = json.loads(mf.read_text())
                self.skills.append(m)
                loaded += 1
            except Exception:
                pass

        if not self.skills:
            log.warning("No manifests found")
            return

        self._build_index()
        log.info(f"Router: loaded {loaded} skills")

    def _build_index(self):
        N = len(self.skills)
        df = defaultdict(int)

        self._docs = []
        self._skill_tokens_cache = []

        for skill in self.skills:
            tokens = self._skill_tokens(skill)
            self._skill_tokens_cache.append(tokens)

            tf = defaultdict(int)
            for t in tokens:
                tf[t] += 1

            max_tf = max(tf.values()) if tf else 1
            tf_norm = {t: c / max_tf for t, c in tf.items()}
            self._docs.append(tf_norm)

            for t in set(tokens):
                df[t] += 1

        self._idf = {
            t: math.log((N + 1) / (n + 1)) + 1
            for t, n in df.items()
        }

    def _skill_tokens(self, skill: dict) -> list[str]:
        parts = [
            skill.get("name", ""),
            skill.get("description", ""),
            " ".join(skill.get("triggers", [])),
            " ".join(skill.get("tags", [])),
            skill.get("category", ""),
        ]
        return _tokenize(" ".join(parts))

    # ═════════════════════════════════════════════
    # SCORING
    # ═════════════════════════════════════════════

    def _score(self, query_tokens: list[str], doc_tf: dict,
               skill_tokens: list = None) -> float:
        """Enhanced scoring with fuzzy matching and phrase weighting."""
        score = 0.0

        for qt in query_tokens:
            # Exact match
            if qt in doc_tf and qt in self._idf:
                score += doc_tf[qt] * self._idf[qt] * 1.5  # boost exact

            # Fuzzy match (typo tolerance)
            else:
                for dt in doc_tf:
                    if _fuzzy_match(qt, dt):
                        score += doc_tf[dt] * self._idf.get(dt, 1) * 0.7
                        break

        # Phrase bonus: consecutive query tokens appearing in skill tokens
        if skill_tokens and len(query_tokens) >= 2:
            skill_text = " ".join(skill_tokens)
            query_phrase = " ".join(query_tokens)
            if query_phrase in skill_text:
                score *= 2.0  # Big bonus for phrase match

            # Check 2-word subsequences
            for i in range(len(query_tokens) - 1):
                pair = f"{query_tokens[i]} {query_tokens[i+1]}"
                if pair in skill_text:
                    score *= 1.3

        return score

    # ═════════════════════════════════════════════
    # ROUTING
    # ═════════════════════════════════════════════

    def route(self, query: str, category_hint: str = None) -> dict | None:
        if not self.skills:
            return None

        q_lower = query.lower().strip()

        # 1. Alias exact match (with fuzzy)
        for alias, skill_name in self.aliases.items():
            if q_lower.startswith(alias.lower()):
                match = self._find_by_name(skill_name)
                if match:
                    return {**match, "score": 1.0, "via": "alias"}

        # 2. Alias fuzzy match
        first_word = q_lower.split()[0] if q_lower.split() else ""
        if first_word:
            for alias, skill_name in self.aliases.items():
                if _fuzzy_match(first_word, alias.lower()):
                    match = self._find_by_name(skill_name)
                    if match:
                        return {**match, "score": 0.95, "via": "fuzzy_alias"}

        # 3. Exact trigger phrase match
        for skill in self.skills:
            for trigger in skill.get("triggers", []):
                if trigger.lower() in q_lower:
                    return {**skill, "score": 0.99, "via": "trigger"}

        # 4. TF-IDF scoring with fuzzy + phrase weighting
        q_tokens = _tokenize(query)
        if not q_tokens:
            return None

        # Category pre-filter
        candidates = list(range(len(self.skills)))
        if category_hint and category_hint != "general":
            cat_indices = [
                i for i, s in enumerate(self.skills)
                if s.get("category", "") == category_hint
            ]
            if cat_indices:
                # Search category first, fall back to all if nothing found
                candidates = cat_indices

        best_score = 0.0
        best_idx = -1

        for i in candidates:
            s = self._score(q_tokens, self._docs[i],
                           self._skill_tokens_cache[i] if i < len(self._skill_tokens_cache) else None)

            # Category boost
            if category_hint and self.skills[i].get("category") == category_hint:
                s *= 1.2

            if s > best_score:
                best_score = s
                best_idx = i

        # If category filter found nothing, try all skills
        if best_score < self.THRESHOLD and category_hint and category_hint != "general":
            for i in range(len(self.skills)):
                if i in candidates:
                    continue
                s = self._score(q_tokens, self._docs[i],
                               self._skill_tokens_cache[i] if i < len(self._skill_tokens_cache) else None)
                if s > best_score:
                    best_score = s
                    best_idx = i

        norm_score = min(best_score / 5.0, 1.0)

        if norm_score < self.THRESHOLD or best_idx < 0:
            return None

        self._log_route(query, self.skills[best_idx]["name"], norm_score)
        return {**self.skills[best_idx], "score": norm_score, "via": "tfidf"}

    def top_k(self, query: str, k: int = 5) -> list:
        if not self.skills:
            return []

        q_tokens = _tokenize(query)
        scored = []

        for i, doc in enumerate(self._docs):
            s = self._score(q_tokens, doc,
                           self._skill_tokens_cache[i] if i < len(self._skill_tokens_cache) else None)
            if s > 0:
                scored.append((min(s / 5.0, 1.0), i))

        scored.sort(reverse=True)
        return [{**self.skills[i], "score": sc} for sc, i in scored[:k]]

    # ═════════════════════════════════════════════
    # HELPERS
    # ═════════════════════════════════════════════

    def _find_by_name(self, name: str) -> dict | None:
        for s in self.skills:
            if s.get("name") == name:
                return s
        return None

    def list_skills(self, category: str = None) -> list:
        if category:
            return [s for s in self.skills if s.get("category") == category]
        return self.skills

    def search_skills(self, query: str, k: int = 8) -> list:
        return self.top_k(query, k=k)

    def skill_info(self, name: str) -> dict | None:
        return self._find_by_name(name)

    def get_categories(self) -> dict:
        cats = defaultdict(int)
        for s in self.skills:
            cats[s.get("category", "general")] += 1
        return dict(cats)

    def _log_route(self, query: str, skill: str, score: float):
        log_path = self.settings.SKILL_INDEX_PATH.parent / "router.log"
        try:
            with open(log_path, "a") as f:
                f.write(json.dumps({
                    "ts": datetime.now().isoformat() if 'datetime' in dir() else "",
                    "query": query,
                    "skill": skill,
                    "score": round(score, 3)
                }) + "\n")
        except Exception:
            pass
