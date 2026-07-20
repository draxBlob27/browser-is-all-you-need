"""Clean-room v2 trie cases with distinct representations and behaviors."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    legacy_id: str
    task_id: str
    class_name: str
    objective: str
    behavior: str
    header: str
    reference: str
    starter: str
    visible: str
    hidden: str
    required_tokens: tuple[str, ...]


def _header(class_name: str, declarations: str, audit: str, private: str) -> str:
    return f'''#pragma once
#include <array>
#include <cstddef>
#include <map>
#include <memory>
#include <optional>
#include <set>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>
namespace curriculum {{
class {class_name} {{
 public:
  struct Audit {{ bool valid; {audit} }};
  {class_name}();
  ~{class_name}();
  {class_name}(const {class_name}&) = delete;
  {class_name}& operator=(const {class_name}&) = delete;
{declarations}
  Audit audit_for_test() const;
 private:
{private}
}};
}}  // namespace curriculum
'''


def _stub(class_name: str, definitions: str) -> str:
    return f'''#include "task.h"
namespace curriculum {{
struct {class_name}::Node {{}};
{class_name}::{class_name}():root_(std::make_unique<Node>()){{}}
{class_name}::~{class_name}()=default;
{definitions}
{class_name}::Audit {class_name}::audit_for_test()const{{return {{false,0U,0U}};}}
}}  // namespace curriculum
'''


def _case_radix() -> Case:
    cls = "RadixCommandCatalog"
    header = _header(cls, '''  bool add(const std::string& command);
  bool erase(const std::string& command);
  bool contains(const std::string& command) const;
  std::vector<std::string> complete(const std::string& prefix, std::size_t limit) const;
  std::size_t size() const;''', "std::size_t nodes; std::size_t terminals;", "  struct Node;\n  std::unique_ptr<Node> root_;\n  std::size_t size_ = 0;")
    ref = r'''#include "task.h"
#include <algorithm>
#include <functional>
namespace curriculum {
struct RadixCommandCatalog::Node{bool terminal=false;std::map<std::string,std::unique_ptr<Node>>edges;};
namespace{bool valid(const std::string&s){return !s.empty()&&std::all_of(s.begin(),s.end(),[](char c){return c>='a'&&c<='z';});}std::size_t common(const std::string&a,const std::string&b){std::size_t n=0;while(n<a.size()&&n<b.size()&&a[n]==b[n])++n;return n;}}
RadixCommandCatalog::RadixCommandCatalog():root_(std::make_unique<Node>()){} RadixCommandCatalog::~RadixCommandCatalog()=default;
bool RadixCommandCatalog::add(const std::string&s){if(!valid(s))return false;Node*n=root_.get();std::string rest=s;for(;;){auto hit=n->edges.end();std::size_t shared=0;for(auto it=n->edges.begin();it!=n->edges.end();++it){auto k=common(it->first,rest);if(k){hit=it;shared=k;break;}}if(hit==n->edges.end()){auto leaf=std::make_unique<Node>();leaf->terminal=true;n->edges.emplace(rest,std::move(leaf));++size_;return true;}if(shared==hit->first.size()){rest.erase(0,shared);n=hit->second.get();if(rest.empty()){if(n->terminal)return false;n->terminal=true;++size_;return true;}continue;}auto label=hit->first;auto old=std::move(hit->second);n->edges.erase(hit);auto middle=std::make_unique<Node>();middle->edges.emplace(label.substr(shared),std::move(old));if(shared==rest.size())middle->terminal=true;else{auto leaf=std::make_unique<Node>();leaf->terminal=true;middle->edges.emplace(rest.substr(shared),std::move(leaf));}n->edges.emplace(label.substr(0,shared),std::move(middle));++size_;return true;}}
bool RadixCommandCatalog::contains(const std::string&s)const{if(!valid(s))return false;const Node*n=root_.get();std::string rest=s;while(!rest.empty()){bool found=false;for(const auto&e:n->edges)if(rest.rfind(e.first,0)==0){rest.erase(0,e.first.size());n=e.second.get();found=true;break;}if(!found)return false;}return n->terminal;}
bool RadixCommandCatalog::erase(const std::string&s){if(!contains(s))return false;std::function<bool(Node*,const std::string&)>del=[&](Node*n,const std::string&rest){if(rest.empty()){n->terminal=false;return true;}for(auto it=n->edges.begin();it!=n->edges.end();++it)if(rest.rfind(it->first,0)==0){auto label=it->first;Node*child=it->second.get();if(!del(child,rest.substr(label.size())))return false;if(!child->terminal&&child->edges.empty())n->edges.erase(it);else if(!child->terminal&&child->edges.size()==1){auto only=child->edges.begin();auto merged=label+only->first;auto ptr=std::move(only->second);n->edges.erase(it);n->edges.emplace(std::move(merged),std::move(ptr));}return true;}return false;};del(root_.get(),s);--size_;return true;}
std::vector<std::string> RadixCommandCatalog::complete(const std::string&p,std::size_t limit)const{std::vector<std::string>out;if(!valid(p)||!limit)return out;std::function<void(const Node*,std::string)>walk=[&](const Node*n,std::string word){if(out.size()>=limit)return;if(n->terminal)out.push_back(word);for(const auto&e:n->edges)walk(e.second.get(),word+e.first);};std::function<void(const Node*,std::string,std::string)>seek=[&](const Node*n,std::string rest,std::string built){if(rest.empty()){walk(n,built);return;}for(const auto&e:n->edges){auto k=common(e.first,rest);if(k==rest.size()){walk(e.second.get(),built+e.first);return;}if(k==e.first.size()){seek(e.second.get(),rest.substr(k),built+e.first);return;}}};seek(root_.get(),p,"");out.erase(std::remove_if(out.begin(),out.end(),[&](const auto&s){return s.rfind(p,0)!=0;}),out.end());std::sort(out.begin(),out.end());if(out.size()>limit)out.resize(limit);return out;}
std::size_t RadixCommandCatalog::size()const{return size_;}
RadixCommandCatalog::Audit RadixCommandCatalog::audit_for_test()const{bool ok=true;std::size_t nodes=0,terms=0;std::function<void(const Node*,bool)>walk=[&](const Node*n,bool root){++nodes;if(n->terminal)++terms;if(!root&&!n->terminal&&n->edges.size()==1)ok=false;char prior=0;for(const auto&e:n->edges){if(e.first.empty()||(prior&&prior==e.first.front()))ok=false;prior=e.first.front();walk(e.second.get(),false);}};walk(root_.get(),true);return{ok&&terms==size_,nodes,terms};}
}'''
    stub = _stub(cls, '''bool RadixCommandCatalog::add(const std::string&){return false;} bool RadixCommandCatalog::erase(const std::string&){return false;} bool RadixCommandCatalog::contains(const std::string&)const{return false;} std::vector<std::string> RadixCommandCatalog::complete(const std::string&,std::size_t)const{return{};} std::size_t RadixCommandCatalog::size()const{return 0;}''')
    return Case("trie-command-completion","radix-command-catalog",cls,"Path-compressed command completion","Lower-case commands, lexical bounded completion, split/merge radix edges.",header,ref,stub,
        'RadixCommandCatalog x;check(x.add("car"));check(x.add("cart"));check(x.add("cat"));check(!x.add("car"));check((x.complete("ca",2)==std::vector<std::string>{"car","cart"}));check(x.erase("cart"));check(x.contains("car"));',
        'RadixCommandCatalog x;std::vector<std::string>model;for(int i=0;i<80;++i){std::string s="a"+std::string(1,char(\'a\'+i%8))+std::string(1,char(\'a\'+(i*3)%9));bool want=std::find(model.begin(),model.end(),s)==model.end();check(x.add(s)==want);if(want)model.push_back(s);if(i%4==0){check(x.erase(s));model.erase(std::find(model.begin(),model.end(),s));}auto got=x.complete("a",500);std::sort(model.begin(),model.end());check(got==model);check(x.audit_for_test().valid);} check(!x.add("A"));',
        ("std::map<std::string,std::unique_ptr<Node>>edges","common(","edges.size()==1","audit_for_test"))


def _case_tst() -> Case:
    cls="ProductPrefixTst"
    header=_header(cls,'''  struct Product { std::string code; int stock; };
  bool add(const std::string& code, int stock);
  bool set_stock(const std::string& code, int stock);
  bool erase(const std::string& code);
  std::optional<int> stock_of(const std::string& code) const;
  std::vector<Product> with_prefix(const std::string& prefix, std::size_t limit) const;''',"std::size_t nodes; std::size_t terminals;","  struct Node;\n  std::unique_ptr<Node> root_;")
    ref=r'''#include "task.h"
#include <algorithm>
#include <functional>
namespace curriculum{struct ProductPrefixTst::Node{explicit Node(char x):ch(x){}char ch;std::unique_ptr<Node>lo,eq,hi;std::optional<int>stock;};namespace{bool valid(const std::string&s){return !s.empty()&&std::all_of(s.begin(),s.end(),[](char c){return c>='A'&&c<='Z';});}}
ProductPrefixTst::ProductPrefixTst()=default;ProductPrefixTst::~ProductPrefixTst()=default;
bool ProductPrefixTst::add(const std::string&s,int stock){if(!valid(s)||stock<0)return false;std::function<bool(std::unique_ptr<Node>&,std::size_t)>put=[&](auto&n,std::size_t i){if(!n)n=std::make_unique<Node>(s[i]);if(s[i]<n->ch)return put(n->lo,i);if(s[i]>n->ch)return put(n->hi,i);if(i+1<s.size())return put(n->eq,i+1);if(n->stock)return false;n->stock=stock;return true;};return put(root_,0);}
std::optional<int> ProductPrefixTst::stock_of(const std::string&s)const{if(!valid(s))return{};const Node*n=root_.get();std::size_t i=0;while(n){if(s[i]<n->ch)n=n->lo.get();else if(s[i]>n->ch)n=n->hi.get();else if(++i==s.size())return n->stock;else n=n->eq.get();}return{};}
bool ProductPrefixTst::set_stock(const std::string&s,int v){if(v<0||!stock_of(s))return false;Node*n=root_.get();std::size_t i=0;while(n){if(s[i]<n->ch)n=n->lo.get();else if(s[i]>n->ch)n=n->hi.get();else if(++i==s.size()){n->stock=v;return true;}else n=n->eq.get();}return false;}
bool ProductPrefixTst::erase(const std::string&s){if(!stock_of(s))return false;Node*n=root_.get();std::size_t i=0;while(n){if(s[i]<n->ch)n=n->lo.get();else if(s[i]>n->ch)n=n->hi.get();else if(++i==s.size()){n->stock.reset();return true;}else n=n->eq.get();}return false;}
std::vector<ProductPrefixTst::Product> ProductPrefixTst::with_prefix(const std::string&p,std::size_t limit)const{std::vector<Product>out;if(!valid(p)||!limit)return out;const Node*n=root_.get();std::size_t i=0;while(n){if(p[i]<n->ch)n=n->lo.get();else if(p[i]>n->ch)n=n->hi.get();else if(++i==p.size())break;else n=n->eq.get();}if(!n)return out;if(n->stock)out.push_back({p,*n->stock});std::function<void(const Node*,std::string)>walk=[&](const Node*x,std::string w){if(!x||out.size()>=limit)return;walk(x->lo.get(),w);auto next=w+x->ch;if(x->stock)out.push_back({next,*x->stock});walk(x->eq.get(),next);walk(x->hi.get(),w);};walk(n->eq.get(),p);if(out.size()>limit)out.resize(limit);return out;}
ProductPrefixTst::Audit ProductPrefixTst::audit_for_test()const{bool ok=true;std::size_t nodes=0,terms=0;std::function<void(const Node*,int,int)>walk=[&](const Node*n,int low,int high){if(!n)return;++nodes;if(n->ch<=low||n->ch>=high)ok=false;if(n->stock)++terms;walk(n->lo,low,n->ch);walk(n->eq,0,127);walk(n->hi,n->ch,127);};walk(root_.get(),0,127);return{ok,nodes,terms};}}
'''
    # fix unique_ptr arguments are passed as raw pointers through implicit get below in generated source
    ref=ref.replace("walk(n->lo,low", "walk(n->lo.get(),low").replace("walk(n->eq,0", "walk(n->eq.get(),0").replace("walk(n->hi,n->ch", "walk(n->hi.get(),n->ch")
    stub=_stub(cls,'''bool ProductPrefixTst::add(const std::string&,int){return false;} bool ProductPrefixTst::set_stock(const std::string&,int){return false;} bool ProductPrefixTst::erase(const std::string&){return false;} std::optional<int> ProductPrefixTst::stock_of(const std::string&)const{return{};} std::vector<ProductPrefixTst::Product> ProductPrefixTst::with_prefix(const std::string&,std::size_t)const{return{};}''')
    return Case("trie-product-search","tst-product-prefix",cls,"Ternary-search-trie product inventory","Upper-case codes with mutable stock and lexical prefix traversal.",header,ref,stub,
      'ProductPrefixTst x;check(x.add("AX",4));check(x.add("AB",2));check(!x.add("AX",9));check(x.set_stock("AX",7));check(x.stock_of("AX")==7);auto v=x.with_prefix("A",9);check(v.size()==2&&v[0].code=="AB");',
      'ProductPrefixTst x;std::vector<std::pair<std::string,int>>m;for(int i=0;i<60;++i){std::string s="P"+std::string(1,char(\'A\'+i%20))+std::string(1,char(\'A\'+(i*7)%23));bool exists=std::find_if(m.begin(),m.end(),[&](const auto&e){return e.first==s;})!=m.end();check(x.add(s,i)==!exists);if(!exists)m.push_back({s,i});check(x.audit_for_test().valid);}check(!x.add("bad",1));',
      ("std::unique_ptr<Node>lo,eq,hi","s[i]<n->ch","walk(x->lo","audit_for_test"))


def _case_digit() -> Case:
    cls="DigitCallRangeTrie"
    header=_header(cls,'''  bool add(const std::string& call_number);
  bool erase(const std::string& call_number);
  bool contains(const std::string& call_number) const;
  std::size_t count_prefix(const std::string& prefix) const;
  std::optional<std::string> next_after(const std::string& prefix, const std::string& after) const;''',"std::size_t nodes; std::size_t terminals;","  struct Node;\n  std::unique_ptr<Node> root_;")
    ref=r'''#include "task.h"
#include <algorithm>
#include <functional>
namespace curriculum{struct DigitCallRangeTrie::Node{std::array<std::unique_ptr<Node>,10>child;bool terminal=false;std::size_t below=0;};namespace{bool valid_key(const std::string&s,bool empty=false){return (empty||!s.empty())&&s.size()<=12&&std::all_of(s.begin(),s.end(),[](char c){return c>='0'&&c<='9';});}}
DigitCallRangeTrie::DigitCallRangeTrie():root_(std::make_unique<Node>()){}DigitCallRangeTrie::~DigitCallRangeTrie()=default;
bool DigitCallRangeTrie::add(const std::string&s){if(!valid_key(s))return false;Node*n=root_.get();std::vector<Node*>path{n};for(char c:s){auto&i=n->child[std::size_t(c-'0')];if(!i)i=std::make_unique<Node>();n=i.get();path.push_back(n);}if(n->terminal)return false;n->terminal=true;for(auto*x:path)++x->below;return true;}
bool DigitCallRangeTrie::contains(const std::string&s)const{if(!valid_key(s))return false;const Node*n=root_.get();for(char c:s){n=n->child[std::size_t(c-'0')].get();if(!n)return false;}return n->terminal;}
bool DigitCallRangeTrie::erase(const std::string&s){if(!contains(s))return false;Node*n=root_.get();std::vector<Node*>path{n};std::vector<std::pair<Node*,std::size_t>>edges;for(char c:s){auto i=std::size_t(c-'0');edges.push_back({n,i});n=n->child[i].get();path.push_back(n);}n->terminal=false;for(auto*x:path)--x->below;for(std::size_t i=edges.size();i>0;--i)if(edges[i-1].first->child[edges[i-1].second]->below==0)edges[i-1].first->child[edges[i-1].second].reset();else break;return true;}
std::size_t DigitCallRangeTrie::count_prefix(const std::string&p)const{if(!valid_key(p,true))return 0;const Node*n=root_.get();for(char c:p){n=n->child[std::size_t(c-'0')].get();if(!n)return 0;}return n->below;}
std::optional<std::string> DigitCallRangeTrie::next_after(const std::string&p,const std::string&after)const{if(!valid_key(p,true)||!valid_key(after,true))return{};const Node*n=root_.get();for(char c:p){n=n->child[std::size_t(c-'0')].get();if(!n)return{};}std::optional<std::string>answer;std::function<void(const Node*,std::string)>walk=[&](const Node*x,std::string word){if(answer)return;if(x->terminal&&word>after){answer=word;return;}for(std::size_t i=0;i<10&&!answer;++i)if(x->child[i])walk(x->child[i].get(),word+char('0'+i));};walk(n,p);return answer;}
DigitCallRangeTrie::Audit DigitCallRangeTrie::audit_for_test()const{bool ok=true;std::size_t nodes=0,terms=0;std::function<std::size_t(const Node*)>walk=[&](const Node*n){++nodes;std::size_t sum=n->terminal?1U:0U;if(n->terminal)++terms;for(const auto&c:n->child)if(c)sum+=walk(c.get());if(sum!=n->below)ok=false;return sum;};walk(root_.get());return{ok,nodes,terms};}}
'''
    stub=_stub(cls,'''bool DigitCallRangeTrie::add(const std::string&){return false;} bool DigitCallRangeTrie::erase(const std::string&){return false;} bool DigitCallRangeTrie::contains(const std::string&)const{return false;} std::size_t DigitCallRangeTrie::count_prefix(const std::string&)const{return 0;} std::optional<std::string> DigitCallRangeTrie::next_after(const std::string&,const std::string&)const{return{};}''')
    return Case("trie-library-call-prefixes","digit-call-range-trie",cls,"Digit-trie counted ranges","Digit-only prefix counts and lexical successors from fixed branches.",header,ref,stub,
      'DigitCallRangeTrie x;check(x.add("12"));check(x.add("120"));check(x.add("13"));check(x.count_prefix("12")==2);check(x.next_after("1","12")==std::optional<std::string>("120"));check(x.erase("12"));check(x.contains("120"));',
      'DigitCallRangeTrie x;std::vector<std::string>m;for(int i=0;i<90;++i){std::string s=std::to_string(1000+(i*37)%701);bool want=std::find(m.begin(),m.end(),s)==m.end();check(x.add(s)==want);if(want)m.push_back(s);if(i%5==0){check(x.erase(s));m.erase(std::find(m.begin(),m.end(),s));}std::size_t count=0;for(const auto&v:m)if(v.rfind("1",0)==0)++count;check(x.count_prefix("1")==count);check(x.audit_for_test().valid);}check(!x.add("12x"));',
      ("std::array<std::unique_ptr<Node>,10>","below","next_after","audit_for_test"))


def _case_dna() -> Case:
    cls="DnaMotifCounterTrie"
    header=_header(cls,'''  bool add(const std::string& motif);
  bool erase(const std::string& motif);
  bool contains(const std::string& motif) const;
  std::size_t count_prefix(const std::string& prefix) const;
  std::optional<std::string> longest_stored_prefix(const std::string& sequence) const;''',"std::size_t nodes; std::size_t terminals;","  struct Node;\n  std::unique_ptr<Node> root_;")
    # Reuse digit algorithm after translating a four-symbol alphabet, while preserving a separate fixed representation.
    ref=r'''#include "task.h"
#include <algorithm>
#include <functional>
namespace curriculum{struct DnaMotifCounterTrie::Node{std::array<std::unique_ptr<Node>,4>child;bool terminal=false;std::size_t below=0;};namespace{int slot(char c){return c=='A'?0:c=='C'?1:c=='G'?2:c=='T'?3:-1;}bool valid(const std::string&s,bool empty=false){return(empty||!s.empty())&&std::all_of(s.begin(),s.end(),[](char c){return slot(c)>=0;});}}
DnaMotifCounterTrie::DnaMotifCounterTrie():root_(std::make_unique<Node>()){}DnaMotifCounterTrie::~DnaMotifCounterTrie()=default;
bool DnaMotifCounterTrie::add(const std::string&s){if(!valid(s))return false;Node*n=root_.get();std::vector<Node*>path{n};for(char c:s){auto&i=n->child[std::size_t(slot(c))];if(!i)i=std::make_unique<Node>();n=i.get();path.push_back(n);}if(n->terminal)return false;n->terminal=true;for(auto*x:path)++x->below;return true;}
bool DnaMotifCounterTrie::contains(const std::string&s)const{if(!valid(s))return false;const Node*n=root_.get();for(char c:s){n=n->child[std::size_t(slot(c))].get();if(!n)return false;}return n->terminal;}
bool DnaMotifCounterTrie::erase(const std::string&s){if(!contains(s))return false;Node*n=root_.get();std::vector<Node*>path{n};std::vector<std::pair<Node*,std::size_t>>edges;for(char c:s){auto i=std::size_t(slot(c));edges.push_back({n,i});n=n->child[i].get();path.push_back(n);}n->terminal=false;for(auto*x:path)--x->below;for(std::size_t i=edges.size();i>0;--i)if(edges[i-1].first->child[edges[i-1].second]->below==0)edges[i-1].first->child[edges[i-1].second].reset();else break;return true;}
std::size_t DnaMotifCounterTrie::count_prefix(const std::string&p)const{if(!valid(p,true))return 0;const Node*n=root_.get();for(char c:p){n=n->child[std::size_t(slot(c))].get();if(!n)return 0;}return n->below;}
std::optional<std::string>DnaMotifCounterTrie::longest_stored_prefix(const std::string&s)const{if(!valid(s,true))return{};const Node*n=root_.get();std::optional<std::string>out;std::string seen;for(char c:s){n=n->child[std::size_t(slot(c))].get();if(!n)break;seen+=c;if(n->terminal)out=seen;}return out;}
DnaMotifCounterTrie::Audit DnaMotifCounterTrie::audit_for_test()const{bool ok=true;std::size_t nodes=0,terms=0;std::function<std::size_t(const Node*)>walk=[&](const Node*n){++nodes;std::size_t sum=n->terminal?1U:0U;if(n->terminal)++terms;for(const auto&c:n->child)if(c)sum+=walk(c.get());if(sum!=n->below)ok=false;return sum;};walk(root_.get());return{ok,nodes,terms};}}
'''
    stub=_stub(cls,'''bool DnaMotifCounterTrie::add(const std::string&){return false;} bool DnaMotifCounterTrie::erase(const std::string&){return false;} bool DnaMotifCounterTrie::contains(const std::string&)const{return false;} std::size_t DnaMotifCounterTrie::count_prefix(const std::string&)const{return 0;} std::optional<std::string> DnaMotifCounterTrie::longest_stored_prefix(const std::string&)const{return{};}''')
    return Case("trie-dna-motifs","dna-motif-counter-trie",cls,"Four-way DNA motif counters","A/C/G/T branches, subtree motif counts, and longest stored sequence prefix.",header,ref,stub,
      'DnaMotifCounterTrie x;check(x.add("AC"));check(x.add("ACG"));check(x.add("ACT"));check(x.count_prefix("AC")==3);check(x.longest_stored_prefix("ACGA")==std::optional<std::string>("ACG"));check(x.erase("AC"));check(x.contains("ACG"));',
      'DnaMotifCounterTrie x;std::vector<std::string>m;const std::string alpha="ACGT";for(int i=0;i<80;++i){std::string s;for(int j=0;j<4;++j)s+=alpha[std::size_t((i*7+j*3)%4)];s+=alpha[std::size_t(i%4)];bool want=std::find(m.begin(),m.end(),s)==m.end();check(x.add(s)==want);if(want)m.push_back(s);if(i%6==0&&want){check(x.erase(s));m.pop_back();}check(x.audit_for_test().valid);}check(!x.add("AX"));',
      ("std::array<std::unique_ptr<Node>,4>","slot(char","below","longest_stored_prefix"))


def _case_contact() -> Case:
    cls="ContactAliasTrie"
    header=_header(cls,'''  struct Contact { int id; std::string normalized_name; };
  bool add(int id, const std::string& name);
  bool rename(int id, const std::string& name);
  bool erase(int id);
  std::vector<Contact> search(const std::string& prefix) const;''',"std::size_t nodes; std::size_t contacts;","  struct Node;\n  std::unique_ptr<Node> root_;\n  std::unordered_map<int,std::string> names_;")
    ref=r'''#include "task.h"
#include <algorithm>
#include <cctype>
#include <functional>
namespace curriculum{struct ContactAliasTrie::Node{std::map<char,std::unique_ptr<Node>>child;std::set<int>ids;};namespace{std::optional<std::string>norm(const std::string&s){std::string out;bool space=false;for(unsigned char c:s){if(c==' '){if(!out.empty())space=true;continue;}if(!std::isalpha(c))return{};if(space){out+=' ';space=false;}out+=char(std::tolower(c));}if(out.empty())return{};return out;}}
ContactAliasTrie::ContactAliasTrie():root_(std::make_unique<Node>()){}ContactAliasTrie::~ContactAliasTrie()=default;
bool ContactAliasTrie::add(int id,const std::string&raw){auto name=norm(raw);if(id<=0||!name||names_.count(id))return false;Node*n=root_.get();for(char c:*name){auto&p=n->child[c];if(!p)p=std::make_unique<Node>();n=p.get();}n->ids.insert(id);names_[id]=*name;return true;}
bool ContactAliasTrie::erase(int id){auto found=names_.find(id);if(found==names_.end())return false;std::vector<std::pair<Node*,char>>path;Node*n=root_.get();for(char c:found->second){path.push_back({n,c});n=n->child[c].get();}n->ids.erase(id);names_.erase(found);for(std::size_t i=path.size();i>0;--i){auto&ptr=path[i-1].first->child[path[i-1].second];if(ptr->ids.empty()&&ptr->child.empty())ptr.reset(),path[i-1].first->child.erase(path[i-1].second);else break;}return true;}
bool ContactAliasTrie::rename(int id,const std::string&raw){auto name=norm(raw);auto old=names_.find(id);if(!name||old==names_.end())return false;std::string prior=old->second;if(prior==*name)return true;erase(id);if(add(id,*name))return true;add(id,prior);return false;}
std::vector<ContactAliasTrie::Contact>ContactAliasTrie::search(const std::string&raw)const{auto prefix=norm(raw);std::vector<Contact>out;if(!prefix)return out;const Node*n=root_.get();for(char c:*prefix){auto it=n->child.find(c);if(it==n->child.end())return{};n=it->second.get();}std::function<void(const Node*,std::string)>walk=[&](const Node*x,std::string word){for(int id:x->ids)out.push_back({id,word});for(const auto&e:x->child)walk(e.second.get(),word+e.first);};walk(n,*prefix);std::sort(out.begin(),out.end(),[](const auto&a,const auto&b){return a.normalized_name!=b.normalized_name?a.normalized_name<b.normalized_name:a.id<b.id;});return out;}
ContactAliasTrie::Audit ContactAliasTrie::audit_for_test()const{std::size_t nodes=0,contacts=0;bool ok=true;std::function<void(const Node*)>walk=[&](const Node*n){++nodes;contacts+=n->ids.size();for(int id:n->ids)if(!names_.count(id))ok=false;for(const auto&e:n->child)walk(e.second.get());};walk(root_.get());return{ok&&contacts==names_.size(),nodes,contacts};}}
'''
    stub=_stub(cls,'''bool ContactAliasTrie::add(int,const std::string&){return false;} bool ContactAliasTrie::rename(int,const std::string&){return false;} bool ContactAliasTrie::erase(int){return false;} std::vector<ContactAliasTrie::Contact> ContactAliasTrie::search(const std::string&)const{return{};}''')
    return Case("trie-contact-directory","contact-alias-trie",cls,"Normalized contact-ID trie","Atomic rename and prefix results through terminal ID postings.",header,ref,stub,
      'ContactAliasTrie x;check(x.add(2,"Ada  Lovelace"));check(x.add(1,"ada lee"));check(!x.add(1,"other"));auto v=x.search("ADA ");check(v.size()==2&&v[0].id==1);check(x.rename(2,"Grace Hopper"));check(x.search("ada").size()==1);',
      'ContactAliasTrie x;std::vector<std::pair<int,std::string>>m;for(int i=1;i<=50;++i){std::string name="person "+std::string(1,char(\'a\'+i%20));check(x.add(i,name));m.push_back({i,name});if(i%7==0){check(x.rename(i,"renamed "+std::string(1,char(\'a\'+i%20))));}check(x.audit_for_test().valid);}for(int i=1;i<=50;i+=3)check(x.erase(i));check(x.audit_for_test().contacts==33);check(!x.add(-1,"bad"));',
      ("std::set<int>ids","names_","norm(","walk(e.second.get()"))


def _case_route() -> Case:
    cls="SegmentRouteDispatchTrie"
    header=_header(cls,'''  struct Match { int handler; std::size_t consumed_segments; };
  bool set(const std::vector<std::string>& segments, int handler);
  bool erase(const std::vector<std::string>& segments);
  std::optional<Match> resolve(const std::vector<std::string>& path) const;
  std::size_t route_count_under(const std::vector<std::string>& prefix) const;''',"std::size_t nodes; std::size_t routes;","  struct Node;\n  std::unique_ptr<Node> root_;")
    ref=r'''#include "task.h"
#include <algorithm>
#include <functional>
namespace curriculum{struct SegmentRouteDispatchTrie::Node{std::map<std::string,std::unique_ptr<Node>>child;std::optional<int>handler;std::size_t routes=0;};namespace{bool valid(const std::vector<std::string>&v,bool empty=false){if(v.empty())return empty;for(const auto&s:v)if(s.empty()||!std::all_of(s.begin(),s.end(),[](char c){return(c>='a'&&c<='z')||(c>='0'&&c<='9')||c=='-';}))return false;return true;}}
SegmentRouteDispatchTrie::SegmentRouteDispatchTrie():root_(std::make_unique<Node>()){}SegmentRouteDispatchTrie::~SegmentRouteDispatchTrie()=default;
bool SegmentRouteDispatchTrie::set(const std::vector<std::string>&v,int h){if(h<=0||!valid(v))return false;Node*n=root_.get();std::vector<Node*>path{n};for(const auto&s:v){auto&p=n->child[s];if(!p)p=std::make_unique<Node>();n=p.get();path.push_back(n);}if(n->handler)return false;n->handler=h;for(auto*x:path)++x->routes;return true;}
bool SegmentRouteDispatchTrie::erase(const std::vector<std::string>&v){if(!valid(v))return false;Node*n=root_.get();std::vector<Node*>path{n};std::vector<std::pair<Node*,std::string>>edges;for(const auto&s:v){auto it=n->child.find(s);if(it==n->child.end())return false;edges.push_back({n,s});n=it->second.get();path.push_back(n);}if(!n->handler)return false;n->handler.reset();for(auto*x:path)--x->routes;for(std::size_t i=edges.size();i>0;--i){auto&p=edges[i-1].first->child[edges[i-1].second];if(p->routes==0)edges[i-1].first->child.erase(edges[i-1].second);else break;}return true;}
std::optional<SegmentRouteDispatchTrie::Match>SegmentRouteDispatchTrie::resolve(const std::vector<std::string>&v)const{if(!valid(v,true))return{};const Node*n=root_.get();std::optional<Match>out;if(n->handler)out=Match{*n->handler,0};for(std::size_t i=0;i<v.size();++i){auto it=n->child.find(v[i]);if(it==n->child.end())break;n=it->second.get();if(n->handler)out=Match{*n->handler,i+1};}return out;}
std::size_t SegmentRouteDispatchTrie::route_count_under(const std::vector<std::string>&v)const{if(!valid(v,true))return 0;const Node*n=root_.get();for(const auto&s:v){auto it=n->child.find(s);if(it==n->child.end())return 0;n=it->second.get();}return n->routes;}
SegmentRouteDispatchTrie::Audit SegmentRouteDispatchTrie::audit_for_test()const{bool ok=true;std::size_t nodes=0,routes=0;std::function<std::size_t(const Node*)>walk=[&](const Node*n){++nodes;std::size_t sum=n->handler?1U:0U;if(n->handler)++routes;for(const auto&e:n->child)sum+=walk(e.second.get());if(sum!=n->routes)ok=false;return sum;};walk(root_.get());return{ok,nodes,routes};}}
'''
    stub=_stub(cls,'''bool SegmentRouteDispatchTrie::set(const std::vector<std::string>&,int){return false;} bool SegmentRouteDispatchTrie::erase(const std::vector<std::string>&){return false;} std::optional<SegmentRouteDispatchTrie::Match> SegmentRouteDispatchTrie::resolve(const std::vector<std::string>&)const{return{};} std::size_t SegmentRouteDispatchTrie::route_count_under(const std::vector<std::string>&)const{return 0;}''')
    return Case("trie-url-router","segment-route-dispatch-trie",cls,"Segment route longest-prefix dispatch","Segment-keyed route terminals and deepest ancestor resolution.",header,ref,stub,
      'SegmentRouteDispatchTrie x;check(x.set({"api"},1));check(x.set({"api","v2"},2));check(x.resolve({"api","v2","users"})->handler==2);check(x.resolve({"api","v1"})->handler==1);check(x.route_count_under({"api"})==2);',
      'SegmentRouteDispatchTrie x;std::vector<std::vector<std::string>>m;for(int i=0;i<60;++i){auto v=std::vector<std::string>{"r",std::to_string(i%17),std::to_string(i)};check(x.set(v,i+1));m.push_back(v);if(i%5==0){check(x.erase(v));m.pop_back();}check(x.route_count_under({"r"})==m.size());check(x.audit_for_test().valid);}check(!x.set({"bad/seg"},1));',
      ("std::map<std::string,std::unique_ptr<Node>>child","Match{","routes","resolve("))


def _case_dns() -> Case:
    cls="ReversedDomainPolicyTrie"
    header=_header(cls,'''  struct Match { std::string suffix; int policy; };
  bool set(const std::string& domain_suffix, int policy);
  bool erase(const std::string& domain_suffix);
  std::optional<Match> resolve(const std::string& host) const;
  std::size_t rule_count() const;''',"std::size_t nodes; std::size_t rules;","  struct Node;\n  std::unique_ptr<Node> root_;\n  std::size_t rules_ = 0;")
    ref=r'''#include "task.h"
#include <algorithm>
#include <functional>
#include <sstream>
namespace curriculum{struct ReversedDomainPolicyTrie::Node{std::map<std::string,std::unique_ptr<Node>>child;std::optional<int>policy;};namespace{std::optional<std::vector<std::string>>labels(const std::string&s){if(s.empty())return{};std::vector<std::string>v;std::string part;std::istringstream in(s);while(std::getline(in,part,'.')){if(part.empty()||!std::all_of(part.begin(),part.end(),[](char c){return(c>='a'&&c<='z')||(c>='0'&&c<='9')||c=='-';}))return{};v.push_back(part);}std::reverse(v.begin(),v.end());return v;}std::string suffix(const std::vector<std::string>&v,std::size_t n){std::string out;for(std::size_t i=n;i>0;--i){if(!out.empty())out+='.';out+=v[i-1];}return out;}}
ReversedDomainPolicyTrie::ReversedDomainPolicyTrie():root_(std::make_unique<Node>()){}ReversedDomainPolicyTrie::~ReversedDomainPolicyTrie()=default;
bool ReversedDomainPolicyTrie::set(const std::string&s,int p){auto v=labels(s);if(!v||p<=0)return false;Node*n=root_.get();for(const auto&label:*v){auto&x=n->child[label];if(!x)x=std::make_unique<Node>();n=x.get();}if(n->policy)return false;n->policy=p;++rules_;return true;}
bool ReversedDomainPolicyTrie::erase(const std::string&s){auto v=labels(s);if(!v)return false;Node*n=root_.get();std::vector<std::pair<Node*,std::string>>path;for(const auto&x:*v){auto it=n->child.find(x);if(it==n->child.end())return false;path.push_back({n,x});n=it->second.get();}if(!n->policy)return false;n->policy.reset();--rules_;for(std::size_t i=path.size();i>0;--i){auto&p=path[i-1].first->child[path[i-1].second];if(!p->policy&&p->child.empty())path[i-1].first->child.erase(path[i-1].second);else break;}return true;}
std::optional<ReversedDomainPolicyTrie::Match>ReversedDomainPolicyTrie::resolve(const std::string&s)const{auto v=labels(s);if(!v)return{};const Node*n=root_.get();std::optional<Match>out;for(std::size_t i=0;i<v->size();++i){auto it=n->child.find((*v)[i]);if(it==n->child.end())break;n=it->second.get();if(n->policy)out=Match{suffix(*v,i+1),*n->policy};}return out;}
std::size_t ReversedDomainPolicyTrie::rule_count()const{return rules_;}
ReversedDomainPolicyTrie::Audit ReversedDomainPolicyTrie::audit_for_test()const{std::size_t nodes=0,rules=0;std::function<void(const Node*)>walk=[&](const Node*n){++nodes;if(n->policy)++rules;for(const auto&e:n->child)walk(e.second.get());};walk(root_.get());return{rules==rules_,nodes,rules};}}
'''
    stub=_stub(cls,'''bool ReversedDomainPolicyTrie::set(const std::string&,int){return false;} bool ReversedDomainPolicyTrie::erase(const std::string&){return false;} std::optional<ReversedDomainPolicyTrie::Match> ReversedDomainPolicyTrie::resolve(const std::string&)const{return{};} std::size_t ReversedDomainPolicyTrie::rule_count()const{return 0;}''')
    return Case("trie-dns-suffixes","reversed-domain-policy-trie",cls,"Reversed-label suffix policy","Most-specific DNS-style suffix matching by reversed labels.",header,ref,stub,
      'ReversedDomainPolicyTrie x;check(x.set("example.com",1));check(x.set("api.example.com",2));check(x.resolve("v2.api.example.com")->policy==2);check(x.resolve("www.example.com")->suffix=="example.com");check(x.erase("api.example.com"));',
      'ReversedDomainPolicyTrie x;for(int i=0;i<40;++i){std::string d="s"+std::to_string(i)+".example.org";check(x.set(d,i+1));check(x.resolve("host."+d)->policy==i+1);check(x.audit_for_test().valid);}for(int i=0;i<40;i+=2)check(x.erase("s"+std::to_string(i)+".example.org"));check(x.rule_count()==20);check(!x.set("bad..org",1));',
      ("std::reverse(v.begin(),v.end())","suffix(","policy","labels("))


def _case_shortcode() -> Case:
    cls="UniqueShortcodeTrie"
    header=_header(cls,'''  bool add(const std::string& shortcode, const std::string& expansion);
  bool erase(const std::string& shortcode);
  std::optional<std::string> expand_unique(const std::string& prefix) const;
  std::size_t count_prefix(const std::string& prefix) const;''',"std::size_t nodes; std::size_t terminals;","  struct Node;\n  std::unique_ptr<Node> root_;")
    ref=r'''#include "task.h"
#include <algorithm>
#include <functional>
namespace curriculum{struct UniqueShortcodeTrie::Node{std::map<char,std::unique_ptr<Node>>child;std::optional<std::string>value;std::size_t below=0;};namespace{bool valid(const std::string&s,bool empty=false){return(empty||!s.empty())&&std::all_of(s.begin(),s.end(),[](char c){return(c>='a'&&c<='z')||(c>='0'&&c<='9')||c=='_';});}}
UniqueShortcodeTrie::UniqueShortcodeTrie():root_(std::make_unique<Node>()){}UniqueShortcodeTrie::~UniqueShortcodeTrie()=default;
bool UniqueShortcodeTrie::add(const std::string&s,const std::string&v){if(!valid(s)||v.empty())return false;Node*n=root_.get();std::vector<Node*>path{n};for(char c:s){auto&p=n->child[c];if(!p)p=std::make_unique<Node>();n=p.get();path.push_back(n);}if(n->value)return false;n->value=v;for(auto*x:path)++x->below;return true;}
bool UniqueShortcodeTrie::erase(const std::string&s){if(!valid(s))return false;Node*n=root_.get();std::vector<Node*>path{n};std::vector<std::pair<Node*,char>>edges;for(char c:s){auto it=n->child.find(c);if(it==n->child.end())return false;edges.push_back({n,c});n=it->second.get();path.push_back(n);}if(!n->value)return false;n->value.reset();for(auto*x:path)--x->below;for(std::size_t i=edges.size();i>0;--i){auto&p=edges[i-1].first->child[edges[i-1].second];if(p->below==0)edges[i-1].first->child.erase(edges[i-1].second);else break;}return true;}
std::size_t UniqueShortcodeTrie::count_prefix(const std::string&s)const{if(!valid(s,true))return 0;const Node*n=root_.get();for(char c:s){auto it=n->child.find(c);if(it==n->child.end())return 0;n=it->second.get();}return n->below;}
std::optional<std::string>UniqueShortcodeTrie::expand_unique(const std::string&s)const{if(count_prefix(s)!=1)return{};const Node*n=root_.get();for(char c:s)n=n->child.at(c).get();while(!n->value){if(n->child.size()!=1)return{};n=n->child.begin()->second.get();}return n->value;}
UniqueShortcodeTrie::Audit UniqueShortcodeTrie::audit_for_test()const{bool ok=true;std::size_t nodes=0,terms=0;std::function<std::size_t(const Node*)>walk=[&](const Node*n){++nodes;std::size_t sum=n->value?1U:0U;if(n->value)++terms;for(const auto&e:n->child)sum+=walk(e.second.get());if(sum!=n->below)ok=false;return sum;};walk(root_.get());return{ok,nodes,terms};}}
'''
    stub=_stub(cls,'''bool UniqueShortcodeTrie::add(const std::string&,const std::string&){return false;} bool UniqueShortcodeTrie::erase(const std::string&){return false;} std::optional<std::string> UniqueShortcodeTrie::expand_unique(const std::string&)const{return{};} std::size_t UniqueShortcodeTrie::count_prefix(const std::string&)const{return 0;}''')
    return Case("trie-emoji-shortcodes","unique-shortcode-trie",cls,"Unique-prefix payload expansion","Descendant counts decide unique expansion without enumeration.",header,ref,stub,
      'UniqueShortcodeTrie x;check(x.add("smile","happy"));check(x.expand_unique("s")==std::optional<std::string>("happy"));check(x.add("smirk","wry"));check(!x.expand_unique("sm"));check(x.erase("smirk"));check(x.expand_unique("sm")==std::optional<std::string>("happy"));',
      'UniqueShortcodeTrie x;std::vector<std::string>m;for(int i=0;i<70;++i){std::string s="tag_"+std::to_string(i);check(x.add(s,s+"_value"));m.push_back(s);check(x.count_prefix("tag_")==m.size());check(x.audit_for_test().valid);}for(int i=0;i<70;i+=2)check(x.erase("tag_"+std::to_string(i)));check(x.count_prefix("tag_")==35);check(!x.add("bad!","x"));',
      ("below","expand_unique","child.size()!=1","std::optional<std::string>value"))


def _case_spell() -> Case:
    cls="LevenshteinSpellTrie"
    header=_header(cls,'''  struct Suggestion { std::string word; int distance; };
  bool add(const std::string& word);
  bool erase(const std::string& word);
  bool contains(const std::string& word) const;
  std::vector<Suggestion> suggest(const std::string& query, int max_distance, std::size_t limit) const;''',"std::size_t nodes; std::size_t terminals;","  struct Node;\n  std::unique_ptr<Node> root_;")
    ref=r'''#include "task.h"
#include <algorithm>
#include <functional>
namespace curriculum{struct LevenshteinSpellTrie::Node{std::map<char,std::unique_ptr<Node>>child;bool terminal=false;};namespace{bool valid(const std::string&s){return !s.empty()&&std::all_of(s.begin(),s.end(),[](char c){return c>='a'&&c<='z';});}}
LevenshteinSpellTrie::LevenshteinSpellTrie():root_(std::make_unique<Node>()){}LevenshteinSpellTrie::~LevenshteinSpellTrie()=default;
bool LevenshteinSpellTrie::add(const std::string&s){if(!valid(s))return false;Node*n=root_.get();for(char c:s){auto&p=n->child[c];if(!p)p=std::make_unique<Node>();n=p.get();}if(n->terminal)return false;n->terminal=true;return true;}
bool LevenshteinSpellTrie::contains(const std::string&s)const{if(!valid(s))return false;const Node*n=root_.get();for(char c:s){auto it=n->child.find(c);if(it==n->child.end())return false;n=it->second.get();}return n->terminal;}
bool LevenshteinSpellTrie::erase(const std::string&s){if(!contains(s))return false;Node*n=root_.get();std::vector<std::pair<Node*,char>>path;for(char c:s){path.push_back({n,c});n=n->child[c].get();}n->terminal=false;for(std::size_t i=path.size();i>0;--i){auto&p=path[i-1].first->child[path[i-1].second];if(!p->terminal&&p->child.empty())path[i-1].first->child.erase(path[i-1].second);else break;}return true;}
std::vector<LevenshteinSpellTrie::Suggestion>LevenshteinSpellTrie::suggest(const std::string&q,int bound,std::size_t limit)const{std::vector<Suggestion>out;if(!valid(q)||bound<0||bound>2||!limit)return out;std::vector<int>initial(q.size()+1);for(std::size_t i=0;i<initial.size();++i)initial[i]=int(i);std::function<void(const Node*,char,std::string,const std::vector<int>&)>walk=[&](const Node*n,char ch,std::string word,const std::vector<int>&prior){std::vector<int>row(q.size()+1);row[0]=prior[0]+1;int minimum=row[0];for(std::size_t i=1;i<row.size();++i){row[i]=std::min({row[i-1]+1,prior[i]+1,prior[i-1]+(q[i-1]==ch?0:1)});minimum=std::min(minimum,row[i]);}word+=ch;if(n->terminal&&row.back()<=bound)out.push_back({word,row.back()});if(minimum<=bound)for(const auto&e:n->child)walk(e.second.get(),e.first,word,row);};for(const auto&e:root_->child)walk(e.second.get(),e.first,"",initial);std::sort(out.begin(),out.end(),[](const auto&a,const auto&b){return a.distance!=b.distance?a.distance<b.distance:a.word<b.word;});if(out.size()>limit)out.resize(limit);return out;}
LevenshteinSpellTrie::Audit LevenshteinSpellTrie::audit_for_test()const{std::size_t nodes=0,terms=0;std::function<void(const Node*)>walk=[&](const Node*n){++nodes;if(n->terminal)++terms;for(const auto&e:n->child)walk(e.second.get());};walk(root_.get());return{true,nodes,terms};}}
'''
    stub=_stub(cls,'''bool LevenshteinSpellTrie::add(const std::string&){return false;} bool LevenshteinSpellTrie::erase(const std::string&){return false;} bool LevenshteinSpellTrie::contains(const std::string&)const{return false;} std::vector<LevenshteinSpellTrie::Suggestion> LevenshteinSpellTrie::suggest(const std::string&,int,std::size_t)const{return{};}''')
    return Case("trie-spell-checker","levenshtein-spell-trie",cls,"Edit-distance trie search","Dynamic-programming rows travel down edges and prune distant subtrees.",header,ref,stub,
      'LevenshteinSpellTrie x;check(x.add("cat"));check(x.add("cart"));check(x.add("dog"));auto v=x.suggest("cot",1,9);check(v.size()==1&&v[0].word=="cat"&&v[0].distance==1);check(x.erase("cart"));',
      'LevenshteinSpellTrie x;for(int i=0;i<50;++i)check(x.add("word"+std::string(1,char(\'a\'+i%26))+std::string(1,char(\'a\'+(i/26)))));auto exact=x.suggest("wordaa",0,5);check(exact.size()==1&&exact[0].distance==0);auto near=x.suggest("wordaz",1,100);check(!near.empty());check(x.audit_for_test().terminals==50);check(x.suggest("word",3,1).empty());',
      ("std::vector<int>row","prior[i-1]","minimum<=bound","distance"))


def _case_path() -> Case:
    cls="PathDescendantTrie"
    header=_header(cls,'''  bool add_file(const std::vector<std::string>& segments, long long bytes);
  bool erase_file(const std::vector<std::string>& segments);
  std::size_t descendant_files(const std::vector<std::string>& directory) const;
  long long descendant_bytes(const std::vector<std::string>& directory) const;
  std::vector<std::string> child_names(const std::vector<std::string>& directory) const;''',"std::size_t nodes; std::size_t files; long long bytes;","  struct Node;\n  std::unique_ptr<Node> root_;")
    ref=r'''#include "task.h"
#include <algorithm>
#include <functional>
#include <limits>
namespace curriculum{struct PathDescendantTrie::Node{std::map<std::string,std::unique_ptr<Node>>child;std::optional<long long>file_bytes;std::size_t files=0;long long bytes=0;};namespace{bool valid(const std::vector<std::string>&v,bool empty=false){if(v.empty())return empty;for(const auto&s:v)if(s.empty()||s=="."||s==".."||s.find('/')!=std::string::npos)return false;return true;}}
PathDescendantTrie::PathDescendantTrie():root_(std::make_unique<Node>()){}PathDescendantTrie::~PathDescendantTrie()=default;
bool PathDescendantTrie::add_file(const std::vector<std::string>&v,long long bytes){if(!valid(v)||bytes<0)return false;Node*n=root_.get();std::vector<Node*>path{n};for(const auto&s:v){auto&p=n->child[s];if(!p)p=std::make_unique<Node>();n=p.get();path.push_back(n);}if(n->file_bytes)return false;for(auto*x:path)if(x->bytes>std::numeric_limits<long long>::max()-bytes)return false;n->file_bytes=bytes;for(auto*x:path){++x->files;x->bytes+=bytes;}return true;}
bool PathDescendantTrie::erase_file(const std::vector<std::string>&v){if(!valid(v))return false;Node*n=root_.get();std::vector<Node*>path{n};std::vector<std::pair<Node*,std::string>>edges;for(const auto&s:v){auto it=n->child.find(s);if(it==n->child.end())return false;edges.push_back({n,s});n=it->second.get();path.push_back(n);}if(!n->file_bytes)return false;auto bytes=*n->file_bytes;n->file_bytes.reset();for(auto*x:path){--x->files;x->bytes-=bytes;}for(std::size_t i=edges.size();i>0;--i){auto&p=edges[i-1].first->child[edges[i-1].second];if(p->files==0)edges[i-1].first->child.erase(edges[i-1].second);else break;}return true;}
namespace{const PathDescendantTrie::Node*find_node(const PathDescendantTrie::Node*root,const std::vector<std::string>&v){auto*n=root;for(const auto&s:v){auto it=n->child.find(s);if(it==n->child.end())return nullptr;n=it->second.get();}return n;}}
std::size_t PathDescendantTrie::descendant_files(const std::vector<std::string>&v)const{if(!valid(v,true))return 0;auto*n=find_node(root_.get(),v);return n?n->files:0;}
long long PathDescendantTrie::descendant_bytes(const std::vector<std::string>&v)const{if(!valid(v,true))return 0;auto*n=find_node(root_.get(),v);return n?n->bytes:0;}
std::vector<std::string>PathDescendantTrie::child_names(const std::vector<std::string>&v)const{std::vector<std::string>out;if(!valid(v,true))return out;auto*n=find_node(root_.get(),v);if(n)for(const auto&e:n->child)out.push_back(e.first);return out;}
PathDescendantTrie::Audit PathDescendantTrie::audit_for_test()const{bool ok=true;std::size_t nodes=0,files=0;long long bytes=0;std::function<std::pair<std::size_t,long long>(const Node*)>walk=[&](const Node*n){++nodes;std::size_t f=n->file_bytes?1U:0U;long long b=n->file_bytes.value_or(0);if(n->file_bytes){++files;bytes+=*n->file_bytes;}for(const auto&e:n->child){auto x=walk(e.second.get());f+=x.first;b+=x.second;}if(f!=n->files||b!=n->bytes)ok=false;return std::pair<std::size_t,long long>{f,b};};walk(root_.get());return{ok,nodes,files,bytes};}}
'''
    # Nested Node is private, so avoid a namespace helper naming it by making a local lambda in each query.
    ref=ref.replace('namespace{const PathDescendantTrie::Node*find_node(const PathDescendantTrie::Node*root,const std::vector<std::string>&v){auto*n=root;for(const auto&s:v){auto it=n->child.find(s);if(it==n->child.end())return nullptr;n=it->second.get();}return n;}}\n','').replace('auto*n=find_node(root_.get(),v);', 'const Node*n=root_.get();for(const auto&s:v){auto it=n->child.find(s);if(it==n->child.end()){n=nullptr;break;}n=it->second.get();}')
    stub=_stub(cls,'''bool PathDescendantTrie::add_file(const std::vector<std::string>&,long long){return false;} bool PathDescendantTrie::erase_file(const std::vector<std::string>&){return false;} std::size_t PathDescendantTrie::descendant_files(const std::vector<std::string>&)const{return 0;} long long PathDescendantTrie::descendant_bytes(const std::vector<std::string>&)const{return 0;} std::vector<std::string> PathDescendantTrie::child_names(const std::vector<std::string>&)const{return{};}''').replace("return {false,0U,0U};","return {false,0U,0U,0};")
    return Case("trie-file-path-index","path-descendant-trie",cls,"Aggregated path trie","Segment paths maintain file counts and byte sums after every mutation.",header,ref,stub,
      'PathDescendantTrie x;check(x.add_file({"src","a.cpp"},10));check(x.add_file({"src","lib","b.cpp"},7));check(x.descendant_files({"src"})==2);check(x.descendant_bytes({"src"})==17);check((x.child_names({"src"})==std::vector<std::string>{"a.cpp","lib"}));',
      'PathDescendantTrie x;long long total=0;for(int i=0;i<60;++i){auto v=std::vector<std::string>{"d",std::to_string(i%5),"f"+std::to_string(i)};check(x.add_file(v,i));total+=i;check(x.descendant_bytes({"d"})==total);check(x.audit_for_test().valid);}for(int i=0;i<60;i+=2){check(x.erase_file({"d",std::to_string(i%5),"f"+std::to_string(i)}));total-=i;}check(x.descendant_bytes({"d"})==total);check(!x.add_file({".."},1));',
      ("file_bytes","descendant_bytes","numeric_limits<long long>","std::map<std::string,std::unique_ptr<Node>>child"))


def _case_plate() -> Case:
    cls="NormalizedPlateReservationTrie"
    header=_header(cls,'''  bool reserve(const std::string& plate);
  bool release(const std::string& plate);
  bool is_reserved(const std::string& plate) const;
  std::size_t count_prefix(const std::string& prefix) const;
  bool prefix_is_unique(const std::string& prefix) const;''',"std::size_t nodes; std::size_t terminals;","  struct Node;\n  std::unique_ptr<Node> root_;")
    ref=r'''#include "task.h"
#include <algorithm>
#include <cctype>
#include <functional>
namespace curriculum{struct NormalizedPlateReservationTrie::Node{std::array<std::unique_ptr<Node>,36>child;bool terminal=false;std::size_t below=0;};namespace{std::optional<std::string>norm(const std::string&s,bool prefix=false){std::string out;for(unsigned char c:s){if(c==' '||c=='-')continue;if(!std::isalnum(c))return{};out+=char(std::toupper(c));}if((!prefix&&out.size()<2)||out.size()>10)return{};return out;}std::size_t slot(char c){return c>='0'&&c<='9'?std::size_t(c-'0'):std::size_t(c-'A'+10);}}
NormalizedPlateReservationTrie::NormalizedPlateReservationTrie():root_(std::make_unique<Node>()){}NormalizedPlateReservationTrie::~NormalizedPlateReservationTrie()=default;
bool NormalizedPlateReservationTrie::reserve(const std::string&raw){auto s=norm(raw);if(!s)return false;Node*n=root_.get();std::vector<Node*>path{n};for(char c:*s){auto&p=n->child[slot(c)];if(!p)p=std::make_unique<Node>();n=p.get();path.push_back(n);}if(n->terminal)return false;n->terminal=true;for(auto*x:path)++x->below;return true;}
bool NormalizedPlateReservationTrie::is_reserved(const std::string&raw)const{auto s=norm(raw);if(!s)return false;const Node*n=root_.get();for(char c:*s){n=n->child[slot(c)].get();if(!n)return false;}return n->terminal;}
bool NormalizedPlateReservationTrie::release(const std::string&raw){auto s=norm(raw);if(!s||!is_reserved(*s))return false;Node*n=root_.get();std::vector<Node*>path{n};std::vector<std::pair<Node*,std::size_t>>edges;for(char c:*s){auto i=slot(c);edges.push_back({n,i});n=n->child[i].get();path.push_back(n);}n->terminal=false;for(auto*x:path)--x->below;for(std::size_t i=edges.size();i>0;--i)if(edges[i-1].first->child[edges[i-1].second]->below==0)edges[i-1].first->child[edges[i-1].second].reset();else break;return true;}
std::size_t NormalizedPlateReservationTrie::count_prefix(const std::string&raw)const{auto s=norm(raw,true);if(!s)return 0;const Node*n=root_.get();for(char c:*s){n=n->child[slot(c)].get();if(!n)return 0;}return n->below;}
bool NormalizedPlateReservationTrie::prefix_is_unique(const std::string&s)const{return count_prefix(s)==1;}
NormalizedPlateReservationTrie::Audit NormalizedPlateReservationTrie::audit_for_test()const{bool ok=true;std::size_t nodes=0,terms=0;std::function<std::size_t(const Node*)>walk=[&](const Node*n){++nodes;std::size_t sum=n->terminal?1U:0U;if(n->terminal)++terms;for(const auto&c:n->child)if(c)sum+=walk(c.get());if(sum!=n->below)ok=false;return sum;};walk(root_.get());return{ok,nodes,terms};}}
'''
    stub=_stub(cls,'''bool NormalizedPlateReservationTrie::reserve(const std::string&){return false;} bool NormalizedPlateReservationTrie::release(const std::string&){return false;} bool NormalizedPlateReservationTrie::is_reserved(const std::string&)const{return false;} std::size_t NormalizedPlateReservationTrie::count_prefix(const std::string&)const{return 0;} bool NormalizedPlateReservationTrie::prefix_is_unique(const std::string&)const{return false;}''')
    return Case("trie-license-plate-index","normalized-plate-reservation-trie",cls,"Normalized fixed-branch plate trie","Shared normalization and 36-way counted reservations.",header,ref,stub,
      'NormalizedPlateReservationTrie x;check(x.reserve("ab-12"));check(x.is_reserved("AB 12"));check(x.reserve("AB13"));check(x.count_prefix("ab-1")==2);check(!x.prefix_is_unique("AB1"));check(x.release("a b 1 3"));check(x.prefix_is_unique("AB"));',
      'NormalizedPlateReservationTrie x;for(int i=0;i<70;++i){check(x.reserve("XY-"+std::to_string(100+i)));check(x.count_prefix("xy")==std::size_t(i+1));check(x.audit_for_test().valid);}for(int i=0;i<70;i+=2)check(x.release("XY"+std::to_string(100+i)));check(x.count_prefix("XY")==35);check(!x.reserve("!bad"));',
      ("std::array<std::unique_ptr<Node>,36>","std::toupper","slot(char","below"))


def _case_rack() -> Case:
    cls="RackPrefixWordTrie"
    header=_header(cls,'''  bool add(const std::string& word);
  bool erase(const std::string& word);
  bool contains(const std::string& word) const;
  std::vector<std::string> playable(const std::string& required_prefix, const std::string& rack, std::size_t limit) const;''',"std::size_t nodes; std::size_t terminals;","  struct Node;\n  std::unique_ptr<Node> root_;")
    ref=r'''#include "task.h"
#include <algorithm>
#include <functional>
namespace curriculum{struct RackPrefixWordTrie::Node{std::array<std::unique_ptr<Node>,26>child;bool terminal=false;};namespace{bool valid(const std::string&s,bool empty=false){return(empty||!s.empty())&&std::all_of(s.begin(),s.end(),[](char c){return c>='a'&&c<='z';});}}
RackPrefixWordTrie::RackPrefixWordTrie():root_(std::make_unique<Node>()){}RackPrefixWordTrie::~RackPrefixWordTrie()=default;
bool RackPrefixWordTrie::add(const std::string&s){if(!valid(s))return false;Node*n=root_.get();for(char c:s){auto&p=n->child[std::size_t(c-'a')];if(!p)p=std::make_unique<Node>();n=p.get();}if(n->terminal)return false;n->terminal=true;return true;}
bool RackPrefixWordTrie::contains(const std::string&s)const{if(!valid(s))return false;const Node*n=root_.get();for(char c:s){n=n->child[std::size_t(c-'a')].get();if(!n)return false;}return n->terminal;}
bool RackPrefixWordTrie::erase(const std::string&s){if(!contains(s))return false;Node*n=root_.get();std::vector<std::pair<Node*,std::size_t>>path;for(char c:s){auto i=std::size_t(c-'a');path.push_back({n,i});n=n->child[i].get();}n->terminal=false;for(std::size_t i=path.size();i>0;--i){auto&p=path[i-1].first->child[path[i-1].second];bool any=std::any_of(p->child.begin(),p->child.end(),[](const auto&x){return bool(x);});if(!p->terminal&&!any)p.reset();else break;}return true;}
std::vector<std::string>RackPrefixWordTrie::playable(const std::string&p,const std::string&r,std::size_t limit)const{std::vector<std::string>out;if(!valid(p,true)||!valid(r,true)||!limit)return out;const Node*n=root_.get();for(char c:p){n=n->child[std::size_t(c-'a')].get();if(!n)return{};}std::array<int,26>left{};for(char c:r)++left[std::size_t(c-'a')];std::function<void(const Node*,std::string)>walk=[&](const Node*x,std::string word){if(out.size()>=limit)return;if(x->terminal)out.push_back(word);for(std::size_t i=0;i<26;++i)if(x->child[i]&&left[i]){--left[i];walk(x->child[i].get(),word+char('a'+i));++left[i];}};walk(n,p);return out;}
RackPrefixWordTrie::Audit RackPrefixWordTrie::audit_for_test()const{std::size_t nodes=0,terms=0;std::function<void(const Node*)>walk=[&](const Node*n){++nodes;if(n->terminal)++terms;for(const auto&c:n->child)if(c)walk(c.get());};walk(root_.get());return{true,nodes,terms};}}
'''
    stub=_stub(cls,'''bool RackPrefixWordTrie::add(const std::string&){return false;} bool RackPrefixWordTrie::erase(const std::string&){return false;} bool RackPrefixWordTrie::contains(const std::string&)const{return false;} std::vector<std::string> RackPrefixWordTrie::playable(const std::string&,const std::string&,std::size_t)const{return{};}''')
    return Case("trie-word-game-dictionary","rack-prefix-word-trie",cls,"Rack-constrained word traversal","A 26-way trie consumes rack multiplicities only after the required prefix.",header,ref,stub,
      'RackPrefixWordTrie x;check(x.add("star"));check(x.add("start"));check(x.add("stay"));check((x.playable("st","ary",9)==std::vector<std::string>{"star","stay"}));check(x.erase("stay"));',
      'RackPrefixWordTrie x;for(const auto&s:std::vector<std::string>{"a","ab","aba","abb","abc","abcd"})check(x.add(s));check((x.playable("a","bcd",20)==std::vector<std::string>{"a","ab","abc","abcd"}));check(x.playable("a","bb",20)==std::vector<std::string>({"a","ab","abb"}));check(x.audit_for_test().valid);check(!x.add("Bad"));',
      ("std::array<int,26>left","--left[i]","++left[i]","playable"))


def _case_predictive() -> Case:
    cls="CachedTopKTextTrie"
    header=_header(cls,'''  struct Completion { std::string word; int frequency; };
  bool record(const std::string& word, int delta);
  bool erase(const std::string& word);
  std::optional<int> frequency(const std::string& word) const;
  std::vector<Completion> top(const std::string& prefix, std::size_t limit) const;''',"std::size_t nodes; std::size_t terminals;","  struct Node;\n  std::unique_ptr<Node> root_;")
    ref=r'''#include "task.h"
#include <algorithm>
#include <functional>
namespace curriculum{struct CachedTopKTextTrie::Node{std::map<char,std::unique_ptr<Node>>child;std::optional<int>frequency;std::vector<Completion>cache;};namespace{bool valid(const std::string&s){return !s.empty()&&std::all_of(s.begin(),s.end(),[](char c){return c>='a'&&c<='z';});}bool better(const CachedTopKTextTrie::Completion&a,const CachedTopKTextTrie::Completion&b){return a.frequency!=b.frequency?a.frequency>b.frequency:a.word<b.word;}}
CachedTopKTextTrie::CachedTopKTextTrie():root_(std::make_unique<Node>()){}CachedTopKTextTrie::~CachedTopKTextTrie()=default;
bool CachedTopKTextTrie::record(const std::string&s,int delta){if(!valid(s)||delta<=0)return false;Node*n=root_.get();for(char c:s){auto&p=n->child[c];if(!p)p=std::make_unique<Node>();n=p.get();}n->frequency=n->frequency.value_or(0)+delta;std::function<std::vector<Completion>(Node*,std::string)>rebuild=[&](Node*x,std::string prefix){std::vector<Completion>all;if(x->frequency)all.push_back({prefix,*x->frequency});for(auto&e:x->child){auto sub=rebuild(e.second.get(),prefix+e.first);all.insert(all.end(),sub.begin(),sub.end());}std::sort(all.begin(),all.end(),better);x->cache.assign(all.begin(),all.begin()+std::ptrdiff_t(std::min<std::size_t>(8,all.size())));return all;};rebuild(root_.get(),"");return true;}
std::optional<int>CachedTopKTextTrie::frequency(const std::string&s)const{if(!valid(s))return{};const Node*n=root_.get();for(char c:s){auto it=n->child.find(c);if(it==n->child.end())return{};n=it->second.get();}return n->frequency;}
bool CachedTopKTextTrie::erase(const std::string&s){if(!frequency(s))return false;Node*n=root_.get();std::vector<std::pair<Node*,char>>path;for(char c:s){path.push_back({n,c});n=n->child[c].get();}n->frequency.reset();for(std::size_t i=path.size();i>0;--i){auto&p=path[i-1].first->child[path[i-1].second];if(!p->frequency&&p->child.empty())path[i-1].first->child.erase(path[i-1].second);else break;}std::function<std::vector<Completion>(Node*,std::string)>rebuild=[&](Node*x,std::string prefix){std::vector<Completion>all;if(x->frequency)all.push_back({prefix,*x->frequency});for(auto&e:x->child){auto sub=rebuild(e.second.get(),prefix+e.first);all.insert(all.end(),sub.begin(),sub.end());}std::sort(all.begin(),all.end(),better);x->cache.assign(all.begin(),all.begin()+std::ptrdiff_t(std::min<std::size_t>(8,all.size())));return all;};rebuild(root_.get(),"");return true;}
std::vector<CachedTopKTextTrie::Completion>CachedTopKTextTrie::top(const std::string&p,std::size_t limit)const{std::vector<Completion>out;if((!p.empty()&&!valid(p))||!limit)return out;const Node*n=root_.get();for(char c:p){auto it=n->child.find(c);if(it==n->child.end())return{};n=it->second.get();}limit=std::min<std::size_t>(limit,8);out.assign(n->cache.begin(),n->cache.begin()+std::ptrdiff_t(std::min(limit,n->cache.size())));return out;}
CachedTopKTextTrie::Audit CachedTopKTextTrie::audit_for_test()const{bool ok=true;std::size_t nodes=0,terms=0;std::function<std::vector<Completion>(const Node*,std::string)>walk=[&](const Node*n,std::string prefix){++nodes;std::vector<Completion>all;if(n->frequency){++terms;all.push_back({prefix,*n->frequency});}for(const auto&e:n->child){auto sub=walk(e.second.get(),prefix+e.first);all.insert(all.end(),sub.begin(),sub.end());}std::sort(all.begin(),all.end(),better);auto count=std::min<std::size_t>(8,all.size());if(n->cache.size()!=count)ok=false;else for(std::size_t i=0;i<count;++i)if(n->cache[i].word!=all[i].word||n->cache[i].frequency!=all[i].frequency)ok=false;return all;};walk(root_.get(),"");return{ok,nodes,terms};}}
'''
    stub=_stub(cls,'''bool CachedTopKTextTrie::record(const std::string&,int){return false;} bool CachedTopKTextTrie::erase(const std::string&){return false;} std::optional<int> CachedTopKTextTrie::frequency(const std::string&)const{return{};} std::vector<CachedTopKTextTrie::Completion> CachedTopKTextTrie::top(const std::string&,std::size_t)const{return{};}''').replace('struct CachedTopKTextTrie::Node{};', 'struct CachedTopKTextTrie::Node{};')
    return Case("trie-predictive-text","cached-topk-text-trie",cls,"Mutation-maintained top-k cache","Each prefix node caches at most eight ranked descendant terminals.",header,ref,stub,
      'CachedTopKTextTrie x;check(x.record("cat",2));check(x.record("car",4));check(x.record("cat",3));auto v=x.top("ca",5);check(v.size()==2&&v[0].word=="cat"&&v[0].frequency==5);check(x.erase("cat"));check(x.top("ca",2)[0].word=="car");',
      'CachedTopKTextTrie x;std::vector<std::pair<std::string,int>>m;for(int i=0;i<50;++i){std::string s="w"+std::string(1,char(\'a\'+i%20))+std::string(1,char(\'a\'+i/20));check(x.record(s,1+i));m.push_back({s,1+i});check(x.audit_for_test().valid);}auto got=x.top("w",100);check(got.size()==8);for(std::size_t i=1;i<got.size();++i)check(got[i-1].frequency>=got[i].frequency);check(!x.record("Bad",1));',
      ("std::vector<Completion>cache","rebuild=","std::min<std::size_t>(limit,8)","better("))


def _case_tags() -> Case:
    cls="TagPostingTrie"
    header=_header(cls,'''  bool add(const std::string& tag, int snippet_id);
  bool remove(const std::string& tag, int snippet_id);
  std::vector<int> ids_with_prefix(const std::string& prefix) const;
  std::size_t exact_posting_count(const std::string& tag) const;''',"std::size_t nodes; std::size_t postings;","  struct Node;\n  std::unique_ptr<Node> root_;")
    ref=r'''#include "task.h"
#include <algorithm>
#include <functional>
namespace curriculum{struct TagPostingTrie::Node{std::map<char,std::unique_ptr<Node>>child;std::set<int>exact;std::map<int,std::size_t>aggregate;};namespace{bool valid(const std::string&s,bool empty=false){return(empty||!s.empty())&&std::all_of(s.begin(),s.end(),[](char c){return(c>='a'&&c<='z')||c=='-';});}}
TagPostingTrie::TagPostingTrie():root_(std::make_unique<Node>()){}TagPostingTrie::~TagPostingTrie()=default;
bool TagPostingTrie::add(const std::string&s,int id){if(!valid(s)||id<=0)return false;Node*n=root_.get();std::vector<Node*>path{n};for(char c:s){auto&p=n->child[c];if(!p)p=std::make_unique<Node>();n=p.get();path.push_back(n);}if(n->exact.count(id))return false;n->exact.insert(id);for(auto*x:path)++x->aggregate[id];return true;}
bool TagPostingTrie::remove(const std::string&s,int id){if(!valid(s)||id<=0)return false;Node*n=root_.get();std::vector<Node*>path{n};std::vector<std::pair<Node*,char>>edges;for(char c:s){auto it=n->child.find(c);if(it==n->child.end())return false;edges.push_back({n,c});n=it->second.get();path.push_back(n);}if(!n->exact.erase(id))return false;for(auto*x:path){auto it=x->aggregate.find(id);if(--it->second==0)x->aggregate.erase(it);}for(std::size_t i=edges.size();i>0;--i){auto&p=edges[i-1].first->child[edges[i-1].second];if(p->aggregate.empty())edges[i-1].first->child.erase(edges[i-1].second);else break;}return true;}
std::vector<int>TagPostingTrie::ids_with_prefix(const std::string&s)const{std::vector<int>out;if(!valid(s,true))return out;const Node*n=root_.get();for(char c:s){auto it=n->child.find(c);if(it==n->child.end())return{};n=it->second.get();}for(const auto&e:n->aggregate)out.push_back(e.first);return out;}
std::size_t TagPostingTrie::exact_posting_count(const std::string&s)const{if(!valid(s))return 0;const Node*n=root_.get();for(char c:s){auto it=n->child.find(c);if(it==n->child.end())return 0;n=it->second.get();}return n->exact.size();}
TagPostingTrie::Audit TagPostingTrie::audit_for_test()const{bool ok=true;std::size_t nodes=0,postings=0;std::function<std::map<int,std::size_t>(const Node*)>walk=[&](const Node*n){++nodes;postings+=n->exact.size();std::map<int,std::size_t>sum;for(int id:n->exact)++sum[id];for(const auto&e:n->child){auto sub=walk(e.second.get());for(const auto&x:sub)sum[x.first]+=x.second;}if(sum!=n->aggregate)ok=false;return sum;};walk(root_.get());return{ok,nodes,postings};}}
'''
    stub=_stub(cls,'''bool TagPostingTrie::add(const std::string&,int){return false;} bool TagPostingTrie::remove(const std::string&,int){return false;} std::vector<int> TagPostingTrie::ids_with_prefix(const std::string&)const{return{};} std::size_t TagPostingTrie::exact_posting_count(const std::string&)const{return 0;}''')
    return Case("trie-snippet-tags","tag-posting-trie",cls,"Trie posting aggregation","Prefix nodes maintain per-ID posting multiplicities for sorted union queries.",header,ref,stub,
      'TagPostingTrie x;check(x.add("cpp",2));check(x.add("cpp-tools",1));check(x.add("cpp",1));check((x.ids_with_prefix("cpp")==std::vector<int>{1,2}));check(x.exact_posting_count("cpp")==2);check(x.remove("cpp",1));check((x.ids_with_prefix("cpp")==std::vector<int>{1,2}));',
      'TagPostingTrie x;for(int i=1;i<=50;++i){check(x.add("tag-"+std::string(1,char(\'a\'+i%20)),i));check(x.add("tag-all",i));check(x.audit_for_test().valid);}check(x.ids_with_prefix("tag").size()==50);for(int i=1;i<=50;i+=2)check(x.remove("tag-all",i));check(x.exact_posting_count("tag-all")==25);check(!x.add("BAD",1));',
      ("std::map<int,std::size_t>aggregate","exact","ids_with_prefix","sum!=n->aggregate"))


def _case_log() -> Case:
    cls="HierarchicalLogPolicyTrie"
    header=_header(cls,'''  bool set(const std::string& category, LogPolicy policy);
  bool clear(const std::string& category);
  LogPolicy effective(const std::string& category) const;
  std::vector<std::string> explicit_under(const std::string& prefix) const;''',"std::size_t nodes; std::size_t explicit_policies;","  struct Node;\n  std::unique_ptr<Node> root_;").replace("namespace curriculum {\nclass", "namespace curriculum {\nenum class LogPolicy { inherit, allow, deny };\nclass")
    ref=r'''#include "task.h"
#include <algorithm>
#include <functional>
#include <sstream>
namespace curriculum{struct HierarchicalLogPolicyTrie::Node{std::map<std::string,std::unique_ptr<Node>>child;LogPolicy policy=LogPolicy::inherit;};namespace{std::optional<std::vector<std::string>>parts(const std::string&s,bool empty=false){if(s.empty())return empty?std::optional<std::vector<std::string>>({}):std::nullopt;std::vector<std::string>v;std::string p;std::istringstream in(s);while(std::getline(in,p,'.')){if(p.empty()||!std::all_of(p.begin(),p.end(),[](char c){return c>='a'&&c<='z';}))return{};v.push_back(p);}return v;}}
HierarchicalLogPolicyTrie::HierarchicalLogPolicyTrie():root_(std::make_unique<Node>()){}HierarchicalLogPolicyTrie::~HierarchicalLogPolicyTrie()=default;
bool HierarchicalLogPolicyTrie::set(const std::string&s,LogPolicy p){auto v=parts(s);if(!v||p==LogPolicy::inherit)return false;Node*n=root_.get();for(const auto&x:*v){auto&c=n->child[x];if(!c)c=std::make_unique<Node>();n=c.get();}if(n->policy!=LogPolicy::inherit)return false;n->policy=p;return true;}
bool HierarchicalLogPolicyTrie::clear(const std::string&s){auto v=parts(s);if(!v)return false;Node*n=root_.get();std::vector<std::pair<Node*,std::string>>path;for(const auto&x:*v){auto it=n->child.find(x);if(it==n->child.end())return false;path.push_back({n,x});n=it->second.get();}if(n->policy==LogPolicy::inherit)return false;n->policy=LogPolicy::inherit;for(std::size_t i=path.size();i>0;--i){auto&p=path[i-1].first->child[path[i-1].second];if(p->policy==LogPolicy::inherit&&p->child.empty())path[i-1].first->child.erase(path[i-1].second);else break;}return true;}
LogPolicy HierarchicalLogPolicyTrie::effective(const std::string&s)const{auto v=parts(s);if(!v)return LogPolicy::deny;const Node*n=root_.get();LogPolicy out=LogPolicy::deny;for(const auto&x:*v){auto it=n->child.find(x);if(it==n->child.end())break;n=it->second.get();if(n->policy!=LogPolicy::inherit)out=n->policy;}return out;}
std::vector<std::string>HierarchicalLogPolicyTrie::explicit_under(const std::string&s)const{auto v=parts(s,true);std::vector<std::string>out;if(!v)return out;const Node*n=root_.get();for(const auto&x:*v){auto it=n->child.find(x);if(it==n->child.end())return{};n=it->second.get();}std::function<void(const Node*,std::string)>walk=[&](const Node*x,std::string name){if(x->policy!=LogPolicy::inherit&&!name.empty())out.push_back(name);for(const auto&e:x->child)walk(e.second.get(),name.empty()?e.first:name+"."+e.first);};walk(n,s);return out;}
HierarchicalLogPolicyTrie::Audit HierarchicalLogPolicyTrie::audit_for_test()const{std::size_t nodes=0,count=0;std::function<void(const Node*)>walk=[&](const Node*n){++nodes;if(n->policy!=LogPolicy::inherit)++count;for(const auto&e:n->child)walk(e.second.get());};walk(root_.get());return{true,nodes,count};}}
'''
    stub=_stub(cls,'''bool HierarchicalLogPolicyTrie::set(const std::string&,LogPolicy){return false;} bool HierarchicalLogPolicyTrie::clear(const std::string&){return false;} LogPolicy HierarchicalLogPolicyTrie::effective(const std::string&)const{return LogPolicy::deny;} std::vector<std::string> HierarchicalLogPolicyTrie::explicit_under(const std::string&)const{return{};}''')
    return Case("trie-log-category-filter","hierarchical-log-policy-trie",cls,"Inherited category policies","Dotted segment traversal tracks the deepest explicit allow/deny ancestor.",header,ref,stub,
      'HierarchicalLogPolicyTrie x;using P=LogPolicy;check(x.set("app",P::allow));check(x.set("app.secret",P::deny));check(x.effective("app.http")==P::allow);check(x.effective("app.secret.token")==P::deny);check(x.clear("app.secret"));check(x.effective("app.secret")==P::allow);',
      'HierarchicalLogPolicyTrie x;using P=LogPolicy;for(int i=0;i<40;++i){std::string c="root.c"+std::string(1,char(\'a\'+i%20));if(i<20)check(x.set(c,i%2?P::allow:P::deny));check(x.audit_for_test().valid);}check(x.explicit_under("root").size()==20);check(x.effective("missing")==P::deny);check(!x.set("bad..name",P::allow));',
      ("LogPolicy::inherit","effective","std::istringstream","explicit_under"))


def _case_morse() -> Case:
    cls="PrefixFreeMorseTrie"
    header=_header(cls,'''  bool add(char symbol, const std::string& code);
  bool erase(char symbol);
  std::optional<char> decode(const std::string& code) const;
  bool can_add(const std::string& code) const;''',"std::size_t nodes; std::size_t symbols;","  struct Node;\n  std::unique_ptr<Node> root_;\n  std::unordered_map<char,std::string> codes_;")
    ref=r'''#include "task.h"
#include <algorithm>
#include <cctype>
#include <functional>
namespace curriculum{struct PrefixFreeMorseTrie::Node{std::array<std::unique_ptr<Node>,2>child;std::optional<char>symbol;};namespace{bool valid(const std::string&s){return !s.empty()&&s.size()<=8&&std::all_of(s.begin(),s.end(),[](char c){return c=='.'||c=='-';});}std::size_t slot(char c){return c=='-'?1U:0U;}}
PrefixFreeMorseTrie::PrefixFreeMorseTrie():root_(std::make_unique<Node>()){}PrefixFreeMorseTrie::~PrefixFreeMorseTrie()=default;
bool PrefixFreeMorseTrie::can_add(const std::string&s)const{if(!valid(s))return false;const Node*n=root_.get();for(char c:s){if(n->symbol)return false;n=n->child[slot(c)].get();if(!n)return true;}if(n->symbol)return false;return !n->child[0]&&!n->child[1];}
bool PrefixFreeMorseTrie::add(char symbol,const std::string&s){if(!std::isgraph(static_cast<unsigned char>(symbol))||codes_.count(symbol)||!can_add(s))return false;Node*n=root_.get();for(char c:s){auto&p=n->child[slot(c)];if(!p)p=std::make_unique<Node>();n=p.get();}n->symbol=symbol;codes_[symbol]=s;return true;}
bool PrefixFreeMorseTrie::erase(char symbol){auto it=codes_.find(symbol);if(it==codes_.end())return false;Node*n=root_.get();std::vector<std::pair<Node*,std::size_t>>path;for(char c:it->second){auto i=slot(c);path.push_back({n,i});n=n->child[i].get();}n->symbol.reset();codes_.erase(it);for(std::size_t i=path.size();i>0;--i){auto&p=path[i-1].first->child[path[i-1].second];if(!p->symbol&&!p->child[0]&&!p->child[1])p.reset();else break;}return true;}
std::optional<char>PrefixFreeMorseTrie::decode(const std::string&s)const{if(!valid(s))return{};const Node*n=root_.get();for(char c:s){n=n->child[slot(c)].get();if(!n)return{};}return n->symbol;}
PrefixFreeMorseTrie::Audit PrefixFreeMorseTrie::audit_for_test()const{bool ok=true;std::size_t nodes=0,symbols=0;std::function<void(const Node*)>walk=[&](const Node*n){++nodes;if(n->symbol){++symbols;if(n->child[0]||n->child[1])ok=false;}for(const auto&c:n->child)if(c)walk(c.get());};walk(root_.get());return{ok&&symbols==codes_.size(),nodes,symbols};}}
'''
    stub=_stub(cls,'''bool PrefixFreeMorseTrie::add(char,const std::string&){return false;} bool PrefixFreeMorseTrie::erase(char){return false;} std::optional<char> PrefixFreeMorseTrie::decode(const std::string&)const{return{};} bool PrefixFreeMorseTrie::can_add(const std::string&)const{return false;}''')
    return Case("trie-morse-codebook","prefix-free-morse-trie",cls,"Prefix-free dot/dash codebook","Binary traversal rejects codes that are ancestors or descendants of terminals.",header,ref,stub,
      'PrefixFreeMorseTrie x;check(x.add(\'A\',".-"));check(!x.add(\'B\',"."));check(!x.add(\'C\',".-."));check(x.add(\'D\',"--"));check(x.decode(".-")==std::optional<char>(\'A\'));check(x.erase(\'A\'));check(x.can_add("."));',
      'PrefixFreeMorseTrie x;for(int i=0;i<16;++i){std::string code;for(int b=3;b>=0;--b)code+=((i>>b)&1)?\'-\':\'.\';check(x.add(char(\'A\'+i),code));check(x.audit_for_test().valid);}check(!x.can_add("..."));for(char c=\'A\';c<\'I\';++c)check(x.erase(c));check(x.audit_for_test().symbols==8);check(!x.add(\'Z\',"x"));',
      ("std::array<std::unique_ptr<Node>,2>","can_add","if(n->symbol)","codes_"))


def _case_token() -> Case:
    cls="ShortestTokenPrefixTrie"
    header=_header(cls,'''  bool issue(const std::string& token);
  bool revoke(const std::string& token);
  PrefixResolution resolve(const std::string& prefix) const;
  std::optional<std::string> shortest_unique(const std::string& token) const;''',"std::size_t nodes; std::size_t terminals;","  struct Node;\n  std::unique_ptr<Node> root_;").replace("namespace curriculum {\nclass", "namespace curriculum {\nenum class PrefixState { absent, unique, ambiguous };\nstruct PrefixResolution { PrefixState state; std::string token; };\nclass")
    ref=r'''#include "task.h"
#include <algorithm>
#include <cctype>
#include <functional>
namespace curriculum{struct ShortestTokenPrefixTrie::Node{std::map<char,std::unique_ptr<Node>>child;std::optional<std::string>terminal;std::size_t below=0;};namespace{bool valid(const std::string&s,bool prefix=false){return(prefix||s.size()>=4)&&s.size()<=32&&std::all_of(s.begin(),s.end(),[](unsigned char c){return std::isalnum(c);});}}
ShortestTokenPrefixTrie::ShortestTokenPrefixTrie():root_(std::make_unique<Node>()){}ShortestTokenPrefixTrie::~ShortestTokenPrefixTrie()=default;
bool ShortestTokenPrefixTrie::issue(const std::string&s){if(!valid(s))return false;Node*n=root_.get();std::vector<Node*>path{n};for(char c:s){auto&p=n->child[c];if(!p)p=std::make_unique<Node>();n=p.get();path.push_back(n);}if(n->terminal)return false;n->terminal=s;for(auto*x:path)++x->below;return true;}
bool ShortestTokenPrefixTrie::revoke(const std::string&s){if(!valid(s))return false;Node*n=root_.get();std::vector<Node*>path{n};std::vector<std::pair<Node*,char>>edges;for(char c:s){auto it=n->child.find(c);if(it==n->child.end())return false;edges.push_back({n,c});n=it->second.get();path.push_back(n);}if(!n->terminal)return false;n->terminal.reset();for(auto*x:path)--x->below;for(std::size_t i=edges.size();i>0;--i){auto&p=edges[i-1].first->child[edges[i-1].second];if(p->below==0)edges[i-1].first->child.erase(edges[i-1].second);else break;}return true;}
PrefixResolution ShortestTokenPrefixTrie::resolve(const std::string&p)const{if(!valid(p,true))return{PrefixState::absent,""};const Node*n=root_.get();for(char c:p){auto it=n->child.find(c);if(it==n->child.end())return{PrefixState::absent,""};n=it->second.get();}if(n->below==0)return{PrefixState::absent,""};if(n->below>1)return{PrefixState::ambiguous,""};while(!n->terminal){if(n->child.size()!=1)return{PrefixState::absent,""};n=n->child.begin()->second.get();}return{PrefixState::unique,*n->terminal};}
std::optional<std::string>ShortestTokenPrefixTrie::shortest_unique(const std::string&s)const{if(!valid(s))return{};const Node*n=root_.get();std::string p;for(char c:s){auto it=n->child.find(c);if(it==n->child.end())return{};n=it->second.get();p+=c;if(n->below==1)return p;}return{};}
ShortestTokenPrefixTrie::Audit ShortestTokenPrefixTrie::audit_for_test()const{bool ok=true;std::size_t nodes=0,terms=0;std::function<std::size_t(const Node*)>walk=[&](const Node*n){++nodes;std::size_t sum=n->terminal?1U:0U;if(n->terminal)++terms;for(const auto&e:n->child)sum+=walk(e.second.get());if(sum!=n->below)ok=false;return sum;};walk(root_.get());return{ok,nodes,terms};}}
'''
    stub=_stub(cls,'''bool ShortestTokenPrefixTrie::issue(const std::string&){return false;} bool ShortestTokenPrefixTrie::revoke(const std::string&){return false;} PrefixResolution ShortestTokenPrefixTrie::resolve(const std::string&)const{return{PrefixState::absent,""};} std::optional<std::string> ShortestTokenPrefixTrie::shortest_unique(const std::string&)const{return{};}''')
    return Case("trie-access-token-prefixes","shortest-token-prefix-trie",cls,"Shortest unique access-token prefixes","Subtree terminal counts distinguish absent, unique, and ambiguous prefixes.",header,ref,stub,
      'ShortestTokenPrefixTrie x;using S=PrefixState;check(x.issue("abc1"));check(x.issue("abc2"));check(x.resolve("abc").state==S::ambiguous);check(x.resolve("abc1").token=="abc1");check(x.shortest_unique("abc1")==std::optional<std::string>("abc1"));check(x.revoke("abc2"));check(x.resolve("a").state==S::unique);',
      'ShortestTokenPrefixTrie x;for(int i=0;i<80;++i){std::string s="tok"+std::to_string(100+i);check(x.issue(s));check(x.audit_for_test().valid);}using S=PrefixState;check(x.resolve("tok").state==S::ambiguous);for(int i=1;i<80;++i)check(x.revoke("tok"+std::to_string(100+i)));check(x.resolve("t").state==S::unique);check(x.shortest_unique("tok100")==std::optional<std::string>("t"));check(!x.issue("x"));',
      ("PrefixState::ambiguous","below","shortest_unique","terminal"))


def _case_sku() -> Case:
    cls="NumericSkuAllocationTrie"
    header=_header(cls,'''  bool reserve(const std::string& prefix, unsigned suffix, unsigned width);
  bool release(const std::string& prefix, unsigned suffix, unsigned width);
  std::optional<unsigned> allocate_first(const std::string& prefix, unsigned width);
  bool is_reserved(const std::string& prefix, unsigned suffix, unsigned width) const;''',"std::size_t nodes; std::size_t terminals;","  struct Node;\n  std::unique_ptr<Node> root_;")
    ref=r'''#include "task.h"
#include <algorithm>
#include <functional>
#include <iomanip>
#include <sstream>
namespace curriculum{struct NumericSkuAllocationTrie::Node{std::map<char,std::unique_ptr<Node>>child;bool terminal=false;std::size_t below=0;};namespace{bool prefix_ok(const std::string&s){return !s.empty()&&std::all_of(s.begin(),s.end(),[](char c){return c>='A'&&c<='Z';});}unsigned capacity(unsigned w){unsigned n=1;while(w--)n*=10;return n;}std::optional<std::string>key(const std::string&p,unsigned s,unsigned w){if(!prefix_ok(p)||w<1||w>4||s>=capacity(w))return{};std::ostringstream out;out<<p<<std::setw(int(w))<<std::setfill('0')<<s;return out.str();}}
NumericSkuAllocationTrie::NumericSkuAllocationTrie():root_(std::make_unique<Node>()){}NumericSkuAllocationTrie::~NumericSkuAllocationTrie()=default;
bool NumericSkuAllocationTrie::reserve(const std::string&p,unsigned s,unsigned w){auto k=key(p,s,w);if(!k)return false;Node*n=root_.get();std::vector<Node*>path{n};for(char c:*k){auto&x=n->child[c];if(!x)x=std::make_unique<Node>();n=x.get();path.push_back(n);}if(n->terminal)return false;n->terminal=true;for(auto*x:path)++x->below;return true;}
bool NumericSkuAllocationTrie::is_reserved(const std::string&p,unsigned s,unsigned w)const{auto k=key(p,s,w);if(!k)return false;const Node*n=root_.get();for(char c:*k){auto it=n->child.find(c);if(it==n->child.end())return false;n=it->second.get();}return n->terminal;}
bool NumericSkuAllocationTrie::release(const std::string&p,unsigned s,unsigned w){auto k=key(p,s,w);if(!k||!is_reserved(p,s,w))return false;Node*n=root_.get();std::vector<Node*>path{n};std::vector<std::pair<Node*,char>>edges;for(char c:*k){edges.push_back({n,c});n=n->child[c].get();path.push_back(n);}n->terminal=false;for(auto*x:path)--x->below;for(std::size_t i=edges.size();i>0;--i){auto&x=edges[i-1].first->child[edges[i-1].second];if(x->below==0)edges[i-1].first->child.erase(edges[i-1].second);else break;}return true;}
std::optional<unsigned>NumericSkuAllocationTrie::allocate_first(const std::string&p,unsigned w){if(!prefix_ok(p)||w<1||w>4)return{};Node*n=root_.get();for(char c:p){auto&x=n->child[c];if(!x)x=std::make_unique<Node>();n=x.get();}std::function<std::optional<unsigned>(Node*,unsigned,unsigned)>gap=[&](Node*x,unsigned depth,unsigned value)->std::optional<unsigned>{if(depth==w)return x&&x->terminal?std::nullopt:std::optional<unsigned>(value);unsigned remaining=capacity(w-depth-1);for(unsigned d=0;d<10;++d){auto it=x?x->child.find(char('0'+d)):std::map<char,std::unique_ptr<Node>>::iterator{};Node*child=(x&&it!=x->child.end())?it->second.get():nullptr;if(!child||child->below<remaining){auto found=gap(child,depth+1,value*10+d);if(found)return found;}}return{};};auto found=gap(n,0,0);if(found&&!reserve(p,*found,w))return{};return found;}
NumericSkuAllocationTrie::Audit NumericSkuAllocationTrie::audit_for_test()const{bool ok=true;std::size_t nodes=0,terms=0;std::function<std::size_t(const Node*)>walk=[&](const Node*n){++nodes;std::size_t sum=n->terminal?1U:0U;if(n->terminal)++terms;for(const auto&e:n->child)sum+=walk(e.second.get());if(sum!=n->below)ok=false;return sum;};walk(root_.get());return{ok,nodes,terms};}}
'''
    # Avoid constructing a singular map iterator in the gap routine.
    ref=ref.replace("auto it=x?x->child.find(char('0'+d)):std::map<char,std::unique_ptr<Node>>::iterator{};Node*child=(x&&it!=x->child.end())?it->second.get():nullptr;", "Node*child=nullptr;if(x){auto it=x->child.find(char('0'+d));if(it!=x->child.end())child=it->second.get();}")
    stub=_stub(cls,'''bool NumericSkuAllocationTrie::reserve(const std::string&,unsigned,unsigned){return false;} bool NumericSkuAllocationTrie::release(const std::string&,unsigned,unsigned){return false;} std::optional<unsigned> NumericSkuAllocationTrie::allocate_first(const std::string&,unsigned){return{};} bool NumericSkuAllocationTrie::is_reserved(const std::string&,unsigned,unsigned)const{return false;}''')
    return Case("trie-sku-allocator","numeric-sku-allocation-trie",cls,"Numeric suffix gap allocation","Digit branches and subtree occupancy find and reserve the smallest free suffix.",header,ref,stub,
      'NumericSkuAllocationTrie x;check(x.reserve("AB",0,2));check(x.reserve("AB",1,2));check(x.allocate_first("AB",2)==std::optional<unsigned>(2));check(x.is_reserved("AB",2,2));check(x.release("AB",1,2));check(x.allocate_first("AB",2)==std::optional<unsigned>(1));',
      'NumericSkuAllocationTrie x;for(unsigned i=0;i<100;++i)check(x.reserve("SKU",i,2));check(!x.allocate_first("SKU",2));for(unsigned i=0;i<100;i+=3)check(x.release("SKU",i,2));check(x.allocate_first("SKU",2)==std::optional<unsigned>(0));check(x.audit_for_test().valid);check(!x.reserve("bad",1,2));',
      ("capacity(","child->below<remaining","gap(","std::setw"))


def _case_wildcard() -> Case:
    cls="SingleWildcardWordTrie"
    header=_header(cls,'''  bool add(const std::string& word);
  bool erase(const std::string& word);
  bool contains(const std::string& word) const;
  std::vector<std::string> match(const std::string& pattern, std::size_t limit) const;''',"std::size_t nodes; std::size_t terminals;","  struct Node;\n  std::unique_ptr<Node> root_;")
    ref=r'''#include "task.h"
#include <algorithm>
#include <functional>
namespace curriculum{struct SingleWildcardWordTrie::Node{std::map<char,std::unique_ptr<Node>>child;bool terminal=false;};namespace{bool word_ok(const std::string&s){return !s.empty()&&std::all_of(s.begin(),s.end(),[](char c){return c>='a'&&c<='z';});}bool pattern_ok(const std::string&s){return !s.empty()&&std::all_of(s.begin(),s.end(),[](char c){return(c>='a'&&c<='z')||c=='?';});}}
SingleWildcardWordTrie::SingleWildcardWordTrie():root_(std::make_unique<Node>()){}SingleWildcardWordTrie::~SingleWildcardWordTrie()=default;
bool SingleWildcardWordTrie::add(const std::string&s){if(!word_ok(s))return false;Node*n=root_.get();for(char c:s){auto&p=n->child[c];if(!p)p=std::make_unique<Node>();n=p.get();}if(n->terminal)return false;n->terminal=true;return true;}
bool SingleWildcardWordTrie::contains(const std::string&s)const{if(!word_ok(s))return false;const Node*n=root_.get();for(char c:s){auto it=n->child.find(c);if(it==n->child.end())return false;n=it->second.get();}return n->terminal;}
bool SingleWildcardWordTrie::erase(const std::string&s){if(!contains(s))return false;Node*n=root_.get();std::vector<std::pair<Node*,char>>path;for(char c:s){path.push_back({n,c});n=n->child[c].get();}n->terminal=false;for(std::size_t i=path.size();i>0;--i){auto&p=path[i-1].first->child[path[i-1].second];if(!p->terminal&&p->child.empty())path[i-1].first->child.erase(path[i-1].second);else break;}return true;}
std::vector<std::string>SingleWildcardWordTrie::match(const std::string&p,std::size_t limit)const{std::vector<std::string>out;if(!pattern_ok(p)||!limit)return out;std::function<void(const Node*,std::size_t,std::string)>walk=[&](const Node*n,std::size_t i,std::string word){if(out.size()>=limit)return;if(i==p.size()){if(n->terminal)out.push_back(word);return;}if(p[i]=='?'){for(const auto&e:n->child)walk(e.second.get(),i+1,word+e.first);}else{auto it=n->child.find(p[i]);if(it!=n->child.end())walk(it->second.get(),i+1,word+p[i]);}};walk(root_.get(),0,"");return out;}
SingleWildcardWordTrie::Audit SingleWildcardWordTrie::audit_for_test()const{std::size_t nodes=0,terms=0;std::function<void(const Node*)>walk=[&](const Node*n){++nodes;if(n->terminal)++terms;for(const auto&e:n->child)walk(e.second.get());};walk(root_.get());return{true,nodes,terms};}}
'''
    stub=_stub(cls,'''bool SingleWildcardWordTrie::add(const std::string&){return false;} bool SingleWildcardWordTrie::erase(const std::string&){return false;} bool SingleWildcardWordTrie::contains(const std::string&)const{return false;} std::vector<std::string> SingleWildcardWordTrie::match(const std::string&,std::size_t)const{return{};}''')
    return Case("trie-wildcard-dictionary","single-wildcard-word-trie",cls,"Wildcard edge branching","Question-mark patterns branch through trie children at exact depth.",header,ref,stub,
      'SingleWildcardWordTrie x;check(x.add("cat"));check(x.add("cot"));check(x.add("dog"));check((x.match("c?t",9)==std::vector<std::string>{"cat","cot"}));check(x.match("??g",9)==std::vector<std::string>({"dog"}));check(x.erase("cot"));',
      'SingleWildcardWordTrie x;for(int a=0;a<8;++a)for(int b=0;b<8;++b){std::string word="w";word.push_back(char(\'a\'+a));word.push_back(char(\'a\'+b));check(x.add(word));}check(x.match("w??",100).size()==64);check(x.match("w?a",100).size()==8);check(x.audit_for_test().terminals==64);check(x.match("***",1).empty());',
      ("p[i]=='?'","for(const auto&e:n->child)","i==p.size()","match("))


def _case_glossary() -> Case:
    cls="MultilingualGlossaryTrie"
    # This case intentionally exposes Node forward declaration publicly so language-owned unique_ptr values are well-formed in the exact header.
    header=_header(cls,'''  struct Entry { std::string term; std::string translation; };
  bool add(const std::string& language, const std::string& term, const std::string& translation);
  bool erase(const std::string& language, const std::string& term);
  std::optional<std::string> exact(const std::string& language, const std::string& term) const;
  std::vector<Entry> with_prefix(const std::string& language, const std::string& prefix) const;''',"std::size_t language_tries; std::size_t terms;","  struct Node;\n  std::map<std::string,std::unique_ptr<Node>> languages_;")
    ref=r'''#include "task.h"
#include <algorithm>
#include <functional>
namespace curriculum{struct MultilingualGlossaryTrie::Node{std::map<char,std::unique_ptr<Node>>child;std::optional<std::string>translation;};namespace{bool language_ok(const std::string&s){return s.size()==2&&std::all_of(s.begin(),s.end(),[](char c){return c>='a'&&c<='z';});}bool term_ok(const std::string&s,bool empty=false){return(empty||!s.empty())&&std::all_of(s.begin(),s.end(),[](char c){return c>='a'&&c<='z';});}}
MultilingualGlossaryTrie::MultilingualGlossaryTrie()=default;MultilingualGlossaryTrie::~MultilingualGlossaryTrie()=default;
bool MultilingualGlossaryTrie::add(const std::string&lang,const std::string&term,const std::string&translation){if(!language_ok(lang)||!term_ok(term)||translation.empty())return false;auto&root=languages_[lang];if(!root)root=std::make_unique<Node>();Node*n=root.get();for(char c:term){auto&p=n->child[c];if(!p)p=std::make_unique<Node>();n=p.get();}if(n->translation)return false;n->translation=translation;return true;}
std::optional<std::string>MultilingualGlossaryTrie::exact(const std::string&lang,const std::string&term)const{if(!language_ok(lang)||!term_ok(term))return{};auto root=languages_.find(lang);if(root==languages_.end())return{};const Node*n=root->second.get();for(char c:term){auto it=n->child.find(c);if(it==n->child.end())return{};n=it->second.get();}return n->translation;}
bool MultilingualGlossaryTrie::erase(const std::string&lang,const std::string&term){if(!exact(lang,term))return false;auto root=languages_.find(lang);Node*n=root->second.get();std::vector<std::pair<Node*,char>>path;for(char c:term){path.push_back({n,c});n=n->child[c].get();}n->translation.reset();for(std::size_t i=path.size();i>0;--i){auto&p=path[i-1].first->child[path[i-1].second];if(!p->translation&&p->child.empty())path[i-1].first->child.erase(path[i-1].second);else break;}if(root->second->child.empty()&&!root->second->translation)languages_.erase(root);return true;}
std::vector<MultilingualGlossaryTrie::Entry>MultilingualGlossaryTrie::with_prefix(const std::string&lang,const std::string&p)const{std::vector<Entry>out;if(!language_ok(lang)||!term_ok(p,true))return out;auto root=languages_.find(lang);if(root==languages_.end())return out;const Node*n=root->second.get();for(char c:p){auto it=n->child.find(c);if(it==n->child.end())return{};n=it->second.get();}std::function<void(const Node*,std::string)>walk=[&](const Node*x,std::string word){if(x->translation)out.push_back({word,*x->translation});for(const auto&e:x->child)walk(e.second.get(),word+e.first);};walk(n,p);return out;}
MultilingualGlossaryTrie::Audit MultilingualGlossaryTrie::audit_for_test()const{std::size_t terms=0;for(const auto&language:languages_){std::function<void(const Node*)>walk=[&](const Node*n){if(n->translation)++terms;for(const auto&e:n->child)walk(e.second.get());};walk(language.second.get());}return{true,languages_.size(),terms};}}
'''
    # Audit initializer has bool plus two counts.
    ref=ref.replace('return{true,languages_.size(),terms};', 'return{true,languages_.size(),terms};')
    stub=_stub(cls,'''bool MultilingualGlossaryTrie::add(const std::string&,const std::string&,const std::string&){return false;} bool MultilingualGlossaryTrie::erase(const std::string&,const std::string&){return false;} std::optional<std::string> MultilingualGlossaryTrie::exact(const std::string&,const std::string&)const{return{};} std::vector<MultilingualGlossaryTrie::Entry> MultilingualGlossaryTrie::with_prefix(const std::string&,const std::string&)const{return{};}''').replace(':root_(std::make_unique<Node>())','')
    return Case("trie-translation-glossary","multilingual-glossary-trie",cls,"Language-partitioned glossary tries","A language map selects independent term tries and never owns terms directly.",header,ref,stub,
      'MultilingualGlossaryTrie x;check(x.add("en","cat","gato"));check(x.add("en","car","auto"));check(x.add("fr","car","voiture"));check(x.exact("fr","car")==std::optional<std::string>("voiture"));auto v=x.with_prefix("en","ca");check(v.size()==2&&v[0].term=="car");',
      'MultilingualGlossaryTrie x;for(int i=0;i<40;++i){std::string term="term"+std::string(1,char(\'a\'+i%20))+std::string(1,char(\'a\'+i/20));check(x.add(i%2?"en":"fr",term,"v"+std::to_string(i)));check(x.audit_for_test().valid);}check(x.with_prefix("en","term").size()==20);check(x.with_prefix("fr","term").size()==20);check(x.erase("en","termba"));check(!x.add("english","word","x"));',
      ("languages_","std::map<char,std::unique_ptr<Node>>child","translation","with_prefix"))


CASES = (
    _case_radix(),
    _case_tst(),
    _case_contact(),
    _case_digit(),
    _case_route(),
    _case_dns(),
    _case_dna(),
    _case_shortcode(),
    _case_spell(),
    _case_path(),
    _case_plate(),
    _case_predictive(),
    _case_tags(),
    _case_log(),
    _case_morse(),
    _case_token(),
    _case_sku(),
    _case_wildcard(),
    _case_glossary(),
    _case_rack(),
)
