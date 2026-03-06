import pytest

from app.services.processor import ACTION_HANDLERS, echo, handle


@pytest.mark.asyncio
async def test_handle_echo():
    result = await handle("echo", {"x": 1})
    assert result == {"echo": {"x": 1}}


@pytest.mark.asyncio
async def test_handle_unknown_raises():
    with pytest.raises(ValueError, match="Acción desconocida"):
        await handle("no_existe", {})


@pytest.mark.asyncio
async def test_echo_directly():
    result = await echo({"hello": "world"})
    assert result == {"echo": {"hello": "world"}}


def test_action_handlers_has_echo():
    assert "echo" in ACTION_HANDLERS
