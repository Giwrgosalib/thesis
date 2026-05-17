# Use Node.js LTS (Alpine for size)
FROM node:lts-alpine

WORKDIR /app

# Install dependencies first (better caching)
COPY package.json package-lock.json ./
RUN npm install

# Copy source code
COPY . .

# Expose Vue dev server port (matches docker-compose port mapping)
EXPOSE 3000

# Build the production bundle into ./dist at container startup, THEN run the
# dev server. We must build at runtime (not RUN at image build time) because
# the docker-compose volume mount `./frontend:/app` shadows anything baked
# into the image — so `dist/` has to land on the host-mounted volume, which
# the backend container reads via its `.:/app` mount to serve
# `frontend/dist/index.html` at `/` (see backend/app.py:serve_frontend).
#
# After the build completes, the Vue dev server still comes up on :3000 for
# HMR during development. Either entrypoint works:
#   FRONTEND_URL=http://localhost:5000 → Flask serves the built SPA
#   FRONTEND_URL=http://localhost:3000 → Vue dev server serves with HMR
CMD ["sh", "-c", "npm run build && npm run serve -- --port 3000 --host 0.0.0.0"]
