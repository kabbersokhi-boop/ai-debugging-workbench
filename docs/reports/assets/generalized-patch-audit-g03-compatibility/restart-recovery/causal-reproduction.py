"""Controlled legacy deadline reproduction; no network, Docker, DB or candidate execution.

Run: uv run --project backend python <this-file>
Legacy loop matches service.py at reviewed 41c1bb0. Scheduling only is controlled:
the real asyncio timeout is moved to the AnyIO connection-scope cancellation window.
"""

import asyncio
import importlib.metadata
import json

import anyio


async def main():
    entered, connected = asyncio.Event(), asyncio.Event()
    deadline = asyncio.timeout(None)
    polls = 0

    async def terminal():
        nonlocal polls
        polls += 1
        if polls == 1:
            async with anyio.create_task_group() as group:

                async def connection_attempt():
                    entered.set()
                    await connected.wait()
                    group.cancel_scope.cancel()

                group.start_soon(connection_attempt)
                await anyio.sleep_forever()
        return None

    async def legacy_wait_terminal():
        async with deadline:
            while True:
                result = await terminal()
                if result is not None:
                    return result
                await asyncio.sleep(0.3)

    task = asyncio.create_task(legacy_wait_terminal())
    await entered.wait()
    connected.set()
    # Public APIs only. Match a native deadline expiring while connect_tcp's
    # successful child cancels the AnyIO connection task group.
    asyncio.get_running_loop().call_soon(deadline.reschedule, asyncio.get_running_loop().time())
    done, _ = await asyncio.wait({task}, timeout=0.65)
    observation = {
        "anyio_version": importlib.metadata.version("anyio"),
        "deadline_expired": deadline.expired(),
        "polls": polls,
        "task_done": task.done(),
        "task_cancelled": task.cancelled(),
        "pending_native_cancellations": task.cancelling(),
        "legacy_polling_outlived_expired_deadline": not done and deadline.expired() and polls > 1,
        "exact_original_ci_schedule_reproduced": False,
        "controlled_cancellation_mechanism_reproduced": not done and task.cancelling() > 0,
    }
    # Clean up the known losing legacy loop. This is not a trial retry.
    task.cancel("bounded causal harness cleanup")
    try:
        await task
    except (asyncio.CancelledError, TimeoutError):
        pass
    observation["harness_task_cleaned_up"] = task.done()
    print(json.dumps(observation, indent=2))


asyncio.run(main())
