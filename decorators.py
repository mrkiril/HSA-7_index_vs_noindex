import asyncio
import logging
from functools import wraps

logger = logging.getLogger(__name__)


def async_retry(times, exceptions, timeout=1, async_callback=None):
    """
    Retry ASYNC Decorator
    Retries the wrapped function/method `times` times if the exceptions listed
    in ``exceptions`` are thrown
    :param times: The number of times to repeat the wrapped function/method
    :type times: Int
    :param Exceptions: Lists of exceptions that trigger a retry attempt
    :type Exceptions: Tuple of Exceptions
    """

    def decorator(func):
        @wraps(func)
        async def wrapped(*args, **kwargs):
            attempt = 0
            while attempt < times:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    logger.warning(
                        "Exception thrown when attempting to run %s, attempt "
                        "%d of %d", func, attempt, times, exc_info=e
                    )
                    if async_callback:
                        await async_callback()
                    await asyncio.sleep(timeout*(attempt+1))
                    attempt += 1
            return await func(*args, **kwargs)

        return wrapped

    return decorator
