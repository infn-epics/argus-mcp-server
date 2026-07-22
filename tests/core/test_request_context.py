import structlog.contextvars

from argus.core.request_context import request_scope


async def test_request_scope_binds_request_id_only_by_default():
    with request_scope() as rid:
        bound = structlog.contextvars.get_contextvars()
        assert bound["request_id"] == rid
        assert "conversation_id" not in bound


async def test_request_scope_binds_extra_fields():
    with request_scope(extra={"conversation_id": "conv-1", "user_id": "user-1"}):
        bound = structlog.contextvars.get_contextvars()
        assert bound["conversation_id"] == "conv-1"
        assert bound["user_id"] == "user-1"
        assert "request_id" in bound


async def test_request_scope_unbinds_everything_on_exit():
    with request_scope(extra={"conversation_id": "conv-1"}):
        pass
    bound = structlog.contextvars.get_contextvars()
    assert "request_id" not in bound
    assert "conversation_id" not in bound


async def test_request_scope_with_no_extra_does_not_error():
    with request_scope(extra=None):
        bound = structlog.contextvars.get_contextvars()
        assert "request_id" in bound
