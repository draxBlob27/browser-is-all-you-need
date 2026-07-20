"""Hand-authored, semantically distinct C++ cases for nested-structure v2."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    task_id: str
    legacy_task_id: str
    title: str
    kind: str
    objective: str
    instructions: str
    header: str
    reference: str
    visible_test: str
    private_test: str
    negative_name: str


def _case(task_id: str, legacy: str, title: str, kind: str, objective: str,
          instructions: str, header: str, reference: str, visible: str,
          private: str, negative: str) -> Case:
    return Case(task_id, legacy, title, kind, objective, instructions, header,
                reference, visible, private, negative)


CASES: tuple[Case, ...] = (
    _case(
        "nest-access-policies-v2", "nest-access-policies", "Access policy audit", "policy-events",
        "Interpret inherited allow/deny scopes and reject privilege escalation.",
        "Interpret typed policy events. `enter_allow` below any active deny is invalid. `leave` requires an active scope. A request is granted only when the nearest active scope is allow; requests without a scope are denied but valid. Empty names are invalid, the first error wins, and granted request names retain event order.",
        r'''#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum {
enum class PolicyOp { enter_allow, enter_deny, leave, request };
struct PolicyEvent { PolicyOp op; std::string name; };
struct PolicyAudit { bool valid; std::size_t event; std::vector<std::string> granted; std::string reason; };
PolicyAudit audit_access_policy(const std::vector<PolicyEvent>& events);
}
''',
        r'''#include "task.h"
namespace curriculum {
PolicyAudit audit_access_policy(const std::vector<PolicyEvent>& events) {
 std::vector<PolicyOp> modes; std::vector<std::string> granted;
 for (std::size_t i=0;i<events.size();++i) { const auto& e=events[i];
  if (e.op!=PolicyOp::leave && e.name.empty()) return {false,i,granted,"empty name"};
  if (e.op==PolicyOp::enter_allow) { for (auto m:modes) if (m==PolicyOp::enter_deny) return {false,i,granted,"allow below deny"}; modes.push_back(e.op); }
  else if (e.op==PolicyOp::enter_deny) modes.push_back(e.op);
  else if (e.op==PolicyOp::leave) { if (modes.empty()) return {false,i,granted,"leave without scope"}; modes.pop_back(); }
  else if (!modes.empty() && modes.back()==PolicyOp::enter_allow) granted.push_back(e.name);
 }
 return {true,events.size(),granted,""};
}
}
''',
        r'''#include "task.h"
int main(){using namespace curriculum;auto r=audit_access_policy({{PolicyOp::enter_allow,"team"},{PolicyOp::request,"read"},{PolicyOp::enter_deny,"secret"},{PolicyOp::request,"write"},{PolicyOp::leave,""},{PolicyOp::leave,""}});return !(r.valid&&r.granted==std::vector<std::string>{"read"});}
''',
        r'''#include "task.h"
int main(){using namespace curriculum;auto a=audit_access_policy({{PolicyOp::enter_deny,"x"},{PolicyOp::enter_allow,"y"}});auto b=audit_access_policy({{PolicyOp::leave,""}});auto c=audit_access_policy({{PolicyOp::request,"r"}});return !(!a.valid&&a.event==1U&&!b.valid&&c.valid&&c.granted.empty());}
''', "negative-flat-policy"),
    _case(
        "nest-build-directives-v2", "nest-build-directives", "Build directive resolver", "conditional-frames",
        "Resolve nested conditional directives against a symbol set.",
        "Lines beginning `#if NAME`, `#else`, and `#endif` control emission. A symbol is true when listed in `symbols`. Each frame remembers its parent activity and permits one else. Ordinary lines are emitted only when every enclosing branch is active. Malformed directives, duplicate else, unmatched endif, and unclosed frames fail at the first line.",
        r'''#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct DirectiveResult { bool valid; std::size_t line; std::vector<std::string> active_lines; std::string reason; }; DirectiveResult resolve_build_directives(const std::vector<std::string>& lines,const std::vector<std::string>& symbols); }
''',
        r'''#include "task.h"
#include <algorithm>
namespace curriculum { DirectiveResult resolve_build_directives(const std::vector<std::string>& lines,const std::vector<std::string>& symbols){struct Frame{bool parent,cond,other;};std::vector<Frame> st;std::vector<std::string> out;bool active=true;for(std::size_t i=0;i<lines.size();++i){const auto& s=lines[i];if(s.rfind("#if ",0)==0){auto n=s.substr(4);if(n.empty())return{false,i,out,"empty symbol"};bool c=std::find(symbols.begin(),symbols.end(),n)!=symbols.end();st.push_back({active,c,false});active=active&&c;}else if(s=="#else"){if(st.empty()||st.back().other)return{false,i,out,"invalid else"};st.back().other=true;active=st.back().parent&&!st.back().cond;}else if(s=="#endif"){if(st.empty())return{false,i,out,"unexpected endif"};auto f=st.back();st.pop_back();active=f.parent;}else if(s.rfind("#",0)==0)return{false,i,out,"unknown directive"};else if(active)out.push_back(s);}if(!st.empty())return{false,lines.size(),out,"unclosed if"};return{true,lines.size(),out,""};} }
''',
        r'''#include "task.h"
int main(){auto r=curriculum::resolve_build_directives({"a","#if X","x","#else","y","#endif","z"},{"X"});return !(r.valid&&r.active_lines==std::vector<std::string>{"a","x","z"});}
''',
        r'''#include "task.h"
int main(){auto a=curriculum::resolve_build_directives({"#if X","#if Y","bad","#else","good","#endif","#endif"},{"X"});auto b=curriculum::resolve_build_directives({"#else"},{});auto c=curriculum::resolve_build_directives({"#if X","#else","#else"},{});return !(a.valid&&a.active_lines==std::vector<std::string>{"good"}&&!b.valid&&!c.valid);}
''', "negative-toggle-only"),
    _case(
        "nest-chat-quotes-v2", "nest-chat-quotes", "Chat quote audit", "line-depth-fence",
        "Audit line quote depth while ignoring fenced snippets.",
        "Outside triple-backtick fences, the number of leading `>` bytes is quote depth and one following space is stripped from the body. Depth may rise by at most one and may fall freely. Fence marker lines and fenced content produce no bodies. An unclosed fence or depth jump is invalid; bodies and maximum depth are returned in source order.",
        r'''#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct QuoteAudit { bool valid; std::size_t line; std::size_t max_depth; std::vector<std::string> bodies; std::string reason; }; QuoteAudit audit_chat_quotes(const std::vector<std::string>& lines); }
''',
        r'''#include "task.h"
#include <algorithm>
namespace curriculum { QuoteAudit audit_chat_quotes(const std::vector<std::string>& lines){bool fence=false;std::size_t prior=0,maxd=0;std::vector<std::string>b;for(std::size_t i=0;i<lines.size();++i){if(lines[i].rfind("```",0)==0){fence=!fence;continue;}if(fence)continue;std::size_t d=0;while(d<lines[i].size()&&lines[i][d]=='>')++d;if(d>prior+1U)return{false,i,maxd,b,"depth jump"};std::size_t p=d;if(p<lines[i].size()&&lines[i][p]==' ')++p;b.push_back(lines[i].substr(p));prior=d;maxd=std::max(maxd,d);}if(fence)return{false,lines.size(),maxd,b,"unclosed fence"};return{true,lines.size(),maxd,b,""};} }
''',
        r'''#include "task.h"
int main(){auto r=curriculum::audit_chat_quotes({"> a",">> b","```cpp",">>>> literal","```","plain"});return !(r.valid&&r.max_depth==2U&&r.bodies==std::vector<std::string>{"a","b","plain"});}
''',
        r'''#include "task.h"
int main(){auto a=curriculum::audit_chat_quotes({">>> jump"});auto b=curriculum::audit_chat_quotes({"> a","plain"});auto c=curriculum::audit_chat_quotes({"```"});return !(!a.valid&&b.valid&&!c.valid);}
''', "negative-count-all-markers"),
    _case(
        "nest-code-fences-v2", "nest-code-fences", "Code fence extraction", "fence-length-language",
        "Extract code blocks with compatible marker, length, and language rules.",
        "An opening line starts with at least three identical backticks or tildes followed by an optional alphanumeric language. A closing line contains only the same marker byte repeated at least the opening length. Short or different fence-looking lines inside a block are code. Return blocks in order; malformed labels and unclosed blocks fail.",
        r'''#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct CodeBlock { std::string language; std::vector<std::string> lines; }; struct FenceResult { bool valid; std::size_t line; std::vector<CodeBlock> blocks; std::string reason; }; FenceResult extract_code_fences(const std::vector<std::string>& lines); }
''',
        r'''#include "task.h"
#include <cctype>
namespace curriculum { FenceResult extract_code_fences(const std::vector<std::string>& lines){char mark=0;std::size_t need=0;CodeBlock cur;std::vector<CodeBlock>out;for(std::size_t i=0;i<lines.size();++i){const auto&s=lines[i];if(!mark){if(s.empty()||(s[0]!='`'&&s[0]!='~'))continue;std::size_t n=0;while(n<s.size()&&s[n]==s[0])++n;if(n<3U)continue;for(std::size_t j=n;j<s.size();++j)if(!std::isalnum(static_cast<unsigned char>(s[j])))return{false,i,out,"bad language"};mark=s[0];need=n;cur={s.substr(n),{}};}else{std::size_t n=0;while(n<s.size()&&s[n]==mark)++n;if(n>=need&&n==s.size()){out.push_back(cur);cur={};mark=0;need=0;}else cur.lines.push_back(s);}}if(mark)return{false,lines.size(),out,"unclosed fence"};return{true,lines.size(),out,""};} }
''',
        r'''#include "task.h"
int main(){auto r=curriculum::extract_code_fences({"````cpp","x","```","````","~~~","y","~~~~"});return !(r.valid&&r.blocks.size()==2U&&r.blocks[0].lines==std::vector<std::string>{"x","```"});}
''',
        r'''#include "task.h"
int main(){auto a=curriculum::extract_code_fences({"```c++","```"});auto b=curriculum::extract_code_fences({"~~~txt","x"});auto c=curriculum::extract_code_fences({"~~~","x","~~~~"});return !(!a.valid&&!b.valid&&c.valid);}
''', "negative-triple-toggle"),
    _case(
        "nest-command-blocks-v2", "nest-command-blocks", "Command transaction audit", "labeled-events",
        "Validate labeled command transactions and return execution order.",
        "`begin` pushes a nonempty label that is not already active. `run` must name the current label and records it. `end` must match the current label, removes it, and records `end:LABEL`. Any absent, mismatched, duplicate-active, or unclosed block is invalid at its first event.",
        r'''#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { enum class CommandOp { begin, run, end }; struct CommandEvent { CommandOp op; std::string label; }; struct CommandResult { bool valid; std::size_t event; std::vector<std::string> execution; std::string reason; }; CommandResult validate_command_blocks(const std::vector<CommandEvent>& events); }
''',
        r'''#include "task.h"
#include <algorithm>
namespace curriculum { CommandResult validate_command_blocks(const std::vector<CommandEvent>& events){std::vector<std::string>st,out;for(std::size_t i=0;i<events.size();++i){const auto&e=events[i];if(e.label.empty())return{false,i,out,"empty label"};if(e.op==CommandOp::begin){if(std::find(st.begin(),st.end(),e.label)!=st.end())return{false,i,out,"duplicate active label"};st.push_back(e.label);}else if(st.empty()||st.back()!=e.label)return{false,i,out,"label mismatch"};else if(e.op==CommandOp::run)out.push_back(e.label);else{out.push_back("end:"+e.label);st.pop_back();}}if(!st.empty())return{false,events.size(),out,"unclosed block"};return{true,events.size(),out,""};} }
''',
        r'''#include "task.h"
int main(){using namespace curriculum;auto r=validate_command_blocks({{CommandOp::begin,"a"},{CommandOp::begin,"b"},{CommandOp::run,"b"},{CommandOp::end,"b"},{CommandOp::end,"a"}});return !(r.valid&&r.execution==std::vector<std::string>{"b","end:b","end:a"});}
''',
        r'''#include "task.h"
int main(){using namespace curriculum;auto a=validate_command_blocks({{CommandOp::begin,"a"},{CommandOp::run,"b"}});auto b=validate_command_blocks({{CommandOp::begin,"a"},{CommandOp::begin,"a"}});return !(!a.valid&&!b.valid);}
''', "negative-ignore-labels"),
    _case(
        "nest-config-sections-v2", "nest-config-sections", "Configuration section parser", "section-path-keys",
        "Build canonical section paths and reject duplicate keys per section.",
        "Trim records. `begin NAME` enters an identifier section, `end NAME` must match it, and `KEY=VALUE` emits an entry at the slash-joined current path. Blank and `#` comment lines are ignored. Keys are unique within one path but may repeat elsewhere. Bad identifiers, malformed records, mismatched ends, duplicates, and unclosed sections fail first.",
        r'''#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct SectionEntry { std::string path,key,value; }; struct SectionResult { bool valid; std::size_t line; std::vector<SectionEntry> entries; std::string reason; }; SectionResult parse_config_sections(const std::vector<std::string>& lines); }
''',
        r'''#include "task.h"
#include <algorithm>
#include <cctype>
#include <set>
namespace curriculum { static std::string trim(std::string s){while(!s.empty()&&std::isspace(static_cast<unsigned char>(s.front())))s.erase(s.begin());while(!s.empty()&&std::isspace(static_cast<unsigned char>(s.back())))s.pop_back();return s;}static bool ident(const std::string&s){return !s.empty()&&std::all_of(s.begin(),s.end(),[](unsigned char c){return std::isalnum(c)||c=='_'||c=='-';});}SectionResult parse_config_sections(const std::vector<std::string>& lines){std::vector<std::string>st;std::set<std::string>keys;std::vector<SectionEntry>out;for(std::size_t i=0;i<lines.size();++i){auto s=trim(lines[i]);if(s.empty()||s[0]=='#')continue;if(s.rfind("begin ",0)==0){auto n=trim(s.substr(6));if(!ident(n))return{false,i,out,"bad section"};st.push_back(n);}else if(s.rfind("end ",0)==0){auto n=trim(s.substr(4));if(st.empty()||st.back()!=n)return{false,i,out,"bad end"};st.pop_back();}else{auto p=s.find('=');auto k=trim(s.substr(0,p));if(p==std::string::npos||!ident(k))return{false,i,out,"bad entry"};std::string path;for(const auto&n:st){if(!path.empty())path+='/';path+=n;}auto key=path+"\n"+k;if(!keys.insert(key).second)return{false,i,out,"duplicate key"};out.push_back({path,k,trim(s.substr(p+1))});}}if(!st.empty())return{false,lines.size(),out,"unclosed section"};return{true,lines.size(),out,""};} }
''',
        r'''#include "task.h"
int main(){auto r=curriculum::parse_config_sections({"begin app","x=1","begin child","x=2","end child","end app"});return !(r.valid&&r.entries.size()==2U&&r.entries[1].path=="app/child");}
''',
        r'''#include "task.h"
int main(){auto a=curriculum::parse_config_sections({"begin a","x=1","x=2","end a"});auto b=curriculum::parse_config_sections({"begin a","end b"});auto c=curriculum::parse_config_sections({"begin a","begin b","x=1","end b","end a"});return !(!a.valid&&!b.valid&&c.valid);}
''', "negative-global-key-set"),
    _case(
        "nest-diagram-groups-v2", "nest-diagram-groups", "Diagram group resolver", "ancestor-references",
        "Resolve references only to currently open ancestor drawing groups.",
        "`open` pushes a globally unique nonempty ID. `reference` must name an ID in the current ancestor stack and emits the path through that ancestor. `close` must match the current ID. Duplicate opens, sibling/historical references, mismatched closes, and remaining groups fail first.",
        r'''#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { enum class DiagramOp { open, reference, close }; struct DiagramEvent { DiagramOp op; std::string id; }; struct DiagramResult { bool valid; std::size_t event; std::vector<std::string> resolved_paths; std::string reason; }; DiagramResult resolve_diagram_groups(const std::vector<DiagramEvent>& events); }
''',
        r'''#include "task.h"
#include <algorithm>
#include <set>
namespace curriculum { DiagramResult resolve_diagram_groups(const std::vector<DiagramEvent>& events){std::vector<std::string>st,out;std::set<std::string>seen;for(std::size_t i=0;i<events.size();++i){const auto&e=events[i];if(e.id.empty())return{false,i,out,"empty id"};if(e.op==DiagramOp::open){if(!seen.insert(e.id).second)return{false,i,out,"duplicate id"};st.push_back(e.id);}else if(e.op==DiagramOp::close){if(st.empty()||st.back()!=e.id)return{false,i,out,"bad close"};st.pop_back();}else{auto p=std::find(st.begin(),st.end(),e.id);if(p==st.end())return{false,i,out,"reference not ancestor"};std::string path;for(auto it=st.begin();it!=p+1;++it){if(!path.empty())path+='/';path+=*it;}out.push_back(path);}}if(!st.empty())return{false,events.size(),out,"unclosed group"};return{true,events.size(),out,""};} }
''',
        r'''#include "task.h"
int main(){using namespace curriculum;auto r=resolve_diagram_groups({{DiagramOp::open,"a"},{DiagramOp::open,"b"},{DiagramOp::reference,"a"},{DiagramOp::close,"b"},{DiagramOp::close,"a"}});return !(r.valid&&r.resolved_paths==std::vector<std::string>{"a"});}
''',
        r'''#include "task.h"
int main(){using namespace curriculum;auto a=resolve_diagram_groups({{DiagramOp::open,"a"},{DiagramOp::close,"a"},{DiagramOp::open,"b"},{DiagramOp::reference,"a"}});auto b=resolve_diagram_groups({{DiagramOp::open,"a"},{DiagramOp::open,"a"}});return !(!a.valid&&!b.valid);}
''', "negative-history-reference"),
    _case(
        "nest-json-stream-v2", "nest-json-stream", "Incremental JSON structure", "incremental-json-state",
        "Maintain JSON container and string lexical state across chunks.",
        "`consume` processes bytes without retaining the full source. It tracks object/array closures, strings and escapes across chunk boundaries, one top-level value, absolute offsets, and sticky errors. Non-whitespace after completion is invalid. `finish` reports complete only for a closed value; empty input is valid but incomplete.",
        r'''#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct JsonProgress { bool valid,complete; std::size_t absolute_offset,depth; std::string reason; }; class JsonStreamValidator { public: JsonProgress consume(const std::string& chunk); JsonProgress finish(); private: std::vector<char> stack_; bool in_string_=false,escape_=false,started_=false,complete_=false,error_=false; std::size_t offset_=0; std::string reason_; JsonProgress state() const; }; }
''',
        r'''#include "task.h"
#include <cctype>
namespace curriculum { JsonProgress JsonStreamValidator::state()const{return{!error_,complete_&&!in_string_&&stack_.empty(),offset_,stack_.size(),reason_};}JsonProgress JsonStreamValidator::consume(const std::string& chunk){if(error_)return state();for(char c:chunk){const auto here=offset_++;if(complete_){if(!std::isspace(static_cast<unsigned char>(c))){error_=true;reason_="trailing data at "+std::to_string(here);}continue;}if(in_string_){if(escape_)escape_=false;else if(c=='\\')escape_=true;else if(c=='\"')in_string_=false;continue;}if(c=='\"'){started_=true;in_string_=true;}else if(c=='{'||c=='['){started_=true;stack_.push_back(c);}else if(c=='}'||c==']'){if(stack_.empty()||((c=='}'&&stack_.back()!='{')||(c==']'&&stack_.back()!='['))){error_=true;reason_="mismatched closer at "+std::to_string(here);}else stack_.pop_back();}else if(!std::isspace(static_cast<unsigned char>(c)))started_=true;if(started_&&!in_string_&&stack_.empty()&&!error_)complete_=true;}return state();}JsonProgress JsonStreamValidator::finish(){if(!error_&&(!started_||in_string_||!stack_.empty()))reason_=!started_?"incomplete value":"unclosed value";return state();} }
''',
        r'''#include "task.h"
int main(){curriculum::JsonStreamValidator v;auto a=v.consume("{\"x\":\"");auto b=v.consume("a\\\"");auto c=v.consume("b\"}");return !(!a.complete&&!b.complete&&c.valid&&c.complete&&c.depth==0U);}
''',
        r'''#include "task.h"
int main(){curriculum::JsonStreamValidator a;a.consume("{");auto x=a.finish();curriculum::JsonStreamValidator b;b.consume("{]");auto y=b.consume("{}");curriculum::JsonStreamValidator c;auto z=c.finish();return !(!x.complete&&!y.valid&&!z.complete&&z.valid);}
''', "negative-reset-each-chunk"),
    _case(
        "nest-legal-clauses-v2", "nest-legal-clauses", "Legal clause succession", "numeric-hierarchy",
        "Validate numeric clause parentage and sibling succession.",
        "Clause numbers are dot-separated positive integers. Every non-root clause requires an already seen immediate parent, the first child is 1, and later siblings under the same parent increment by one. Root clauses follow the same succession. Duplicates, gaps, zero, malformed or overflowing components fail first; canonical numbers retain input order.",
        r'''#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct ClauseResult { bool valid; std::size_t index; std::vector<std::string> canonical; std::string reason; }; ClauseResult validate_clause_numbers(const std::vector<std::string>& numbers); }
''',
        r'''#include "task.h"
#include <limits>
#include <map>
#include <set>
namespace curriculum { ClauseResult validate_clause_numbers(const std::vector<std::string>& numbers){std::set<std::string>seen;std::map<std::string,unsigned long long>next;std::vector<std::string>out;for(std::size_t i=0;i<numbers.size();++i){const auto&s=numbers[i];std::vector<unsigned long long>parts;std::size_t p=0;while(p<s.size()){std::size_t q=s.find('.',p);auto t=s.substr(p,q==std::string::npos?s.size()-p:q-p);if(t.empty())return{false,i,out,"bad component"};unsigned long long v=0;for(char c:t){if(c<'0'||c>'9'||v>(std::numeric_limits<unsigned long long>::max()-static_cast<unsigned>(c-'0'))/10U)return{false,i,out,"bad component"};v=v*10U+static_cast<unsigned>(c-'0');}if(v==0)return{false,i,out,"zero component"};parts.push_back(v);if(q==std::string::npos)break;p=q+1;}auto dot=s.rfind('.');std::string parent=dot==std::string::npos?"":s.substr(0,dot);if(!parent.empty()&&!seen.count(parent))return{false,i,out,"missing parent"};auto expected=next[parent]==0?1:next[parent];if(parts.back()!=expected)return{false,i,out,"sibling gap"};if(!seen.insert(s).second)return{false,i,out,"duplicate"};next[parent]=expected+1;out.push_back(s);}return{true,numbers.size(),out,""};} }
''',
        r'''#include "task.h"
int main(){auto r=curriculum::validate_clause_numbers({"1","1.1","1.2","2","2.1"});return !(r.valid&&r.canonical.size()==5U);}
''',
        r'''#include "task.h"
int main(){auto a=curriculum::validate_clause_numbers({"1.1"});auto b=curriculum::validate_clause_numbers({"1","1.2"});auto c=curriculum::validate_clause_numbers({"1","1.1","2"});return !(!a.valid&&!b.valid&&c.valid);}
''', "negative-lexicographic-only"),
    _case(
        "nest-markdown-links-v2", "nest-markdown-links", "Markdown link spans", "link-span-parser",
        "Extract link labels and nested destinations with exact spans.",
        "Recognize `[label](destination)`. Backslash escapes the following byte in labels and destinations; labels cannot nest, while destination parentheses may nest. Empty label/destination and malformed initiated links fail at their first byte. Ordinary text and standalone brackets are ignored. Return half-open source spans in order.",
        r'''#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct LinkSpan { std::string label,destination; std::size_t begin,end; }; struct LinkResult { bool valid; std::size_t offset; std::vector<LinkSpan> links; std::string reason; }; LinkResult extract_markdown_links(const std::string& source); }
''',
        r'''#include "task.h"
namespace curriculum { LinkResult extract_markdown_links(const std::string&s){std::vector<LinkSpan>out;for(std::size_t i=0;i<s.size();++i){if(s[i]!='['|| (i&&s[i-1]=='\\'))continue;auto begin=i;std::string label;bool esc=false;std::size_t j=i+1;for(;j<s.size();++j){char c=s[j];if(esc){label+=c;esc=false;}else if(c=='\\')esc=true;else if(c==']')break;else if(c=='[')return{false,begin,out,"nested label"};else label+=c;}if(j==s.size()||j+1>=s.size()||s[j+1]!='(')continue;if(label.empty())return{false,begin,out,"empty label"};std::string dest;int depth=1;esc=false;std::size_t k=j+2;for(;k<s.size()&&depth;++k){char c=s[k];if(esc){dest+=c;esc=false;}else if(c=='\\')esc=true;else if(c=='('){++depth;dest+=c;}else if(c==')'){--depth;if(depth)dest+=c;}else dest+=c;}if(depth||dest.empty())return{false,begin,out,"bad destination"};out.push_back({label,dest,begin,k});i=k-1;}return{true,s.size(),out,""};} }
''',
        r'''#include "task.h"
int main(){auto r=curriculum::extract_markdown_links("see [a](x(y)) and [b](z)");return !(r.valid&&r.links.size()==2U&&r.links[0].destination=="x(y)");}
''',
        r'''#include "task.h"
int main(){auto a=curriculum::extract_markdown_links("[a](x\\)y)");auto b=curriculum::extract_markdown_links("[](x)");auto c=curriculum::extract_markdown_links("[a](x");return !(a.valid&&a.links[0].destination=="x)y"&&!b.valid&&!c.valid);}
''', "negative-flat-regex"),
    _case(
        "nest-math-expressions-v2", "nest-math-expressions", "Expression evaluator", "precedence-evaluator",
        "Evaluate arithmetic expressions with precedence, unary signs, and scientific notation.",
        "Accept finite decimal/scientific numbers, parentheses, binary `+ - * /`, and unary `+/-` where an operand is expected. Multiplication/division bind above addition/subtraction and binary operators are left associative. Return canonical postfix tokens and the value. Empty input, bad exponent/token placement, mismatch, division by zero, and nonfinite results fail first.",
        r'''#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct ExpressionResult { bool valid; std::size_t offset; double value; std::vector<std::string> postfix; std::string reason; }; ExpressionResult evaluate_expression(const std::string& source); }
''',
        r'''#include "task.h"
#include <cmath>
#include <cstdlib>
#include <stack>
namespace curriculum { static int prec(char c){return(c=='*'||c=='/')?2:1;}ExpressionResult evaluate_expression(const std::string&s){std::vector<std::string>out;std::vector<char>ops;bool need=true;for(std::size_t i=0;i<s.size();){if(s[i]==' '){++i;continue;}if(need&&(s[i]=='+'||s[i]=='-')){std::size_t j=i+1;while(j<s.size()&&s[j]==' ')++j;if(j<s.size()&&s[j]=='('){if(s[i]=='-'){out.push_back("0");while(!ops.empty()&&ops.back()!='('&&prec(ops.back())>=prec('-')){out.push_back(std::string(1,ops.back()));ops.pop_back();}ops.push_back('-');}++i;continue;}}if((s[i]>='0'&&s[i]<='9')||s[i]=='.'||(need&&(s[i]=='+'||s[i]=='-'))){char*e=nullptr;double v=std::strtod(s.c_str()+i,&e);if(e==s.c_str()+i||!std::isfinite(v))return{false,i,0,out,"bad number"};std::size_t n=static_cast<std::size_t>(e-s.c_str());out.push_back(s.substr(i,n-i));i=n;need=false;continue;}char c=s[i];if(c=='('&&need){ops.push_back(c);++i;}else if(c==')'&&!need){while(!ops.empty()&&ops.back()!='('){out.push_back(std::string(1,ops.back()));ops.pop_back();}if(ops.empty())return{false,i,0,out,"mismatch"};ops.pop_back();++i;need=false;}else if((c=='+'||c=='-'||c=='*'||c=='/')&&!need){while(!ops.empty()&&ops.back()!='('&&prec(ops.back())>=prec(c)){out.push_back(std::string(1,ops.back()));ops.pop_back();}ops.push_back(c);++i;need=true;}else return{false,i,0,out,"bad token"};}if(need||out.empty())return{false,s.size(),0,out,"missing operand"};while(!ops.empty()){if(ops.back()=='(')return{false,s.size(),0,out,"mismatch"};out.push_back(std::string(1,ops.back()));ops.pop_back();}std::vector<double>vs;for(const auto&t:out){if(t.size()==1&&std::string("+-*/").find(t[0])!=std::string::npos){if(vs.size()<2)return{false,s.size(),0,out,"missing operand"};double b=vs.back();vs.pop_back();double a=vs.back();vs.pop_back();if(t[0]=='/'&&b==0)return{false,s.size(),0,out,"divide by zero"};double v=t[0]=='+'?a+b:t[0]=='-'?a-b:t[0]=='*'?a*b:a/b;if(!std::isfinite(v))return{false,s.size(),0,out,"nonfinite"};vs.push_back(v);}else vs.push_back(std::strtod(t.c_str(),nullptr));}return{true,s.size(),vs.back(),out,""};} }
''',
        r'''#include "task.h"
#include <cmath>
int main(){auto r=curriculum::evaluate_expression("2+3*4-1e1");return !(r.valid&&std::fabs(r.value-4.0)<1e-9&&r.postfix.back()=="-");}
''',
        r'''#include "task.h"
#include <cmath>
int main(){auto a=curriculum::evaluate_expression("8/4/2");auto b=curriculum::evaluate_expression("-(2+3)*2");auto c=curriculum::evaluate_expression("1/0");return !(a.valid&&std::fabs(a.value-1.0)<1e-9&&b.valid&&std::fabs(b.value+10.0)<1e-9&&!c.valid);}
''', "negative-left-to-right"),
    _case(
        "nest-protocol-frames-v2", "nest-protocol-frames", "Binary frame decoder", "binary-length-boundaries",
        "Decode nested length-delimited binary frames with exact boundaries.",
        "Each frame has one type byte and a big-endian 16-bit payload length. A type with bit 7 set contains only child frames; another type has opaque payload. Container payload must be nonempty and child frames must exactly fill it. Return preorder records with offset, payload size, and depth. Truncation, overflow, boundary mismatch, or depth beyond 64 fails first.",
        r'''#pragma once
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>
namespace curriculum { struct FrameRecord { std::uint8_t type; std::size_t offset,payload_size,depth; }; struct FrameResult { bool valid; std::size_t offset; std::vector<FrameRecord> preorder; std::string reason; }; FrameResult decode_frames(const std::vector<std::uint8_t>& bytes); }
''',
        r'''#include "task.h"
namespace curriculum { static bool parse(const std::vector<std::uint8_t>&b,std::size_t&pos,std::size_t end,std::size_t d,std::vector<FrameRecord>&out,std::size_t&bad){if(d>64||end-pos<3){bad=pos;return false;}auto at=pos;auto type=b[pos++];auto hi=b[pos++];auto lo=b[pos++];std::size_t n=static_cast<std::size_t>(hi)*256U+lo;if(n>end-pos){bad=at;return false;}auto stop=pos+n;out.push_back({type,at,n,d});if(type&0x80U){if(n==0){bad=at;return false;}while(pos<stop)if(!parse(b,pos,stop,d+1,out,bad))return false;}else pos=stop;if(pos!=stop){bad=pos;return false;}return true;}FrameResult decode_frames(const std::vector<std::uint8_t>&b){std::vector<FrameRecord>out;std::size_t p=0,bad=0;while(p<b.size())if(!parse(b,p,b.size(),0,out,bad))return{false,bad,out,"invalid frame"};return{true,b.size(),out,""};} }
''',
        r'''#include "task.h"
int main(){std::vector<std::uint8_t>b={0x80,0,4,1,0,1,9};auto r=curriculum::decode_frames(b);return !(r.valid&&r.preorder.size()==2U&&r.preorder[1].depth==1U);}
''',
        r'''#include "task.h"
int main(){auto a=curriculum::decode_frames({1,0,2,9});auto b=curriculum::decode_frames({0x80,0,0});auto c=curriculum::decode_frames({1,0,3,0x80,0,0});return !(!a.valid&&!b.valid&&c.valid&&c.preorder.size()==1U);}
''', "negative-ignore-length"),
    _case(
        "nest-query-groups-v2", "nest-query-groups", "Boolean query parser", "boolean-precedence",
        "Parse boolean query grammar into canonical postfix.",
        "Identifiers contain letters, digits, `_` or `-`. Operators are uppercase `NOT`, `AND`, and `OR` with precedence NOT > AND > OR; NOT is unary. Parentheses group expressions and `#` begins a comment through end of input. Missing operands/operators, adjacent identifiers, mismatched groups, or unknown bytes fail at the first offset.",
        r'''#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct QueryResult { bool valid; std::size_t offset; std::vector<std::string> postfix; std::size_t operands; std::string reason; }; QueryResult parse_boolean_query(const std::string& source); }
''',
        r'''#include "task.h"
#include <cctype>
namespace curriculum { static int qp(const std::string&o){return o=="NOT"?3:o=="AND"?2:1;}QueryResult parse_boolean_query(const std::string&s){std::vector<std::string>out,ops;bool need=true;std::size_t count=0;for(std::size_t i=0;i<s.size();){if(s[i]=='#')break;if(std::isspace(static_cast<unsigned char>(s[i]))){++i;continue;}if(s[i]=='('&&need){ops.push_back("(");++i;continue;}if(s[i]==')'&&!need){while(!ops.empty()&&ops.back()!="("){out.push_back(ops.back());ops.pop_back();}if(ops.empty())return{false,i,out,count,"mismatch"};ops.pop_back();++i;need=false;continue;}if(std::isalnum(static_cast<unsigned char>(s[i]))||s[i]=='_'||s[i]=='-'){std::size_t j=i;while(j<s.size()&&(std::isalnum(static_cast<unsigned char>(s[j]))||s[j]=='_'||s[j]=='-'))++j;auto t=s.substr(i,j-i);bool op=t=="NOT"||t=="AND"||t=="OR";if(t=="NOT"&&need){ops.push_back(t);}else if((t=="AND"||t=="OR")&&!need){while(!ops.empty()&&ops.back()!="("&&qp(ops.back())>=qp(t)){out.push_back(ops.back());ops.pop_back();}ops.push_back(t);need=true;}else if(!op&&need){out.push_back(t);++count;need=false;while(!ops.empty()&&ops.back()=="NOT"){out.push_back("NOT");ops.pop_back();}}else return{false,i,out,count,"operator placement"};i=j;continue;}return{false,i,out,count,"unknown byte"};}if(need||count==0)return{false,s.size(),out,count,"missing operand"};while(!ops.empty()){if(ops.back()=="(")return{false,s.size(),out,count,"mismatch"};out.push_back(ops.back());ops.pop_back();}return{true,s.size(),out,count,""};} }
''',
        r'''#include "task.h"
int main(){auto r=curriculum::parse_boolean_query("a OR b AND NOT c");return !(r.valid&&r.postfix==std::vector<std::string>{"a","b","c","NOT","AND","OR"}&&r.operands==3U);}
''',
        r'''#include "task.h"
int main(){auto a=curriculum::parse_boolean_query("(a OR b) AND c # tail");auto b=curriculum::parse_boolean_query("a b");auto c=curriculum::parse_boolean_query("AND a");return !(a.valid&&!b.valid&&!c.valid);}
''', "negative-equal-precedence"),
    _case(
        "nest-recipe-steps-v2", "nest-recipe-steps", "Recipe step tree", "indentation-lifecycle",
        "Construct preparation paths from indentation and explicit done records.",
        "Records are `step NAME` or `done NAME` after a multiple of two leading spaces. A step may be at the current depth or one deeper, never skip a level. `done` uses the current step indentation and matches it. Sibling names are unique only under the same parent. Blank lines are ignored; malformed indentation, duplicate siblings, bad done, or unclosed steps fail first.",
        r'''#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct RecipeNode { std::string path; std::size_t line; }; struct RecipeResult { bool valid; std::size_t line; std::vector<RecipeNode> preorder; std::string reason; }; RecipeResult parse_recipe_steps(const std::vector<std::string>& lines); }
''',
        r'''#include "task.h"
#include <map>
#include <set>
namespace curriculum { RecipeResult parse_recipe_steps(const std::vector<std::string>&lines){std::vector<std::string>st;std::map<std::string,std::set<std::string>>kids;std::vector<RecipeNode>out;for(std::size_t i=0;i<lines.size();++i){const auto&s=lines[i];if(s.empty())continue;std::size_t spaces=0;while(spaces<s.size()&&s[spaces]==' ')++spaces;if(spaces%2)return{false,i,out,"odd indentation"};auto d=spaces/2;auto text=s.substr(spaces);if(text.rfind("step ",0)==0){auto n=text.substr(5);if(n.empty()||d>st.size())return{false,i,out,"indentation gap"};while(st.size()>d)st.pop_back();std::string parent;for(const auto&x:st){if(!parent.empty())parent+='/';parent+=x;}if(!kids[parent].insert(n).second)return{false,i,out,"duplicate sibling"};st.push_back(n);std::string path=parent.empty()?n:parent+"/"+n;out.push_back({path,i});}else if(text.rfind("done ",0)==0){auto n=text.substr(5);if(st.empty()||d+1U!=st.size()||st.back()!=n)return{false,i,out,"bad done"};st.pop_back();}else return{false,i,out,"bad record"};}if(!st.empty())return{false,lines.size(),out,"unclosed step"};return{true,lines.size(),out,""};} }
''',
        r'''#include "task.h"
int main(){auto r=curriculum::parse_recipe_steps({"step prep","  step chop","  done chop","done prep"});return !(r.valid&&r.preorder[1].path=="prep/chop");}
''',
        r'''#include "task.h"
int main(){auto a=curriculum::parse_recipe_steps({"    step gap"});auto b=curriculum::parse_recipe_steps({"step a","done b"});auto c=curriculum::parse_recipe_steps({"step a","  step x","  done x","  step x","  done x","done a"});return !(!a.valid&&!b.valid&&!c.valid);}
''', "negative-ignore-indentation"),
    _case(
        "nest-regex-groups-v2", "nest-regex-groups", "Regex group classifier", "regex-lexical-groups",
        "Classify regex group openings while honoring escapes and character classes.",
        "Classify capturing `(`, noncapturing `(?:`, named `(?<name>`, and lookaround `(?=`/`(?!` groups. Parentheses inside character classes or after backslash are literal. Named groups are nonempty identifiers and unique. Unsupported `(?` prefixes, unexpected closes, unclosed groups/classes, and trailing escapes fail first.",
        r'''#pragma once
#include <cstddef>
#include <string>
namespace curriculum { struct RegexGroups { bool valid; std::size_t offset,capturing,noncapturing,named,lookaround,max_depth; std::string reason; }; RegexGroups inspect_regex_groups(const std::string& source); }
''',
        r'''#include "task.h"
#include <algorithm>
#include <set>
#include <vector>
namespace curriculum { RegexGroups inspect_regex_groups(const std::string&s){RegexGroups r{true,s.size(),0,0,0,0,0,""};std::vector<char>st;std::set<std::string>names;bool cls=false,esc=false;for(std::size_t i=0;i<s.size();++i){char c=s[i];if(esc){esc=false;continue;}if(c=='\\'){esc=true;continue;}if(cls){if(c==']')cls=false;continue;}if(c=='['){cls=true;continue;}if(c=='('){char kind='c';if(i+1<s.size()&&s[i+1]=='?'){if(i+2>=s.size())return{false,i,r.capturing,r.noncapturing,r.named,r.lookaround,r.max_depth,"bad group prefix"};char p=s[i+2];if(p==':'){++r.noncapturing;i+=2;kind='n';}else if(p=='='||p=='!'){++r.lookaround;i+=2;kind='l';}else if(p=='<'){auto e=s.find('>',i+3);if(e==std::string::npos||e==i+3)return{false,i,r.capturing,r.noncapturing,r.named,r.lookaround,r.max_depth,"bad name"};auto n=s.substr(i+3,e-i-3);if(!names.insert(n).second)return{false,i,r.capturing,r.noncapturing,r.named,r.lookaround,r.max_depth,"duplicate name"};++r.named;i=e;kind='m';}else return{false,i,r.capturing,r.noncapturing,r.named,r.lookaround,r.max_depth,"bad group prefix"};}else ++r.capturing;st.push_back(kind);r.max_depth=std::max(r.max_depth,st.size());}else if(c==')'){if(st.empty())return{false,i,r.capturing,r.noncapturing,r.named,r.lookaround,r.max_depth,"unexpected close"};st.pop_back();}}if(esc||cls||!st.empty())return{false,s.size(),r.capturing,r.noncapturing,r.named,r.lookaround,r.max_depth,"unclosed lexical state"};return r;} }
''',
        r'''#include "task.h"
int main(){auto r=curriculum::inspect_regex_groups("(a)(?:b)(?<id>c)(?=d)[()]");return !(r.valid&&r.capturing==1U&&r.noncapturing==1U&&r.named==1U&&r.lookaround==1U);}
''',
        r'''#include "task.h"
int main(){auto a=curriculum::inspect_regex_groups("\\([)]");auto b=curriculum::inspect_regex_groups("(?<x>a)(?<x>b)");auto c=curriculum::inspect_regex_groups("(?q)");return !(a.valid&&!b.valid&&!c.valid);}
''', "negative-paren-counter"),
    _case(
        "nest-rich-text-tags-v2", "nest-rich-text-tags", "Rich text tag audit", "tag-attribute-lexer",
        "Validate typed tags, quoted attributes, void tags, and source coordinates.",
        "Parse lowercase alphanumeric/hyphen opening and closing tags. Attributes are `name=\"value\"` with backslash escapes. A trailing `/` makes a self-closing tag; `br` and `img` are void even without it. Closing names match the current open tag. Return zero-based line/column and open names on the first malformed tag, mismatch, or unclosed input.",
        r'''#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct TagDiagnostic { bool valid; std::size_t line,column; std::vector<std::string> open_tags; std::string reason; }; TagDiagnostic validate_rich_text(const std::string& source); }
''',
        r'''#include "task.h"
#include <cctype>
namespace curriculum { static bool tn(char c){return std::islower(static_cast<unsigned char>(c))||std::isdigit(static_cast<unsigned char>(c))||c=='-';}TagDiagnostic validate_rich_text(const std::string&s){std::vector<std::string>st;std::size_t line=0,col=0;for(std::size_t i=0;i<s.size();){if(s[i]=='\n'){++line;col=0;++i;continue;}if(s[i]!='<'){++i;++col;continue;}auto el=line,ec=col;std::size_t j=i+1;bool close=j<s.size()&&s[j]=='/';if(close)++j;auto b=j;while(j<s.size()&&tn(s[j]))++j;if(j==b)return{false,el,ec,st,"bad tag name"};auto name=s.substr(b,j-b);bool quote=false,esc=false,self=false;for(;j<s.size()&&s[j]!='>'; ++j){char c=s[j];if(quote){if(esc)esc=false;else if(c=='\\')esc=true;else if(c=='\"')quote=false;}else if(c=='\"')quote=true;else if(c=='/'&&j+1<s.size()&&s[j+1]=='>')self=true;else if(!(std::isspace(static_cast<unsigned char>(c))||c=='='||tn(c)))return{false,el,ec,st,"bad attribute"};}if(j==s.size()||quote)return{false,el,ec,st,"unclosed tag"};if(close){if(self||st.empty()||st.back()!=name)return{false,el,ec,st,"tag mismatch"};st.pop_back();}else if(!self&&name!="br"&&name!="img")st.push_back(name);col+=j-i+1;i=j+1;}if(!st.empty())return{false,line,col,st,"unclosed tags"};return{true,line,col,{},""};} }
''',
        r'''#include "task.h"
int main(){auto r=curriculum::validate_rich_text("<panel id=\"a\\\"b\"><br><item/></panel>");return !r.valid;}
''',
        r'''#include "task.h"
int main(){auto a=curriculum::validate_rich_text("<a>\n</b>");auto b=curriculum::validate_rich_text("<a q=\"x>");auto c=curriculum::validate_rich_text("<img>");return !(!a.valid&&a.line==1U&&!b.valid&&c.valid);}
''', "negative-angle-counter"),
    _case(
        "nest-script-comments-v2", "nest-script-comments", "Nested comment stripper", "position-preserving-comments",
        "Strip nested block comments while preserving literals and source positions.",
        "Outside single/double quoted literals, `/*` opens and `*/` closes nested comments. Comment bytes become spaces, but newlines are preserved, so output length equals input length. Literals honor backslash escapes and remain unchanged. Unexpected close, unterminated comment, literal, or escape fails at the first relevant offset.",
        r'''#pragma once
#include <cstddef>
#include <string>
namespace curriculum { struct StripResult { bool valid; std::size_t offset; std::string text; std::size_t comments,max_depth; std::string reason; }; StripResult strip_nested_comments(const std::string& source); }
''',
        r'''#include "task.h"
#include <algorithm>
namespace curriculum { StripResult strip_nested_comments(const std::string&s){std::string out=s;std::size_t depth=0,count=0,maxd=0;char quote=0;bool esc=false;for(std::size_t i=0;i<s.size();++i){if(depth){if(i+1<s.size()&&s[i]=='/'&&s[i+1]=='*'){out[i]=out[i+1]=' ';++depth;++count;maxd=std::max(maxd,depth);++i;}else if(i+1<s.size()&&s[i]=='*'&&s[i+1]=='/'){out[i]=out[i+1]=' ';--depth;++i;}else if(s[i]!='\n')out[i]=' ';continue;}if(quote){if(esc)esc=false;else if(s[i]=='\\')esc=true;else if(s[i]==quote)quote=0;continue;}if(s[i]=='\''||s[i]=='\"'){quote=s[i];continue;}if(i+1<s.size()&&s[i]=='/'&&s[i+1]=='*'){out[i]=out[i+1]=' ';depth=1;++count;maxd=std::max(maxd,depth);++i;}else if(i+1<s.size()&&s[i]=='*'&&s[i+1]=='/')return{false,i,out,count,maxd,"unexpected close"};}if(depth||quote||esc)return{false,s.size(),out,count,maxd,"unterminated state"};return{true,s.size(),out,count,maxd,""};} }
''',
        r'''#include "task.h"
int main(){std::string s="a/* one /* two */ x\n*/\"/*keep*/\"";auto r=curriculum::strip_nested_comments(s);return !(r.valid&&r.text.size()==s.size()&&r.comments==2U&&r.max_depth==2U&&r.text.find("/*keep*/")!=std::string::npos);}
''',
        r'''#include "task.h"
int main(){auto a=curriculum::strip_nested_comments("*/");auto b=curriculum::strip_nested_comments("/*x");auto c=curriculum::strip_nested_comments("'/*'");return !(!a.valid&&!b.valid&&c.valid);}
''', "negative-first-close"),
    _case(
        "nest-spreadsheet-formulas-v2", "nest-spreadsheet-formulas", "Formula call audit", "formula-call-arity",
        "Validate locale-specific function arguments and report call arities.",
        "A formula begins `=`. An identifier followed by `(` opens a function call. Comma or semicolon is the configured separator; the other is invalid outside quoted strings. Each call needs at least one nonempty argument. Parentheses may group expressions. Return function calls in preorder with argument count and depth; empty/trailing arguments, mismatch, and unclosed strings fail first.",
        r'''#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct FunctionCall { std::string name; std::size_t arguments,depth; }; struct FormulaResult { bool valid; std::size_t offset; std::vector<FunctionCall> calls; std::string reason; }; FormulaResult inspect_formula(const std::string& source,char separator); }
''',
        r'''#include "task.h"
#include <cctype>
namespace curriculum { FormulaResult inspect_formula(const std::string&s,char sep){if((sep!=','&&sep!=';')||s.empty()||s[0]!='=')return{false,0,{},"bad formula"};struct F{std::size_t index,args;bool has;};std::vector<F>st;std::vector<FunctionCall>out;bool quote=false,esc=false;for(std::size_t i=1;i<s.size();++i){char c=s[i];if(quote){if(esc)esc=false;else if(c=='\\')esc=true;else if(c=='\"')quote=false;if(!st.empty())st.back().has=true;continue;}if(c=='\"'){quote=true;if(!st.empty())st.back().has=true;continue;}if(std::isalpha(static_cast<unsigned char>(c))||c=='_'){std::size_t j=i+1;while(j<s.size()&&(std::isalnum(static_cast<unsigned char>(s[j]))||s[j]=='_'))++j;auto name=s.substr(i,j-i);if(j<s.size()&&s[j]=='('){out.push_back({name,0,st.size()});st.push_back({out.size()-1,0,false});i=j;}else{if(!st.empty())st.back().has=true;i=j-1;}}else if(c==sep){if(st.empty()||!st.back().has)return{false,i,out,"empty argument"};++st.back().args;st.back().has=false;}else if((c==','||c==';')&&c!=sep)return{false,i,out,"wrong separator"};else if(c==')'){if(st.empty()||!st.back().has)return{false,i,out,"bad close"};out[st.back().index].arguments=st.back().args+1;st.pop_back();if(!st.empty())st.back().has=true;}else if(!std::isspace(static_cast<unsigned char>(c))&&c!='('&&c!='+'&&c!='-'&&c!='*'&&c!='/'){if(!std::isdigit(static_cast<unsigned char>(c))&&c!='.')return{false,i,out,"bad token"};if(!st.empty())st.back().has=true;}else if((std::isdigit(static_cast<unsigned char>(c))||c=='.')&&!st.empty())st.back().has=true;}if(quote||!st.empty())return{false,s.size(),out,"unclosed formula"};return{true,s.size(),out,""};} }
''',
        r'''#include "task.h"
int main(){auto r=curriculum::inspect_formula("=SUM(1;AVG(2;3);\"a,b\")",';');return !(r.valid&&r.calls.size()==2U&&r.calls[0].arguments==3U&&r.calls[1].arguments==2U);}
''',
        r'''#include "task.h"
int main(){auto a=curriculum::inspect_formula("=F(1,,2)",',');auto b=curriculum::inspect_formula("=F(1;2)",',');auto c=curriculum::inspect_formula("=F(\"a,b\",2)",',');return !(!a.valid&&!b.valid&&c.valid);}
''', "negative-global-split"),
    _case(
        "nest-template-placeholders-v2", "nest-template-placeholders", "Template placeholder tree", "placeholder-parent-spans",
        "Parse nested placeholders into parent-linked source-span records.",
        "A placeholder is `{{name}}` or `{{name|default}}`; names are identifiers and defaults may contain nested placeholders. Backslash escapes the following byte. Return records in opening/preorder order with half-open spans and parent index (`npos` at root). Empty/bad names, multiple frame separators, unexpected close, and unclosed frames fail first.",
        r'''#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { inline constexpr std::size_t no_parent=static_cast<std::size_t>(-1); struct Placeholder { std::string name,default_text; std::size_t parent,begin,end; }; struct TemplateResult { bool valid; std::size_t offset; std::vector<Placeholder> preorder; std::string reason; }; TemplateResult parse_placeholders(const std::string& source); }
''',
        r'''#include "task.h"
#include <cctype>
namespace curriculum { TemplateResult parse_placeholders(const std::string&s){struct F{std::size_t index,start,bar;};std::vector<F>st;std::vector<Placeholder>out;for(std::size_t i=0;i<s.size();++i){if(s[i]=='\\'){++i;continue;}if(i+1<s.size()&&s[i]=='{'&&s[i+1]=='{'){auto parent=st.empty()?no_parent:st.back().index;out.push_back({"","",parent,i,0});st.push_back({out.size()-1,i,no_parent});++i;}else if(i+1<s.size()&&s[i]=='}'&&s[i+1]=='}'){if(st.empty())return{false,i,out,"unexpected close"};auto f=st.back();st.pop_back();std::size_t ns=f.start+2,ne=f.bar==no_parent?i:f.bar;auto name=s.substr(ns,ne-ns);if(name.empty())return{false,f.start,out,"empty name"};for(char c:name)if(!(std::isalnum(static_cast<unsigned char>(c))||c=='_'))return{false,f.start,out,"bad name"};out[f.index].name=name;out[f.index].default_text=f.bar==no_parent?"":s.substr(f.bar+1,i-f.bar-1);out[f.index].end=i+2;++i;}else if(s[i]=='|'&&!st.empty()&&st.back().bar==no_parent)st.back().bar=i;else if(s[i]=='|'&&!st.empty()&&st.back().bar!=no_parent)return{false,i,out,"multiple separators"};}if(!st.empty())return{false,s.size(),out,"unclosed placeholder"};return{true,s.size(),out,""};} }
''',
        r'''#include "task.h"
int main(){auto r=curriculum::parse_placeholders("x{{name|before {{child}} after}}");return !(r.valid&&r.preorder.size()==2U&&r.preorder[0].parent==curriculum::no_parent&&r.preorder[1].parent==0U);}
''',
        r'''#include "task.h"
int main(){auto a=curriculum::parse_placeholders("{{|x}}");auto b=curriculum::parse_placeholders("{{a|b|c}}");auto c=curriculum::parse_placeholders("\\{{literal\\}}");return !(!a.valid&&!b.valid&&c.valid&&c.preorder.empty());}
''', "negative-flat-placeholder"),
    _case(
        "nest-workflow-scopes-v2", "nest-workflow-scopes", "Workflow lifecycle audit", "workflow-parent-lifecycle",
        "Validate workflow scope parentage and direct task completion before closure.",
        "`open` uses a globally unique nonempty ID and declares the current scope as parent (or empty at root). `complete_task` needs an active scope and a globally unique nonempty task ID. `close` must match the current scope and that scope must have at least one direct completed task. Return completed tasks in event order and unclosed scopes at end; the first invalid event does not mutate earlier state.",
        r'''#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { enum class WorkflowOp { open,complete_task,close }; struct WorkflowEvent { WorkflowOp op; std::string id,parent; }; struct WorkflowResult { bool valid; std::size_t event; std::vector<std::string> completed,remaining; std::string reason; }; WorkflowResult validate_workflow(const std::vector<WorkflowEvent>& events); }
''',
        r'''#include "task.h"
#include <set>
namespace curriculum { WorkflowResult validate_workflow(const std::vector<WorkflowEvent>&e){struct S{std::string id;std::size_t done;};std::vector<S>st;std::set<std::string>ids,tasks;std::vector<std::string>done;for(std::size_t i=0;i<e.size();++i){const auto&x=e[i];if(x.id.empty())return{false,i,done,{},"empty id"};if(x.op==WorkflowOp::open){auto parent=st.empty()?"":st.back().id;if(x.parent!=parent||!ids.insert(x.id).second)return{false,i,done,{},"bad parent or duplicate"};st.push_back({x.id,0});}else if(x.op==WorkflowOp::complete_task){if(st.empty()||!tasks.insert(x.id).second)return{false,i,done,{},"bad task"};++st.back().done;done.push_back(x.id);}else{if(st.empty()||st.back().id!=x.id||st.back().done==0)return{false,i,done,{},"bad close"};st.pop_back();}}std::vector<std::string>remain;for(const auto&s:st)remain.push_back(s.id);return{true,e.size(),done,remain,""};} }
''',
        r'''#include "task.h"
int main(){using namespace curriculum;auto r=validate_workflow({{WorkflowOp::open,"root",""},{WorkflowOp::complete_task,"a",""},{WorkflowOp::open,"child","root"},{WorkflowOp::complete_task,"b",""},{WorkflowOp::close,"child",""},{WorkflowOp::close,"root",""}});return !(r.valid&&r.completed==std::vector<std::string>{"a","b"});}
''',
        r'''#include "task.h"
int main(){using namespace curriculum;auto a=validate_workflow({{WorkflowOp::open,"a","wrong"}});auto b=validate_workflow({{WorkflowOp::open,"a",""},{WorkflowOp::close,"a",""}});auto c=validate_workflow({{WorkflowOp::open,"a",""},{WorkflowOp::complete_task,"x",""}});return !(!a.valid&&!b.valid&&c.valid&&c.remaining==std::vector<std::string>{"a"});}
''', "negative-global-task-count"),
)


if len(CASES) != 20 or len({case.kind for case in CASES}) != len(CASES):
    raise RuntimeError("nested-structure cases must contain 20 distinct mechanisms")
