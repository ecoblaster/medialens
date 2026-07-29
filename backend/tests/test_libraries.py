from fastapi.testclient import TestClient


def test_library_crud(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/libraries",
        json={
            "name": "Movies",
            "media_kind": "movies",
            "source_type": "filesystem",
            "root_path": "/media/movies",
        },
    )
    assert create_response.status_code == 201
    library = create_response.json()
    library_id = library["id"]

    list_response = client.get("/api/v1/libraries")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    update_response = client.patch(
        f"/api/v1/libraries/{library_id}", json={"name": "4K Movies"}
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "4K Movies"

    delete_response = client.delete(f"/api/v1/libraries/{library_id}")
    assert delete_response.status_code == 204

    missing_response = client.get(f"/api/v1/libraries/{library_id}")
    assert missing_response.status_code == 404
    assert missing_response.json()["error"]["code"] == "LIBRARY_NOT_FOUND"


def test_duplicate_library_is_rejected(client: TestClient) -> None:
    payload = {
        "name": "Movies",
        "media_kind": "movies",
        "source_type": "filesystem",
        "root_path": "/media/movies",
    }
    assert client.post("/api/v1/libraries", json=payload).status_code == 201
    assert client.post("/api/v1/libraries", json=payload).status_code == 409
