FROM node:20-slim

# Install system dependencies including Python
RUN apt-get update && apt-get install -y \
    curl \
    python3 \
    python3-venv \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install bun
RUN npm install -g bun

# Install uv for Python dependency management
ENV UV_INSTALL_DIR="/usr/local/bin"
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Set timezone dynamically if needed, or simply let it be default
ENV TZ=UTC

# Setup working directory
WORKDIR /app

# --- Python Backend Setup ---
# Copy python requirements
COPY pyproject.toml uv.lock ./
# Install python dependencies using uv (creates .venv)
RUN uv sync --frozen

# --- Next.js Frontend Setup ---
# Setup frontend working directory
WORKDIR /app/frontend

# Copy frontend dependencies and install
COPY frontend/package.json frontend/bun.lock ./
RUN bun install --frozen-lockfile

# Copy the rest of the frontend code
# Note: Ensure .dockerignore properly ignores local node_modules, .next, and large folders
COPY frontend ./

# Build the Next.js app in standalone mode (configured in next.config.ts)
RUN bun run build

# --- Finalize Image ---
WORKDIR /app

# Ensure trailing copies of root-level python files (e.g. main.py, scraper module)
COPY main.py ./
COPY scraper/ ./scraper/

# Expose port the Next app runs on
EXPOSE 3000

# Specify environment variable for Next.js standalone mode
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"
ENV NODE_ENV="production"

# Set up the run script starting the standalone server
# Using node instead of bun to run the standalone build as it's optimized for Node.js
WORKDIR /app/frontend

CMD ["node", ".next/standalone/frontend/server.js"]
