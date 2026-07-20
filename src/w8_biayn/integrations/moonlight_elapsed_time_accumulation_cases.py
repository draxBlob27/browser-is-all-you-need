"""Independent C++ contracts for elapsed-time accumulation remediation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ElapsedCase:
    task_id: str
    legacy_id: str
    title: str
    objective: str
    public_api: str
    mechanism: str
    selection_rule: str
    invalid_rule: str
    marker: str
    instructions: str
    header: str
    starter: str
    reference: str
    visible_test: str
    hidden_test: str
    negative_old: str
    negative_new: str
    negative_reason: str


CASES = (
    ElapsedCase(
        task_id="capped-client-day-ledger",
        legacy_id="elapsed-consulting-invoice",
        title="Capped consulting invoice ledger",
        objective="Allocate accepted entries through independent client/day caps and report capped minutes.",
        public_api="ConsultingInvoice::summarize(vector<Entry>, int) -> Report",
        mechanism="per-client/day remaining-cap ledger plus sorted client aggregation",
        selection_rule="input-order allocation consumes the remaining cap for that client/day",
        invalid_rule="bad IDs, client/day fields, negative minutes, and duplicates are rejected without consuming cap",
        marker="remaining_by_client_day",
        instructions=r'''# Instructions

Implement `curriculum::ConsultingInvoice::summarize`. Each `Entry` has a unique
non-empty `id`, non-empty `client`, non-negative `day`, non-negative `minutes`,
and an `approved` flag. A negative `daily_cap` makes the whole report invalid.
Otherwise process entries in input order. Invalid or duplicate entries increase
`rejected`; unapproved entries increase `excluded_minutes`. Approved entries
consume the remaining cap independently for their `(client, day)` pair.
Minutes beyond that remaining cap increase `capped_minutes`.

Return one `ClientTotal` per client that had a valid approved entry, sorted by
client name. Zero-minute entries are valid. Checked `int` arithmetic is
required; overflow makes the report invalid and clears totals.
''',
        header=r'''#pragma once
#include <string>
#include <vector>
namespace curriculum {
class ConsultingInvoice {
 public:
  struct Entry { std::string id; std::string client; int day; int minutes; bool approved; };
  struct ClientTotal { std::string client; int billable_minutes; int capped_minutes; };
  struct Report { bool valid; int rejected; int excluded_minutes; std::vector<ClientTotal> clients; };
  Report summarize(const std::vector<Entry>& entries, int daily_cap) const;
};
}
''',
        starter=r'''#include "task.h"
namespace curriculum {
ConsultingInvoice::Report ConsultingInvoice::summarize(const std::vector<Entry>&, int) const {
  return {false, 0, 0, {}};
}
}
''',
        reference=r'''#include "task.h"
#include <climits>
#include <map>
#include <set>
#include <utility>
namespace curriculum {
ConsultingInvoice::Report ConsultingInvoice::summarize(const std::vector<Entry>& entries, int daily_cap) const {
  Report report{daily_cap >= 0, 0, 0, {}};
  if (!report.valid) return report;
  std::set<std::string> ids;
  std::map<std::pair<std::string, int>, int> remaining_by_client_day;
  std::map<std::string, std::pair<int, int>> totals;
  for (const auto& entry : entries) {
    if (entry.id.empty() || entry.client.empty() || entry.day < 0 || entry.minutes < 0 || !ids.insert(entry.id).second) {
      ++report.rejected;
      continue;
    }
    if (!entry.approved) {
      if (entry.minutes > INT_MAX - report.excluded_minutes) return {false, report.rejected, 0, {}};
      report.excluded_minutes += entry.minutes;
      continue;
    }
    auto key = std::make_pair(entry.client, entry.day);
    auto inserted = remaining_by_client_day.emplace(key, daily_cap);
    int& remaining = inserted.first->second;
    const int accepted = entry.minutes < remaining ? entry.minutes : remaining;
    const int capped = entry.minutes - accepted;
    auto& total = totals[entry.client];
    if (accepted > INT_MAX - total.first || capped > INT_MAX - total.second) return {false, report.rejected, 0, {}};
    total.first += accepted;
    total.second += capped;
    remaining -= accepted;
  }
  for (const auto& item : totals) report.clients.push_back({item.first, item.second.first, item.second.second});
  return report;
}
}
''',
        visible_test=r'''#include "task.h"
#include <vector>
int main() {
  curriculum::ConsultingInvoice ledger;
  std::vector<curriculum::ConsultingInvoice::Entry> entries{{"a","acme",1,6,true},{"b","acme",1,7,true},{"c","beta",1,4,true},{"d","acme",2,3,false}};
  const auto r = ledger.summarize(entries, 10);
  return r.valid && r.rejected == 0 && r.excluded_minutes == 3 && r.clients.size() == 2 && r.clients[0].billable_minutes == 10 && r.clients[0].capped_minutes == 3 ? 0 : 1;
}
''',
        hidden_test=r'''#include "task.h"
#include <vector>
int main() {
  curriculum::ConsultingInvoice ledger;
  std::vector<curriculum::ConsultingInvoice::Entry> entries{{"a","x",0,0,true},{"a","x",0,8,true},{"b","x",1,8,true},{"bad","",1,2,true}};
  const auto r = ledger.summarize(entries, 5);
  const auto bad = ledger.summarize(entries, -1);
  return r.valid && r.rejected == 2 && r.clients.size() == 1 && r.clients[0].billable_minutes == 5 && r.clients[0].capped_minutes == 3 && !bad.valid && bad.clients.empty() ? 0 : 1;
}
''',
        negative_old="const int accepted = entry.minutes < remaining ? entry.minutes : remaining;",
        negative_new="const int accepted = entry.minutes;",
        negative_reason="ignores the per-client/day cap",
    ),
    ElapsedCase(
        task_id="machine-state-coverage-audit",
        legacy_id="elapsed-machine-utilization",
        title="Machine state interval audit",
        objective="Validate a non-overlapping half-open state timeline and aggregate each state.",
        public_api="MachineUtilization::analyze(vector<Interval>) -> Report",
        mechanism="stable interval ordering followed by overlap rejection and state buckets",
        selection_rule="sort by start/end/id, then accept only a globally non-overlapping timeline",
        invalid_rule="unknown states or non-positive intervals are individually rejected; any overlap invalidates all totals",
        marker="ordered_intervals",
        instructions=r'''# Instructions

Implement `MachineUtilization::analyze`. Valid state names are `running`,
`idle`, `setup`, and `fault`. Intervals are half-open `[start, end)` and require
non-empty unique IDs, `0 <= start < end`, and a valid state. Reject malformed
records individually, then stable-sort the remaining records by start, end,
and ID. Touching endpoints are allowed. Any overlap makes the report invalid
and clears all duration totals. Otherwise return the four totals and the first
and final covered positions. An empty accepted timeline is valid with both
positions `-1`. Arithmetic overflow invalidates the report.
''',
        header=r'''#pragma once
#include <array>
#include <string>
#include <vector>
namespace curriculum {
class MachineUtilization {
 public:
  struct Interval { std::string id; int start; int end; std::string state; };
  struct Report { bool valid; int rejected; std::array<int,4> state_minutes; int first_position; int final_position; };
  Report analyze(const std::vector<Interval>& intervals) const;
};
}
''',
        starter=r'''#include "task.h"
namespace curriculum {
MachineUtilization::Report MachineUtilization::analyze(const std::vector<Interval>&) const {
  return {false, 0, {0,0,0,0}, -1, -1};
}
}
''',
        reference=r'''#include "task.h"
#include <algorithm>
#include <climits>
#include <set>
namespace curriculum {
MachineUtilization::Report MachineUtilization::analyze(const std::vector<Interval>& intervals) const {
  Report report{true, 0, {0,0,0,0}, -1, -1};
  std::set<std::string> ids;
  std::vector<Interval> ordered_intervals;
  const std::array<std::string,4> names{{"running","idle","setup","fault"}};
  for (const auto& interval : intervals) {
    const auto found = std::find(names.begin(), names.end(), interval.state);
    if (interval.id.empty() || interval.start < 0 || interval.start >= interval.end || found == names.end() || !ids.insert(interval.id).second) {
      ++report.rejected;
    } else {
      ordered_intervals.push_back(interval);
    }
  }
  std::stable_sort(ordered_intervals.begin(), ordered_intervals.end(), [](const Interval& a, const Interval& b) { return a.start != b.start ? a.start < b.start : (a.end != b.end ? a.end < b.end : a.id < b.id); });
  for (std::size_t i = 1; i < ordered_intervals.size(); ++i) {
    if (ordered_intervals[i].start < ordered_intervals[i-1].end) return {false, report.rejected, {0,0,0,0}, -1, -1};
  }
  if (!ordered_intervals.empty()) { report.first_position = ordered_intervals.front().start; report.final_position = ordered_intervals.back().end; }
  for (const auto& interval : ordered_intervals) {
    const auto found = std::find(names.begin(), names.end(), interval.state);
    const std::size_t index = static_cast<std::size_t>(found - names.begin());
    const int duration = interval.end - interval.start;
    if (duration > INT_MAX - report.state_minutes[index]) return {false, report.rejected, {0,0,0,0}, -1, -1};
    report.state_minutes[index] += duration;
  }
  return report;
}
}
''',
        visible_test=r'''#include "task.h"
#include <vector>
int main() {
  curriculum::MachineUtilization audit;
  std::vector<curriculum::MachineUtilization::Interval> xs{{"b",5,8,"idle"},{"a",0,5,"running"},{"c",9,11,"fault"}};
  const auto r = audit.analyze(xs);
  return r.valid && r.state_minutes[0] == 5 && r.state_minutes[1] == 3 && r.state_minutes[3] == 2 && r.first_position == 0 && r.final_position == 11 ? 0 : 1;
}
''',
        hidden_test=r'''#include "task.h"
#include <vector>
int main() {
  curriculum::MachineUtilization audit;
  const auto overlap = audit.analyze({{"a",0,5,"running"},{"b",4,6,"idle"}});
  const auto malformed = audit.analyze({{"a",0,0,"running"},{"b",2,4,"unknown"}});
  return !overlap.valid && overlap.state_minutes[0] == 0 && malformed.valid && malformed.rejected == 2 && malformed.first_position == -1 ? 0 : 1;
}
''',
        negative_old="if (ordered_intervals[i].start < ordered_intervals[i-1].end)",
        negative_new="if (ordered_intervals[i].start < ordered_intervals[i-1].start)",
        negative_reason="fails to reject overlapping half-open intervals",
    ),
    ElapsedCase(
        task_id="reading-session-correction-ledger",
        legacy_id="elapsed-reading-challenge",
        title="Reading session correction ledger",
        objective="Apply signed corrections atomically to named sessions and aggregate books.",
        public_api="ReadingChallenge::evaluate(vector<Session>, vector<Correction>, int) -> Report",
        mechanism="session-indexed mutable correction ledger with per-book recomputation",
        selection_rule="corrections apply in input order to the referenced session only",
        invalid_rule="unknown correction IDs and corrections that make one session negative are rejected atomically",
        marker="minutes_by_session",
        instructions=r'''# Instructions

Implement `ReadingChallenge::evaluate`. Sessions require unique non-empty IDs,
non-empty book names, and non-negative minutes. Invalid sessions are rejected.
Corrections are applied in input order to a referenced accepted session. An
unknown session or a correction that would make that session negative is
rejected without mutation. Return the corrected total, per-book totals sorted
by book, rejected session/correction counts, and whether `goal_minutes` was
reached. A negative goal invalidates the whole report. Checked arithmetic is
required.
''',
        header=r'''#pragma once
#include <string>
#include <vector>
namespace curriculum {
class ReadingChallenge {
 public:
  struct Session { std::string id; std::string book; int minutes; };
  struct Correction { std::string session_id; int delta; };
  struct BookTotal { std::string book; int minutes; };
  struct Report { bool valid; int rejected_sessions; int rejected_corrections; int total_minutes; bool goal_reached; std::vector<BookTotal> books; };
  Report evaluate(const std::vector<Session>& sessions, const std::vector<Correction>& corrections, int goal_minutes) const;
};
}
''',
        starter=r'''#include "task.h"
namespace curriculum {
ReadingChallenge::Report ReadingChallenge::evaluate(const std::vector<Session>&, const std::vector<Correction>&, int) const {
  return {false, 0, 0, 0, false, {}};
}
}
''',
        reference=r'''#include "task.h"
#include <climits>
#include <map>
#include <set>
namespace curriculum {
ReadingChallenge::Report ReadingChallenge::evaluate(const std::vector<Session>& sessions, const std::vector<Correction>& corrections, int goal_minutes) const {
  Report report{goal_minutes >= 0, 0, 0, 0, false, {}};
  if (!report.valid) return report;
  std::set<std::string> ids;
  std::map<std::string, int> minutes_by_session;
  std::map<std::string, std::string> book_by_session;
  for (const auto& session : sessions) {
    if (session.id.empty() || session.book.empty() || session.minutes < 0 || !ids.insert(session.id).second) { ++report.rejected_sessions; continue; }
    minutes_by_session[session.id] = session.minutes;
    book_by_session[session.id] = session.book;
  }
  for (const auto& correction : corrections) {
    const auto found = minutes_by_session.find(correction.session_id);
    if (found == minutes_by_session.end() || (correction.delta < 0 && found->second < -static_cast<long long>(correction.delta)) || (correction.delta > 0 && correction.delta > INT_MAX - found->second)) {
      ++report.rejected_corrections;
      continue;
    }
    found->second += correction.delta;
  }
  std::map<std::string, int> by_book;
  for (const auto& item : minutes_by_session) {
    int& subtotal = by_book[book_by_session[item.first]];
    if (item.second > INT_MAX - subtotal || item.second > INT_MAX - report.total_minutes) return {false, report.rejected_sessions, report.rejected_corrections, 0, false, {}};
    subtotal += item.second;
    report.total_minutes += item.second;
  }
  for (const auto& item : by_book) report.books.push_back({item.first, item.second});
  report.goal_reached = report.total_minutes >= goal_minutes;
  return report;
}
}
''',
        visible_test=r'''#include "task.h"
#include <vector>
int main() {
  curriculum::ReadingChallenge tracker;
  const auto r = tracker.evaluate({{"s1","A",20},{"s2","B",15}}, {{"s1",5},{"s2",-3}}, 35);
  return r.valid && r.total_minutes == 37 && r.goal_reached && r.books.size() == 2 && r.books[0].minutes == 25 ? 0 : 1;
}
''',
        hidden_test=r'''#include "task.h"
#include <vector>
int main() {
  curriculum::ReadingChallenge tracker;
  const auto r = tracker.evaluate({{"s","A",4},{"s","B",9},{"bad","",2}}, {{"missing",1},{"s",-5},{"s",2}}, 6);
  const auto bad = tracker.evaluate({}, {}, -1);
  return r.valid && r.rejected_sessions == 2 && r.rejected_corrections == 2 && r.total_minutes == 6 && r.goal_reached && !bad.valid ? 0 : 1;
}
''',
        negative_old="++report.rejected_corrections;\n      continue;",
        negative_new="++report.rejected_corrections;\n      found->second = 0;\n      continue;",
        negative_reason="mutates a session after rejecting an underflowing correction",
    ),
    ElapsedCase(
        task_id="freelance-event-reconciler",
        legacy_id="elapsed-freelance-breaks",
        title="Freelance work/break event reconciler",
        objective="Reconcile worker event state machines into paid and break durations.",
        public_api="FreelanceBreaks::reconcile(vector<Event>) -> Report",
        mechanism="independent per-worker Idle/Active/Break transition machines",
        selection_rule="events are consumed in input order and equal-minute transitions retain input order",
        invalid_rule="illegal transitions increment errors and leave that worker state unchanged; open states invalidate the report",
        marker="state_by_worker",
        instructions=r'''# Instructions

Implement `FreelanceBreaks::reconcile`. Events are processed in input order and
have kind `start`, `break-start`, `break-end`, or `stop`. Each worker begins
idle. Legal sequences are idle→start→active, active→break-start→break,
break→break-end→active, and active→stop→idle. Minutes must be non-negative and
must not move backward for that worker. An illegal event increments `errors`
without changing state. Accumulate active spans as paid minutes and break spans
separately per worker. Any worker left active or on break makes `valid=false`.
Return worker totals sorted by worker. Checked arithmetic is required.
''',
        header=r'''#pragma once
#include <string>
#include <vector>
namespace curriculum {
class FreelanceBreaks {
 public:
  struct Event { std::string worker; int minute; std::string kind; };
  struct WorkerTotal { std::string worker; int paid_minutes; int break_minutes; };
  struct Report { bool valid; int errors; std::vector<WorkerTotal> workers; };
  Report reconcile(const std::vector<Event>& events) const;
};
}
''',
        starter=r'''#include "task.h"
namespace curriculum {
FreelanceBreaks::Report FreelanceBreaks::reconcile(const std::vector<Event>&) const {
  return {false, 0, {}};
}
}
''',
        reference=r'''#include "task.h"
#include <climits>
#include <map>
namespace curriculum {
FreelanceBreaks::Report FreelanceBreaks::reconcile(const std::vector<Event>& events) const {
  struct State { int mode = 0; int since = 0; int paid = 0; int paused = 0; int last = -1; };
  std::map<std::string, State> state_by_worker;
  Report report{true, 0, {}};
  for (const auto& event : events) {
    if (event.worker.empty() || event.minute < 0) { ++report.errors; continue; }
    State& state = state_by_worker[event.worker];
    if (event.minute < state.last) { ++report.errors; continue; }
    bool accepted = false;
    if (event.kind == "start" && state.mode == 0) { state.mode = 1; state.since = event.minute; accepted = true; }
    else if (event.kind == "break-start" && state.mode == 1) {
      const int span = event.minute - state.since;
      if (span <= INT_MAX - state.paid) { state.paid += span; state.mode = 2; state.since = event.minute; accepted = true; }
    } else if (event.kind == "break-end" && state.mode == 2) {
      const int span = event.minute - state.since;
      if (span <= INT_MAX - state.paused) { state.paused += span; state.mode = 1; state.since = event.minute; accepted = true; }
    } else if (event.kind == "stop" && state.mode == 1) {
      const int span = event.minute - state.since;
      if (span <= INT_MAX - state.paid) { state.paid += span; state.mode = 0; accepted = true; }
    }
    if (accepted) state.last = event.minute; else ++report.errors;
  }
  for (const auto& item : state_by_worker) {
    if (item.second.mode != 0) report.valid = false;
    report.workers.push_back({item.first, item.second.paid, item.second.paused});
  }
  return report;
}
}
''',
        visible_test=r'''#include "task.h"
#include <vector>
int main() {
  curriculum::FreelanceBreaks reconciler;
  const auto r = reconciler.reconcile({{"ava",0,"start"},{"ava",10,"break-start"},{"ava",15,"break-end"},{"ava",25,"stop"}});
  return r.valid && r.errors == 0 && r.workers.size() == 1 && r.workers[0].paid_minutes == 20 && r.workers[0].break_minutes == 5 ? 0 : 1;
}
''',
        hidden_test=r'''#include "task.h"
#include <vector>
int main() {
  curriculum::FreelanceBreaks reconciler;
  const auto r = reconciler.reconcile({{"b",1,"stop"},{"a",2,"start"},{"a",1,"stop"},{"a",5,"stop"},{"b",3,"start"}});
  return !r.valid && r.errors == 2 && r.workers.size() == 2 && r.workers[0].paid_minutes == 3 ? 0 : 1;
}
''',
        negative_old="state.paused += span; state.mode = 1; state.since = event.minute; accepted = true;",
        negative_new="state.paid += span; state.mode = 1; state.since = event.minute; accepted = true;",
        negative_reason="misclassifies break duration as paid work",
    ),
    ElapsedCase(
        task_id="weighted-training-load",
        legacy_id="elapsed-training-load",
        title="Bounded weighted training load",
        objective="Aggregate valid exercise sets with checked intensity weighting and a post-sum cap.",
        public_api="TrainingLoad::accumulate(vector<Exercise>, int) -> Report",
        mechanism="checked duration-times-intensity products followed by one aggregate cap",
        selection_rule="valid non-rest records contribute in input order; the cap is applied after all products",
        invalid_rule="invalid IDs, duplicate IDs, negative duration, or intensity outside 1..5 are rejected; rest is excluded",
        marker="uncapped_load",
        instructions=r'''# Instructions

Implement `TrainingLoad::accumulate`. Exercises need a unique non-empty ID,
non-negative minutes, and intensity in `[1,5]`. Invalid or duplicate exercises
increase `rejected`. Valid rest records add to `rest_minutes`; other valid
records add to `active_minutes` and contribute `minutes * intensity` to the
uncapped load. Apply the non-negative `load_cap` once after aggregation and
report both uncapped and capped load. A negative cap or any checked-arithmetic
overflow invalidates the report and clears numeric totals. Zero durations are
valid.
''',
        header=r'''#pragma once
#include <string>
#include <vector>
namespace curriculum {
class TrainingLoad {
 public:
  struct Exercise { std::string id; int minutes; int intensity; bool rest; };
  struct Report { bool valid; int rejected; int active_minutes; int rest_minutes; int uncapped_load; int capped_load; };
  Report accumulate(const std::vector<Exercise>& exercises, int load_cap) const;
};
}
''',
        starter=r'''#include "task.h"
namespace curriculum {
TrainingLoad::Report TrainingLoad::accumulate(const std::vector<Exercise>&, int) const {
  return {false, 0, 0, 0, 0, 0};
}
}
''',
        reference=r'''#include "task.h"
#include <climits>
#include <set>
namespace curriculum {
TrainingLoad::Report TrainingLoad::accumulate(const std::vector<Exercise>& exercises, int load_cap) const {
  Report report{load_cap >= 0, 0, 0, 0, 0, 0};
  if (!report.valid) return report;
  std::set<std::string> ids;
  for (const auto& exercise : exercises) {
    if (exercise.id.empty() || exercise.minutes < 0 || exercise.intensity < 1 || exercise.intensity > 5 || !ids.insert(exercise.id).second) { ++report.rejected; continue; }
    int& duration = exercise.rest ? report.rest_minutes : report.active_minutes;
    if (exercise.minutes > INT_MAX - duration) return {false, report.rejected, 0, 0, 0, 0};
    duration += exercise.minutes;
    if (!exercise.rest) {
      if (exercise.minutes != 0 && exercise.intensity > INT_MAX / exercise.minutes) return {false, report.rejected, 0, 0, 0, 0};
      const int product = exercise.minutes * exercise.intensity;
      if (product > INT_MAX - report.uncapped_load) return {false, report.rejected, 0, 0, 0, 0};
      report.uncapped_load += product;
    }
  }
  report.capped_load = report.uncapped_load < load_cap ? report.uncapped_load : load_cap;
  return report;
}
}
''',
        visible_test=r'''#include "task.h"
#include <vector>
int main() {
  curriculum::TrainingLoad load;
  const auto r = load.accumulate({{"a",10,3,false},{"b",5,2,false},{"r",4,1,true}}, 35);
  return r.valid && r.active_minutes == 15 && r.rest_minutes == 4 && r.uncapped_load == 40 && r.capped_load == 35 ? 0 : 1;
}
''',
        hidden_test=r'''#include "task.h"
#include <vector>
int main() {
  curriculum::TrainingLoad load;
  const auto r = load.accumulate({{"a",0,5,false},{"a",3,2,false},{"b",2,0,false},{"r",3,5,true}}, 1);
  const auto bad = load.accumulate({}, -1);
  return r.valid && r.rejected == 2 && r.active_minutes == 0 && r.rest_minutes == 3 && r.capped_load == 0 && !bad.valid ? 0 : 1;
}
''',
        negative_old="report.capped_load = report.uncapped_load < load_cap ? report.uncapped_load : load_cap;",
        negative_new="report.capped_load = report.uncapped_load;",
        negative_reason="fails to apply the aggregate load cap",
    ),
    ElapsedCase(
        task_id="service-outage-interval-union",
        legacy_id="elapsed-network-uptime",
        title="Service outage union ledger",
        objective="Compute per-service uptime by clipping and unioning half-open outages.",
        public_api="NetworkUptime::summarize(vector<Outage>, int) -> Report",
        mechanism="per-service sorted interval union with touching-interval coalescing",
        selection_rule="clip to the observation window, sort, and merge overlap or adjacency per service",
        invalid_rule="bad IDs/services/endpoints and duplicates are rejected; fully outside valid records contribute zero",
        marker="merged_end_by_service",
        instructions=r'''# Instructions

Implement `NetworkUptime::summarize` for the observation window `[0,horizon)`.
A negative horizon invalidates the report. Outages require unique non-empty IDs,
non-empty services, and `start < end`; malformed and duplicate records increase
`rejected`. Clip valid outages to the window and ignore empty clips. For each
service, sort clips and union overlaps and touching intervals. Return covered
outage minutes and `horizon - outage_minutes`, sorted by service. Services with
only outside-window valid records still appear with full uptime. Checked
arithmetic is required.
''',
        header=r'''#pragma once
#include <string>
#include <vector>
namespace curriculum {
class NetworkUptime {
 public:
  struct Outage { std::string id; std::string service; int start; int end; };
  struct ServiceTotal { std::string service; int outage_minutes; int uptime_minutes; };
  struct Report { bool valid; int rejected; std::vector<ServiceTotal> services; };
  Report summarize(const std::vector<Outage>& outages, int horizon) const;
};
}
''',
        starter=r'''#include "task.h"
namespace curriculum {
NetworkUptime::Report NetworkUptime::summarize(const std::vector<Outage>&, int) const {
  return {false, 0, {}};
}
}
''',
        reference=r'''#include "task.h"
#include <algorithm>
#include <map>
#include <set>
#include <utility>
namespace curriculum {
NetworkUptime::Report NetworkUptime::summarize(const std::vector<Outage>& outages, int horizon) const {
  Report report{horizon >= 0, 0, {}};
  if (!report.valid) return report;
  std::set<std::string> ids;
  std::map<std::string, std::vector<std::pair<int,int>>> clips;
  for (const auto& outage : outages) {
    if (outage.id.empty() || outage.service.empty() || outage.start >= outage.end || !ids.insert(outage.id).second) { ++report.rejected; continue; }
    auto& service = clips[outage.service];
    const int start = std::max(0, outage.start);
    const int end = std::min(horizon, outage.end);
    if (start < end) service.push_back({start, end});
  }
  std::map<std::string, int> merged_end_by_service;
  for (auto& item : clips) {
    auto& spans = item.second;
    std::sort(spans.begin(), spans.end());
    int total = 0;
    int start = -1;
    int end = -1;
    for (const auto& span : spans) {
      if (start < 0) { start = span.first; end = span.second; }
      else if (span.first <= end) { end = std::max(end, span.second); }
      else { total += end - start; start = span.first; end = span.second; }
    }
    if (start >= 0) total += end - start;
    merged_end_by_service[item.first] = end;
    report.services.push_back({item.first, total, horizon - total});
  }
  return report;
}
}
''',
        visible_test=r'''#include "task.h"
#include <vector>
int main() {
  curriculum::NetworkUptime ledger;
  const auto r = ledger.summarize({{"a","api",-2,3},{"b","api",3,6},{"c","api",5,8},{"d","db",20,30}}, 10);
  return r.valid && r.services.size() == 2 && r.services[0].outage_minutes == 8 && r.services[0].uptime_minutes == 2 && r.services[1].uptime_minutes == 10 ? 0 : 1;
}
''',
        hidden_test=r'''#include "task.h"
#include <vector>
int main() {
  curriculum::NetworkUptime ledger;
  const auto r = ledger.summarize({{"a","x",1,4},{"a","x",5,8},{"b","",1,2},{"c","x",4,5}}, 8);
  const auto bad = ledger.summarize({}, -1);
  return r.valid && r.rejected == 2 && r.services.size() == 1 && r.services[0].outage_minutes == 4 && r.services[0].uptime_minutes == 4 && !bad.valid ? 0 : 1;
}
''',
        negative_old="else if (span.first <= end)",
        negative_new="else if (span.first < start)",
        negative_reason="does not union overlapping outage intervals and double-counts coverage",
    ),
    ElapsedCase(
        task_id="podcast-attempt-selector",
        legacy_id="elapsed-podcast-production",
        title="Latest-attempt podcast production digest",
        objective="Select the latest valid attempt per immutable job before totaling stages.",
        public_api="PodcastProduction::digest(vector<Attempt>) -> Report",
        mechanism="job-indexed latest-sequence replacement followed by stage totals",
        selection_rule="strictly greatest sequence per job wins; equal sequences are rejected and retain the first",
        invalid_rule="bad IDs, negative sequences/minutes, and unknown stages are rejected; incomplete winning attempts are excluded",
        marker="latest_by_job",
        instructions=r'''# Instructions

Implement `PodcastProduction::digest`. Valid stages are `record`, `edit`, and
`review`. Attempts need non-empty job IDs, non-negative sequence and minutes,
and a valid stage. Keep the greatest sequence per job regardless of input
order. An equal sequence is rejected and leaves the earlier record selected;
an older sequence is counted as superseded. After selection, incomplete latest
attempts add their minutes to `excluded_minutes`; complete attempts contribute
to the three stage totals. Return selected job IDs sorted. Checked arithmetic
is required.
''',
        header=r'''#pragma once
#include <array>
#include <string>
#include <vector>
namespace curriculum {
class PodcastProduction {
 public:
  struct Attempt { std::string job; int sequence; std::string stage; int minutes; bool complete; };
  struct Report { bool valid; int rejected; int superseded; int excluded_minutes; std::array<int,3> stage_minutes; std::vector<std::string> selected_jobs; };
  Report digest(const std::vector<Attempt>& attempts) const;
};
}
''',
        starter=r'''#include "task.h"
namespace curriculum {
PodcastProduction::Report PodcastProduction::digest(const std::vector<Attempt>&) const {
  return {false, 0, 0, 0, {0,0,0}, {}};
}
}
''',
        reference=r'''#include "task.h"
#include <algorithm>
#include <climits>
#include <map>
namespace curriculum {
PodcastProduction::Report PodcastProduction::digest(const std::vector<Attempt>& attempts) const {
  Report report{true, 0, 0, 0, {0,0,0}, {}};
  const std::array<std::string,3> stages{{"record","edit","review"}};
  std::map<std::string, Attempt> latest_by_job;
  for (const auto& attempt : attempts) {
    if (attempt.job.empty() || attempt.sequence < 0 || attempt.minutes < 0 || std::find(stages.begin(), stages.end(), attempt.stage) == stages.end()) { ++report.rejected; continue; }
    const auto found = latest_by_job.find(attempt.job);
    if (found == latest_by_job.end()) latest_by_job.emplace(attempt.job, attempt);
    else if (attempt.sequence > found->second.sequence) { ++report.superseded; found->second = attempt; }
    else if (attempt.sequence == found->second.sequence) ++report.rejected;
    else ++report.superseded;
  }
  for (const auto& item : latest_by_job) {
    report.selected_jobs.push_back(item.first);
    const Attempt& attempt = item.second;
    if (!attempt.complete) {
      if (attempt.minutes > INT_MAX - report.excluded_minutes) return {false, report.rejected, report.superseded, 0, {0,0,0}, {}};
      report.excluded_minutes += attempt.minutes;
      continue;
    }
    const auto found = std::find(stages.begin(), stages.end(), attempt.stage);
    const std::size_t index = static_cast<std::size_t>(found - stages.begin());
    if (attempt.minutes > INT_MAX - report.stage_minutes[index]) return {false, report.rejected, report.superseded, 0, {0,0,0}, {}};
    report.stage_minutes[index] += attempt.minutes;
  }
  return report;
}
}
''',
        visible_test=r'''#include "task.h"
#include <vector>
int main() {
  curriculum::PodcastProduction digest;
  const auto r = digest.digest({{"j",1,"record",10,true},{"j",3,"edit",7,true},{"j",2,"review",9,true},{"k",0,"review",4,false}});
  return r.valid && r.superseded == 2 && r.stage_minutes[1] == 7 && r.excluded_minutes == 4 && r.selected_jobs.size() == 2 ? 0 : 1;
}
''',
        hidden_test=r'''#include "task.h"
#include <vector>
int main() {
  curriculum::PodcastProduction digest;
  const auto r = digest.digest({{"j",2,"edit",5,true},{"j",2,"review",9,true},{"x",-1,"edit",2,true},{"",1,"edit",2,true}});
  return r.valid && r.rejected == 3 && r.superseded == 0 && r.stage_minutes[1] == 5 && r.stage_minutes[2] == 0 ? 0 : 1;
}
''',
        negative_old="else if (attempt.sequence > found->second.sequence)",
        negative_new="else if (attempt.sequence < found->second.sequence)",
        negative_reason="selects the earliest rather than latest job attempt",
    ),
    ElapsedCase(
        task_id="incident-budget-frontier",
        legacy_id="elapsed-incident-response",
        title="Per-incident response budget timeline",
        objective="Validate ordered incident phases and locate the first active-budget breach.",
        public_api="IncidentResponse::assess(vector<Phase>, int) -> Report",
        mechanism="per-incident ordinal frontier and independent active-budget accumulator",
        selection_rule="input order is retained; the first phase that reaches or exceeds budget is recorded per incident",
        invalid_rule="unknown kinds, duplicate/non-increasing ordinals, bad IDs, and negative minutes are rejected without advancing the frontier",
        marker="frontier_by_incident",
        instructions=r'''# Instructions

Implement `IncidentResponse::assess`. Valid phase kinds are `active` and
`waiting`. A non-negative `active_budget` applies independently to each
incident. Records need non-empty incident IDs, non-negative ordinal/minutes,
and strictly increasing ordinals for that incident in input order. Reject bad
records without changing the incident frontier. Waiting remains separate.
For each incident, accumulate active/waiting minutes and record the ordinal of
the first active phase for which cumulative active minutes becomes greater
than or equal to the budget; use `-1` when absent. Return incidents sorted by
ID. Checked arithmetic is required.
''',
        header=r'''#pragma once
#include <string>
#include <vector>
namespace curriculum {
class IncidentResponse {
 public:
  struct Phase { std::string incident; int ordinal; std::string kind; int minutes; };
  struct IncidentTotal { std::string incident; int active_minutes; int waiting_minutes; int first_breach_ordinal; };
  struct Report { bool valid; int rejected; std::vector<IncidentTotal> incidents; };
  Report assess(const std::vector<Phase>& phases, int active_budget) const;
};
}
''',
        starter=r'''#include "task.h"
namespace curriculum {
IncidentResponse::Report IncidentResponse::assess(const std::vector<Phase>&, int) const {
  return {false, 0, {}};
}
}
''',
        reference=r'''#include "task.h"
#include <climits>
#include <map>
namespace curriculum {
IncidentResponse::Report IncidentResponse::assess(const std::vector<Phase>& phases, int active_budget) const {
  struct State { int frontier = -1; int active = 0; int waiting = 0; int breach = -1; };
  Report report{active_budget >= 0, 0, {}};
  if (!report.valid) return report;
  std::map<std::string, State> frontier_by_incident;
  for (const auto& phase : phases) {
    if (phase.incident.empty() || phase.ordinal < 0 || phase.minutes < 0 || (phase.kind != "active" && phase.kind != "waiting")) { ++report.rejected; continue; }
    State& state = frontier_by_incident[phase.incident];
    if (phase.ordinal <= state.frontier) { ++report.rejected; continue; }
    int& total = phase.kind == "active" ? state.active : state.waiting;
    if (phase.minutes > INT_MAX - total) return {false, report.rejected, {}};
    total += phase.minutes;
    state.frontier = phase.ordinal;
    if (phase.kind == "active" && state.breach < 0 && state.active >= active_budget) state.breach = phase.ordinal;
  }
  for (const auto& item : frontier_by_incident) report.incidents.push_back({item.first, item.second.active, item.second.waiting, item.second.breach});
  return report;
}
}
''',
        visible_test=r'''#include "task.h"
#include <vector>
int main() {
  curriculum::IncidentResponse timeline;
  const auto r = timeline.assess({{"i",0,"waiting",4},{"i",1,"active",3},{"j",0,"active",8},{"i",2,"active",4}}, 7);
  return r.valid && r.incidents.size() == 2 && r.incidents[0].active_minutes == 7 && r.incidents[0].waiting_minutes == 4 && r.incidents[0].first_breach_ordinal == 2 && r.incidents[1].first_breach_ordinal == 0 ? 0 : 1;
}
''',
        hidden_test=r'''#include "task.h"
#include <vector>
int main() {
  curriculum::IncidentResponse timeline;
  const auto r = timeline.assess({{"i",2,"active",2},{"i",1,"active",9},{"i",3,"waiting",1},{"",0,"active",1}}, 2);
  const auto bad = timeline.assess({}, -1);
  return r.valid && r.rejected == 2 && r.incidents.size() == 1 && r.incidents[0].active_minutes == 2 && r.incidents[0].waiting_minutes == 1 && r.incidents[0].first_breach_ordinal == 2 && !bad.valid ? 0 : 1;
}
''',
        negative_old="state.active >= active_budget",
        negative_new="state.active > active_budget",
        negative_reason="treats an exact active-budget match as non-breaching",
    ),
)


REJECTED_LEGACY = {
    "elapsed-battery-test-log": "semantic duplicate of latest-attempt selection retained by elapsed-podcast-production",
    "elapsed-lab-equipment-booking": "semantic duplicate of capped allocation retained by elapsed-consulting-invoice",
}
