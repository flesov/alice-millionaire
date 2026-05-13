import random
from questions import QUESTIONS, PRIZE_LADDER, SAFE_HAVENS, format_prize

# распознавание букв ответа из разных форм ввода
ANSWER_ALIASES = {
    "а": "А", "a": "А", "вариант а": "А", "первый": "А", "1": "А",
    "б": "Б", "b": "Б", "вариант б": "Б", "второй": "Б", "2": "Б",
    "в": "В", "c": "В", "вариант в": "В", "третий": "В", "3": "В",
    "г": "Г", "d": "Г", "вариант г": "Г", "четвёртый": "Г", "четвертый": "Г", "4": "Г",
}

TAKE_KEYWORDS     = {"забрать", "забираю", "беру", "ухожу", "стоп", "хватит", "остановиться"}
HINT_50_KEYWORDS  = {"пятьдесят на пятьдесят", "50 на 50", "50/50", "убрать два"}
HINT_AUD_KEYWORDS = {"помощь зала", "спросить зал", "зал"}
HINT_FRD_KEYWORDS = {"звонок другу", "позвонить другу", "звоню другу", "другу"}
LB_KEYWORDS       = {"рекорды", "таблица рекордов", "лучшие результаты", "топ"}


class GameSession:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.state = "greeting"
        self.current_question = 0   # индекс текущего вопроса
        self.score = 0              # текущий выигрыш
        self.safe_score = 0         # последняя несгораемая сумма
        self.hints = {"50/50": True, "audience": True, "friend": True}
        self.removed_options: set[str] = set()  # убранные вариантом 50/50

    def process_command(self, command: str) -> tuple[str, bool]:
        cmd = command.strip().lower()

        if any(kw in cmd for kw in LB_KEYWORDS):
            return self._get_leaderboard(), False

        if self.state == "greeting":
            return self._handle_greeting(cmd)
        if self.state == "question":
            return self._handle_question(cmd)
        if self.state in ("gameover", "victory"):
            return self._handle_restart(cmd)

        return "Что-то пошло не так. Попробуйте начать заново.", True

    # --- обработчики состояний ---

    def _handle_greeting(self, cmd: str) -> tuple[str, bool]:
        start = {"начать", "играть", "старт", "да", "поехали", "начнём", "начнем", ""}
        if any(kw in cmd for kw in start) or cmd == "":
            self.state = "question"
            return self._ask_question(), False
        return _welcome_text(), False

    def _handle_question(self, cmd: str) -> tuple[str, bool]:
        if any(kw in cmd for kw in TAKE_KEYWORDS):
            return self._take_money(), True

        if any(kw in cmd for kw in HINT_50_KEYWORDS):
            return self._hint_5050()
        if any(kw in cmd for kw in HINT_AUD_KEYWORDS):
            return self._hint_audience()
        if any(kw in cmd for kw in HINT_FRD_KEYWORDS):
            return self._hint_friend()

        if cmd in {"повторить", "повтори"}:
            return self._ask_question(repeat=True), False
        if cmd in {"счёт", "счет", "сколько", "выигрыш"}:
            return self._prize_info(), False

        letter = self._parse_answer(cmd)
        if letter:
            return self._check_answer(letter)

        return "Назовите букву варианта: А, Б, В или Г. Или скажите «забрать».", False

    def _handle_restart(self, cmd: str) -> tuple[str, bool]:
        if any(kw in cmd for kw in {"да", "ещё раз", "еще раз", "заново", "начать", "играть"}):
            self._reset()
            self.state = "question"
            return self._ask_question(), False
        if any(kw in cmd for kw in {"нет", "стоп", "выход"}):
            return "Спасибо за игру! До свидания! 👋", True
        return "Сыграем ещё раз? Скажите «да» или «нет».", False

    # --- логика вопроса и ответа ---

    def _ask_question(self, repeat: bool = False) -> str:
        q = QUESTIONS[self.current_question]
        prize_now  = format_prize(self.score) if self.score else "0 ₽"
        prize_next = format_prize(PRIZE_LADDER[self.current_question])
        prefix = "Повторяю вопрос.\n\n" if repeat else ""
        return (
            f"{prefix}❓ Вопрос {self.current_question + 1} из 15. "
            f"Розыгрыш: {prize_next}\n(У вас: {prize_now})\n\n"
            f"{q['text']}\n\n{self._format_options(q['options'])}\n\n"
            f"{self._hints_summary()}"
        )

    def _check_answer(self, letter: str) -> tuple[str, bool]:
        q = QUESTIONS[self.current_question]
        correct = q["answer"]

        if letter == correct:
            self.score = PRIZE_LADDER[self.current_question]
            if self.current_question in SAFE_HAVENS:
                self.safe_score = SAFE_HAVENS[self.current_question]

            self.current_question += 1
            self.removed_options.clear()

            if self.current_question >= len(QUESTIONS):
                self.state = "victory"
                return _victory_text(), True

            # переходим к следующему вопросу
            nq = QUESTIONS[self.current_question]
            return (
                f"✅ Правильно! Вы заработали {format_prize(self.score)}!\n\n"
                f"❓ Вопрос {self.current_question + 1} из 15. "
                f"Розыгрыш: {format_prize(PRIZE_LADDER[self.current_question])}\n\n"
                f"{nq['text']}\n\n{self._format_options(nq['options'])}\n\n"
                f"{self._hints_summary()}"
            ), False

        self.state = "gameover"
        safe_str = format_prize(self.safe_score) if self.safe_score else "0 ₽"
        return (
            f"❌ Неверно! Правильный ответ: {correct} — {q['options'][correct]}.\n\n"
            f"Вы уходите с несгораемой суммой: {safe_str}.\n\nСыграем ещё раз?"
        ), True

    # --- подсказки ---

    def _hint_5050(self) -> tuple[str, bool]:
        if not self.hints["50/50"]:
            return "Подсказка «50 на 50» уже использована.", False
        self.hints["50/50"] = False
        q = QUESTIONS[self.current_question]
        wrong = [k for k in q["options"] if k != q["answer"]]
        self.removed_options = set(random.sample(wrong, 2))
        return (
            f"✂️ Убраны варианты: {' и '.join(sorted(self.removed_options))}\n\n"
            f"{q['text']}\n\n{self._format_options(q['options'])}"
        ), False

    def _hint_audience(self) -> tuple[str, bool]:
        if not self.hints["audience"]:
            return "Подсказка «Помощь зала» уже использована.", False
        self.hints["audience"] = False
        q = QUESTIONS[self.current_question]
        pcts = _audience_percents(q["answer"], list(q["options"].keys()))
        lines = "\n".join(f"  {k}: {pcts[k]}%" for k in sorted(q["options"]))
        return f"👥 Зал проголосовал:\n{lines}\n\nВаш ответ?", False

    def _hint_friend(self) -> tuple[str, bool]:
        if not self.hints["friend"]:
            return "Подсказка «Звонок другу» уже использована.", False
        self.hints["friend"] = False
        q = QUESTIONS[self.current_question]
        answer_text = q["options"][q["answer"]]
        phrase = random.choice([
            f"Я почти уверен — это {q['answer']} ({answer_text}).",
            f"Думаю, {q['answer']}, но не ручаюсь на 100%.",
            f"Кажется, {q['answer']} — {answer_text}.",
        ])
        return f"📞 Друг: «{phrase}»\n\nВаш ответ?", False

    # --- вспомогательные методы ---

    def _take_money(self) -> str:
        return (
            f"💰 Вы забираете {format_prize(self.score)}. Умное решение!\n"
            f"Спасибо за игру!\n\nСыграем ещё раз?"
        )

    def _prize_info(self) -> str:
        return (
            f"Сейчас: {format_prize(self.score) if self.score else '0 ₽'}\n"
            f"Следующий приз: {format_prize(PRIZE_LADDER[self.current_question])}"
        )

    def _hints_summary(self) -> str:
        av = [n for n, ok in [("«50 на 50»", self.hints["50/50"]),
                               ("«Помощь зала»", self.hints["audience"]),
                               ("«Звонок другу»", self.hints["friend"])] if ok]
        return "💡 Подсказки: " + ", ".join(av) if av else "💡 Подсказки закончились."

    def _format_options(self, options: dict) -> str:
        return "\n".join(
            f"  {k}: {'—' if k in self.removed_options else v}"
            for k, v in sorted(options.items())
        )

    def _parse_answer(self, cmd: str) -> str | None:
        if cmd in ANSWER_ALIASES:
            return ANSWER_ALIASES[cmd]
        for alias, letter in ANSWER_ALIASES.items():
            if alias in cmd:
                return letter
        return None

    def _get_leaderboard(self) -> str:
        from app import leaderboard  # noqa: PLC0415
        return leaderboard.format_top()

    def _reset(self):
        self.current_question = 0
        self.score = 0
        self.safe_score = 0
        self.hints = {"50/50": True, "audience": True, "friend": True}
        self.removed_options = set()
        self.state = "greeting"


# --- функции вне класса ---

def _welcome_text() -> str:
    return (
        "Добро пожаловать в «Кто хочет стать миллионером?»! 🎯\n\n"
        "• 15 вопросов нарастающей сложности\n"
        "• Несгораемые суммы: 5 000 ₽ и 50 000 ₽\n"
        "• Подсказки: «50 на 50», «Помощь зала», «Звонок другу»\n"
        "• В любой момент можно сказать «забрать»\n\n"
        "Скажите «начать»!"
    )


def _victory_text() -> str:
    return (
        "🎉🎉🎉 ПОЗДРАВЛЯЕМ! 🎉🎉🎉\n\n"
        "Вы ответили на все 15 вопросов и выиграли 1 000 000 ₽!\n"
        "Вы настоящий миллионер! 🏆\n\nСыграем ещё раз?"
    )


def _audience_percents(correct: str, options: list[str]) -> dict[str, int]:
    # правильный вариант получает большинство голосов
    cp = random.randint(55, 75)
    rest = 100 - cp
    others = [o for o in options if o != correct]
    splits = sorted(random.sample(range(1, rest), len(others) - 1))
    parts = [splits[0]] + [splits[i] - splits[i-1] for i in range(1, len(splits))] + [rest - splits[-1]]
    return {correct: cp, **dict(zip(others, parts))}
