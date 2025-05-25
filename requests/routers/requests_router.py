from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

import uuid

from requests.models.request import RequestStatusEnum, Request, RequestsResponse, RequestsRequest
from shared.dependencies import get_db

router = APIRouter(prefix='/requests')


@router.get('/', response_model=List[RequestsResponse])
def get_requests(status: Optional[RequestStatusEnum] = Query(None, description="Filtrar solicitações por status"),
                 db: Session = Depends(get_db)):
    query = db.query(Request)
    if status:
        query = query.filter(Request.status == status.value)
    return query.all()


@router.post('/', response_model=RequestsResponse, status_code=201)
def create_request(request_in: RequestsRequest,
                   db: Session = Depends(get_db)) -> RequestsResponse:

    request = Request(**request_in.model_dump())

    db.add(request)
    db.commit()
    db.refresh(request)

    return request


@router.put('/approve/{request_id}', response_model=RequestsResponse, status_code=200)
def create_request(request_id: uuid.UUID,
                   db: Session = Depends(get_db)) -> RequestsResponse:

    request: Request = db.query(Request).get(request_id)
    request.status = RequestStatusEnum.approved

    db.add(request)
    db.commit()
    db.refresh(request)

    return request


@router.put('/reject/{request_id}', response_model=RequestsResponse, status_code=200)
def create_request(request_id: uuid.UUID,
                   db: Session = Depends(get_db)) -> RequestsResponse:

    request: Request = db.query(Request).get(request_id)
    request.status = RequestStatusEnum.rejected

    db.add(request)
    db.commit()
    db.refresh(request)

    return request