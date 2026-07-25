"""Thirty mechanism-distinct clean-room reflow and layout expansion cases."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class LayoutCase:
    task_id: str
    title: str
    mechanism: str
    api: str
    instructions: str
    header: str
    starter: str
    reference: str
    visible_test: str
    hidden_test: str
    negative_old: str
    negative_new: str
    negative_reason: str


def _starter(signature: str, result: str) -> str:
    parameters = re.findall(r"\b([a-z_][a-z_0-9]*)\s*(?=,|\))", signature)
    suppressions = "".join(
        f"static_cast<void>({parameter});" for parameter in parameters
    )
    return (
        '#include "task.h"\n'
        f"namespace curriculum {{ {result} {signature} "
        f"{{ {suppressions}return {{}}; }} }}\n"
    )


def _escape_cpp_control_literals(content: str) -> str:
    """Undo Python's control-character decoding inside C++ quoted literals."""

    pattern = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', re.S)

    def escape(match: re.Match[str]) -> str:
        return (
            match.group(0)
            .replace("\0", "\\0")
            .replace("\r", "\\r")
            .replace("\n", "\\n")
            .replace("\t", "\\t")
        )

    return pattern.sub(escape, content)


def _case(
    task_id: str,
    title: str,
    mechanism: str,
    api: str,
    instructions: str,
    header: str,
    signature: str,
    result: str,
    reference: str,
    visible: str,
    hidden: str,
    mutation: tuple[str, str, str],
) -> LayoutCase:
    old, new, reason = mutation
    header = _escape_cpp_control_literals(header)
    reference = _escape_cpp_control_literals(reference)
    visible = _escape_cpp_control_literals(visible)
    hidden = _escape_cpp_control_literals(hidden)
    old = _escape_cpp_control_literals(old)
    new = _escape_cpp_control_literals(new)
    if old not in reference:
        raise ValueError(f"negative mutation marker missing for {task_id}: {old}")
    starter = _starter(signature, result)
    if task_id == "reflow-stream-fragments":
        starter = '''#include "task.h"
namespace curriculum {
StreamReflower::StreamReflower(std::size_t width):width_(width){}
bool StreamReflower::push(const std::string&){return false;}
StreamLayout StreamReflower::finish(){return {};}
void StreamReflower::word(){}
void StreamReflower::paragraph(){}
}
'''
    return LayoutCase(
        task_id, title, mechanism, api, instructions, header,
        starter, reference, visible, hidden, old, new, reason,
    )


CASES = (
    _case(
        "reflow-stream-fragments", "Streaming paragraph reflow",
        "incremental tokenizer with cross-chunk paragraph state",
        "StreamReflower(width).push(chunk); finish()->StreamLayout",
        """Feed ASCII chunks into a stateful reflower. Spaces, tabs, and single LF bytes separate words; two consecutive LF bytes close a paragraph. Chunk boundaries have no semantic effect. Width is 3..40, CR is invalid, words longer than width are invalid, and finish is idempotent. Empty input finishes as a valid empty layout.""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct StreamLayout{bool valid=false;std::vector<std::string> lines;}; class StreamReflower{public:explicit StreamReflower(std::size_t);bool push(const std::string&);StreamLayout finish();private:std::size_t width_;bool valid_=true,done_=false,pending_lf_=false;std::string word_,line_;std::vector<std::string> lines_;void word();void paragraph();}; }
""",
        "StreamReflower::StreamReflower(std::size_t width)", "",
        """#include "task.h"
namespace curriculum { StreamReflower::StreamReflower(std::size_t width):width_(width){valid_=width>=3U&&width<=40U;}void StreamReflower::word(){if(word_.empty()||!valid_)return;if(word_.size()>width_){valid_=false;return;}if(line_.empty())line_=word_;else if(line_.size()+1U+word_.size()<=width_)line_+=" "+word_;else{lines_.push_back(line_);line_=word_;}word_.clear();}void StreamReflower::paragraph(){word();if(!line_.empty()){lines_.push_back(line_);line_.clear();}if(!lines_.empty()&&!lines_.back().empty())lines_.push_back("");}bool StreamReflower::push(const std::string& chunk){if(done_)return false;for(char c:chunk){if(c=='\r'){valid_=false;continue;}if(c=='\n'){word();if(pending_lf_)paragraph();pending_lf_=true;}else{if(pending_lf_)pending_lf_=false;if(c==' '||c=='\t')word();else word_.push_back(c);}}return valid_;}StreamLayout StreamReflower::finish(){if(done_)return {valid_,valid_?lines_:std::vector<std::string>{}};done_=true;word();if(!line_.empty())lines_.push_back(line_);while(!lines_.empty()&&lines_.back().empty())lines_.pop_back();return {valid_,valid_?lines_:std::vector<std::string>{}};} }
""",
        """#include "task.h"
int main(){using namespace curriculum;StreamReflower r(7);r.push("one tw");r.push("o\nthree\n\nfour");auto x=r.finish();return x.valid&&x.lines==std::vector<std::string>{"one two","three","","four"}?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;StreamReflower a(6);a.push("ab");a.push(" cd");auto x=a.finish();f+=!x.valid||x.lines!=std::vector<std::string>{"ab cd"};f+=a.push("x");StreamReflower b(3);b.push("toolong");f+=b.finish().valid;StreamReflower c(4);c.push("a\r");f+=c.finish().valid;StreamReflower d(3);d.push("ok\n\nlongword");auto first=d.finish();auto second=d.finish();f+=first.valid||second.valid||!first.lines.empty()||!second.lines.empty();return f;}
""",
        ("if(pending_lf_)paragraph();", "if(false&&pending_lf_)paragraph();", "paragraph separators disappear"),
    ),
    _case(
        "layout-nested-bullets", "Nested bullet forest layout",
        "parent-index forest traversal with measured hanging prefixes",
        "layout_bullets(items,width)->BulletLayout",
        """Render a parent-index forest. Each item has a nonempty label, text words, and parent index -1 or a smaller item index. Roots use `* ` and children use two spaces per depth followed by `- `. Wrap words beneath the first text byte. Width is 6..60, depth is at most 8, and input order defines sibling order. Valid empty input returns no lines.""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct BulletItem{int parent=-1;std::string label;std::vector<std::string> words;};struct BulletLayout{bool valid=false;std::vector<std::string> lines;};BulletLayout layout_bullets(const std::vector<BulletItem>&,std::size_t); }
""",
        "layout_bullets(const std::vector<BulletItem>& items,std::size_t width)", "BulletLayout",
        """#include "task.h"
namespace curriculum { BulletLayout layout_bullets(const std::vector<BulletItem>& items,std::size_t width){BulletLayout o;if(width<6U||width>60U)return o;std::vector<int> depth(items.size());for(std::size_t i=0;i<items.size();++i){const auto&x=items[i];if(x.parent>=static_cast<int>(i)||x.parent< -1||x.label.empty()||x.words.empty())return{};depth[i]=x.parent<0?0:depth[static_cast<std::size_t>(x.parent)]+1;if(depth[i]>8)return{};std::string prefix(static_cast<std::size_t>(depth[i])*2U,' ');prefix+=depth[i]==0?"* ":"- ";prefix+=x.label+" ";if(prefix.size()>=width)return{};std::string line=prefix;for(const auto&w:x.words){if(w.empty()||w.find_first_of(" \t\n")!=std::string::npos||w.size()>width-prefix.size())return{};if(line.size()+(line==prefix?0U:1U)+w.size()>width){o.lines.push_back(line);line=std::string(prefix.size(),' ')+w;}else{if(line!=prefix)line+=' ';line+=w;}}o.lines.push_back(line);}o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=layout_bullets({{-1,"A",{"one","two"}},{0,"B",{"three","four"}}},11);return x.valid&&x.lines==std::vector<std::string>{"* A one two","  - B three","      four"}?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;auto e=layout_bullets({},8);f+=!e.valid||!e.lines.empty();f+=layout_bullets({{0,"x",{"y"}}},9).valid;f+=layout_bullets({{-1,"",{"y"}}},9).valid;auto x=layout_bullets({{-1,"A",{"one","two"}}},8);f+=!x.valid||x.lines.size()!=2;return f;}
""",
        ("depth[i]=x.parent<0?0:depth[static_cast<std::size_t>(x.parent)]+1", "depth[i]=0", "all nesting is flattened"),
    ),
    _case(
        "reflow-markdown-blocks", "Fenced-block-aware prose reflow",
        "line-state classifier preserving complete fenced blocks",
        "reflow_markdown(lines,width)->MarkdownLayout",
        """Input is a vector of lines without newline bytes. A line exactly ``` opens or closes a fence. Fence lines and all enclosed lines are copied byte-for-byte. Outside fences, nonblank lines form whitespace-tokenized paragraphs and blank lines delimit them. Wrap prose to width 4..60. Indented or unclosed fences and overlong prose words are invalid. Empty input is valid.""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct MarkdownLayout{bool valid=false;std::vector<std::string> lines;};MarkdownLayout reflow_markdown(const std::vector<std::string>&,std::size_t); }
""",
        "reflow_markdown(const std::vector<std::string>& input,std::size_t width)", "MarkdownLayout",
        """#include "task.h"
#include <sstream>
namespace curriculum { MarkdownLayout reflow_markdown(const std::vector<std::string>& input,std::size_t width){MarkdownLayout o;if(width<4U||width>60U)return o;bool fence=false;std::vector<std::string> words;auto flush=[&](){std::string line;for(const auto&w:words){if(w.size()>width){o.valid=false;return false;}if(!line.empty()&&line.size()+1U+w.size()>width){o.lines.push_back(line);line=w;}else{if(!line.empty())line+=' ';line+=w;}}if(!line.empty())o.lines.push_back(line);words.clear();return true;};for(const auto&s:input){if(s.find('\n')!=std::string::npos)return{};std::size_t first=s.find_first_not_of(" \t");if(s!="```"&&first!=std::string::npos&&s.substr(first)=="```")return{};if(s=="```"){if(!fence&&!flush())return{};fence=!fence;o.lines.push_back(s);continue;}if(fence){o.lines.push_back(s);continue;}if(s.empty()){if(!flush())return{};if(!o.lines.empty()&&!o.lines.back().empty())o.lines.push_back("");continue;}std::istringstream in(s);for(std::string w;in>>w;)words.push_back(w);}if(fence||!flush())return{};while(!o.lines.empty()&&o.lines.back().empty())o.lines.pop_back();o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=reflow_markdown({"one two three","```"," a  b ","```","four"},7);return x.valid&&x.lines==std::vector<std::string>{"one two","three","```"," a  b ","```","four"}?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;f+=reflow_markdown({"```","x"},8).valid;f+=reflow_markdown({" ```","x"," ```"},20).valid;auto x=reflow_markdown({"","a  b"},4);f+=!x.valid||x.lines!=std::vector<std::string>{"a b"};f+=reflow_markdown({"longword"},4).valid;return f;}
""",
        ("if(fence){o.lines.push_back(s);continue;}", "if(fence){std::istringstream in(s);for(std::string w;in>>w;)words.push_back(w);continue;}", "fenced bytes are normalized"),
    ),
    _case(
        "layout-footnote-pages", "Footnote-reserving page layout",
        "longest-prefix page allocation with bottom-note reservation",
        "paginate_footnotes(lines,notes,page_rows)->FootnotePages",
        """Each body line cites zero or more unique note IDs. Notes have unique positive IDs and nonempty text. For each page choose the longest nonempty body prefix whose body rows plus one row per first-seen cited note fit page_rows 3..12. Notes appear on the earliest citing page in first-citation order. An uncatalogued citation or a body line that cannot fit is invalid. Empty body is valid.""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct BodyLine{std::string text;std::vector<int> notes;};struct Note{int id=0;std::string text;};struct FootnotePage{std::vector<std::string> body,notes;};struct FootnotePages{bool valid=false;std::vector<FootnotePage> pages;};FootnotePages paginate_footnotes(const std::vector<BodyLine>&,const std::vector<Note>&,std::size_t); }
""",
        "paginate_footnotes(const std::vector<BodyLine>& body,const std::vector<Note>& notes,std::size_t rows)", "FootnotePages",
        """#include "task.h"
#include <algorithm>
#include <map>
#include <set>
namespace curriculum { FootnotePages paginate_footnotes(const std::vector<BodyLine>& body,const std::vector<Note>& notes,std::size_t rows){FootnotePages o;if(rows<3U||rows>12U)return o;std::map<int,std::string> catalog;for(const auto&n:notes)if(n.id<=0||n.text.empty()||!catalog.emplace(n.id,n.text).second)return{};std::set<int> placed;for(std::size_t begin=0;begin<body.size();){std::size_t best=begin;std::vector<int> best_ids;std::vector<int> ids;for(std::size_t end=begin;end<body.size();++end){if(body[end].text.empty())return{};std::set<int> line_ids;for(int id:body[end].notes){if(!line_ids.insert(id).second||catalog.count(id)==0U)return{};if(placed.count(id)==0U&&std::find(ids.begin(),ids.end(),id)==ids.end())ids.push_back(id);}if(end-begin+1U+ids.size()<=rows){best=end+1U;best_ids=ids;}else break;}if(best==begin)return{};FootnotePage page;for(std::size_t i=begin;i<best;++i)page.body.push_back(body[i].text);for(int id:best_ids){page.notes.push_back("["+std::to_string(id)+"] "+catalog[id]);placed.insert(id);}o.pages.push_back(page);begin=best;}o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=paginate_footnotes({{"a",{1}},{"b",{2}},{"c",{}}},{{1,"n1"},{2,"n2"}},3);return x.valid&&x.pages.size()==2&&x.pages[0].body==std::vector<std::string>{"a"}&&x.pages[1].body.size()==2?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;auto e=paginate_footnotes({},{{1,"n"}},4);f+=!e.valid||!e.pages.empty();f+=paginate_footnotes({{"a",{2}}},{{1,"n"}},4).valid;f+=paginate_footnotes({{"a",{1,1}}},{{1,"n"}},4).valid;f+=paginate_footnotes({{"a",{1}}},{{1,""}},4).valid;auto x=paginate_footnotes({{"a",{1}},{"b",{1}}},{{1,"n"}},3);f+=!x.valid||x.pages.size()!=1;return f;}
""",
        ("if(end-begin+1U+ids.size()<=rows)", "if(end-begin+1U<=rows)", "body pagination ignores reserved note rows"),
    ),
    _case(
        "reflow-comment-prefixes", "Comment-prefix group reflow",
        "adjacent exact-prefix grouping with prefix-local continuation width",
        "reflow_comments(lines,width)->CommentLayout",
        """Every nonblank line starts with exactly `// ` or `# `. Adjacent lines with the same prefix form one paragraph; prefix changes and blank lines close a group. Collapse payload whitespace and wrap words to width 5..50, repeating the exact prefix on every output line. A prefix-only line is a retained blank comment. Malformed or overlong words are invalid.""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct CommentLayout{bool valid=false;std::vector<std::string> lines;};CommentLayout reflow_comments(const std::vector<std::string>&,std::size_t); }
""",
        "reflow_comments(const std::vector<std::string>& input,std::size_t width)", "CommentLayout",
        """#include "task.h"
#include <sstream>
namespace curriculum { CommentLayout reflow_comments(const std::vector<std::string>& input,std::size_t width){CommentLayout o;if(width<5U||width>50U)return o;std::string prefix;std::vector<std::string> words;auto flush=[&](){std::string line=prefix;for(const auto&w:words){if(prefix.size()+w.size()>width)return false;if(line.size()+(line==prefix?0U:1U)+w.size()>width){o.lines.push_back(line);line=prefix+w;}else{if(line!=prefix)line+=' ';line+=w;}}if(!words.empty())o.lines.push_back(line);words.clear();return true;};for(const auto&s:input){if(s.empty()){if(!flush())return{};prefix.clear();if(!o.lines.empty()&&!o.lines.back().empty())o.lines.push_back("");continue;}std::string p=s.rfind("// ",0)==0?"// ":s.rfind("# ",0)==0?"# ":"";if(p.empty())return{};if(!prefix.empty()&&p!=prefix){if(!flush())return{};}prefix=p;std::string payload=s.substr(p.size());if(payload.empty()){if(!flush())return{};o.lines.push_back(prefix);continue;}std::istringstream in(payload);for(std::string w;in>>w;)words.push_back(w);}if(!flush())return{};while(!o.lines.empty()&&o.lines.back().empty())o.lines.pop_back();o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=reflow_comments({"// one two","// three","# four"},9);return x.valid&&x.lines==std::vector<std::string>{"// one","// two","// three","# four"}?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;f+=reflow_comments({"bad"},8).valid;auto x=reflow_comments({"// ","# a"},8);f+=!x.valid||x.lines!=std::vector<std::string>{"// ","# a"};f+=reflow_comments({"// toolong"},7).valid;return f;}
""",
        ("if(!prefix.empty()&&p!=prefix)", "if(false&& !prefix.empty()&&p!=prefix)", "different prefixes are merged"),
    ),
    _case(
        "layout-terminal-columns", "ANSI-aware terminal columns",
        "SGR scanner with zero-cell escape spans and shared visible widths",
        "layout_terminal(rows,gutter)->TerminalLayout",
        """Lay out a rectangular table of cell strings. Complete ANSI CSI sequences of the form ESC `[` digits/semicolons `m` occupy zero display cells; every other byte occupies one. Reject malformed escapes, ragged rows, empty input, or gutter outside 1..4. Pad every nonfinal column to its family-wide visible maximum and preserve escape bytes exactly.""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct TerminalLayout{bool valid=false;std::vector<std::string> lines;std::vector<std::size_t> widths;};TerminalLayout layout_terminal(const std::vector<std::vector<std::string>>&,std::size_t); }
""",
        "layout_terminal(const std::vector<std::vector<std::string>>& rows,std::size_t gutter)", "TerminalLayout",
        """#include "task.h"
#include <algorithm>
namespace curriculum { namespace {bool cells(const std::string&s,std::size_t&n){n=0;for(std::size_t i=0;i<s.size();){if(static_cast<unsigned char>(s[i])==27U){if(i+2U>=s.size()||s[i+1U]!='[')return false;i+=2U;bool any=false;while(i<s.size()&&((s[i]>='0'&&s[i]<='9')||s[i]==';')){any=true;++i;}if(!any||i>=s.size()||s[i]!='m')return false;++i;}else{++n;++i;}}return true;}}TerminalLayout layout_terminal(const std::vector<std::vector<std::string>>& rows,std::size_t gutter){TerminalLayout o;if(rows.empty()||rows[0].empty()||gutter<1U||gutter>4U)return o;std::size_t cols=rows[0].size();o.widths.assign(cols,0);std::vector<std::vector<std::size_t>> measured;for(const auto&r:rows){if(r.size()!=cols)return{};measured.push_back({});for(std::size_t c=0;c<cols;++c){std::size_t n=0;if(!cells(r[c],n))return{};measured.back().push_back(n);o.widths[c]=std::max(o.widths[c],n);}}for(std::size_t r=0;r<rows.size();++r){std::string line;for(std::size_t c=0;c<cols;++c){line+=rows[r][c];if(c+1U<cols)line+=std::string(o.widths[c]-measured[r][c]+gutter,' ');}o.lines.push_back(line);}o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;std::string red="\x1b[31mA\x1b[0m";auto x=layout_terminal({{red,"x"},{"BBBB","y"}},1);return x.valid&&x.widths==std::vector<std::size_t>{4,1}&&x.lines[0]==red+"    x"?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;f+=layout_terminal({},1).valid;f+=layout_terminal({{"\x1b[31X"}},1).valid;f+=layout_terminal({{"a"},{"a","b"}},1).valid;auto x=layout_terminal({{"a","b"}},2);f+=!x.valid||x.lines[0]!="a  b";return f;}
""",
        ("if(static_cast<unsigned char>(s[i])==27U)", "if(false&&static_cast<unsigned char>(s[i])==27U)", "ANSI bytes are counted as visible cells"),
    ),
    _case(
        "layout-path-ellipsis", "Component-aware path ellipsis",
        "root/basename preservation with longest fitting suffix selection",
        "elide_path(path,width)->PathLayout",
        """Fit an absolute slash-delimited path to width 5..80. Components are nonempty and may not be `.` or `..`. If needed preserve `/`, the basename, and the longest contiguous suffix of preceding components separated from an `...` component. Longest retained suffix wins; equal byte fits prefer the earlier start. If root, ellipsis, and basename cannot fit, return invalid.""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct PathLayout{bool valid=false;std::string text;std::size_t omitted=0;};PathLayout elide_path(const std::string&,std::size_t); }
""",
        "elide_path(const std::string& path,std::size_t width)", "PathLayout",
        """#include "task.h"
namespace curriculum { PathLayout elide_path(const std::string& path,std::size_t width){PathLayout o;if(width<5U||width>80U||path.empty()||path[0]!='/')return o;std::vector<std::string> parts;for(std::size_t b=1;b<=path.size();){std::size_t e=path.find('/',b);if(e==std::string::npos)e=path.size();std::string p=path.substr(b,e-b);if(p.empty()||p=="."||p=="..")return{};parts.push_back(p);b=e+1U;}if(parts.empty())return o;if(path.size()<=width)return {true,path,0};std::string base="/.../"+parts.back();if(base.size()>width)return o;std::size_t start=parts.size()-1U;std::string best=base;for(std::size_t i=parts.size()-1U;i>0;--i){std::string candidate="/...";for(std::size_t j=i-1U;j<parts.size();++j)candidate+="/"+parts[j];if(candidate.size()>width)break;best=candidate;start=i-1U;}o.valid=true;o.text=best;o.omitted=start;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=elide_path("/alpha/beta/gamma/file.txt",24);return x.valid&&x.text=="/.../beta/gamma/file.txt"&&x.omitted==1?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;f+=elide_path("relative/a",10).valid;f+=elide_path("/a/../b",10).valid;auto x=elide_path("/a/b",20);f+=!x.valid||x.text!="/a/b";f+=elide_path("/longname",5).valid;return f;}
""",
        ("for(std::size_t i=parts.size()-1U;i>0;--i)", "for(std::size_t i=parts.size()-1U;i==0;--i)", "no preceding components are retained"),
    ),
    _case(
        "reflow-sentence-spacing", "Protected-span sentence spacing",
        "range-aware sentence terminal scanner and whitespace canonicalizer",
        "space_sentences(text,protected_ranges,double_gap)->SentenceLayout",
        """Protected half-open byte ranges are sorted, disjoint, nonempty, and copied byte-for-byte. Outside them collapse whitespace. After a maximal `.?!` terminal run use one or two spaces according to double_gap; otherwise use one. Never add leading/trailing space. NUL, out-of-range spans, or overlap is invalid. Valid empty input returns empty text.""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct ByteRange{std::size_t begin=0,end=0;};struct SentenceLayout{bool valid=false;std::string text;std::size_t sentence_gaps=0;};SentenceLayout space_sentences(const std::string&,const std::vector<ByteRange>&,bool); }
""",
        "space_sentences(const std::string& text,const std::vector<ByteRange>& ranges,bool double_gap)", "SentenceLayout",
        """#include "task.h"
#include <cctype>
namespace curriculum { SentenceLayout space_sentences(const std::string& text,const std::vector<ByteRange>& ranges,bool double_gap){SentenceLayout o;std::vector<int> owner(text.size(),-1);for(std::size_t r=0;r<ranges.size();++r){auto x=ranges[r];if(x.begin>=x.end||x.end>text.size()||(r>0U&&ranges[r-1U].end>x.begin))return o;for(std::size_t i=x.begin;i<x.end;++i)owner[i]=static_cast<int>(r);}bool pending=false,terminal=false;for(std::size_t i=0;i<text.size();){if(text[i]=='\0')return{};if(owner[i]>=0){if(pending&&!o.text.empty()){if(terminal){o.text+=double_gap?"  ":" ";++o.sentence_gaps;}else o.text+=' ';}pending=false;int r=owner[i];while(i<text.size()&&owner[i]==r)o.text+=text[i++];terminal=false;continue;}unsigned char c=static_cast<unsigned char>(text[i++]);if(std::isspace(c)){pending=true;continue;}if(pending&&!o.text.empty()){if(terminal){o.text+=double_gap?"  ":" ";++o.sentence_gaps;}else o.text+=' ';}pending=false;o.text+=static_cast<char>(c);terminal=c=='.'||c=='?'||c=='!'?true:false;}o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;std::string s="Hi!   CODE  X.  Next";auto x=space_sentences(s,{{6,13}},true);return x.valid&&x.text=="Hi!  CODE  X.  Next"&&x.sentence_gaps==2?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;auto e=space_sentences("",{},false);f+=!e.valid||!e.text.empty();f+=space_sentences("abc",{{1,4}},false).valid;f+=space_sentences("abc",{{0,2},{1,3}},false).valid;auto x=space_sentences(" A ?!   B ",{},false);f+=!x.valid||x.text!="A ?! B";return f;}
""",
        ("if(owner[i]>=0)", "if(false&&owner[i]>=0)", "protected bytes are normalized"),
    ),
    _case(
        "layout-outline-tree", "Connector-aware outline tree",
        "iterative DFS with ancestor last-sibling connector state",
        "render_outline(nodes)->OutlineLayout",
        """Nodes are in preorder and name their parent by earlier index; exactly one root is required. Render `+-- ` for nonfinal siblings and `\\-- ` for final siblings, with each ancestor contributing `|   ` while later siblings remain or four spaces otherwise. Names are nonempty and newline-free. The parent relation must match preorder and depth is at most 12.""",
        """#pragma once
#include <string>
#include <vector>
namespace curriculum { struct OutlineNode{int parent=-1;std::string name;};struct OutlineLayout{bool valid=false;std::vector<std::string> lines;};OutlineLayout render_outline(const std::vector<OutlineNode>&); }
""",
        "render_outline(const std::vector<OutlineNode>& nodes)", "OutlineLayout",
        """#include "task.h"
namespace curriculum {
OutlineLayout render_outline(const std::vector<OutlineNode>& nodes){
  OutlineLayout o;
  if(nodes.empty()||nodes[0].parent!=-1)return o;
  std::vector<std::size_t> depth(nodes.size());
  std::vector<std::size_t> open{0U};
  if(nodes[0].name.empty()||nodes[0].name.find('\n')!=std::string::npos)return o;
  for(std::size_t i=1;i<nodes.size();++i){
    const auto& n=nodes[i];
    if(n.name.empty()||n.name.find('\n')!=std::string::npos||n.parent<0||n.parent>=static_cast<int>(i))return{};
    depth[i]=depth[static_cast<std::size_t>(n.parent)]+1U;
    if(depth[i]>12U||open.size()<depth[i]||open[depth[i]-1U]!=static_cast<std::size_t>(n.parent))return{};
    open.resize(depth[i]);
    open.push_back(i);
  }
  std::vector<bool> last(nodes.size(),true);
  for(std::size_t i=0;i<nodes.size();++i){
    for(std::size_t j=i+1U;j<nodes.size();++j){
      if(depth[j]<depth[i])break;
      if(depth[j]==depth[i]){last[i]=false;break;}
    }
  }
  for(std::size_t i=0;i<nodes.size();++i){
    std::string line;
    std::vector<std::size_t> ancestors(depth[i]);
    int parent=nodes[i].parent;
    for(std::size_t d=depth[i];d>0U;--d){ancestors[d-1U]=static_cast<std::size_t>(parent);parent=nodes[static_cast<std::size_t>(parent)].parent;}
    for(std::size_t d=1U;d<depth[i];++d)line+=last[ancestors[d]]?"    ":"|   ";
    if(depth[i]>0U)line+=last[i]?"\\\\-- ":"+-- ";
    line+=nodes[i].name;
    o.lines.push_back(line);
  }
  o.valid=true;
  return o;
}
}
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=render_outline({{-1,"root"},{0,"a"},{1,"x"},{0,"b"}});return x.valid&&x.lines==std::vector<std::string>{"root","+-- a","|   \\\\-- x","\\\\-- b"}?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;f+=render_outline({}).valid;f+=render_outline({{-1,"a"},{-1,"b"}}).valid;f+=render_outline({{-1,"a"},{2,"b"}}).valid;auto x=render_outline({{-1,"a"},{0,"b"}});f+=!x.valid||x.lines[1]!="\\\\-- b";return f;}
""",
        ("line+=last[ancestors[d]]?\"    \":\"|   \"", "line+=std::string(ancestors[d]*0U+4U,' ')", "ancestor continuation connectors disappear"),
    ),
    _case(
        "reflow-log-continuations", "Timestamp gutter log reflow",
        "record parser with continuation attachment and measured gutter wrapping",
        "reflow_logs(lines,width)->LogLayout",
        """A record starts with `[dddd] ` where d is a digit. Lines beginning with two spaces continue the preceding record; other forms are invalid. Collapse payload whitespace, retain an empty continuation as an empty word boundary, and wrap under the seven-byte timestamp prefix, using seven blank bytes on continuations. Width is 9..50 and record order is stable. Orphan continuation and overlong word are invalid.""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct LogLayout{bool valid=false;std::vector<std::string> lines;std::size_t records=0;};LogLayout reflow_logs(const std::vector<std::string>&,std::size_t); }
""",
        "reflow_logs(const std::vector<std::string>& input,std::size_t width)", "LogLayout",
        """#include "task.h"
#include <cctype>
#include <sstream>
namespace curriculum { LogLayout reflow_logs(const std::vector<std::string>& input,std::size_t width){LogLayout o;if(width<9U||width>50U)return o;std::string stamp;std::vector<std::string> words;auto flush=[&](){if(stamp.empty())return true;std::string line=stamp;for(const auto&w:words){if(w.size()>width-stamp.size())return false;if(line.size()+(line==stamp?0U:1U)+w.size()>width){o.lines.push_back(line);line=std::string(stamp.size(),' ')+w;}else{if(line!=stamp)line+=' ';line+=w;}}o.lines.push_back(line);++o.records;words.clear();return true;};for(const auto&s:input){bool head=s.size()>=7U&&s[0]=='['&&s[5]==']'&&s[6]==' ';for(int i=1;i<=4&&head;++i)head=std::isdigit(static_cast<unsigned char>(s[static_cast<std::size_t>(i)]))!=0;if(head){if(!flush())return{};stamp=s.substr(0,7);}else if(s.rfind("  ",0)!=0||stamp.empty())return{};std::istringstream in(s.substr(head?7U:2U));for(std::string w;in>>w;)words.push_back(w);}if(!flush())return{};o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=reflow_logs({"[0001] alpha beta","  gamma","[0002] z"},12);return x.valid&&x.records==2&&x.lines==std::vector<std::string>{"[0001] alpha","       beta","       gamma","[0002] z"}?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;f+=reflow_logs({"  orphan"},12).valid;f+=reflow_logs({"[12] bad"},12).valid;auto x=reflow_logs({},12);f+=!x.valid||x.records!=0;f+=reflow_logs({"[0001] toolongword"},9).valid;return f;}
""",
        ("else if(s.rfind(\"  \",0)!=0||stamp.empty())return{};", "else if(s.rfind(\"  \",0)!=0)return{};", "orphan continuations are accepted"),
    ),
    _case(
        "layout-decimal-columns", "Lexical decimal column alignment",
        "three-field decimal lexeme validation and shared column maxima",
        "align_decimals(values)->DecimalLayout",
        """Align signed ASCII decimal lexemes without numeric conversion. A value has an optional leading sign, at least one digit before an optional point, and zero or more digits after it. Exponents and other bytes are invalid. Right-align integer fields, align points, and left-align fractional fields; absent points occupy a blank point cell. Valid empty input returns no lines.""",
        """#pragma once
#include <string>
#include <vector>
namespace curriculum { struct DecimalLayout{bool valid=false;std::vector<std::string> lines;std::size_t integer_width=0,fraction_width=0;};DecimalLayout align_decimals(const std::vector<std::string>&); }
""",
        "align_decimals(const std::vector<std::string>& values)", "DecimalLayout",
        """#include "task.h"
#include <algorithm>
#include <cctype>
namespace curriculum { DecimalLayout align_decimals(const std::vector<std::string>& values){DecimalLayout o;struct Part{std::string integer,fraction;bool point=false;};std::vector<Part> parts;for(const auto&s:values){if(s.empty())return{};std::size_t i=(s[0]=='+'||s[0]=='-')?1U:0U,start=i;if(i==s.size())return{};while(i<s.size()&&std::isdigit(static_cast<unsigned char>(s[i])))++i;if(i==start)return{};Part p{s.substr(0,i),"",false};if(i<s.size()&&s[i]=='.'){p.point=true;++i;std::size_t f=i;while(i<s.size()&&std::isdigit(static_cast<unsigned char>(s[i])))++i;p.fraction=s.substr(f);}if(i!=s.size())return{};o.integer_width=std::max(o.integer_width,p.integer.size());o.fraction_width=std::max(o.fraction_width,p.fraction.size());parts.push_back(p);}for(const auto&p:parts)o.lines.push_back(std::string(o.integer_width-p.integer.size(),' ')+p.integer+(p.point?".":" ")+p.fraction+std::string(o.fraction_width-p.fraction.size(),' '));o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=align_decimals({"1.2","-12","+3.45"});return x.valid&&x.lines==std::vector<std::string>{"  1.2 ","-12   "," +3.45"}?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;auto e=align_decimals({});f+=!e.valid||!e.lines.empty();f+=align_decimals({".2"}).valid;f+=align_decimals({"1e2"}).valid;auto x=align_decimals({"1."});f+=!x.valid||x.lines[0]!="1.";return f;}
""",
        ("std::string(o.integer_width-p.integer.size(),' ')", "std::string(0U,' ')", "integer fields are not aligned"),
    ),
    _case(
        "reflow-diff-hunks", "Marker-preserving diff hunk reflow",
        "hunk-state validation with marker-specific continuation wrapping",
        "reflow_diff(lines,width)->DiffLayout",
        """Copy lines beginning `@@` atomically and treat them as hunk headers. Within a hunk, lines beginning `+`, `-`, or one space are change/context payload. Wrap payload words to width 6..60; the first line keeps its marker and continuations use marker plus `>`. A change before a header, newline byte, empty payload, or overlong word is invalid.""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct DiffLayout{bool valid=false;std::vector<std::string> lines;std::size_t hunks=0;};DiffLayout reflow_diff(const std::vector<std::string>&,std::size_t); }
""",
        "reflow_diff(const std::vector<std::string>& input,std::size_t width)", "DiffLayout",
        """#include "task.h"
#include <sstream>
namespace curriculum { DiffLayout reflow_diff(const std::vector<std::string>& input,std::size_t width){DiffLayout o;if(width<6U||width>60U)return o;bool hunk=false;for(const auto&s:input){if(s.find('\n')!=std::string::npos)return{};if(s.rfind("@@",0)==0){o.lines.push_back(s);hunk=true;++o.hunks;continue;}if(!hunk||s.size()<2U||(s[0]!='+'&&s[0]!='-'&&s[0]!=' '))return{};std::istringstream in(s.substr(1));std::vector<std::string>w;for(std::string x;in>>x;)w.push_back(x);if(w.empty())return{};std::string prefix(1,s[0]),line=prefix;for(const auto&x:w){if(x.size()+2U>width)return{};if(line.size()+(line==prefix?0U:1U)+x.size()>width){o.lines.push_back(line);line=prefix+">"+x;}else{if(line!=prefix)line+=' ';line+=x;}}o.lines.push_back(line);}o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=reflow_diff({"@@ one","+alpha beta gamma"},9);return x.valid&&x.hunks==1&&x.lines==std::vector<std::string>{"@@ one","+alpha","+>beta","+>gamma"}?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;f+=reflow_diff({"+x"},8).valid;f+=reflow_diff({"@@ h","?x"},8).valid;auto x=reflow_diff({},8);f+=!x.valid||x.hunks!=0;f+=reflow_diff({"@@ h","+longword"},6).valid;return f;}
""",
        ("line=prefix+\">\"+x", "line=prefix+x", "continuation markers are omitted"),
    ),
    _case(
        "reflow-poetry-stanzas", "Caesura-only poetry reflow",
        "latest-fitting declared-cut selection with stanza preservation",
        "reflow_verse(lines,width)->VerseLayout",
        """Input lines contain verse bytes and optional caesura marker `|`; empty lines delimit stanzas. Remove a selected marker when splitting an overlong verse. Repeatedly choose the latest marker whose left segment fits width 3..40; trim one adjacent space at the cut but otherwise preserve bytes. A nonempty overlong segment without a legal marker, leading/trailing marker, or double marker is invalid.""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct VerseLayout{bool valid=false;std::vector<std::string> lines;std::size_t cuts=0;};VerseLayout reflow_verse(const std::vector<std::string>&,std::size_t); }
""",
        "reflow_verse(const std::vector<std::string>& input,std::size_t width)", "VerseLayout",
        """#include "task.h"
namespace curriculum { VerseLayout reflow_verse(const std::vector<std::string>& input,std::size_t width){VerseLayout o;if(width<3U||width>40U)return o;for(std::string s:input){if(s.empty()){o.lines.push_back("");continue;}if(s.front()=='|'||s.back()=='|'||s.find("||")!=std::string::npos)return{};while(s.size()>width){std::size_t cut=std::string::npos;for(std::size_t p=s.find('|');p!=std::string::npos&&p<=width;p=s.find('|',p+1U))cut=p;if(cut==std::string::npos)return{};std::string left=s.substr(0,cut);while(!left.empty()&&left.back()==' ')left.pop_back();if(left.empty())return{};for(char&c:left)if(c=='|')c=' ';o.lines.push_back(left);s=s.substr(cut+1U);if(!s.empty()&&s.front()==' ')s.erase(s.begin());++o.cuts;}for(char&c:s)if(c=='|')c=' ';o.lines.push_back(s);}while(!o.lines.empty()&&o.lines.back().empty())o.lines.pop_back();o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=reflow_verse({"red sky | over sea","","calm"},9);auto y=reflow_verse({"ab|cd|ef"},5);return x.valid&&x.cuts==1&&x.lines==std::vector<std::string>{"red sky","over sea","","calm"}&&y.valid&&y.cuts==1&&y.lines==std::vector<std::string>{"ab cd","ef"}?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;f+=reflow_verse({"toolong"},3).valid;f+=reflow_verse({"|bad"},5).valid;auto x=reflow_verse({"a|b"},10);f+=!x.valid||x.lines[0]!="a b";auto e=reflow_verse({},5);f+=!e.valid;return f;}
""",
        ("cut=p;", "if(cut==std::string::npos)cut=p;", "the earliest rather than latest fitting caesura is selected"),
    ),
    _case(
        "layout-template-slots", "Measured template slot layout",
        "placeholder expansion before wrapping with emitted offset ledger",
        "layout_template(segments,values,width)->TemplateLayout",
        """Segments are literal bytes or named slots. Values have unique nonempty names and byte strings. Expand each slot atomically before layout, wrap only between segments to width 4..60, and report each slot's output line and byte column. Unknown or duplicate slots, whitespace inside names, newline bytes, or a segment wider than width is invalid. Empty segments are valid and ignored.""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct TemplateSegment{bool slot=false;std::string text;};struct SlotValue{std::string name,value;};struct SlotOffset{std::string name;std::size_t line=0,column=0;};struct TemplateLayout{bool valid=false;std::vector<std::string> lines;std::vector<SlotOffset> offsets;};TemplateLayout layout_template(const std::vector<TemplateSegment>&,const std::vector<SlotValue>&,std::size_t); }
""",
        "layout_template(const std::vector<TemplateSegment>& segs,const std::vector<SlotValue>& values,std::size_t width)", "TemplateLayout",
        """#include "task.h"
#include <map>
#include <set>
namespace curriculum { TemplateLayout layout_template(const std::vector<TemplateSegment>& segs,const std::vector<SlotValue>& values,std::size_t width){TemplateLayout o;if(width<4U||width>60U)return o;std::map<std::string,std::string> map;for(const auto&v:values)if(v.name.empty()||v.name.find_first_of(" \t\n")!=std::string::npos||v.value.find('\n')!=std::string::npos||!map.emplace(v.name,v.value).second)return{};std::set<std::string> used;std::string line;for(const auto&s:segs){std::string part=s.text;if(s.slot){auto it=map.find(s.text);if(it==map.end())return{};part=it->second;used.insert(s.text);}if(part.empty())continue;if(part.size()>width)return{};if(!line.empty()&&line.size()+1U+part.size()>width){o.lines.push_back(line);line.clear();}if(s.slot)o.offsets.push_back({s.text,o.lines.size(),line.empty()?0U:line.size()+1U});if(!line.empty())line+=' ';line+=part;}if(used.size()!=map.size())return{};if(!line.empty())o.lines.push_back(line);o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=layout_template({{false,"Hi"},{true,"who"},{false,"today"}},{{"who","Ada"}},8);return x.valid&&x.lines==std::vector<std::string>{"Hi Ada","today"}&&x.offsets[0].column==3?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;f+=layout_template({{true,"x"}},{{}},8).valid;f+=layout_template({},{{"x","a"},{"x","b"}},8).valid;f+=layout_template({},{{"unused","value"}},8).valid;auto e=layout_template({}, {},8);f+=!e.valid||!e.lines.empty();auto x=layout_template({{false,"a"},{true,"x"}},{{"x","b"}},4);f+=!x.valid||x.offsets[0].column!=2;return f;}
""",
        ("part=it->second;", "part=s.text;", "slot names are measured instead of expansions"),
    ),
    _case(
        "layout-gutter-line-numbers", "Stable line-number gutter layout",
        "final-number digit measurement with continuation gutters",
        "number_and_wrap(lines,start,width)->GutterLayout",
        """Number every source line starting at a positive integer. Compute one gutter width from the final number. Prefix first wrapped row with the right-aligned number plus ` | ` and continuations with equal blank gutter plus ` | `. Split payload on ASCII whitespace and wrap to width 8..70. Blank source lines emit a numbered empty payload. Overflow and overlong words are invalid.""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct GutterLayout{bool valid=false;std::vector<std::string> lines;std::size_t gutter=0;};GutterLayout number_and_wrap(const std::vector<std::string>&,std::size_t,std::size_t); }
""",
        "number_and_wrap(const std::vector<std::string>& input,std::size_t start,std::size_t width)", "GutterLayout",
        """#include "task.h"
#include <limits>
#include <sstream>
namespace curriculum { GutterLayout number_and_wrap(const std::vector<std::string>& input,std::size_t start,std::size_t width){GutterLayout o;if(start==0U||width<8U||width>70U||(!input.empty()&&start>std::numeric_limits<std::size_t>::max()-input.size()+1U))return o;std::size_t last=input.empty()?start:start+input.size()-1U;o.gutter=std::to_string(last).size();std::size_t cap=width-o.gutter-3U;if(cap==0U)return o;for(std::size_t i=0;i<input.size();++i){std::istringstream in(input[i]);std::vector<std::string>w;for(std::string x;in>>x;)w.push_back(x);std::vector<std::string> rows(1);for(const auto&x:w){if(x.size()>cap)return{};if(!rows.back().empty()&&rows.back().size()+1U+x.size()>cap)rows.push_back(x);else{if(!rows.back().empty())rows.back()+=' ';rows.back()+=x;}}for(std::size_t r=0;r<rows.size();++r){std::string number=r==0?std::to_string(start+i):"";o.lines.push_back(std::string(o.gutter-number.size(),' ')+number+" | "+rows[r]);}}o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=number_and_wrap({"a b c",""},9,8);return x.valid&&x.gutter==2&&x.lines==std::vector<std::string>{" 9 | a b","   | c","10 | "}?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;f+=number_and_wrap({"x"},0,9).valid;auto e=number_and_wrap({},1,9);f+=!e.valid||!e.lines.empty();f+=number_and_wrap({"toolong"},1,8).valid;auto x=number_and_wrap({"a"},99,9);f+=!x.valid||x.gutter!=2;return f;}
""",
        ("std::size_t last=input.empty()?start:start+input.size()-1U;o.gutter=std::to_string(last).size();", "o.gutter=std::to_string(start).size();", "gutter width is recomputed from the first number"),
    ),
    _case(
        "layout-ruler-tabs", "Repeating ruler tab expansion",
        "cyclic tab-stop expansion with source-to-output column map",
        "expand_ruler_tabs(text,stops)->TabLayout",
        """Expand ASCII tab bytes against strictly increasing positive stops in one cycle. After the last stop, repeat the cycle width. A tab exactly on a stop advances to the next stop. Newline resets the column and is copied. Return every source byte's output column before expansion. Empty text is valid; CR, empty stops, duplicates, or a zero cycle are invalid.""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct TabLayout{bool valid=false;std::string text;std::vector<std::size_t> source_columns;};TabLayout expand_ruler_tabs(const std::string&,const std::vector<std::size_t>&); }
""",
        "expand_ruler_tabs(const std::string& text,const std::vector<std::size_t>& stops)", "TabLayout",
        """#include "task.h"
namespace curriculum { TabLayout expand_ruler_tabs(const std::string& text,const std::vector<std::size_t>& stops){TabLayout o;if(stops.empty()||stops[0]==0U)return o;for(std::size_t i=1;i<stops.size();++i)if(stops[i]<=stops[i-1U])return o;std::size_t cycle=stops.back(),column=0;for(char c:text){o.source_columns.push_back(column);if(c=='\r')return{};if(c=='\n'){o.text+=c;column=0;continue;}if(c!='\t'){o.text+=c;++column;continue;}std::size_t base=(column/cycle)*cycle,next=0;for(std::size_t stop:stops)if(base+stop>column){next=base+stop;break;}if(next==0)next=base+cycle+stops[0];o.text+=std::string(next-column,' ');column=next;}o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=expand_ruler_tabs("a\tb\t",{4,8});return x.valid&&x.text=="a   b   "&&x.source_columns==std::vector<std::size_t>{0,1,4,5}?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;f+=expand_ruler_tabs("x",{}).valid;f+=expand_ruler_tabs("x",{4,4}).valid;auto e=expand_ruler_tabs("",{4});f+=!e.valid||!e.text.empty();auto x=expand_ruler_tabs("1234\t",{4,8});f+=!x.valid||x.text!="1234    ";return f;}
""",
        ("if(base+stop>column)", "if(base+stop>=column)", "a tab on a stop fails to advance"),
    ),
    _case(
        "layout-leader-lines", "Shared-width dotted leader layout",
        "global page-number width and exact dot allocation",
        "leader_lines(entries,width)->LeaderLayout",
        """Entries have a nonempty label without dot/newline and a positive page number. Width is 8..60. Compute the shared page-number width, left-align labels, allocate at least two dots, and right-align every page number. Preserve entry order. Duplicate labels and any row that cannot provide two dots are invalid. Empty input is valid.""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct LeaderEntry{std::string label;std::size_t page=0;};struct LeaderLayout{bool valid=false;std::vector<std::string> lines;std::size_t number_width=0;};LeaderLayout leader_lines(const std::vector<LeaderEntry>&,std::size_t); }
""",
        "leader_lines(const std::vector<LeaderEntry>& entries,std::size_t width)", "LeaderLayout",
        """#include "task.h"
#include <algorithm>
#include <set>
namespace curriculum { LeaderLayout leader_lines(const std::vector<LeaderEntry>& entries,std::size_t width){LeaderLayout o;if(width<8U||width>60U)return o;std::set<std::string> labels;for(const auto&e:entries){if(e.label.empty()||e.page==0U||e.label.find_first_of(".\n")!=std::string::npos||!labels.insert(e.label).second)return{};o.number_width=std::max(o.number_width,std::to_string(e.page).size());}for(const auto&e:entries){std::string number=std::to_string(e.page);if(e.label.size()+2U+o.number_width>width)return{};std::size_t dots=width-e.label.size()-o.number_width;o.lines.push_back(e.label+std::string(dots,'.')+std::string(o.number_width-number.size(),' ')+number);}o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=leader_lines({{"Intro",120},{"End",2}},12);return x.valid&&x.number_width==3&&x.lines==std::vector<std::string>{"Intro....120","End......  2"}?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;auto e=leader_lines({},8);f+=!e.valid;f+=leader_lines({{"A",1},{"A",2}},8).valid;f+=leader_lines({{"longname",1}},8).valid;auto x=leader_lines({{"A",9}},8);f+=!x.valid||x.lines[0]!="A......9";return f;}
""",
        ("o.number_width=std::max(o.number_width,std::to_string(e.page).size());", "o.number_width=std::to_string(e.page).size();", "only the last page controls number width"),
    ),
    _case(
        "reflow-rfc-headers", "Atomic-clause header folding",
        "field validator and semicolon-clause boundary folding",
        "fold_header(name,clauses,width)->HeaderLayout",
        """Validate a nonempty field name of ASCII letters/digits/hyphen and nonempty clauses without CR/LF or semicolon. Emit `Name: clause` then append `; clause` while it fits width 8..72; otherwise start a continuation with one space plus the clause. Clauses are atomic, order is stable, and an overlong first or continuation row is invalid. Empty clause input is invalid.""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct HeaderLayout{bool valid=false;std::vector<std::string> lines;};HeaderLayout fold_header(const std::string&,const std::vector<std::string>&,std::size_t); }
""",
        "fold_header(const std::string& name,const std::vector<std::string>& clauses,std::size_t width)", "HeaderLayout",
        """#include "task.h"
#include <cctype>
namespace curriculum { HeaderLayout fold_header(const std::string& name,const std::vector<std::string>& clauses,std::size_t width){HeaderLayout o;if(name.empty()||clauses.empty()||width<8U||width>72U)return o;for(char c:name)if(!(std::isalnum(static_cast<unsigned char>(c))||c=='-'))return{};std::string line=name+": ";for(const auto&clause:clauses){if(clause.empty()||clause.find_first_of(";\r\n")!=std::string::npos)return{};std::string piece=(line==name+": "?"":"; ")+clause;if(line.size()+piece.size()<=width)line+=piece;else{if(line==name+": ")return{};o.lines.push_back(line);line=" "+clause;if(line.size()>width)return{};}}o.lines.push_back(line);o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=fold_header("Cache-Control",{"max-age=0","private","must-revalidate"},25);return x.valid&&x.lines==std::vector<std::string>{"Cache-Control: max-age=0"," private; must-revalidate"}?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;f+=fold_header("Bad Name",{"x"},20).valid;f+=fold_header("X",{},20).valid;f+=fold_header("X",{"a;b"},20).valid;auto x=fold_header("X",{"a","b"},20);f+=!x.valid||x.lines.size()!=1;return f;}
""",
        ("line=\" \"+clause", "line=clause", "continuation whitespace is omitted"),
    ),
    _case(
        "layout-glyph-kerning", "Blank-column glyph kerning",
        "pairwise maximum safe blank-column overlap composition",
        "kern_glyphs(glyphs)->GlyphLayout",
        """Each glyph is a nonempty rectangular ASCII bitmap using space for blank and any other byte for ink. Compose glyphs horizontally. For each next glyph remove the maximum number of overlapping boundary columns for which no row has ink in both glyphs; preserve at least one column from every glyph. Ragged/unequal-height glyphs are invalid. Empty glyph list is valid.""",
        """#pragma once
#include <string>
#include <vector>
namespace curriculum { struct Glyph{std::vector<std::string> rows;};struct GlyphLayout{bool valid=false;std::vector<std::string> rows;std::vector<std::size_t> overlaps;};GlyphLayout kern_glyphs(const std::vector<Glyph>&); }
""",
        "kern_glyphs(const std::vector<Glyph>& glyphs)", "GlyphLayout",
        """#include "task.h"
#include <algorithm>
namespace curriculum { GlyphLayout kern_glyphs(const std::vector<Glyph>& glyphs){GlyphLayout o;if(glyphs.empty()){o.valid=true;return o;}std::size_t height=glyphs[0].rows.size();if(height==0U)return o;auto valid=[&](const Glyph&g){if(g.rows.size()!=height||g.rows.empty()||g.rows[0].empty())return false;for(const auto&r:g.rows)if(r.size()!=g.rows[0].size())return false;return true;};if(!valid(glyphs[0]))return o;o.rows=glyphs[0].rows;for(std::size_t k=1;k<glyphs.size();++k){if(!valid(glyphs[k]))return{};std::size_t cap=std::min(o.rows[0].size(),glyphs[k].rows[0].size())-1U,best=0;for(std::size_t overlap=1;overlap<=cap;++overlap){bool safe=true;for(std::size_t r=0;r<height&&safe;++r)for(std::size_t c=0;c<overlap;++c)if(o.rows[r][o.rows[r].size()-overlap+c]!=' '&&glyphs[k].rows[r][c]!=' ')safe=false;if(safe)best=overlap;}o.overlaps.push_back(best);for(std::size_t r=0;r<height;++r){for(std::size_t c=0;c<best;++c)if(o.rows[r][o.rows[r].size()-best+c]==' ')o.rows[r][o.rows[r].size()-best+c]=glyphs[k].rows[r][c];o.rows[r]+=glyphs[k].rows[r].substr(best);}}o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=kern_glyphs({{{"X "," X"}},{{"Y "," Y"}}});return x.valid&&x.overlaps==std::vector<std::size_t>{1}&&x.rows==std::vector<std::string>{"XY "," XY"}?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;auto e=kern_glyphs({});f+=!e.valid||!e.rows.empty();f+=kern_glyphs({{{"x","yy"}}}).valid;auto x=kern_glyphs({{{"X "}},{{" Y"}}});f+=!x.valid||x.overlaps[0]!=1;return f;}
""",
        ("if(safe)best=overlap;", "if(false&&safe)best=overlap;", "all safe overlap is disabled"),
    ),
    _case(
        "reflow-punctuation-glue", "Punctuation-aware group reflow",
        "balanced punctuation scanner with glued token groups",
        "reflow_punctuation(tokens,width)->PunctuationLayout",
        """Tokens are words or one-byte punctuation from `([{`, `)]}`, and `,.;:!?`. Opening punctuation glues to the following group, closing/suffix punctuation glues to the preceding group, and groups wrap at spaces to width 3..50. Brackets must balance by type; leading closers, trailing openers, empty tokens, or a group wider than width are invalid. Empty input is valid.""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct PunctuationLayout{bool valid=false;std::vector<std::string> lines;};PunctuationLayout reflow_punctuation(const std::vector<std::string>&,std::size_t); }
""",
        "reflow_punctuation(const std::vector<std::string>& tokens,std::size_t width)", "PunctuationLayout",
        """#include "task.h"
namespace curriculum { PunctuationLayout reflow_punctuation(const std::vector<std::string>& tokens,std::size_t width){PunctuationLayout o;if(width<3U||width>50U)return o;std::vector<std::string> groups;std::string pending,stack;auto open=[](char c){return c=='('||c=='['||c=='{';};auto close=[](char c){return c==')'||c==']'||c=='}';};for(const auto&t:tokens){if(t.empty()||t.find_first_of(" \t\n\r")!=std::string::npos)return{};if(t.size()==1U&&open(t[0])){pending+=t;stack+=t;continue;}if(t.size()==1U&&(close(t[0])||std::string(",.;:!?").find(t[0])!=std::string::npos)){if(groups.empty())return{};if(close(t[0])){if(stack.empty()||std::string("([{ ").find(stack.back())!=std::string("([{ ").find(t[0]==')'?'(':t[0]==']'?'[':'{'))return{};stack.pop_back();}groups.back()+=t;continue;}groups.push_back(pending+t);pending.clear();}if(!pending.empty()||!stack.empty())return{};std::string line;for(const auto&g:groups){if(g.size()>width)return{};if(!line.empty()&&line.size()+1U+g.size()>width){o.lines.push_back(line);line=g;}else{if(!line.empty())line+=' ';line+=g;}}if(!line.empty())o.lines.push_back(line);o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=reflow_punctuation({"(","hello",",","world","!", ")"},12);return x.valid&&x.lines==std::vector<std::string>{"(hello,","world!)"}?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;auto e=reflow_punctuation({},5);f+=!e.valid;f+=reflow_punctuation({")","x"},5).valid;f+=reflow_punctuation({"(","x", "]"},5).valid;f+=reflow_punctuation({"two words"},20).valid;auto x=reflow_punctuation({"a",",","b"},4);f+=!x.valid||x.lines!=std::vector<std::string>{"a, b"};return f;}
""",
        ("groups.back()+=t;", "groups.push_back(t);", "suffix punctuation becomes a separate spaced group"),
    ),
    _case(
        "layout-snake-columns", "Alternating snake column layout",
        "column-major alternating-direction placement with shared widths",
        "snake_columns(lines,columns,gutter)->SnakeLayout",
        """Place nonempty newline-free lines into exactly `columns` nonempty columns. Column heights differ by at most one; even columns fill top-down and odd columns bottom-up. Render rows left-to-right using each column's maximum width and gutter 1..4. Columns are 1..line count and input order is consumed once. Empty input is valid only with columns zero.""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct SnakeLayout{bool valid=false;std::vector<std::string> rows;std::vector<std::size_t> widths;};SnakeLayout snake_columns(const std::vector<std::string>&,std::size_t,std::size_t); }
""",
        "snake_columns(const std::vector<std::string>& lines,std::size_t columns,std::size_t gutter)", "SnakeLayout",
        """#include "task.h"
#include <algorithm>
namespace curriculum { SnakeLayout snake_columns(const std::vector<std::string>& lines,std::size_t columns,std::size_t gutter){SnakeLayout o;if(lines.empty()){o.valid=columns==0U;return o;}if(columns==0U||columns>lines.size()||gutter<1U||gutter>4U)return o;for(const auto&s:lines)if(s.empty()||s.find('\n')!=std::string::npos)return{};std::size_t base=lines.size()/columns,extra=lines.size()%columns,pos=0,max_rows=base+(extra?1U:0U);std::vector<std::vector<std::string>> grid(columns);o.widths.assign(columns,0);for(std::size_t c=0;c<columns;++c){std::size_t h=base+(c<extra?1U:0U);grid[c].resize(h);for(std::size_t r=0;r<h;++r){std::size_t target=c%2U==0U?r:h-1U-r;grid[c][target]=lines[pos++];o.widths[c]=std::max(o.widths[c],grid[c][target].size());}}for(std::size_t r=0;r<max_rows;++r){std::size_t last=columns;while(last>0U&&r>=grid[last-1U].size())--last;std::string row;for(std::size_t c=0;c<last;++c){std::string cell=grid[c][r];row+=cell;if(c+1U<last)row+=std::string(o.widths[c]-cell.size()+gutter,' ');}o.rows.push_back(row);}o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=snake_columns({"a","bb","c","dd","e"},2,1);return x.valid&&x.rows==std::vector<std::string>{"a  e","bb dd","c"}?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;auto e=snake_columns({},0,1);f+=!e.valid;f+=snake_columns({"a"},2,1).valid;f+=snake_columns({""},1,1).valid;auto x=snake_columns({"a","b"},1,1);f+=!x.valid||x.rows.size()!=2;return f;}
""",
        ("c%2U==0U?r:h-1U-r", "r", "every column fills top-down"),
    ),
    _case(
        "layout-caption-skyline", "Caption box skyline packing",
        "lowest-y leftmost rectangle placement over a skyline vector",
        "pack_captions(boxes,canvas_width,canvas_height)->CaptionLayout",
        """Pack positive-width/height caption boxes in input order into a bounded canvas. For each box evaluate every fitting x, choose the placement with minimum resulting y and then smallest x, and raise the skyline across its span. Reject duplicate IDs, zero dimensions, overflow, or an impossible placement atomically. Empty boxes are valid.""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct CaptionBox{std::string id;std::size_t width=0,height=0;};struct CaptionPlacement{std::string id;std::size_t x=0,y=0;};struct CaptionLayout{bool valid=false;std::vector<CaptionPlacement> placements;std::size_t used_height=0;};CaptionLayout pack_captions(const std::vector<CaptionBox>&,std::size_t,std::size_t); }
""",
        "pack_captions(const std::vector<CaptionBox>& boxes,std::size_t width,std::size_t height)", "CaptionLayout",
        """#include "task.h"
#include <algorithm>
#include <limits>
#include <set>
namespace curriculum { CaptionLayout pack_captions(const std::vector<CaptionBox>& boxes,std::size_t width,std::size_t height){CaptionLayout o;if(width==0U||height==0U)return o;std::vector<std::size_t> sky(width);std::set<std::string> ids;for(const auto&b:boxes){if(b.id.empty()||b.width==0U||b.height==0U||b.width>width||!ids.insert(b.id).second)return{};std::size_t best_y=std::numeric_limits<std::size_t>::max(),best_x=0;for(std::size_t x=0;x+b.width<=width;++x){std::size_t y=*std::max_element(sky.begin()+static_cast<std::ptrdiff_t>(x),sky.begin()+static_cast<std::ptrdiff_t>(x+b.width));if(y<=height&&b.height<=height-y&&(y<best_y||(y==best_y&&x<best_x))){best_y=y;best_x=x;}}if(best_y==std::numeric_limits<std::size_t>::max())return{};for(std::size_t x=best_x;x<best_x+b.width;++x)sky[x]=best_y+b.height;o.placements.push_back({b.id,best_x,best_y});o.used_height=std::max(o.used_height,best_y+b.height);}o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=pack_captions({{"a",2,2},{"b",2,1},{"c",3,1}},4,4);return x.valid&&x.placements[0].x==0&&x.placements[1].x==2&&x.placements[2].y==2?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;auto e=pack_captions({},3,3);f+=!e.valid||!e.placements.empty();f+=pack_captions({{"a",1,1},{"a",1,1}},3,3).valid;f+=pack_captions({{"x",4,1}},3,3).valid;auto x=pack_captions({{"x",3,3}},3,3);f+=!x.valid||x.used_height!=3;return f;}
""",
        ("y<best_y||(y==best_y&&x<best_x)", "y<best_y||(y==best_y&&x>best_x)", "equal-height placements choose the rightmost position"),
    ),
    _case(
        "reflow-alternating-justification", "Alternating remainder justification",
        "greedy lines with parity-directed exact gap remainder distribution",
        "justify_cadence(words,width)->CadenceLayout",
        """Greedily form lines from nonempty whitespace-free words at width 3..40. Fully justify every nonfinal multiword line. On nonfinal line zero distribute remainder spaces left-to-right, on line one right-to-left, and alternate thereafter. Single-word and final lines are left aligned without trailing spaces. Empty input is valid.""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct CadenceLayout{bool valid=false;std::vector<std::string> lines;};CadenceLayout justify_cadence(const std::vector<std::string>&,std::size_t); }
""",
        "justify_cadence(const std::vector<std::string>& words,std::size_t width)", "CadenceLayout",
        """#include "task.h"
namespace curriculum { CadenceLayout justify_cadence(const std::vector<std::string>& words,std::size_t width){CadenceLayout o;if(width<3U||width>40U)return o;std::vector<std::vector<std::string>> lines;for(const auto&w:words){if(w.empty()||w.find_first_of(" \t\n")!=std::string::npos||w.size()>width)return{};if(lines.empty())lines.push_back({});std::size_t used=0;for(const auto&x:lines.back())used+=x.size();if(!lines.back().empty()&&used+lines.back().size()+w.size()>width)lines.push_back({});lines.back().push_back(w);}for(std::size_t row=0;row<lines.size();++row){const auto&line=lines[row];if(row+1U==lines.size()||line.size()<2U){std::string s;for(const auto&w:line){if(!s.empty())s+=' ';s+=w;}o.lines.push_back(s);continue;}std::size_t letters=0;for(const auto&w:line)letters+=w.size();std::size_t gaps=line.size()-1U,spaces=width-letters,each=spaces/gaps,extra=spaces%gaps;std::string s=line[0];for(std::size_t g=0;g<gaps;++g){bool bonus=row%2U==0U?g<extra:g>=gaps-extra;s+=std::string(each+(bonus?1U:0U),' ')+line[g+1U];}o.lines.push_back(s);}o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=justify_cadence({"a","b","c","d","e","f","g"},6);return x.valid&&x.lines==std::vector<std::string>{"a  b c","d e  f","g"}?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;auto e=justify_cadence({},5);f+=!e.valid||!e.lines.empty();f+=justify_cadence({"a b"},5).valid;f+=justify_cadence({"long"},3).valid;auto x=justify_cadence({"a","b"},5);f+=!x.valid||x.lines[0]!="a b";return f;}
""",
        ("row%2U==0U?g<extra:g>=gaps-extra", "g<extra", "all remainders are assigned from the left"),
    ),
    _case(
        "layout-print-regions", "Side-by-side print regions",
        "fixed-height body partition with repeated headers and horizontal rendering",
        "print_regions(header,lines,body_rows,gutter)->RegionLayout",
        """Partition ordered body lines into regions of exactly `body_rows` content rows. Repeat the nonempty header at row zero of every region. Render regions side-by-side, using each region's maximum width and gutter 1..4; pad the short final region with blank rows. Body rows are 1..8 and body lines are newline-free. Empty body is valid and emits no regions.""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct RegionLayout{bool valid=false;std::vector<std::string> rows;std::size_t regions=0;};RegionLayout print_regions(const std::string&,const std::vector<std::string>&,std::size_t,std::size_t); }
""",
        "print_regions(const std::string& header,const std::vector<std::string>& lines,std::size_t body_rows,std::size_t gutter)", "RegionLayout",
        """#include "task.h"
#include <algorithm>
namespace curriculum { RegionLayout print_regions(const std::string& header,const std::vector<std::string>& lines,std::size_t body_rows,std::size_t gutter){RegionLayout o;if(header.empty()||header.find('\n')!=std::string::npos||body_rows<1U||body_rows>8U||gutter<1U||gutter>4U)return o;for(const auto&s:lines)if(s.find('\n')!=std::string::npos)return{};if(lines.empty()){o.valid=true;return o;}o.regions=(lines.size()+body_rows-1U)/body_rows;std::vector<std::vector<std::string>> cells(o.regions,std::vector<std::string>(body_rows+1U));std::vector<std::size_t> widths(o.regions,header.size());for(std::size_t c=0;c<o.regions;++c){cells[c][0]=header;for(std::size_t r=0;r<body_rows&&c*body_rows+r<lines.size();++r){cells[c][r+1U]=lines[c*body_rows+r];widths[c]=std::max(widths[c],cells[c][r+1U].size());}}for(std::size_t r=0;r<=body_rows;++r){std::string row;for(std::size_t c=0;c<o.regions;++c){row+=cells[c][r];if(c+1U<o.regions)row+=std::string(widths[c]-cells[c][r].size()+gutter,' ');}o.rows.push_back(row);}o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=print_regions("H",{"a","bb","c"},2,1);return x.valid&&x.regions==2&&x.rows==std::vector<std::string>{"H  H","a  c","bb "}?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;auto e=print_regions("H",{},2,1);f+=!e.valid||e.regions!=0;f+=print_regions("",{"a"},2,1).valid;f+=print_regions("H",{"a\nb"},2,1).valid;auto x=print_regions("H",{"a"},1,1);f+=!x.valid||x.rows.size()!=2;return f;}
""",
        ("cells[c][0]=header;", "if(c==0U)cells[c][0]=header;", "headers are not repeated"),
    ),
    _case(
        "reflow-escaped-whitespace", "Escape-aware whitespace reflow",
        "single-pass protected escape scanner and unescaped run canonicalization",
        "reflow_escapes(text)->EscapeLayout",
        """A backslash escapes exactly the next byte. Escaped spaces, tabs, and LF bytes are copied as literal bytes and never delimit words or paragraphs. Unescaped spaces/tabs collapse to one space; unescaped LF runs collapse to one LF. Remove leading/trailing canonical whitespace. A dangling backslash, CR, or NUL is invalid. Empty input is valid.""",
        """#pragma once
#include <string>
namespace curriculum { struct EscapeLayout{bool valid=false;std::string text;std::size_t escaped=0;};EscapeLayout reflow_escapes(const std::string&); }
""",
        "reflow_escapes(const std::string& text)", "EscapeLayout",
        r"""#include "task.h"
namespace curriculum { EscapeLayout reflow_escapes(const std::string& text){EscapeLayout o;bool pending=false,newline=false;auto flush=[&](){if(pending&&!o.text.empty())o.text+=newline?'\n':' ';pending=false;newline=false;};for(std::size_t i=0;i<text.size();++i){char c=text[i];if(c=='\0'||c=='\r')return{};if(c=='\\'){if(i+1U>=text.size())return{};flush();o.text+=text[++i];++o.escaped;continue;}if(c==' '||c=='\t'||c=='\n'){pending=true;newline=newline||c=='\n';continue;}flush();o.text+=c;}o.valid=true;return o;} }
""",
        r"""#include "task.h"
int main(){using namespace curriculum;auto x=reflow_escapes(" a\\  \t b\\\n c ");return x.valid&&x.text=="a  b\n c"&&x.escaped==2?0:1;}
""",
        r"""#include "task.h"
int main(){using namespace curriculum;int f=0;auto e=reflow_escapes("");f+=!e.valid||!e.text.empty();f+=reflow_escapes("x\\").valid;f+=reflow_escapes("x\r").valid;auto x=reflow_escapes("a  b");f+=!x.valid||x.text!="a b";return f;}
""",
        ("o.text+=text[++i];", "pending=true;++i;", "escaped whitespace is normalized"),
    ),
    _case(
        "reflow-query-folding", "Atomic query parameter folding",
        "validated key/value atom parser with boundary-only folding",
        "fold_query(query,width,continuation)->QueryLayout",
        """Parse a nonempty ASCII query as `key=value` atoms separated by `&`. Keys are unique and alphanumeric/hyphen; values are nonempty and may contain valid `%HH` triplets but no raw `&` or `=`. Fold only between whole atoms to width 8..72. First line has no prefix; continuations use the supplied nonempty space-only prefix. Preserve atom order and separators.""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct QueryLayout{bool valid=false;std::vector<std::string> lines;std::size_t parameters=0;};QueryLayout fold_query(const std::string&,std::size_t,const std::string&); }
""",
        "fold_query(const std::string& query,std::size_t width,const std::string& continuation)", "QueryLayout",
        """#include "task.h"
#include <cctype>
#include <set>
namespace curriculum { QueryLayout fold_query(const std::string& query,std::size_t width,const std::string& continuation){QueryLayout o;if(query.empty()||width<8U||width>72U||continuation.empty()||continuation.find_first_not_of(' ')!=std::string::npos)return o;std::vector<std::string> atoms;std::set<std::string> keys;for(std::size_t b=0;b<=query.size();){std::size_t e=query.find('&',b);if(e==std::string::npos)e=query.size();std::string atom=query.substr(b,e-b);std::size_t eq=atom.find('=');if(eq==0U||eq==std::string::npos||eq+1U==atom.size()||atom.find('=',eq+1U)!=std::string::npos)return{};std::string key=atom.substr(0,eq);for(char c:key)if(!(std::isalnum(static_cast<unsigned char>(c))||c=='-'))return{};if(!keys.insert(key).second)return{};for(std::size_t i=eq+1U;i<atom.size();++i)if(atom[i]=='%'){if(i+2U>=atom.size()||!std::isxdigit(static_cast<unsigned char>(atom[i+1U]))||!std::isxdigit(static_cast<unsigned char>(atom[i+2U])))return{};i+=2U;}atoms.push_back(atom);b=e+1U;}std::string line;for(const auto&a:atoms){std::string piece=(line.empty()||line==continuation?"":"&")+a;if(line.size()+piece.size()>width){if(line.empty()||line==continuation)return{};o.lines.push_back(line);line=continuation+a;if(line.size()>width)return{};}else line+=piece;}o.lines.push_back(line);o.parameters=atoms.size();o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=fold_query("a=1&long=two&z=%20",11,"  ");return x.valid&&x.parameters==3&&x.lines==std::vector<std::string>{"a=1","  long=two","  z=%20"}?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;f+=fold_query("a=1&a=2",20," ").valid;f+=fold_query("a=%X0",20," ").valid;f+=fold_query("a=",20," ").valid;auto x=fold_query("a=1&b=2",20," ");f+=!x.valid||x.lines.size()!=1;return f;}
""",
        ("std::string piece=(line.empty()||line==continuation?\"\":\"&\")+a", "std::string piece=a", "ampersand separators disappear"),
    ),
    _case(
        "layout-annotation-lanes", "Interval annotation lane layout",
        "stable lowest-lane interval coloring and anchor rendering",
        "layout_annotations(text,annotations)->AnnotationLayout",
        """Annotations name nonempty half-open byte spans in one newline-free base string. Sort by start then original order, assign each span to the lowest lane whose previous span ends at or before its start, and render a caret at every covered byte plus the label at the span start. Equal starts preserve input order. Out-of-range spans, empty labels, or overlapping labels within one rendered lane are invalid.""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct Annotation{std::size_t begin=0,end=0;std::string label;};struct AnnotationLayout{bool valid=false;std::vector<std::string> lanes;std::vector<std::size_t> assignments;};AnnotationLayout layout_annotations(const std::string&,const std::vector<Annotation>&); }
""",
        "layout_annotations(const std::string& text,const std::vector<Annotation>& annotations)", "AnnotationLayout",
        """#include "task.h"
#include <algorithm>
#include <numeric>
namespace curriculum { AnnotationLayout layout_annotations(const std::string& text,const std::vector<Annotation>& annotations){AnnotationLayout o;if(text.find('\n')!=std::string::npos)return o;std::vector<std::size_t> order(annotations.size());std::iota(order.begin(),order.end(),0U);std::stable_sort(order.begin(),order.end(),[&](std::size_t a,std::size_t b){return annotations[a].begin<annotations[b].begin;});std::vector<std::size_t> ends;o.assignments.assign(annotations.size(),0);for(std::size_t index:order){const auto&a=annotations[index];if(a.begin>=a.end||a.end>text.size()||a.label.empty()||a.label.find('\n')!=std::string::npos)return{};std::size_t lane=0;while(lane<ends.size()&&ends[lane]>a.begin)++lane;if(lane==ends.size()){ends.push_back(0);o.lanes.push_back(std::string(text.size(),' '));}if(a.begin+a.label.size()>o.lanes[lane].size())return{};for(std::size_t i=a.begin;i<a.end;++i)o.lanes[lane][i]='^';for(std::size_t i=0;i<a.label.size();++i)o.lanes[lane][a.begin+i]=a.label[i];ends[lane]=std::max(a.end,a.begin+a.label.size());o.assignments[index]=lane;}o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=layout_annotations("abcdefgh",{{0,3,"A"},{2,5,"B"},{5,7,"C"}});return x.valid&&x.assignments==std::vector<std::size_t>{0,1,0}&&x.lanes.size()==2?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;f+=layout_annotations("abc",{{2,2,"x"}}).valid;f+=layout_annotations("abc",{{0,4,"x"}}).valid;auto e=layout_annotations("abc",{});f+=!e.valid||!e.lanes.empty();auto x=layout_annotations("abc",{{0,1,"x"},{1,2,"y"}});f+=!x.valid||x.lanes.size()!=1;return f;}
""",
        ("while(lane<ends.size()&&ends[lane]>a.begin)++lane;", "while(lane<ends.size())++lane;", "every annotation receives a new lane"),
    ),
    _case(
        "reflow-newline-canonicalization", "Canonical line-ending stream",
        "CRLF/LF state scanner with bounded blank-run emission",
        "canonical_newlines(chunks)->NewlineLayout",
        """Concatenate chunks logically while scanning line endings across chunk boundaries. Accept LF and CRLF, reject bare CR and NUL. Canonicalize every accepted ending to LF and cap consecutive empty lines at two while preserving whether nonempty input ended in a line ending. Chunk boundaries have no effect. Valid empty input returns empty text.""",
        """#pragma once
#include <string>
#include <vector>
namespace curriculum { struct NewlineLayout{bool valid=false;std::string text;bool terminal_newline=false;std::size_t collapsed=0;};NewlineLayout canonical_newlines(const std::vector<std::string>&); }
""",
        "canonical_newlines(const std::vector<std::string>& chunks)", "NewlineLayout",
        """#include "task.h"
namespace curriculum { NewlineLayout canonical_newlines(const std::vector<std::string>& chunks){NewlineLayout o;bool cr=false;std::size_t run=0;for(const auto&chunk:chunks)for(char c:chunk){if(c=='\0')return{};if(cr){if(c!='\n')return{};cr=false;c='\n';}else if(c=='\r'){cr=true;continue;}if(c=='\n'){++run;if(run<=2U)o.text+='\n';else ++o.collapsed;o.terminal_newline=true;}else{run=0;o.text+=c;o.terminal_newline=false;}}if(cr)return{};o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=canonical_newlines({"a\r","\n\n\nb"});return x.valid&&x.text=="a\n\nb"&&x.collapsed==1&& !x.terminal_newline?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;auto e=canonical_newlines({});f+=!e.valid||!e.text.empty();f+=canonical_newlines({"a\r"}).valid;f+=canonical_newlines({"a\rb"}).valid;auto x=canonical_newlines({"a\n"});f+=!x.valid||!x.terminal_newline;return f;}
""",
        ("if(run<=2U)", "if(run<=1U)", "only one empty-line boundary is retained"),
    ),
    _case(
        "layout-marginal-notes", "Anchored marginal note flow",
        "occupied-row side-column flow with monotone anchored starts",
        "layout_margins(main,notes,note_width)->MarginLayout",
        """Main lines are immutable and newline-free. Notes have a nondecreasing in-range anchor row and nonempty words. Wrap each note to note_width 3..30; its first row is the later of its anchor and the first unoccupied side row. Later notes never overwrite earlier note rows. Return paired main/note rows through the final occupied row. Empty notes leave the main text unchanged.""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct MarginNote{std::size_t anchor=0;std::vector<std::string> words;};struct MarginRow{std::string main,note;bool operator==(const MarginRow& other)const{return main==other.main&&note==other.note;}};struct MarginLayout{bool valid=false;std::vector<MarginRow> rows;};MarginLayout layout_margins(const std::vector<std::string>&,const std::vector<MarginNote>&,std::size_t); }
""",
        "layout_margins(const std::vector<std::string>& main,const std::vector<MarginNote>& notes,std::size_t width)", "MarginLayout",
        """#include "task.h"
#include <algorithm>
namespace curriculum { MarginLayout layout_margins(const std::vector<std::string>& main,const std::vector<MarginNote>& notes,std::size_t width){MarginLayout o;if(width<3U||width>30U)return o;for(const auto&s:main)if(s.find('\n')!=std::string::npos)return{};std::vector<std::string> side;std::size_t occupied=0,prior=0;for(std::size_t n=0;n<notes.size();++n){const auto&note=notes[n];if(note.anchor>=main.size()||(n>0U&&note.anchor<prior)||note.words.empty())return{};prior=note.anchor;std::vector<std::string> wrapped(1);for(const auto&w:note.words){if(w.empty()||w.find_first_of(" \t\n")!=std::string::npos||w.size()>width)return{};if(!wrapped.back().empty()&&wrapped.back().size()+1U+w.size()>width)wrapped.push_back(w);else{if(!wrapped.back().empty())wrapped.back()+=' ';wrapped.back()+=w;}}std::size_t start=std::max(note.anchor,occupied);if(side.size()<start+wrapped.size())side.resize(start+wrapped.size());for(std::size_t i=0;i<wrapped.size();++i)side[start+i]=wrapped[i];occupied=start+wrapped.size();}std::size_t rows=std::max(main.size(),side.size());for(std::size_t i=0;i<rows;++i)o.rows.push_back({i<main.size()?main[i]:"",i<side.size()?side[i]:""});o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=layout_margins({"a","b","c"},{{1,{"one","two"}},{1,{"three"}}},5);return x.valid&&x.rows==std::vector<MarginRow>{{"a",""},{"b","one"},{"c","two"},{"","three"}}?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;f+=layout_margins({"a"},{{1,{"x"}}},4).valid;f+=layout_margins({"a","b"},{{1,{"x"}},{0,{"y"}}},4).valid;auto x=layout_margins({"a"},{},4);f+=!x.valid||x.rows.size()!=1||x.rows[0].main!="a";return f;}
""",
        ("std::max(note.anchor,occupied)", "note.anchor+0U*occupied", "later notes overwrite occupied side rows"),
    ),
    _case(
        "layout-ruby-annotations", "Ruby-style annotation alignment",
        "ordered span expansion with right-biased padding and dual-row emission",
        "layout_ruby(base,annotations)->RubyLayout",
        """Annotations cover sorted, nonoverlapping, nonempty half-open spans of newline-free ASCII base text. Emit an annotation row and a base row. If an annotation is wider than its span, insert the needed spaces immediately after that span in the base row; if narrower, right-pad the annotation within the span. Preserve base-byte order and record each inserted gap. Empty annotations return the unchanged base and a blank annotation row.""",
        """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct RubyAnnotation{std::size_t begin=0,end=0;std::string text;};struct RubyGap{std::size_t source_end=0,spaces=0;bool operator==(const RubyGap& other)const{return source_end==other.source_end&&spaces==other.spaces;}};struct RubyLayout{bool valid=false;std::string annotation_row,base_row;std::vector<RubyGap> gaps;};RubyLayout layout_ruby(const std::string&,const std::vector<RubyAnnotation>&); }
""",
        "layout_ruby(const std::string& base,const std::vector<RubyAnnotation>& annotations)", "RubyLayout",
        """#include "task.h"
namespace curriculum { RubyLayout layout_ruby(const std::string& base,const std::vector<RubyAnnotation>& annotations){RubyLayout o;if(base.find('\n')!=std::string::npos)return o;std::size_t cursor=0;for(const auto&a:annotations){if(a.begin<a.end&&a.begin>=cursor&&a.end<=base.size()&&!a.text.empty()&&a.text.find('\n')==std::string::npos){}else return{};std::string prefix=base.substr(cursor,a.begin-cursor);o.base_row+=prefix;o.annotation_row+=std::string(prefix.size(),' ');std::string span=base.substr(a.begin,a.end-a.begin);std::size_t width=span.size();o.base_row+=span;o.annotation_row+=a.text;if(a.text.size()<width)o.annotation_row+=std::string(width-a.text.size(),' ');else if(a.text.size()>width){std::size_t gap=a.text.size()-width;o.base_row+=std::string(gap,' ');o.gaps.push_back({a.end,gap});}cursor=a.end;}o.base_row+=base.substr(cursor);o.annotation_row+=std::string(base.size()-cursor,' ');o.valid=true;return o;} }
""",
        """#include "task.h"
int main(){using namespace curriculum;auto x=layout_ruby("abcd",{{1,2,"XYZ"},{3,4,"Q"}});return x.valid&&x.base_row=="ab  cd"&&x.annotation_row==" XYZ Q"&&x.gaps==std::vector<RubyGap>{{2,2}}?0:1;}
""",
        """#include "task.h"
int main(){using namespace curriculum;int f=0;f+=layout_ruby("abc",{{1,1,"x"}}).valid;f+=layout_ruby("abc",{{0,2,"x"},{1,3,"y"}}).valid;auto e=layout_ruby("abc",{});f+=!e.valid||e.base_row!="abc"||e.annotation_row!="   ";auto x=layout_ruby("ab",{{0,2,"x"}});f+=!x.valid||x.annotation_row!="x ";return f;}
""",
        ("o.base_row+=std::string(gap,' ');", "o.base_row=std::string(gap,' ')+o.base_row;", "wide-annotation padding is inserted at the left edge"),
    ),
)


TASKS = CASES
