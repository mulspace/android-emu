/* Native guest CPU/atomic smoke test. No network, app or account access. */
#define _GNU_SOURCE
#include <errno.h>
#include <pthread.h>
#include <sched.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>

#define ITERATIONS 25000
static atomic_uint total;
static pthread_barrier_t barrier;
struct worker { int cpu; int observed_cpu; int error; uint32_t checksum; };

static uint32_t mix(uint32_t x) {
    for (unsigned n = 0; n < 64; ++n) {
        x ^= x << 13;
        x ^= x >> 17;
        x ^= x << 5;
    }
    return x;
}
static void *work(void *opaque) {
    struct worker *w = opaque;
    cpu_set_t affinity;
    CPU_ZERO(&affinity);
    CPU_SET(w->cpu, &affinity);
    if (sched_setaffinity(0, sizeof(affinity), &affinity)) w->error = errno;
    w->observed_cpu = sched_getcpu();
    pthread_barrier_wait(&barrier);
    uint32_t value = 0x12345678U;
    for (unsigned i = 0; i < ITERATIONS; ++i) {
        value = mix(value + i);
        atomic_fetch_add_explicit(&total, 1, memory_order_relaxed);
    }
    w->checksum = value;
    return NULL;
}
int main(int argc, char **argv) {
    alarm(30);
    int count = argc == 2 ? atoi(argv[1]) : 2;
    if (count < 1 || count > 2) return 2;
    cpu_set_t allowed;
    if (sched_getaffinity(0, sizeof(allowed), &allowed)) return 3;
    struct worker workers[2] = {{0}};
    int found = 0;
    for (int cpu = 0; cpu < CPU_SETSIZE && found < count; ++cpu) {
        if (CPU_ISSET(cpu, &allowed)) workers[found++].cpu = cpu;
    }
    if (found != count) {
        fprintf(stderr, "need %d online allowed CPUs; found %d\n", count, found);
        return 4;
    }
    if (pthread_barrier_init(&barrier, NULL, count)) return 5;
    pthread_t threads[2];
    struct timespec start, end;
    clock_gettime(CLOCK_MONOTONIC, &start);
    for (int i = 0; i < count; ++i)
        if (pthread_create(&threads[i], NULL, work, &workers[i])) return 6;
    for (int i = 0; i < count; ++i)
        if (pthread_join(threads[i], NULL)) return 7;
    clock_gettime(CLOCK_MONOTONIC, &end);
    uint32_t expected = 0x12345678U;
    for (unsigned i = 0; i < ITERATIONS; ++i) expected = mix(expected + i);
    for (int i = 0; i < count; ++i)
        if (workers[i].error || workers[i].observed_cpu != workers[i].cpu ||
            workers[i].checksum != expected) return 8;
    if (atomic_load(&total) != (unsigned)count * ITERATIONS) return 9;
    double elapsed = (end.tv_sec - start.tv_sec) + (end.tv_nsec - start.tv_nsec) / 1e9;
    printf("{\"passed\":true,\"workers\":%d,\"cpu0\":%d,\"cpu1\":%d,"
           "\"atomic_total\":%u,\"checksum\":%u,\"seconds\":%.6f}\n",
           count, workers[0].observed_cpu, count == 2 ? workers[1].observed_cpu : -1,
           atomic_load(&total), expected, elapsed);
    pthread_barrier_destroy(&barrier);
    return 0;
}
