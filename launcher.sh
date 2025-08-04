#!/bin/sh
port=8501
/home/jimfeng/anaconda3/envs/open_manus/bin/streamlit run /home/jimfeng/Documents/项目/OpenNahida/main_gui.py --server.address 0.0.0.0 --server.port $port &
google-chrome --new-window --window-size="800,600" localhost:$port
# konsole -e /home/jimfeng/anaconda3/envs/open_manus/bin/python /home/jimfeng/Documents/项目/OpenNahida/main.py
