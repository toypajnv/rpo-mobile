import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./data/test_rpo.db")
os.environ.setdefault("MAIL_MODE", "file")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "Test123!")

from fastapi.testclient import TestClient

from app.main import Base, app, engine

Base.metadata.create_all(engine)


def survey_answers():
    return {
        "q1": "Сразу останавливаю работу / прошу прекратить опасное действие",
        "q2": "Несколько раз в месяц",
        "q3": "5",
        "q4": ["Не уверен, что нарушение действительно является нарушением"],
        "q5": "Сам остановлю работу",
        "q6": "Да, хорошо знаю",
        "q7": "Поддерживает и помогает устранить нарушение",
        "q8": "Нарушение устранят и работу продолжат",
        "q9": ["Поддержка руководителя", "Понятный порядок действий"],
        "q10": "Остановил работу и сообщил ответственному.",
        "q11": "Неуверенность в своих полномочиях.",
        "q12": "Дать понятный алгоритм действий.",
        "q13": "Полностью согласен",
        "q14": "Сделать быстрый способ сообщить о нарушении.",
    }


def test_survey_page_is_public():
    with TestClient(app) as client:
        response = client.get("/opros/")
        assert response.status_code == 200
        assert "Опрос анонимный" in response.text
        assert "Статистика" in response.text


def test_survey_submission_and_q9_limit():
    with TestClient(app) as client:
        response = client.post("/opros/api/responses", json={"answers": survey_answers()})
        assert response.status_code == 200, response.text
        assert response.json()["ok"] is True

        invalid = survey_answers()
        invalid["q9"] = [
            "Поддержка руководителя",
            "Понятный порядок действий",
            "Обучение на реальных ситуациях",
            "Обратная связь о результатах",
        ]
        rejected = client.post("/opros/api/responses", json={"answers": invalid})
        assert rejected.status_code == 422


def test_survey_statistics_are_protected():
    with TestClient(app) as client:
        page = client.get("/opros/statistika")
        assert page.status_code == 200
        assert "Войдите, чтобы посмотреть" in page.text

        api = client.get("/opros/api/stats")
        assert api.status_code == 401

        wrong = client.post(
            "/opros/statistika/login",
            data={"username": "admin", "password": "wrong-password"},
            follow_redirects=False,
        )
        assert wrong.status_code == 401
