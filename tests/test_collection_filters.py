import pytest


def test_live_filter_combines_title_and_status(client, seed_game, stored_games):
    seed_game(title="Resident Finished", status="Completed")
    seed_game(title="Resident Pending", status="Backlog")
    seed_game(title="Portal Finished", status="Completed")
    before = stored_games()
    response = client.get("/library?q=res&status=Completed", headers={"Accept": "application/json"})
    assert response.status_code == 200
    assert response.json["count"] == 1
    assert response.json["total"] == 3
    assert 'id="collection-count" aria-label="1 of 3 games">1 / 3</span>' in client.get("/library?q=res&status=Completed").get_data(as_text=True)
    assert "Resident Finished" in response.json["html"]
    assert "Resident Pending" not in response.json["html"]
    assert "Portal Finished" not in response.json["html"]
    assert "<html" not in response.json["html"]
    assert stored_games() == before
    assert "Accept" in response.vary


def test_live_filter_can_restore_entire_collection(client, seed_game):
    seed_game(title="Portal 2")
    seed_game(title="Resident Evil")
    response = client.get("/library", headers={"Accept": "application/json"})
    assert response.json["count"] == 2
    assert response.json["total"] == 2
    assert 'id="collection-count" aria-label="2 games">2</span>' in client.get("/library").get_data(as_text=True)


def test_live_filter_empty_result_is_helpful(client, seed_game):
    seed_game()
    response = client.get("/library?q=no-match", headers={"Accept": "application/json"})
    assert response.json["count"] == 0
    assert response.json["total"] == 1
    assert 'id="collection-count" aria-label="0 of 1 game">0 / 1</span>' in client.get("/library?q=no-match").get_data(as_text=True)
    assert "No games match your search" in response.json["html"]


def test_live_filter_escapes_untrusted_text(client, seed_game):
    seed_game(title='<img src=x onerror="alert(1)">', review="<script>alert(1)</script>")
    html = client.get("/library", headers={"Accept": "application/json"}).json["html"]
    assert "<script>" not in html
    assert "<img src=x" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;img" in html


@pytest.mark.parametrize("query", [{"status": "Invalid"}, {"q": "x" * 201}])
def test_live_filter_keeps_server_validation(client, query):
    assert client.get("/library", query_string=query, headers={"Accept": "application/json"}).status_code == 400


def test_full_page_keeps_non_javascript_filter_fallback(client):
    response = client.get("/library")
    assert response.mimetype == "text/html"
    assert "Accept" in response.vary
    assert b'id="collection-filters" method="get"' in response.data
    assert b"Apply filters" in response.data
    assert b"collection-filters.js" in response.data
