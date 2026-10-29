#define _GNU_SOURCE
#include <dlfcn.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* SIMULATION ONLY. Redirect two read-only proc inputs; never alter the host procfs.
 * This leaves the pinned upstream Scaphandre executable unchanged. */
static const char *fixture_path(const char *path) {
    const char *enabled = getenv("SCAPHANDRE_SIMULATION");
    if (enabled && strcmp(enabled, "1") == 0) {
        if (strcmp(path, "/proc/modules") == 0) return "/simulation/modules";
        if (strcmp(path, "/proc/cpuinfo") == 0) return "/simulation/cpuinfo";
    }
    return path;
}

static int needs_mode(int flags) {
    return (flags & O_CREAT) || ((flags & O_TMPFILE) == O_TMPFILE);
}

#define OPEN_WRAPPER(symbol) \
int symbol(const char *path, int flags, ...) { \
    int (*original)(const char *, int, ...) = dlsym(RTLD_NEXT, #symbol); \
    mode_t mode = 0; \
    if (needs_mode(flags)) { \
        va_list args; va_start(args, flags); mode = va_arg(args, mode_t); va_end(args); \
    } \
    return original(fixture_path(path), flags, mode); \
}

#define OPENAT_WRAPPER(symbol) \
int symbol(int dirfd, const char *path, int flags, ...) { \
    int (*original)(int, const char *, int, ...) = dlsym(RTLD_NEXT, #symbol); \
    mode_t mode = 0; \
    if (needs_mode(flags)) { \
        va_list args; va_start(args, flags); mode = va_arg(args, mode_t); va_end(args); \
    } \
    return original(dirfd, fixture_path(path), flags, mode); \
}

OPEN_WRAPPER(open)
OPEN_WRAPPER(open64)
OPENAT_WRAPPER(openat)
OPENAT_WRAPPER(openat64)

FILE *fopen(const char *path, const char *mode) {
    FILE *(*original)(const char *, const char *) = dlsym(RTLD_NEXT, "fopen");
    return original(fixture_path(path), mode);
}

FILE *fopen64(const char *path, const char *mode) {
    FILE *(*original)(const char *, const char *) = dlsym(RTLD_NEXT, "fopen64");
    return original(fixture_path(path), mode);
}
