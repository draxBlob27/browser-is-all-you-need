"""Declarative cases for the expanded circular-deque remediation family."""

from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ExtraCase:
    task_id:str; class_name:str; kind:str; title:str; objective:str
    header:str; starter:str; reference:str; visible:str; hidden:str
    required:tuple[str,...]; forbidden:tuple[str,...]

def _case(task_id,class_name,kind,title,objective,header,starter,reference,visible,hidden,required,forbidden):
    return ExtraCase(task_id,class_name,kind,title,objective,header,starter,reference,visible,hidden,required,forbidden)

CASES=(
_case("deque-center-sequence","CenteredSequence","center_halves","Centered sequence","Maintain front, middle, and back insertion with deterministic left-middle removal.",
"""#pragma once
#include <deque>
#include <optional>
#include <vector>
namespace curriculum { class CenteredSequence { public: void push_front(int);void push_middle(int);void push_back(int);std::optional<int> pop_middle();std::vector<int> values()const;private:void rebalance();std::deque<int> left_,right_;};}
""",
"""#include "task.h"
namespace curriculum {void CenteredSequence::rebalance(){}void CenteredSequence::push_front(int){}void CenteredSequence::push_middle(int){}void CenteredSequence::push_back(int){}std::optional<int> CenteredSequence::pop_middle(){return std::nullopt;}std::vector<int> CenteredSequence::values()const{return {};}}
""",
"""#include "task.h"
namespace curriculum {void CenteredSequence::rebalance(){while(left_.size()>right_.size()+1U){right_.push_front(left_.back());left_.pop_back();}while(right_.size()>left_.size()){left_.push_back(right_.front());right_.pop_front();}}void CenteredSequence::push_front(int v){left_.push_front(v);rebalance();}void CenteredSequence::push_back(int v){right_.push_back(v);rebalance();}void CenteredSequence::push_middle(int v){if(left_.size()>right_.size()){right_.push_front(left_.back());left_.pop_back();}left_.push_back(v);}std::optional<int> CenteredSequence::pop_middle(){if(left_.empty())return std::nullopt;int v=left_.back();left_.pop_back();rebalance();return v;}std::vector<int> CenteredSequence::values()const{std::vector<int> out(left_.begin(),left_.end());out.insert(out.end(),right_.begin(),right_.end());return out;}}
""",
"""#include "task.h"
#include <optional>
#include <vector>
int main(){curriculum::CenteredSequence s;s.push_back(3);s.push_front(1);s.push_middle(2);s.push_back(4);return s.values()==std::vector<int>{1,2,3,4}&&s.pop_middle()==std::optional<int>(2)?0:1;}
""",
"""#include "task.h"
#include <optional>
#include <vector>
int main(){curriculum::CenteredSequence s;for(int i=0;i<20;++i){if(i%3==0)s.push_front(i);else if(i%3==1)s.push_middle(i);else s.push_back(i);}auto v=s.values();if(v.size()!=20U)return 1;for(int i=0;i<20;++i)if(!s.pop_middle())return 1;return s.values().empty()&&!s.pop_middle()?0:1;}
""",("left_","right_","rebalance()","push_front(left_.back())"),("std::vector<int> state_","insert(state_")),

_case("deque-prefix-expression","PrefixExpression","prefix_parser","Prefix expression","Evaluate a strict integer prefix token stream with checked arithmetic.",
"""#pragma once
#include <optional>
#include <string>
#include <vector>
namespace curriculum {std::optional<long long> evaluate_prefix(const std::vector<std::string>& tokens);}
""",
"""#include "task.h"
namespace curriculum {std::optional<long long> evaluate_prefix(const std::vector<std::string>&){return std::nullopt;}}
""",
"""#include "task.h"
#include <charconv>
#include <deque>
#include <limits>
namespace curriculum {static std::optional<long long> parse(std::deque<std::string>& q){if(q.empty())return std::nullopt;std::string t=q.front();q.pop_front();if(t!="+"&&t!="-"&&t!="*"&&t!="/"){long long v=0;auto r=std::from_chars(t.data(),t.data()+t.size(),v);if(r.ec!=std::errc()||r.ptr!=t.data()+t.size())return std::nullopt;return v;}auto a=parse(q),b=parse(q);if(!a||!b)return std::nullopt;long long z=0;if(t=="+"&&__builtin_add_overflow(*a,*b,&z))return std::nullopt;if(t=="-"&&__builtin_sub_overflow(*a,*b,&z))return std::nullopt;if(t=="*"&&__builtin_mul_overflow(*a,*b,&z))return std::nullopt;if(t=="/"){if(*b==0||(*a==std::numeric_limits<long long>::min()&&*b==-1))return std::nullopt;z=*a / *b;}return z;}std::optional<long long> evaluate_prefix(const std::vector<std::string>& tokens){std::deque<std::string> q(tokens.begin(),tokens.end());auto out=parse(q);return out&&q.empty()?out:std::nullopt;}}
""",
"""#include "task.h"
#include <optional>
int main(){auto v=curriculum::evaluate_prefix({"+","2","*","3","4"});return v==std::optional<long long>(14)&&!curriculum::evaluate_prefix({"/","7","0"})?0:1;}
""",
"""#include "task.h"
#include <limits>
int main(){if(curriculum::evaluate_prefix({"-","*","8","7","+","2","3"})!=51)return 1;if(curriculum::evaluate_prefix({"1","2"}))return 1;if(curriculum::evaluate_prefix({"*","9223372036854775807","2"}))return 1;return 0;}
""",("std::deque<std::string>","parse(q)","q.pop_front()","__builtin_mul_overflow"),("std::stack","postfix")),

_case("deque-run-segment-editor","RunSegmentEditor","run_editor","Run segment editor","Store a double-ended character sequence as maximal equal-character runs.",
"""#pragma once
#include <cstddef>
#include <deque>
#include <string>
namespace curriculum {class RunSegmentEditor{public:void prepend(char,std::size_t);void append(char,std::size_t);std::size_t drop_front(std::size_t);std::size_t drop_back(std::size_t);std::string text()const;std::size_t run_count()const;private:struct Run{char value;std::size_t count;};std::deque<Run> runs_;};}
""",
"""#include "task.h"
namespace curriculum {void RunSegmentEditor::prepend(char,std::size_t){}void RunSegmentEditor::append(char,std::size_t){}std::size_t RunSegmentEditor::drop_front(std::size_t){return 0;}std::size_t RunSegmentEditor::drop_back(std::size_t){return 0;}std::string RunSegmentEditor::text()const{return {};}std::size_t RunSegmentEditor::run_count()const{return 0;}}
""",
"""#include "task.h"
#include <algorithm>
namespace curriculum {void RunSegmentEditor::prepend(char c,std::size_t n){if(!n)return;if(!runs_.empty()&&runs_.front().value==c)runs_.front().count+=n;else runs_.push_front({c,n});}void RunSegmentEditor::append(char c,std::size_t n){if(!n)return;if(!runs_.empty()&&runs_.back().value==c)runs_.back().count+=n;else runs_.push_back({c,n});}std::size_t RunSegmentEditor::drop_front(std::size_t n){std::size_t gone=0;while(n&&!runs_.empty()){auto take=std::min(n,runs_.front().count);runs_.front().count-=take;n-=take;gone+=take;if(!runs_.front().count)runs_.pop_front();}return gone;}std::size_t RunSegmentEditor::drop_back(std::size_t n){std::size_t gone=0;while(n&&!runs_.empty()){auto take=std::min(n,runs_.back().count);runs_.back().count-=take;n-=take;gone+=take;if(!runs_.back().count)runs_.pop_back();}return gone;}std::string RunSegmentEditor::text()const{std::string out;for(auto r:runs_)out.append(r.count,r.value);return out;}std::size_t RunSegmentEditor::run_count()const{return runs_.size();}}
""",
"""#include "task.h"
int main(){curriculum::RunSegmentEditor e;e.append('a',2);e.append('a',3);e.prepend('b',2);if(e.text()!="bbaaaaa"||e.run_count()!=2)return 1;e.drop_front(3);e.drop_back(2);return e.text()=="aa"?0:1;}
""",
"""#include "task.h"
int main(){curriculum::RunSegmentEditor e;for(int i=0;i<100;++i){e.append(char('a'+i%4),i%5+1);if(i%3==0)e.prepend('z',1);if(i%4==0)e.drop_back(2);if(i%7==0)e.drop_front(1);}auto t=e.text();return e.drop_front(t.size()+10)==t.size()&&e.run_count()==0?0:1;}
""",("runs_","front().count","back().count","out.append"),("std::deque<char>","std::string state_")),

_case("deque-snake-arena","SnakeArena","snake_body","Snake arena","Advance a snake with growth and tail-vacate collision semantics.",
"""#pragma once
#include <cstddef>
#include <deque>
#include <unordered_set>
#include <vector>
namespace curriculum {struct Cell{int row,col;bool operator==(const Cell&)const;};enum class Direction{up,down,left,right};enum class StepResult{moved,wall,self_collision,invalid};class SnakeArena{public:SnakeArena(int rows,int cols,const std::vector<Cell>& body);StepResult step(Direction,bool grow);std::vector<Cell> body()const;private:long long key(Cell)const;int rows_,cols_;bool valid_;std::deque<Cell> body_;std::unordered_set<long long> occupied_;};}
""",
"""#include "task.h"
namespace curriculum {bool Cell::operator==(const Cell&o)const{return row==o.row&&col==o.col;}SnakeArena::SnakeArena(int r,int c,const std::vector<Cell>&):rows_(r),cols_(c),valid_(false){}long long SnakeArena::key(Cell c)const{return c.row*1000000LL+c.col;}StepResult SnakeArena::step(Direction,bool){return StepResult::invalid;}std::vector<Cell> SnakeArena::body()const{return {};}}
""",
"""#include "task.h"
namespace curriculum {bool Cell::operator==(const Cell&o)const{return row==o.row&&col==o.col;}long long SnakeArena::key(Cell c)const{return (static_cast<long long>(c.row)<<32)^static_cast<unsigned>(c.col);}SnakeArena::SnakeArena(int r,int c,const std::vector<Cell>& b):rows_(r),cols_(c),valid_(r>0&&c>0&&!b.empty()),body_(b.begin(),b.end()){for(auto x:b){if(x.row<0||x.row>=r||x.col<0||x.col>=c||!occupied_.insert(key(x)).second)valid_=false;}}StepResult SnakeArena::step(Direction d,bool grow){if(!valid_)return StepResult::invalid;Cell n=body_.front();if(d==Direction::up)--n.row;else if(d==Direction::down)++n.row;else if(d==Direction::left)--n.col;else ++n.col;if(n.row<0||n.row>=rows_||n.col<0||n.col>=cols_)return StepResult::wall;Cell tail=body_.back();if(!grow){occupied_.erase(key(tail));body_.pop_back();}if(occupied_.count(key(n))){if(!grow){body_.push_back(tail);occupied_.insert(key(tail));}return StepResult::self_collision;}body_.push_front(n);occupied_.insert(key(n));return StepResult::moved;}std::vector<Cell> SnakeArena::body()const{return {body_.begin(),body_.end()};}}
""",
"""#include "task.h"
int main(){curriculum::SnakeArena s(3,4,{{1,2},{1,1},{1,0}});if(s.step(curriculum::Direction::left,false)!=curriculum::StepResult::self_collision)return 1;if(s.step(curriculum::Direction::right,false)!=curriculum::StepResult::moved)return 1;return s.body().front()==curriculum::Cell{1,3}?0:1;}
""",
"""#include "task.h"
int main(){curriculum::SnakeArena s(4,4,{{2,2},{2,1},{1,1},{1,2}});if(s.step(curriculum::Direction::up,false)!=curriculum::StepResult::moved)return 1;if(s.step(curriculum::Direction::left,true)!=curriculum::StepResult::self_collision)return 1;curriculum::SnakeArena bad(2,2,{{0,0},{0,0}});return bad.step(curriculum::Direction::right,false)==curriculum::StepResult::invalid?0:1;}
""",("body_","occupied_","occupied_.erase","body_.push_front"),("std::vector<Cell> body_","linear_collision_scan")),

_case("deque-deficit-scheduler","DeficitScheduler","deficit_rr","Deficit scheduler","Dispatch variable-cost jobs with deficit round-robin fairness.",
"""#pragma once
#include <cstddef>
#include <deque>
#include <optional>
#include <string>
#include <unordered_map>
namespace curriculum {class DeficitScheduler{public:explicit DeficitScheduler(unsigned quantum);bool submit(const std::string&,const std::string&,unsigned);std::optional<std::string> dispatch();std::size_t pending()const;private:struct Job{std::string id;unsigned cost;};struct Flow{std::deque<Job> jobs;unsigned long long deficit=0;bool active=false;};unsigned quantum_;std::size_t pending_=0;std::deque<std::string> active_;std::unordered_map<std::string,Flow> flows_;};}
""",
"""#include "task.h"
namespace curriculum {DeficitScheduler::DeficitScheduler(unsigned q):quantum_(q){}bool DeficitScheduler::submit(const std::string&,const std::string&,unsigned){return false;}std::optional<std::string> DeficitScheduler::dispatch(){return std::nullopt;}std::size_t DeficitScheduler::pending()const{return pending_;}}
""",
"""#include "task.h"
#include <limits>
namespace curriculum {DeficitScheduler::DeficitScheduler(unsigned q):quantum_(q){}bool DeficitScheduler::submit(const std::string& f,const std::string& id,unsigned cost){if(!quantum_||f.empty()||id.empty()||!cost)return false;auto& flow=flows_[f];flow.jobs.push_back({id,cost});if(!flow.active){flow.active=true;active_.push_back(f);}++pending_;return true;}std::optional<std::string> DeficitScheduler::dispatch(){while(!active_.empty()){auto name=active_.front();active_.pop_front();auto& flow=flows_[name];flow.deficit=std::min<unsigned long long>(std::numeric_limits<unsigned long long>::max(),flow.deficit+quantum_);if(flow.jobs.front().cost<=flow.deficit){auto job=flow.jobs.front();flow.jobs.pop_front();flow.deficit-=job.cost;--pending_;if(flow.jobs.empty())flow.active=false;else active_.push_back(name);return job.id;}active_.push_back(name);}return std::nullopt;}std::size_t DeficitScheduler::pending()const{return pending_;}}
""",
"""#include "task.h"
int main(){curriculum::DeficitScheduler s(3);s.submit("a","a6",6);s.submit("b","b2",2);if(s.dispatch()!="b2")return 1;if(s.dispatch()!="a6")return 1;return !s.dispatch()?0:1;}
""",
"""#include "task.h"
int main(){curriculum::DeficitScheduler s(4);if(s.submit("","",0))return 1;for(int i=0;i<20;++i){s.submit("x","x"+std::to_string(i),7);s.submit("y","y"+std::to_string(i),1);}for(int i=0;i<40;++i)if(!s.dispatch())return 1;return s.pending()==0?0:1;}
""",("active_","flows_","deficit","active_.push_back"),("std::priority_queue","global_fifo")),

_case("deque-temporal-join","TemporalJoin","temporal_join","Temporal join","Greedily join two monotonic timestamp streams within a tolerance.",
"""#pragma once
#include <cstddef>
#include <cstdint>
#include <deque>
#include <optional>
#include <string>
namespace curriculum {struct TimedEvent{std::uint64_t time;std::string id;};struct TemporalMatch{TimedEvent left,right;};class TemporalJoin{public:explicit TemporalJoin(std::uint64_t tolerance);std::optional<TemporalMatch> push_left(TimedEvent);std::optional<TemporalMatch> push_right(TimedEvent);std::size_t dropped()const;private:std::optional<TemporalMatch> match();std::uint64_t tolerance_;std::deque<TimedEvent> left_,right_;std::size_t dropped_=0;};}
""",
"""#include "task.h"
namespace curriculum {TemporalJoin::TemporalJoin(std::uint64_t t):tolerance_(t){}std::optional<TemporalMatch> TemporalJoin::match(){return std::nullopt;}std::optional<TemporalMatch> TemporalJoin::push_left(TimedEvent){return std::nullopt;}std::optional<TemporalMatch> TemporalJoin::push_right(TimedEvent){return std::nullopt;}std::size_t TemporalJoin::dropped()const{return dropped_;}}
""",
"""#include "task.h"
namespace curriculum {TemporalJoin::TemporalJoin(std::uint64_t t):tolerance_(t){}std::optional<TemporalMatch> TemporalJoin::match(){while(!left_.empty()&&!right_.empty()){auto l=left_.front(),r=right_.front();if(l.time<=r.time? r.time-l.time<=tolerance_:l.time-r.time<=tolerance_){left_.pop_front();right_.pop_front();return TemporalMatch{l,r};}if(l.time<r.time){left_.pop_front();++dropped_;}else{right_.pop_front();++dropped_;}}return std::nullopt;}std::optional<TemporalMatch> TemporalJoin::push_left(TimedEvent e){if(e.id.empty()||(!left_.empty()&&e.time<left_.back().time))return std::nullopt;left_.push_back(e);return match();}std::optional<TemporalMatch> TemporalJoin::push_right(TimedEvent e){if(e.id.empty()||(!right_.empty()&&e.time<right_.back().time))return std::nullopt;right_.push_back(e);return match();}std::size_t TemporalJoin::dropped()const{return dropped_;}}
""",
"""#include "task.h"
int main(){curriculum::TemporalJoin j(3);if(j.push_left({10,"a"}))return 1;auto m=j.push_right({12,"b"});return m&&m->left.id=="a"&&m->right.id=="b"?0:1;}
""",
"""#include "task.h"
int main(){curriculum::TemporalJoin j(2);j.push_left({1,"a"});j.push_left({5,"b"});if(j.push_right({4,"x"})->left.id!="b")return 1;if(j.dropped()!=1)return 1;if(j.push_left({3,"late"}))return 1;return 0;}
""",("left_","right_","match()","dropped_"),("std::sort","std::map")),

_case("deque-palindrome-fingerprint","PalindromeFingerprint","pal_hash","Palindrome fingerprint","Maintain reversible hashes for constant-time palindrome checks under end edits.",
"""#pragma once
#include <cstdint>
#include <deque>
#include <optional>
#include <string>
#include <vector>
namespace curriculum {class PalindromeFingerprint{public:PalindromeFingerprint();void push_front(char);void push_back(char);std::optional<char> pop_front();std::optional<char> pop_back();bool is_palindrome()const;std::string text()const;private:void ensure(std::size_t);static std::uint64_t mod_pow(std::uint64_t,std::uint64_t);std::deque<char> chars_;std::vector<std::uint64_t> powers_;std::uint64_t forward_=0,reverse_=0;};}
""",
"""#include "task.h"
namespace curriculum {PalindromeFingerprint::PalindromeFingerprint():powers_{1}{}void PalindromeFingerprint::ensure(std::size_t){}std::uint64_t PalindromeFingerprint::mod_pow(std::uint64_t,std::uint64_t){return 0;}void PalindromeFingerprint::push_front(char){}void PalindromeFingerprint::push_back(char){}std::optional<char> PalindromeFingerprint::pop_front(){return std::nullopt;}std::optional<char> PalindromeFingerprint::pop_back(){return std::nullopt;}bool PalindromeFingerprint::is_palindrome()const{return true;}std::string PalindromeFingerprint::text()const{return {};}}
""",
"""#include "task.h"
namespace curriculum {static constexpr std::uint64_t M=1000000007ULL,B=911382323ULL;static std::uint64_t val(char c){return static_cast<unsigned char>(c)+1U;}std::uint64_t PalindromeFingerprint::mod_pow(std::uint64_t a,std::uint64_t e){std::uint64_t r=1;for(;e;e>>=1,a=a*a%M)if(e&1)r=r*a%M;return r;}PalindromeFingerprint::PalindromeFingerprint():powers_{1}{}void PalindromeFingerprint::ensure(std::size_t n){while(powers_.size()<=n)powers_.push_back(powers_.back()*B%M);}void PalindromeFingerprint::push_back(char c){ensure(chars_.size());forward_=(forward_+val(c)*powers_[chars_.size()])%M;reverse_=(reverse_*B+val(c))%M;chars_.push_back(c);}void PalindromeFingerprint::push_front(char c){ensure(chars_.size());forward_=(forward_*B+val(c))%M;reverse_=(reverse_+val(c)*powers_[chars_.size()])%M;chars_.push_front(c);}std::optional<char> PalindromeFingerprint::pop_back(){if(chars_.empty())return std::nullopt;auto c=chars_.back();ensure(chars_.size());forward_=(forward_+M-val(c)*powers_[chars_.size()-1]%M)%M;reverse_=(reverse_+M-val(c))%M*mod_pow(B,M-2)%M;chars_.pop_back();return c;}std::optional<char> PalindromeFingerprint::pop_front(){if(chars_.empty())return std::nullopt;auto c=chars_.front();ensure(chars_.size());forward_=(forward_+M-val(c))%M*mod_pow(B,M-2)%M;reverse_=(reverse_+M-val(c)*powers_[chars_.size()-1]%M)%M;chars_.pop_front();return c;}bool PalindromeFingerprint::is_palindrome()const{return forward_==reverse_;}std::string PalindromeFingerprint::text()const{return {chars_.begin(),chars_.end()};}}
""",
"""#include "task.h"
int main(){curriculum::PalindromeFingerprint p;p.push_back('a');p.push_back('b');p.push_back('a');if(!p.is_palindrome())return 1;p.push_front('x');if(p.is_palindrome())return 1;p.pop_front();return p.text()=="aba"&&p.is_palindrome()?0:1;}
""",
"""#include "task.h"
#include <algorithm>
int main(){curriculum::PalindromeFingerprint p;std::string s;for(int i=0;i<200;++i){char c=char('a'+i%5);if(i%2){p.push_front(c);s.insert(s.begin(),c);}else{p.push_back(c);s.push_back(c);}std::string r=s;std::reverse(r.begin(),r.end());if(p.is_palindrome()!=(s==r))return 1;if(i%7==0){p.pop_back();s.pop_back();}}return p.text()==s?0:1;}
""",("forward_","reverse_","mod_pow","powers_"),("std::reverse","chars_==")),

_case("deque-chunked-text","ChunkedText","chunked_text","Chunked text","Maintain text as bounded nonempty chunks under bulk end edits.",
"""#pragma once
#include <cstddef>
#include <deque>
#include <string>
namespace curriculum {class ChunkedText{public:explicit ChunkedText(std::size_t limit);bool prepend(const std::string&);bool append(const std::string&);std::size_t erase_front(std::size_t);std::size_t erase_back(std::size_t);std::string str()const;std::size_t chunks()const;private:std::size_t limit_;std::deque<std::string> chunks_;};}
""",
"""#include "task.h"
namespace curriculum {ChunkedText::ChunkedText(std::size_t l):limit_(l){}bool ChunkedText::prepend(const std::string&){return false;}bool ChunkedText::append(const std::string&){return false;}std::size_t ChunkedText::erase_front(std::size_t){return 0;}std::size_t ChunkedText::erase_back(std::size_t){return 0;}std::string ChunkedText::str()const{return {};}std::size_t ChunkedText::chunks()const{return 0;}}
""",
"""#include "task.h"
#include <algorithm>
namespace curriculum {ChunkedText::ChunkedText(std::size_t l):limit_(l){}bool ChunkedText::append(const std::string& s){if(!limit_)return false;for(char c:s){if(chunks_.empty()||chunks_.back().size()==limit_)chunks_.push_back({});chunks_.back().push_back(c);}return true;}bool ChunkedText::prepend(const std::string& s){if(!limit_)return false;for(auto it=s.rbegin();it!=s.rend();++it){if(chunks_.empty()||chunks_.front().size()==limit_)chunks_.push_front({});chunks_.front().insert(chunks_.front().begin(),*it);}return true;}std::size_t ChunkedText::erase_front(std::size_t n){std::size_t gone=0;while(n&&!chunks_.empty()){auto take=std::min(n,chunks_.front().size());chunks_.front().erase(0,take);n-=take;gone+=take;if(chunks_.front().empty())chunks_.pop_front();}return gone;}std::size_t ChunkedText::erase_back(std::size_t n){std::size_t gone=0;while(n&&!chunks_.empty()){auto take=std::min(n,chunks_.back().size());chunks_.back().erase(chunks_.back().size()-take);n-=take;gone+=take;if(chunks_.back().empty())chunks_.pop_back();}return gone;}std::string ChunkedText::str()const{std::string out;for(const auto& c:chunks_)out+=c;return out;}std::size_t ChunkedText::chunks()const{return chunks_.size();}}
""",
"""#include "task.h"
int main(){curriculum::ChunkedText t(3);t.append("cdef");t.prepend("ab");if(t.str()!="abcdef"||t.chunks()!=3)return 1;t.erase_front(2);t.erase_back(1);return t.str()=="cde"?0:1;}
""",
"""#include "task.h"
int main(){curriculum::ChunkedText z(0);if(z.append("x"))return 1;curriculum::ChunkedText t(4);std::string s;for(int i=0;i<100;++i){auto x=std::to_string(i);if(i%2){t.prepend(x);s=x+s;}else{t.append(x);s+=x;}if(i%5==0){auto n=t.erase_front(3);s.erase(0,n);}}return t.str()==s?0:1;}
""",("chunks_","limit_","push_front","push_back"),("std::deque<char>","std::string text_","struct Run")),

_case("deque-josephus-elimination","JosephusElimination","josephus","Josephus elimination","Produce circular elimination order with direction and step.",
"""#pragma once
#include <cstddef>
#include <optional>
#include <vector>
namespace curriculum {std::optional<std::vector<int>> josephus_order(const std::vector<int>& ids,std::size_t step,bool clockwise);}
""",
"""#include "task.h"
namespace curriculum {std::optional<std::vector<int>> josephus_order(const std::vector<int>&,std::size_t,bool){return std::nullopt;}}
""",
"""#include "task.h"
#include <deque>
#include <unordered_set>
namespace curriculum {std::optional<std::vector<int>> josephus_order(const std::vector<int>& ids,std::size_t step,bool cw){if(!step)return std::nullopt;std::unordered_set<int> unique(ids.begin(),ids.end());if(unique.size()!=ids.size())return std::nullopt;std::deque<int> q(ids.begin(),ids.end());std::vector<int> out;while(!q.empty()){for(std::size_t i=1;i<step;++i)if(cw){q.push_back(q.front());q.pop_front();}else{q.push_front(q.back());q.pop_back();}if(cw){out.push_back(q.front());q.pop_front();}else{out.push_back(q.back());q.pop_back();}}return out;}}
""",
"""#include "task.h"
#include <vector>
int main(){auto v=curriculum::josephus_order({1,2,3,4,5,6,7},3,true);return v&&*v==std::vector<int>({3,6,2,7,5,1,4})?0:1;}
""",
"""#include "task.h"
#include <vector>
int main(){if(curriculum::josephus_order({1,1},2,true))return 1;if(curriculum::josephus_order({1,2},0,true))return 1;auto v=curriculum::josephus_order({1,2,3,4},1,false);return v&&*v==std::vector<int>({4,3,2,1})?0:1;}
""",("std::deque<int>","push_front(q.back())","push_back(q.front())","unique"),("erase(q.begin()","closed_form")),

_case("deque-lexicographic-end-picker","LexicographicEndPicker","lex_picker","Lexicographic end picker","Choose ends with full tie lookahead to minimize the result.",
"""#pragma once
#include <string>
namespace curriculum {struct EndPickResult{std::string value,sides;};EndPickResult pick_lexicographic_ends(const std::string& input);}
""",
"""#include "task.h"
namespace curriculum {EndPickResult pick_lexicographic_ends(const std::string&){return {};}}
""",
"""#include "task.h"
#include <deque>
namespace curriculum {EndPickResult pick_lexicographic_ends(const std::string& input){std::deque<char> q(input.begin(),input.end());EndPickResult out;while(!q.empty()){bool left=true;for(std::size_t i=0;i<q.size()/2U+q.size()%2U;++i){char a=q[i],b=q[q.size()-1U-i];if(a<b){left=true;break;}if(a>b){left=false;break;}}if(left){out.value.push_back(q.front());q.pop_front();out.sides.push_back('L');}else{out.value.push_back(q.back());q.pop_back();out.sides.push_back('R');}}return out;}}
""",
"""#include "task.h"
int main(){auto r=curriculum::pick_lexicographic_ends("ACDBCB");return r.value=="ABCBCD"&&r.sides.size()==6?0:1;}
""",
"""#include "task.h"
int main(){auto a=curriculum::pick_lexicographic_ends("AAAA");if(a.value!="AAAA"||a.sides!="LLLL")return 1;auto b=curriculum::pick_lexicographic_ends("BACAB");return b.value=="BABAC"?0:1;}
""",("std::deque<char>","q[q.size()-1U-i]","pop_front()","pop_back()"),("std::sort","always_left")),

_case("deque-card-war-cycle","CardWarCycle","war_cycle","Card war cycle","Simulate two decks with capture order and repeated-state detection.",
"""#pragma once
#include <cstddef>
#include <optional>
#include <vector>
namespace curriculum {enum class WarOutcome{first,second,cycle,round_limit};struct WarResult{WarOutcome outcome;std::size_t rounds;};std::optional<WarResult> simulate_card_war(std::vector<unsigned> first,std::vector<unsigned> second,std::size_t limit);}
""",
"""#include "task.h"
namespace curriculum {std::optional<WarResult> simulate_card_war(std::vector<unsigned>,std::vector<unsigned>,std::size_t){return std::nullopt;}}
""",
"""#include "task.h"
#include <deque>
#include <string>
#include <unordered_set>
namespace curriculum {static std::string encode(const std::deque<unsigned>&a,const std::deque<unsigned>&b){std::string s;for(auto x:a)s+=std::to_string(x)+",";s+="|";for(auto x:b)s+=std::to_string(x)+",";return s;}std::optional<WarResult> simulate_card_war(std::vector<unsigned>a,std::vector<unsigned>b,std::size_t limit){std::deque<unsigned>x(a.begin(),a.end()),y(b.begin(),b.end());std::unordered_set<std::string> seen;std::size_t rounds=0;while(!x.empty()&&!y.empty()){if(rounds==limit)return WarResult{WarOutcome::round_limit,rounds};if(!seen.insert(encode(x,y)).second)return WarResult{WarOutcome::cycle,rounds};auto p=x.front(),q=y.front();x.pop_front();y.pop_front();if(p==q)return std::nullopt;if(p>q){x.push_back(p);x.push_back(q);}else{y.push_back(q);y.push_back(p);}++rounds;}return WarResult{x.empty()?WarOutcome::second:WarOutcome::first,rounds};}}
""",
"""#include "task.h"
int main(){auto r=curriculum::simulate_card_war({4,3},{2,1},20);return r&&r->outcome==curriculum::WarOutcome::first?0:1;}
""",
"""#include "task.h"
int main(){if(curriculum::simulate_card_war({1},{1},3))return 1;auto l=curriculum::simulate_card_war({2,1},{4,3},0);if(!l||l->outcome!=curriculum::WarOutcome::round_limit)return 1;auto e=curriculum::simulate_card_war({}, {1},5);return e&&e->outcome==curriculum::WarOutcome::second?0:1;}
""",("std::deque<unsigned>","seen.insert","encode(x,y)","push_back(p)"),("score_only","no_cycle_state")),

_case("deque-stable-radix","StableRadix","radix_buckets","Stable radix","Stable LSD radix sorting with deque digit buckets.",
"""#pragma once
#include <optional>
#include <vector>
namespace curriculum {std::optional<std::vector<unsigned>> stable_lsd_radix(std::vector<unsigned> values,unsigned base);}
""",
"""#include "task.h"
namespace curriculum {std::optional<std::vector<unsigned>> stable_lsd_radix(std::vector<unsigned>,unsigned){return std::nullopt;}}
""",
"""#include "task.h"
#include <algorithm>
#include <deque>
#include <limits>
namespace curriculum {std::optional<std::vector<unsigned>> stable_lsd_radix(std::vector<unsigned> values,unsigned base){if(base<2U||base>16U)return std::nullopt;unsigned maximum=values.empty()?0U:*std::max_element(values.begin(),values.end());std::vector<std::deque<unsigned>> buckets(base);for(unsigned place=1;;){for(auto v:values)buckets[(v/place)%base].push_back(v);std::size_t i=0;for(auto& bucket:buckets)while(!bucket.empty()){values[i++]=bucket.front();bucket.pop_front();}if(place>maximum/base)break;if(place>std::numeric_limits<unsigned>::max()/base)break;place*=base;}return values;}}
""",
"""#include "task.h"
#include <vector>
int main(){auto v=curriculum::stable_lsd_radix({170,45,75,90,802,24,2,66},10);return v&&*v==std::vector<unsigned>({2,24,45,66,75,90,170,802})?0:1;}
""",
"""#include "task.h"
#include <algorithm>
int main(){if(curriculum::stable_lsd_radix({1},1))return 1;std::vector<unsigned> a;unsigned s=99;for(int i=0;i<500;++i){s=s*1664525U+1013904223U;a.push_back(s);}auto e=a;std::stable_sort(e.begin(),e.end());auto got=curriculum::stable_lsd_radix(a,16);return got&&*got==e?0:1;}
""",("std::vector<std::deque<unsigned>>","buckets","place*=base","pop_front()"),("std::sort(","std::stable_sort("))
)
