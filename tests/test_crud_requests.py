import pytest
import uuid
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from requests.models.request import RequestTypeEnum, RequestStatusEnum, Request
from services.crud import create_team_request_in_db_sync


@pytest.fixture
def mock_db_session():
    """Simula a sessão do SQLAlchemy"""
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None
    return session


@pytest.fixture
def mock_get_db(mock_db_session):
    """Simula a função get_db que retorna um generator."""

    def get_db_mock():
        yield mock_db_session

    return get_db_mock


# Caso 1: Mensagem sem 'team_id'
def test_create_request_missing_team_id(mock_get_db):
    """Caso 1: Testa se ValueError é lançado quando team_id está ausente"""
    message_data = {
        "campus_code": "NAT-CN",
        "request_type": "approve_team",
        "competition_id": str(uuid.uuid4())
    }

    with patch("services.crud.get_db", mock_get_db):
        with pytest.raises(ValueError, match="'team_id' é obrigatório na mensagem"):
            create_team_request_in_db_sync(message_data)


# Caso 2: Mensagem sem 'campus_code'
def test_create_request_missing_campus_code(mock_get_db):
    """Caso 2: Testa se ValueError é lançado quando campus_code está ausente"""
    message_data = {
        "team_id": str(uuid.uuid4()),
        "request_type": "approve_team",
        "competition_id": str(uuid.uuid4())
    }

    with patch("services.crud.get_db", mock_get_db):
        with pytest.raises(ValueError, match="'campus_code' é obrigatório na mensagem"):
            create_team_request_in_db_sync(message_data)


# Caso 3: team_id inválido (não é UUID)
def test_create_request_invalid_team_id(mock_get_db):
    """Caso 3: Testa se ValueError é lançado quando team_id não é um UUID válido"""
    message_data = {
        "team_id": "1234",
        "campus_code": "NAT-CN",
        "request_type": "approve_team",
        "competition_id": str(uuid.uuid4())
    }

    with patch("services.crud.get_db", mock_get_db):
        with pytest.raises(ValueError, match="team_id '1234' não é um UUID válido"):
            create_team_request_in_db_sync(message_data)


# Caso 4: request_type inválido
def test_create_request_invalid_type(mock_get_db):
    """Caso 4: Testa se ValueError é lançado para request_type inválido"""
    message_data = {
        "team_id": str(uuid.uuid4()),
        "campus_code": "NAT-CN",
        "request_type": "invalid_type"
    }

    with patch("services.crud.get_db", mock_get_db):
        with pytest.raises(ValueError, match="Request type inválido: invalid_type"):
            create_team_request_in_db_sync(message_data)


# Caso 5: approve_team sem competition_id
def test_create_request_approve_team_missing_competition_id(mock_get_db):
    """Caso 5: Testa se ValueError é lançado quando competition_id está ausente em approve_team"""
    message_data = {
        "team_id": str(uuid.uuid4()),
        "campus_code": "NAT-CN",
        "request_type": "approve_team"
    }

    with patch("services.crud.get_db", mock_get_db):
        with pytest.raises(ValueError, match="'competition_id' é obrigatório para approve_team"):
            create_team_request_in_db_sync(message_data)


# Caso 6: remove_team_member sem user_id
def test_create_request_remove_member_missing_user_id(mock_get_db):
    """Caso 6: Testa se ValueError é lançado quando user_id está ausente em remove_team_member"""
    message_data = {
        "team_id": str(uuid.uuid4()),
        "campus_code": "NAT-CN",
        "request_type": "remove_team_member"
    }

    with patch("services.crud.get_db", mock_get_db):
        with pytest.raises(ValueError, match="'user_id' é obrigatório para o tipo de requisição 'remove_team_member'"):
            create_team_request_in_db_sync(message_data)


# Caso 7: delete_team sem aprovação prévia
def test_create_request_delete_team_without_prior_approval(mock_get_db, mock_db_session):
    """Caso 7: Testa se ValueError é lançado quando não há aprovação prévia para delete_team"""
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    message_data = {
        "team_id": str(uuid.uuid4()),
        "campus_code": "NAT-CN",
        "request_type": "delete_team"
    }

    with patch("services.crud.get_db", mock_get_db):
        with pytest.raises(ValueError, match="Não foi possível encontrar uma aprovação prévia para esta equipe"):
            create_team_request_in_db_sync(message_data)


# Caso 8: Solicitação pendente duplicada
def test_create_request_duplicate_pending(mock_get_db, mock_db_session):
    """Caso 8: Testa se uma solicitação duplicada pendente é identificada corretamente"""
    existing_request_id = uuid.uuid4()

    existing_mock = MagicMock(spec=Request)
    existing_mock.id = existing_request_id
    existing_mock.status = RequestStatusEnum.pendent
    mock_db_session.query.return_value.filter.return_value.first.return_value = existing_mock

    message_data = {
        "team_id": str(uuid.uuid4()),
        "campus_code": "NAT-CN",
        "request_type": "approve_team",
        "competition_id": str(uuid.uuid4())
    }

    with patch("services.crud.get_db", mock_get_db):
        result = create_team_request_in_db_sync(message_data)

    assert result["message"] == "Solicitação pendente já existente processada como duplicada."
    assert result["request_id"] == existing_request_id
    mock_db_session.add.assert_not_called()


# Caso 9: Criação com created_at personalizado
def test_create_request_with_custom_created_at(mock_get_db, mock_db_session):
    """Caso 9: Testa criação de solicitação com created_at personalizado"""
    team_id = uuid.uuid4()
    comp_id = uuid.uuid4()
    custom_date = "2025-10-25T21:30:00Z"

    message_data = {
        "team_id": str(team_id),
        "campus_code": "NAT-CN",
        "request_type": "approve_team",
        "competition_id": str(comp_id),
        "created_at": custom_date
    }

    with patch("services.crud.get_db", mock_get_db):
        result = create_team_request_in_db_sync(message_data)

    assert "request_id" in result
    assert result["status"] == RequestStatusEnum.pendent.value

    mock_db_session.add.assert_called_once()
    added_object = mock_db_session.add.call_args[0][0]

    expected_date = datetime.fromisoformat(custom_date.replace("Z", "+00:00"))
    assert added_object.created_at == expected_date


# Criação sem created_at (usa datetime.now)
def test_create_request_without_created_at(mock_get_db, mock_db_session):
    """Testa criação de solicitação sem created_at (usa datetime.now)"""
    team_id = uuid.uuid4()
    comp_id = uuid.uuid4()

    message_data = {
        "team_id": str(team_id),
        "campus_code": "NAT-CN",
        "request_type": "approve_team",
        "competition_id": str(comp_id)
    }

    before_test = datetime.now(timezone.utc)

    with patch("services.crud.get_db", mock_get_db):
        result = create_team_request_in_db_sync(message_data)

    after_test = datetime.now(timezone.utc)

    assert "request_id" in result
    assert result["status"] == RequestStatusEnum.pendent.value

    mock_db_session.add.assert_called_once()
    added_object = mock_db_session.add.call_args[0][0]

    assert before_test <= added_object.created_at <= after_test


# Criar approve_team com sucesso
def test_create_request_approve_team_success(mock_get_db, mock_db_session):
    """Testa a criação bem-sucedida de uma solicitação approve_team"""
    team_id = uuid.uuid4()
    comp_id = uuid.uuid4()

    message_data = {
        "team_id": str(team_id),
        "campus_code": "NAT-CN",
        "request_type": "approve_team",
        "competition_id": str(comp_id)
    }

    with patch("services.crud.get_db", mock_get_db):
        result = create_team_request_in_db_sync(message_data)

    assert "request_id" in result
    assert result["status"] == RequestStatusEnum.pendent.value

    mock_db_session.add.assert_called_once()
    added_object = mock_db_session.add.call_args[0][0]
    assert isinstance(added_object, Request)
    assert added_object.team_id == team_id
    assert added_object.request_type == RequestTypeEnum.approve_team
    assert added_object.competition_id == comp_id
    assert added_object.status == RequestStatusEnum.pendent

    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(added_object)