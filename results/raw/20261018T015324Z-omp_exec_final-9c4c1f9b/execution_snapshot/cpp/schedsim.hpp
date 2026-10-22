// C++ workload simulator for the CS15 scheduling model: an independent port of schedlab/model.py
// (Instance, ScheduleBuilder, validate, bounds, upward_rank) and schedlab/heuristics.py.
//
// Semantics are matched operation by operation so results can be compared bit for bit:
//  - all times are IEEE doubles; build with -ffp-contract=off (no FMA contraction);
//  - mean cost uses numpy's pairwise summation (numpy.mean(axis=1));
//  - column sums are sequential, except m == 1, where numpy sums the contiguous column pairwise;
//  - ties: lowest task id, then lowest processor id, exactly as in the Python code.
// Times are simulated time units (sim_tu), not seconds.
#pragma once

#include <algorithm>
#include <cmath>
#include <set>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace schedsim {

struct Instance {
    std::string id;
    int n = 0, m = 0;
    std::vector<std::vector<int>> preds, succs;  // sorted ascending
    std::vector<std::vector<double>> cost;       // n x m, > 0
};

struct Schedule {
    std::vector<long> proc;
    std::vector<double> start, finish;
    double makespan() const { return finish.empty() ? 0.0 : *std::max_element(finish.begin(), finish.end()); }
};

// Mirrors make_instance(): topological numbering (u < v), no duplicate edges, finite positive costs.
inline Instance make_instance(std::string id, int m, const std::vector<std::pair<int, int>>& edges,
                              std::vector<std::vector<double>> cost) {
    if (m < 1) throw std::invalid_argument("processor count must be >= 1");
    for (auto& row : cost) {
        if ((int)row.size() != m) throw std::invalid_argument("cost row length != m");
        for (double c : row)
            if (!std::isfinite(c) || c <= 0) throw std::invalid_argument("costs must be finite and strictly positive");
    }
    Instance in;
    in.id = std::move(id);
    in.n = (int)cost.size();
    in.m = m;
    in.cost = std::move(cost);
    in.preds.assign(in.n, {});
    in.succs.assign(in.n, {});
    std::set<std::pair<int, int>> seen;
    for (auto [u, v] : edges) {
        if (!(0 <= u && u < v && v < in.n)) throw std::invalid_argument("edge must satisfy 0 <= u < v < n");
        if (!seen.insert({u, v}).second) throw std::invalid_argument("duplicate edge");
        in.preds[v].push_back(u);
        in.succs[u].push_back(v);
    }
    for (auto& p : in.preds) std::sort(p.begin(), p.end());
    for (auto& s : in.succs) std::sort(s.begin(), s.end());
    return in;
}

// numpy's pairwise_sum (numpy/_core/src/umath/loops_utils.h.src), block size 128, 8-way unrolled.
inline double pairwise_sum(const double* a, long n) {
    if (n < 8) {
        double res = -0.0;
        for (long i = 0; i < n; i++) res += a[i];
        return res;
    }
    if (n <= 128) {
        double r[8];
        for (int j = 0; j < 8; j++) r[j] = a[j];
        long i = 8;
        for (; i < n - (n % 8); i += 8)
            for (int j = 0; j < 8; j++) r[j] += a[i + j];
        double res = ((r[0] + r[1]) + (r[2] + r[3])) + ((r[4] + r[5]) + (r[6] + r[7]));
        for (; i < n; i++) res += a[i];
        return res;
    }
    long n2 = n / 2;
    n2 -= n2 % 8;
    return pairwise_sum(a, n2) + pairwise_sum(a + n2, n - n2);
}

inline std::vector<double> mean_cost(const Instance& in) {  // numpy: cost.mean(axis=1)
    std::vector<double> out(in.n);
    for (int t = 0; t < in.n; t++) out[t] = pairwise_sum(in.cost[t].data(), in.m) / in.m;
    return out;
}

inline std::vector<double> upward_rank(const Instance& in) {
    auto mean = mean_cost(in);
    std::vector<double> rank(in.n, 0.0);
    for (int t = in.n - 1; t >= 0; t--) {
        double mx = 0.0;
        bool any = false;
        for (int v : in.succs[t])
            if (!any || rank[v] > mx) { mx = rank[v]; any = true; }
        rank[t] = mean[t] + mx;
    }
    return rank;
}

struct Bounds { double serial_best, cp_min, work_lb, lower_bound; };

inline Bounds bounds(const Instance& in) {
    if (in.n == 0) return {0.0, 0.0, 0.0, 0.0};
    std::vector<double> cmin(in.n), ef(in.n);
    for (int t = 0; t < in.n; t++) cmin[t] = *std::min_element(in.cost[t].begin(), in.cost[t].end());
    double cp = 0.0;
    for (int t = 0; t < in.n; t++) {  // ids are topological
        double mx = 0.0;
        bool any = false;
        for (int u : in.preds[t])
            if (!any || ef[u] > mx) { mx = ef[u]; any = true; }
        ef[t] = cmin[t] + mx;
        if (t == 0 || ef[t] > cp) cp = ef[t];
    }
    double work_lb = pairwise_sum(cmin.data(), in.n) / in.m;
    double serial = 0.0;
    for (int p = 0; p < in.m; p++) {
        double s;
        if (in.m == 1) {  // a single column is contiguous: numpy sums it pairwise
            std::vector<double> col(in.n);
            for (int t = 0; t < in.n; t++) col[t] = in.cost[t][0];
            s = pairwise_sum(col.data(), in.n);
        } else {
            s = 0.0;
            for (int t = 0; t < in.n; t++) s += in.cost[t][p];
        }
        if (p == 0 || s < serial) serial = s;
    }
    return {serial, cp, work_lb, std::max(cp, work_lb)};
}

// The execution simulator; mirrors model.ScheduleBuilder.
class Builder {
public:
    const Instance& in;
    std::vector<double> avail, ready_time;
    std::vector<int> ready;  // sorted by task id

    explicit Builder(const Instance& inst)
        : in(inst), avail(inst.m, 0.0), ready_time(inst.n, 0.0), npred_(inst.n), busy_(inst.m),
          proc_(inst.n, -1), start_(inst.n, 0.0), finish_(inst.n, 0.0) {
        for (int t = 0; t < in.n; t++) {
            npred_[t] = (int)in.preds[t].size();
            if (npred_[t] == 0) ready.push_back(t);
        }
    }

    double est(int t, int p, bool insert) const {
        double s = ready_time[t];
        if (!insert) return std::max(avail[p], s);
        double c = in.cost[t][p];
        for (auto [a, b] : busy_[p]) {
            if (s + c <= a) return s;
            if (b > s) s = b;
        }
        return s;
    }
    double eft(int t, int p, bool insert) const { return est(t, p, insert) + in.cost[t][p]; }

    void place(int t, int p, bool insert) {
        if (!(0 <= p && p < in.m)) throw std::invalid_argument("processor out of range");
        if (!(0 <= t && t < in.n) || proc_[t] != -1 || npred_[t] != 0)
            throw std::invalid_argument("task " + std::to_string(t) + " is not ready");
        double s = est(t, p, insert), f = s + in.cost[t][p];
        proc_[t] = p;
        start_[t] = s;
        finish_[t] = f;
        auto& bp = busy_[p];
        bp.insert(std::upper_bound(bp.begin(), bp.end(), std::make_pair(s, f)), {s, f});  // bisect.insort
        if (f > avail[p]) avail[p] = f;
        ready.erase(std::find(ready.begin(), ready.end(), t));
        for (int v : in.succs[t]) {
            if (f > ready_time[v]) ready_time[v] = f;
            if (--npred_[v] == 0) ready.insert(std::upper_bound(ready.begin(), ready.end(), v), v);
        }
        placed_++;
    }
    bool done() const { return placed_ == in.n; }
    Schedule schedule() const {
        if (!done()) throw std::invalid_argument("schedule is incomplete");
        return {std::vector<long>(proc_.begin(), proc_.end()), start_, finish_};
    }

private:
    std::vector<int> npred_;
    std::vector<std::vector<std::pair<double, double>>> busy_;
    std::vector<int> proc_;
    std::vector<double> start_, finish_;
    int placed_ = 0;
};

// Replay a placement order with a processor per task (indexed by task id).
inline Schedule replay(const Instance& in, const std::vector<int>& order, const std::vector<int>& proc, bool insert) {
    if ((int)order.size() != in.n || (int)proc.size() != in.n) throw std::invalid_argument("order/proc length != n");
    Builder b(in);
    for (int t : order) {
        if (!(0 <= t && t < in.n)) throw std::invalid_argument("task id out of range");
        b.place(t, proc[t], insert);
    }
    return b.schedule();
}

// ga.decode: highest key among ready tasks (ties: lowest id); proc empty = GA-KEYS-EFT (earliest finish, append).
inline Schedule decode_keys(const Instance& in, const std::vector<double>& key, const std::vector<int>& proc) {
    Builder b(in);
    while (!b.ready.empty()) {
        int t = b.ready[0];
        for (int u : b.ready)
            if (key[u] > key[t]) t = u;
        int p;
        if (!proc.empty()) {
            p = proc[t];
        } else {
            p = 0;
            for (int q = 1; q < in.m; q++)
                if (b.eft(t, q, false) < b.eft(t, p, false)) p = q;
        }
        b.place(t, p, false);
    }
    return b.schedule();
}

// ---- heuristics.py ---------------------------------------------------------------------------

inline Schedule list_schedule(const Instance& in, const std::string& task_rule, const std::string& proc_rule,
                              bool insert) {
    if (proc_rule != "EAT" && proc_rule != "EFT") throw std::invalid_argument("unknown processor rule");
    std::vector<double> keys;  // smaller = higher priority; empty means FCFS (live ready time)
    if (task_rule == "SPT") {
        keys = mean_cost(in);
    } else if (task_rule == "LPT") {
        keys = mean_cost(in);
        for (double& k : keys) k = -k;
    } else if (task_rule == "RANKU") {
        keys = upward_rank(in);
        for (double& k : keys) k = -k;
    } else if (task_rule != "FCFS") {
        throw std::invalid_argument("unknown task rule");
    }
    Builder b(in);
    const bool eft = proc_rule == "EFT";
    while (!b.done()) {
        const std::vector<double>& k = keys.empty() ? b.ready_time : keys;
        int t = b.ready[0];
        for (int u : b.ready)
            if (k[u] < k[t]) t = u;  // ready is sorted, so ties keep the lowest id
        int p = 0;
        double best = eft ? b.eft(t, 0, insert) : b.est(t, 0, insert);
        for (int q = 1; q < in.m; q++) {
            double sc = eft ? b.eft(t, q, insert) : b.est(t, q, insert);
            if (sc < best) { best = sc; p = q; }
        }
        b.place(t, p, insert);
    }
    return b.schedule();
}

inline Schedule minmin(const Instance& in, bool insert) {
    Builder b(in);
    while (!b.done()) {
        int bt = -1, bp = -1;
        double best = 0.0;
        for (int t : b.ready)  // (eft, t, p) lexicographic minimum
            for (int p = 0; p < in.m; p++) {
                double e = b.eft(t, p, insert);
                if (bt < 0 || e < best) { best = e; bt = t; bp = p; }
            }
        b.place(bt, bp, insert);
    }
    return b.schedule();
}

inline const std::vector<std::string>& heuristic_names() {
    static const std::vector<std::string> names{"FCFS-EAT", "FCFS-EFT", "SPT-EFT", "LPT-EFT", "HEFT", "MINMIN"};
    return names;
}

inline Schedule heuristic(const Instance& in, const std::string& name, bool insert) {
    if (name == "FCFS-EAT") return list_schedule(in, "FCFS", "EAT", insert);
    if (name == "FCFS-EFT") return list_schedule(in, "FCFS", "EFT", insert);
    if (name == "SPT-EFT") return list_schedule(in, "SPT", "EFT", insert);
    if (name == "LPT-EFT") return list_schedule(in, "LPT", "EFT", insert);
    if (name == "HEFT") return list_schedule(in, "RANKU", "EFT", insert);
    if (name == "MINMIN") return minmin(in, insert);
    throw std::invalid_argument("unknown heuristic " + name);
}

// ---- model.validate --------------------------------------------------------------------------

inline double tol(double x) { return 1e-9 * std::max(1.0, std::fabs(x)); }

inline std::vector<std::string> validate(const Instance& in, const Schedule& s) {
    const int n = in.n, m = in.m;
    std::vector<std::string> out;
    if ((int)s.proc.size() != n || (int)s.start.size() != n || (int)s.finish.size() != n)
        return {"array shapes do not match n"};
    if (n == 0) return out;
    for (int t = 0; t < n; t++)
        if (s.proc[t] < 0 || s.proc[t] >= m)
            out.push_back("task " + std::to_string(t) + ": processor out of range (unscheduled?)");
    for (int t = 0; t < n; t++)
        if (!std::isfinite(s.start[t]) || !std::isfinite(s.finish[t])) {
            out.push_back("non-finite start or finish time");
            break;
        }
    if (!out.empty()) return out;
    for (int t = 0; t < n; t++) {
        if (s.start[t] < -tol(0.0)) out.push_back("task " + std::to_string(t) + ": negative start");
        if (std::fabs(s.finish[t] - s.start[t] - in.cost[t][s.proc[t]]) > tol(s.finish[t]))
            out.push_back("task " + std::to_string(t) + ": finish - start != cost");
        for (int u : in.preds[t])
            if (s.start[t] < s.finish[u] - tol(s.finish[u]))
                out.push_back("task " + std::to_string(t) + ": starts before predecessor " + std::to_string(u));
    }
    for (int p = 0; p < m; p++) {
        std::vector<int> ts;
        for (int t = 0; t < n; t++)
            if (s.proc[t] == p) ts.push_back(t);
        std::sort(ts.begin(), ts.end(), [&](int a, int b) {
            return s.start[a] != s.start[b] ? s.start[a] < s.start[b] : a < b;
        });
        for (size_t i = 1; i < ts.size(); i++)
            if (s.start[ts[i]] < s.finish[ts[i - 1]] - tol(s.finish[ts[i - 1]]))
                out.push_back("processor " + std::to_string(p) + ": tasks overlap");
    }
    return out;
}

}  // namespace schedsim
