# C++ components of schedlab. Toolchain: Homebrew GCC 15 (g++-15); override with `make CXX=...`.
# -ffp-contract=off -fno-fast-math: no FMA contraction, so simulated times are the same IEEE operations
# as in the Python core (required for the bit-exact cross-language checks).
CXX      = g++-15
CXXFLAGS = -O2 -std=c++17 -Wall -Wextra -Wno-psabi -ffp-contract=off -fno-fast-math
BUILD    := build

all: $(BUILD)/schedsim $(BUILD)/ompexec

$(BUILD)/schedsim: schedsim.cpp schedsim.hpp | $(BUILD)
	$(CXX) $(CXXFLAGS) -DSCHEDSIM_VERSION='"schedsim 1 ($(shell $(CXX) --version | head -1); $(CXXFLAGS))"' -o $@ schedsim.cpp

# OpenMP executor: same flags plus -fopenmp (GCC libgomp). The simulator part must stay bit-exact.
$(BUILD)/ompexec: ompexec.cpp schedsim.hpp | $(BUILD)
	$(CXX) $(CXXFLAGS) -fopenmp -DOMPEXEC_VERSION='"ompexec 1 ($(shell $(CXX) --version | head -1); $(CXXFLAGS) -fopenmp)"' -o $@ ompexec.cpp

$(BUILD):
	mkdir -p $@

clean:
	rm -rf $(BUILD)

.PHONY: all clean
