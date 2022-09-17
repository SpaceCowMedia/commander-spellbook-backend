FROM nginx:1.23-alpine AS base
COPY nginx.conf /etc/nginx/templates/default.conf.template

FROM base AS ssl
COPY ssl.conf /etc/nginx/ssl/ssl.conf
