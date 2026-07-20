"""Mechanism-distinct text-layout cases for local family remediation."""
from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class TextCase:
    task_id: str
    legacy_id: str
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


def _starter(signature: str, result: str) -> str:
    return f'#include "task.h"\nnamespace curriculum {{ {result} {signature} {{ return {{}}; }} }}\n'


CASES = (
    TextCase(
        "justify-assembly-agenda", "justify-assembly-agenda",
        "Hanging-indent agenda layout", "hanging-indent-prefix-width-wrap",
        "Wrap agenda labels and continuation text with a measured hanging indent.",
        "layout_agenda(items,width)->AgendaLayout",
        "continuation(item.label.size() + 1U",
        """# Instructions
Lay out nonempty labelled agenda items. The first line starts with label and one
space; continuation lines start beneath the first text byte. Collapse spaces in text
and greedily wrap whole words. Width is 4..80 and every label must fit with one text
byte. Invalid input is atomic. Preserve item order.
""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct AgendaItem{std::string label,text;}; struct AgendaLayout{bool valid=false;std::vector<std::string> lines;}; AgendaLayout layout_agenda(const std::vector<AgendaItem>&,std::size_t); }
""",
        _starter("layout_agenda(const std::vector<AgendaItem>&,std::size_t)", "AgendaLayout"),
        """#include "task.h"
#include <sstream>
namespace curriculum { AgendaLayout layout_agenda(const std::vector<AgendaItem>& items,std::size_t width){AgendaLayout out;if(items.empty()||width<4U||width>80U)return out;for(const AgendaItem& item:items){if(item.label.empty()||item.label.size()+2U>width)return{};std::istringstream in(item.text);std::vector<std::string>w;for(std::string x;in>>x;)w.push_back(x);if(w.empty())return{};std::string prefix=item.label+" ";std::string continuation(item.label.size() + 1U,' '),line=prefix;for(const auto& x:w){if(x.size()>width-continuation.size())return{};if(line.size()+(line==prefix?0U:1U)+x.size()>width){out.lines.push_back(line);line=continuation+x;}else{if(line!=prefix)line+=" ";line+=x;}}out.lines.push_back(line);}out.valid=true;return out;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=layout_agenda({{"1.","alpha beta gamma"}},10);return x.valid&&x.lines==std::vector<std::string>{"1. alpha","   beta","   gamma"}?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;f+=layout_agenda({},10).valid;f+=layout_agenda({{"long","x"}},5).valid;auto x=layout_agenda({{"A","one two"}},7);f+=!x.valid||x.lines[1]!="  two";return f;}
""",
    ),
    TextCase(
        "segment-flight-telex", "justify-aviation-brief",
        "Flight telex segmentation", "atomic-slash-separated-first-fit",
        "Segment indivisible flight tokens into bounded slash-separated telex lines.",
        "segment_telex(tokens,width)->TelexPlan",
        "candidate = current.size() + 1U + token.size()",
        """# Instructions
Tokens are nonempty uppercase letters or digits. Pack them in order with slash
separators. Never split a token. A token longer than width is recorded in overflow.
Width is 3..40. Invalid characters make the result invalid atomically.
""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct TelexPlan{bool valid=false;std::vector<std::string> lines,overflow;}; TelexPlan segment_telex(const std::vector<std::string>&,std::size_t); }
""",
        _starter("segment_telex(const std::vector<std::string>&,std::size_t)", "TelexPlan"),
        """#include "task.h"
#include <cctype>
namespace curriculum { TelexPlan segment_telex(const std::vector<std::string>& ts,std::size_t width){TelexPlan o;if(ts.empty()||width<3U||width>40U)return o;std::string current;for(const auto& token:ts){if(token.empty())return{};for(unsigned char c:token)if(!std::isupper(c)&&!std::isdigit(c))return{};if(token.size()>width){if(!current.empty()){o.lines.push_back(current);current.clear();}o.overflow.push_back(token);continue;}std::size_t candidate = current.size() + 1U + token.size();if(!current.empty()&&candidate>width){o.lines.push_back(current);current=token;}else{if(!current.empty())current+="/";current+=token;}}if(!current.empty())o.lines.push_back(current);o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=segment_telex({"AB12","CD","EF"},6);return x.valid&&x.lines==std::vector<std::string>{"AB12","CD/EF"}?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;auto x=segment_telex({"TOOLONG","A"},4);f+=!x.valid||x.overflow.size()!=1||x.lines[0]!="A";f+=segment_telex({"a"},4).valid;return f;}
""",
    ),
    TextCase(
        "layout-protocol-steps", "justify-emergency-protocol",
        "Aligned protocol steps", "global-label-column-continuation-wrap",
        "Align numbered protocol steps to the widest label and wrap at a shared text column.",
        "layout_steps(steps,width)->ProtocolLayout",
        "label_width = std::max(label_width",
        """# Instructions
Each step has a nonempty identifier and text. Compute the widest identifier label,
then align every text at the same column. Continuations use spaces to that column.
Collapse text whitespace and greedily wrap. Width is 6..100; invalid input is atomic.
""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct ProtocolStep{std::string id,text;}; struct ProtocolLayout{bool valid=false;std::size_t text_column=0;std::vector<std::string> lines;}; ProtocolLayout layout_steps(const std::vector<ProtocolStep>&,std::size_t); }
""",
        _starter("layout_steps(const std::vector<ProtocolStep>&,std::size_t)", "ProtocolLayout"),
        """#include "task.h"
#include <algorithm>
#include <sstream>
namespace curriculum { ProtocolLayout layout_steps(const std::vector<ProtocolStep>& a,std::size_t width){ProtocolLayout o;if(a.empty()||width<6U||width>100U)return o;std::size_t label_width=0;for(auto& s:a){if(s.id.empty()||s.text.empty())return{};label_width = std::max(label_width,s.id.size()+1U);}o.text_column=label_width+1U;if(o.text_column+1U>width)return{};for(auto&s:a){std::istringstream in(s.text);std::string line=s.id+"."+std::string(label_width-s.id.size(),' '),word;bool any=false;while(in>>word){any=true;if(word.size()>width-o.text_column)return{};if(line.size()+(line.size()>o.text_column?1U:0U)+word.size()>width){o.lines.push_back(line);line=std::string(o.text_column,' ')+word;}else{if(line.size()>o.text_column)line+=" ";line+=word;}}if(!any)return{};o.lines.push_back(line);}o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=layout_steps({{"12","call"},{"1","cut power"}},10);return x.valid&&x.text_column==4&&x.lines==std::vector<std::string>{"12. call","1.  cut","    power"}?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;f+=layout_steps({},9).valid;f+=layout_steps({{"","x"}},9).valid;auto x=layout_steps({{"A","one two"}},7);f+=!x.valid||x.lines.size()!=2;return f;}
""",
    ),
    TextCase(
        "paginate-expedition-ledger", "justify-expedition-log",
        "Expedition ledger pagination", "indivisible-entry-block-page-bin",
        "Paginate timestamped entry blocks without splitting a block.",
        "paginate_ledger(entries,page_height)->LedgerPages",
        "used + block.size() > page_height",
        """# Instructions
An entry has a timestamp and one or more rendered body lines. Its first line begins
with the timestamp and remaining lines align below the body. A block may not cross a
page. Page height is 2..20; oversized blocks are reported by input index.
""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct LogEntry{std::string timestamp;std::vector<std::string> body;}; struct LedgerPages{bool valid=false;std::vector<std::vector<std::string>> pages;std::vector<std::size_t> oversized;}; LedgerPages paginate_ledger(const std::vector<LogEntry>&,std::size_t); }
""",
        _starter("paginate_ledger(const std::vector<LogEntry>&,std::size_t)", "LedgerPages"),
        """#include "task.h"
namespace curriculum { LedgerPages paginate_ledger(const std::vector<LogEntry>& es,std::size_t page_height){LedgerPages o;if(es.empty()||page_height<2U||page_height>20U)return o;std::vector<std::string> page;for(std::size_t i=0;i<es.size();++i){auto&e=es[i];if(e.timestamp.empty()||e.body.empty())return{};std::vector<std::string> block;for(std::size_t j=0;j<e.body.size();++j){if(e.body[j].empty()||e.body[j].find('\n')!=std::string::npos)return{};block.push_back(j==0?e.timestamp+" "+e.body[j]:std::string(e.timestamp.size()+1U,' ')+e.body[j]);}if(block.size()>page_height){o.oversized.push_back(i);continue;}std::size_t used=page.size();if(!page.empty() && used + block.size() > page_height){o.pages.push_back(page);page.clear();}page.insert(page.end(),block.begin(),block.end());}if(!page.empty())o.pages.push_back(page);o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=paginate_ledger({{"T1",{"a"}},{"T2",{"b"}}},2);return x.valid&&x.pages.size()==1&&x.pages[0]==std::vector<std::string>{"T1 a","T2 b"}?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;auto x=paginate_ledger({{"T",{"a","b","c"}}},2);f+=!x.valid||x.oversized!=std::vector<std::size_t>{0};f+=paginate_ledger({{"",{"x"}}},3).valid;return f;}
""",
    ),
    TextCase(
        "align-field-observations", "justify-field-notebook",
        "Observation table alignment", "column-maxima-tab-stop-clipping",
        "Align observation fields at computed tab stops and audit clipped rows.",
        "align_observations(rows,width)->ObservationTable",
        "value_column = code_width + 2U",
        """# Instructions
Rows contain nonempty code, value, and unit. Compute code and value column maxima,
render with two-space gaps, and clip rows longer than width while recording indices.
Width is 8..120. Newlines are invalid.
""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct Observation{std::string code,value,unit;}; struct ObservationTable{bool valid=false;std::size_t value_column=0,unit_column=0;std::vector<std::string> lines;std::vector<std::size_t> clipped;}; ObservationTable align_observations(const std::vector<Observation>&,std::size_t); }
""",
        _starter("align_observations(const std::vector<Observation>&,std::size_t)", "ObservationTable"),
        """#include "task.h"
#include <algorithm>
namespace curriculum { ObservationTable align_observations(const std::vector<Observation>& rs,std::size_t width){ObservationTable o;if(rs.empty()||width<8U||width>120U)return o;std::size_t code_width=0,value_width=0;for(auto&r:rs){if(r.code.empty()||r.value.empty()||r.unit.empty()||r.code.find('\n')!=std::string::npos||r.value.find('\n')!=std::string::npos||r.unit.find('\n')!=std::string::npos)return{};code_width=std::max(code_width,r.code.size());value_width=std::max(value_width,r.value.size());}o.value_column = code_width + 2U;o.unit_column=o.value_column+value_width+2U;for(std::size_t i=0;i<rs.size();++i){auto&r=rs[i];std::string line=r.code+std::string(o.value_column-r.code.size(),' ')+r.value+std::string(o.unit_column-o.value_column-r.value.size(),' ')+r.unit;if(line.size()>width){line.resize(width);o.clipped.push_back(i);}o.lines.push_back(line);}o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=align_observations({{"A","12","m"},{"LONG","3","s"}},20);return x.valid&&x.value_column==6&&x.unit_column==10&&x.lines[0]=="A     12  m"?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;auto x=align_observations({{"ABCDE","12345","unit"}},8);f+=!x.valid||x.clipped!=std::vector<std::size_t>{0}||x.lines[0].size()!=8;f+=align_observations({{"A","","m"}},10).valid;return f;}
""",
    ),
    TextCase(
        "paginate-dialogue-boxes", "justify-game-dialogue",
        "Dialogue box pagination", "speaker-prefix-wrap-box-state",
        "Wrap speaker-labelled utterances and paginate lines into fixed-height boxes.",
        "paginate_dialogue(lines,width,height)->DialoguePages",
        "pages.back().size() == height",
        """# Instructions
Use speaker plus colon as the first-line prefix and align continuations below the
text. Greedily wrap words, then stream lines into boxes of height rows. Width is
8..60 and height 1..8. Empty fields and overlong words are invalid.
""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct Utterance{std::string speaker,text;}; struct DialoguePages{bool valid=false;std::vector<std::vector<std::string>> pages;}; DialoguePages paginate_dialogue(const std::vector<Utterance>&,std::size_t,std::size_t); }
""",
        _starter("paginate_dialogue(const std::vector<Utterance>&,std::size_t,std::size_t)", "DialoguePages"),
        """#include "task.h"
#include <sstream>
namespace curriculum { DialoguePages paginate_dialogue(const std::vector<Utterance>& us,std::size_t width,std::size_t height){DialoguePages o;if(us.empty()||width<8U||width>60U||height<1U||height>8U)return o;o.pages.push_back({});for(auto&u:us){std::string prefix=u.speaker+": ";if(u.speaker.empty()||u.text.empty()||prefix.size()+1U>width)return{};std::istringstream in(u.text);std::string line=prefix,w;while(in>>w){if(w.size()>width-prefix.size())return{};if(line.size()+(line==prefix?0U:1U)+w.size()>width){if(o.pages.back().size() == height)o.pages.push_back({});o.pages.back().push_back(line);line=std::string(prefix.size(),' ')+w;}else{if(line!=prefix)line+=" ";line+=w;}}if(o.pages.back().size()==height)o.pages.push_back({});o.pages.back().push_back(line);}o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=paginate_dialogue({{"A","one two three"}},8,2);return x.valid&&x.pages.size()==2&&x.pages[0]==std::vector<std::string>{"A: one","   two"}&&x.pages[1][0]=="   three"?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;f+=paginate_dialogue({},10,2).valid;f+=paginate_dialogue({{"","x"}},10,2).valid;auto x=paginate_dialogue({{"A","x"}},8,1);f+=!x.valid||x.pages.size()!=1;return f;}
""",
    ),
    TextCase(
        "balance-catalog-columns", "justify-garden-catalog",
        "Catalog column balancing", "prefix-sum-stable-split",
        "Choose an order-preserving split minimizing column-height imbalance.",
        "balance_catalog(entries)->CatalogSpread",
        "difference < best_difference",
        """# Instructions
Entries have nonempty names and positive rendered heights. Split after at least one
and before the final entry. Minimize absolute height difference; ties choose the
earliest split. Preserve order. Fewer than two entries or overflow is invalid.
""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct CatalogEntry{std::string name;std::size_t height;}; struct CatalogSpread{bool valid=false;std::vector<std::string> left,right;std::size_t left_height=0,right_height=0;}; CatalogSpread balance_catalog(const std::vector<CatalogEntry>&); }
""",
        _starter("balance_catalog(const std::vector<CatalogEntry>&)", "CatalogSpread"),
        """#include "task.h"
#include <limits>
namespace curriculum { CatalogSpread balance_catalog(const std::vector<CatalogEntry>& es){CatalogSpread o;if(es.size()<2U)return o;std::size_t total=0;for(auto&e:es){if(e.name.empty()||e.height==0U||total>std::numeric_limits<std::size_t>::max()-e.height)return{};total+=e.height;}std::size_t prefix=0,best=1,best_difference=total;for(std::size_t i=1;i<es.size();++i){prefix+=es[i-1].height;std::size_t difference=prefix>total-prefix?prefix-(total-prefix):(total-prefix)-prefix;if(difference < best_difference){best_difference=difference;best=i;}}for(std::size_t i=0;i<es.size();++i)(i<best?o.left:o.right).push_back(es[i].name);for(std::size_t i=0;i<best;++i)o.left_height+=es[i].height;o.right_height=total-o.left_height;o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=balance_catalog({{"a",3},{"b",2},{"c",4}});return x.valid&&x.left==std::vector<std::string>{"a","b"}&&x.left_height==5&&x.right_height==4?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;auto x=balance_catalog({{"a",2},{"b",2},{"c",2}});f+=!x.valid||x.left.size()!=1;f+=balance_catalog({{"a",1}}).valid;f+=balance_catalog({{"",1},{"b",1}}).valid;return f;}
""",
    ),
    TextCase(
        "reflow-nested-quotes", "justify-helpdesk-replies",
        "Nested quote reflow", "quote-depth-prefix-parser",
        "Wrap each reply line after preserving its quote-depth prefix.",
        "reflow_quotes(lines,width)->ReplyLayout",
        "while (depth < raw.size() && raw[depth] == '>')",
        """# Instructions
Each line begins with zero or more greater-than bytes, optionally one space, then
nonempty text. Preserve depth as the prefix and greedily wrap collapsed words.
Continuations repeat the prefix. Width is 4..80; impossible prefixes are invalid.
""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct ReplyLayout{bool valid=false;std::vector<std::string> lines;std::size_t max_depth=0;}; ReplyLayout reflow_quotes(const std::vector<std::string>&,std::size_t); }
""",
        _starter("reflow_quotes(const std::vector<std::string>&,std::size_t)", "ReplyLayout"),
        """#include "task.h"
#include <algorithm>
#include <sstream>
namespace curriculum { ReplyLayout reflow_quotes(const std::vector<std::string>& rs,std::size_t width){ReplyLayout o;if(rs.empty()||width<4U||width>80U)return o;for(auto&raw:rs){std::size_t depth=0;while (depth < raw.size() && raw[depth] == '>')++depth;std::size_t p=depth;if(p<raw.size()&&raw[p]==' ')++p;std::string prefix(depth,'>');if(depth)prefix+=" ";if(p>=raw.size()||prefix.size()+1U>width)return{};o.max_depth=std::max(o.max_depth,depth);std::istringstream in(raw.substr(p));std::string line=prefix,w;while(in>>w){if(w.size()>width-prefix.size())return{};if(line.size()+(line==prefix?0U:1U)+w.size()>width){o.lines.push_back(line);line=prefix+w;}else{if(line!=prefix)line+=" ";line+=w;}}o.lines.push_back(line);}o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=reflow_quotes({">> one two three"},9);return x.valid&&x.max_depth==2&&x.lines==std::vector<std::string>{">> one",">> two",">> three"}?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;f+=reflow_quotes({">>> x"},4).valid;f+=reflow_quotes({"> "},8).valid;auto x=reflow_quotes({"a  b"},4);f+=!x.valid||x.lines[0]!="a b";return f;}
""",
    ),
    TextCase(
        "align-invoice-tabstops", "justify-invoice-notes",
        "Invoice tab-stop alignment", "maximum-key-tabstop-overflow-ledger",
        "Align invoice key and value rows at a computed separator column.",
        "align_notes(notes,width)->InvoiceTable",
        "separator_column = longest + 1U",
        """# Instructions
Set the separator column one byte after the longest nonempty key. Render key, spaces,
vertical bar, one space, and value. Omit over-width rows and report their indices.
Width is 6..100. Newlines and empty fields are invalid.
""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct InvoiceNote{std::string key,value;}; struct InvoiceTable{bool valid=false;std::size_t separator_column=0;std::vector<std::string> rows;std::vector<std::size_t> overflow;}; InvoiceTable align_notes(const std::vector<InvoiceNote>&,std::size_t); }
""",
        _starter("align_notes(const std::vector<InvoiceNote>&,std::size_t)", "InvoiceTable"),
        """#include "task.h"
#include <algorithm>
namespace curriculum { InvoiceTable align_notes(const std::vector<InvoiceNote>& ns,std::size_t width){InvoiceTable o;if(ns.empty()||width<6U||width>100U)return o;std::size_t longest=0;for(auto&n:ns){if(n.key.empty()||n.value.empty()||n.key.find('\n')!=std::string::npos||n.value.find('\n')!=std::string::npos)return{};longest=std::max(longest,n.key.size());}o.separator_column = longest + 1U;for(std::size_t i=0;i<ns.size();++i){auto&n=ns[i];std::string row=n.key+std::string(o.separator_column-n.key.size(),' ')+"| "+n.value;if(row.size()>width)o.overflow.push_back(i);else o.rows.push_back(row);}o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=align_notes({{"tax","5"},{"subtotal","10"}},20);return x.valid&&x.separator_column==9&&x.rows[0]=="tax      | 5"?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;auto x=align_notes({{"a","longvalue"}},8);f+=!x.valid||x.overflow!=std::vector<std::size_t>{0}||!x.rows.empty();f+=align_notes({{"","x"}},9).valid;return f;}
""",
    ),
    TextCase(
        "break-clauses-by-penalty", "justify-legal-notice",
        "Minimum-penalty clause breaking", "cubic-raggedness-dynamic-program",
        "Choose line breaks minimizing cubic unused-width penalty.",
        "break_clauses(words,width)->ClauseLayout",
        "penalty * penalty * penalty + cost[j + 1U]",
        """# Instructions
Words use one separating space and may not exceed width. A nonfinal line costs the
cube of unused width; the final line costs zero. Return the minimum penalty and lines.
Width is 2..60. Invalid or impossible input is invalid; ties use the earliest break.
""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct ClauseLayout{bool valid=false;unsigned long long penalty=0;std::vector<std::string> lines;}; ClauseLayout break_clauses(const std::vector<std::string>&,std::size_t); }
""",
        _starter("break_clauses(const std::vector<std::string>&,std::size_t)", "ClauseLayout"),
        """#include "task.h"
#include <limits>
namespace curriculum { ClauseLayout break_clauses(const std::vector<std::string>& w,std::size_t width){ClauseLayout o;if(w.empty()||width<2U||width>60U)return o;for(auto&s:w)if(s.empty()||s.find_first_of(" \t\n")!=std::string::npos||s.size()>width)return o;const auto inf=std::numeric_limits<unsigned long long>::max()/4U;std::vector<unsigned long long> cost(w.size()+1U,inf);std::vector<std::size_t> next(w.size());cost[w.size()]=0;for(std::size_t ii=w.size();ii-->0;){std::size_t used=0;for(std::size_t j=ii;j<w.size();++j){used+=(j==ii?0U:1U)+w[j].size();if(used>width)break;unsigned long long penalty=width-used;unsigned long long candidate=j+1U==w.size()?0U:penalty * penalty * penalty + cost[j + 1U];if(candidate<cost[ii]){cost[ii]=candidate;next[ii]=j+1U;}}}if(cost[0]==inf)return o;for(std::size_t i=0;i<w.size();i=next[i]){std::string line;for(std::size_t j=i;j<next[i];++j){if(!line.empty())line+=" ";line+=w[j];}o.lines.push_back(line);}o.penalty=cost[0];o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=break_clauses({"aaa","bb","cc","d"},6);return x.valid&&x.lines==std::vector<std::string>{"aaa bb","cc d"}&&x.penalty==0?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;f+=break_clauses({},5).valid;f+=break_clauses({"toolong"},3).valid;auto x=break_clauses({"a","b","cc","dd"},4);f+=!x.valid||x.penalty!=9||x.lines!=std::vector<std::string>{"a b","cc","dd"};return f;}
""",
    ),
    TextCase(
        "prevent-notice-widows", "justify-library-notices",
        "Widow-controlled notice wrapping", "greedy-wrap-backward-widow-rebalance",
        "Rebalance a legal one-word final line from its predecessor.",
        "wrap_without_widows(words,width)->NoticeLayout",
        "lines.back().size() == 1U",
        """# Instructions
Greedily wrap words with one space. If the final line has one word and its predecessor
has at least two, move the predecessor's last word when both new lines fit. Report
whether rebalanced. Width is 3..50. Invalid or overlong words are invalid.
""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct NoticeLayout{bool valid=false,rebalanced=false;std::vector<std::string> lines;}; NoticeLayout wrap_without_widows(const std::vector<std::string>&,std::size_t); }
""",
        _starter("wrap_without_widows(const std::vector<std::string>&,std::size_t)", "NoticeLayout"),
        """#include "task.h"
namespace curriculum { NoticeLayout wrap_without_widows(const std::vector<std::string>& ws,std::size_t width){NoticeLayout o;if(ws.empty()||width<3U||width>50U)return o;std::vector<std::vector<std::string>> lines(1);std::size_t used=0;for(auto&w:ws){if(w.empty()||w.find_first_of(" \t\n")!=std::string::npos||w.size()>width)return{};if(!lines.back().empty()&&used+1U+w.size()>width){lines.push_back({});used=0;}lines.back().push_back(w);used+=(used?1U:0U)+w.size();}if(lines.size()>1U&&lines.back().size() == 1U&&lines[lines.size()-2U].size()>=2U){auto&prev=lines[lines.size()-2U];std::string moved=prev.back();std::size_t last_len=moved.size()+1U+lines.back()[0].size();prev.pop_back();if(last_len<=width&&!prev.empty()){lines.back().insert(lines.back().begin(),moved);o.rebalanced=true;}else prev.push_back(moved);}for(auto&v:lines){std::string line;for(auto&w:v){if(!line.empty())line+=" ";line+=w;}o.lines.push_back(line);}o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=wrap_without_widows({"one","two","six"},7);if(!x.valid||!x.rebalanced)return 1;if(x.lines.size()!=2U||x.lines[0].size()!=3U)return 2;return x.lines==std::vector<std::string>{"one","two six"}?0:3;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;auto x=wrap_without_widows({"aa","bb","cccc"},5);f+=!x.valid||x.rebalanced;f+=wrap_without_widows({"bad word"},9).valid;return f;}
""",
    ),
    TextCase(
        "wrap-dosage-hyphenation", "justify-medication-leaflet",
        "Declared-point dosage hyphenation", "residual-token-largest-cut-queue",
        "Wrap dosage words by splitting only at declared byte cuts.",
        "wrap_dosage(words,width)->DosageLayout",
        "cut > chosen && cut + 1U <= remaining",
        """# Instructions
Each word declares strictly internal cut positions. Greedily fill lines. When a word
does not fit an empty line, choose the largest cut whose prefix plus hyphen fits,
emit it, and continue with the residual. Width is 3..30. No legal cut is invalid.
""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct DosageWord{std::string text;std::vector<std::size_t> cuts;}; struct DosageLayout{bool valid=false;std::vector<std::string> lines;std::size_t splits=0;}; DosageLayout wrap_dosage(const std::vector<DosageWord>&,std::size_t); }
""",
        _starter("wrap_dosage(const std::vector<DosageWord>&,std::size_t)", "DosageLayout"),
        """#include "task.h"
#include <deque>
namespace curriculum { DosageLayout wrap_dosage(const std::vector<DosageWord>& input,std::size_t width){DosageLayout o;if(input.empty()||width<3U||width>30U)return o;std::deque<DosageWord> q(input.begin(),input.end());std::string line;while(!q.empty()){DosageWord w=q.front();q.pop_front();if(w.text.empty())return{};for(auto c:w.cuts)if(c==0U||c>=w.text.size())return{};std::size_t need=(line.empty()?0U:1U)+w.text.size();if(line.size()+need<=width){if(!line.empty())line+=" ";line+=w.text;continue;}if(!line.empty()){o.lines.push_back(line);line.clear();q.push_front(w);continue;}std::size_t remaining=width,chosen=0;for(auto cut:w.cuts)if(cut > chosen && cut + 1U <= remaining)chosen=cut;if(chosen==0U)return{};o.lines.push_back(w.text.substr(0,chosen)+"-");DosageWord rest{w.text.substr(chosen),{}};for(auto c:w.cuts)if(c>chosen)rest.cuts.push_back(c-chosen);q.push_front(rest);++o.splits;}if(!line.empty())o.lines.push_back(line);o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=wrap_dosage({{"medication",{3,5}}},6);return x.valid&&x.splits==1&&x.lines==std::vector<std::string>{"medic-","ation"}?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;f+=wrap_dosage({{"abcdef",{2}}},3).valid;f+=wrap_dosage({{"abc",{0}}},4).valid;f+=wrap_dosage({{"abcdefg",{6}}},6).valid;auto x=wrap_dosage({{"ab",{}},{"cd",{}}},5);f+=!x.valid||x.lines[0]!="ab cd";return f;}
""",
    ),
    TextCase(
        "center-plaque-lines", "justify-museum-plaques",
        "Centered plaque lines", "left-biased-odd-padding-center",
        "Greedily form plaque lines and center with deterministic odd padding.",
        "center_plaque(words,width)->PlaqueLayout",
        "left = spare / 2U",
        """# Instructions
Greedily group words with one space. Center each line to exactly width bytes using
floor(extra/2) spaces on the left and the remainder on the right. Return original
content widths. Width is 3..60; invalid or overlong words are invalid.
""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct PlaqueLayout{bool valid=false;std::vector<std::string> lines;std::vector<std::size_t> content_widths;}; PlaqueLayout center_plaque(const std::vector<std::string>&,std::size_t); }
""",
        _starter("center_plaque(const std::vector<std::string>&,std::size_t)", "PlaqueLayout"),
        """#include "task.h"
namespace curriculum { PlaqueLayout center_plaque(const std::vector<std::string>& ws,std::size_t width){PlaqueLayout o;if(ws.empty()||width<3U||width>60U)return o;std::vector<std::string> raw;for(auto&w:ws){if(w.empty()||w.find_first_of(" \t\n")!=std::string::npos||w.size()>width)return{};if(raw.empty()||raw.back().size()+1U+w.size()>width)raw.push_back(w);else raw.back()+=" "+w;}for(auto&line:raw){o.content_widths.push_back(line.size());std::size_t spare=width-line.size(),left = spare / 2U;o.lines.push_back(std::string(left,' ')+line+std::string(spare-left,' '));}o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=center_plaque({"red","fox"},9);return x.valid&&x.lines==std::vector<std::string>{" red fox "}&&x.content_widths[0]==7?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;auto x=center_plaque({"abcd"},7);f+=!x.valid||x.lines[0]!=" abcd  ";f+=center_plaque({"a b"},5).valid;return f;}
""",
    ),
    TextCase(
        "segment-radio-cues", "justify-radio-script",
        "Radio cue segmentation", "dual-byte-duration-resource-segmentation",
        "Partition spoken words under byte-width and duration limits.",
        "segment_cues(words,width,max_ms)->CueSheet",
        "next_ms > max_ms",
        """# Instructions
Greedily append spoken words while both one-space byte width and total milliseconds
stay within limits. Start a cue when either would exceed. A single word exceeding a
limit is overflow by index. Width is 2..80 and durations must be positive.
""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct SpokenWord{std::string text;int milliseconds;}; struct CueSheet{bool valid=false;std::vector<std::string> cues;std::vector<int> durations;std::vector<std::size_t> overflow;}; CueSheet segment_cues(const std::vector<SpokenWord>&,std::size_t,int); }
""",
        _starter("segment_cues(const std::vector<SpokenWord>&,std::size_t,int)", "CueSheet"),
        """#include "task.h"
namespace curriculum { CueSheet segment_cues(const std::vector<SpokenWord>& ws,std::size_t width,int max_ms){CueSheet o;if(ws.empty()||width<2U||width>80U||max_ms<=0)return o;std::string line;int ms=0;for(std::size_t i=0;i<ws.size();++i){auto&w=ws[i];if(w.text.empty()||w.milliseconds<=0)return{};if(w.text.size()>width||w.milliseconds>max_ms){if(!line.empty()){o.cues.push_back(line);o.durations.push_back(ms);line.clear();ms=0;}o.overflow.push_back(i);continue;}std::size_t next_width=line.size()+(line.empty()?0U:1U)+w.text.size();int next_ms=ms+w.milliseconds;if(!line.empty()&&(next_width>width||next_ms > max_ms)){o.cues.push_back(line);o.durations.push_back(ms);line=w.text;ms=w.milliseconds;}else{if(!line.empty())line+=" ";line+=w.text;ms=next_ms;}}if(!line.empty()){o.cues.push_back(line);o.durations.push_back(ms);}o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=segment_cues({{"one",400},{"two",700},{"x",100}},9,1000);return x.valid&&x.cues==std::vector<std::string>{"one","two x"}&&x.durations[1]==800?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;auto x=segment_cues({{"long",2000},{"ok",1}},5,1000);f+=!x.valid||x.overflow!=std::vector<std::size_t>{0}||x.cues[0]!="ok";auto exact=segment_cues({{"a",400},{"b",600}},8,1000);f+=!exact.valid||exact.cues.size()!=1;f+=segment_cues({{"x",0}},4,4).valid;return f;}
""",
    ),
    TextCase(
        "scroll-platform-pages", "justify-rail-platform-board",
        "Overlapping platform pages", "prefix-reserved-overlap-window",
        "Wrap route-prefixed tokens and form pages with one-line overlap.",
        "make_board_pages(route,messages,width,rows)->BoardPages",
        "start += rows - 1U",
        """# Instructions
Prefix every line with route plus colon. Pack indivisible message tokens within the
remaining width. Form pages of at most rows lines, repeating the last line as the
first of the next page. Width is 8..60 and rows 2..8.
""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct BoardPages{bool valid=false;std::vector<std::vector<std::string>> pages;}; BoardPages make_board_pages(const std::string&,const std::vector<std::string>&,std::size_t,std::size_t); }
""",
        _starter("make_board_pages(const std::string&,const std::vector<std::string>&,std::size_t,std::size_t)", "BoardPages"),
        """#include "task.h"
namespace curriculum { BoardPages make_board_pages(const std::string& route,const std::vector<std::string>& ms,std::size_t width,std::size_t rows){BoardPages o;std::string prefix=route+": ";if(route.empty()||ms.empty()||width<8U||width>60U||rows<2U||rows>8U||prefix.size()+1U>width)return o;std::vector<std::string> lines;std::string line=prefix;for(auto&m:ms){if(m.empty()||m.find_first_of(" \t\n")!=std::string::npos||m.size()>width-prefix.size())return{};if(line.size()+(line==prefix?0U:1U)+m.size()>width){lines.push_back(line);line=prefix+m;}else{if(line!=prefix)line+=" ";line+=m;}}lines.push_back(line);for(std::size_t start=0;start<lines.size();start += rows - 1U){std::size_t end=start+rows<lines.size()?start+rows:lines.size();o.pages.emplace_back(lines.begin()+static_cast<std::ptrdiff_t>(start),lines.begin()+static_cast<std::ptrdiff_t>(end));if(end==lines.size())break;}o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=make_board_pages("R",{"aaaa","bbbb","cccc","dddd"},8,2);return x.valid&&x.pages.size()==3&&x.pages[0][1]==x.pages[1][0]?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;f+=make_board_pages("",{"x"},8,2).valid;f+=make_board_pages("R",{"too long"},9,2).valid;auto x=make_board_pages("R",{"a"},8,2);f+=!x.valid||x.pages.size()!=1;return f;}
""",
    ),
    TextCase(
        "wrap-recipe-quantities", "justify-recipe-cards",
        "Ingredient hanging layout", "atomic-quantity-prefix-hanging-wrap",
        "Keep quantity and unit atomic and wrap descriptions beneath them.",
        "wrap_ingredients(items,width)->RecipeLayout",
        "prefix = item.quantity + \" \" + item.unit + \" \"",
        """# Instructions
Each ingredient has quantity, unit, and description words. The first line starts with
quantity and unit; continuation text aligns beneath the description. Greedily wrap.
Width is 8..80. Empty fields, overlong words, or an oversized prefix are invalid.
""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct Ingredient{std::string quantity,unit;std::vector<std::string> words;}; struct RecipeLayout{bool valid=false;std::vector<std::string> lines;}; RecipeLayout wrap_ingredients(const std::vector<Ingredient>&,std::size_t); }
""",
        _starter("wrap_ingredients(const std::vector<Ingredient>&,std::size_t)", "RecipeLayout"),
        """#include "task.h"
namespace curriculum { RecipeLayout wrap_ingredients(const std::vector<Ingredient>& is,std::size_t width){RecipeLayout o;if(is.empty()||width<8U||width>80U)return o;for(auto&item:is){std::string prefix = item.quantity + " " + item.unit + " ";if(item.quantity.empty()||item.unit.empty()||item.words.empty()||prefix.size()+1U>width)return{};std::string line=prefix;for(auto&w:item.words){if(w.empty()||w.find_first_of(" \t\n")!=std::string::npos||w.size()>width-prefix.size())return{};if(line.size()+(line==prefix?0U:1U)+w.size()>width){o.lines.push_back(line);line=std::string(prefix.size(),' ')+w;}else{if(line!=prefix)line+=" ";line+=w;}}o.lines.push_back(line);}o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=wrap_ingredients({{"2","tbsp",{"olive","oil"}}},12);return x.valid&&x.lines==std::vector<std::string>{"2 tbsp olive","       oil"}?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;f+=wrap_ingredients({},10).valid;f+=wrap_ingredients({{"","g",{"x"}}},10).valid;auto x=wrap_ingredients({{"1","g",{"a","b"}}},8);f+=!x.valid||x.lines.size()!=1;return f;}
""",
    ),
    TextCase(
        "fit-poster-font-scale", "justify-safety-posters",
        "Poster scale fitting", "descending-discrete-scale-simulation",
        "Choose the largest integer font scale whose wrapped text fits a cell grid.",
        "fit_poster(words,columns,rows)->PosterFit",
        "for (int scale = 4; scale >= 1; --scale)",
        """# Instructions
At scale s, each byte consumes s columns and each line consumes s rows. Greedily wrap
words with one scaled space. Choose the largest scale in 1..4 that fits columns and
rows, returning unscaled lines. Invalid dimensions or words are invalid.
""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct PosterFit{bool valid=false;int scale=0;std::vector<std::string> lines;}; PosterFit fit_poster(const std::vector<std::string>&,std::size_t,std::size_t); }
""",
        _starter("fit_poster(const std::vector<std::string>&,std::size_t,std::size_t)", "PosterFit"),
        """#include "task.h"
namespace curriculum { PosterFit fit_poster(const std::vector<std::string>& ws,std::size_t columns,std::size_t rows){PosterFit o;if(ws.empty()||columns==0U||rows==0U)return o;for(auto&w:ws)if(w.empty()||w.find_first_of(" \t\n")!=std::string::npos)return o;for (int scale = 4; scale >= 1; --scale){std::size_t cap=columns/static_cast<std::size_t>(scale);if(cap==0U)continue;std::vector<std::string> lines(1);bool possible=true;for(auto&w:ws){if(w.size()>cap){possible=false;break;}if(!lines.back().empty()&&lines.back().size()+1U+w.size()>cap)lines.push_back(w);else{if(!lines.back().empty())lines.back()+=" ";lines.back()+=w;}}if(possible&&lines.size()*static_cast<std::size_t>(scale)<=rows){o.valid=true;o.scale=scale;o.lines=lines;return o;}}return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=fit_poster({"AB","CD"},12,4);return x.valid&&x.scale==2&&x.lines==std::vector<std::string>{"AB CD"}?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;auto x=fit_poster({"abcd"},4,1);f+=!x.valid||x.scale!=1;f+=fit_poster({"a b"},8,8).valid;f+=fit_poster({"long"},2,2).valid;return f;}
""",
    ),
    TextCase(
        "balance-newsletter-columns", "justify-school-newsletter",
        "Newsletter linear partition", "order-preserving-minimax-partition-dp",
        "Partition article heights into contiguous columns minimizing maximum height.",
        "balance_articles(articles,columns)->NewsletterLayout",
        "candidate = std::max(dp[k - 1U][j]",
        """# Instructions
Partition positive-height articles in source order into exactly the requested number
of nonempty contiguous columns. Minimize the maximum column height; ties choose the
earliest break. Return title groups and maximum height. Invalid counts are invalid.
""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct Article{std::string title;std::size_t height;}; struct NewsletterLayout{bool valid=false;std::size_t max_height=0;std::vector<std::vector<std::string>> columns;}; NewsletterLayout balance_articles(const std::vector<Article>&,std::size_t); }
""",
        _starter("balance_articles(const std::vector<Article>&,std::size_t)", "NewsletterLayout"),
        """#include "task.h"
#include <algorithm>
#include <limits>
namespace curriculum { NewsletterLayout balance_articles(const std::vector<Article>& a,std::size_t columns){NewsletterLayout o;if(a.empty()||columns==0U||columns>a.size())return o;std::vector<std::size_t> prefix(a.size()+1U);for(std::size_t i=0;i<a.size();++i){if(a[i].title.empty()||a[i].height==0U||prefix[i]>std::numeric_limits<std::size_t>::max()-a[i].height)return{};prefix[i+1U]=prefix[i]+a[i].height;}auto inf=std::numeric_limits<std::size_t>::max();std::vector<std::vector<std::size_t>> dp(columns+1U,std::vector<std::size_t>(a.size()+1U,inf)),cut=dp;dp[0][0]=0;for(std::size_t k=1;k<=columns;++k)for(std::size_t i=k;i<=a.size();++i)for(std::size_t j=k-1U;j<i;++j){if(dp[k-1U][j]==inf)continue;std::size_t candidate = std::max(dp[k - 1U][j],prefix[i]-prefix[j]);if(candidate<dp[k][i]){dp[k][i]=candidate;cut[k][i]=j;}}std::vector<std::size_t> ends(columns+1U);ends[columns]=a.size();for(std::size_t k=columns;k>0;--k)ends[k-1U]=cut[k][ends[k]];for(std::size_t k=0;k<columns;++k){o.columns.push_back({});for(std::size_t i=ends[k];i<ends[k+1U];++i)o.columns.back().push_back(a[i].title);}o.max_height=dp[columns][a.size()];o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=balance_articles({{"a",2},{"b",3},{"c",4}},2);return x.valid&&x.columns==std::vector<std::vector<std::string>>{{"a","b"},{"c"}}&&x.max_height==5?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;f+=balance_articles({{"a",1}},2).valid;f+=balance_articles({{"",1}},1).valid;auto x=balance_articles({{"a",4},{"b",1},{"c",1}},2);f+=!x.valid||x.max_height!=4;return f;}
""",
    ),
    TextCase(
        "pack-address-lines", "justify-shipping-labels",
        "Typed address packing", "field-state-locality-postcode-coalescing",
        "Render address fields while requiring locality and postcode to share a line.",
        "pack_address(address,width)->LabelLayout",
        "locality_postcode = address.locality",
        """# Instructions
Recipient is its own line. Greedily pack ordered street parts. The atomic locality
plus postcode pair is the final line and may not split. Width is 6..50. All fields
are nonempty and newline-free; any overlong field makes the result invalid.
""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct Address{std::string recipient;std::vector<std::string> street;std::string locality,postcode;}; struct LabelLayout{bool valid=false;std::vector<std::string> lines;}; LabelLayout pack_address(const Address&,std::size_t); }
""",
        _starter("pack_address(const Address&,std::size_t)", "LabelLayout"),
        """#include "task.h"
namespace curriculum { LabelLayout pack_address(const Address& address,std::size_t width){LabelLayout o;if(width<6U||width>50U||address.recipient.empty()||address.street.empty()||address.locality.empty()||address.postcode.empty())return o;auto clean=[](const std::string&s){return !s.empty()&&s.find('\n')==std::string::npos;};if(!clean(address.recipient)||address.recipient.size()>width)return o;o.lines.push_back(address.recipient);std::string line;for(auto&p:address.street){if(!clean(p)||p.size()>width)return{};if(!line.empty()&&line.size()+1U+p.size()>width){o.lines.push_back(line);line=p;}else{if(!line.empty())line+=" ";line+=p;}}o.lines.push_back(line);std::string locality_postcode = address.locality + " " + address.postcode;if(!clean(address.locality)||!clean(address.postcode)||locality_postcode.size()>width)return{};o.lines.push_back(locality_postcode);o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=pack_address({"Ada",{"12","Long","Road"},"Rome","42"},8);return x.valid&&x.lines==std::vector<std::string>{"Ada","12 Long","Road","Rome 42"}?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;f+=pack_address({"A",{},"X","1"},8).valid;f+=pack_address({"A",{"street"},"Longtown","99"},8).valid;auto x=pack_address({"A",{"x"},"Y","1"},6);f+=!x.valid||x.lines.back()!="Y 1";return f;}
""",
    ),
    TextCase(
        "merge-bulletin-regions", "justify-weather-bulletin",
        "Bulletin region coalescing", "adjacent-severity-run-coalescing",
        "Coalesce adjacent equal-severity regions before bounded rendering.",
        "merge_regions(notices,width)->BulletinLayout",
        "back.severity == notice.severity",
        """# Instructions
Merge each maximal adjacent run with equal severity: join regions with plus and texts
with one space. Render a severity prefix, regions, and text. Records longer than width
go to overflow without splitting. Width is 8..100; severity is 1..5.
""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct RegionNotice{std::string region,text;int severity;}; struct BulletinLayout{bool valid=false;std::vector<std::string> lines,overflow;std::size_t merged_runs=0;}; BulletinLayout merge_regions(const std::vector<RegionNotice>&,std::size_t); }
""",
        _starter("merge_regions(const std::vector<RegionNotice>&,std::size_t)", "BulletinLayout"),
        """#include "task.h"
namespace curriculum { BulletinLayout merge_regions(const std::vector<RegionNotice>& ns,std::size_t width){BulletinLayout o;if(ns.empty()||width<8U||width>100U)return o;std::vector<RegionNotice> runs;for(auto&notice:ns){if(notice.region.empty()||notice.text.empty()||notice.severity<1||notice.severity>5||notice.region.find('\n')!=std::string::npos||notice.text.find('\n')!=std::string::npos)return{};if(!runs.empty()){auto&back=runs.back();if(back.severity == notice.severity){back.region+="+"+notice.region;back.text+=" "+notice.text;++o.merged_runs;continue;}}runs.push_back(notice);}for(auto&r:runs){std::string line="["+std::to_string(r.severity)+"] "+r.region+": "+r.text;(line.size()>width?o.overflow:o.lines).push_back(line);}o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=merge_regions({{"N","rain",2},{"S","wind",2},{"E","clear",1}},40);return x.valid&&x.merged_runs==1&&x.lines==std::vector<std::string>{"[2] N+S: rain wind","[1] E: clear"}?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;auto x=merge_regions({{"N","long text",3}},8);f+=!x.valid||x.overflow.size()!=1;f+=merge_regions({{"","x",1}},20).valid;auto y=merge_regions({{"A","x",1},{"B","y",2}},20);f+=y.merged_runs!=0;return f;}
""",
    ),
)


def _escape_cpp_literals(content: str) -> str:
    return content.replace("find('\n')", "find('\\n')").replace(
        'find_first_of(" \t\n")', 'find_first_of(" \\t\\n")'
    )


CASES = tuple(
    replace(
        case,
        reference=_escape_cpp_literals(case.reference),
        visible_test=_escape_cpp_literals(case.visible_test),
        hidden_test=_escape_cpp_literals(case.hidden_test),
    )
    for case in CASES
)


NEGATIVE_MUTATIONS: dict[str, tuple[str, str, str]] = {
    "justify-assembly-agenda": (
        "std::string continuation(item.label.size() + 1U,' ')",
        "std::string continuation(1U,' ')",
        "continuations ignore the measured label",
    ),
    "segment-flight-telex": (
        "current.size() + 1U + token.size()",
        "current.size() + token.size()",
        "separator width is omitted",
    ),
    "layout-protocol-steps": (
        "label_width = std::max(label_width,s.id.size()+1U)",
        "label_width = s.id.size()+1U",
        "only the last label controls alignment",
    ),
    "paginate-expedition-ledger": (
        "used + block.size() > page_height",
        "used + block.size() >= page_height",
        "an exact-fit block is moved",
    ),
    "align-field-observations": (
        "o.value_column = code_width + 2U",
        "o.value_column = code_width + 1U",
        "the required column gap is lost",
    ),
    "paginate-dialogue-boxes": (
        "if(o.pages.back().size()==height)o.pages.push_back({});",
        "if(o.pages.back().size()>height)o.pages.push_back({});",
        "boxes exceed their row capacity",
    ),
    "balance-catalog-columns": (
        "difference < best_difference",
        "difference <= best_difference",
        "ties choose the latest split",
    ),
    "reflow-nested-quotes": (
        "std::string prefix(depth,'>')",
        "std::string prefix(depth-1U,'>')",
        "quote depth is undercounted",
    ),
    "align-invoice-tabstops": (
        "o.separator_column = longest + 1U",
        "o.separator_column = longest",
        "the separator touches the longest key",
    ),
    "break-clauses-by-penalty": (
        "penalty * penalty * penalty + cost[j + 1U]",
        "penalty + cost[j + 1U]",
        "linear penalty replaces cubic raggedness",
    ),
    "prevent-notice-widows": (
        "lines.back().size() == 1U",
        "lines.back().empty()",
        "widow rebalance never runs",
    ),
    "wrap-dosage-hyphenation": (
        "cut > chosen && cut + 1U <= remaining",
        "cut > chosen && cut <= remaining",
        "hyphen width is omitted",
    ),
    "center-plaque-lines": (
        "left = spare / 2U",
        "left = (spare + 1U) / 2U",
        "odd padding is biased to the wrong side",
    ),
    "segment-radio-cues": (
        "next_ms > max_ms",
        "next_ms >= max_ms",
        "exact duration fits are rejected",
    ),
    "scroll-platform-pages": (
        "start += rows - 1U",
        "start += rows",
        "page overlap is removed",
    ),
    "wrap-recipe-quantities": (
        'prefix = item.quantity + " " + item.unit + " "',
        'prefix = item.quantity + item.unit + " "',
        "quantity and unit are not separated",
    ),
    "fit-poster-font-scale": (
        "for (int scale = 4; scale >= 1; --scale)",
        "for (int scale = 1; scale <= 4; ++scale)",
        "the smallest fitting scale is selected",
    ),
    "balance-newsletter-columns": (
        "candidate = std::max(dp[k - 1U][j],prefix[i]-prefix[j])",
        "candidate = dp[k - 1U][j]+prefix[i]-prefix[j]",
        "sum replaces the minimax objective",
    ),
    "pack-address-lines": (
        'locality_postcode = address.locality + " " + address.postcode',
        "locality_postcode = address.locality + address.postcode",
        "locality and postcode are not separated",
    ),
    "merge-bulletin-regions": (
        "back.severity == notice.severity",
        "back.severity != notice.severity",
        "different severities are merged",
    ),
}
TASKS = CASES
