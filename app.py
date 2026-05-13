import logging
from flask import Flask, request, jsonify
from game import GameSession
from leaderboard import Leaderboard

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)

sessions: dict[str, GameSession] = {}  # активные сессии
leaderboard = Leaderboard()


@app.route("/alice", methods=["POST"])
def alice_webhook():
    data = request.get_json(force=True, silent=True) or {}
    if not data:
        return jsonify({"error": "empty body"}), 400

    session_info = data.get("session", {})
    session_id = session_info.get("session_id", "")
    user_id = session_info.get("user_id", "anonymous")
    is_new = session_info.get("new", False)
    command = data.get("request", {}).get("command", "").strip().lower()

    log.info("session=%s new=%s cmd=%r", session_id[:8], is_new, command)

    if is_new or session_id not in sessions:
        sessions[session_id] = GameSession(user_id)

    game = sessions[session_id]
    response_text, end_session = game.process_command(command)

    if end_session:
        if game.score > 0:
            leaderboard.add_score(user_id, game.score, game.current_question)
        sessions.pop(session_id, None)

    return jsonify(_build_response(data, response_text, end_session))


@app.route("/health")
def health():
    return jsonify({"status": "ok", "sessions": len(sessions)})


@app.route("/leaderboard")
def show_leaderboard():
    records = leaderboard.get_top(10)
    rows = "".join(
        f"<tr><td>{i}</td><td>{r['prize']:,} ₽</td>"
        f"<td>вопрос {r['questions']}</td><td>{r['date']}</td></tr>"
        for i, r in enumerate(records, 1)
    )
    return f"""<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">
<title>Рекорды</title>
<style>body{{font-family:sans-serif;max-width:600px;margin:40px auto}}
table{{width:100%;border-collapse:collapse}}th,td{{padding:8px;border:1px solid #ddd}}
th{{background:#f5f5f5}}</style></head><body>
<h1>🏆 Таблица рекордов</h1>
<table><tr><th>#</th><th>Выигрыш</th><th>Вопросов</th><th>Дата</th></tr>
{rows or '<tr><td colspan="4">пока нет записей</td></tr>'}
</table></body></html>"""


def _build_response(original: dict, text: str, end_session: bool) -> dict:
    # собираем кнопки для текущего состояния игры
    buttons = []
    if not end_session:
        sid = original.get("session", {}).get("session_id", "")
        game = sessions.get(sid)
        if game and game.state == "question":
            buttons = [
                {"title": "А", "hide": True},
                {"title": "Б", "hide": True},
                {"title": "В", "hide": True},
                {"title": "Г", "hide": True},
                {"title": "Забрать", "hide": False},
            ]
            if game.hints["50/50"]:
                buttons.append({"title": "50 на 50", "hide": False})
            if game.hints["audience"]:
                buttons.append({"title": "Помощь зала", "hide": False})
            if game.hints["friend"]:
                buttons.append({"title": "Звонок другу", "hide": False})

    return {
        "version": original.get("version", "1.0"),
        "session": original.get("session", {}),
        "response": {
            "text": text,
            # убираем эмодзи для синтеза речи
            "tts": text.translate(str.maketrans("", "", "❓✅❌💰👥📞💡🎉🏆🥇🥈🥉✂️")),
            "buttons": buttons,
            "end_session": end_session,
        },
    }


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
