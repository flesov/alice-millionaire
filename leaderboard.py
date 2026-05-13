import json
import os
from datetime import datetime

LEADERBOARD_FILE = os.path.join(os.path.dirname(__file__), "leaderboard.json")
MAX_RECORDS = 10


class Leaderboard:
    def __init__(self):
        self._records: list[dict] = []
        self._load()

    def add_score(self, user_id: str, prize: int, questions_answered: int) -> int:
        # обновляем запись если результат лучше предыдущего
        existing = next((r for r in self._records if r["user_id"] == user_id), None)
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        if existing:
            if prize > existing["prize"]:
                existing.update({"prize": prize, "questions": questions_answered, "date": now})
        else:
            self._records.append({"user_id": user_id, "prize": prize,
                                   "questions": questions_answered, "date": now})

        self._records.sort(key=lambda r: r["prize"], reverse=True)
        self._records = self._records[:MAX_RECORDS]
        self._save()

        # возвращаем место в рейтинге
        for i, r in enumerate(self._records, 1):
            if r["user_id"] == user_id:
                return i
        return MAX_RECORDS + 1

    def get_top(self, n: int = 5) -> list[dict]:
        return self._records[:n]

    def format_top(self, n: int = 5) -> str:
        top = self.get_top(n)
        if not top:
            return "Таблица рекордов пока пуста. Будьте первым!"
        medals = ["🥇", "🥈", "🥉"]
        lines = ["🏆 Таблица рекордов:"]
        for i, r in enumerate(top, 1):
            medal = medals[i - 1] if i <= 3 else f"{i}."
            lines.append(f"{medal} {r['prize']:,} ₽ — вопрос {r['questions']} ({r['date']})")
        return "\n".join(lines)

    def _load(self):
        if os.path.exists(LEADERBOARD_FILE):
            try:
                with open(LEADERBOARD_FILE, encoding="utf-8") as f:
                    self._records = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._records = []

    def _save(self):
        try:
            with open(LEADERBOARD_FILE, "w", encoding="utf-8") as f:
                json.dump(self._records, f, ensure_ascii=False, indent=2)
        except IOError:
            pass
