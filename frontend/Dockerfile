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

# Run in development mode.
# --port 3000 to match docker-compose and ngrok target.
# --host 0.0.0.0 so the dev server is reachable from outside the container
# (Vue CLI defaults to localhost which is unreachable across Docker network).
CMD ["npm", "run", "serve", "--", "--port", "3000", "--host", "0.0.0.0"]
