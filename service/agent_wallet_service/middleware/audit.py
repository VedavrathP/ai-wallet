"""Audit logging middleware."""

import hashlib
import json
from typing import Callable, Optional
from uuid import UUID

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from agent_wallet_service.db.session import AsyncSessionLocal
from agent_wallet_service.models.audit_log import AuditLog


def hash_request_body(body: bytes) -> str:
    """Create a SHA-256 hash of the request body."""
    return hashlib.sha256(body).hexdigest()


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware for logging all API requests."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and log audit information."""
        # Skip health check endpoint
        if request.url.path == "/health":
            return await call_next(request)

        # Get request information
        route = request.url.path
        method = request.method
        ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")[:512]

        # Read and hash request body for POST/PUT/PATCH
        request_hash: Optional[str] = None
        if method in ("POST", "PUT", "PATCH"):
            body = await request.body()
            if body:
                request_hash = hash_request_body(body)

        # Process the request
        response = await call_next(request)

        # Get API key ID from request state (set by auth middleware)
        api_key_id: Optional[UUID] = getattr(request.state, "api_key_id", None)

        # Log the request asynchronously
        await self._log_request(
            api_key_id=api_key_id,
            route=route,
            method=method,
            ip=ip,
            user_agent=user_agent,
            request_hash=request_hash,
            response_status=response.status_code,
        )

        return response

    def _get_client_ip(self, request: Request) -> Optional[str]:
        """Extract client IP from request headers or connection."""
        # Check X-Forwarded-For header first (for proxied requests)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fall back to direct connection
        if request.client:
            return request.client.host

        return None

    async def _log_request(
        self,
        api_key_id: Optional[UUID],
        route: str,
        method: str,
        ip: Optional[str],
        user_agent: Optional[str],
        request_hash: Optional[str],
        response_status: int,
    ) -> None:
        """Log the request to the database."""
        try:
            async with AsyncSessionLocal() as db:
                audit_log = AuditLog(
                    api_key_id=api_key_id,
                    route=route,
                    method=method,
                    ip=ip,
                    user_agent=user_agent,
                    request_hash=request_hash,
                    response_status=response_status,
                )
                db.add(audit_log)
                await db.commit()
        except Exception:
            # Don't fail the request if audit logging fails
            # In production, you might want to log this to a separate system
            pass


def setup_audit_middleware(app: ASGIApp) -> AuditMiddleware:
    """Create and return the audit middleware."""
    return AuditMiddleware(app)
