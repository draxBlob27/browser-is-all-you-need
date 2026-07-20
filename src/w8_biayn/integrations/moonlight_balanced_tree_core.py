"""Private C++17 source fragments for the clean-room balanced-tree renderer."""

AVL_TREE = r'''namespace curriculum { namespace detail {
template<class K,class V,class Compare=std::less<K>> class AvlTree { struct Node{K key;V value;Node*left=nullptr;Node*right=nullptr;int height=1;std::size_t size=1;Node(K k,V v):key(std::move(k)),value(std::move(v)){} };Node*root_=nullptr;Compare less_{};static int h(const Node*n){return n?n->height:0;}static std::size_t z(const Node*n){return n?n->size:0;}static void fix(Node*n){n->height=1+std::max(h(n->left),h(n->right));n->size=1+z(n->left)+z(n->right);}static Node*l(Node*x){Node*y=x->right;x->right=y->left;y->left=x;fix(x);fix(y);return y;}static Node*r(Node*y){Node*x=y->left;y->left=x->right;x->right=y;fix(y);fix(x);return x;}Node*bal(Node*n){fix(n);int d=h(n->left)-h(n->right);if(d>1){if(h(n->left->right)>h(n->left->left))n->left=l(n->left);return r(n);}if(d<-1){if(h(n->right->left)>h(n->right->right))n->right=r(n->right);return l(n);}return n;}Node*put(Node*n,K k,V v,bool&c){if(!n){c=true;return new Node(std::move(k),std::move(v));}if(less_(k,n->key))n->left=put(n->left,std::move(k),std::move(v),c);else if(less_(n->key,k))n->right=put(n->right,std::move(k),std::move(v),c);else{n->value=std::move(v);return n;}return bal(n);}Node*del(Node*n,const K&k,bool&c){if(!n)return nullptr;if(less_(k,n->key))n->left=del(n->left,k,c);else if(less_(n->key,k))n->right=del(n->right,k,c);else{c=true;if(!n->left||!n->right){Node*q=n->left?n->left:n->right;delete n;return q;}Node*s=n->right;while(s->left)s=s->left;n->key=s->key;n->value=s->value;bool x=false;n->right=del(n->right,s->key,x);}return bal(n);}static void bye(Node*n){if(n){bye(n->left);bye(n->right);delete n;}}static void out(const Node*n,std::vector<V>&v){if(n){out(n->left,v);v.push_back(n->value);out(n->right,v);}}bool check(const Node*node,const K*lo,const K*hi,std::size_t&count,int&ht)const{if(!node){ht=0;return true;}if((lo&&!less_(*lo,node->key))||(hi&&!less_(node->key,*hi)))return false;int a=0,b=0;bool ok=check(node->left,lo,&node->key,count,a)&&check(node->right,&node->key,hi,count,b);ht=1+std::max(a,b);++count;return ok&&node->height==ht&&node->size==1+z(node->left)+z(node->right)&&std::abs(a-b)<=1;}public:AvlTree()=default;~AvlTree(){bye(root_);}AvlTree(const AvlTree&)=delete;AvlTree&operator=(const AvlTree&)=delete;bool put(K k,V v){bool c=false;root_=put(root_,std::move(k),std::move(v),c);return c;}bool erase(const K&k){bool c=false;root_=del(root_,k,c);return c;}const V*find(const K&k)const{const Node*n=root_;while(n){if(less_(k,n->key))n=n->left;else if(less_(n->key,k))n=n->right;else return &n->value;}return nullptr;}std::size_t size()const{return z(root_);}const V*select(std::size_t rank)const{if(rank==0||rank>z(root_))return nullptr;const Node*n=root_;while(n){const std::size_t left=z(n->left);if(rank<=left)n=n->left;else if(rank==left+1U)return &n->value;else{rank-=left+1U;n=n->right;}}return nullptr;}std::optional<std::size_t> rank_of(const K&k)const{const Node*n=root_;std::size_t rank=0;while(n){if(less_(k,n->key))n=n->left;else if(less_(n->key,k)){rank+=z(n->left)+1U;n=n->right;}else return rank+z(n->left)+1U;}return std::nullopt;}std::vector<V>values()const{std::vector<V>v;out(root_,v);return v;}bool valid(std::size_t&n,int&ht)const{n=0;return check(root_,nullptr,nullptr,n,ht);}}; }}'''


RB_TREE = r'''namespace curriculum { namespace detail {
template<class K,class V,class Compare=std::less<K>> class RbTree {
 enum class Color{red,black};
 struct Node{K key;V value;Color color=Color::red;Node*parent=nullptr;Node*left=nullptr;Node*right=nullptr;std::size_t weight=1,total=1;Node(K k,V v):key(std::move(k)),value(std::move(v)){}};
 Node*root_=nullptr;Compare less_{};
 static Color color(const Node*n){return n?n->color:Color::black;}
 static std::size_t total(const Node*n){return n?n->total:0;}
 static void clear(Node*n){if(n){clear(n->left);clear(n->right);delete n;}}
 static std::size_t refresh(Node*n){if(!n)return 0;n->total=refresh(n->left)+n->weight+refresh(n->right);return n->total;}
 Node*find_node(const K&k)const{Node*n=root_;while(n){if(less_(k,n->key))n=n->left;else if(less_(n->key,k))n=n->right;else return n;}return nullptr;}
 static Node*minimum(Node*n){while(n&&n->left)n=n->left;return n;}
 void left(Node*x){Node*y=x->right;x->right=y->left;if(y->left)y->left->parent=x;y->parent=x->parent;if(!x->parent)root_=y;else if(x==x->parent->left)x->parent->left=y;else x->parent->right=y;y->left=x;x->parent=y;}
 void right(Node*y){Node*x=y->left;y->left=x->right;if(x->right)x->right->parent=y;x->parent=y->parent;if(!y->parent)root_=x;else if(y==y->parent->right)y->parent->right=x;else y->parent->left=x;x->right=y;y->parent=x;}
 void insert_fix(Node*n){
  while(n->parent&&n->parent->color==Color::red){Node*p=n->parent;Node*g=p->parent;
   if(p==g->left){Node*u=g->right;if(color(u)==Color::red){p->color=Color::black;u->color=Color::black;g->color=Color::red;n=g;}else{if(n==p->right){n=p;left(n);p=n->parent;g=p->parent;}p->color=Color::black;g->color=Color::red;right(g);}}
   else{Node*u=g->left;if(color(u)==Color::red){p->color=Color::black;u->color=Color::black;g->color=Color::red;n=g;}else{if(n==p->left){n=p;right(n);p=n->parent;g=p->parent;}p->color=Color::black;g->color=Color::red;left(g);}}
  }root_->color=Color::black;
 }
 void transplant(Node*a,Node*b){if(!a->parent)root_=b;else if(a==a->parent->left)a->parent->left=b;else a->parent->right=b;if(b)b->parent=a->parent;}
 void erase_fix(Node*n,Node*p){
  while(n!=root_&&color(n)==Color::black){if(!p)break;
   if(n==p->left){Node*s=p->right;if(color(s)==Color::red){s->color=Color::black;p->color=Color::red;left(p);s=p->right;}if(!s){n=p;p=n->parent;continue;}if(color(s->left)==Color::black&&color(s->right)==Color::black){s->color=Color::red;n=p;p=n->parent;}else{if(color(s->right)==Color::black){if(s->left)s->left->color=Color::black;s->color=Color::red;right(s);s=p->right;}s->color=p->color;p->color=Color::black;if(s->right)s->right->color=Color::black;left(p);n=root_;p=nullptr;}}
   else{Node*s=p->left;if(color(s)==Color::red){s->color=Color::black;p->color=Color::red;right(p);s=p->left;}if(!s){n=p;p=n->parent;continue;}if(color(s->right)==Color::black&&color(s->left)==Color::black){s->color=Color::red;n=p;p=n->parent;}else{if(color(s->left)==Color::black){if(s->right)s->right->color=Color::black;s->color=Color::red;left(s);s=p->left;}s->color=p->color;p->color=Color::black;if(s->left)s->left->color=Color::black;right(p);n=root_;p=nullptr;}}
  }if(n)n->color=Color::black;
 }
 static void out(const Node*n,std::vector<V>&v){if(n){out(n->left,v);v.push_back(n->value);out(n->right,v);}}
 bool check(const Node*n,const Node*p,const K*lo,const K*hi,std::size_t&count,std::size_t&bh)const{
  if(!n){bh=1;return true;}if(n->parent!=p||(lo&&!less_(*lo,n->key))||(hi&&!less_(n->key,*hi)))return false;
  if(n->color==Color::red&&(color(n->left)==Color::red||color(n->right)==Color::red))return false;
  std::size_t a=0,b=0;if(!check(n->left,n,lo,&n->key,count,a)||!check(n->right,n,&n->key,hi,count,b))return false;
  ++count;bh=a+(n->color==Color::black?1U:0U);return a==b&&n->total==total(n->left)+n->weight+total(n->right);
 }
 public:
 RbTree()=default;~RbTree(){clear(root_);}RbTree(const RbTree&)=delete;RbTree&operator=(const RbTree&)=delete;
 bool put(K k,V v){Node*p=nullptr;Node*n=root_;while(n){p=n;if(less_(k,n->key))n=n->left;else if(less_(n->key,k))n=n->right;else{n->value=std::move(v);return false;}}n=new Node(std::move(k),std::move(v));n->parent=p;if(!p)root_=n;else if(less_(n->key,p->key))p->left=n;else p->right=n;insert_fix(n);refresh(root_);return true;}
 bool erase(const K&k){Node*z=find_node(k);if(!z)return false;Node*y=z;Color old=y->color;Node*x=nullptr;Node*xp=nullptr;if(!z->left){x=z->right;xp=z->parent;transplant(z,z->right);}else if(!z->right){x=z->left;xp=z->parent;transplant(z,z->left);}else{y=minimum(z->right);old=y->color;x=y->right;if(y->parent==z){xp=y;if(x)x->parent=y;}else{xp=y->parent;transplant(y,y->right);y->right=z->right;y->right->parent=y;}transplant(z,y);y->left=z->left;y->left->parent=y;y->color=z->color;}delete z;if(old==Color::black)erase_fix(x,x?x->parent:xp);if(root_)root_->color=Color::black;refresh(root_);return true;}
 const V*find(const K&k)const{Node*n=find_node(k);return n?&n->value:nullptr;}
 bool set_weight(const K&k,std::size_t w){Node*n=find_node(k);if(!n||w==0)return false;n->weight=w;refresh(root_);return true;}
 const V*select(std::size_t rank)const{if(rank==0||rank>total(root_))return nullptr;const Node*n=root_;while(n){std::size_t left_total=total(n->left);if(rank<=left_total)n=n->left;else if(rank<=left_total+n->weight)return &n->value;else{rank-=left_total+n->weight;n=n->right;}}return nullptr;}
 const K*select_key(std::size_t rank)const{if(rank==0||rank>total(root_))return nullptr;const Node*n=root_;while(n){std::size_t left_total=total(n->left);if(rank<=left_total)n=n->left;else if(rank<=left_total+n->weight)return &n->key;else{rank-=left_total+n->weight;n=n->right;}}return nullptr;}
 std::vector<V>values()const{std::vector<V>v;out(root_,v);return v;}
 std::size_t total_weight()const{return total(root_);}
 bool valid(std::size_t&n,std::size_t&bh)const{n=0;bh=1;if(root_&&(root_->parent||root_->color!=Color::black))return false;return check(root_,nullptr,nullptr,nullptr,n,bh);}
}; }}'''

def tree_source(kind: str) -> str:
    if kind == "AVL":
        return AVL_TREE
    if kind == "RB":
        return RB_TREE
    raise ValueError(f"unknown balanced-tree kind: {kind}")
