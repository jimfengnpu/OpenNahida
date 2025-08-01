import asyncio

from app.agent.nahida import Nahida
from app.logger import logger
from app.config import config
from app.async_timer import AsyncTimer
import traceback


async def main():
    loop = asyncio.get_event_loop()
    agent = Nahida(extra_system_prompt=config.agent_config.extra_prompt)
    while True:
        try:
            prompt = await loop.run_in_executor(None, input, ">>>")
            result = ""
            may_internal_cmd = prompt.lower()
            if may_internal_cmd == "exit":
                logger.info("Goodbye!")
                break
            elif may_internal_cmd == "next":
                result = await agent.run("")
                continue
            elif may_internal_cmd == "abort":
                exit(-1)
                break
            elif may_internal_cmd == "timers":
                logger.info('\n'.join([str(t) for t in AsyncTimer.timers]))
                continue
            elif may_internal_cmd == "llmreload":
                agent.llm.reload()
                continue
            # logger.warning("Processing your request...")
            if prompt:
                result = await agent.run(prompt)
            if result:
                print(result)
        except (Exception, asyncio.CancelledError, KeyboardInterrupt, EOFError)  as e:
            logger.error(e)
            traceback.print_exc()
    await AsyncTimer.close()
    agent.close()


if __name__ == "__main__":
    asyncio.run(main())
