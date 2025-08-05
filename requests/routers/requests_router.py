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
                 request_type: Optional[RequestTypeEnum] = Query(
                     None, description="Filtrar solicitações por tipo"),
                 db: Session = Depends(get_db),
                 current_user: dict = Depends(get_current_user)):
    """
    List Requests

    Lista as solicitações pendentes, aprovadas ou rejeitadas. O acesso é restrito para usuários com o papel 'Organizador'.
    É possível filtrar a lista por status (ex: `pending`) ou por tipo de solicitação (ex: `approve_team`).

    **Exemplo de Resposta:**

    .. code-block:: json

       [
         {
           "id": "a1b2c3d4-e5f6-a7b8-c9d0-e1f2a3b4c5d6",
           "request_type": "approve_team",
           "status": "pending",
           "reason": null,
           "reason_rejected": null,
           "campus_code": "NAT-CN",
           "team_id": "c1d2e3f4-a5b6-b7c8-d9e0-f1a2b3c4d5e6",
           "user_id": null,
           "competition_id": "d1e2f3a4-b5c6-d7e8-f9a0-b1c2d3e4f5a6",
           "created_at": "2025-08-04T21:14:25.123Z"
         },
         {
           "id": "b2c3d4e5-f6a7-b8c9-d0e1-f2a3b4c5d6e7",
           "request_type": "add_team_member",
           "status": "pending",
           "reason": null,
           "reason_rejected": null,
           "campus_code": "NAT-CN",
           "team_id": "c1d2e3f4-a5b6-b7c8-d9e0-f1a2b3c4d5e6",
           "user_id": "20231012030015",
           "competition_id": null,
           "created_at": "2025-08-04T22:30:00.000Z"
         }
       ]
    """
    campus_code = current_user["campus"]
    groups = current_user["groups"]

    query = db.query(Request).filter(
        Request.campus_code == campus_code)  # type: ignore

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
    """
    Get Request Details

    Busca os detalhes de uma solicitação específica pelo seu ID.
    O acesso é restrito para usuários com o papel 'Organizador'.

    **Exemplo de Resposta:**

    .. code-block:: json

       {
         "id": "a1b2c3d4-e5f6-a7b8-c9d0-e1f2a3b4c5d6",
         "request_type": "approve_team",
         "status": "pending",
         "reason": "Criação da equipe para os JIFs 2025.",
         "reason_rejected": null,
         "campus_code": "NAT-CN",
         "team_id": "c1d2e3f4-a5b6-b7c8-d9e0-f1a2b3c4d5e6",
         "user_id": null,
         "competition_id": "d1e2f3a4-b5c6-d7e8-f9a0-b1c2d3e4f5a6",
         "created_at": "2025-08-04T21:14:25.123Z"
       }
    """
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
    """
    Approve or Reject a Request

    Aprova ou rejeita uma solicitação pendente. Esta ação é realizada por um 'Organizador'.
    A rota atualiza o status da solicitação e publica um evento para que o serviço correspondente
    (ex: serviço de times) execute a ação final (criar time, adicionar membro, etc.).

    - Para rejeitar, o status deve ser `rejected` e o campo `reason_rejected` é obrigatório.
    - Para aprovar, o status deve ser `approved`.

    **Exemplo de Corpo da Requisição (Aprovação):**

    .. code-block:: json

       {
         "status": "approved"
       }

    **Exemplo de Corpo da Requisição (Rejeição):**

    .. code-block:: json

       {
         "status": "rejected",
         "reason_rejected": "A equipe não possui o número mínimo de membros inscritos."
       }


    **Exemplo de Resposta (202 Accepted):**

    .. code-block:: json

       {
         "message": "Solicitação para criação de equipe atualizada!",
         "team_id": "c1d2e3f4-a5b6-b7c8-d9e0-f1a2b3c4d5e6",
         "campus_code": "NAT-CN"
       }
    """
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

    request: Request = db.query(Request).filter(
        Request.id == request_id, Request.campus_code == campus_code).first()  # type: ignore

    if not request:
        raise NotFound("Solicitação")

    return request
