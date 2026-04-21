FROM node:lts-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm install

COPY . .

EXPOSE 8080

# --host 0.0.0.0 makes the dev server reachable from outside the container
CMD ["npm", "run", "serve", "--", "--host", "0.0.0.0"]
