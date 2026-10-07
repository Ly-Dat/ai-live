FROM docker.io/library/python:3.10

# Set the working directory
WORKDIR .

# Copy application files into the container
COPY . .


# Install application dependencies
RUN apt-get update && \
    apt-get install -y portaudio19-dev ffmpeg libasound2-dev

RUN pip install requests

# Running the AI VTuber in Docker does not work well: sound card loading is problematic, and pyautogui (keyboard/mouse simulation) also fails to load
RUN pip install -r requirements.txt -i https://pypi.org/simple/ 

# Set environment variables (if needed)

# Expose the application port (if needed)
EXPOSE 8081
EXPOSE 8082

# Start the application
CMD ["python", "webui.py"]