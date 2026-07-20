from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DateMathCase:
    legacy_id: str
    task_id: str
    title: str
    objective: str
    profile: str
    types: str
    return_type: str
    function: str
    params: str
    body: str
    visible: str
    hidden: str
    oracle: str
    negative_old: str
    negative_new: str
    negative_description: str
    mutation_rule: str
    boundary_rule: str
    prompt_terms: tuple[str, ...]


CASES = (
    DateMathCase(
        "safe-date-audit-export",
        "safe-date-audit-export",
        "Checked audit export windows",
        "classify independently shifted closed audit windows",
        "checked two-endpoint shifts followed by stable multi-bucket classification",
        """struct Date { int year; int month; int day; };
struct AuditWindow { std::string id; Date first; Date last; long long signed_shift_days; };
enum class AuditStatus { ok, invalid_input, overflow };
struct AuditDecision { AuditStatus status = AuditStatus::invalid_input; std::vector<std::string> accepted_ids; std::vector<std::string> reversed_ids; std::vector<std::string> outside_ids; std::string blocking_id; int policy_revision = 1; };""",
        "AuditDecision",
        "classify_audit_windows",
        "const std::vector<AuditWindow>& windows, Date archive_first, Date archive_last",
        """AuditDecision result;
result.policy_revision = 1;
if (!valid_date(archive_first) || !valid_date(archive_last) || date_less(archive_last, archive_first)) return result;
std::set<std::string> ids;
result.status = AuditStatus::ok;
for (const auto& window : windows) {
 if (window.id.empty() || !ids.insert(window.id).second || !valid_date(window.first) || !valid_date(window.last)) { AuditDecision bad; bad.blocking_id = window.id; return bad; }
 Date shifted_first{}; Date shifted_last{};
 if (!add_days(window.first, window.signed_shift_days, shifted_first) || !add_days(window.last, window.signed_shift_days, shifted_last)) { AuditDecision bad; bad.status = AuditStatus::overflow; bad.blocking_id = window.id; return bad; }
 if (date_less(shifted_last, shifted_first)) { result.reversed_ids.push_back(window.id); if (result.blocking_id.empty()) result.blocking_id = window.id; }
 else if (date_less(shifted_first, archive_first) || date_less(archive_last, shifted_last)) { result.outside_ids.push_back(window.id); if (result.blocking_id.empty()) result.blocking_id = window.id; }
 else result.accepted_ids.push_back(window.id);
}
return result;""",
        """auto r = classify_audit_windows({{"inside", {2024,2,28}, {2024,2,28}, 1}, {"outside-one", {2024,3,1}, {2024,3,2}, 1}, {"outside-two", {2024,1,1}, {2024,1,2}, -1}}, {2024,2,1}, {2024,3,2});
return r.status == AuditStatus::ok && r.accepted_ids == std::vector<std::string>{"inside"} && r.outside_ids == std::vector<std::string>({"outside-one", "outside-two"}) && r.blocking_id == "outside-one" && r.policy_revision == 1 ? 0 : 1;""",
        """auto reversed = classify_audit_windows({{"r", {2024,3,2}, {2024,3,1}, 0}}, {2024,1,1}, {2024,12,31});
auto overflow = classify_audit_windows({{"huge", {2024,1,1}, {2024,1,1}, std::numeric_limits<long long>::max()}}, {2024,1,1}, {2024,12,31});
auto duplicate = classify_audit_windows({{"x", {2024,1,1}, {2024,1,1}, 0}, {"x", {2024,1,2}, {2024,1,2}, 0}}, {2024,1,1}, {2024,12,31});
return reversed.reversed_ids == std::vector<std::string>{"r"} && overflow.status == AuditStatus::overflow && overflow.accepted_ids.empty() && duplicate.status == AuditStatus::invalid_input ? 0 : 1;""",
        """std::vector<AuditWindow> windows{{"a", {2000,2,28}, {2000,2,29}, 1}, {"b", {2000,3,1}, {2000,3,1}, -1}};
auto r = classify_audit_windows(windows, {2000,2,1}, {2000,3,31});
bool complete = r.accepted_ids == std::vector<std::string>({"a", "b"}) && r.reversed_ids.empty() && r.outside_ids.empty();
auto empty = classify_audit_windows({}, {1,1,1}, {9999,12,31});
return complete && empty.status == AuditStatus::ok ? 0 : 1;""",
        "if (!add_days(window.first, window.signed_shift_days, shifted_first) || !add_days(window.last, window.signed_shift_days, shifted_last))",
        "if (!add_days(window.first, static_cast<int>(window.signed_shift_days), shifted_first) || !add_days(window.last, static_cast<int>(window.signed_shift_days), shifted_last))",
        "narrow the signed shift before checked arithmetic so an extreme offset is accepted",
        "preserve source order in each bucket and choose the first rejected input ID",
        "closed archive endpoints are inclusive; invalid or unrepresentable input discards all staged buckets",
        ("closed windows", "stable buckets", "first rejected", "checked signed shift"),
    ),
    DateMathCase(
        "safe-date-grant-reporting",
        "checked-grant-dependency-shift",
        "Checked grant dependency shift",
        "propagate approved extensions through a milestone dependency DAG",
        "Kahn topological traversal with maximum inherited-delay dynamic programming",
        """struct Date { int year; int month; int day; };
struct GrantMilestone { std::string id; Date due; std::vector<std::string> predecessors; };
struct GrantExtension { std::string milestone_id; int days; };
enum class GrantStatus { ok, invalid_input, cycle, range_exceeded };
struct ShiftedMilestone { std::string id; Date due; long long total_delay_days; };
struct GrantShiftResult { GrantStatus status = GrantStatus::invalid_input; std::vector<ShiftedMilestone> shifted; std::string blocking_id; };""",
        "GrantShiftResult",
        "shift_grant_dependencies",
        "const std::vector<GrantMilestone>& milestones, const std::vector<GrantExtension>& extensions, Date minimum, Date maximum",
        """GrantShiftResult result;
if (!valid_date(minimum) || !valid_date(maximum) || date_less(maximum, minimum)) return result;
std::map<std::string, std::size_t> index;
for (std::size_t i = 0; i < milestones.size(); ++i) if (milestones[i].id.empty() || !valid_date(milestones[i].due) || !index.emplace(milestones[i].id, i).second) { result.blocking_id = milestones[i].id; return result; }
std::vector<std::vector<std::size_t>> next(milestones.size()); std::vector<int> indegree(milestones.size(), 0); std::vector<long long> direct(milestones.size(), 0);
for (std::size_t i = 0; i < milestones.size(); ++i) for (const auto& predecessor : milestones[i].predecessors) { auto it=index.find(predecessor); if (it==index.end() || it->second==i) { result.blocking_id=milestones[i].id; return result; } next[it->second].push_back(i); ++indegree[i]; }
for (const auto& extension : extensions) { auto it=index.find(extension.milestone_id); if (it==index.end() || extension.days<0 || direct[it->second] > std::numeric_limits<long long>::max()-extension.days) { result.blocking_id=extension.milestone_id; return result; } direct[it->second]+=extension.days; }
std::set<std::string> ready; for (std::size_t i=0;i<milestones.size();++i) if(indegree[i]==0) ready.insert(milestones[i].id);
std::vector<long long> propagated(milestones.size(),0); std::vector<ShiftedMilestone> staged;
while(!ready.empty()) { std::string id=*ready.begin(); ready.erase(ready.begin()); std::size_t i=index.at(id); long long total=direct[i];
 for (const auto& predecessor : milestones[i].predecessors) { long long inherited=propagated[index.at(predecessor)]; total = std::max(total, inherited + direct[i]); }
 Date shifted{}; if(!add_days(milestones[i].due,total,shifted) || date_less(shifted,minimum) || date_less(maximum,shifted)) { result.status=GrantStatus::range_exceeded; result.blocking_id=id; return result; }
 propagated[i]=total; staged.push_back({id,shifted,total}); for(std::size_t child:next[i]) if(--indegree[child]==0) ready.insert(milestones[child].id);
}
if(staged.size()!=milestones.size()) { result.status=GrantStatus::cycle; return result; }
result.status=GrantStatus::ok; result.shifted=std::move(staged); return result;""",
        """std::vector<GrantMilestone> m{{"draft",{2024,1,1},{}},{"review",{2024,1,10},{"draft"}},{"file",{2024,1,20},{"review"}}};
auto r=shift_grant_dependencies(m,{{"draft",2},{"review",3}},{2024,1,1},{2024,12,31});
return r.status==GrantStatus::ok && r.shifted.size()==3 && r.shifted[0].total_delay_days==2 && r.shifted[1].total_delay_days==5 && r.shifted[2].due.day==25 ? 0 : 1;""",
        """std::vector<GrantMilestone> cycle{{"a",{2024,1,1},{"b"}},{"b",{2024,1,1},{"a"}}};
auto c=shift_grant_dependencies(cycle,{}, {2024,1,1},{2024,12,31});
auto o=shift_grant_dependencies({{"a",{2024,12,31},{}}},{{"a",1}}, {2024,1,1},{2024,12,31});
return c.status==GrantStatus::cycle && o.status==GrantStatus::range_exceeded && o.shifted.empty() ? 0 : 1;""",
        """std::vector<GrantMilestone> m{{"a",{2020,2,28},{}},{"b",{2020,3,1},{}},{"c",{2020,3,5},{"a","b"}}};
auto r=shift_grant_dependencies(m,{{"a",1},{"b",4}}, {2020,1,1},{2021,1,1});
bool ordered=r.shifted.size()==3 && r.shifted[0].id=="a" && r.shifted[1].id=="b" && r.shifted[2].id=="c";
return r.status==GrantStatus::ok && ordered && r.shifted[2].total_delay_days==4 && r.shifted[2].due.day==9 ? 0 : 1;""",
        "total = std::max(total, inherited + direct[i]);",
        "total = direct[i] + (inherited - inherited);",
        "drop inherited dependency delay and apply only direct extensions",
        "select lexicographically from ready milestones and propagate the maximum predecessor delay",
        "unknown dependencies, cycles, negative extensions, or one range failure invalidate the atomic result",
        ("dependency DAG", "topological", "maximum inherited delay", "atomic shift"),
    ),
    DateMathCase(
        "safe-date-lease-amendment",
        "transactional-lease-amendments",
        "Transactional lease amendments",
        "apply sequence-numbered calendar-month and day amendments transactionally",
        "ordered unit-specific fold with end-of-month clamp and rollback",
        """struct Date { int year; int month; int day; };
enum class AmendmentUnit { calendar_months, days };
struct LeaseAmendment { int sequence; AmendmentUnit unit; long long amount; };
enum class LeaseStatus { ok, invalid_input, range_exceeded };
struct LeaseAmendmentResult { LeaseStatus status = LeaseStatus::invalid_input; Date final_date{}; std::vector<int> applied_sequences; int blocking_sequence = -1; };""",
        "LeaseAmendmentResult",
        "apply_lease_amendments",
        "Date effective, const std::vector<LeaseAmendment>& amendments, Date minimum, Date maximum",
        """LeaseAmendmentResult result; result.final_date=effective;
if(!valid_date(effective)||!valid_date(minimum)||!valid_date(maximum)||date_less(effective,minimum)||date_less(maximum,effective)) return result;
Date current=effective; int previous=std::numeric_limits<int>::min(); std::vector<int> applied;
for(const auto& amendment:amendments) { if(amendment.sequence<=previous || amendment.amount < -120000 || amendment.amount > 120000) { result.blocking_sequence=amendment.sequence; return result; } previous=amendment.sequence; Date next{}; bool ok=amendment.unit==AmendmentUnit::calendar_months?add_months(current,amendment.amount,next):add_days(current,amendment.amount,next); if(!ok||date_less(next,minimum)||date_less(maximum,next)) { result.status=LeaseStatus::range_exceeded; result.blocking_sequence=amendment.sequence; result.final_date = effective; return result; } current=next; applied.push_back(amendment.sequence); }
result.status=LeaseStatus::ok; result.final_date=current; result.applied_sequences=std::move(applied); return result;""",
        """auto r=apply_lease_amendments({2024,1,31},{{10,AmendmentUnit::calendar_months,1},{20,AmendmentUnit::days,1}}, {2024,1,1},{2024,12,31});
return r.status==LeaseStatus::ok && r.final_date.year==2024 && r.final_date.month==3 && r.final_date.day==1 && r.applied_sequences==std::vector<int>({10,20}) ? 0 : 1;""",
        """auto rollback=apply_lease_amendments({2024,1,31},{{1,AmendmentUnit::calendar_months,1},{2,AmendmentUnit::days,400}}, {2024,1,1},{2024,12,31});
auto order=apply_lease_amendments({2024,1,1},{{2,AmendmentUnit::days,1},{1,AmendmentUnit::days,1}}, {2024,1,1},{2024,12,31});
return rollback.status==LeaseStatus::range_exceeded && rollback.final_date.month==1 && rollback.final_date.day==31 && rollback.applied_sequences.empty() && order.status==LeaseStatus::invalid_input ? 0 : 1;""",
        """auto empty=apply_lease_amendments({2000,2,29},{}, {1999,1,1},{2001,1,1});
auto subtract=apply_lease_amendments({2000,3,31},{{7,AmendmentUnit::calendar_months,-1},{8,AmendmentUnit::days,-1}}, {1999,1,1},{2001,1,1});
return empty.status==LeaseStatus::ok && empty.final_date.day==29 && subtract.status==LeaseStatus::ok && subtract.final_date.month==2 && subtract.final_date.day==28 ? 0 : 1;""",
        "result.final_date = effective; return result;",
        "result.final_date = current; return result;",
        "return the last valid partial amendment state instead of rolling back",
        "consume amendments in caller order and never sort sequence numbers",
        "every intermediate date must remain inside the inclusive range; any failure restores the original date",
        ("transaction", "sequence order", "month clamp", "rollback"),
    ),
    DateMathCase(
        "safe-date-library-preservation",
        "preservation-policy-join",
        "Preservation policy join",
        "join collection items to preservation policies with ordered per-item diagnostics",
        "validated two-table lookup and partial per-item scheduling",
        """struct Date { int year; int month; int day; };
struct CollectionItem { std::string id; std::string policy_code; Date acquired; };
struct PreservationPolicy { std::string code; int inspection_months; int treatment_days; };
enum class PreservationIssue { duplicate_item, unknown_policy, invalid_date, range_exceeded };
struct PreservationRow { std::string id; Date inspection; Date treatment; };
struct PreservationDiagnostic { std::string id; PreservationIssue issue; };
struct PreservationReport { bool valid_policies = false; std::vector<PreservationRow> scheduled; std::vector<PreservationDiagnostic> diagnostics; };""",
        "PreservationReport",
        "build_preservation_schedule",
        "const std::vector<CollectionItem>& items, const std::vector<PreservationPolicy>& policies, Date minimum, Date maximum",
        """PreservationReport report;
if(!valid_date(minimum)||!valid_date(maximum)||date_less(maximum,minimum)) return report;
std::map<std::string,PreservationPolicy> policies_by_code;
for(const auto& policy:policies) if(policy.code.empty()||policy.inspection_months<0||policy.treatment_days<0||!policies_by_code.emplace(policy.code,policy).second) return report;
report.valid_policies=true; std::set<std::string> item_ids;
for(const auto& item:items) { if(item.id.empty()||!item_ids.insert(item.id).second) { report.diagnostics.push_back({item.id,PreservationIssue::duplicate_item}); continue; }
 auto policy_it=policies_by_code.find(item.policy_code); if(policy_it==policies_by_code.end()) { report.diagnostics.push_back({item.id,PreservationIssue::unknown_policy}); continue; }
 if(!valid_date(item.acquired)) { report.diagnostics.push_back({item.id,PreservationIssue::invalid_date}); continue; }
 Date inspection{}; Date treatment{}; if(!add_months(item.acquired,policy_it->second.inspection_months,inspection)||!add_days(inspection,policy_it->second.treatment_days,treatment)||date_less(inspection,minimum)||date_less(maximum,treatment)) { report.diagnostics.push_back({item.id,PreservationIssue::range_exceeded}); continue; }
 report.scheduled.push_back({item.id,inspection,treatment}); }
return report;""",
        """auto r=build_preservation_schedule({{"folio","paper",{2024,1,31}},{"film","cold",{2024,2,1}}},{{"paper",1,1},{"cold",0,7}}, {2024,1,1},{2024,12,31});
return r.valid_policies && r.scheduled.size()==2 && r.scheduled[0].inspection.month==2 && r.scheduled[0].treatment.day==1 && r.scheduled[1].treatment.day==8 ? 0 : 1;""",
        """auto r=build_preservation_schedule({{"a","missing",{2024,1,1}},{"a","p",{2024,1,1}},{"b","p",{2024,12,31}}},{{"p",1,0}}, {2024,1,1},{2024,12,31});
bool issues=r.diagnostics.size()==3 && r.diagnostics[0].issue==PreservationIssue::unknown_policy && r.diagnostics[1].issue==PreservationIssue::duplicate_item && r.diagnostics[2].issue==PreservationIssue::range_exceeded;
return r.valid_policies && r.scheduled.empty() && issues ? 0 : 1;""",
        """auto bad=build_preservation_schedule({},{{"p",1,1},{"p",2,2}}, {2024,1,1},{2024,12,31});
auto empty=build_preservation_schedule({},{{"p",1,1}}, {2024,1,1},{2024,12,31});
return !bad.valid_policies && bad.scheduled.empty() && empty.valid_policies && empty.diagnostics.empty() ? 0 : 1;""",
        "report.diagnostics.push_back({item.id,PreservationIssue::unknown_policy}); continue;",
        "policy_it=policies_by_code.begin();",
        "silently substitute the first policy when an item has an unknown policy code",
        "preserve item order while admitting valid rows and retaining item-local diagnostics",
        "duplicate policies invalidate the whole report; item failures do not suppress unrelated valid items",
        ("policy join", "partial admission", "ordered diagnostics", "month then treatment"),
    ),
    DateMathCase(
        "safe-date-manufacturing-cycle",
        "bounded-service-recurrence",
        "Bounded service recurrence",
        "merge bounded equipment service recurrences into one chronological forecast",
        "per-machine cursor state and k-way earliest-event selection",
        """struct Date { int year; int month; int day; };
struct ServiceMachine { std::string id; Date start; int cadence_months; int usage_buffer_days; int occurrence_limit; };
struct ServiceEvent { std::string machine_id; int occurrence; Date due; };
enum class ServiceStatus { ok, invalid_input, range_exceeded };
struct ServiceForecast { ServiceStatus status = ServiceStatus::invalid_input; std::vector<ServiceEvent> events; std::string blocking_machine; };""",
        "ServiceForecast",
        "forecast_service_cycles",
        "const std::vector<ServiceMachine>& machines, Date through",
        """ServiceForecast result;
if(!valid_date(through)) return result;
std::set<std::string> ids;
struct Cursor { Date next; int emitted; bool active; }; std::vector<Cursor> cursors;
for(const auto& machine:machines) { if(machine.id.empty()||!ids.insert(machine.id).second||!valid_date(machine.start)||machine.cadence_months<=0||machine.occurrence_limit<0) { result.blocking_machine=machine.id; return result; } cursors.push_back({machine.start,0,machine.occurrence_limit>0&&!date_less(through,machine.start)}); }
result.status=ServiceStatus::ok;
while(true) { std::size_t best=machines.size(); for(std::size_t i=0;i<machines.size();++i) if(cursors[i].active && (best==machines.size()||date_less(cursors[i].next,cursors[best].next)||(!date_less(cursors[best].next,cursors[i].next)&&!date_less(cursors[i].next,cursors[best].next)&&machines[i].id<machines[best].id))) best=i; if(best==machines.size()) break;
 result.events.push_back({machines[best].id,cursors[best].emitted+1,cursors[best].next}); ++cursors[best].emitted; if(cursors[best].emitted>=machines[best].occurrence_limit) { cursors[best].active=false; continue; }
 Date month_due{}; Date buffered{}; if(!add_months(cursors[best].next,machines[best].cadence_months,month_due)||!add_days(month_due,machines[best].usage_buffer_days,buffered)) { result.status=ServiceStatus::range_exceeded; result.blocking_machine=machines[best].id; result.events.clear(); return result; } cursors[best].next=buffered; if(date_less(through,buffered)) cursors[best].active=false;
}
return result;""",
        """auto r=forecast_service_cycles({{"b",{2024,1,15},1,0,2},{"a",{2024,1,10},2,0,2}}, {2024,4,30});
return r.status==ServiceStatus::ok && r.events.size()==4 && r.events[0].machine_id=="a" && r.events[1].machine_id=="b" && r.events[2].machine_id=="b" && r.events[3].machine_id=="a" ? 0 : 1;""",
        """auto ties=forecast_service_cycles({{"z",{2024,1,1},1,0,1},{"a",{2024,1,1},1,0,1}}, {2024,1,1});
auto bad=forecast_service_cycles({{"x",{9999,12,31},1,0,2}}, {9999,12,31});
return ties.events.size()==2 && ties.events[0].machine_id=="a" && bad.status==ServiceStatus::range_exceeded && bad.events.empty() ? 0 : 1;""",
        """auto empty=forecast_service_cycles({}, {2024,1,1});
auto clamped=forecast_service_cycles({{"m",{2024,1,31},1,1,2}}, {2024,3,31});
return empty.status==ServiceStatus::ok && clamped.events.size()==2 && clamped.events[1].due.month==3 && clamped.events[1].due.day==1 ? 0 : 1;""",
        "if(cursors[i].active && (best==machines.size()||date_less(cursors[i].next,cursors[best].next)||",
        "if(cursors[i].active && (best==machines.size()||false||",
        "select the first active machine instead of the globally earliest recurrence",
        "select the earliest due date globally and break equal dates by machine ID",
        "bad cadence, duplicate IDs, invalid dates, or one recurrence overflow invalidate all staged events",
        ("k-way merge", "machine cursor", "chronological", "stable tie"),
    ),
    DateMathCase(
        "safe-date-medical-protocol",
        "clinical-milestone-expansion",
        "Clinical milestone expansion",
        "expand labeled cumulative or treatment-relative gap protocols",
        "bounded indexed prefix/direct day-gap expansion",
        """struct Date { int year; int month; int day; };
struct ClinicalProtocol { std::vector<std::string> labels; std::vector<int> gap_days; bool cumulative; };
struct ClinicalMilestone { std::size_t index; std::string label; Date due; };
enum class ClinicalStatus { ok, invalid_protocol, horizon_exceeded };
struct ClinicalSchedule { ClinicalStatus status = ClinicalStatus::invalid_protocol; std::vector<ClinicalMilestone> milestones; std::size_t blocking_index = 0; };""",
        "ClinicalSchedule",
        "expand_clinical_protocol",
        "Date treatment, const ClinicalProtocol& protocol, Date horizon",
        """ClinicalSchedule result;
if(!valid_date(treatment)||!valid_date(horizon)||date_less(horizon,treatment)||protocol.labels.size()!=protocol.gap_days.size()||protocol.labels.size()>64) return result;
std::set<std::string> labels; for(std::size_t i=0;i<protocol.labels.size();++i) if(protocol.labels[i].empty()||protocol.gap_days[i]<=0||!labels.insert(protocol.labels[i]).second) { result.blocking_index=i; return result; }
Date current=treatment; std::vector<ClinicalMilestone> staged;
for(std::size_t i=0;i<protocol.labels.size();++i) { Date origin=protocol.cumulative?current:treatment; Date due{}; if(!add_days(origin,protocol.gap_days[i],due)||date_less(horizon,due)) { result.status=ClinicalStatus::horizon_exceeded; result.blocking_index=i; return result; } staged.push_back({i,protocol.labels[i],due}); current=due; }
result.status=ClinicalStatus::ok; result.milestones=std::move(staged); return result;""",
        """ClinicalProtocol p{{"check","scan","review"},{1,2,3},true}; auto r=expand_clinical_protocol({2024,2,28},p,{2024,3,10});
return r.status==ClinicalStatus::ok && r.milestones.size()==3 && r.milestones[0].due.day==29 && r.milestones[1].due.month==3 && r.milestones[1].due.day==2 && r.milestones[2].due.day==5 ? 0 : 1;""",
        """ClinicalProtocol direct{{"a","b"},{2,3},false}; auto d=expand_clinical_protocol({2024,1,1},direct,{2024,1,4});
ClinicalProtocol cumulative{{"a","b"},{2,3},true}; auto c=expand_clinical_protocol({2024,1,1},cumulative,{2024,1,4});
return d.status==ClinicalStatus::ok && d.milestones[1].due.day==4 && c.status==ClinicalStatus::horizon_exceeded && c.milestones.empty() && c.blocking_index==1 ? 0 : 1;""",
        """auto empty=expand_clinical_protocol({2024,1,1},{},{2024,1,1}); auto bad=expand_clinical_protocol({2024,1,1},{{"x","x"},{1,1},true},{2024,1,10});
return empty.status==ClinicalStatus::ok && empty.milestones.empty() && bad.status==ClinicalStatus::invalid_protocol && bad.blocking_index==1 ? 0 : 1;""",
        "Date origin=protocol.cumulative?current:treatment;",
        "Date origin=treatment;",
        "measure every gap from treatment and ignore cumulative protocol state",
        "preserve label order and use the previous milestone only in cumulative mode",
        "labels/gaps must align and dates exactly at the inclusive horizon are accepted; failure is atomic",
        ("gap expansion", "cumulative", "direct origin", "blocking index"),
    ),
    DateMathCase(
        "safe-date-retention",
        "retention-stage-calculator",
        "Retention stage calculator",
        "calculate review and purge stages with checked year conversion",
        "checked year-to-month multiplication followed by two-stage atomic transformation",
        """struct Date { int year; int month; int day; };
struct RetentionRecord { std::string id; Date created; };
struct RetentionRule { long long review_years; long long purge_days_after_review; };
struct RetentionStage { std::string id; Date review; Date purge; };
enum class RetentionStatus { ok, invalid_input, range_exceeded };
struct RetentionBatch { RetentionStatus status = RetentionStatus::invalid_input; std::vector<RetentionStage> stages; std::string blocking_id; };""",
        "RetentionBatch",
        "calculate_retention_stages",
        "const std::vector<RetentionRecord>& records, const RetentionRule& rule, Date maximum",
        """RetentionBatch result;
if(!valid_date(maximum)||rule.review_years<0||rule.purge_days_after_review<0||rule.review_years>std::numeric_limits<long long>::max()/12) return result;
long long review_months=rule.review_years*12; std::set<std::string> ids; std::vector<RetentionStage> staged;
for(const auto& record:records) { if(record.id.empty()||!ids.insert(record.id).second||!valid_date(record.created)) { result.blocking_id=record.id; return result; } Date review{}; Date purge{}; if(!add_months(record.created,review_months,review)||!add_days(review,rule.purge_days_after_review,purge)||date_less(maximum,review)||date_less(maximum,purge)) { result.status=RetentionStatus::range_exceeded; result.blocking_id=record.id; return result; } staged.push_back({record.id,review,purge}); }
result.status=RetentionStatus::ok; result.stages=std::move(staged); return result;""",
        """auto r=calculate_retention_stages({{"case",{2020,2,29}}},{1,1},{2022,12,31});
return r.status==RetentionStatus::ok && r.stages.size()==1 && r.stages[0].review.year==2021 && r.stages[0].review.month==2 && r.stages[0].review.day==28 && r.stages[0].purge.year==2021 && r.stages[0].purge.month==3 && r.stages[0].purge.day==1 ? 0 : 1;""",
        """auto exact=calculate_retention_stages({{"x",{2024,1,1}}},{0,1},{2024,1,2}); auto overflow=calculate_retention_stages({{"x",{9999,12,31}}},{1,0},{9999,12,31});
return exact.status==RetentionStatus::ok && exact.stages[0].purge.day==2 && overflow.status==RetentionStatus::range_exceeded && overflow.stages.empty() ? 0 : 1;""",
        """auto empty=calculate_retention_stages({}, {100,100}, {9999,12,31}); auto duplicate=calculate_retention_stages({{"x",{2024,1,1}},{"x",{2024,1,2}}},{0,0},{2024,12,31});
return empty.status==RetentionStatus::ok && duplicate.status==RetentionStatus::invalid_input && duplicate.stages.empty() ? 0 : 1;""",
        "add_days(review,rule.purge_days_after_review,purge)",
        "add_days(record.created,rule.purge_days_after_review,purge)",
        "compute purge from creation rather than from the checked review stage",
        "preserve record order and stage the complete batch before commit",
        "year multiplication, review, purge, and the inclusive maximum are checked separately; one failure is atomic",
        ("review stage", "purge stage", "checked multiply", "batch atomic"),
    ),
    DateMathCase(
        "safe-date-satellite-ephemeris",
        "epoch-span-partitioner",
        "Epoch span partitioner",
        "partition a requested closed date span around a supported epoch horizon",
        "closed-interval intersection with predecessor/successor segmentation",
        """struct Date { int year; int month; int day; };
struct DateSpan { Date first; Date last; };
struct ObservationSpan { Date first; Date last; };
struct EpochHorizon { Date first; Date last; };
enum class EpochStatus { ok, invalid_span };
struct EpochPartition { EpochStatus status = EpochStatus::invalid_span; std::optional<DateSpan> before; std::optional<DateSpan> representable; std::optional<DateSpan> after; long long representable_days = 0; };""",
        "EpochPartition",
        "partition_epoch_span",
        "ObservationSpan requested, EpochHorizon supported",
        """EpochPartition result;
if(!valid_date(requested.first)||!valid_date(requested.last)||!valid_date(supported.first)||!valid_date(supported.last)||date_less(requested.last,requested.first)||date_less(supported.last,supported.first)) return result;
long long rf=serial_day(requested.first), rl=serial_day(requested.last), sf=serial_day(supported.first), sl=serial_day(supported.last); result.status=EpochStatus::ok;
long long inside_first=std::max(rf,sf), inside_last=std::min(rl,sl);
if(inside_first<=inside_last) { result.representable=DateSpan{date_from_serial(inside_first),date_from_serial(inside_last)}; result.representable_days=inside_last-inside_first+1; }
if(rf<inside_first) result.before=DateSpan{requested.first,date_from_serial(std::min(rl,inside_first-1))}; else if(rl<sf) result.before=DateSpan{requested.first,requested.last};
if(inside_last<rl && inside_first<=inside_last) result.after=DateSpan{date_from_serial(inside_last+1),requested.last}; else if(sl<rf) result.after=DateSpan{requested.first,requested.last};
return result;""",
        """auto r=partition_epoch_span({{2023,12,30},{2024,1,3}},{{2024,1,1},{2024,1,2}});
return r.status==EpochStatus::ok && r.before.has_value() && r.representable.has_value() && r.after.has_value() && r.representable_days==2 && r.before->last.day==31 && r.after->first.day==3 ? 0 : 1;""",
        """auto one=partition_epoch_span({{2024,1,1},{2024,1,1}},{{2024,1,1},{2024,1,1}}); auto before=partition_epoch_span({{2023,1,1},{2023,1,2}},{{2024,1,1},{2024,1,2}});
return one.representable_days==1 && !one.before.has_value() && !one.after.has_value() && before.before.has_value() && !before.representable.has_value() && before.representable_days==0 ? 0 : 1;""",
        """auto invalid=partition_epoch_span({{2024,2,1},{2024,1,1}},{{2024,1,1},{2024,12,31}}); auto after=partition_epoch_span({{2025,1,1},{2025,1,2}},{{2024,1,1},{2024,12,31}});
return invalid.status==EpochStatus::invalid_span && after.after.has_value() && !after.before.has_value() && !after.representable.has_value() ? 0 : 1;""",
        "inside_last-inside_first+1",
        "inside_last-inside_first",
        "treat closed endpoints as half-open and lose the one-day intersection",
        "return at most three disjoint pieces in chronological order",
        "both spans are closed and touching endpoints form a one-day representable segment",
        ("closed span", "intersection", "before segment", "after segment"),
    ),
    DateMathCase(
        "safe-date-supply-chain",
        "checked-stage-pipeline",
        "Checked supply-stage pipeline",
        "evaluate a branching supply graph by maximum predecessor completion",
        "topological critical-path evaluation with mixed month/day stage transforms",
        """struct Date { int year; int month; int day; };
struct SupplyStage { std::string id; std::vector<std::string> predecessors; int lead_months; int lead_days; };
struct StageCompletion { std::string id; Date started; Date completed; };
enum class SupplyStatus { ok, invalid_input, cycle, range_exceeded };
struct SupplyPlan { SupplyStatus status = SupplyStatus::invalid_input; std::vector<StageCompletion> completions; std::string blocking_stage; };""",
        "SupplyPlan",
        "evaluate_supply_stages",
        "Date order_date, const std::vector<SupplyStage>& stages, Date latest",
        """SupplyPlan result;
if(!valid_date(order_date)||!valid_date(latest)||date_less(latest,order_date)) return result;
std::map<std::string,std::size_t> index;
for(std::size_t i=0;i<stages.size();++i) if(stages[i].id.empty()||stages[i].lead_months<0||stages[i].lead_days<0||!index.emplace(stages[i].id,i).second) { result.blocking_stage=stages[i].id; return result; }
std::vector<int> indegree(stages.size(),0); std::vector<std::vector<std::size_t>> next(stages.size()); for(std::size_t i=0;i<stages.size();++i) for(const auto& p:stages[i].predecessors) { auto it=index.find(p); if(it==index.end()||it->second==i) { result.blocking_stage=stages[i].id; return result; } ++indegree[i]; next[it->second].push_back(i); }
std::set<std::string> ready; for(std::size_t i=0;i<stages.size();++i) if(indegree[i]==0) ready.insert(stages[i].id); std::vector<Date> completed(stages.size()); std::vector<StageCompletion> staged;
while(!ready.empty()) { std::string id=*ready.begin(); ready.erase(ready.begin()); std::size_t i=index.at(id); Date start=order_date; bool have_start=false; for(const auto& p:stages[i].predecessors) { Date candidate=completed[index.at(p)]; if(!have_start||date_less(start,candidate)) { start=candidate; have_start=true; } }
 Date month_due{}; Date done{}; if(!add_months(start,stages[i].lead_months,month_due)||!add_days(month_due,stages[i].lead_days,done)||date_less(latest,done)) { result.status=SupplyStatus::range_exceeded; result.blocking_stage=id; return result; } completed[i]=done; staged.push_back({id,start,done}); for(std::size_t child:next[i]) if(--indegree[child]==0) ready.insert(stages[child].id); }
if(staged.size()!=stages.size()) { result.status=SupplyStatus::cycle; return result; } result.status=SupplyStatus::ok; result.completions=std::move(staged); return result;""",
        """std::vector<SupplyStage> s{{"make",{},0,5},{"ship",{},0,10},{"merge",{"make","ship"},0,2}}; auto r=evaluate_supply_stages({2024,1,1},s,{2024,12,31});
return r.status==SupplyStatus::ok && r.completions.size()==3 && r.completions[2].started.day==11 && r.completions[2].completed.day==13 ? 0 : 1;""",
        """auto cycle=evaluate_supply_stages({2024,1,1},{{"a",{"b"},0,1},{"b",{"a"},0,1}},{2024,12,31}); auto range=evaluate_supply_stages({2024,12,31},{{"a",{},0,1}},{2024,12,31});
return cycle.status==SupplyStatus::cycle && range.status==SupplyStatus::range_exceeded && range.completions.empty() ? 0 : 1;""",
        """auto month=evaluate_supply_stages({2024,1,31},{{"a",{},1,1}},{2024,3,1}); auto empty=evaluate_supply_stages({2024,1,1},{},{2024,1,1});
return month.status==SupplyStatus::ok && month.completions[0].completed.month==3 && month.completions[0].completed.day==1 && empty.status==SupplyStatus::ok ? 0 : 1;""",
        "if(!have_start||date_less(start,candidate))",
        "if(!have_start)",
        "use only the first predecessor instead of the maximum completion date",
        "select lexicographically ready stages and start a join after its latest predecessor",
        "cycles, unknown predecessors, negative leads, and any completion after latest invalidate the atomic plan",
        ("critical path", "maximum predecessor", "mixed lead", "topological stage"),
    ),
    DateMathCase(
        "safe-date-voucher-expiry",
        "voucher-lifecycle-ledger",
        "Voucher lifecycle ledger",
        "replay voucher lifecycle events with checked paused-duration expiry transfer",
        "event-sourced per-voucher finite-state machine",
        """struct Date { int year; int month; int day; };
enum class VoucherEventKind { issue, suspend, reactivate, redeem };
struct VoucherEvent { int event_id; std::string voucher_id; VoucherEventKind kind; Date date; int lifetime_days; };
enum class VoucherStateKind { live, suspended, redeemed };
struct VoucherState { std::string voucher_id; VoucherStateKind state; Date expiry; std::optional<Date> suspended_at; };
enum class VoucherStatus { ok, invalid_event, range_exceeded };
struct VoucherLedger { VoucherStatus status = VoucherStatus::invalid_event; std::vector<VoucherState> states; std::vector<int> applied_event_ids; int blocking_event_id = -1; };""",
        "VoucherLedger",
        "replay_voucher_events",
        "const std::vector<VoucherEvent>& events, Date maximum",
        """VoucherLedger result;
if(!valid_date(maximum)) return result;
std::map<std::string,VoucherState> states; int previous=std::numeric_limits<int>::min(); std::vector<int> applied;
for(const auto& event:events) { if(event.event_id<=previous||event.voucher_id.empty()||!valid_date(event.date)) { result.blocking_event_id=event.event_id; return result; } previous=event.event_id; auto it=states.find(event.voucher_id);
 if(event.kind==VoucherEventKind::issue) { Date expiry{}; if(it!=states.end()||event.lifetime_days<0) { result.blocking_event_id=event.event_id; return result; } if(!add_days(event.date,event.lifetime_days,expiry)||date_less(maximum,expiry)) { result.status=VoucherStatus::range_exceeded; result.blocking_event_id=event.event_id; return result; } states.emplace(event.voucher_id,VoucherState{event.voucher_id,VoucherStateKind::live,expiry,std::nullopt}); }
 else { if(it==states.end()||date_less(event.date,it->second.suspended_at.value_or(event.date))) { result.blocking_event_id=event.event_id; return result; }
  if(event.kind==VoucherEventKind::suspend) { if(it->second.state!=VoucherStateKind::live||date_less(it->second.expiry,event.date)) { result.blocking_event_id=event.event_id; return result; } it->second.state=VoucherStateKind::suspended; it->second.suspended_at=event.date; }
  else if(event.kind==VoucherEventKind::reactivate) { if(it->second.state!=VoucherStateKind::suspended) { result.blocking_event_id=event.event_id; return result; } long long pause=serial_day(event.date)-serial_day(*it->second.suspended_at); Date shifted{}; if(pause<0||!add_days(it->second.expiry,pause,shifted)||date_less(maximum,shifted)) { result.status=VoucherStatus::range_exceeded; result.blocking_event_id=event.event_id; return result; } it->second.expiry=shifted; it->second.state=VoucherStateKind::live; it->second.suspended_at.reset(); }
  else { if(it->second.state!=VoucherStateKind::live||date_less(it->second.expiry,event.date)) { result.blocking_event_id=event.event_id; return result; } it->second.state=VoucherStateKind::redeemed; }
 }
 applied.push_back(event.event_id); }
result.status=VoucherStatus::ok; result.applied_event_ids=std::move(applied); for(const auto& item:states) result.states.push_back(item.second); return result;""",
        """std::vector<VoucherEvent> e{{1,"v",VoucherEventKind::issue,{2024,1,1},10},{2,"v",VoucherEventKind::suspend,{2024,1,4},0},{3,"v",VoucherEventKind::reactivate,{2024,1,6},0},{4,"v",VoucherEventKind::redeem,{2024,1,12},0}}; auto r=replay_voucher_events(e,{2024,12,31});
return r.status==VoucherStatus::ok && r.states.size()==1 && r.states[0].state==VoucherStateKind::redeemed && r.states[0].expiry.day==13 && r.applied_event_ids.size()==4 ? 0 : 1;""",
        """auto illegal=replay_voucher_events({{1,"v",VoucherEventKind::issue,{2024,1,1},2},{2,"v",VoucherEventKind::suspend,{2024,1,2},0},{3,"v",VoucherEventKind::redeem,{2024,1,2},0}},{2024,12,31}); auto order=replay_voucher_events({{2,"v",VoucherEventKind::issue,{2024,1,1},2},{1,"v",VoucherEventKind::redeem,{2024,1,2},0}},{2024,12,31});
return illegal.status==VoucherStatus::invalid_event && illegal.states.empty() && order.status==VoucherStatus::invalid_event ? 0 : 1;""",
        """auto empty=replay_voucher_events({}, {9999,12,31}); auto range=replay_voucher_events({{1,"v",VoucherEventKind::issue,{9999,12,31},1}},{9999,12,31});
return empty.status==VoucherStatus::ok && range.status==VoucherStatus::range_exceeded && range.states.empty() ? 0 : 1;""",
        "it->second.expiry=shifted; it->second.state=VoucherStateKind::live;",
        "it->second.state=VoucherStateKind::live;",
        "reactivate a voucher without transferring the paused duration to expiry",
        "replay globally increasing event IDs and retain voucher states in ID order",
        "illegal transitions or time reversal stop at the first event; no final state is committed on error",
        ("event replay", "suspend", "reactivate", "pause transfer"),
    ),
)
