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

avatar_url = "https://images-wixmp-ed30a86b8c4ca887773594c2.wixmp.com/f/0d65c16d-8083-42b6-a0f0-e1e3c70b3124/dfu4bvo-28736225-9a0a-410e-8c53-d8d34aea3bfd.png/v1/fill/w_894,h_894,q_70,strp/nahida_avatars__by_claudiaiaai_dfu4bvo-pre.jpg?token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1cm46YXBwOjdlMGQxODg5ODIyNjQzNzNhNWYwZDQxNWVhMGQyNmUwIiwiaXNzIjoidXJuOmFwcDo3ZTBkMTg4OTgyMjY0MzczYTVmMGQ0MTVlYTBkMjZlMCIsIm9iaiI6W1t7ImhlaWdodCI6Ijw9MTI4MCIsInBhdGgiOiJcL2ZcLzBkNjVjMTZkLTgwODMtNDJiNi1hMGYwLWUxZTNjNzBiMzEyNFwvZGZ1NGJ2by0yODczNjIyNS05YTBhLTQxMGUtOGM1My1kOGQzNGFlYTNiZmQucG5nIiwid2lkdGgiOiI8PTEyODAifV1dLCJhdWQiOlsidXJuOnNlcnZpY2U6aW1hZ2Uub3BlcmF0aW9ucyJdfQ.6DmcOFWtRzRlHQ1najLv7F9iIfI7U2oxzsCU_wM0zt4"
app_name = "虚空终端"
st.set_page_config(page_title=app_name)

@st.cache_resource
def init_agent():
    return Nahida(extra_system_prompt=config.agent_config.extra_prompt)

agent = init_agent()

async def main():
    for message in agent.memory.get_recent_messages(agent.context_recent):
        with st.chat_message(message.role, avatar=avatar_url if message.role == "assistant" else None):
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
        elif may_internal_cmd == "/exit":
            await AsyncTimer.close()
            agent.close()
            os.kill(os.getpid(), signal.SIGTERM)
        elif prompt:
            with st.chat_message('user'):
                st.markdown(prompt)
            result = await agent.run(prompt)
        if result:
            with st.chat_message('assistant', avatar=avatar_url):
                st.markdown(result)


if __name__ == "__main__":
    asyncio.run(main())
