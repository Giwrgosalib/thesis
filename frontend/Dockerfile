# Use Node.js LTS (Alpine for size)
FROM node:lts-alpine

WORKDIR /app

# Install dependencies first (better caching)
COPY package.json package-lock.json ./
RUN npm install

# Copy source code
COPY . .

# Expose Vue.js dev server port
EXPOSE 8080

# Run in development mode
CMD ["npm", "run", "serve"]
