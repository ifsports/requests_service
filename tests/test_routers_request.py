import pytest
import uuid
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.sql.elements import BooleanClauseList

from main import app
from auth import get_current_user
from shared.dependencies import get_db
from requests.models.request import (
    RequestTypeEnum,
    RequestStatusEnum,
    Request,
    RequestsPutRequest
)
from shared.exceptions import NotFound, Conflict


@pytest.fixture
def client():
    """Cria um cliente HTTP para chamar a API"""
    return TestClient(app)


@pytest.fixture
def mock_db_session():
    """Simula a sessão do SQLAlchemy"""
    session = MagicMock()
    session.query.return_value.filter.return_value.all.return_value = []
    session.query.return_value.filter.return_value.first.return_value = None
    return session


@pytest.fixture
def mock_current_user_organizador():
    """Simula um usuário com papel de Organizador"""
    return {
        "campus": "NAT-CN",
        "groups": ["Organizador"],
        "matricula": "20231012030015",
        "access_token": "fake_token"
    }


@pytest.fixture
def mock_current_user_aluno():
    """Simula um usuário com papel de Aluno (sem permissão)"""
    return {
        "campus": "NAT-CN",
        "groups": ["Aluno"],
        "matricula": "20231012030016",
        "access_token": "fake_token_aluno"
    }


@pytest.fixture
def sample_request_data():
    """Cria dados de uma solicitação de exemplo para o mock do DB"""
    req_id = uuid.uuid4()
    return {
        "id": req_id,
        "request_type": RequestTypeEnum.approve_team,
        "team_id": uuid.uuid4(),
        "competition_id": uuid.uuid4(),
        "campus_code": "NAT-CN",
        "status": RequestStatusEnum.pendent,
        "created_at": datetime.now(timezone.utc),
        "user_id": None,
        "reason": "Motivo teste",
        "reason_rejected": None
    }


@pytest.fixture
def mock_publishers(mocker):
    """Mocks para as funções de publicação no RabbitMQ"""
    mocks = {
        "creation": mocker.patch("requests.routers.requests_router.publish_team_creation_request",
                                 new_callable=AsyncMock),
        "removal": mocker.patch("requests.routers.requests_router.publish_team_remove_request", new_callable=AsyncMock),
        "add_member": mocker.patch("requests.routers.requests_router.publish_member_add_request",
                                   new_callable=AsyncMock),
        "remove_member": mocker.patch("requests.routers.requests_router.publish_member_remove_request",
                                      new_callable=AsyncMock),
        "audit": mocker.patch("requests.routers.requests_router.run_async_audit", autospec=True)
    }
    return mocks


# Caso 1: Listar todas (usuário Organizador)
def test_list_requests_as_organizador_http(client, mock_db_session, mock_current_user_organizador, sample_request_data):
    """Caso 1 (HTTP): Testa listagem por Organizador via TestClient"""
    mock_request_obj = MagicMock(spec=Request)
    for key, value in sample_request_data.items():
        setattr(mock_request_obj, key, value)

    mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_request_obj]

    app.dependency_overrides[get_current_user] = lambda: mock_current_user_organizador
    app.dependency_overrides[get_db] = lambda: mock_db_session

    response = client.get("/api/v1/requests/")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == str(sample_request_data["id"])
    assert data[0]["status"] == sample_request_data["status"].value

    filter_expression = mock_db_session.query.return_value.filter.call_args[0][0]
    assert filter_expression.left.name == 'campus_code'
    assert filter_expression.right.value == mock_current_user_organizador["campus"]

    app.dependency_overrides = {}


# Caso 2: Listar todas (usuário sem permissão)
def test_list_requests_without_permission_http(client, mock_db_session, mock_current_user_aluno):
    """Caso 2 (HTTP): Testa GET sem permissão via TestClient"""
    app.dependency_overrides[get_current_user] = lambda: mock_current_user_aluno
    app.dependency_overrides[get_db] = lambda: mock_db_session

    response = client.get("/api/v1/requests/")

    assert response.status_code == 403
    assert "não tem permissão" in response.json()["detail"]

    app.dependency_overrides = {}


# Listar com filtro de status
def test_list_requests_with_status_filter_http(client, mock_db_session, mock_current_user_organizador,
                                               sample_request_data):
    """Testa listagem com filtro de status via TestClient"""
    sample_request_data["status"] = RequestStatusEnum.pendent
    mock_request_obj = MagicMock(spec=Request)
    for key, value in sample_request_data.items():
        setattr(mock_request_obj, key, value)

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = [mock_request_obj]

    app.dependency_overrides[get_current_user] = lambda: mock_current_user_organizador
    app.dependency_overrides[get_db] = lambda: mock_db_session

    response = client.get("/api/v1/requests/?status=pendent")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["status"] == "pendent"

    assert mock_query.filter.call_count >= 2

    app.dependency_overrides = {}


# Caso 3: Buscar por ID válido (Organizador)
def test_get_request_by_id_as_organizador_http(client, mock_db_session, mock_current_user_organizador,
                                               sample_request_data):
    """Caso 3 (HTTP): Testa busca por ID com Organizador via TestClient"""
    mock_request_obj = MagicMock(spec=Request)
    for key, value in sample_request_data.items():
        setattr(mock_request_obj, key, value)

    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_request_obj

    app.dependency_overrides[get_current_user] = lambda: mock_current_user_organizador
    app.dependency_overrides[get_db] = lambda: mock_db_session

    request_id_str = str(sample_request_data["id"])

    response = client.get(f"/api/v1/requests/{request_id_str}")

    assert response.status_code == 200
    assert response.json()["id"] == request_id_str

    filter_args = mock_db_session.query.return_value.filter.call_args[0]

    assert len(filter_args) == 2

    cond1 = filter_args[0]
    col1_name = cond1.left.name
    val1 = cond1.right.value

    cond2 = filter_args[1]
    col2_name = cond2.left.name
    val2 = cond2.right.value

    assert {col1_name, col2_name} == {'id', 'campus_code'}

    if col1_name == 'id':
        assert val1 == sample_request_data["id"]
        assert val2 == mock_current_user_organizador["campus"]
    else:
        assert val1 == mock_current_user_organizador["campus"]
        assert val2 == sample_request_data["id"]

    app.dependency_overrides = {}


# Caso 4: Buscar por ID inexistente
def test_get_request_by_id_not_found_http(client, mock_db_session, mock_current_user_organizador):
    """Caso 4 (HTTP): Testa busca por ID inexistente via TestClient"""
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    app.dependency_overrides[get_current_user] = lambda: mock_current_user_organizador
    app.dependency_overrides[get_db] = lambda: mock_db_session

    non_existent_id = uuid.UUID("99999999-9999-9999-9999-999999999999")

    response = client.get(f"/api/v1/requests/{non_existent_id}")

    assert response.status_code == 404
    assert "Solicitação não encontrado(a)" in response.json()["message"]

    app.dependency_overrides = {}


# Caso 5: Buscar sem permissão
def test_get_request_by_id_without_permission_http(client, mock_db_session, mock_current_user_aluno,
                                                   sample_request_data):
    """Caso 5 (HTTP): Testa busca por ID sem permissão via TestClient"""
    mock_request_obj = MagicMock(spec=Request)
    for key, value in sample_request_data.items():
        setattr(mock_request_obj, key, value)
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_request_obj

    app.dependency_overrides[get_current_user] = lambda: mock_current_user_aluno
    app.dependency_overrides[get_db] = lambda: mock_db_session

    request_id_str = str(sample_request_data["id"])

    response = client.get(f"/api/v1/requests/{request_id_str}")

    assert response.status_code == 403
    assert "não tem permissão" in response.json()["detail"]

    app.dependency_overrides = {}


# Aprovar solicitação
@pytest.mark.asyncio
async def test_approve_request_http(client, mock_db_session, mock_current_user_organizador, sample_request_data,
                                    mock_publishers):
    """Caso 1 (HTTP): Testa aprovação via TestClient"""
    sample_request_data["status"] = RequestStatusEnum.pendent
    mock_request_obj = MagicMock(spec=Request)
    for key, value in sample_request_data.items():
        setattr(mock_request_obj, key, value)

    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_request_obj

    app.dependency_overrides[get_current_user] = lambda: mock_current_user_organizador
    app.dependency_overrides[get_db] = lambda: mock_db_session

    request_id_str = str(sample_request_data["id"])
    payload = {"status": "approved"}

    response = client.put(f"/api/v1/requests/{request_id_str}", json=payload)

    assert response.status_code == 202
    response_data = response.json()
    assert "message" in response_data
    assert "Solicitação para criação de equipe atualizada" in response_data["message"]

    assert mock_request_obj.status == RequestStatusEnum.approved
    mock_db_session.add.assert_called_with(mock_request_obj)
    mock_db_session.commit.assert_called_once()

    mock_publishers["creation"].assert_called_once()
    mock_publishers["audit"].assert_called_once()
    mock_publishers["removal"].assert_not_called()

    app.dependency_overrides = {}


# Rejeitar solicitação
@pytest.mark.asyncio
async def test_reject_request_http(client, mock_db_session, mock_current_user_organizador, sample_request_data,
                                   mock_publishers):
    """Testa rejeição com motivo via TestClient"""
    sample_request_data["status"] = RequestStatusEnum.pendent
    mock_request_obj = MagicMock(spec=Request)
    for key, value in sample_request_data.items():
        setattr(mock_request_obj, key, value)

    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_request_obj

    app.dependency_overrides[get_current_user] = lambda: mock_current_user_organizador
    app.dependency_overrides[get_db] = lambda: mock_db_session

    request_id_str = str(sample_request_data["id"])
    payload = {
        "status": "rejected",
        "reason_rejected": "Equipe incompleta"
    }

    response = client.put(f"/api/v1/requests/{request_id_str}", json=payload)

    assert response.status_code == 202
    assert mock_request_obj.status == RequestStatusEnum.rejected
    assert mock_request_obj.reason_rejected == "Equipe incompleta"
    mock_db_session.add.assert_called_with(mock_request_obj)
    mock_db_session.commit.assert_called_once()
    mock_publishers["audit"].assert_called_once()
    mock_publishers["creation"].assert_called_once()

    app.dependency_overrides = {}


# Tentar aprovar solicitação já aprovada
@pytest.mark.asyncio
async def test_approve_already_approved_request_http(client, mock_db_session, mock_current_user_organizador,
                                                     sample_request_data):
    """Caso 3 (HTTP): Testa PUT em solicitação já aprovada via TestClient"""
    sample_request_data["status"] = RequestStatusEnum.approved
    mock_request_obj = MagicMock(spec=Request)
    for key, value in sample_request_data.items():
        setattr(mock_request_obj, key, value)

    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_request_obj

    app.dependency_overrides[get_current_user] = lambda: mock_current_user_organizador
    app.dependency_overrides[get_db] = lambda: mock_db_session

    request_id_str = str(sample_request_data["id"])
    payload = {"status": "approved"}

    response = client.put(f"/api/v1/requests/{request_id_str}", json=payload)

    assert response.status_code == 409
    assert "A operação não pode ser realizada" in response.json()["message"]
    mock_db_session.commit.assert_not_called()

    app.dependency_overrides = {}


# Atualizar sem permissão
@pytest.mark.asyncio
async def test_update_request_without_permission_http(client, mock_db_session, mock_current_user_aluno,
                                                      sample_request_data):
    """Caso 4 (HTTP): Testa PUT sem permissão via TestClient"""
    sample_request_data["status"] = RequestStatusEnum.pendent
    mock_request_obj = MagicMock(spec=Request)
    for key, value in sample_request_data.items():
        setattr(mock_request_obj, key, value)

    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_request_obj

    app.dependency_overrides[get_current_user] = lambda: mock_current_user_aluno
    app.dependency_overrides[get_db] = lambda: mock_db_session

    request_id_str = str(sample_request_data["id"])
    payload = {"status": "approved"}

    response = client.put(f"/api/v1/requests/{request_id_str}", json=payload)

    assert response.status_code == 403
    assert "não tem permissão" in response.json()["detail"]
    mock_db_session.commit.assert_not_called()

    app.dependency_overrides = {}


# Rejeição com status approved + reason_rejected deve dar conflito
@pytest.mark.asyncio
async def test_reject_with_wrong_status_and_reason_http(client, mock_db_session, mock_current_user_organizador,
                                                        sample_request_data):
    """Testa PUT com combinação inválida de status e reason_rejected via TestClient"""
    sample_request_data["status"] = RequestStatusEnum.pendent
    mock_request_obj = MagicMock(spec=Request)
    for key, value in sample_request_data.items():
        setattr(mock_request_obj, key, value)

    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_request_obj

    app.dependency_overrides[get_current_user] = lambda: mock_current_user_organizador
    app.dependency_overrides[get_db] = lambda: mock_db_session

    request_id_str = str(sample_request_data["id"])
    payload = {
        "status": "approved",
        "reason_rejected": "Motivo inválido aqui"
    }

    response = client.put(f"/api/v1/requests/{request_id_str}", json=payload)

    assert response.status_code == 409
    assert "A operação não pode ser realizada" in response.json()["message"]
    mock_db_session.commit.assert_not_called()

    app.dependency_overrides = {}


def test_find_by_id_function(mock_db_session, sample_request_data):
    """Testa a função auxiliar find_by_id"""
    from requests.routers.requests_router import find_by_id

    mock_request_obj = MagicMock(spec=Request)
    for key, value in sample_request_data.items():
        setattr(mock_request_obj, key, value)

    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_request_obj

    result = find_by_id(sample_request_data["id"], "NAT-CN", mock_db_session)

    assert result.id == sample_request_data["id"]
    mock_db_session.query.assert_called_once()


def test_find_by_id_not_found(mock_db_session):
    """Testa find_by_id quando a solicitação não é encontrada"""
    from requests.routers.requests_router import find_by_id

    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(NotFound) as exc_info:
        find_by_id(uuid.uuid4(), "NAT-CN", mock_db_session)

    assert exc_info.value.name == "Solicitação"