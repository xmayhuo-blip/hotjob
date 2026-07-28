#!/bin/bash
# hotjob start script — Railway runs this directly
cd "$(dirname "$0")/web" && python app.py
