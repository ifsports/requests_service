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

        new_request = Request(
            team_id=message_data.get("team_id"),
            campus_code=message_data.get("campus_code"),
            request_type=RequestTypeEnum.approve_team,
            status=RequestStatusEnum.pendent,
            created_at=datetime.now(timezone.utc)
        )

        existing_pending_request: Request = db.query(Request).filter(
            Request.team_id == new_request.team_id,
            Request.request_type == new_request.request_type,
            Request.status == new_request.status
        ).first()

        if existing_pending_request:
            return {
                "message": "Solicitação pendente já existente processada como duplicada.",
                "request_id": existing_pending_request.id,
                "status": existing_pending_request.status.value
            }

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