from flask import Blueprint, render_template

main = Blueprint("main", __name__)


@main.get("/")
def index():
    games = [
        {
            "title": "Minecraft",
            "platform": "PC",
            "status": "Playing",
        },
        {
            "title": "GOD OF WAR Ragnarok",
            "platform": "PC",
            "status": "Backlog",
        },
        {
            "title": "Resident Evil Requiem",
            "platform": "PC",
            "status": "Completed",
        },
    ]

    return render_template("index.html", games=games)