from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi import Request as RequestObject
from sqlalchemy.orm import Session

from auth import get_current_user
from messaging.request_event_publisher import publish_team_creation_request, publish_team_remove_request, \
    publish_member_add_request, publish_member_remove_request
from shared.auth_utils import has_role
from shared.exceptions import NotFound, Conflict

import uuid

from requests.models.request import (RequestStatusEnum, Request,
                                     RequestsResponse, RequestsPutRequest, RequestsCreateRequest, RequestTypeEnum)
from shared.dependencies import get_db

from messaging.audit_publisher import generate_log_payload, run_async_audit, model_to_dict

router = APIRouter(
    prefix='/api/v1/requests',
    tags=['Requests']
)


@router.get('/', response_model=List[RequestsResponse])
def get_requests(status: Optional[RequestStatusEnum] = Query(None, description="Filtrar solicitações por status"),
                 request_type: Optional[RequestTypeEnum] = Query(None, description="Filtrar solicitações por tipo"),
                 db: Session = Depends(get_db),
                 current_user: dict = Depends(get_current_user)):

    campus_code = current_user["campus"]
    groups = current_user["groups"]

    query = db.query(Request).filter(Request.campus_code == campus_code) # type: ignore

    if status:
        query = query.filter(Request.status == status.value)

    if request_type:
        query = query.filter(Request.request_type == request_type.value)

    if has_role(groups, "Organizador"):
        return query.all()

    else:
        raise HTTPException(
            status_code=403,
            detail="Você não tem permissão para visualizar as solicitações."
        )


@router.get('/{request_id}', response_model=RequestsResponse, status_code=200)
def details_request(request_id: uuid.UUID,
                    db: Session = Depends(get_db),
                    current_user: dict = Depends(get_current_user)) -> RequestsResponse:

    campus_code = current_user["campus"]
    groups = current_user["groups"]

    request = find_by_id(request_id, campus_code, db)

    response = RequestsResponse.model_validate(request)

    if has_role(groups, "Organizador"):
        return response

    else:
        raise HTTPException(
            status_code=403,
            detail="Você não tem permissão para visualizar essa solicitação."
        )


@router.put('/{request_id}', status_code=202)
async def update_request_reason_rejected(request_id: uuid.UUID,
                                         request_in: RequestsPutRequest,
                                         request_object: RequestObject,
                                         db: Session = Depends(get_db),
                                         current_user: dict = Depends(get_current_user)):

    campus_code = current_user["campus"]
    groups = current_user["groups"]

    request: Request = find_by_id(request_id, campus_code, db)

    if request.status != RequestStatusEnum.pendent:
        raise Conflict("Conflito")

    old_data = model_to_dict(request)

    if request_in.status:
        request.status = request_in.status

    if request_in.reason_rejected:
        if request_in.status != RequestStatusEnum.rejected:
            raise Conflict("Conflito")
        request.reason_rejected = request_in.reason_rejected

    if has_role(groups, "Organizador"):
        db.add(request)
        db.commit()
        db.refresh(request)

        log_payload = None
        event_type = None

        if old_data.get("status") != request.status.value:
            if request.status == RequestStatusEnum.rejected:
                event_type = "request.rejected"
            elif request.status == RequestStatusEnum.approved:
                event_type = "request.approved"
        
        if event_type:
            new_data = model_to_dict(request)

            log_payload = generate_log_payload(
                event_type=event_type,
                service_origin="requests_service",
                entity_type="request",
                entity_id=request.id,
                operation_type="UPDATE",
                campus_code=request.campus_code,
                user_registration=current_user.get("matricula"),
                request_object=request_object,
                old_data=old_data,
                new_data=new_data
            )

            run_async_audit(log_payload)

        add_team_request_message_data = {
            "team_id": str(request.team_id),
            "campus_code": request.campus_code,
            "status": request.status.value,
            "competition_id": str(request.competition_id),
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

            await publish_member_add_request(add_team_request_message_data)

            return {
                "message": "Solicitação para adição de membro atualizada!",
                "team_id": request.team_id,
                "user_id": request.user_id,
                "campus_code": request.campus_code,
            }

        if request.request_type == RequestTypeEnum.remove_team_member:
            add_team_request_message_data["request_type"] = RequestTypeEnum.remove_team_member.value
            add_team_request_message_data["user_id"] = str(request.user_id)

            await publish_member_remove_request(add_team_request_message_data)

            return {
                "message": "Solicitação para remoção de membro atualizada!",
                "team_id": request.team_id,
                "user_id": request.user_id,
                "campus_code": request.campus_code,
            }

        return {
            "message": "Solicitação atualizada com sucesso!"
        }

    else:
        raise HTTPException(
            status_code=403,
            detail="Você não tem permissão para atualizar solicitações."
        )


def find_by_id(request_id: uuid.UUID, campus_code: str, db: Session) -> Request:

    request: Request = db.query(Request).filter(Request.id == request_id, Request.campus_code == campus_code).first() # type: ignore

    if not request:
        raise NotFound("Solicitação")

    return request