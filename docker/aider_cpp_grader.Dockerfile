# Build and publish this image by immutable digest before admitting tasks.
FROM gcc:13.3.0-bookworm@sha256:1d71f0f3450214bef38fe09e6f610fb6cca90cf97b43f4ce845bfc32a4168818

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates=20230311+deb12u1 \
        cmake=3.25.1-1 \
        libgtest-dev=1.12.1-0.2 \
        make=4.3-4.1 \
        ninja-build=1.11.1-2~deb12u1 \
    && rm -rf /var/lib/apt/lists/*

ENV ASAN_OPTIONS=abort_on_error=1:detect_leaks=1:strict_string_checks=1 \
    UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1

WORKDIR /work
