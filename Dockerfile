# --- Stage 1: Build Rust API ---------------------------------------------------
FROM rust:1.75-slim AS rust-builder

WORKDIR /build

# Cache deps layer separately
COPY api/Cargo.toml api/Cargo.lock* ./
RUN mkdir src && echo 'fn main() {}' > src/main.rs
RUN cargo build --release 2>/dev/null; rm -f src/main.rs

# Build actual binary
COPY api/src ./src
RUN touch src/main.rs && cargo build --release

# --- Stage 2: Runtime ----------------------------------------------------------
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install dendrite Python package
COPY dendrite/ ./dendrite/
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

# Copy compiled Rust binary
COPY --from=rust-builder /build/target/release/dendrite-api /usr/local/bin/dendrite-api

# Data directory for SQLite persistence
RUN mkdir -p /data

EXPOSE 8080

ENV DENDRITE_DB=/data/dendrite.db
ENV PORT=8080

CMD ["dendrite-api"]
