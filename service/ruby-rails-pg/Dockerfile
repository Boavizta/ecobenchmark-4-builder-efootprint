FROM ruby:4.0.9-slim-trixie AS build

RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev libyaml-dev pkg-config && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY Gemfile Gemfile.lock ./
RUN bundle config set frozen true && bundle install

FROM ruby:4.0.9-slim-trixie
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd --system rails && useradd --system --gid rails --create-home rails
WORKDIR /app
ENV RAILS_ENV=production RAILS_LOG_TO_STDOUT=1 PORT=8080
COPY --from=build /usr/local/bundle /usr/local/bundle
COPY --chown=rails:rails . .
RUN mkdir -p log tmp/pids && chown -R rails:rails log tmp && \
    chmod +x docker-entrypoint.sh bin/rails bin/rake bin/setup
USER rails
EXPOSE 8080
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["bundle", "exec", "puma", "-C", "config/puma.rb"]
