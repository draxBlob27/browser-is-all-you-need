"""Task-specific C++ contracts for sequence-pattern remediation v2."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SequenceCase:
    legacy_id: str
    task_id: str
    title: str
    profile: str
    objective: str
    public_api: str
    marker: str
    instructions: str
    header: str
    starter: str
    reference: str
    visible_test: str
    hidden_test: str


def _starter(body: str) -> str:
    return '#include "task.h"\nnamespace curriculum {\n' + body.strip() + '\n}\n'


CASES = (
SequenceCase(
"seq-audit-signature", "audit-event-kmp-v2", "Audit Event KMP", "typed-event-prefix-kmp",
"Locate overlapping typed audit signatures with one prefix-function scan.",
"AuditEventMatcher::find(stream, signature) -> ordered half-open spans", "prefix[j - 1U]",
r"""# Instructions

`AuditEventMatcher::find` matches `(code,severity)` keys. Codes and IDs must be
nonempty and severities nonnegative; invalid input or an empty signature returns
empty. Preserve overlapping matches and return half-open spans by increasing begin.
Use one prefix-function scan; do not restart a comparison at every stream position.
""",
r"""#pragma once
#include <cstddef>
#include <string>
#include <utility>
#include <vector>
namespace curriculum {
struct AuditEvent { std::string code; int severity=0; std::string id; };
struct AuditSpan { std::size_t begin=0,end=0; bool operator==(const AuditSpan& o)const{return begin==o.begin&&end==o.end;} };
class AuditEventMatcher { public: static std::vector<AuditSpan> find(const std::vector<AuditEvent>&,const std::vector<std::pair<std::string,int>>&); };
}
""",
_starter("std::vector<AuditSpan> AuditEventMatcher::find(const std::vector<AuditEvent>&,const std::vector<std::pair<std::string,int>>&){return {}; }"),
r"""#include "task.h"
namespace curriculum {
std::vector<AuditSpan> AuditEventMatcher::find(const std::vector<AuditEvent>& stream,const std::vector<std::pair<std::string,int>>& pattern){
 if(pattern.empty())return{};for(const auto& e:stream)if(e.code.empty()||e.id.empty()||e.severity<0)return{};for(const auto& p:pattern)if(p.first.empty()||p.second<0)return{};
 std::vector<std::size_t> prefix(pattern.size());for(std::size_t i=1,j=0;i<pattern.size();++i){while(j&&pattern[i]!=pattern[j])j=prefix[j-1U];if(pattern[i]==pattern[j])++j;prefix[i]=j;}
 std::vector<AuditSpan> out;for(std::size_t i=0,j=0;i<stream.size();++i){std::pair<std::string,int> key{stream[i].code,stream[i].severity};while(j&&key!=pattern[j])j=prefix[j-1U];if(key==pattern[j])++j;if(j==pattern.size()){out.push_back({i+1U-j,i+1U});j=prefix[j-1U];}}return out;
}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;std::vector<AuditEvent>s{{"a",1,"1"},{"b",2,"2"},{"a",1,"3"},{"b",2,"4"}};return AuditEventMatcher::find(s,{{"a",1},{"b",2}})==std::vector<AuditSpan>{{0,2},{2,4}}?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;std::vector<AuditEvent>s{{"a",1,"1"},{"a",1,"2"},{"b",2,"3"},{"a",1,"4"},{"a",1,"5"},{"b",2,"6"}};f+=AuditEventMatcher::find(s,{{"a",1},{"a",1},{"b",2}})!=std::vector<AuditSpan>{{0,3},{3,6}};s[2].severity=9;f+=AuditEventMatcher::find(s,{{"a",1},{"a",1},{"b",2}})!=std::vector<AuditSpan>{{3,6}};return f;}
"""),
SequenceCase(
"seq-dna-motif", "dna-shift-and-v2", "DNA Shift-And", "iupac-bit-parallel-shift-and",
"Scan IUPAC motifs with a bit-parallel Shift-And state.", "DnaShiftAnd::scan(dna, motif) -> MotifScan", "state = ((state << 1U) | 1U)",
r"""# Instructions

DNA accepts uppercase A/C/G/T. Motifs accept A/C/G/T/R/Y/N and have length
1..63. Invalid input returns `valid=false` with the first bad index. Otherwise
return every overlapping offset. Compile IUPAC masks and update one Shift-And
word per DNA base; literal substring search is not the task.
""",
r"""#pragma once
#include <cstddef>
#include <limits>
#include <string_view>
#include <vector>
namespace curriculum {struct MotifScan{std::vector<std::size_t> offsets;std::size_t invalid_index=std::numeric_limits<std::size_t>::max();bool valid=true;};class DnaShiftAnd{public:static MotifScan scan(std::string_view,std::string_view);};}
""",
_starter("MotifScan DnaShiftAnd::scan(std::string_view,std::string_view){return{{},0,false};}"),
r"""#include "task.h"
#include <array>
#include <cstdint>
namespace curriculum {namespace {int base(char c){return c=='A'?0:c=='C'?1:c=='G'?2:c=='T'?3:-1;}int mask(char c){return c=='A'?1:c=='C'?2:c=='G'?4:c=='T'?8:c=='R'?5:c=='Y'?10:c=='N'?15:0;}}
MotifScan DnaShiftAnd::scan(std::string_view dna,std::string_view motif){MotifScan out;if(motif.empty()||motif.size()>63){out.valid=false;out.invalid_index=0;return out;}std::array<std::uint64_t,4> accept{};for(std::size_t i=0;i<motif.size();++i){int m=mask(motif[i]);if(!m){out.valid=false;out.invalid_index=i;return out;}for(int b=0;b<4;++b)if(m&(1<<b))accept[b]|=(std::uint64_t{1}<<i);}std::uint64_t state=0,hit=std::uint64_t{1}<<(motif.size()-1U);for(std::size_t i=0;i<dna.size();++i){int b=base(dna[i]);if(b<0){out.offsets.clear();out.valid=false;out.invalid_index=i;return out;}state=((state<<1U)|1U)&accept[static_cast<std::size_t>(b)];if(state&hit)out.offsets.push_back(i+1U-motif.size());}return out;}}
""",
r"""#include "task.h"
int main(){auto r=curriculum::DnaShiftAnd::scan("ACACAC","AN");return r.valid&&r.offsets==std::vector<std::size_t>{0,2,4}?0:1;}
""",
r"""#include "task.h"
int main(){using curriculum::DnaShiftAnd;int f=0;f+=DnaShiftAnd::scan("AGCT","RY").offsets!=std::vector<std::size_t>{1};auto bad=DnaShiftAnd::scan("ACX","AN");f+=bad.valid||bad.invalid_index!=2;f+=!DnaShiftAnd::scan("AAAA","AA").valid;f+=DnaShiftAnd::scan("AAAA","AA").offsets!=std::vector<std::size_t>{0,1,2};return f;}
"""),
SequenceCase(
"seq-command-policy", "command-aho-policy-v2", "Command Aho Policy", "multi-policy-aho-corasick",
"Find the first multi-policy command violation with an Aho-Corasick automaton.", "CommandPolicyAutomaton(policies).first_violation(commands)", "failure",
r"""# Instructions

Policies have unique nonempty IDs, nonempty command lists, and nonnegative
priority; invalid construction throws. Build trie failure links once. The first
violation is chosen by earliest end, lower priority, then lexical ID. Return
`found=false` when no policy matches.
""",
r"""#pragma once
#include <cstddef>
#include <map>
#include <string>
#include <vector>
namespace curriculum {struct CommandPolicy{std::string id;std::vector<std::string> commands;int priority=0;};struct PolicyHit{bool found=false;std::string policy_id;std::size_t begin=0,end=0;};class CommandPolicyAutomaton{struct Node{std::map<std::string,std::size_t> next;std::size_t failure=0;std::vector<std::size_t> outputs;};std::vector<CommandPolicy> policies_;std::vector<Node> nodes_;public:explicit CommandPolicyAutomaton(std::vector<CommandPolicy>);PolicyHit first_violation(const std::vector<std::string>&)const;};}
""",
_starter("CommandPolicyAutomaton::CommandPolicyAutomaton(std::vector<CommandPolicy> p):policies_(std::move(p)),nodes_(1){} PolicyHit CommandPolicyAutomaton::first_violation(const std::vector<std::string>&)const{return{};}"),
r"""#include "task.h"
#include <algorithm>
#include <queue>
#include <set>
#include <stdexcept>
#include <tuple>
namespace curriculum {CommandPolicyAutomaton::CommandPolicyAutomaton(std::vector<CommandPolicy> p):policies_(std::move(p)),nodes_(1){std::set<std::string>ids;for(std::size_t k=0;k<policies_.size();++k){auto& x=policies_[k];if(x.id.empty()||x.commands.empty()||x.priority<0||!ids.insert(x.id).second)throw std::invalid_argument("policy");std::size_t n=0;for(const auto& c:x.commands){if(c.empty())throw std::invalid_argument("command");auto [it,added]=nodes_[n].next.emplace(c,nodes_.size());if(added)nodes_.push_back({});n=it->second;}nodes_[n].outputs.push_back(k);}std::queue<std::size_t>q;for(auto [_,n]:nodes_[0].next)q.push(n);while(!q.empty()){auto u=q.front();q.pop();for(auto [token,v]:nodes_[u].next){std::size_t failure=nodes_[u].failure;while(failure&&nodes_[failure].next.count(token)==0)failure=nodes_[failure].failure;auto it=nodes_[failure].next.find(token);if(it!=nodes_[failure].next.end()&&it->second!=v)failure=it->second;nodes_[v].failure=failure;nodes_[v].outputs.insert(nodes_[v].outputs.end(),nodes_[failure].outputs.begin(),nodes_[failure].outputs.end());q.push(v);}}}
PolicyHit CommandPolicyAutomaton::first_violation(const std::vector<std::string>& stream)const{std::size_t state=0;for(std::size_t i=0;i<stream.size();++i){while(state&&nodes_[state].next.count(stream[i])==0)state=nodes_[state].failure;auto it=nodes_[state].next.find(stream[i]);if(it!=nodes_[state].next.end())state=it->second;if(!nodes_[state].outputs.empty()){auto best=*std::min_element(nodes_[state].outputs.begin(),nodes_[state].outputs.end(),[&](auto a,auto b){return std::tie(policies_[a].priority,policies_[a].id)<std::tie(policies_[b].priority,policies_[b].id);});return{true,policies_[best].id,i+1U-policies_[best].commands.size(),i+1U};}}return{};}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;CommandPolicyAutomaton a({{"danger",{"rm","all"},2},{"safer",{"all"},1}});auto h=a.first_violation({"rm","all"});return h.found&&h.policy_id=="safer"&&h.end==2?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;CommandPolicyAutomaton a({{"long",{"a","b","a"},2},{"suffix",{"b","a"},1}});auto h=a.first_violation({"x","a","b","a"});int f=!(h.found&&h.policy_id=="suffix"&&h.begin==2);f+=a.first_violation({"a","x"}).found;return f;}
"""),
SequenceCase(
"seq-playlist-excerpt", "playlist-gap-alignment-v2", "Playlist Gap Alignment", "minimum-gap-dynamic-program",
"Align a folded playlist excerpt with a bounded number of skipped tracks.", "PlaylistGapAligner::align(playlist, clip, max_skips)", "predecessor",
r"""# Instructions

Track IDs use ASCII case-folding. Unavailable tracks cannot match. Choose a
complete alignment with minimum skipped positions between selected tracks,
then the lexicographically smallest index vector; reject alignments exceeding
`max_skips`. An empty clip matches with empty indices.
""",
r"""#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum {struct PlaylistTrack{std::string id;bool unavailable=false;};struct ExcerptAlignment{bool found=false;std::vector<std::size_t> indices;std::size_t skipped=0;};class PlaylistGapAligner{public:static ExcerptAlignment align(const std::vector<PlaylistTrack>&,const std::vector<std::string>&,std::size_t);};}
""",
_starter("ExcerptAlignment PlaylistGapAligner::align(const std::vector<PlaylistTrack>&,const std::vector<std::string>&,std::size_t){return{};}"),
r"""#include "task.h"
#include <algorithm>
#include <cctype>
#include <optional>
namespace curriculum {namespace {std::string fold(std::string s){for(char&c:s)c=static_cast<char>(std::tolower(static_cast<unsigned char>(c)));return s;}}
ExcerptAlignment PlaylistGapAligner::align(const std::vector<PlaylistTrack>& list,const std::vector<std::string>& clip,std::size_t limit){if(clip.empty())return{true,{},0};for(const auto&x:clip)if(x.empty())return{};std::vector<std::optional<std::vector<std::size_t>>> predecessor(list.size());for(std::size_t i=0;i<list.size();++i)if(!list[i].unavailable&&fold(list[i].id)==fold(clip[0]))predecessor[i]=std::vector<std::size_t>{i};for(std::size_t k=1;k<clip.size();++k){std::vector<std::optional<std::vector<std::size_t>>> next(list.size());for(std::size_t i=0;i<list.size();++i)if(!list[i].unavailable&&fold(list[i].id)==fold(clip[k]))for(std::size_t j=0;j<i;++j)if(predecessor[j]){auto candidate=*predecessor[j];candidate.push_back(i);std::size_t gaps=i-candidate.front()+1U-candidate.size();if(gaps<=limit&&(!next[i]||candidate<*next[i]))next[i]=candidate;}predecessor=std::move(next);}std::optional<std::vector<std::size_t>>best;std::size_t gaps=0;for(auto&v:predecessor)if(v){auto g=v->back()-v->front()+1U-v->size();if(!best||g<gaps||(g==gaps&&*v<*best)){best=*v;gaps=g;}}return best?ExcerptAlignment{true,*best,gaps}:ExcerptAlignment{};}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;auto r=PlaylistGapAligner::align({{"A",false},{"x",false},{"B",false}}, {"a","b"},1);return r.found&&r.indices==std::vector<std::size_t>{0,2}&&r.skipped==1?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;auto r=PlaylistGapAligner::align({{"a",false},{"b",true},{"b",false},{"c",false}}, {"a","b","c"},1);f+=!(r.found&&r.indices==std::vector<std::size_t>{0,2,3});f+=PlaylistGapAligner::align({{"a",false},{"x",false},{"b",false}}, {"a","b"},0).found;f+=!PlaylistGapAligner::align({}, {},0).found;return f;}
"""),
SequenceCase(
"seq-sensor-anomaly", "sensor-stream-window-v2", "Sensor Stream Window", "stateful-ring-window-matcher",
"Match tolerance windows in a fixed-size streaming ring.", "SensorWindowMatcher(pattern,tolerance).push(value)", "head_ = (head_ + 1U) % pattern_.size()",
r"""# Instructions

Construction requires a nonempty pattern and nonnegative tolerance. Each push
gets a monotonic sequence number and returns only a newly completed match.
Keep exactly one pattern-sized circular buffer; do not retain and rescan the
whole history. Absolute differences must be safe at integer extremes.
""",
r"""#pragma once
#include <cstddef>
#include <cstdint>
#include <optional>
#include <vector>
namespace curriculum {struct SensorMatch{std::uint64_t first_sequence=0,last_sequence=0;};class SensorWindowMatcher{std::vector<long>pattern_,ring_;long tolerance_;std::size_t head_=0,count_=0;std::uint64_t sequence_=0;public:SensorWindowMatcher(std::vector<long>,long);std::optional<SensorMatch>push(long);std::size_t buffered()const{return count_;};};}
""",
_starter("SensorWindowMatcher::SensorWindowMatcher(std::vector<long>p,long t):pattern_(std::move(p)),ring_(pattern_.size()),tolerance_(t){} std::optional<SensorMatch> SensorWindowMatcher::push(long){return std::nullopt;}"),
r"""#include "task.h"
#include <limits>
#include <stdexcept>
namespace curriculum {namespace {unsigned long long distance(long a,long b){return a>=b?static_cast<unsigned long long>(a)-static_cast<unsigned long long>(b):static_cast<unsigned long long>(b)-static_cast<unsigned long long>(a);}}
SensorWindowMatcher::SensorWindowMatcher(std::vector<long>p,long t):pattern_(std::move(p)),ring_(pattern_.size()),tolerance_(t){if(pattern_.empty()||t<0)throw std::invalid_argument("pattern");}
std::optional<SensorMatch> SensorWindowMatcher::push(long value){ring_[head_]=value;head_=(head_+1U)%pattern_.size();if(count_<pattern_.size())++count_;auto current=sequence_++;if(count_<pattern_.size())return std::nullopt;for(std::size_t i=0;i<pattern_.size();++i){auto actual=ring_[(head_+i)%pattern_.size()];if(distance(actual,pattern_[i])>static_cast<unsigned long long>(tolerance_))return std::nullopt;}return SensorMatch{current+1U-pattern_.size(),current};}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;SensorWindowMatcher m({10,20,30},1);m.push(9);m.push(20);auto r=m.push(31);return r&&r->first_sequence==0&&r->last_sequence==2&&m.buffered()==3?0:1;}
""",
r"""#include "task.h"
#include <limits>
int main(){using namespace curriculum;int f=0;SensorWindowMatcher m({1,2},0);m.push(1);f+=!m.push(2).has_value();f+=m.push(2).has_value();f+=m.push(1).has_value();f+=!m.push(2).has_value();SensorWindowMatcher x({std::numeric_limits<long>::min()},0);f+=!x.push(std::numeric_limits<long>::min()).has_value();return f;}
"""),
SequenceCase(
"seq-shipment-checkpoints", "checkpoint-gap-dp-v2", "Checkpoint Gap DP", "timestamp-bounded-subsequence-dp",
"Validate required shipment checkpoints under a timestamp gap bound.", "CheckpointGapVerifier::verify(events,required,max_gap)", "reachable",
r"""# Instructions

Checkpoint names are nonempty, times are nondecreasing, and `max_gap` is
nonnegative. Choose the lexicographically smallest complete index sequence
whose consecutive times differ by at most `max_gap`. Invalid input reports
incomplete at required index zero. An empty requirement is complete.
""",
r"""#pragma once
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>
namespace curriculum {struct Checkpoint{std::string name;std::int64_t time=0;};struct RouteAudit{bool complete=false;std::vector<std::size_t>indices;std::size_t missing_required=0;};class CheckpointGapVerifier{public:static RouteAudit verify(const std::vector<Checkpoint>&,const std::vector<std::string>&,std::int64_t);};}
""",
_starter("RouteAudit CheckpointGapVerifier::verify(const std::vector<Checkpoint>&,const std::vector<std::string>&,std::int64_t){return{};}"),
r"""#include "task.h"
#include <optional>
namespace curriculum {RouteAudit CheckpointGapVerifier::verify(const std::vector<Checkpoint>& e,const std::vector<std::string>& req,std::int64_t gap){if(gap<0)return{};for(std::size_t i=0;i<e.size();++i)if(e[i].name.empty()||(i&&e[i].time<e[i-1].time))return{};for(auto&s:req)if(s.empty())return{};if(req.empty())return{true,{},0};std::vector<std::optional<std::vector<std::size_t>>> reachable(e.size());for(std::size_t i=0;i<e.size();++i)if(e[i].name==req[0])reachable[i]=std::vector<std::size_t>{i};std::size_t matched=0;for(std::size_t k=1;k<req.size();++k){std::vector<std::optional<std::vector<std::size_t>>> next(e.size());for(std::size_t i=0;i<e.size();++i)if(e[i].name==req[k])for(std::size_t j=0;j<i;++j)if(reachable[j]&&e[i].time-e[j].time<=gap){auto v=*reachable[j];v.push_back(i);if(!next[i]||v<*next[i])next[i]=v;}bool any=false;for(auto&v:next)any=any||v.has_value();if(!any)return{false,{},k};reachable=std::move(next);matched=k;}std::optional<std::vector<std::size_t>>best;for(auto&v:reachable)if(v&&(!best||*v<*best))best=*v;return best?RouteAudit{true,*best,req.size()}:RouteAudit{false,{},matched};}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;auto r=CheckpointGapVerifier::verify({{"a",0},{"x",2},{"b",4}}, {"a","b"},4);return r.complete&&r.indices==std::vector<std::size_t>{0,2}?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;auto bad=CheckpointGapVerifier::verify({{"a",0},{"b",10}}, {"a","b"},3);f+=bad.complete||bad.missing_required!=1;auto tie=CheckpointGapVerifier::verify({{"a",0},{"a",1},{"b",2}}, {"a","b"},5);f+=tie.indices!=std::vector<std::size_t>{0,2};f+=!CheckpointGapVerifier::verify({}, {},0).complete;return f;}
"""),
SequenceCase(
"seq-log-phrase", "log-lexer-kmp-v2", "Log Lexer KMP", "coordinate-lexer-plus-kmp",
"Lex folded log tokens and locate overlapping phrases with coordinates.", "LogPhraseLexer::find(lines,phrase)", "std::isalnum",
r"""# Instructions

Tokens are maximal ASCII alphanumeric runs, folded to lowercase. Every phrase
entry must normalize to exactly one token. Matches may overlap and cross lines.
Return source begin and exclusive end coordinates. Empty or malformed phrases
return empty; whitespace-only splitting is not sufficient.
""",
r"""#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum {struct LogCoordinate{std::size_t line=0,column=0;bool operator==(const LogCoordinate&o)const{return line==o.line&&column==o.column;}};struct LogPhraseSpan{LogCoordinate begin,end;bool operator==(const LogPhraseSpan&o)const{return begin==o.begin&&end==o.end;}};class LogPhraseLexer{public:static std::vector<LogPhraseSpan>find(const std::vector<std::string>&,const std::vector<std::string>&);};}
""",
_starter("std::vector<LogPhraseSpan> LogPhraseLexer::find(const std::vector<std::string>&,const std::vector<std::string>&){return{};}"),
r"""#include "task.h"
#include <cctype>
namespace curriculum {namespace {struct Tok{std::string value;LogCoordinate begin,end;};std::vector<Tok>lex(const std::vector<std::string>&lines){std::vector<Tok>out;for(std::size_t l=0;l<lines.size();++l)for(std::size_t i=0;i<lines[l].size();){while(i<lines[l].size()&&!std::isalnum(static_cast<unsigned char>(lines[l][i])))++i;std::size_t b=i;std::string v;while(i<lines[l].size()&&std::isalnum(static_cast<unsigned char>(lines[l][i])))v.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(lines[l][i++]))));if(!v.empty())out.push_back({v,{l,b},{l,i}});}return out;}}
std::vector<LogPhraseSpan>LogPhraseLexer::find(const std::vector<std::string>&lines,const std::vector<std::string>&phrase){if(phrase.empty())return{};std::vector<std::string>p;for(auto&s:phrase){auto t=lex({s});if(t.size()!=1)return{};p.push_back(t[0].value);}std::vector<std::size_t>prefix(p.size());for(std::size_t i=1,j=0;i<p.size();++i){while(j&&p[i]!=p[j])j=prefix[j-1];if(p[i]==p[j])++j;prefix[i]=j;}auto tokens=lex(lines);std::vector<LogPhraseSpan>out;for(std::size_t i=0,j=0;i<tokens.size();++i){while(j&&tokens[i].value!=p[j])j=prefix[j-1];if(tokens[i].value==p[j])++j;if(j==p.size()){out.push_back({tokens[i+1-j].begin,tokens[i].end});j=prefix[j-1];}}return out;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;auto r=LogPhraseLexer::find({"Warn: disk","FULL now"},{"disk","full"});return r.size()==1&&r[0].begin==LogCoordinate{0,6}&&r[0].end==LogCoordinate{1,4}?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;auto r=LogPhraseLexer::find({"A,a-a"},{"a","a"});f+=r.size()!=2;f+=!LogPhraseLexer::find({"x y"},{"x y"}).empty();f+=!LogPhraseLexer::find({"a"},{}).empty();return f;}
"""),
SequenceCase(
"seq-ui-workflow", "ui-workflow-dfa-v2", "UI Workflow DFA", "reset-ignore-explicit-dfa",
"Detect login-select-confirm with explicit ignore and reset transitions.", "UiWorkflowDfa::detect(events)", "enum class State",
r"""# Instructions

Detect `login -> select -> confirm`. Benign events preserve state. Reset or
cancel clears it, and a new login restarts at that event. Non-benign events
require nonempty IDs. Return the first completed half-open span and implicated
IDs, or no detection.
""",
r"""#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum {enum class UiKind{benign,reset,login,select,confirm,cancel};struct UiEvent{UiKind kind=UiKind::benign;std::string id;};struct WorkflowDetection{bool found=false;std::size_t begin=0,end=0;std::vector<std::string>ids;};class UiWorkflowDfa{public:WorkflowDetection detect(const std::vector<UiEvent>&)const;};}
""",
_starter("WorkflowDetection UiWorkflowDfa::detect(const std::vector<UiEvent>&)const{return{};}"),
r"""#include "task.h"
namespace curriculum {WorkflowDetection UiWorkflowDfa::detect(const std::vector<UiEvent>&events)const{enum class State{idle,logged,selected};State state=State::idle;std::size_t begin=0;std::vector<std::string>ids;for(std::size_t i=0;i<events.size();++i){auto e=events[i];if(e.kind!=UiKind::benign&&e.id.empty())return{};if(e.kind==UiKind::benign)continue;if(e.kind==UiKind::reset||e.kind==UiKind::cancel){state=State::idle;ids.clear();continue;}if(e.kind==UiKind::login){state=State::logged;begin=i;ids={e.id};continue;}if(e.kind==UiKind::select&&state==State::logged){state=State::selected;ids.push_back(e.id);continue;}if(e.kind==UiKind::confirm&&state==State::selected){ids.push_back(e.id);return{true,begin,i+1,ids};}state=State::idle;ids.clear();}return{};}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;auto r=UiWorkflowDfa{}.detect({{UiKind::login,"l"},{UiKind::benign,""},{UiKind::select,"s"},{UiKind::confirm,"c"}});return r.found&&r.begin==0&&r.end==4&&r.ids.size()==3?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;auto no=UiWorkflowDfa{}.detect({{UiKind::login,"a"},{UiKind::reset,"r"},{UiKind::select,"b"},{UiKind::confirm,"c"}});f+=no.found;auto yes=UiWorkflowDfa{}.detect({{UiKind::login,"old"},{UiKind::login,"new"},{UiKind::select,"s"},{UiKind::confirm,"c"}});f+=!(yes.found&&yes.begin==1&&yes.ids[0]=="new");return f;}
"""),
SequenceCase(
"seq-factory-cycle", "factory-z-cycle-v2", "Factory Z Cycle", "z-function-overlap-counter",
"Count overlapping production cycles with the Z function.", "FactoryCycleZ::locate(stages,cycle)", "right",
r"""# Instructions

Stage IDs must be positive and the cycle nonempty. Return all overlapping start
indices and the longest cycle prefix observed anywhere. Invalid input returns
empty. Build one cycle/sentinel/stage sequence and maintain a Z-box; do not
restart a nested comparison at every stage.
""",
r"""#pragma once
#include <cstddef>
#include <vector>
namespace curriculum {struct CycleReport{std::vector<std::size_t>starts;std::size_t longest_prefix=0;};class FactoryCycleZ{public:static CycleReport locate(const std::vector<int>&,const std::vector<int>&);};}
""",
_starter("CycleReport FactoryCycleZ::locate(const std::vector<int>&,const std::vector<int>&){return{};}"),
r"""#include "task.h"
#include <algorithm>
namespace curriculum {CycleReport FactoryCycleZ::locate(const std::vector<int>&stages,const std::vector<int>&cycle){if(cycle.empty())return{};for(int x:stages)if(x<=0)return{};for(int x:cycle)if(x<=0)return{};std::vector<int>a=cycle;a.push_back(0);a.insert(a.end(),stages.begin(),stages.end());std::vector<std::size_t>z(a.size());std::size_t left=0,right=0;for(std::size_t i=1;i<a.size();++i){if(i<=right)z[i]=std::min(right-i+1,z[i-left]);while(i+z[i]<a.size()&&a[z[i]]==a[i+z[i]])++z[i];if(i+z[i]&&i+z[i]-1>right){left=i;right=i+z[i]-1;}}CycleReport out;for(std::size_t i=cycle.size()+1;i<a.size();++i){auto n=std::min(z[i],cycle.size());out.longest_prefix=std::max(out.longest_prefix,n);if(n==cycle.size())out.starts.push_back(i-cycle.size()-1);}return out;}}
""",
r"""#include "task.h"
int main(){auto r=curriculum::FactoryCycleZ::locate({1,2,1,2,1},{1,2,1});return r.starts==std::vector<std::size_t>{0,2}&&r.longest_prefix==3?0:1;}
""",
r"""#include "task.h"
int main(){using curriculum::FactoryCycleZ;int f=0;auto r=FactoryCycleZ::locate({1,1,1,2},{1,1,2});f+=r.starts!=std::vector<std::size_t>{1};f+=FactoryCycleZ::locate({1,0},{1}).starts.size()!=0;f+=FactoryCycleZ::locate({1,2},{1,2,3}).longest_prefix!=2;return f;}
"""),
SequenceCase(
"seq-network-handshake", "handshake-schema-machine-v2", "Handshake Schema Machine", "optional-repeated-schema-state-machine",
"Verify optional, required, and repeatable protocol fields with a schema state machine.", "HandshakeSchemaMachine::verify(schema,fields)", "FieldRule::repeatable",
r"""# Instructions

Schema names are nonempty. Required fields occur once, optional fields zero or
one time, and repeatable fields one or more times. Adjacent repeatable specs
with the same name are invalid. Field values are nonempty. Report the first
unconsumable input index and expected schema name.
""",
r"""#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum {enum class FieldRule{required,optional,repeatable};struct FieldSpec{std::string name;FieldRule rule=FieldRule::required;};struct ProtocolField{std::string name,value;};struct HandshakeAudit{bool accepted=false;std::size_t field_index=0;std::string expected;};class HandshakeSchemaMachine{public:static HandshakeAudit verify(const std::vector<FieldSpec>&,const std::vector<ProtocolField>&);};}
""",
_starter("HandshakeAudit HandshakeSchemaMachine::verify(const std::vector<FieldSpec>&,const std::vector<ProtocolField>&){return{};}"),
r"""#include "task.h"
namespace curriculum {HandshakeAudit HandshakeSchemaMachine::verify(const std::vector<FieldSpec>&schema,const std::vector<ProtocolField>&fields){for(std::size_t i=0;i<schema.size();++i)if(schema[i].name.empty()||(i&&schema[i].rule==FieldRule::repeatable&&schema[i-1].rule==FieldRule::repeatable&&schema[i].name==schema[i-1].name))return{false,0,"invalid schema"};for(auto&f:fields)if(f.name.empty()||f.value.empty())return{false,0,"invalid field"};std::size_t s=0,i=0;while(s<schema.size()){auto spec=schema[s];if(spec.rule==FieldRule::optional){if(i<fields.size()&&fields[i].name==spec.name)++i;++s;continue;}if(spec.rule==FieldRule::repeatable){std::size_t begin=i;while(i<fields.size()&&fields[i].name==spec.name)++i;if(i==begin)return{false,i,spec.name};++s;continue;}if(i>=fields.size()||fields[i].name!=spec.name)return{false,i,spec.name};++i;++s;}if(i!=fields.size())return{false,i,"end"};return{true,i,""};}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;auto r=HandshakeSchemaMachine::verify({{"hello",FieldRule::required},{"ext",FieldRule::optional},{"data",FieldRule::repeatable}},{{"hello","1"},{"data","a"},{"data","b"}});return r.accepted?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;auto missing=HandshakeSchemaMachine::verify({{"x",FieldRule::repeatable}},{});f+=missing.accepted||missing.expected!="x";auto extra=HandshakeSchemaMachine::verify({{"x",FieldRule::optional}},{{"x","1"},{"x","2"}});f+=extra.accepted||extra.field_index!=1;return f;}
"""),
SequenceCase(
"seq-route-detour", "route-rabin-karp-v2", "Route Rabin-Karp", "pair-key-rabin-karp",
"Locate route detours with a rolling hash over location-direction pairs.", "RouteRabinKarp::find(route,detour)", "rolling",
r"""# Instructions

Locations are nonnegative and directions one of N/E/S/W. Invalid input or an
empty detour returns empty. Return every overlapping half-open match. Hash both
fields with a rolling polynomial and verify equality on each hash hit.
""",
r"""#pragma once
#include <cstddef>
#include <vector>
namespace curriculum {struct RouteStep{int location=0;char direction='N';bool operator==(const RouteStep&o)const{return location==o.location&&direction==o.direction;}};struct DetourSpan{std::size_t begin=0,end=0;bool operator==(const DetourSpan&o)const{return begin==o.begin&&end==o.end;}};class RouteRabinKarp{public:static std::vector<DetourSpan>find(const std::vector<RouteStep>&,const std::vector<RouteStep>&);};}
""",
_starter("std::vector<DetourSpan> RouteRabinKarp::find(const std::vector<RouteStep>&,const std::vector<RouteStep>&){return{};}"),
r"""#include "task.h"
#include <algorithm>
#include <cstdint>
namespace curriculum {namespace {bool valid(RouteStep s){return s.location>=0&&(s.direction=='N'||s.direction=='E'||s.direction=='S'||s.direction=='W');}std::uint64_t key(RouteStep s){return static_cast<std::uint64_t>(s.location+1)*257U+static_cast<unsigned char>(s.direction);}}
std::vector<DetourSpan>RouteRabinKarp::find(const std::vector<RouteStep>&route,const std::vector<RouteStep>&pattern){if(pattern.empty()||pattern.size()>route.size())return{};for(auto s:route)if(!valid(s))return{};for(auto s:pattern)if(!valid(s))return{};constexpr std::uint64_t base=1000003U;std::uint64_t power=1,want=0,rolling=0;for(std::size_t i=0;i<pattern.size();++i){want=want*base+key(pattern[i]);rolling=rolling*base+key(route[i]);if(i+1<pattern.size())power*=base;}std::vector<DetourSpan>out;for(std::size_t i=0;;++i){if(rolling==want&&std::equal(pattern.begin(),pattern.end(),route.begin()+static_cast<std::ptrdiff_t>(i)))out.push_back({i,i+pattern.size()});if(i+pattern.size()==route.size())break;rolling=(rolling-key(route[i])*power)*base+key(route[i+pattern.size()]);}return out;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;auto r=RouteRabinKarp::find({{1,'N'},{2,'E'},{1,'N'},{2,'E'}},{{1,'N'},{2,'E'}});return r==std::vector<DetourSpan>{{0,2},{2,4}}?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;f+=RouteRabinKarp::find({{1,'N'},{2,'E'}},{{1,'N'},{2,'E'}})!=std::vector<DetourSpan>{{0,2}};f+=!RouteRabinKarp::find({{1,'N'},{2,'W'}},{{1,'N'},{2,'E'}}).empty();f+=!RouteRabinKarp::find({{-1,'N'}},{{-1,'N'}}).empty();return f;}
"""),
SequenceCase(
"seq-medication-schedule", "dose-window-deque-v2", "Dose Window Deque", "time-window-deque-state",
"Find the first class A-B-A dose pattern inside a time window.", "DoseWindowPolicy::first_aba(events,window)", "pop_front",
r"""# Instructions

Events require nonempty class/ID, nondecreasing time, and a nonnegative window.
Find the earliest third event completing an A-B-A class pattern with three
distinct event positions and total span at most the window. Ties use the
earliest first event. Unrelated events may occur between the three.
""",
r"""#pragma once
#include <cstdint>
#include <string>
#include <vector>
namespace curriculum {struct DoseEvent{std::string dose_class;std::int64_t time=0;std::string id;};struct DoseViolation{bool found=false;std::vector<std::string>ids;std::int64_t span=0;};class DoseWindowPolicy{public:static DoseViolation first_aba(const std::vector<DoseEvent>&,std::int64_t);};}
""",
_starter("DoseViolation DoseWindowPolicy::first_aba(const std::vector<DoseEvent>&,std::int64_t){return{};}"),
r"""#include "task.h"
#include <deque>
#include <map>
namespace curriculum {DoseViolation DoseWindowPolicy::first_aba(const std::vector<DoseEvent>&e,std::int64_t window){if(window<0)return{};for(std::size_t i=0;i<e.size();++i)if(e[i].dose_class.empty()||e[i].id.empty()||(i&&e[i].time<e[i-1].time))return{};struct Pair{std::size_t a,b;};std::deque<std::size_t>starts;std::deque<Pair>pairs;for(std::size_t i=0;i<e.size();++i){while(!starts.empty()&&e[i].time-e[starts.front()].time>window)starts.pop_front();while(!pairs.empty()&&e[i].time-e[pairs.front().a].time>window)pairs.pop_front();if(e[i].dose_class=="A"&&!pairs.empty()){auto p=pairs.front();return{true,{e[p.a].id,e[p.b].id,e[i].id},e[i].time-e[p.a].time};}if(e[i].dose_class=="B"&&!starts.empty())pairs.push_back({starts.front(),i});if(e[i].dose_class=="A")starts.push_back(i);}return{};}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;auto r=DoseWindowPolicy::first_aba({{"A",0,"a"},{"X",1,"x"},{"B",2,"b"},{"A",4,"c"}},5);return r.found&&r.ids==std::vector<std::string>{"a","b","c"}&&r.span==4?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;f+=DoseWindowPolicy::first_aba({{"A",0,"a"},{"B",5,"b"},{"A",10,"c"}},4).found;auto r=DoseWindowPolicy::first_aba({{"A",0,"a0"},{"A",1,"a1"},{"B",2,"b"},{"A",3,"a2"}},9);f+=!r.found||r.ids[0]!="a0";return f;}
"""),
SequenceCase(
"seq-price-pattern", "price-movement-prefix-v2", "Price Movement Prefix", "derived-alphabet-prefix-function",
"Match a relative movement pattern derived from adjacent prices.", "PriceMovementMatcher::find(quotes,pattern)", "prefix",
r"""# Instructions

Derive `up`, `down`, or `equal` from direct comparisons of consecutive signed
quotes; never subtract them. Match the movement pattern with a prefix function
and preserve overlaps. An empty pattern matches every quote position.
""",
r"""#pragma once
#include <cstddef>
#include <cstdint>
#include <vector>
namespace curriculum {enum class Movement{up,down,equal};struct PricePatternReport{std::vector<std::size_t>quote_starts;};class PriceMovementMatcher{public:static PricePatternReport find(const std::vector<std::int64_t>&,const std::vector<Movement>&);};}
""",
_starter("PricePatternReport PriceMovementMatcher::find(const std::vector<std::int64_t>&,const std::vector<Movement>&){return{};}"),
r"""#include "task.h"
namespace curriculum {PricePatternReport PriceMovementMatcher::find(const std::vector<std::int64_t>&q,const std::vector<Movement>&p){PricePatternReport out;if(p.empty()){for(std::size_t i=0;i<q.size();++i)out.quote_starts.push_back(i);return out;}std::vector<Movement>moves;for(std::size_t i=1;i<q.size();++i)moves.push_back(q[i]>q[i-1]?Movement::up:q[i]<q[i-1]?Movement::down:Movement::equal);std::vector<std::size_t>prefix(p.size());for(std::size_t i=1,j=0;i<p.size();++i){while(j&&p[i]!=p[j])j=prefix[j-1];if(p[i]==p[j])++j;prefix[i]=j;}for(std::size_t i=0,j=0;i<moves.size();++i){while(j&&moves[i]!=p[j])j=prefix[j-1];if(moves[i]==p[j])++j;if(j==p.size()){out.quote_starts.push_back(i+1-j);j=prefix[j-1];}}return out;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;auto r=PriceMovementMatcher::find({1,2,1,2,1},{Movement::up,Movement::down});return r.quote_starts==std::vector<std::size_t>{0,2}?0:1;}
""",
r"""#include "task.h"
#include <limits>
int main(){using namespace curriculum;int f=0;auto a=PriceMovementMatcher::find({10,20,10},{Movement::up,Movement::down});auto b=PriceMovementMatcher::find({-5,5,-5},{Movement::up,Movement::down});f+=a.quote_starts!=b.quote_starts;f+=PriceMovementMatcher::find({std::numeric_limits<std::int64_t>::min(),std::numeric_limits<std::int64_t>::max()},{Movement::up}).quote_starts!=std::vector<std::size_t>{0};f+=PriceMovementMatcher::find({7,8},{ }).quote_starts.size()!=2;return f;}
"""),
SequenceCase(
"seq-document-template", "heading-lcs-alignment-v2", "Heading LCS Alignment", "deterministic-lcs-reconstruction",
"Align normalized required headings by deterministic longest common subsequence.", "HeadingLcsAligner::align(document,required)", "lcs",
r"""# Instructions

Trim ASCII spaces and case-fold headings. Return a longest order-preserving
alignment of required headings into the document. Ties use the
lexicographically smallest document-index vector. Empty requirements return an
empty alignment. This is LCS alignment, not contiguous search.
""",
r"""#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum {struct Heading{std::string text;std::size_t line=0;};struct HeadingAlignment{std::vector<std::size_t>document_indices;std::size_t matched=0;};class HeadingLcsAligner{public:static HeadingAlignment align(const std::vector<Heading>&,const std::vector<std::string>&);};}
""",
_starter("HeadingAlignment HeadingLcsAligner::align(const std::vector<Heading>&,const std::vector<std::string>&){return{};}"),
r"""#include "task.h"
#include <algorithm>
#include <cctype>
namespace curriculum {namespace {std::string norm(std::string s){while(!s.empty()&&s.front()==' ')s.erase(s.begin());while(!s.empty()&&s.back()==' ')s.pop_back();for(char&c:s)c=static_cast<char>(std::tolower(static_cast<unsigned char>(c)));return s;}}
HeadingAlignment HeadingLcsAligner::align(const std::vector<Heading>&d,const std::vector<std::string>&r){std::size_t n=d.size(),m=r.size();std::vector<std::vector<std::size_t>>lcs(n+1,std::vector<std::size_t>(m+1));for(std::size_t i=n;i-->0;)for(std::size_t j=m;j-->0;)lcs[i][j]=norm(d[i].text)==norm(r[j])?1+lcs[i+1][j+1]:std::max(lcs[i+1][j],lcs[i][j+1]);HeadingAlignment out;std::size_t i=0,j=0;while(i<n&&j<m){if(norm(d[i].text)==norm(r[j])&&lcs[i][j]==1+lcs[i+1][j+1]){out.document_indices.push_back(i);++i;++j;}else if(lcs[i+1][j]>=lcs[i][j+1])++i;else ++j;}out.matched=out.document_indices.size();return out;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;auto r=HeadingLcsAligner::align({{"Intro",1},{"x",2},{"API",3}}, {" intro ","api"});return r.matched==2&&r.document_indices==std::vector<std::size_t>{0,2}?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;auto r=HeadingLcsAligner::align({{"a",0},{"b",1},{"a",2}}, {"a","a"});f+=r.document_indices!=std::vector<std::size_t>{0,2};f+=HeadingLcsAligner::align({},{}).matched!=0;return f;}
"""),
SequenceCase(
"seq-access-escalation", "access-gap-nfa-v2", "Access Gap NFA", "bounded-gap-nfa",
"Match multiple privilege rules with bounded unrelated-event gaps.", "AccessGapNfa::first(events,rules)", "active",
r"""# Instructions

Events and rules require nonempty IDs/kinds; rules have nonempty patterns.
Consecutive matched kinds may have at most `max_gap` unrelated events between
them. Return the rule completing at the earliest event, then lexical rule ID,
and its implicated event IDs. Invalid input returns no hit.
""",
r"""#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum {struct AccessEvent{std::string kind,id;};struct EscalationRule{std::string id;std::vector<std::string>kinds;std::size_t max_gap=0;};struct EscalationHit{bool found=false;std::string rule_id;std::vector<std::string>event_ids;};class AccessGapNfa{public:static EscalationHit first(const std::vector<AccessEvent>&,const std::vector<EscalationRule>&);};}
""",
_starter("EscalationHit AccessGapNfa::first(const std::vector<AccessEvent>&,const std::vector<EscalationRule>&){return{};}"),
r"""#include "task.h"
#include <algorithm>
namespace curriculum {EscalationHit AccessGapNfa::first(const std::vector<AccessEvent>&events,const std::vector<EscalationRule>&rules){for(auto&e:events)if(e.kind.empty()||e.id.empty())return{};for(auto&r:rules)if(r.id.empty()||r.kinds.empty()||std::any_of(r.kinds.begin(),r.kinds.end(),[](auto&s){return s.empty();}))return{};struct State{std::size_t rule,pos,last;std::vector<std::string>ids;};std::vector<State>active;for(std::size_t i=0;i<events.size();++i){std::vector<State>next;for(auto&s:active)if(i-s.last-1<=rules[s.rule].max_gap){next.push_back(s);if(events[i].kind==rules[s.rule].kinds[s.pos]){auto t=s;t.last=i;t.ids.push_back(events[i].id);++t.pos;if(t.pos==rules[t.rule].kinds.size())return{true,rules[t.rule].id,t.ids};next.push_back(std::move(t));}}for(std::size_t r=0;r<rules.size();++r)if(events[i].kind==rules[r].kinds[0]){if(rules[r].kinds.size()==1)return{true,rules[r].id,{events[i].id}};next.push_back({r,1,i,{events[i].id}});}std::sort(next.begin(),next.end(),[&](auto&a,auto&b){return rules[a.rule].id<rules[b.rule].id;});active=std::move(next);}return{};}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;auto r=AccessGapNfa::first({{"user","1"},{"noise","2"},{"admin","3"}},{{"review",{"user","admin"},1}});return r.found&&r.rule_id=="review"&&r.event_ids==std::vector<std::string>{"1","3"}?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;f+=AccessGapNfa::first({{"a","1"},{"x","2"},{"x","3"},{"b","4"}},{{"r",{"a","b"},1}}).found;auto t=AccessGapNfa::first({{"a","1"},{"b","2"}},{{"z",{"a","b"},0},{"a",{"a","b"},0}});f+=!t.found||t.rule_id!="a";return f;}
"""),
SequenceCase(
"seq-game-combo", "combo-wildcard-trie-v2", "Combo Wildcard Trie", "wildcard-trie-multi-pattern",
"Recognize the best literal/wildcard combo through one trie.", "ComboTrie(combos).best(presses)", "wildcard",
r"""# Instructions

Combo IDs/buttons are nonempty and IDs unique; invalid construction throws.
`*` matches exactly one press. Choose the longest match, then lower priority,
earlier begin, and lexical ID. Build one trie with literal and wildcard edges;
do not scan each combo independently.
""",
r"""#pragma once
#include <cstddef>
#include <map>
#include <string>
#include <vector>
namespace curriculum {struct Combo{std::string id;std::vector<std::string>buttons;int priority=0;};struct ComboHit{bool found=false;std::string id;std::size_t begin=0,end=0;};class ComboTrie{struct Node{std::map<std::string,std::size_t>literal;std::size_t wildcard=0;std::vector<std::size_t>outputs;};std::vector<Combo>combos_;std::vector<Node>nodes_;public:explicit ComboTrie(std::vector<Combo>);ComboHit best(const std::vector<std::string>&)const;};}
""",
_starter("ComboTrie::ComboTrie(std::vector<Combo> c):combos_(std::move(c)),nodes_(1){} ComboHit ComboTrie::best(const std::vector<std::string>&)const{return{};}"),
r"""#include "task.h"
#include <set>
#include <stdexcept>
#include <tuple>
namespace curriculum {ComboTrie::ComboTrie(std::vector<Combo>c):combos_(std::move(c)),nodes_(1){std::set<std::string>ids;for(std::size_t k=0;k<combos_.size();++k){auto&x=combos_[k];if(x.id.empty()||x.buttons.empty()||x.priority<0||!ids.insert(x.id).second)throw std::invalid_argument("combo");std::size_t n=0;for(auto&b:x.buttons){if(b.empty())throw std::invalid_argument("button");if(b=="*"){if(!nodes_[n].wildcard){nodes_[n].wildcard=nodes_.size();nodes_.push_back({});}n=nodes_[n].wildcard;}else{auto[it,add]=nodes_[n].literal.emplace(b,nodes_.size());if(add)nodes_.push_back({});n=it->second;}}nodes_[n].outputs.push_back(k);}}
ComboHit ComboTrie::best(const std::vector<std::string>&presses)const{ComboHit best;std::size_t best_len=0,best_combo=0;for(std::size_t begin=0;begin<presses.size();++begin){std::vector<std::size_t>active{0};for(std::size_t i=begin;i<presses.size()&&!active.empty();++i){std::vector<std::size_t>next;for(auto n:active){auto it=nodes_[n].literal.find(presses[i]);if(it!=nodes_[n].literal.end())next.push_back(it->second);if(nodes_[n].wildcard)next.push_back(nodes_[n].wildcard);}active=std::move(next);for(auto n:active)for(auto k:nodes_[n].outputs){auto len=i+1-begin;if(!best.found||len>best_len||(len==best_len&&std::tie(combos_[k].priority,begin,combos_[k].id)<std::tie(combos_[best_combo].priority,best.begin,best.id))){best={true,combos_[k].id,begin,i+1};best_len=len;best_combo=k;}}}}return best;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;ComboTrie t({{"short",{"A","*"},2},{"long",{"A","B","C"},5}});auto h=t.best({"A","B","C"});return h.found&&h.id=="long"&&h.end==3?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;ComboTrie t({{"wild",{"A","*"},2},{"literal",{"A","B"},1}});auto h=t.best({"x","A","B"});f+=!h.found||h.id!="literal"||h.begin!=1;f+=t.best({"A"}).found;return f;}
"""),
SequenceCase(
"seq-support-macro", "support-suffix-automaton-v2", "Support Suffix Automaton", "suffix-automaton-repeated-factor",
"Find the longest nonoverlapping repeated unquoted macro factor.", "SupportSuffixAutomaton::longest_repeat(tokens,minimum)", "link",
r"""# Instructions

Remove quoted tokens and ASCII-fold the rest. Return the longest repeated,
nonoverlapping contiguous factor of at least `minimum`; ties use smaller first
then second begin in original-token coordinates. Zero minimum or empty text
returns length zero. Build suffix states and links rather than fixed-length
pairwise scans.
""",
r"""#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum {struct TicketToken{std::string text;bool quoted=false;};struct MacroRepeat{std::size_t length=0,first_begin=0,second_begin=0;};class SupportSuffixAutomaton{public:static MacroRepeat longest_repeat(const std::vector<TicketToken>&,std::size_t);};}
""",
_starter("MacroRepeat SupportSuffixAutomaton::longest_repeat(const std::vector<TicketToken>&,std::size_t){return{};}"),
r"""#include "task.h"
#include <algorithm>
#include <cctype>
#include <map>
#include <tuple>
namespace curriculum {namespace {std::string fold(std::string s){for(char&c:s)c=static_cast<char>(std::tolower(static_cast<unsigned char>(c)));return s;}struct State{int link=-1;std::size_t len=0;std::map<std::string,int>next;std::vector<std::size_t>ends;};}
MacroRepeat SupportSuffixAutomaton::longest_repeat(const std::vector<TicketToken>&input,std::size_t minimum){if(!minimum)return{};std::vector<std::string>text;std::vector<std::size_t>pos;for(std::size_t i=0;i<input.size();++i)if(!input[i].quoted&&!input[i].text.empty()){text.push_back(fold(input[i].text));pos.push_back(i);}std::vector<State>st(1);int last=0;for(std::size_t at=0;at<text.size();++at){int cur=st.size();st.push_back({});st[cur].len=st[last].len+1;st[cur].ends.push_back(at);int p=last;while(p>=0&&!st[p].next.count(text[at])){st[p].next[text[at]]=cur;p=st[p].link;}if(p<0)st[cur].link=0;else{int q=st[p].next[text[at]];if(st[p].len+1==st[q].len)st[cur].link=q;else{int clone=st.size();st.push_back(st[q]);st[clone].len=st[p].len+1;st[clone].ends.clear();while(p>=0&&st[p].next[text[at]]==q){st[p].next[text[at]]=clone;p=st[p].link;}st[q].link=st[cur].link=clone;}}last=cur;}for(int v=static_cast<int>(st.size())-1;v>0;--v)st[st[v].link].ends.insert(st[st[v].link].ends.end(),st[v].ends.begin(),st[v].ends.end());MacroRepeat best;for(auto&s:st)if(s.len>=minimum&&s.ends.size()>=2){std::sort(s.ends.begin(),s.ends.end());for(std::size_t a=0;a<s.ends.size();++a)for(std::size_t b=a+1;b<s.ends.size();++b){auto len=s.len;auto first=s.ends[a]+1-len,second=s.ends[b]+1-len;if(first+len<=second&&(len>best.length||(len==best.length&&std::tie(pos[first],pos[second])<std::tie(best.first_begin,best.second_begin))))best={len,pos[first],pos[second]};}}return best;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;auto r=SupportSuffixAutomaton::longest_repeat({{"Please",false},{"reset",false},{"x",false},{"please",false},{"reset",false}},2);return r.length==2&&r.first_begin==0&&r.second_begin==3?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;auto r=SupportSuffixAutomaton::longest_repeat({{"a",false},{"b",false},{"a",false},{"b",false},{"a",false}},2);f+=r.length!=2;auto q=SupportSuffixAutomaton::longest_repeat({{"a",false},{"b",true},{"a",false}},1);f+=q.length!=1||q.second_begin!=2;return f;}
"""),
SequenceCase(
"seq-assembly-inspection", "inspection-optional-dp-v2", "Inspection Optional DP", "optional-step-dp-witness",
"Match passed inspection steps against required and optional pattern steps.", "OptionalInspectionDp::inspect(steps,pattern)", "optional",
r"""# Instructions

Codes are nonempty and only passed steps may be consumed. Required pattern
steps must match; optional steps may match or be skipped. Choose an accepting
alignment with the most consumed steps, then lexicographically smallest input
indices. Empty patterns accept. Report the first pattern index that cannot be
satisfied.
""",
r"""#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum {struct InspectionStep{std::string code;bool passed=false;};struct PatternStep{std::string code;bool optional=false;};struct InspectionAudit{bool accepted=false;std::vector<std::size_t>consumed;std::size_t failed_pattern=0;};class OptionalInspectionDp{public:static InspectionAudit inspect(const std::vector<InspectionStep>&,const std::vector<PatternStep>&);};}
""",
_starter("InspectionAudit OptionalInspectionDp::inspect(const std::vector<InspectionStep>&,const std::vector<PatternStep>&){return{};}"),
r"""#include "task.h"
#include <optional>
namespace curriculum {InspectionAudit OptionalInspectionDp::inspect(const std::vector<InspectionStep>&steps,const std::vector<PatternStep>&pattern){for(auto&s:steps)if(s.code.empty())return{};for(auto&p:pattern)if(p.code.empty())return{};std::vector<std::optional<std::vector<std::size_t>>>dp(steps.size()+1);dp[0]=std::vector<std::size_t>{};std::size_t far=0;for(std::size_t k=0;k<pattern.size();++k){std::vector<std::optional<std::vector<std::size_t>>>next(steps.size()+1);if(pattern[k].optional)for(std::size_t i=0;i<dp.size();++i)if(dp[i])next[i]=dp[i];for(std::size_t i=0;i<dp.size();++i)if(dp[i])for(std::size_t j=i;j<steps.size();++j)if(steps[j].passed&&steps[j].code==pattern[k].code){auto v=*dp[i];v.push_back(j);if(!next[j+1]||v.size()>next[j+1]->size()||(v.size()==next[j+1]->size()&&v<*next[j+1]))next[j+1]=v;}bool any=false;for(auto&v:next)any=any||v.has_value();if(!any)return{false,{},k};dp=std::move(next);far=k+1;}std::optional<std::vector<std::size_t>>best;for(auto&v:dp)if(v&&(!best||v->size()>best->size()||(v->size()==best->size()&&*v<*best)))best=*v;return{true,best.value_or(std::vector<std::size_t>{}),far};}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;auto r=OptionalInspectionDp::inspect({{"a",true},{"b",true},{"c",true}},{{"a",false},{"b",true},{"c",false}});return r.accepted&&r.consumed==std::vector<std::size_t>{0,1,2}?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;auto r=OptionalInspectionDp::inspect({{"a",true},{"c",true}},{{"a",false},{"b",true},{"c",false}});f+=!r.accepted||r.consumed!=std::vector<std::size_t>{0,1};auto bad=OptionalInspectionDp::inspect({{"a",false}},{{"a",false}});f+=bad.accepted||bad.failed_pattern!=0;return f;}
"""),
SequenceCase(
"seq-currency-arbitrage", "quote-product-window-v2", "Quote Product Window", "checked-oriented-product-window",
"Find the first continuous profitable directed quote cycle.", "QuoteProductWindow::first_cycle(quotes,threshold)", "std::isfinite",
r"""# Instructions

Quotes require nonempty currencies/IDs and finite positive rates. Threshold is
finite and greater than one. A window is a directed continuous chain returning
to its first currency with product at least threshold. Choose earliest end,
then begin. Any invalid input or nonfinite intermediate product returns no hit.
""",
r"""#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum {struct FxQuote{std::string from,to;long double rate=0;std::string id;};struct ArbitrageWindow{bool found=false;std::size_t begin=0,end=0;long double product=0;};class QuoteProductWindow{public:static ArbitrageWindow first_cycle(const std::vector<FxQuote>&,long double);};}
""",
_starter("ArbitrageWindow QuoteProductWindow::first_cycle(const std::vector<FxQuote>&,long double){return{};}"),
r"""#include "task.h"
#include <cmath>
namespace curriculum {ArbitrageWindow QuoteProductWindow::first_cycle(const std::vector<FxQuote>&q,long double threshold){if(!std::isfinite(threshold)||threshold<=1)return{};for(auto&x:q)if(x.from.empty()||x.to.empty()||x.id.empty()||!std::isfinite(x.rate)||x.rate<=0)return{};for(std::size_t end=0;end<q.size();++end)for(std::size_t begin=0;begin<=end;++begin){long double product=1;bool continuous=true;for(std::size_t i=begin;i<=end;++i){if(i>begin&&q[i-1].to!=q[i].from){continuous=false;break;}product*=q[i].rate;if(!std::isfinite(product))return{};}if(continuous&&q[end].to==q[begin].from&&product>=threshold)return{true,begin,end+1,product};}return{};}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;auto r=QuoteProductWindow::first_cycle({{"USD","EUR",1.1L,"a"},{"EUR","USD",1.0L,"b"}},1.05L);return r.found&&r.begin==0&&r.end==2?0:1;}
""",
r"""#include "task.h"
#include <limits>
int main(){using namespace curriculum;int f=0;f+=QuoteProductWindow::first_cycle({{"A","B",2,"1"},{"C","A",2,"2"}},2).found;f+=QuoteProductWindow::first_cycle({{"A","A",std::numeric_limits<long double>::infinity(),"x"}},2).found;f+=!QuoteProductWindow::first_cycle({{"A","A",1.2L,"x"}},1.2L).found;return f;}
"""),
SequenceCase(
"seq-version-migration", "migration-dag-validator-v2", "Migration DAG Validator", "prerequisite-dag-sequence-validator",
"Validate an applied migration sequence against an acyclic prerequisite graph.", "MigrationDagValidator::validate(graph,applied)", "indegree",
r"""# Instructions

Node IDs are unique/nonempty and prerequisites must name existing nodes. The
graph must be acyclic. Applied IDs must exist, be unique, and have all
prerequisites already applied. Invalid graph reports step zero; otherwise
report the first invalid applied index and a deterministic diagnostic.
""",
r"""#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum {struct MigrationNode{std::string id;std::vector<std::string>prerequisites;};struct MigrationAudit{bool valid=false;std::size_t step=0;std::string diagnostic;};class MigrationDagValidator{public:static MigrationAudit validate(const std::vector<MigrationNode>&,const std::vector<std::string>&);};}
""",
_starter("MigrationAudit MigrationDagValidator::validate(const std::vector<MigrationNode>&,const std::vector<std::string>&){return{};}"),
r"""#include "task.h"
#include <map>
#include <queue>
#include <set>
namespace curriculum {MigrationAudit MigrationDagValidator::validate(const std::vector<MigrationNode>&g,const std::vector<std::string>&applied){std::map<std::string,std::size_t>index;for(std::size_t i=0;i<g.size();++i)if(g[i].id.empty()||!index.emplace(g[i].id,i).second)return{false,0,"invalid graph"};std::vector<std::size_t>indegree(g.size());std::vector<std::vector<std::size_t>>edges(g.size());for(std::size_t i=0;i<g.size();++i){std::set<std::string>seen;for(auto&p:g[i].prerequisites){auto it=index.find(p);if(it==index.end()||!seen.insert(p).second)return{false,0,"invalid graph"};edges[it->second].push_back(i);++indegree[i];}}std::queue<std::size_t>q;for(std::size_t i=0;i<g.size();++i)if(!indegree[i])q.push(i);std::size_t visited=0;while(!q.empty()){auto u=q.front();q.pop();++visited;for(auto v:edges[u])if(--indegree[v]==0)q.push(v);}if(visited!=g.size())return{false,0,"cycle"};std::set<std::string>done;for(std::size_t step=0;step<applied.size();++step){auto it=index.find(applied[step]);if(it==index.end())return{false,step,"unknown"};if(!done.insert(applied[step]).second)return{false,step,"duplicate"};for(auto&p:g[it->second].prerequisites)if(!done.count(p))return{false,step,"prerequisite"};}return{true,applied.size(),""};}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;auto r=MigrationDagValidator::validate({{"a",{}},{"b",{"a"}},{"c",{"b"}}},{"a","b","c"});return r.valid&&r.step==3?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;auto p=MigrationDagValidator::validate({{"a",{}},{"b",{"a"}}},{"b"});f+=p.valid||p.step!=0||p.diagnostic!="prerequisite";f+=MigrationDagValidator::validate({{"a",{"b"}},{"b",{"a"}}},{}).valid;f+=MigrationDagValidator::validate({{"a",{}}},{"a","a"}).valid;return f;}
"""),
)


assert len(CASES) == 20
