/* ARM MMU/TLB smoke and bounded working-set timings. No App/account/network access. */
#define _GNU_SOURCE
#include <errno.h>
#include <sched.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static size_t page_size;
static int cpu[2];
static unsigned cpu_count;
static void fail(const char *phase) { perror(phase); exit(1); }
static double seconds(void) {
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts)) fail("clock");
    return ts.tv_sec + ts.tv_nsec / 1e9;
}
static void pin(unsigned n) {
    cpu_set_t mask;
    CPU_ZERO(&mask); CPU_SET(cpu[n % cpu_count], &mask);
    if (sched_setaffinity(0, sizeof(mask), &mask)) fail("affinity");
}
static volatile uint32_t *slot(void *base, size_t page) {
    return (volatile uint32_t *)((char *)base + page * page_size);
}
static void *mapping(size_t pages, int flags, int fd) {
    void *p = mmap(NULL, pages * page_size, PROT_READ | PROT_WRITE, flags, fd, 0);
    if (p == MAP_FAILED) fail("mmap");
    return p;
}
static void expect_fault(void *p, int protection, int write_access) {
    pid_t child = fork();
    if (child < 0) fail("fork");
    if (!child) {
        signal(SIGSEGV, SIG_DFL); signal(SIGBUS, SIG_DFL);
        volatile uint32_t value = *slot(p, 0); (void)value;
        if (mprotect(p, page_size, protection)) _exit(66);
        if (write_access) *slot(p, 0) = 99;
        else { value = *slot(p, 0); (void)value; }
        _exit(77); /* A stale translation incorrectly permitted access. */
    }
    int status;
    if (waitpid(child, &status, 0) != child || !WIFSIGNALED(status) ||
        (WTERMSIG(status) != SIGSEGV && WTERMSIG(status) != SIGBUS)) {
        fprintf(stderr, "permission change did not fault as expected\n"); exit(2);
    }
}
static void test_permissions_and_cow(void) {
    void *p = mapping(1, MAP_PRIVATE | MAP_ANONYMOUS, -1);
    *slot(p, 0) = 7;
    expect_fault(p, PROT_NONE, 0);
    expect_fault(p, PROT_READ, 1);
    pid_t child = fork();
    if (child < 0) fail("fork cow");
    if (!child) { *slot(p, 0) = 23; _exit(*slot(p, 0) == 23 ? 0 : 3); }
    int status;
    if (waitpid(child, &status, 0) != child || !WIFEXITED(status) ||
        WEXITSTATUS(status) || *slot(p, 0) != 7) fail("copy-on-write");
    if (munmap(p, page_size)) fail("unmap permissions");
}
static void test_aliases(void) {
    char name[] = "/data/local/tmp/arm-mmu-XXXXXX";
#if !defined(__ANDROID__)
    char host_name[] = "/tmp/arm-mmu-XXXXXX";
    int fd = mkstemp(host_name);
    if (fd >= 0) unlink(host_name);
#else
    int fd = mkstemp(name);
    if (fd >= 0) unlink(name);
#endif
    (void)name;
    if (fd < 0 || ftruncate(fd, (off_t)(128 * page_size))) fail("shared file");
    void *a = mapping(128, MAP_SHARED, fd), *b = mapping(128, MAP_SHARED, fd);
    close(fd);
    for (unsigned i = 0; i < 128; ++i) *slot(a, i) = i ^ 0xa5a5U;
    pin(1);
    for (unsigned i = 0; i < 128; ++i) {
        if (*slot(b, i) != (i ^ 0xa5a5U)) fail("alias read");
        *slot(b, i) ^= 0xffffU;
    }
    pin(0);
    for (unsigned i = 0; i < 128; ++i)
        if (*slot(a, i) != ((i ^ 0xa5a5U) ^ 0xffffU)) fail("alias write");
    if (munmap(a, 128 * page_size) || munmap(b, 128 * page_size)) fail("unmap aliases");
}
static void test_replacements(void) {
    const unsigned pages = 128;
    void *p = mapping(pages, MAP_PRIVATE | MAP_ANONYMOUS, -1);
    for (unsigned round = 0; round < 24; ++round) {
        pin(round);
        for (unsigned i = 0; i < pages; ++i) *slot(p, i) = round + i + 1;
        pin(round + 1);
        for (unsigned i = 0; i < pages; ++i)
            if (*slot(p, i) != round + i + 1) fail("cross cpu prime");
        /* Replace only this owned mapping; never expose an unreserved address gap. */
        if (mmap(p, pages * page_size, PROT_READ | PROT_WRITE,
                 MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, -1, 0) != p) fail("replace");
        pin(round);
        for (unsigned i = 0; i < pages; ++i)
            if (*slot(p, i) != 0) fail("stale remap translation");
    }
    *slot(p, 0) = 77;
    if (madvise(p, page_size, MADV_DONTNEED) || *slot(p, 0) != 0) fail("discard page");
    if (munmap(p, pages * page_size)) fail("unmap replacements");
}
static int test_code_updates(void) {
#if defined(__arm__)
    void *code = mapping(1, MAP_PRIVATE | MAP_ANONYMOUS, -1);
    for (unsigned i = 1; i <= 48; ++i) {
        pin(i);
        if (mprotect(code, page_size, PROT_READ | PROT_WRITE)) fail("code write permission");
        ((volatile uint32_t *)code)[0] = 0xe3a00000U | i; /* ARM mov r0, #i */
        ((volatile uint32_t *)code)[1] = 0xe12fff1eU;     /* ARM bx lr */
        __builtin___clear_cache((char *)code, (char *)code + 8);
        if (mprotect(code, page_size, PROT_READ | PROT_EXEC)) fail("code execute permission");
        pin(i + 1);
        if (((unsigned (*)(void))code)() != i) fail("stale code translation");
    }
    if (munmap(code, page_size)) fail("unmap code");
    return 1;
#else
    return 0;
#endif
}
static double benchmark(unsigned pages) {
    void *p = mapping(pages, MAP_PRIVATE | MAP_ANONYMOUS, -1);
    for (unsigned i = 0; i < pages; ++i) *slot(p, i) = i + 1;
    uint64_t sum = 0;
    double start = seconds();
    for (unsigned round = 0; round < 256; ++round)
        for (unsigned i = 0; i < pages; ++i)
            sum += *slot(p, (i * 33U) & (pages - 1));
    double elapsed = seconds() - start;
    if (sum != 256ULL * pages * (pages + 1) / 2) fail("working set checksum");
    if (munmap(p, pages * page_size)) fail("unmap benchmark");
    return elapsed;
}
int main(void) {
    alarm(90);
    struct rlimit core = {0, 0};
    if (setrlimit(RLIMIT_CORE, &core)) fail("core limit");
    page_size = (size_t)sysconf(_SC_PAGESIZE);
    if (page_size != 4096) { fprintf(stderr, "unverified page size\n"); return 2; }
    cpu_set_t allowed;
    if (sched_getaffinity(0, sizeof(allowed), &allowed)) fail("allowed CPUs");
    for (int c = 0; c < CPU_SETSIZE && cpu_count < 2; ++c)
        if (CPU_ISSET(c, &allowed)) cpu[cpu_count++] = c;
    if (cpu_count != 2) { fprintf(stderr, "two allowed CPUs required\n"); return 2; }
    double start = seconds();
    pin(0); test_permissions_and_cow(); test_aliases(); test_replacements();
    int code = test_code_updates();
    pin(0);
    double small = benchmark(128), medium = benchmark(512), large = benchmark(2048);
    printf("{\"passed\":true,\"cpu_count\":%u,\"remap_rounds\":24,"
           "\"permission_faults\":2,\"arm_code_updates\":%s,\"code_updates\":%d,"
           "\"pages128_seconds\":%.6f,\"pages512_seconds\":%.6f,"
           "\"pages2048_seconds\":%.6f,\"total_seconds\":%.6f}\n",
           cpu_count, code ? "true" : "false", code ? 48 : 0,
           small, medium, large, seconds() - start);
    return 0;
}
