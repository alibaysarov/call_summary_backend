import asyncio
import functools
import time
from typing import Callable, ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


def timeit(func: Callable[P, T]) -> Callable[P, T]:
    """
    Декоратор, измеряющий время выполнения функции.
    Работает как с синхронными, так и с асинхронными функциями.
    """

    if asyncio.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            start = time.perf_counter()
            try:
                return await func(*args, **kwargs)  # type: ignore[no-any-return]
            finally:
                elapsed = time.perf_counter() - start
                print(f"[{func.__name__}] выполнена за {elapsed:.4f} сек")

        return async_wrapper  # type: ignore[return-value]

    else:

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - start
                print(f"[{func.__name__}] выполнена за {elapsed:.4f} сек")

        return sync_wrapper