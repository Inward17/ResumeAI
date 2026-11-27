# ResumeAI frontend: build with Vite, serve the static files with nginx.
# VITE_* values are baked into the bundle at build time, so pass them as build args
# (docker compose reads them from the --env-file you give it; see docs/DOCKER.md).

FROM node:24-alpine AS build
WORKDIR /app
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile --network-timeout 600000
COPY . .

ARG VITE_API_URL=http://localhost:8000
ARG VITE_BASE_PATH=/
ARG VITE_FIREBASE_API_KEY=
ARG VITE_FIREBASE_AUTH_DOMAIN=
ARG VITE_FIREBASE_PROJECT_ID=
ARG VITE_FIREBASE_STORAGE_BUCKET=
ARG VITE_FIREBASE_MESSAGING_SENDER_ID=
ARG VITE_FIREBASE_APP_ID=
ARG VITE_FIREBASE_MEASUREMENT_ID=
ENV VITE_API_URL=$VITE_API_URL \
    VITE_BASE_PATH=$VITE_BASE_PATH \
    VITE_FIREBASE_API_KEY=$VITE_FIREBASE_API_KEY \
    VITE_FIREBASE_AUTH_DOMAIN=$VITE_FIREBASE_AUTH_DOMAIN \
    VITE_FIREBASE_PROJECT_ID=$VITE_FIREBASE_PROJECT_ID \
    VITE_FIREBASE_STORAGE_BUCKET=$VITE_FIREBASE_STORAGE_BUCKET \
    VITE_FIREBASE_MESSAGING_SENDER_ID=$VITE_FIREBASE_MESSAGING_SENDER_ID \
    VITE_FIREBASE_APP_ID=$VITE_FIREBASE_APP_ID \
    VITE_FIREBASE_MEASUREMENT_ID=$VITE_FIREBASE_MEASUREMENT_ID
RUN yarn build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
