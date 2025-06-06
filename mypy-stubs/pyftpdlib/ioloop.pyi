import asynchat
from asyncore import _MapType
from _typeshed import ReadableBuffer

from .log import (
    config_logging as config_logging,
    debug as debug,
    is_logging_configured as is_logging_configured,
    logger as logger,
)

import select
import socket
import socket as socket_module
from typing import (
    Any,
    Callable,
    Sized,
    Tuple,
    Type,
)

from typing_extensions import (
    Protocol,
)

class AnyCallable(Protocol):
    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...

TimerProc = Callable[[], float]

timer: TimerProc

class RetryError(Exception): ...

class _Scheduler:
    def __init__(self) -> None: ...
    def poll(self) -> float: ...
    def register(self, what: _CallLater) -> None: ...
    def unregister(self, what: _CallLater) -> None: ...
    def reheapify(self) -> None: ...
    def close(self) -> None: ...

class _CallLater:
    timeout: int
    cancelled: bool
    def __init__(
        self, seconds: float, target: AnyCallable, *args: Any, **kwargs: Any
    ) -> None: ...
    def __lt__(self, other: _CallLater) -> bool: ...
    def __le__(self, other: _CallLater) -> bool: ...
    def call(self) -> None: ...
    def reset(self) -> None: ...
    def cancel(self) -> None: ...

class _CallEvery(_CallLater): ...

class _IOLoop:
    READ: int
    WRITE: int
    socket_map: dict[int, AsyncChat]
    sched: _Scheduler
    def __init__(self) -> None: ...
    def __enter__(self) -> _IOLoop: ...
    def __exit__(self, *args: Any) -> None: ...
    @classmethod
    def instance(cls) -> _IOLoop: ...
    @classmethod
    def factory(cls) -> _IOLoop: ...
    def register(self, fd: int, instance: AsyncChat, events: int) -> None: ...
    def unregister(self, fd: int) -> None: ...
    def modify(self, fd: int, events: int) -> None: ...
    def poll(self, timeout: float) -> None: ...
    def loop(self, timeout: float | None = None, blocking: bool = True) -> float: ...
    def call_later(
        self, seconds: float, target: AnyCallable, *args: Any, **kwargs: Any
    ) -> _CallLater: ...
    def call_every(
        self, seconds: float, target: AnyCallable, *args: Any, **kwargs: Any
    ) -> _CallEvery: ...
    def close(self) -> None: ...

class Select(_IOLoop):
    def __init__(self) -> None: ...
    def register(self, fd: int, instance: AsyncChat, events: int) -> None: ...
    def unregister(self, fd: int) -> None: ...
    def modify(self, fd: int, events: int) -> None: ...
    def poll(self, timeout: float) -> None: ...

class _BasePollEpoll(_IOLoop):
    def __init__(self) -> None: ...
    def register(self, fd: int, instance: AsyncChat, events: int) -> None: ...
    def unregister(self, fd: int) -> None: ...
    def modify(self, fd: int, events: int) -> None: ...
    def poll(self, timeout: float) -> None: ...

class Poll(_BasePollEpoll):
    READ: int
    WRITE: int
    def modify(self, fd: int, events: int) -> None: ...
    def poll(self, timeout: float) -> None: ...

class DevPoll(_BasePollEpoll):
    READ: int
    WRITE: int
    def fileno(self) -> int: ...
    def modify(self, fd: int, events: int) -> None: ...
    def poll(self, timeout: float) -> None: ...
    def close(self) -> None: ...

class Epoll(_BasePollEpoll):
    READ: int
    WRITE: int
    def fileno(self) -> int: ...
    def close(self) -> None: ...

class Kqueue(_IOLoop):
    def __init__(self) -> None: ...
    def fileno(self) -> int: ...
    def close(self) -> None: ...
    def register(self, fd: int, instance: AsyncChat, events: int) -> None: ...
    def unregister(self, fd: int) -> None: ...
    def modify(self, fd: int, events: int) -> None: ...
    def poll(
        self,
        timeout: float,
        _len: Sized = ...,
        _READ: int = ...,
        _WRITE: int = ...,
        _EOF: int = ...,
        _ERROR: int = ...,
    ) -> None: ...

IOLoop: Type[Epoll] | Type[Kqueue] | Type[DevPoll] | Type[Poll] | Type[Select]

class AsyncChat(asynchat.async_chat):  # type: ignore[misc]
    ioloop: _IOLoop
    def __init__(
        self, sock: socket.socket | None = None, ioloop: _IOLoop | None = None
    ) -> None: ...
    def add_channel(
        self, map: _MapType | None = None, events: int | None = None
    ) -> None: ...
    def del_channel(self, map: _MapType | None = None) -> None: ...
    def modify_ioloop_events(self, events: int, logdebug: bool = False) -> None: ...
    def call_later(
        self, seconds: float, target: AnyCallable, *args: Any, **kwargs: Any
    ) -> _CallLater: ...
    def connect(self, addr: Tuple[Any, ...] | str) -> None: ...
    socket: socket.socket | None
    def connect_af_unspecified(
        self, addr: Tuple[Any, ...] | str, source_address: Tuple[str, int] | None = None
    ) -> int: ...
    def send(self, data: ReadableBuffer) -> int: ...
    def recv(self, buffer_size: int) -> bytes: ...
    def handle_read(self) -> None: ...
    def initiate_send(self) -> None: ...
    def close_when_done(self) -> None: ...
    connected: bool
    def close(self) -> None: ...

class Connector(AsyncChat):  # type: ignore[misc]
    def add_channel(
        self, map: _MapType | None = None, events: int | None = None
    ) -> None: ...

class Acceptor(AsyncChat):  # type: ignore[misc]
    def add_channel(
        self, map: _MapType | None = None, events: int | None = None
    ) -> None: ...
    socket: socket_module.socket | None
    def bind_af_unspecified(self, addr: Tuple[str, int]) -> int: ...
    def listen(self, num: int) -> None: ...
    def handle_accept(self) -> None: ...
    def handle_accepted(
        self, sock: socket_module.socket, addr: Tuple[str, int]
    ) -> None: ...
    def set_reuse_addr(self) -> None: ...
