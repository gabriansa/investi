import time
from agents import RunContextWrapper, function_tool
from src.agent.context import Context


@function_tool
def sleep(
    ctx: RunContextWrapper[Context],
    minutes: int,
    ):
    """
    Sleeps for a specified number of minutes.

    Args:
        minutes (required): The number of minutes to sleep (maximum 15 minutes).
    """
    if minutes > 15:
        return {"error": f"Maximum sleep time is 15 minutes. You requested {minutes} minutes. Please request a shorter sleep time or set a task for a future date."}
    time.sleep(minutes * 60)
    return f"Slept for {minutes} minutes"
