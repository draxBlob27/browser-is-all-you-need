"""Declarative cases for the 110-root quoted and nested record expansion family.

The matrix is intentionally two-dimensional: every architecture owns a
different lexical/structural machine and every operation exposes a different
observable API and post-parse algorithm.  Neither axis is a domain-name or
constant-only variant.
"""

from __future__ import annotations

from dataclasses import dataclass
import json


@dataclass(frozen=True)
class Architecture:
    key: str
    title: str
    mechanism: str
    feed_decl: str
    valid_feed: str
    invalid_feed: str
    valid_count: int
    scanner: str
    boundary_rule: str


@dataclass(frozen=True)
class Operation:
    key: str
    title: str
    objective: str
    option_decl: str
    option_value: str
    result_field: str
    result_init: str
    reducer: str
    visible_predicate: str
    private_rule: str


@dataclass(frozen=True)
class Case:
    task_id: str
    title: str
    architecture: Architecture
    operation: Operation

    @property
    def mechanism(self) -> str:
        return f"{self.architecture.mechanism}+{self.operation.key}"


_CORE_DECL = r'''
struct CoreRecordState {
 bool valid = true;
 std::size_t offset = 0;
 std::vector<std::string> values;
 std::vector<std::size_t> depths;
 std::string reason;
};
'''


ARCHITECTURES: tuple[Architecture, ...] = (
    Architecture(
        "quoted-row", "Quoted delimiter row", "five-state quoted-field automaton",
        "struct Feed { std::string row; std::size_t required_fields; };",
        'Feed{R"(alpha,"beta,gamma",delta)" , 3U}',
        'Feed{R"(alpha,"unterminated,delta)" , 3U}',
        3,
        r'''
static CoreRecordState scan(const Feed& feed) {
 CoreRecordState out; std::string field; bool quoted=false, after_quote=false;
 for (std::size_t i=0;i<feed.row.size();++i) { char c=feed.row[i]; out.offset=i;
  if (quoted) { if (c=='"') { if (i+1<feed.row.size()&&feed.row[i+1]=='"') { field+='"'; ++i; } else { quoted=false; after_quote=true; } } else field+=c; }
  else if (after_quote) { if (c==',') { out.values.push_back(field); out.depths.push_back(1U); field.clear(); after_quote=false; } else { out.valid=false; out.reason="byte after quote"; return out; } }
  else if (c==',' ) { out.values.push_back(field); out.depths.push_back(0U); field.clear(); }
  else if (c=='"') { if (!field.empty()) { out.valid=false; out.reason="quote inside bare field"; return out; } quoted=true; }
  else field+=c;
 }
 if (quoted) { out.valid=false; out.offset=feed.row.size(); out.reason="unterminated quote"; return out; }
 out.values.push_back(field); out.depths.push_back(after_quote?1U:0U);
 if (out.values.size()!=feed.required_fields) { out.valid=false; out.reason="field count"; }
 return out;
}''',
        "A quote may open only at field start; doubled quotes decode once and bytes after a closing quote are rejected.",
    ),
    Architecture(
        "escaped-pipe", "Escaped pipe ledger", "escape-aware field transducer",
        "struct Feed { std::string bytes; char escape; bool forbid_empty; };",
        r'''Feed{R"(north|south\|annex|west)", '\\', true}''',
        r'''Feed{R"(north|dangling\)", '\\', true}''',
        3,
        r'''
static CoreRecordState scan(const Feed& feed) {
 CoreRecordState out; std::string field; bool escaped=false;
 for(std::size_t i=0;i<feed.bytes.size();++i){char c=feed.bytes[i];out.offset=i;
  if(escaped){field+=c;escaped=false;continue;} if(c==feed.escape){escaped=true;continue;}
  if(c=='|'){if(feed.forbid_empty&&field.empty()){out.valid=false;out.reason="empty field";return out;}out.values.push_back(field);out.depths.push_back(0U);field.clear();}else field+=c;
 }
 if(escaped){out.valid=false;out.offset=feed.bytes.size();out.reason="dangling escape";return out;}
 if(feed.forbid_empty&&field.empty()){out.valid=false;out.reason="empty final field";return out;}
 out.values.push_back(field);out.depths.push_back(0U);return out;
}''',
        "The escape consumes exactly the following byte, including a pipe or another escape; a terminal escape is invalid.",
    ),
    Architecture(
        "bracket-tree", "Bracketed record tree", "typed delimiter stack with quoted leaves",
        "struct Feed { std::string source; std::size_t maximum_depth; char leaf_separator; };",
        r'''Feed{R"([root,{"left,right",leaf},tail])", 4U, ','}''',
        r'''Feed{R"([root,{left],tail})", 4U, ','}''',
        4,
        r'''
static CoreRecordState scan(const Feed& feed) {
 CoreRecordState out;std::vector<char> stack;std::string atom;bool quote=false,escape=false;
 auto flush=[&](){if(!atom.empty()){out.values.push_back(atom);out.depths.push_back(stack.empty()?0U:stack.size()-1U);atom.clear();}};
 for(std::size_t i=0;i<feed.source.size();++i){char c=feed.source[i];out.offset=i;
  if(quote){if(escape)escape=false;else if(c=='\\')escape=true;else if(c=='"')quote=false;else atom+=c;continue;}
  if(c=='"'){quote=true;continue;}if(c=='['||c=='{'){flush();stack.push_back(c);if(stack.size()>feed.maximum_depth){out.valid=false;out.reason="depth";return out;}}
  else if(c==']'||c=='}'){flush();if(stack.empty()||((c==']'&&stack.back()!='[')||(c=='}'&&stack.back()!='{'))){out.valid=false;out.reason="mismatched close";return out;}stack.pop_back();}
  else if(c==feed.leaf_separator){flush();}else if(c!=' ')atom+=c;
 }
 flush();if(quote||escape||!stack.empty()){out.valid=false;out.offset=feed.source.size();out.reason="unclosed state";}return out;
}''',
        "Square and brace frames are typed, quotes suppress structural bytes, and maximum depth is enforced before accepting a child.",
    ),
    Architecture(
        "tag-stack", "Tagged block records", "open-tag stack with attribute quote lexer",
        "struct Feed { std::string source; std::vector<std::string> void_tags; };",
        r'''Feed{R"(<batch><item id="a>b">one</item><gap/><item>two</item></batch>)", {"gap"}}''',
        r'''Feed{R"(<batch><item>one</batch></item>)", {"gap"}}''',
        2,
        r'''
static CoreRecordState scan(const Feed& feed) {
 CoreRecordState out;std::vector<std::string> stack;
 for(std::size_t i=0;i<feed.source.size();){if(feed.source[i]!='<'){std::size_t j=feed.source.find('<',i);if(j==std::string::npos){j=feed.source.size();}auto text=feed.source.substr(i,j-i);if(!text.empty()){out.values.push_back(text);out.depths.push_back(0U);}i=j;continue;}
  std::size_t j=i+1;bool closing=j<feed.source.size()&&feed.source[j]=='/';if(closing)++j;std::size_t begin=j;while(j<feed.source.size()&&(std::isalnum(static_cast<unsigned char>(feed.source[j]))||feed.source[j]=='-'))++j;
  if(j==begin){out.valid=false;out.offset=i;out.reason="tag name";return out;}auto name=feed.source.substr(begin,j-begin);bool quote=false,escape=false,self=false;
  for(;j<feed.source.size();++j){char c=feed.source[j];if(quote){if(escape)escape=false;else if(c=='\\')escape=true;else if(c=='"')quote=false;}else if(c=='>')break;else if(c=='"')quote=true;else if(c=='/'&&j+1<feed.source.size()&&feed.source[j+1]=='>')self=true;}
  if(j==feed.source.size()||quote){out.valid=false;out.offset=i;out.reason="unclosed tag";return out;}if(closing){if(self||stack.empty()||stack.back()!=name){out.valid=false;out.offset=i;out.reason="tag mismatch";return out;}stack.pop_back();}
  else if(!self&&std::find(feed.void_tags.begin(),feed.void_tags.end(),name)==feed.void_tags.end()){stack.push_back(name);}
  i=j+1;
 }
 if(!stack.empty()){out.valid=false;out.offset=feed.source.size();out.reason="unclosed tags";}return out;
}''',
        "Attribute quotes may contain closing-angle bytes, self-closing tags never enter the stack, and closes must match the current tag.",
    ),
    Architecture(
        "indent-tree", "Indented record forest", "indentation path state machine",
        "struct Feed { std::vector<std::string> lines; std::size_t spaces_per_level; bool allow_roots; };",
        r'''Feed{{"root:one","  child:two","    leaf:three","sibling:four"},2U,true}''',
        r'''Feed{{"root:one","    skipped:two"},2U,true}''',
        4,
        r'''
static CoreRecordState scan(const Feed& feed) {
 CoreRecordState out;std::vector<std::string> path;
 for(std::size_t line=0;line<feed.lines.size();++line){const auto&s=feed.lines[line];std::size_t spaces=0;while(spaces<s.size()&&s[spaces]==' '){++spaces;}if(feed.spaces_per_level==0||spaces%feed.spaces_per_level){out.valid=false;out.offset=line;out.reason="indentation";return out;}std::size_t depth=spaces/feed.spaces_per_level;if(depth>path.size()){out.valid=false;out.offset=line;out.reason="skipped level";return out;}auto colon=s.find(':',spaces);if(colon==std::string::npos||colon==spaces){out.valid=false;out.offset=line;out.reason="record";return out;}while(path.size()>depth){path.pop_back();}auto name=s.substr(spaces,colon-spaces);if(depth==0&&!feed.allow_roots){out.valid=false;out.offset=line;out.reason="root forbidden";return out;}if(path.size()==depth){path.push_back(name);}else{path[depth]=name;}out.values.push_back(s.substr(colon+1));out.depths.push_back(depth);}
 return out;
}''',
        "Indentation is an exact multiple, depth may advance only after an existing parent, and record value parsing follows structural validation.",
    ),
    Architecture(
        "netstring", "Length-prefixed record batch", "overflow-safe length-prefix cursor",
        "struct Feed { std::string bytes; std::size_t maximum_payload; bool require_terminal_comma; };",
        r'''Feed{"5:alpha,4:beta,",16U,true}''',
        r'''Feed{"9:short,",16U,true}''',
        2,
        r'''
static CoreRecordState scan(const Feed& feed) {
 CoreRecordState out;std::size_t i=0;
 while(i<feed.bytes.size()){std::size_t begin=i,length=0;if(!std::isdigit(static_cast<unsigned char>(feed.bytes[i]))){out.valid=false;out.offset=i;out.reason="length digit";return out;}while(i<feed.bytes.size()&&std::isdigit(static_cast<unsigned char>(feed.bytes[i]))){unsigned digit=static_cast<unsigned>(feed.bytes[i]-'0');if(length>(feed.maximum_payload-digit)/10U){out.valid=false;out.offset=i;out.reason="length overflow";return out;}length=length*10U+digit;++i;}if(i==feed.bytes.size()||feed.bytes[i++]!=':'||length>feed.maximum_payload||length>feed.bytes.size()-i){out.valid=false;out.offset=begin;out.reason="payload length";return out;}out.values.push_back(feed.bytes.substr(i,length));out.depths.push_back(0U);i+=length;if(feed.require_terminal_comma&&(i==feed.bytes.size()||feed.bytes[i]!=',')){out.valid=false;out.offset=i;out.reason="terminator";return out;}if(i<feed.bytes.size()&&feed.bytes[i]==',')++i;}
 out.offset=i;return out;
}''',
        "Decimal length accumulation is overflow-safe, payload bytes are opaque, and the cursor must consume the declared terminator exactly.",
    ),
    Architecture(
        "chunk-stream", "Chunked quoted stream", "incremental lexical state across chunks",
        "struct Feed { std::vector<std::string> chunks; char separator; bool final_chunk; };",
        r'''Feed{{"alpha;\"be","ta;gamma\";delta"},';',true}''',
        r'''Feed{{"alpha;\"unterminated"},';',true}''',
        3,
        r'''
static CoreRecordState scan(const Feed& feed) {
 CoreRecordState out;std::string field;bool quote=false,escape=false;std::size_t absolute=0;
 for(const auto&chunk:feed.chunks){for(char c:chunk){out.offset=absolute++;if(quote){if(escape)escape=false;else if(c=='\\')escape=true;else if(c=='"')quote=false;else field+=c;}else if(c=='"')quote=true;else if(c==feed.separator){out.values.push_back(field);out.depths.push_back(quote?1U:0U);field.clear();}else field+=c;}}
 if(feed.final_chunk&&(quote||escape)){out.valid=false;out.offset=absolute;out.reason="unfinished lexical state";return out;}if(feed.final_chunk){out.values.push_back(field);out.depths.push_back(0U);}return out;
}''',
        "Quote and escape state survive arbitrary chunk boundaries, offsets are absolute, and finalization—not a chunk boundary—decides completeness.",
    ),
    Architecture(
        "multipart", "Multipart section reader", "boundary-line and header/body phase machine",
        "struct Feed { std::vector<std::string> lines; std::string boundary; std::size_t maximum_headers; };",
        r'''Feed{{"--cut","Name: first","","body one","--cut","Name: second","","body two","--cut--"},"cut",3U}''',
        r'''Feed{{"--cut","Name first","","body","--cut--"},"cut",3U}''',
        2,
        r'''
static CoreRecordState scan(const Feed& feed) {
 CoreRecordState out;enum class Phase{boundary,headers,body,done};Phase phase=Phase::boundary;std::size_t headers=0;std::string body;
 for(std::size_t i=0;i<feed.lines.size();++i){const auto&line=feed.lines[i];out.offset=i;if(phase==Phase::boundary){if(line=="--"+feed.boundary+"--"){phase=Phase::done;continue;}if(line!="--"+feed.boundary){out.valid=false;out.reason="boundary";return out;}phase=Phase::headers;headers=0;}
  else if(phase==Phase::headers){if(line.empty())phase=Phase::body;else{auto colon=line.find(':');if(colon==std::string::npos||colon==0||++headers>feed.maximum_headers){out.valid=false;out.reason="header";return out;}}}
  else if(phase==Phase::body){if(line=="--"+feed.boundary||line=="--"+feed.boundary+"--"){out.values.push_back(body);out.depths.push_back(0U);body.clear();phase=line=="--"+feed.boundary+"--"?Phase::done:Phase::headers;headers=0;}else{if(!body.empty()){body+='\n';}body+=line;}}
  else if(!line.empty()){out.valid=false;out.reason="trailing data";return out;}}
 if(phase!=Phase::done){out.valid=false;out.offset=feed.lines.size();out.reason="missing final boundary";}return out;
}''',
        "A boundary is recognized only as a complete line, headers precede one blank line, and no bytes may follow the closing boundary.",
    ),
    Architecture(
        "escaped-path", "Escaped hierarchical path", "segment decoder with parent navigation",
        "struct Feed { std::string path; char separator; char escape; bool allow_parent; };",
        r'''Feed{R"(root/child\/alias/../leaf)",'/', '\\',true}''',
        r'''Feed{R"(../../escape)",'/', '\\',true}''',
        2,
        r'''
static CoreRecordState scan(const Feed& feed) {
 CoreRecordState out;std::string segment;bool escaped=false;auto emit=[&](){if(segment.empty()){out.valid=false;out.reason="empty segment";return false;}if(segment==".."){if(!feed.allow_parent||out.values.empty()){out.valid=false;out.reason="parent above root";return false;}out.values.pop_back();out.depths.pop_back();}else if(segment!="."){out.values.push_back(segment);out.depths.push_back(out.values.size()-1U);}segment.clear();return true;};
 for(std::size_t i=0;i<feed.path.size();++i){char c=feed.path[i];out.offset=i;if(escaped){segment+=c;escaped=false;}else if(c==feed.escape)escaped=true;else if(c==feed.separator){if(!emit())return out;}else segment+=c;}
 if(escaped){out.valid=false;out.offset=feed.path.size();out.reason="dangling escape";return out;}emit();return out;
}''',
        "Escaped separators are data, dot segments are explicit, and parent navigation may not pop above the accepted root.",
    ),
    Architecture(
        "typed-fields", "Typed field packet", "structure-first unique-key validator",
        "struct Feed { std::vector<std::pair<std::string,std::string>> fields; std::vector<std::string> required; bool reject_unknown; };",
        r'''Feed{{{"id","17"},{"active","true"},{"label","alpha"}},{"id","active","label"},true}''',
        r'''Feed{{{"id","17"},{"id","18"},{"active","true"}},{"id","active"},true}''',
        3,
        r'''
static CoreRecordState scan(const Feed& feed) {
 CoreRecordState out;std::set<std::string> seen;
 for(std::size_t i=0;i<feed.fields.size();++i){const auto&kv=feed.fields[i];out.offset=i;if(kv.first.empty()||!seen.insert(kv.first).second){out.valid=false;out.reason="duplicate or empty key";return out;}if(feed.reject_unknown&&std::find(feed.required.begin(),feed.required.end(),kv.first)==feed.required.end()){out.valid=false;out.reason="unknown key";return out;}if(kv.first=="id"&&(kv.second.empty()||!std::all_of(kv.second.begin(),kv.second.end(),[](unsigned char c){return std::isdigit(c); }))){out.valid=false;out.reason="typed id";return out;}if(kv.first=="active"&&kv.second!="true"&&kv.second!="false"){out.valid=false;out.reason="typed bool";return out;}out.values.push_back(kv.first+"="+kv.second);out.depths.push_back(0U);}
 for(const auto&name:feed.required){if(!seen.count(name)){out.valid=false;out.offset=feed.fields.size();out.reason="missing required";return out;}}return out;
}''',
        "Keys are made unique before type conversion, required fields are checked after the full packet, and failed packets expose no partial mutation.",
    ),
    Architecture(
        "sexpr", "Quoted S-expression records", "recursive frame stack with atom lexer",
        "struct Feed { std::string source; std::size_t maximum_nodes; bool allow_empty_lists; };",
        r'''Feed{R"((root (left "two words") (right leaf)))",16U,true}''',
        r'''Feed{R"((root (left "unterminated)))",16U,true}''',
        5,
        r'''
static CoreRecordState scan(const Feed& feed) {
 CoreRecordState out;std::vector<std::size_t> child_counts;std::string atom;bool quote=false,escape=false;std::size_t nodes=0;auto emit=[&](){if(!atom.empty()){out.values.push_back(atom);out.depths.push_back(child_counts.empty()?0U:child_counts.size()-1U);if(!child_counts.empty())++child_counts.back();atom.clear();if(++nodes>feed.maximum_nodes){out.valid=false;out.reason="node limit";}}};
 for(std::size_t i=0;i<feed.source.size()&&out.valid;++i){char c=feed.source[i];out.offset=i;if(quote){if(escape)escape=false;else if(c=='\\')escape=true;else if(c=='"'){quote=false;emit();}else atom+=c;continue;}if(c=='"'){emit();quote=true;}else if(c=='('){emit();child_counts.push_back(0U);}else if(c==')'){emit();if(child_counts.empty()||(!feed.allow_empty_lists&&child_counts.back()==0U)){out.valid=false;out.reason="bad close";return out;}child_counts.pop_back();if(!child_counts.empty())++child_counts.back();}else if(std::isspace(static_cast<unsigned char>(c))){emit();}else atom+=c;}
 emit();if(quote||escape||!child_counts.empty()){out.valid=false;out.offset=feed.source.size();out.reason="unclosed expression";}return out;
}''',
        "Quoted atoms preserve spaces, every close targets the current list, and the node budget is applied as atoms are committed.",
    ),
)


OPERATIONS: tuple[Operation, ...] = (
    Operation("project", "stable projection", "return selected parsed values in caller-supplied column order", "const std::vector<std::size_t>& columns", "std::vector<std::size_t>{0U,1U}", "std::vector<std::string> projected;", "{}", r'''for(auto index:columns){if(index>=core.values.size()){return {false,core.offset,"projection index",{}};}result.projected.push_back(core.values[index]);}''', "!result.projected.empty()", "Out-of-range projection indices fail without returning a partial projection."),
    Operation("cardinality", "declared cardinality", "enforce an exact parsed-record count before returning it", "std::size_t expected", "2U", "std::size_t count = 0;", "0U", r'''if(core.values.size()!=expected){return {false,core.offset,"cardinality",0U};}result.count=core.values.size();''', "result.count > 0U", "A declared count mismatch is a semantic error after structural parsing."),
    Operation("unique", "stable uniqueness", "deduplicate parsed values with optional ASCII folding while preserving first occurrence", "bool ascii_fold", "true", "std::vector<std::string> unique_values;", "{}", r'''std::set<std::string> seen;for(auto value:core.values){auto key=value;if(ascii_fold){for(char&c:key)c=static_cast<char>(std::tolower(static_cast<unsigned char>(c)));}if(seen.insert(key).second){result.unique_values.push_back(value);}}''', "!result.unique_values.empty()", "Case-folding affects identity only; the first original spelling is retained."),
    Operation("bounded-total", "bounded byte total", "accumulate decoded leaf byte lengths while keeping the running total inside caller bounds", "long long minimum, long long maximum", "0LL,1000LL", "long long total = 0;", "0LL", r'''for(const auto&value:core.values){auto number=static_cast<long long>(value.size());if(number<minimum||number>maximum||result.total>maximum-number){return {false,core.offset,"bounded total",0LL};}result.total+=number;}''', "result.total >= 0LL", "Every decoded leaf contributes once and the running byte total remains in range."),
    Operation("flatten", "depth-first flatten", "emit depth-prefixed leaves up to an explicit output capacity", "std::size_t maximum_values", "32U", "std::vector<std::string> flattened;", "{}", r'''if(core.values.size()>maximum_values){return {false,core.offset,"flatten capacity",{}};}for(std::size_t i=0;i<core.values.size();++i){result.flattened.push_back(std::to_string(core.depths[i])+":"+core.values[i]);}''', "!result.flattened.empty()", "Depth is part of every flattened value and capacity is checked before emission."),
    Operation("checksum", "ordered rolling checksum", "compute an order-sensitive checked hash over values and structural depths", "std::uint64_t seed", "1469598103934665603ULL", "std::uint64_t checksum = 0;", "0ULL", r'''result.checksum=seed;for(std::size_t i=0;i<core.values.size();++i){for(unsigned char c:core.values[i]){result.checksum=(result.checksum^c)*1099511628211ULL;}result.checksum=(result.checksum^static_cast<std::uint64_t>(core.depths[i]+1U))*1099511628211ULL;}''', "result.checksum != 0ULL", "Both leaf order and structural depth contribute to the checksum."),
    Operation("ancestry", "ancestry paths", "construct deterministic parent paths rooted at a caller label", "const std::string& root_label", 'std::string("root")', "std::vector<std::string> paths;", "{}", r'''if(root_label.empty()){return {false,core.offset,"empty root",{}};}std::vector<std::string> stack;for(std::size_t i=0;i<core.values.size();++i){while(stack.size()>core.depths[i]){stack.pop_back();}if(core.depths[i]>stack.size()){return {false,core.offset,"missing parent",{}};}std::string path=root_label;for(const auto&part:stack){path+="/"+part;}path+="/"+core.values[i];result.paths.push_back(path);stack.push_back(core.values[i]);}''', "!result.paths.empty()", "Depth zero is record-relative; a depth jump beyond the materialized parent stack is rejected instead of inferred."),
    Operation("spans", "accepted value spans", "return stable half-open ordinal spans with optional canonical separator coverage", "bool include_separator", "true", "std::vector<std::pair<std::size_t,std::size_t>> spans;", "{}", r'''std::size_t cursor=0;for(std::size_t i=0;i<core.values.size();++i){auto begin=cursor;cursor+=core.values[i].size();auto end=cursor;if(i+1U<core.values.size()){if(include_separator)++end;++cursor;}result.spans.push_back({begin,end});}''', "!result.spans.empty()", "Every value has one span; enabling separator coverage extends each nonfinal span by the one canonical separator byte."),
    Operation("group", "fixed-width grouping", "partition accepted values into stable fixed-width groups without dropping a tail", "std::size_t width", "2U", "std::vector<std::vector<std::string>> groups;", "{}", r'''if(width==0U){return {false,core.offset,"zero group width",{}};}for(std::size_t i=0;i<core.values.size();i+=width){auto end=std::min(core.values.size(),i+width);result.groups.emplace_back(core.values.begin()+static_cast<std::ptrdiff_t>(i),core.values.begin()+static_cast<std::ptrdiff_t>(end));}''', "!result.groups.empty()", "A final short group is retained and zero width is rejected before grouping."),
    Operation("canonical", "canonical encoding", "escape and join leaves into one deterministic representation", "char output_separator", "'~'", "std::string canonical;", '""', r'''for(std::size_t i=0;i<core.values.size();++i){if(i){result.canonical+=output_separator;}for(char c:core.values[i]){if(c==output_separator||c=='\\'){result.canonical+='\\';}result.canonical+=c;}result.canonical+="@"+std::to_string(core.depths[i]);}''', "!result.canonical.empty()", "The output separator and escape bytes are escaped, and each encoded leaf carries its depth."),
)


def cases() -> tuple[Case, ...]:
    return tuple(
        Case(
            task_id=f"qr-{architecture.key}-{operation.key}",
            title=f"{architecture.title}: {operation.title}",
            architecture=architecture,
            operation=operation,
        )
        for architecture in ARCHITECTURES
        for operation in OPERATIONS
    )


CASES = cases()

if len(ARCHITECTURES) != 11 or len(OPERATIONS) != 10 or len(CASES) != 110:
    raise RuntimeError("quoted/nested record matrix must contain exactly 110 roots")
if len({case.task_id for case in CASES}) != len(CASES):
    raise RuntimeError("quoted/nested record task IDs must be unique")


EXPECTED_PARSE: dict[str, tuple[tuple[str, ...], tuple[int, ...]]] = {
    "quoted-row": (("alpha", "beta,gamma", "delta"), (0, 1, 0)),
    "escaped-pipe": (("north", "south|annex", "west"), (0, 0, 0)),
    "bracket-tree": (("root", "left,right", "leaf", "tail"), (0, 1, 1, 0)),
    "tag-stack": (("one", "two"), (0, 0)),
    "indent-tree": (("one", "two", "three", "four"), (0, 1, 2, 0)),
    "netstring": (("alpha", "beta"), (0, 0)),
    "chunk-stream": (("alpha", "beta;gamma", "delta"), (0, 0, 0)),
    "multipart": (("body one", "body two"), (0, 0)),
    "escaped-path": (("root", "leaf"), (0, 1)),
    "typed-fields": (("id=17", "active=true", "label=alpha"), (0, 0, 0)),
    "sexpr": (("root", "left", "two words", "right", "leaf"), (0, 1, 1, 1, 1)),
}

UNIQUE_PROBES: dict[str, tuple[str, tuple[str, ...], tuple[int, ...]]] = {
    "quoted-row": ('Feed{R"(Alpha,alpha,tail)",3U}', ("Alpha", "alpha", "tail"), (0, 0, 0)),
    "escaped-pipe": (r'''Feed{R"(Alpha|alpha|tail)",'\\',true}''', ("Alpha", "alpha", "tail"), (0, 0, 0)),
    "bracket-tree": ('Feed{R"([Alpha,alpha,tail])",4U,\',\'}', ("Alpha", "alpha", "tail"), (0, 0, 0)),
    "tag-stack": ('Feed{R"(<batch><item>Alpha</item><item>alpha</item></batch>)",{}}', ("Alpha", "alpha"), (0, 0)),
    "indent-tree": ('Feed{{"root:Alpha","sibling:alpha"},2U,true}', ("Alpha", "alpha"), (0, 0)),
    "netstring": ('Feed{"5:Alpha,5:alpha,",16U,true}', ("Alpha", "alpha"), (0, 0)),
    "chunk-stream": ('Feed{{"Alpha;alpha"},\';\',true}', ("Alpha", "alpha"), (0, 0)),
    "multipart": ('Feed{{"--cut","Name: first","","Alpha","--cut","Name: second","","alpha","--cut--"},"cut",3U}', ("Alpha", "alpha"), (0, 0)),
    "escaped-path": ('Feed{"Alpha/alpha",\'/\',\'~\',false}', ("Alpha", "alpha"), (0, 1)),
    "typed-fields": ('Feed{{{"label","Alpha"},{"LABEL","alpha"}},{},false}', ("label=Alpha", "LABEL=alpha"), (0, 0)),
    "sexpr": ('Feed{R"((Alpha alpha))",16U,true}', ("Alpha", "alpha"), (0, 0)),
}

CANONICAL_PROBES: dict[str, tuple[str, tuple[str, ...], tuple[int, ...]]] = {
    "quoted-row": (r'''Feed{R"(a\b,tail)",2U}''', (r"a\b", "tail"), (0, 0)),
    "escaped-pipe": (r'''Feed{R"(a\\b|tail)",'\\',true}''', (r"a\b", "tail"), (0, 0)),
    "bracket-tree": (r'''Feed{R"([a\b,tail])",4U,','}''', (r"a\b", "tail"), (0, 0)),
    "tag-stack": (r'''Feed{R"(<batch><item>a\b</item><item>tail</item></batch>)",{}}''', (r"a\b", "tail"), (0, 0)),
    "indent-tree": (r'''Feed{{R"(root:a\b)","sibling:tail"},2U,true}''', (r"a\b", "tail"), (0, 0)),
    "netstring": (r'''Feed{R"(3:a\b,4:tail,)",16U,true}''', (r"a\b", "tail"), (0, 0)),
    "chunk-stream": (r'''Feed{{R"(a\b;tail)"},';',true}''', (r"a\b", "tail"), (0, 0)),
    "multipart": (r'''Feed{{"--cut","Name: first","",R"(a\b)","--cut","Name: second","","tail","--cut--"},"cut",3U}''', (r"a\b", "tail"), (0, 0)),
    "escaped-path": (r'''Feed{R"(a\b/tail)",'/', '~',false}''', (r"a\b", "tail"), (0, 1)),
    "typed-fields": (r'''Feed{{{"label",R"(a\b)"},{"tail","x"}},{"label","tail"},true}''', (r"label=a\b", "tail=x"), (0, 0)),
    "sexpr": (r'''Feed{R"((a\b tail))",16U,true}''', (r"a\b", "tail"), (0, 0)),
}

ARCHITECTURE_ORACLE_CLAUSES = {
    "quoted-row": "result.reason.empty()",
    "escaped-pipe": "result.reason.size()==0U",
    "bracket-tree": 'result.reason.find("invalid")==std::string::npos',
    "tag-stack": 'result.reason.compare("")==0',
    "indent-tree": "result.reason==std::string{}",
    "netstring": "!result.reason.length()",
    "chunk-stream": "result.reason.begin()==result.reason.end()",
    "multipart": "result.reason.capacity()>=result.reason.size()",
    "escaped-path": "result.reason.substr(0).empty()",
    "typed-fields": "result.reason.find_first_not_of(' ')==std::string::npos",
    "sexpr": 'result.reason.rfind("",0)==0U',
}


def header(case: Case) -> str:
    op = case.operation
    return f'''#pragma once
#include <cstddef>
#include <cstdint>
#include <string>
#include <utility>
#include <vector>
namespace quoted_nested_records {{
{case.architecture.feed_decl}
struct Result {{ bool valid; std::size_t offset; std::string reason; {op.result_field} }};
Result solve(const Feed& feed, {op.option_decl});
}}
'''


def reference(case: Case) -> str:
    op = case.operation
    return f'''#include "task.h"
#include <algorithm>
#include <cctype>
#include <cstdint>
#include <set>
#include <stdexcept>
namespace quoted_nested_records {{
{_CORE_DECL}
{case.architecture.scanner}
Result solve(const Feed& feed, {op.option_decl}) {{
 auto core=scan(feed);
 if(!core.valid)return {{false,core.offset,core.reason,{op.result_init}}};
 Result result{{true,core.offset,"",{op.result_init}}};
 {op.reducer}
 return result;
}}
}}
'''


def instructions(case: Case) -> str:
    return (
        f"Implement the C++17 API declared in the editable header. The parser must use a "
        f"{case.architecture.mechanism}. {case.architecture.boundary_rule} After a structurally "
        f"valid parse, {case.operation.objective}. {case.operation.private_rule} Return the "
        "first failing zero-based byte, line, or record offset selected by the architecture; "
        "do not return partially reduced output on failure. Empty input follows the structural "
        "machine's rules. The implementation may use vectors and strings as result/work buffers, "
        "but it must not delegate parsing to regex, a CSV/JSON/XML library, or a generic parser."
    )


def _cpp_string(value: str) -> str:
    return json.dumps(value)


def _operation_option(case: Case, count: int, *, variant: bool = False) -> str:
    key = case.operation.key
    if key == "project":
        if count == 0:
            return "std::vector<std::size_t>{}"
        limit = min(count, 2)
        return "std::vector<std::size_t>{" + ",".join(f"{index}U" for index in range(limit)) + "}"
    if key == "cardinality":
        return f"{count}U"
    if key == "unique":
        return "false" if variant else "true"
    if key == "checksum":
        return "0ULL" if variant else "1469598103934665603ULL"
    if key == "spans":
        return "false" if variant else "true"
    return case.operation.option_value


def _call(case: Case, feed: str, count: int | None = None, *, variant: bool = False) -> str:
    if count is None:
        count = case.architecture.valid_count
    return f"solve({feed},{_operation_option(case, count, variant=variant)})"


def _checksum(values: tuple[str, ...], depths: tuple[int, ...], seed: int) -> int:
    value = seed
    for text, depth in zip(values, depths, strict=True):
        for byte in text.encode():
            value = ((value ^ byte) * 1099511628211) & ((1 << 64) - 1)
        value = ((value ^ (depth + 1)) * 1099511628211) & ((1 << 64) - 1)
    return value


def _operation_exact(
    case: Case,
    variable: str,
    values: tuple[str, ...],
    depths: tuple[int, ...],
    *,
    variant: bool = False,
    project_indices: tuple[int, ...] | None = None,
    output_separator: str = "~",
) -> str:
    key = case.operation.key
    if key == "project":
        indices = project_indices or tuple(range(min(len(values), 2)))
        selected = tuple(values[index] for index in indices)
        expected = ",".join(_cpp_string(value) for value in selected)
        payload = f"{variable}.projected==std::vector<std::string>{{{expected}}}"
    elif key == "cardinality":
        payload = f"{variable}.count=={len(values)}U"
    elif key == "unique":
        unique: list[str] = []
        seen: set[str] = set()
        for value in values:
            identity = value if variant else value.lower()
            if identity not in seen:
                seen.add(identity)
                unique.append(value)
        expected = ",".join(_cpp_string(value) for value in unique)
        payload = f"{variable}.unique_values==std::vector<std::string>{{{expected}}}"
    elif key == "bounded-total":
        payload = f"{variable}.total=={sum(len(value) for value in values)}LL"
    elif key == "flatten":
        expected = ",".join(
            _cpp_string(f"{depth}:{value}") for value, depth in zip(values, depths, strict=True)
        )
        payload = f"{variable}.flattened==std::vector<std::string>{{{expected}}}"
    elif key == "checksum":
        seed = 0 if variant else 1469598103934665603
        payload = f"{variable}.checksum=={_checksum(values, depths, seed)}ULL"
    elif key == "ancestry":
        stack: list[str] = []
        paths = []
        for value, depth in zip(values, depths, strict=True):
            while len(stack) > depth:
                stack.pop()
            if depth > len(stack):
                raise AssertionError(f"unrepresentable ancestry oracle: {case.task_id}")
            paths.append("root/" + "/".join([*stack, value]))
            stack.append(value)
        expected = ",".join(_cpp_string(value) for value in paths)
        payload = f"{variable}.paths==std::vector<std::string>{{{expected}}}"
    elif key == "spans":
        cursor = 0
        spans = []
        for index, value in enumerate(values):
            begin = cursor
            cursor += len(value)
            end = cursor
            if index + 1 < len(values):
                if not variant:
                    end += 1
                cursor += 1
            spans.append((begin, end))
        expected = ",".join(f"{{{begin}U,{end}U}}" for begin, end in spans)
        payload = (
            f"{variable}.spans==std::vector<std::pair<std::size_t,std::size_t>>{{{expected}}}"
        )
    elif key == "group":
        groups = [values[index : index + 2] for index in range(0, len(values), 2)]
        expected = ",".join(
            "{" + ",".join(_cpp_string(value) for value in group) + "}" for group in groups
        )
        payload = f"{variable}.groups==std::vector<std::vector<std::string>>{{{expected}}}"
    elif key == "canonical":
        encoded = []
        for value, depth in zip(values, depths, strict=True):
            escaped = value.replace("\\", "\\\\").replace(
                output_separator, f"\\{output_separator}"
            )
            encoded.append(f"{escaped}@{depth}")
        payload = f"{variable}.canonical=={_cpp_string(output_separator.join(encoded))}"
    else:
        raise AssertionError(key)
    return f"({variable}.valid&&{variable}.reason.empty()&&({payload}))"


def _empty_payload(case: Case, variable: str) -> str:
    key = case.operation.key
    if key == "cardinality":
        return f"{variable}.count==0U"
    if key == "bounded-total":
        return f"{variable}.total==0LL"
    if key == "checksum":
        return f"{variable}.checksum==0ULL"
    if key == "canonical":
        return f"{variable}.canonical.empty()"
    field = {
        "project": "projected",
        "unique": "unique_values",
        "flatten": "flattened",
        "ancestry": "paths",
        "spans": "spans",
        "group": "groups",
    }[key]
    return f"{variable}.{field}.empty()"


def _operation_probe(case: Case) -> str:
    values, depths = EXPECTED_PARSE[case.architecture.key]
    feed = case.architecture.valid_feed
    key = case.operation.key
    if key == "project":
        call = f"solve({feed},std::vector<std::size_t>{{1U,0U}})"
        invalid = f"solve({feed},std::vector<std::size_t>{{999U}})"
        exact = _operation_exact(
            case, "probe", values, depths, project_indices=(1, 0)
        )
        return f'auto probe={call};auto probe_invalid={invalid};bool operation_ok={exact}&&!probe_invalid.valid&&probe_invalid.reason=="projection index"&&probe_invalid.projected.empty();'
    if key == "cardinality":
        call = f"solve({feed},{len(values) + 1}U)"
        return f'auto probe={call};bool operation_ok=!probe.valid&&probe.reason=="cardinality"&&probe.count==0U;'
    if key == "bounded-total":
        call = f"solve({feed},0LL,0LL)"
        return f'auto probe={call};bool operation_ok=!probe.valid&&probe.reason=="bounded total"&&probe.total==0LL;'
    if key == "flatten":
        call = f"solve({feed},0U)"
        return f'auto probe={call};bool operation_ok=!probe.valid&&probe.reason=="flatten capacity"&&probe.flattened.empty();'
    if key == "ancestry":
        call = f"solve({feed},std::string(\"\"))"
        return f'auto probe={call};bool operation_ok=!probe.valid&&probe.reason=="empty root"&&probe.paths.empty();'
    if key == "group":
        call = f"solve({feed},0U)"
        return f'auto probe={call};bool operation_ok=!probe.valid&&probe.reason=="zero group width"&&probe.groups.empty();'
    if key == "unique":
        probe_feed, probe_values, probe_depths = UNIQUE_PROBES[case.architecture.key]
        folded = _call(case, probe_feed, len(probe_values))
        original = _call(case, probe_feed, len(probe_values), variant=True)
        folded_exact = _operation_exact(case, "probe", probe_values, probe_depths)
        original_exact = _operation_exact(
            case, "probe_original", probe_values, probe_depths, variant=True
        )
        return f"auto probe={folded};auto probe_original={original};bool operation_ok={folded_exact}&&{original_exact};"
    if key in {"checksum", "spans"}:
        call = _call(case, feed, len(values), variant=True)
        exact = _operation_exact(case, "probe", values, depths, variant=True)
        return f"auto probe={call};bool operation_ok={exact};"
    if key == "canonical":
        probe_feed, probe_values, probe_depths = CANONICAL_PROBES[case.architecture.key]
        call = f"solve({probe_feed},'a')"
        exact = _operation_exact(
            case,
            "probe",
            probe_values,
            probe_depths,
            output_separator="a",
        )
        return f"auto probe={call};bool operation_ok={exact};"
    raise AssertionError(key)


def _architecture_probe(case: Case) -> str:
    key = case.architecture.key
    if case.operation.key == "ancestry" and key in {
        "quoted-row",
        "bracket-tree",
        "sexpr",
    }:
        gap_feed = {
            "quoted-row": 'Feed{R"("alpha",beta)",2U}',
            "bracket-tree": 'Feed{R"([[leaf]])",4U,\',\'}',
            "sexpr": 'Feed{R"(((leaf)))",16U,true}',
        }[key]
        gap = _call(case, gap_feed, 1)
        gap_check = (
            '!architecture_gap.valid&&architecture_gap.reason=="missing parent"'
            "&&architecture_gap.paths.empty()"
        )
        if key != "sexpr":
            return f"auto architecture_gap={gap};bool architecture_ok={gap_check};"
        values, depths = ("root", "child"), (0, 1)
        call = _call(case, 'Feed{R"((root (child)))",16U,false}', len(values))
        exact = _operation_exact(case, "architecture", values, depths)
        empty_call = _call(case, 'Feed{R"(())",16U,false}', 0)
        return f"auto architecture_gap={gap};auto architecture={call};auto architecture_empty={empty_call};bool architecture_ok=({gap_check})&&{exact}&&!architecture_empty.valid;"
    if key == "sexpr":
        values, depths = ("root", "child"), (0, 1)
        call = _call(case, 'Feed{R"((root (child)))",16U,false}', len(values))
        exact = _operation_exact(case, "architecture", values, depths)
        empty_call = _call(case, 'Feed{R"(())",16U,false}', 0)
        return f"auto architecture={call};auto architecture_empty={empty_call};bool architecture_ok={exact}&&!architecture_empty.valid;"
    if key == "multipart":
        values, depths = ("body one", "body two"), (0, 0)
        feed = 'Feed{{"--cut-","Name: first","","body one","--cut-","Name: second","","body two","--cut---"},"cut-",3U}'
        call = _call(case, feed, len(values))
        exact = _operation_exact(case, "architecture", values, depths)
        return f"auto architecture={call};bool architecture_ok={exact};"
    if key == "typed-fields":
        option = _operation_option(case, 3)
        feeds = (
            'Feed{{{"id","17"},{"active","true"},{"label","alpha"},{"extra","x"}},{"id","active","label"},true}',
            'Feed{{{"id","17"},{"active","true"}},{"id","active","label"},true}',
            'Feed{{{"","17"},{"active","true"},{"label","alpha"}},{"","active","label"},true}',
            'Feed{{{"id",""},{"active","true"},{"label","alpha"}},{"id","active","label"},true}',
            'Feed{{{"id","17"},{"active","yes"},{"label","alpha"}},{"id","active","label"},true}',
        )
        calls = ";".join(f"auto architecture{index}=solve({feed},{option})" for index, feed in enumerate(feeds))
        checks = "&&".join(f"!architecture{index}.valid" for index in range(len(feeds)))
        return f"{calls};bool architecture_ok={checks};"
    return "bool architecture_ok=true;"


def visible_test(case: Case) -> str:
    call = _call(case, case.architecture.valid_feed)
    values, depths = EXPECTED_PARSE[case.architecture.key]
    exact = _operation_exact(case, "result", values, depths)
    clause = ARCHITECTURE_ORACLE_CLAUSES[case.architecture.key]
    return f'''#include "task.h"
int main(){{using namespace quoted_nested_records;auto result={call};return !({exact}&&({clause}));}}
'''


def private_test(case: Case) -> str:
    valid = _call(case, case.architecture.valid_feed)
    invalid = _call(case, case.architecture.invalid_feed)
    values, depths = EXPECTED_PARSE[case.architecture.key]
    first_exact = _operation_exact(case, "first", values, depths)
    again_exact = _operation_exact(case, "again", values, depths)
    operation_probe = _operation_probe(case)
    architecture = _architecture_probe(case)
    bad_empty = _empty_payload(case, "bad")
    return f'''#include "task.h"
int main(){{using namespace quoted_nested_records;auto first={valid};auto again={valid};auto bad={invalid};{operation_probe}{architecture}return !({first_exact}&&{again_exact}&&!bad.valid&&({bad_empty})&&first.offset==again.offset&&first.reason==again.reason&&operation_ok&&architecture_ok);}}
'''


def negative(case: Case) -> str:
    source = reference(case)
    needle = " return result;\n"
    if needle not in source:
        raise AssertionError(case.task_id)
    mutation = {
        "project": "std::reverse(result.projected.begin(),result.projected.end());",
        "cardinality": "++result.count;",
        "unique": "std::reverse(result.unique_values.begin(),result.unique_values.end());",
        "bounded-total": "++result.total;",
        "flatten": "std::reverse(result.flattened.begin(),result.flattened.end());",
        "checksum": "result.checksum^=1ULL;",
        "ancestry": "std::reverse(result.paths.begin(),result.paths.end());",
        "spans": "std::reverse(result.spans.begin(),result.spans.end());",
        "group": "if(!result.groups.empty())result.groups.pop_back();",
        "canonical": "result.canonical+='!';",
    }[case.operation.key]
    replacement = f" {mutation}\n return result;\n"
    return source.replace(needle, replacement, 1)
