from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from web.backend.app.api import router
from web.backend.app.api.admin import router as admin_router
from web.backend.app.api.auth import router as auth_router
from web.backend.app.errors import WebApiError
from web.backend.app.schemas import ErrorDetail, ErrorResponse, HealthResponse


app = FastAPI(title="ForensiHash API")
app.include_router(router)
app.include_router(auth_router)
app.include_router(admin_router)


@app.exception_handler(WebApiError)
async def web_api_error_handler(_request: Request, error: WebApiError) -> JSONResponse:
    payload = ErrorResponse(
        error=ErrorDetail(
            code=error.code,
            message=error.message,
            request_id=error.request_id,
        )
    )
    return JSONResponse(status_code=error.status_code, content=payload.model_dump())


@app.exception_handler(RequestValidationError)
async def request_validation_handler(
    _request: Request, _error: RequestValidationError
) -> JSONResponse:
    payload = ErrorResponse(
        error=ErrorDetail(
            code="invalid_request",
            message="A requisição enviada é inválida.",
            request_id=str(uuid4()),
        )
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=payload.model_dump(),
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="forensihash-api")
