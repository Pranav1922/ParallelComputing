// schedsim: command-line front end of the C++ workload simulator (schedsim.hpp).
//
//   schedsim version
//   schedsim dump INSTANCE              re-emit the parsed instance (round-trip check)
//   schedsim bounds INSTANCE            serial_best cp_min work_lb lower_bound
//   schedsim ranks INSTANCE             per task: mean cost and upward rank (HEFT priority)
//   schedsim heuristics INSTANCE        the six heuristics, insertion and append mode
//   schedsim eval INSTANCE JOBS         replay placement orders / decode GA keys
//   schedsim validate INSTANCE CHECKS   independent feasibility check of (proc, start, finish)
//
// All doubles are read and written as C99 hex floats (%a), so values cross the language boundary exactly.
// File formats: cpp/README.md.
#include "schedsim.hpp"

#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>

using namespace schedsim;

#ifndef SCHEDSIM_VERSION
#define SCHEDSIM_VERSION "schedsim 1"
#endif

static std::string hexf(double x) {
    char buf[64];
    std::snprintf(buf, sizeof buf, "%a", x);
    return buf;
}

static double parse_double(const std::string& s) {
    char* end = nullptr;
    double x = std::strtod(s.c_str(), &end);
    if (end == s.c_str() || *end != '\0') throw std::invalid_argument("bad number: " + s);
    return x;
}

static void expect(std::istream& in, const std::string& word) {
    std::string w;
    if (!(in >> w) || w != word) throw std::invalid_argument("expected '" + word + "', got '" + w + "'");
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
    if (!(in >> n >> m >> e) || n < 0 || e < 0) throw std::invalid_argument("bad size line");
    std::vector<std::pair<int, int>> edges(e);
    for (auto& [u, v] : edges)
        if (!(in >> u >> v)) throw std::invalid_argument("bad edge");
    std::vector<std::vector<double>> cost(n, std::vector<double>(m > 0 ? m : 0));
    std::string tok;
    for (auto& row : cost)
        for (double& c : row) {
            if (!(in >> tok)) throw std::invalid_argument("truncated cost matrix");
            c = parse_double(tok);
        }
    expect(in, "end");
    return make_instance(id, m, edges, cost);
}

static void write_schedule(std::ostream& out, const std::string& label, const Schedule& s) {
    out << "result " << label << "\nmakespan " << hexf(s.makespan()) << "\n";
    for (size_t t = 0; t < s.proc.size(); t++)
        out << s.proc[t] << ' ' << hexf(s.start[t]) << ' ' << hexf(s.finish[t]) << "\n";
    out << "end\n";
}

template <class T, class F>
static std::vector<T> read_line_values(std::istream& in, const std::string& head, int n, F conv) {
    std::string line;
    if (!std::getline(in >> std::ws, line)) throw std::invalid_argument("missing '" + head + "' line");
    std::istringstream ls(line);
    expect(ls, head);
    std::vector<T> v;
    std::string tok;
    while (ls >> tok) v.push_back(conv(tok));
    if (n >= 0 && (int)v.size() != n) throw std::invalid_argument("'" + head + "' needs " + std::to_string(n) + " values");
    return v;
}

static int to_int(const std::string& s) { return std::stoi(s); }

static int cmd_eval(const Instance& inst, const std::string& jobs_path) {
    std::ifstream in(jobs_path);
    if (!in) throw std::invalid_argument("cannot open " + jobs_path);
    std::string kind;
    while (in >> kind) {
        // Parse the whole block first (a malformed file is fatal), then evaluate it (an infeasible
        // placement order, e.g. a task that is not ready, is reported per block as "error").
        std::string label, mode;
        in >> label;
        std::vector<int> order, proc;
        std::vector<double> key;
        if (kind == "job") {  // job LABEL append|insert / order ... / proc ... / end
            in >> mode;
            if (mode != "append" && mode != "insert") throw std::invalid_argument("mode must be append or insert");
            order = read_line_values<int>(in, "order", inst.n, to_int);
            proc = read_line_values<int>(in, "proc", inst.n, to_int);
        } else if (kind == "keys") {  // keys LABEL / key ... / proc ... | proc - / end
            key = read_line_values<double>(in, "key", inst.n, parse_double);
            std::string line;
            std::getline(in >> std::ws, line);
            if (line != "proc -") {
                std::istringstream ls(line);
                expect(ls, "proc");
                int p;
                while (ls >> p) proc.push_back(p);
                if ((int)proc.size() != inst.n) throw std::invalid_argument("'proc' needs n values");
            }
        } else {
            throw std::invalid_argument("unknown block '" + kind + "'");
        }
        expect(in, "end");
        try {
            write_schedule(std::cout, label, kind == "job" ? replay(inst, order, proc, mode == "insert")
                                                           : decode_keys(inst, key, proc));
        } catch (const std::invalid_argument& e) {
            std::cout << "error " << label << ' ' << e.what() << "\nend\n";
        }
    }
    return 0;
}

static int cmd_validate(const Instance& inst, const std::string& path) {
    std::ifstream in(path);
    if (!in) throw std::invalid_argument("cannot open " + path);
    std::string kind, label;
    while (in >> kind >> label) {
        if (kind != "check") throw std::invalid_argument("unknown block '" + kind + "'");
        Schedule s;
        auto proc = read_line_values<long>(in, "proc", -1, [](const std::string& x) { return std::stol(x); });
        s.proc = proc;
        s.start = read_line_values<double>(in, "start", -1, parse_double);
        s.finish = read_line_values<double>(in, "finish", -1, parse_double);
        expect(in, "end");
        auto v = validate(inst, s);
        std::cout << "verdict " << label << ' ' << v.size() << "\n";
        for (auto& msg : v) std::cout << "violation " << msg << "\n";
        std::cout << "end\n";
    }
    return 0;
}

int main(int argc, char** argv) {
    std::ios::sync_with_stdio(false);
    try {
        std::string cmd = argc > 1 ? argv[1] : "";
        if (cmd == "version") {
            std::cout << SCHEDSIM_VERSION << "\n";
            return 0;
        }
        if (argc < 3) {
            std::cerr << "usage: schedsim version|dump|bounds|ranks|heuristics INSTANCE | eval|validate INSTANCE FILE\n";
            return 2;
        }
        Instance inst = read_instance(argv[2]);
        if (cmd == "dump") {
            int e = 0;
            for (auto& p : inst.preds) e += (int)p.size();
            std::cout << "schedsim-instance 1\nid " << inst.id << "\nsize " << inst.n << ' ' << inst.m << ' ' << e << "\n";
            for (int u = 0; u < inst.n; u++)
                for (int v : inst.succs[u]) std::cout << u << ' ' << v << "\n";
            for (auto& row : inst.cost) {
                for (int p = 0; p < inst.m; p++) std::cout << (p ? " " : "") << hexf(row[p]);
                std::cout << "\n";
            }
            std::cout << "end\n";
        } else if (cmd == "bounds") {
            Bounds b = bounds(inst);
            std::cout << "bounds " << hexf(b.serial_best) << ' ' << hexf(b.cp_min) << ' ' << hexf(b.work_lb) << ' '
                      << hexf(b.lower_bound) << "\n";
        } else if (cmd == "ranks") {
            auto mean = mean_cost(inst);
            auto rank = upward_rank(inst);
            for (int t = 0; t < inst.n; t++) std::cout << hexf(mean[t]) << ' ' << hexf(rank[t]) << "\n";
        } else if (cmd == "heuristics") {
            for (const auto& name : heuristic_names())
                for (bool insert : {true, false})
                    write_schedule(std::cout, name + (insert ? ":insert" : ":append"), heuristic(inst, name, insert));
        } else if (cmd == "eval" && argc > 3) {
            return cmd_eval(inst, argv[3]);
        } else if (cmd == "validate" && argc > 3) {
            return cmd_validate(inst, argv[3]);
        } else {
            std::cerr << "unknown command " << cmd << "\n";
            return 2;
        }
    } catch (const std::exception& e) {
        std::cerr << "schedsim: " << e.what() << "\n";
        return 1;
    }
    return 0;
}
