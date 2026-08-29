#!/bin/bash

# 1. Start the FastAPI/Flask backend in the background on default port 5000
python run.py &

# Wait a second to ensure backend boots up
sleep 2

# 2. Start the Streamlit frontend in the foreground on HuggingFace's required port 7860
streamlit run streamlit_app/main.py --server.port 7860 --server.address 0.0.0.0
