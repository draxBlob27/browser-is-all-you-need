"""Artifact-owned hard-diversity traces and false substitutes for trie v3."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NegativeProfile:
    name: str
    declaration: str
    mutation: str


NEGATIVE_PROFILES = {
    "radix-command-catalog": NegativeProfile("flat-ordered-command-scan", "static std::map<std::string,int> bad_state;", 'return bad_state.emplace("help",1).second;'),
    "tst-product-prefix": NegativeProfile("sorted-product-vector", "static std::vector<std::pair<std::string,int>> bad_state;", 'bad_state.push_back({"PA",1});return true;'),
    "contact-alias-trie": NegativeProfile("flat-contact-alias-table", "static std::unordered_map<int,std::string> bad_state;", 'return bad_state.emplace(1,"ada").second;'),
    "digit-call-range-trie": NegativeProfile("ordered-call-number-set", "static std::set<std::string> bad_state;", 'return bad_state.insert("1200").second;'),
    "segment-route-dispatch-trie": NegativeProfile("joined-route-string-map", "static std::map<std::string,int> bad_state;", 'return bad_state.emplace("api/v1",1).second;'),
    "reversed-domain-policy-trie": NegativeProfile("forward-domain-suffix-scan", "static std::vector<std::pair<std::string,int>> bad_state;", 'bad_state.push_back({"example.org",1});return true;'),
    "dna-motif-counter-trie": NegativeProfile("sorted-motif-vector", "static std::vector<std::string> bad_state;", 'bad_state.push_back("ACGT");return true;'),
    "unique-shortcode-trie": NegativeProfile("flat-shortcode-expansion-map", "static std::map<std::string,std::string> bad_state;", 'return bad_state.emplace("smile","happy").second;'),
    "levenshtein-spell-trie": NegativeProfile("full-dictionary-distance-scan", "static std::set<std::string> bad_state;", 'return bad_state.insert("cat").second;'),
    "path-descendant-trie": NegativeProfile("joined-path-record-map", "static std::map<std::string,long long> bad_state;", 'return bad_state.emplace("src/a.cpp",10).second;'),
    "normalized-plate-reservation-trie": NegativeProfile("normalized-plate-set-scan", "static std::set<std::string> bad_state;", 'return bad_state.insert("AB12").second;'),
    "cached-topk-text-trie": NegativeProfile("global-frequency-sort", "static std::map<std::string,int> bad_state;", 'return bad_state.emplace("alpha",3).second;'),
    "tag-posting-trie": NegativeProfile("flat-tag-posting-map", "static std::map<std::string,std::set<int>> bad_state;", 'return bad_state["tag"].insert(1).second;'),
    "hierarchical-log-policy-trie": NegativeProfile("flat-ancestor-string-scan", "static std::map<std::string,int> bad_state;", 'return bad_state.emplace("root.api",1).second;'),
    "prefix-free-morse-trie": NegativeProfile("flat-codebook-pair-scan", "static std::map<char,std::string> bad_state;", 'return bad_state.emplace(\'A\',".-").second;'),
    "shortest-token-prefix-trie": NegativeProfile("full-token-set-scan", "static std::set<std::string> bad_state;", 'return bad_state.insert("token-a").second;'),
    "numeric-sku-allocation-trie": NegativeProfile("linear-reservation-set-scan", "static std::set<std::string> bad_state;", 'return bad_state.insert("SKU00").second;'),
    "single-wildcard-word-trie": NegativeProfile("full-word-pattern-scan", "static std::vector<std::string> bad_state;", 'bad_state.push_back("cat");return true;'),
    "multilingual-glossary-trie": NegativeProfile("flat-language-term-map", "static std::map<std::pair<std::string,std::string>,std::string> bad_state;", 'return bad_state.emplace(std::make_pair("en","cat"),"gato").second;'),
    "rack-prefix-word-trie": NegativeProfile("full-dictionary-rack-scan", "static std::set<std::string> bad_state;", 'return bad_state.insert("cart").second;'),
}


HARD_RULE_TRACES = {
"radix-command-catalog": r'''
RadixCommandCatalog x; std::vector<std::string> model;
auto verify=[&](){auto expected=model;std::sort(expected.begin(),expected.end());check(x.complete("a",99)==expected);check(x.size()==model.size());for(const auto&s:std::vector<std::string>{"add","app","ape","bad"})check(x.contains(s)==(std::find(model.begin(),model.end(),s)!=model.end()));check(x.audit_for_test().valid);};
auto add=[&](const std::string&s){bool want=std::find(model.begin(),model.end(),s)==model.end();check(x.add(s)==want);if(want)model.push_back(s);verify();};
auto erase=[&](const std::string&s){auto it=std::find(model.begin(),model.end(),s);bool want=it!=model.end();check(x.erase(s)==want);if(want)model.erase(it);verify();};
verify();add("add");add("app");add("ape");add("app");erase("add");erase("bad");check(x.complete("ap",1)==std::vector<std::string>({"ape"}));
''',
"tst-product-prefix": r'''
ProductPrefixTst x;std::map<std::string,int> model;
auto verify=[&](){for(const auto&s:std::vector<std::string>{"PA","PB","PC"}){auto it=model.find(s);check(x.stock_of(s)==(it==model.end()?std::optional<int>{}:std::optional<int>{it->second}));}auto got=x.with_prefix("P",99);check(got.size()==model.size());std::size_t i=0;for(const auto&e:model){check(got[i].code==e.first&&got[i].stock==e.second);++i;}check(x.audit_for_test().valid);};
auto add=[&](std::string s,int v){bool want=!model.count(s);check(x.add(s,v)==want);if(want)model[s]=v;verify();};auto stock=[&](std::string s,int v){bool want=model.count(s);check(x.set_stock(s,v)==want);if(want)model[s]=v;verify();};auto erase=[&](std::string s){bool want=model.erase(s);check(x.erase(s)==want);verify();};
verify();add("PA",2);add("PB",4);stock("PA",7);stock("PC",1);erase("PB");erase("PB");check(x.with_prefix("P",0).empty());
''',
"contact-alias-trie": r'''
ContactAliasTrie x;std::map<int,std::string> model;
auto verify=[&](){for(const std::string p:{"a","g","z"}){std::vector<ContactAliasTrie::Contact>want;for(const auto&e:model)if(e.second.rfind(p,0)==0)want.push_back({e.first,e.second});std::sort(want.begin(),want.end(),[](const auto&a,const auto&b){return a.normalized_name!=b.normalized_name?a.normalized_name<b.normalized_name:a.id<b.id;});auto got=x.search(p);check(got.size()==want.size());for(std::size_t i=0;i<got.size();++i)check(got[i].id==want[i].id&&got[i].normalized_name==want[i].normalized_name);}check(x.audit_for_test().contacts==model.size()&&x.audit_for_test().valid);};
auto add=[&](int id,std::string n){bool want=id>0&&!model.count(id);check(x.add(id,n)==want);if(want)model[id]=n;verify();};auto rename=[&](int id,std::string n){bool want=model.count(id);check(x.rename(id,n)==want);if(want)model[id]=n;verify();};auto erase=[&](int id){bool want=model.erase(id);check(x.erase(id)==want);verify();};
verify();add(1,"ada");add(2,"grace");add(1,"other");rename(1,"alice");rename(9,"nobody");erase(2);erase(2);
''',
"digit-call-range-trie": r'''
DigitCallRangeTrie x;std::set<std::string> model;
auto verify=[&](){for(const std::string s:{"120","121","200"})check(x.contains(s)==model.count(s));for(const std::string p:{"","1","12","2"}){std::vector<std::string>v;for(const auto&s:model)if(s.rfind(p,0)==0)v.push_back(s);check(x.count_prefix(p)==v.size());for(const std::string a:{"","120","199"}){auto it=std::upper_bound(v.begin(),v.end(),a);check(x.next_after(p,a)==(it==v.end()?std::optional<std::string>{}:std::optional<std::string>{*it}));}}check(x.audit_for_test().valid);};auto add=[&](std::string s){bool want=model.insert(s).second;check(x.add(s)==want);verify();};auto erase=[&](std::string s){bool want=model.erase(s);check(x.erase(s)==want);verify();};
verify();add("120");add("121");add("200");add("120");erase("121");erase("999");
''',
"segment-route-dispatch-trie": r'''
SegmentRouteDispatchTrie x;std::map<std::vector<std::string>,int> model;
auto verify=[&](){for(const auto&path:std::vector<std::vector<std::string>>{{"api"},{"api","v1"},{"api","v1","users"},{"web"}}){std::optional<SegmentRouteDispatchTrie::Match>want;for(std::size_t n=1;n<=path.size();++n){std::vector<std::string>p(path.begin(),path.begin()+std::ptrdiff_t(n));auto it=model.find(p);if(it!=model.end())want=SegmentRouteDispatchTrie::Match{it->second,n};}auto got=x.resolve(path);check(bool(got)==bool(want));if(got&&want)check(got->handler==want->handler&&got->consumed_segments==want->consumed_segments);}for(const auto&p:std::vector<std::vector<std::string>>{{},{"api"},{"web"}}){std::size_t n=0;for(const auto&e:model)if(e.first.size()>=p.size()&&std::equal(p.begin(),p.end(),e.first.begin()))++n;check(x.route_count_under(p)==n);}check(x.audit_for_test().valid);};auto set=[&](std::vector<std::string>p,int h){bool want=!model.count(p);check(x.set(p,h)==want);if(want)model[p]=h;verify();};auto erase=[&](std::vector<std::string>p){bool want=model.erase(p);check(x.erase(p)==want);verify();};
verify();set({"api"},1);set({"api","v1"},2);set({"web"},3);set({"api"},9);erase({"api","v1"});erase({"none"});
''',
"reversed-domain-policy-trie": r'''
ReversedDomainPolicyTrie x;std::map<std::string,int> model;
auto suffix=[&](const std::string&host,const std::string&rule){return host==rule||(host.size()>rule.size()&&host.compare(host.size()-rule.size(),rule.size(),rule)==0&&host[host.size()-rule.size()-1]=='.');};auto verify=[&](){for(const std::string host:{"example.org","api.example.org","v1.api.example.org","none.net"}){std::optional<ReversedDomainPolicyTrie::Match>want;for(const auto&e:model)if(suffix(host,e.first)&&(!want||e.first.size()>want->suffix.size()))want=ReversedDomainPolicyTrie::Match{e.first,e.second};auto got=x.resolve(host);check(bool(got)==bool(want));if(got&&want)check(got->suffix==want->suffix&&got->policy==want->policy);}check(x.rule_count()==model.size()&&x.audit_for_test().valid);};auto set=[&](std::string s,int p){bool want=!model.count(s);check(x.set(s,p)==want);if(want)model[s]=p;verify();};auto erase=[&](std::string s){bool want=model.erase(s);check(x.erase(s)==want);verify();};
verify();set("example.org",1);set("api.example.org",2);set("example.org",3);erase("api.example.org");erase("none.org");
''',
"dna-motif-counter-trie": r'''
DnaMotifCounterTrie x;std::set<std::string>model;auto verify=[&](){for(const std::string s:{"A","AC","ACG","ACGT","AG"})check(x.contains(s)==model.count(s));for(const std::string p:{"","A","AC","T"}){std::size_t n=0;for(const auto&s:model)if(s.rfind(p,0)==0)++n;check(x.count_prefix(p)==n);}for(const std::string q:{"ACGTA","AGT","TT"}){std::optional<std::string>w;for(const auto&s:model)if(q.rfind(s,0)==0&&(!w||s.size()>w->size()))w=s;check(x.longest_stored_prefix(q)==w);}check(x.audit_for_test().valid);};auto add=[&](std::string s){bool w=model.insert(s).second;check(x.add(s)==w);verify();};auto erase=[&](std::string s){bool w=model.erase(s);check(x.erase(s)==w);verify();};verify();add("A");add("ACG");add("ACGT");add("A");erase("ACG");erase("TT");
''',
"unique-shortcode-trie": r'''
UniqueShortcodeTrie x;std::map<std::string,std::string>model;auto verify=[&](){for(const std::string p:{"","s","sm","smi","z"}){std::vector<std::string>keys;for(const auto&e:model)if(e.first.rfind(p,0)==0)keys.push_back(e.first);check(x.count_prefix(p)==keys.size());std::optional<std::string>w;if(keys.size()==1)w=model.at(keys[0]);check(x.expand_unique(p)==w);}check(x.audit_for_test().valid);};auto add=[&](std::string s,std::string v){bool w=!model.count(s);check(x.add(s,v)==w);if(w)model[s]=v;verify();};auto erase=[&](std::string s){bool w=model.erase(s);check(x.erase(s)==w);verify();};verify();add("smile","happy");add("smirk","wry");add("smile","x");erase("smirk");erase("none");
''',
"levenshtein-spell-trie": r'''
LevenshteinSpellTrie x;std::set<std::string>model;auto distance=[](const std::string&a,const std::string&b){std::vector<int>p(b.size()+1);for(std::size_t j=0;j<p.size();++j)p[j]=int(j);for(std::size_t i=1;i<=a.size();++i){std::vector<int>r(b.size()+1);r[0]=int(i);for(std::size_t j=1;j<=b.size();++j)r[j]=std::min({r[j-1]+1,p[j]+1,p[j-1]+(a[i-1]==b[j-1]?0:1)});p=r;}return p.back();};auto verify=[&](){for(const std::string s:{"cat","cart","dog"})check(x.contains(s)==model.count(s));for(const std::string q:{"cat","cot"}){std::vector<std::pair<std::string,int>>w;for(const auto&s:model){int d=distance(s,q);if(d<=1)w.push_back({s,d});}std::sort(w.begin(),w.end(),[](const auto&a,const auto&b){return a.second!=b.second?a.second<b.second:a.first<b.first;});auto g=x.suggest(q,1,99);check(g.size()==w.size());for(std::size_t i=0;i<g.size();++i)check(g[i].word==w[i].first&&g[i].distance==w[i].second);}check(x.audit_for_test().valid);};auto add=[&](std::string s){bool w=model.insert(s).second;check(x.add(s)==w);verify();};auto erase=[&](std::string s){bool w=model.erase(s);check(x.erase(s)==w);verify();};verify();add("cat");add("cart");add("dog");add("cat");erase("cart");erase("none");
''',
"path-descendant-trie": r'''
PathDescendantTrie x;std::map<std::vector<std::string>,long long>model;auto verify=[&](){for(const auto&d:std::vector<std::vector<std::string>>{{},{"src"},{"src","lib"}}){std::size_t files=0;long long bytes=0;std::set<std::string>children;for(const auto&e:model)if(e.first.size()>=d.size()&&std::equal(d.begin(),d.end(),e.first.begin())){++files;bytes+=e.second;if(e.first.size()>d.size())children.insert(e.first[d.size()]);}check(x.descendant_files(d)==files);check(x.descendant_bytes(d)==bytes);check(x.child_names(d)==std::vector<std::string>(children.begin(),children.end()));}auto a=x.audit_for_test();check(a.valid&&a.files==model.size());};auto add=[&](std::vector<std::string>p,long long b){bool w=!model.count(p);check(x.add_file(p,b)==w);if(w)model[p]=b;verify();};auto erase=[&](std::vector<std::string>p){bool w=model.erase(p);check(x.erase_file(p)==w);verify();};verify();add({"src","a.cpp"},10);add({"src","lib","b.cpp"},7);add({"src","a.cpp"},3);erase({"src","a.cpp"});erase({"none"});
''',
"normalized-plate-reservation-trie": r'''
NormalizedPlateReservationTrie x;std::set<std::string>model;auto verify=[&](){for(const std::string s:{"AB12","AB13","XY99"})check(x.is_reserved(s)==model.count(s));for(const std::string p:{"","A","AB","X"}){std::size_t n=0;for(const auto&s:model)if(s.rfind(p,0)==0)++n;check(x.count_prefix(p)==n);check(x.prefix_is_unique(p)==(n==1));}check(x.audit_for_test().valid);};auto add=[&](std::string s){bool w=model.insert(s).second;check(x.reserve(s)==w);verify();};auto erase=[&](std::string s){bool w=model.erase(s);check(x.release(s)==w);verify();};verify();add("AB12");add("AB13");add("XY99");add("AB12");erase("AB13");erase("NO00");
''',
"cached-topk-text-trie": r'''
CachedTopKTextTrie x;std::map<std::string,int>model;auto verify=[&](){for(const std::string s:{"ape","app","bat"}){auto i=model.find(s);check(x.frequency(s)==(i==model.end()?std::optional<int>{}:std::optional<int>{i->second}));}for(const std::string p:{"","ap","b"}){std::vector<CachedTopKTextTrie::Completion>w;for(const auto&e:model)if(e.first.rfind(p,0)==0)w.push_back({e.first,e.second});std::sort(w.begin(),w.end(),[](const auto&a,const auto&b){return a.frequency!=b.frequency?a.frequency>b.frequency:a.word<b.word;});if(w.size()>8)w.resize(8);auto g=x.top(p,99);check(g.size()==w.size());for(std::size_t i=0;i<g.size();++i)check(g[i].word==w[i].word&&g[i].frequency==w[i].frequency);}check(x.audit_for_test().valid);};auto record=[&](std::string s,int d){check(x.record(s,d));model[s]+=d;verify();};auto erase=[&](std::string s){bool w=model.erase(s);check(x.erase(s)==w);verify();};verify();record("ape",2);record("app",4);record("ape",3);record("bat",1);erase("app");erase("none");
''',
"tag-posting-trie": r'''
TagPostingTrie x;std::map<std::string,std::set<int>>model;auto verify=[&](){for(const std::string t:{"alpha","api","beta"})check(x.exact_posting_count(t)==model[t].size());for(const std::string p:{"","a","ap","b"}){std::set<int>ids;for(const auto&e:model)if(e.first.rfind(p,0)==0)ids.insert(e.second.begin(),e.second.end());check(x.ids_with_prefix(p)==std::vector<int>(ids.begin(),ids.end()));}check(x.audit_for_test().valid);};auto add=[&](std::string t,int id){bool w=model[t].insert(id).second;check(x.add(t,id)==w);verify();};auto remove=[&](std::string t,int id){bool w=model[t].erase(id);check(x.remove(t,id)==w);verify();};verify();add("alpha",1);add("api",2);add("api",1);add("api",1);remove("alpha",1);remove("alpha",9);
''',
"hierarchical-log-policy-trie": r'''
HierarchicalLogPolicyTrie x;std::map<std::string,LogPolicy>model;auto effective=[&](std::string s){LogPolicy out=LogPolicy::deny;std::string cur;for(char c:s){if(c=='.'){auto i=model.find(cur);if(i!=model.end())out=i->second;}cur+=c;}auto i=model.find(s);if(i!=model.end())out=i->second;return out;};auto verify=[&](){for(const std::string s:{"root","root.api","root.api.db","other"})check(x.effective(s)==effective(s));for(const std::string p:{"root","root.api","other"}){std::vector<std::string>w;for(const auto&e:model)if(e.first==p||e.first.rfind(p+".",0)==0)w.push_back(e.first);check(x.explicit_under(p)==w);}check(x.audit_for_test().valid);};auto set=[&](std::string s,LogPolicy p){bool w=!model.count(s);check(x.set(s,p)==w);if(w)model[s]=p;verify();};auto clear=[&](std::string s){bool w=model.erase(s);check(x.clear(s)==w);verify();};verify();set("root",LogPolicy::allow);set("root.api",LogPolicy::deny);set("root",LogPolicy::deny);clear("root.api");clear("none");
''',
"prefix-free-morse-trie": r'''
PrefixFreeMorseTrie x;std::map<char,std::string>model;auto can=[&](const std::string&c){if(c.empty()||c.find_first_not_of(".-")!=std::string::npos)return false;for(const auto&e:model)if(e.second.rfind(c,0)==0||c.rfind(e.second,0)==0)return false;return true;};auto verify=[&](){for(const std::string c:{".-","--","..","-"}){std::optional<char>w;for(const auto&e:model)if(e.second==c)w=e.first;check(x.decode(c)==w);check(x.can_add(c)==can(c));}check(x.audit_for_test().valid);};auto add=[&](char s,std::string c){bool w=!model.count(s)&&can(c);check(x.add(s,c)==w);if(w)model[s]=c;verify();};auto erase=[&](char s){bool w=model.erase(s);check(x.erase(s)==w);verify();};verify();add('A',".-");add('B',"--");add('C',".");erase('A');erase('Z');
''',
"shortest-token-prefix-trie": r'''
ShortestTokenPrefixTrie x;std::set<std::string>model;auto matches=[&](const std::string&p){std::vector<std::string>v;for(const auto&s:model)if(s.rfind(p,0)==0)v.push_back(s);return v;};auto verify=[&](){for(const std::string p:{"t","to","tokena","x"}){auto v=matches(p);PrefixState st=v.empty()?PrefixState::absent:(v.size()==1?PrefixState::unique:PrefixState::ambiguous);auto g=x.resolve(p);check(g.state==st);if(st==PrefixState::unique)check(g.token==v[0]);}for(const auto&s:model){std::optional<std::string>w;for(std::size_t n=1;n<=s.size();++n)if(matches(s.substr(0,n)).size()==1){w=s.substr(0,n);break;}check(x.shortest_unique(s)==w);}check(x.audit_for_test().valid);};auto add=[&](std::string s){bool w=model.insert(s).second;check(x.issue(s)==w);verify();};auto erase=[&](std::string s){bool w=model.erase(s);check(x.revoke(s)==w);verify();};verify();add("tokena");add("tokenb");add("tokena");erase("tokenb");erase("none");
''',
"numeric-sku-allocation-trie": r'''
NumericSkuAllocationTrie x;std::set<std::string>model;auto key=[](const std::string&p,unsigned s,unsigned w){std::string d=std::to_string(s);return p+std::string(w-d.size(),'0')+d;};auto verify=[&](){for(unsigned i=0;i<4;++i)check(x.is_reserved("SKU",i,2)==model.count(key("SKU",i,2)));check(x.audit_for_test().valid);};auto reserve=[&](unsigned s){bool w=model.insert(key("SKU",s,2)).second;check(x.reserve("SKU",s,2)==w);verify();};auto release=[&](unsigned s){bool w=model.erase(key("SKU",s,2));check(x.release("SKU",s,2)==w);verify();};verify();reserve(0);reserve(1);reserve(1);auto a=x.allocate_first("SKU",2);check(a==std::optional<unsigned>(2));model.insert(key("SKU",2,2));verify();release(1);release(9);auto b=x.allocate_first("TMP",1);check(b==std::optional<unsigned>(0));check(x.release("TMP",0,1));verify();
''',
"single-wildcard-word-trie": r'''
SingleWildcardWordTrie x;std::set<std::string>model;auto match=[](const std::string&s,const std::string&p){if(s.size()!=p.size())return false;for(std::size_t i=0;i<s.size();++i)if(p[i]!='?'&&p[i]!=s[i])return false;return true;};auto verify=[&](){for(const std::string s:{"cat","cot","dog"})check(x.contains(s)==model.count(s));for(const std::string p:{"c?t","???","d?g"}){std::vector<std::string>w;for(const auto&s:model)if(match(s,p))w.push_back(s);check(x.match(p,99)==w);}check(x.audit_for_test().valid);};auto add=[&](std::string s){bool w=model.insert(s).second;check(x.add(s)==w);verify();};auto erase=[&](std::string s){bool w=model.erase(s);check(x.erase(s)==w);verify();};verify();add("cat");add("cot");add("dog");add("cat");erase("cot");erase("none");
''',
"multilingual-glossary-trie": r'''
MultilingualGlossaryTrie x;std::map<std::pair<std::string,std::string>,std::string>model;auto verify=[&](){for(const std::string l:{"en","fr"})for(const std::string t:{"car","cat"}){auto i=model.find({l,t});check(x.exact(l,t)==(i==model.end()?std::optional<std::string>{}:std::optional<std::string>{i->second}));}for(const std::string l:{"en","fr"}){std::vector<MultilingualGlossaryTrie::Entry>w;for(const auto&e:model)if(e.first.first==l&&e.first.second.rfind("ca",0)==0)w.push_back({e.first.second,e.second});auto g=x.with_prefix(l,"ca");check(g.size()==w.size());for(std::size_t i=0;i<g.size();++i)check(g[i].term==w[i].term&&g[i].translation==w[i].translation);}check(x.audit_for_test().valid);};auto add=[&](std::string l,std::string t,std::string v){bool w=!model.count({l,t});check(x.add(l,t,v)==w);if(w)model[{l,t}]=v;verify();};auto erase=[&](std::string l,std::string t){bool w=model.erase({l,t});check(x.erase(l,t)==w);verify();};verify();add("en","cat","gato");add("en","car","auto");add("fr","car","voiture");add("en","cat","x");erase("en","car");erase("fr","cat");
''',
"rack-prefix-word-trie": r'''
RackPrefixWordTrie x;std::set<std::string>model;auto playable=[](const std::string&w,const std::string&p,const std::string&r){if(w.rfind(p,0)!=0)return false;std::array<int,26>count{};for(char c:r)++count[std::size_t(c-'a')];for(std::size_t i=p.size();i<w.size();++i)if(--count[std::size_t(w[i]-'a')]<0)return false;return true;};auto verify=[&](){for(const std::string s:{"a","ab","abc","bad"})check(x.contains(s)==model.count(s));for(const auto&q:std::vector<std::pair<std::string,std::string>>{{"a","bc"},{"b","ad"}}){std::vector<std::string>w;for(const auto&s:model)if(playable(s,q.first,q.second))w.push_back(s);check(x.playable(q.first,q.second,99)==w);}check(x.audit_for_test().valid);};auto add=[&](std::string s){bool w=model.insert(s).second;check(x.add(s)==w);verify();};auto erase=[&](std::string s){bool w=model.erase(s);check(x.erase(s)==w);verify();};verify();add("a");add("ab");add("abc");add("bad");add("a");erase("ab");erase("none");
''',
}


if set(HARD_RULE_TRACES) != set(NEGATIVE_PROFILES):
    raise RuntimeError("hard-rule trace/profile inventory mismatch")
