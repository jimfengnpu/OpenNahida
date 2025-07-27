import asyncio
from app.agent.nahida import Nahida
from app.logger import logger
from app.config import config
from app.async_timer import AsyncTimer
import signal
import os
import streamlit as st

try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

agent = Nahida(extra_system_prompt=config.agent_config.extra_prompt)

app_name = "虚空终端"
st.set_page_config(page_title=app_name)

async def main():
    for message in agent.memory.get_recent_messages(agent.context_recent):
        with st.chat_message(message.role):
            st.markdown(message.content)
    if prompt := st.chat_input(""):
        result = ""
        may_internal_cmd = prompt.lower()
        if may_internal_cmd == "/next":
            result = await agent.run("")
        elif may_internal_cmd == "/timers":
            logger.info('\n'.join([str(t) for t in AsyncTimer.timers]))
        elif may_internal_cmd == "/llmreload":
            agent.llm.reload()
            # logger.warning("Processing your request...")
        elif may_internal_cmd == "/bye":
            await AsyncTimer.close()
            agent.close()
            os.kill(os.getpid(), signal.SIGTERM)
        elif prompt:
            with st.chat_message('user'):
                st.markdown(prompt)
            result = await agent.run(prompt)
        if result:
            with st.chat_message('assistant'):
                st.markdown(result)


if __name__ == "__main__":
    asyncio.run(main())
