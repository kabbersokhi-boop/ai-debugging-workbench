FROM postgres:17-alpine AS vector-build
RUN apk add --no-cache build-base git
RUN git clone --depth 1 --branch v0.8.7 https://github.com/pgvector/pgvector.git /tmp/pgvector
WORKDIR /tmp/pgvector
RUN make OPTFLAGS="" with_llvm=no && make install with_llvm=no

FROM postgres:17-alpine
COPY --from=vector-build /usr/local/lib/postgresql/vector.so /usr/local/lib/postgresql/vector.so
COPY --from=vector-build /usr/local/share/postgresql/extension/vector* /usr/local/share/postgresql/extension/
