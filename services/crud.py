import uuid
from datetime import datetime, timezone

from requests.models.request import Request, RequestStatusEnum, RequestTypeEnum
from shared.dependencies import get_db


def create_team_request_in_db_sync(message_data: dict) -> dict:
    """
    Função síncrona para criar a TeamRequest no banco de dados.
    """
    db_gen = get_db()
    db = next(db_gen)

    try:
        print(f"DB_SYNC: Criando request para team_id: {message_data.get('team_id')}")

        team_id_str = message_data.get("team_id")
        campus_code_str = message_data.get("campus_code")
        request_type_str = message_data.get("request_type")
        user_id_str = message_data.get("user_id", None)
        reason_str = message_data.get("reason")

        if not team_id_str:
            raise ValueError("'team_id' é obrigatório na mensagem")
        if not campus_code_str:
            raise ValueError("'campus_code' é obrigatório na mensagem")
        if not request_type_str:
            raise ValueError("'request_type' é obrigatório na mensagem")

        try:
            current_request_type = RequestTypeEnum(request_type_str)
        except ValueError:
            raise ValueError(f"Request type inválido: {request_type_str}")

        try:
            team_id_for_db = uuid.UUID(team_id_str)
        except ValueError:
            raise ValueError(f"team_id '{team_id_str}' não é um UUID válido")

        print(
            f"DB_SYNC: Processando request para team_id: {team_id_for_db}, request_type: {current_request_type.value}, user_id: {user_id_str}")


        filters = [
            Request.team_id == team_id_for_db,
            Request.campus_code == campus_code_str,
            Request.request_type == current_request_type,
            Request.status == RequestStatusEnum.pendent
        ]

        if current_request_type == RequestTypeEnum.remove_team_member:
            if not user_id_str:
                raise ValueError(
                    f"'user_id' é obrigatório para o tipo de requisição '{current_request_type.value}'")
            filters.append(Request.user_id == user_id_str)

        existing_pending_request: Request = db.query(Request).filter(*filters).first()

        if existing_pending_request:
            print(
                f"DB_SYNC: Solicitação pendente já existe (ID: {existing_pending_request.id}). Nenhuma nova request será criada.")
            return {
                "message": "Solicitação pendente já existente processada como duplicada.",
                "request_id": existing_pending_request.id,
                "status": existing_pending_request.status.value
            }

        print(f"DB_SYNC: Criando nova request...")

        request_creation_data = {
            "request_type": current_request_type,
            "team_id": team_id_for_db,
            "campus_code": campus_code_str,
            "status": RequestStatusEnum.pendent,
            "created_at": datetime.fromisoformat(
                message_data["created_at"].replace("Z", "+00:00")) if message_data.get("created_at") else datetime.now(timezone.utc)
        }

        if user_id_str:
            request_creation_data["user_id"] = user_id_str

        if reason_str:
            request_creation_data["reason"] = reason_str

        new_request = Request(**request_creation_data)

        db.add(new_request)
        db.commit()
        db.refresh(new_request)

        print(f"DB_SYNC: Request ID {new_request.id} criada com sucesso para team_id: {new_request.team_id}")
        return {"request_id": new_request.id, "status": new_request.status.value}
    except Exception as e:
        db.rollback()
        print(f"DB_SYNC: Erro ao criar request no banco: {e}")
        raise
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass