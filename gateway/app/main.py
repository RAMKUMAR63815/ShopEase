
import os
import json
from typing import Any

import httpx

from fastapi import FastAPI, Request, Body, Depends
from fastapi.responses import Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


# --------------------------------------------------
# 1. Create FastAPI application
# --------------------------------------------------

app = FastAPI(
    title="ShopEase API Gateway",
    description="Central entry point for ShopEase microservices",
    version="1.0.0",
)


# --------------------------------------------------
# 2. Swagger Bearer Authentication
# --------------------------------------------------

# auto_error=False allows public APIs such as login
# to work without an Authorization token.
bearer_scheme = HTTPBearer(auto_error=False)


# --------------------------------------------------
# 3. Internal Docker service URLs
# --------------------------------------------------

SERVICES = {
    "auth": os.getenv(
        "AUTH_SERVICE_URL",
        "http://auth_service:8000",
    ),
    "users": os.getenv(
        "USER_SERVICE_URL",
        "http://user_service:8000",
    ),
    "products": os.getenv(
        "PRODUCT_SERVICE_URL",
        "http://product_service:8000",
    ),
    "orders": os.getenv(
        "ORDER_SERVICE_URL",
        "http://order_service:8000",
    ),
    "payments": os.getenv(
        "PAYMENT_SERVICE_URL",
        "http://payment_service:8000",
    ),
}


# --------------------------------------------------
# 4. Home endpoint
# --------------------------------------------------

@app.get("/")
def home():
    return {
        "service": "ShopEase API Gateway",
        "status": "running",
        "available_services": list(SERVICES.keys()),
    }


# --------------------------------------------------
# 5. Gateway health endpoint
# --------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "API Gateway",
    }


# --------------------------------------------------
# 6. Common proxy function
# --------------------------------------------------

async def proxy_request(
    method: str,
    service: str,
    path: str,
    request: Request,
    forwarded_body: bytes | None = None,
):

    # Find the requested microservice.
    service_url = SERVICES.get(service)

    if service_url is None:
        return Response(
            content='{"detail":"Service not found"}',
            status_code=404,
            media_type="application/json",
        )

    # Forward incoming headers, including JWT Authorization.
    headers = dict(request.headers)

    # Remove connection-specific headers.
    headers.pop("host", None)
    headers.pop("content-length", None)
    headers.pop("connection", None)
    headers.pop("transfer-encoding", None)

    # Read the request body if no body was supplied.
    if forwarded_body is None:
        forwarded_body = await request.body()

    # Construct destination URL.
    target_url = (
        f"{service_url.rstrip('/')}/{path.lstrip('/')}"
    )

    try:

        async with httpx.AsyncClient(
            timeout=10.0
        ) as client:

            # Forward request to the selected microservice.
            upstream_response = await client.request(
                method=method,
                url=target_url,
                params=request.query_params,
                headers=headers,
                content=forwarded_body,
            )

        # Filter connection-specific response headers.
        response_headers = {
            key: value
            for key, value in upstream_response.headers.items()
            if key.lower() not in {
                "content-length",
                "transfer-encoding",
                "connection",
                "content-encoding",
            }
        }

        # Return the original microservice response.
        return Response(
            content=upstream_response.content,
            status_code=upstream_response.status_code,
            headers=response_headers,
        )

    except httpx.TimeoutException:

        return Response(
            content='{"detail":"Service request timed out"}',
            status_code=504,
            media_type="application/json",
        )

    except httpx.RequestError:

        return Response(
            content='{"detail":"Service unavailable"}',
            status_code=503,
            media_type="application/json",
        )


# --------------------------------------------------
# 7. GET request
# --------------------------------------------------

@app.get(
    "/{service}/{path:path}",
    operation_id="gateway_proxy_get",
)
async def gateway_get(
    service: str,
    path: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
):
    return await proxy_request(
        "GET",
        service,
        path,
        request,
    )


# --------------------------------------------------
# 8. POST request with JSON body
# --------------------------------------------------

@app.post(
    "/{service}/{path:path}",
    operation_id="gateway_proxy_post",
)
async def gateway_post(
    service: str,
    path: str,
    request: Request,
    payload: dict[str, Any] = Body(...),
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
):

    body = json.dumps(payload).encode("utf-8")

    return await proxy_request(
        "POST",
        service,
        path,
        request,
        forwarded_body=body,
    )


# --------------------------------------------------
# 9. PUT request with JSON body
# --------------------------------------------------

@app.put(
    "/{service}/{path:path}",
    operation_id="gateway_proxy_put",
)
async def gateway_put(
    service: str,
    path: str,
    request: Request,
    payload: dict[str, Any] = Body(...),
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
):

    body = json.dumps(payload).encode("utf-8")

    return await proxy_request(
        "PUT",
        service,
        path,
        request,
        forwarded_body=body,
    )


# --------------------------------------------------
# 10. PATCH request with JSON body
# --------------------------------------------------

@app.patch(
    "/{service}/{path:path}",
    operation_id="gateway_proxy_patch",
)
async def gateway_patch(
    service: str,
    path: str,
    request: Request,
    payload: dict[str, Any] = Body(...),
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
):

    body = json.dumps(payload).encode("utf-8")

    return await proxy_request(
        "PATCH",
        service,
        path,
        request,
        forwarded_body=body,
    )


# --------------------------------------------------
# 11. DELETE request
# --------------------------------------------------

@app.delete(
    "/{service}/{path:path}",
    operation_id="gateway_proxy_delete",
)
async def gateway_delete(
    service: str,
    path: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
):
    return await proxy_request(
        "DELETE",
        service,
        path,
        request,
    )
