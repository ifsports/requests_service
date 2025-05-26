from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from requests.models.campus import Campus
from shared.exceptions import NotFound, Conflict

import uuid

from requests.models.request import RequestStatusEnum, Request, RequestsResponse, RequestsRequest
from shared.dependencies import get_db

router = APIRouter(
    prefix='/api/v1/campus/{campus_code}/requests',
    tags=['Requests']
)


@router.get('/', response_model=List[RequestsResponse])
def get_requests(campus_code: str,
                 status: Optional[RequestStatusEnum] = Query(None, description="Filtrar solicitações por status"),
                 db: Session = Depends(get_db)):

    campus = db.query(Campus).filter(Campus.code == campus_code).first()  # type: ignore

    if not campus:
        raise NotFound("Campus")

    query = db.query(Request).filter(Request.campus_code == campus_code) # type: ignore

    if status:
        query = query.filter(Request.status == status.value)

    return query.all()


@router.post('/', response_model=RequestsResponse, status_code=201)
def create_request(campus_code: str,
                   request_in: RequestsRequest,
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


@router.put('/approve/{request_id}', response_model=RequestsResponse, status_code=200)
def approve_request(campus_code: str,
                    request_id: uuid.UUID,
                    db: Session = Depends(get_db)) -> RequestsResponse:

    request: Request = find_by_id(request_id, campus_code, db)

    if request.status != RequestStatusEnum.pendent:
        raise Conflict("Conflito")

    request.status = RequestStatusEnum.approved

    db.add(request)
    db.commit()
    db.refresh(request)

    return request


@router.put('/reject/{request_id}', response_model=RequestsResponse, status_code=200)
def reject_request(campus_code: str,
                   request_id: uuid.UUID,
                   db: Session = Depends(get_db)) -> RequestsResponse:

    request: Request = find_by_id(request_id, campus_code, db)

    if request.status != RequestStatusEnum.pendent:
        raise Conflict("Conflito")

    request.status = RequestStatusEnum.rejected

    db.add(request)
    db.commit()
    db.refresh(request)

    return request


def find_by_id(request_id: uuid.UUID, campus_code: str, db: Session) -> Request:
    campus = db.query(Campus).filter(Campus.code == campus_code).first()  # type: ignore

    if not campus:
        raise NotFound("Campus")

    request: Request = db.query(Request).filter(Request.id == request_id, Request.campus_code == campus_code).first() # type: ignore

    if not request:
        raise NotFound("Solicitação")

    return request