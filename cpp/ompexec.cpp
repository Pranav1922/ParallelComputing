// ompexec: measured execution of task-DAG schedules on real threads with OpenMP.
//
// Every task runs a work-calibrated compute kernel of llround(cost[t][p] * K) iterations, where K is the
// iterations per simulated time unit, fixed by the caller from calibration. The work is fixed; the time is
// measured, so core-speed differences and runtime overheads show up in the results.
//
//   ompexec version
//   ompexec calibrate ITERS THREADS REPS   kernel time per thread (THREADS threads run concurrently),
//                                          plus the cost of an empty parallel region
//   ompexec run INSTANCE JOBS PLAN K [TRACE]
//
// PLAN lines: <mode> <label> <rep> <warmup 0|1> <verify 0|1> <trace 0|1>
//   serial  all tasks in id (topological) order on one thread, on the processor with the smallest total
//           cost (the simulator's serial_best): the speedup baseline T1; label is ignored ("-")
//   static  thread p runs processor p's task list of job LABEL in start-time order, waiting on
//           per-task completion flags (acquire/release) for predecessors on other threads
//   tasks   OpenMP task runtime: a task is created when its last predecessor finishes; it runs on
//           whichever thread picks it up, with work cost[t][thread] (heterogeneity-blind dynamic policy)
// Output: one CSV row per plan line on stdout. All times are seconds (CLOCK_UPTIME_RAW on macOS).
// Simulated times (sim_tu) are only echoed (sim_makespan_tu); they are never mixed with measured seconds.
#include "schedsim.hpp"

#include <omp.h>

#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <time.h>

using namespace schedsim;

// Timer. libstdc++'s steady_clock on macOS ticks in 1 us steps, too coarse for 10 us tasks.
// clock_gettime_nsec_np(CLOCK_UPTIME_RAW) reads the same counter as mach_absolute_time (41.7 ns ticks on
// Apple silicon; the mach headers themselves do not compile with GCC). Elsewhere steady_clock is used.
struct clk {
    using time_point = unsigned long long;  // nanoseconds
    static time_point now() {
#if defined(__APPLE__)
        return clock_gettime_nsec_np(CLOCK_UPTIME_RAW);
#else
        return (time_point)std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count();
#endif
    }
};

static double now_s(clk::time_point t0) { return (double)(clk::now() - t0) * 1e-9; }

#ifndef OMPEXEC_VERSION
#define OMPEXEC_VERSION "ompexec 1"
#endif

// ---- kernel ---------------------------------------------------------------------------------

// Dependent floating-point chain: latency-bound, no memory traffic, cannot be vectorized or folded
// (no -ffast-math). noipa stops GCC from inferring that the function is pure: a pure call may be deleted
// when its result looks unused, or moved across the clock reads that time it (both observed without it).
// The empty asm makes every iteration's value observable, so the loop cannot be shortened either.
#if defined(__clang__)
__attribute__((noinline, optnone))
#else
__attribute__((noinline, noipa))
#endif
static double kernel(long iters, double x) {
    for (long i = 0; i < iters; i++) {
        x = x * 0.9999999 + 1e-7;
        asm volatile("" : "+w"(x));
    }
    return x;
}


static inline void cpu_relax() {
#if defined(__aarch64__)
    asm volatile("yield");
#elif defined(__x86_64__)
    __builtin_ia32_pause();
#endif
}

// ---- input (same formats as schedsim; see cpp/README.md) -------------------------------------

static void expect(std::istream& in, const std::string& w) {
    std::string x;
    if (!(in >> x) || x != w) throw std::invalid_argument("expected '" + w + "', got '" + x + "'");
}

static Instance read_instance(const std::string& path) {
    std::ifstream in(path);
    if (!in) throw std::invalid_argument("cannot open " + path);
    expect(in, "schedsim-instance");
    expect(in, "1");
    std::string id;
    expect(in, "id");
    in >> id;
    int n, m, e;
    expect(in, "size");
    if (!(in >> n >> m >> e) || n < 0 || e < 0 || m < 1) throw std::invalid_argument("bad size line");
    std::vector<std::pair<int, int>> edges(e);
    for (auto& [u, v] : edges)
        if (!(in >> u >> v)) throw std::invalid_argument("bad edge");
    std::vector<std::vector<double>> cost(n, std::vector<double>(m));
    std::string tok;
    for (auto& row : cost)
        for (double& c : row) {
            if (!(in >> tok)) throw std::invalid_argument("truncated cost matrix");
            c = std::strtod(tok.c_str(), nullptr);
        }
    expect(in, "end");
    return make_instance(id, m, edges, cost);
}

struct Job { std::vector<int> order, proc; bool insert; };

static std::map<std::string, Job> read_jobs(const std::string& path, int n) {
    std::ifstream in(path);
    if (!in) throw std::invalid_argument("cannot open " + path);
    std::map<std::string, Job> jobs;
    std::string kind, label, mode, head;
    while (in >> kind) {
        if (kind != "job") throw std::invalid_argument("only 'job' blocks are executable, got '" + kind + "'");
        in >> label >> mode;
        Job j;
        j.insert = mode == "insert";
        j.order.resize(n);
        j.proc.resize(n);
        expect(in, "order");
        for (int& t : j.order) in >> t;
        expect(in, "proc");
        for (int& p : j.proc) in >> p;
        expect(in, "end");
        if (!in) throw std::invalid_argument("malformed job " + label);
        jobs[label] = std::move(j);
    }
    return jobs;
}

// ---- execution ----------------------------------------------------------------------------------

struct alignas(64) TaskRec {      // one cache line per task: no false sharing between threads
    std::atomic<int> done{0};      // static mode: completion flag
    std::atomic<int> npred{0};     // tasks mode: unfinished predecessors
    std::atomic<int> runs{0};      // how many times the task ran (must be 1)
    int thread = -1, seq = -1;
    long iters = 0;
    double free_at = 0, ready_at = 0, start = 0, end = 0, result = 0;
};

struct RunOut {
    double wall = 0, compute = 0, dep_wait = 0, ready_queue = 0, idle = 0, imbalance = 0;
    bool order_ok = true, thread_ok = true, once_ok = true, verify_ok = true;
    int threads_seen = 0;
    double checksum = 0;
};

static long iters_for(double cost, double k) {
    long it = std::llround(cost * k);
    return it < 1 ? 1 : it;
}

static int serial_proc(const Instance& in) {  // argmin of total cost per processor (serial_best)
    int best = 0;
    double bs = 0;
    for (int p = 0; p < in.m; p++) {
        double s = 0;
        for (int t = 0; t < in.n; t++) s += in.cost[t][p];
        if (p == 0 || s < bs) { bs = s; best = p; }
    }
    return best;
}

static void run_task(TaskRec& r, int t, int thread, clk::time_point t0) {
    r.thread = thread;
    r.start = now_s(t0);
    r.result = kernel(r.iters, 1.0 + t);
    r.end = now_s(t0);
    r.runs.fetch_add(1, std::memory_order_relaxed);
}

static void spawn(const Instance& in, std::vector<TaskRec>& rec, int t, clk::time_point t0, double k) {
    rec[t].ready_at = now_s(t0);
#pragma omp task firstprivate(t) shared(in, rec)
    {
        int th = omp_get_thread_num();
        TaskRec& r = rec[t];
        r.iters = iters_for(in.cost[t][th], k);
        run_task(r, t, th, t0);
        r.done.store(1, std::memory_order_release);
        for (int v : in.succs[t])
            if (rec[v].npred.fetch_sub(1, std::memory_order_acq_rel) == 1) spawn(in, rec, v, t0, k);
    }
}

static RunOut execute(const Instance& in, const std::string& mode, const Job* job, double k, bool verify,
                      std::vector<TaskRec>& rec, std::vector<std::vector<int>>& lists) {
    const int n = in.n, m = in.m;
    rec = std::vector<TaskRec>(n);
    RunOut o;
    int nthreads = 1;
    lists.assign(m, {});
    if (mode == "static") {
        Schedule s = replay(in, job->order, job->proc, job->insert);  // simulator: per-processor order
        for (int t = 0; t < n; t++) lists[s.proc[t]].push_back(t);
        for (auto& l : lists)
            std::sort(l.begin(), l.end(), [&](int a, int b) {
                return s.start[a] != s.start[b] ? s.start[a] < s.start[b] : a < b;
            });
        for (int p = 0; p < m; p++)
            for (int t : lists[p]) rec[t].iters = iters_for(in.cost[t][p], k);
        nthreads = m;
    } else if (mode == "tasks") {
        for (int t = 0; t < n; t++) rec[t].npred.store((int)in.preds[t].size());
        nthreads = m;
    } else if (mode == "serial") {
        int p = serial_proc(in);
        for (int t = 0; t < n; t++) rec[t].iters = iters_for(in.cost[t][p], k);
    } else {
        throw std::invalid_argument("unknown mode " + mode);
    }

    std::atomic<int> seen{0};
    auto t0 = clk::now();
    if (mode == "serial") {
        for (int t = 0; t < n; t++) {
            rec[t].free_at = rec[t].ready_at = now_s(t0);
            run_task(rec[t], t, 0, t0);
        }
        seen = 1;
    } else if (mode == "static") {
#pragma omp parallel num_threads(nthreads) shared(in, rec, lists, seen)
        {
            if (omp_get_thread_num() == 0) seen = omp_get_num_threads();
            const int p = omp_get_thread_num();
            int seq = 0;
            for (int t : lists[p]) {
                TaskRec& r = rec[t];
                r.free_at = now_s(t0);
                for (int u : in.preds[t])
                    while (!rec[u].done.load(std::memory_order_acquire)) cpu_relax();
                r.ready_at = now_s(t0);
                r.seq = seq++;
                run_task(r, t, p, t0);
                r.done.store(1, std::memory_order_release);
            }
        }
    } else {
#pragma omp parallel num_threads(nthreads) shared(in, rec, seen)
        {
            if (omp_get_thread_num() == 0) seen = omp_get_num_threads();
#pragma omp single
            for (int t = 0; t < n; t++)
                if (in.preds[t].empty()) spawn(in, rec, t, t0, k);
        }  // implicit barrier: every task has finished
    }
    o.wall = now_s(t0);
    o.threads_seen = seen;

    // ---- checks (V7, V8) and per-run aggregates, outside the timed region ----
    std::vector<double> busy(nthreads, 0.0);
    for (int t = 0; t < n; t++) {
        const TaskRec& r = rec[t];
        o.once_ok &= r.runs.load() == 1;
        o.thread_ok &= r.thread >= 0 && r.thread < nthreads;
        if (r.thread < 0 || r.thread >= nthreads) continue;
        for (int u : in.preds[t]) o.order_ok &= r.start >= rec[u].end;
        double d = r.end - r.start;
        o.compute += d;
        busy[r.thread] += d;
        if (mode == "static") o.dep_wait += r.ready_at - r.free_at;
        if (mode == "tasks") o.ready_queue += r.start - r.ready_at;
        o.checksum += r.result;
    }
    if (mode == "static")
        for (int p = 0; p < m; p++)
            for (int i = 0; i < (int)lists[p].size(); i++) {
                const TaskRec& r = rec[lists[p][i]];
                o.thread_ok &= r.thread == p && r.seq == i;  // ran on its processor, in schedule order
            }
    double mx = 0, sum = 0;
    for (double b : busy) { mx = std::max(mx, b); sum += b; o.idle += o.wall - b; }
    o.imbalance = sum > 0 ? mx / (sum / nthreads) : 0;
    if (verify)  // every task did exactly its prescribed work
        for (int t = 0; t < n; t++) o.verify_ok &= kernel(rec[t].iters, 1.0 + t) == rec[t].result;
    return o;
}

static int cmd_calibrate(long iters, int threads, int reps) {
    std::cout << "kind,rep,thread,threads,iters,seconds\n";
    std::vector<double> sec(threads);
    for (int r = 0; r < reps; r++) {
#pragma omp parallel num_threads(threads)
        {
            int th = omp_get_thread_num();
            auto t0 = clk::now();
            double x = kernel(iters, 1.0 + th);
            sec[th] = now_s(t0);
            asm volatile("" : : "w"(x));
        }
        for (int th = 0; th < threads; th++)
            std::printf("kernel,%d,%d,%d,%ld,%.9e\n", r, th, threads, iters, sec[th]);
        auto t0 = clk::now();
#pragma omp parallel num_threads(threads)
        {  // minimal body: GCC removes a truly empty region, which would time nothing
            int th = omp_get_thread_num();
            asm volatile("" : : "r"(th));
        }
        std::printf("empty_region,%d,-1,%d,0,%.9e\n", r, threads, now_s(t0));
    }
    return 0;
}

static int cmd_run(const std::string& ipath, const std::string& jpath, const std::string& ppath, double k,
                   const std::string& tpath) {
    Instance in = read_instance(ipath);
    auto jobs = read_jobs(jpath, in.n);
    std::ifstream plan(ppath);
    if (!plan) throw std::invalid_argument("cannot open " + ppath);
    std::ofstream trace;
    if (!tpath.empty()) {
        trace.open(tpath);
        trace << "mode,label,rep,task,thread,seq,iters,free_at_s,ready_at_s,start_s,end_s\n";
    }
    std::cout << "instance_id,mode,label,rep,warmup,threads,n,iters_per_tu,sim_makespan_tu,wall_s,compute_s,"
                 "dep_wait_s,ready_queue_s,idle_s,imbalance,threads_seen,order_ok,thread_ok,once_ok,verify_ok,"
                 "verified,checksum\n";
    std::string mode, label;
    int rep, warm, ver, tr;
    std::vector<TaskRec> rec;
    std::vector<std::vector<int>> lists;
    while (plan >> mode >> label >> rep >> warm >> ver >> tr) {
        const Job* job = nullptr;
        double sim = std::nan("");
        if (mode == "static") {
            auto it = jobs.find(label);
            if (it == jobs.end()) throw std::invalid_argument("no job " + label);
            job = &it->second;
            sim = replay(in, job->order, job->proc, job->insert).makespan();
        } else if (mode == "serial") {
            sim = bounds(in).serial_best;
        }
        RunOut o = execute(in, mode, job, k, ver, rec, lists);
        int nth = mode == "serial" ? 1 : in.m;
        std::printf("%s,%s,%s,%d,%d,%d,%d,%.17g,%.17g,%.9e,%.9e,%.9e,%.9e,%.9e,%.6f,%d,%d,%d,%d,%d,%d,%.17g\n",
                    in.id.c_str(), mode.c_str(), label.c_str(), rep, warm, nth, in.n, k, sim, o.wall, o.compute,
                    mode == "static" ? o.dep_wait : std::nan(""), mode == "tasks" ? o.ready_queue : std::nan(""),
                    o.idle, o.imbalance, o.threads_seen, o.order_ok, o.thread_ok, o.once_ok,
                    ver ? (int)o.verify_ok : -1, ver, o.checksum);
        std::fflush(stdout);
        if (tr && trace)
            for (int t = 0; t < in.n; t++) {
                const TaskRec& r = rec[t];
                trace << mode << ',' << label << ',' << rep << ',' << t << ',' << r.thread << ',' << r.seq << ','
                      << r.iters << ',';
                char buf[160];
                std::snprintf(buf, sizeof buf, "%.9e,%.9e,%.9e,%.9e\n", r.free_at, r.ready_at, r.start, r.end);
                trace << buf;
            }
    }
    return 0;
}

int main(int argc, char** argv) {
    try {
        std::string cmd = argc > 1 ? argv[1] : "";
        if (cmd == "version") {
            std::printf("%s; _OPENMP=%d; timer CLOCK_UPTIME_RAW (ns)\n", OMPEXEC_VERSION, _OPENMP);
            return 0;
        }
        if (cmd == "calibrate" && argc == 5) return cmd_calibrate(std::atol(argv[2]), std::atoi(argv[3]), std::atoi(argv[4]));
        if (cmd == "run" && (argc == 6 || argc == 7))
            return cmd_run(argv[2], argv[3], argv[4], std::strtod(argv[5], nullptr), argc == 7 ? argv[6] : "");
        std::cerr << "usage: ompexec version | calibrate ITERS THREADS REPS | run INSTANCE JOBS PLAN K [TRACE]\n";
        return 2;
    } catch (const std::exception& e) {
        std::cerr << "ompexec: " << e.what() << "\n";
        return 1;
    }
}
