from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from messaging.request_event_publisher import publish_team_creation_request, publish_team_remove_request
from requests.models.campus import Campus
from shared.exceptions import NotFound, Conflict

import uuid

from requests.models.request import (RequestStatusEnum, Request,
                                     RequestsResponse, RequestsPutRequest, RequestsCreateRequest, RequestTypeEnum)
from shared.dependencies import get_db

router = APIRouter(
    prefix='/api/v1/campus/{campus_code}/requests',
    tags=['Requests']
)


@router.get('/', response_model=List[RequestsResponse])
def get_requests(campus_code: str,
                 status: Optional[RequestStatusEnum] = Query(None, description="Filtrar solicitações por status"),
                 request_type: Optional[RequestTypeEnum] = Query(None, description="Filtrar solicitações por tipo"),
                 db: Session = Depends(get_db)):

    campus = db.query(Campus).filter(Campus.code == campus_code).first()  # type: ignore

    if not campus:
        raise NotFound("Campus")

    query = db.query(Request).filter(Request.campus_code == campus_code) # type: ignore

    if status:
        query = query.filter(Request.status == status.value)

    if request_type:
        query = query.filter(Request.request_type == request_type.value)

    return query.all()


@router.post('/', response_model=RequestsResponse, status_code=201)
def create_request(campus_code: str,
                   request_in: RequestsCreateRequest,
                   db: Session = Depends(get_db)) -> RequestsResponse:

    request = Request(**request_in.model_dump())

    campus = db.query(Campus).filter(Campus.code == campus_code).first() # type: ignore

    if not campus:
        raise NotFound("Campus")

    request.campus_code = campus_code

    db.add(request)
    db.commit()
    db.refresh(request)

    return request


@router.get('/{request_id}', response_model=RequestsResponse, status_code=200)
def details_request(campus_code: str,
                    request_id: uuid.UUID,
                    db: Session = Depends(get_db)) -> RequestsResponse:

    request: Request = find_by_id(request_id, campus_code, db)

    return request


@router.put('/{request_id}', status_code=202)
async def update_request_reason_rejected(campus_code: str,
                                   request_id: uuid.UUID,
                                   request_in: RequestsPutRequest,
                                   db: Session = Depends(get_db)):

    request: Request = find_by_id(request_id, campus_code, db)

    if request.status != RequestStatusEnum.pendent:
        raise Conflict("Conflito")

    if request_in.status:
        request.status = request_in.status.value

    if request_in.reason_rejected:
        request.reason_rejected = request_in.reason_rejected

    db.add(request)
    db.commit()
    db.refresh(request)

    add_team_request_message_data = {
        "team_id": str(request.team_id),
        "campus_code": request.campus_code,
        "status": request.status.value,
    }


    if request.request_type == RequestTypeEnum.approve_team:
        add_team_request_message_data["request_type"] = RequestTypeEnum.approve_team.value

        await publish_team_creation_request(add_team_request_message_data)

        return {
            "message": "Solicitação para criação de equipe atualizada!",
            "team_id": request.team_id,
            "campus_code": request.campus_code,
        }


    if request.request_type == RequestTypeEnum.delete_team:
        add_team_request_message_data["request_type"] = RequestTypeEnum.delete_team.value

        await publish_team_remove_request(add_team_request_message_data)

        return {
            "message": "Solicitação para remoção de equipe atualizada!",
            "team_id": request.team_id,
            "campus_code": request.campus_code,
        }


    if request.request_type == RequestTypeEnum.add_team_member:
        add_team_request_message_data["request_type"] = RequestTypeEnum.add_team_member.value
        add_team_request_message_data["user_id"] = str(request.user_id)

        await publish_team_remove_request(add_team_request_message_data)

        return {
            "message": "Solicitação para adição de membro atualizada!",
            "team_id": request.team_id,
            "user_id": request.user_id,
            "campus_code": request.campus_code,
        }

    if request.request_type == RequestTypeEnum.remove_team_member:
        add_team_request_message_data["request_type"] = RequestTypeEnum.remove_team_member.value
        add_team_request_message_data["user_id"] = str(request.user_id)

        await publish_team_remove_request(add_team_request_message_data)

        return {
            "message": "Solicitação para remoção de membro atualizada!",
            "team_id": request.team_id,
            "user_id": request.user_id,
            "campus_code": request.campus_code,
        }

    return {
        "message": "Solicitação atualizada com sucesso!"
    }


def find_by_id(request_id: uuid.UUID, campus_code: str, db: Session) -> Request:
    campus = db.query(Campus).filter(Campus.code == campus_code).first()  # type: ignore

    if not campus:
        raise NotFound("Campus")

    request: Request = db.query(Request).filter(Request.id == request_id, Request.campus_code == campus_code).first() # type: ignore

    if not request:
        raise NotFound("Solicitação")

    return request