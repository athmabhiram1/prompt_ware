# Step 1: Build production bundle using Bun
FROM oven/bun:1.2 AS build

WORKDIR /app

# Copy dependency lists
COPY package.json bun.lock ./

# Install dependencies via bun as requested
RUN bun install

# Copy project source
COPY . .

# Declare build argument for Vite environment variable injection
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Compile application distribution folder
RUN bun run build

# Step 2: Nginx server to deliver static assets
FROM nginx:1.25-alpine

COPY --from=build /app/dist /usr/share/nginx/html

# Mount custom SPA configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
