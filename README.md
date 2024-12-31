# RepoChat - A Chatbot for GitHub Repository Metadata
This tool is a chatbot that allows users to easily access the metadata of their GitHub repositories. It answers questions about users, commits, issues, and files, providing an interactive way to explore repository data.

It is accesible at https://repochattool.streamlit.app/

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)

## Features

- Interactive chatbot interface to query GitHub repository metadata.
- Supports queries about users, commits, issues, and files.
- Web-based interface built with Streamlit.
- Backend API powered by python flask.
- Caching with Redis for keeping conversation history and improved performance.

## Prerequisites

- **Python 3.10**: Ensure you have Python 3.10 installed, as it is required for compatibility with the dependencies.
- **Git**: Required for cloning the repository.
- **Redis**: Install and configure Redis for caching on port `6379`.

## Installation

1. **Clone the Repository**

   ```bash
   git clone https://github.com/sabedu/repositoryChat.git
   cd repositoryChat
   ```

2. **Set Up a Virtual Environment**
    It's recommended to use a virtual environment to manage dependencies.

    ```bash
    python3.10 -m venv venv
    source venv/bin/activate
    ```

3. **Install Dependencies**

    ```bash
    pip install -r requirements.txt
    ```

## Configuration
1. **Setting Up Redis Cache**
    ***Install Redis***

    Install Redis on your system. For local development, you can download and install it from the official website.

    ***Start Redis Server***

    Start the Redis server on port 6379.

    ```bash
    redis-server
    ```
    Configure Redis Host

    The Redis host will be:

    ```plaintext
    REDIS_HOST='redis://127.0.0.1:6379'
    ```

2. **Environment Variables**
    Create .env File

    Copy the content from .env.example to .env:

    ```bash
    cp .env.example .env
    ```

    Configure Environment Variables

    Edit the .env file to include your specific settings.

3. **Streamlit App Secrets**
    Create .streamlit Directory

    ```bash
    mkdir .streamlit
    ```

    Create secrets.toml File

    Copy the content from secrets.toml.example to .streamlit/secrets.toml and modify the values accordingly:

    ```bash
    cp secrets.toml.example .streamlit/secrets.toml
    ```
    Configure Backend API URL

    Edit .streamlit/secrets.toml and set the BASE_URL to your backend API's URL.

    If running locally on port 8000:

    ```toml
    BASE_URL = 'http://127.0.0.1:8000'
    ```

## Usage
    **Starting the Backend API**
    Run the API backend:

    ```bash
    python3 main.py
    ```
    Starting the Web Interface

    Run the Streamlit frontend:

    ```bash
    streamlit run front_end/front_app.py
    ```
    Accessing the Application
    Open your web browser and navigate to the URL provided by Streamlit, typically http://localhost:8501.

## Examples
    **Query about Commits**

    ```markdown
    Show me details about the latest commit.
    ```

    Find the fixing Commit for an Issue

    ```markdown
    Which commit fixed issue X?
    ```
    
## Troubleshooting
    Redis Connection Errors

    Ensure the Redis server is running on port 6379.
    Verify the REDIS_HOST configuration in your .env file.
    Module Compatibility Issues

    Check if the FastAPI backend is running.
    Verify the BASE_URL in .streamlit/secrets.toml.
