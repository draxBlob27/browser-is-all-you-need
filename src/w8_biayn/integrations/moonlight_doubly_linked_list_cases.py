"""Independent contracts and C++ fragments for the remediated DLL family."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    legacy_id: str
    task_id: str
    class_name: str
    declarations: str
    node_fields: str
    private_fields: str
    starter: str
    reference: str
    visible: str
    hidden: str
    contract: str
    logic_tag: str


CASES = (
    Case("dll-book-shelf", "dll-book-shelf", "BookShelf", """
  bool place(int id, int after_id);
  bool remove(int id);
  bool move_range(int first_id, int last_id, int after_id);
  std::vector<int> shelf() const;
  std::vector<int> reverse_shelf() const;""", "", "", """
BookShelf::~BookShelf() = default;
bool BookShelf::place(int,int){return false;} bool BookShelf::remove(int){return false;}
bool BookShelf::move_range(int,int,int){return false;}
std::vector<int> BookShelf::shelf()const{return{};} std::vector<int> BookShelf::reverse_shelf()const{return{};}""", """
bool BookShelf::place(int id,int after_id){if(id<=0||find(id))return false;Node* a=after_id==0?nullptr:find(after_id);if(after_id!=0&&!a)return false;insert_after(new Node{id,nullptr,nullptr},a);return true;}
bool BookShelf::remove(int id){Node*n=find(id);if(!n)return false;unlink(n);delete n;return true;}
bool BookShelf::move_range(int first_id,int last_id,int after_id){Node*f=find(first_id),*l=find(last_id),*a=after_id==0?nullptr:find(after_id);if(!f||!l||(after_id!=0&&!a))return false;bool reached=false,anchor_inside=false;for(Node*n=f;n;n=n->next){if(n==a)anchor_inside=true;if(n==l){reached=true;break;}}if(!reached||anchor_inside)return false;Node*before=f->prev,*after=l->next;if(before)before->next=after;else head_=after;if(after)after->prev=before;else tail_=before;if(!a){f->prev=nullptr;l->next=head_;if(head_)head_->prev=l;else tail_=l;head_=f;}else{f->prev=a;l->next=a->next;if(a->next)a->next->prev=l;else tail_=l;a->next=f;}return true;}
std::vector<int> BookShelf::shelf()const{std::vector<int>v;for(Node*n=head_;n;n=n->next)v.push_back(n->id);return v;}std::vector<int> BookShelf::reverse_shelf()const{std::vector<int>v;for(Node*n=tail_;n;n=n->prev)v.push_back(n->id);return v;}""", """
BookShelf s; REQUIRE(s.place(1,0)); REQUIRE(s.place(2,1)); REQUIRE(s.place(3,2)); REQUIRE(s.move_range(2,3,0)); REQUIRE(s.shelf()==std::vector<int>{2,3,1});""", """
BookShelf s; REQUIRE_FALSE(s.place(0,0)); for(int id:{1,2,3,4})REQUIRE(s.place(id,id==1?0:id-1)); REQUIRE_FALSE(s.move_range(2,4,3)); REQUIRE(s.move_range(2,3,4)); REQUIRE(s.shelf()==std::vector<int>{1,4,2,3}); REQUIRE(s.reverse_shelf()==std::vector<int>{3,2,4,1}); REQUIRE(s.remove(1)); REQUIRE_FALSE(s.remove(1));""",
         "Move a contiguous shelf range atomically; zero anchor means front and an anchor inside the range is invalid.", "contiguous-range-splice"),
    Case("dll-browser-history", "dll-navigation-journal", "NavigationJournal", """
  bool visit(int page_id);
  std::optional<int> back(std::size_t steps);
  std::optional<int> forward(std::size_t steps);
  std::optional<int> current() const;
  std::vector<int> timeline() const;""", "", "Node* current_ = nullptr;", """
NavigationJournal::~NavigationJournal()=default;bool NavigationJournal::visit(int){return false;}std::optional<int> NavigationJournal::back(std::size_t){return std::nullopt;}std::optional<int> NavigationJournal::forward(std::size_t){return std::nullopt;}std::optional<int> NavigationJournal::current()const{return std::nullopt;}std::vector<int> NavigationJournal::timeline()const{return{};}""", """
bool NavigationJournal::visit(int id){if(id<=0)return false;if(!current_){Node*n=new Node{id,nullptr,nullptr};head_=tail_=current_=n;return true;}Node*n=current_->next;while(n){Node*next=n->next;delete n;n=next;}current_->next=nullptr;tail_=current_;Node*added=new Node{id,nullptr,nullptr};insert_after(added,current_);current_=added;return true;}
std::optional<int> NavigationJournal::back(std::size_t steps){Node*n=current_;for(std::size_t i=0;i<steps;++i){if(!n||!n->prev)return std::nullopt;n=n->prev;}if(!n)return std::nullopt;current_=n;return n->id;}std::optional<int> NavigationJournal::forward(std::size_t steps){Node*n=current_;for(std::size_t i=0;i<steps;++i){if(!n||!n->next)return std::nullopt;n=n->next;}if(!n)return std::nullopt;current_=n;return n->id;}std::optional<int> NavigationJournal::current()const{return current_?std::optional<int>(current_->id):std::nullopt;}std::vector<int> NavigationJournal::timeline()const{std::vector<int>v;for(Node*n=head_;n;n=n->next)v.push_back(n->id);return v;}""", """
NavigationJournal j; REQUIRE(j.visit(10)); REQUIRE(j.visit(20)); REQUIRE(j.visit(30)); REQUIRE(j.back(1)==20); REQUIRE(j.visit(40)); REQUIRE(j.timeline()==std::vector<int>{10,20,40});""", """
NavigationJournal j; REQUIRE_FALSE(j.back(1)); for(int id:{1,2,3,4})REQUIRE(j.visit(id)); REQUIRE(j.back(2)==2); REQUIRE_FALSE(j.back(3)); REQUIRE(j.current()==2); REQUIRE(j.forward(1)==3); REQUIRE(j.visit(9)); REQUIRE_FALSE(j.forward(1)); REQUIRE(j.timeline()==std::vector<int>{1,2,3,9});""",
         "Visiting after backward navigation prunes the entire forward branch; failed navigation is atomic.", "cursor-branch-pruning"),
    Case("dll-card-table-order", "dll-elimination-circle", "EliminationCircle", """
  bool seat(int player_id, int after_id);
  std::optional<int> pass(std::size_t steps);
  std::optional<int> eliminate_current();
  void reverse_direction();
  std::optional<int> current() const;
  std::vector<int> clockwise() const;""", "", "Node* current_ = nullptr; int direction_ = 1;", """
EliminationCircle::~EliminationCircle()=default;bool EliminationCircle::seat(int,int){return false;}std::optional<int> EliminationCircle::pass(std::size_t){return std::nullopt;}std::optional<int> EliminationCircle::eliminate_current(){return std::nullopt;}void EliminationCircle::reverse_direction(){}std::optional<int> EliminationCircle::current()const{return std::nullopt;}std::vector<int> EliminationCircle::clockwise()const{return{};}""", """
bool EliminationCircle::seat(int id,int after_id){if(id<=0||find(id))return false;Node*a=after_id==0?tail_:find(after_id);if(after_id!=0&&!a)return false;Node*n=new Node{id,nullptr,nullptr};insert_after(n,a);if(!current_)current_=n;return true;}std::optional<int> EliminationCircle::pass(std::size_t steps){if(!current_)return std::nullopt;for(std::size_t i=0;i<steps;++i)current_=direction_>0?(current_->next?current_->next:head_):(current_->prev?current_->prev:tail_);return current_->id;}std::optional<int> EliminationCircle::eliminate_current(){if(!current_)return std::nullopt;Node*dead=current_;int id=dead->id;if(head_==tail_)current_=nullptr;else current_=direction_>0?(dead->next?dead->next:head_):(dead->prev?dead->prev:tail_);unlink(dead);delete dead;return id;}void EliminationCircle::reverse_direction(){direction_=-direction_;}std::optional<int> EliminationCircle::current()const{return current_?std::optional<int>(current_->id):std::nullopt;}std::vector<int> EliminationCircle::clockwise()const{std::vector<int>v;for(Node*n=head_;n;n=n->next)v.push_back(n->id);return v;}""", """
EliminationCircle c; REQUIRE(c.seat(1,0)); REQUIRE(c.seat(2,1)); REQUIRE(c.seat(3,2)); REQUIRE(c.pass(2)==3); REQUIRE(c.eliminate_current()==3); REQUIRE(c.current()==1);""", """
EliminationCircle c; REQUIRE_FALSE(c.eliminate_current()); for(int id:{1,2,3,4})REQUIRE(c.seat(id,id-1)); c.reverse_direction(); REQUIRE(c.pass(1)==4); REQUIRE(c.eliminate_current()==4); REQUIRE(c.current()==3); REQUIRE(c.pass(5)==1); REQUIRE(c.clockwise()==std::vector<int>{1,2,3});""",
         "Maintain a logical circular turn order over a linear reciprocal chain, including direction reversal and deletion fallback.", "directional-circular-elimination"),
    Case("dll-delivery-route", "dll-route-segment-reverser", "RouteSegmentReverser", """
  bool append(int stop_id);
  bool reverse_segment(int first_id, int last_id);
  bool rotate_origin(int stop_id);
  bool erase(int stop_id);
  std::vector<int> route() const;
  std::vector<int> reverse_route() const;""", "", "", """
RouteSegmentReverser::~RouteSegmentReverser()=default;bool RouteSegmentReverser::append(int){return false;}bool RouteSegmentReverser::reverse_segment(int,int){return false;}bool RouteSegmentReverser::rotate_origin(int){return false;}bool RouteSegmentReverser::erase(int){return false;}std::vector<int> RouteSegmentReverser::route()const{return{};}std::vector<int> RouteSegmentReverser::reverse_route()const{return{};}""", """
bool RouteSegmentReverser::append(int id){if(id<=0||find(id))return false;insert_after(new Node{id,nullptr,nullptr},tail_);return true;}bool RouteSegmentReverser::reverse_segment(int first_id,int last_id){Node*f=find(first_id),*l=find(last_id);if(!f||!l)return false;bool ok=false;for(Node*n=f;n;n=n->next)if(n==l){ok=true;break;}if(!ok)return false;Node*before=f->prev,*after=l->next,*n=f;while(n!=after){Node*next=n->next;n->next=n->prev;n->prev=next;n=next;}if(before)before->next=l;else head_=l;l->prev=before;if(after)after->prev=f;else tail_=f;f->next=after;return true;}bool RouteSegmentReverser::rotate_origin(int id){Node*n=find(id);if(!n)return false;if(n==head_)return true;Node*old_head=head_,*prefix_tail=n->prev;prefix_tail->next=nullptr;n->prev=nullptr;tail_->next=old_head;old_head->prev=tail_;tail_=prefix_tail;head_=n;return true;}bool RouteSegmentReverser::erase(int id){Node*n=find(id);if(!n)return false;unlink(n);delete n;return true;}std::vector<int> RouteSegmentReverser::route()const{std::vector<int>v;for(Node*n=head_;n;n=n->next)v.push_back(n->id);return v;}std::vector<int> RouteSegmentReverser::reverse_route()const{std::vector<int>v;for(Node*n=tail_;n;n=n->prev)v.push_back(n->id);return v;}""", """
RouteSegmentReverser r; for(int id:{1,2,3,4})REQUIRE(r.append(id)); REQUIRE(r.reverse_segment(2,4)); REQUIRE(r.route()==std::vector<int>{1,4,3,2});""", """
RouteSegmentReverser r; for(int id:{1,2,3,4,5})REQUIRE(r.append(id)); REQUIRE_FALSE(r.reverse_segment(4,2)); REQUIRE(r.reverse_segment(2,4)); REQUIRE(r.rotate_origin(3)); REQUIRE(r.route()==std::vector<int>{3,2,5,1,4}); REQUIRE(r.reverse_route()==std::vector<int>{4,1,5,2,3}); REQUIRE(r.erase(3));""",
         "Reverse physical pointer direction inside a contiguous segment and rotate the route origin by relinking prefix and suffix.", "segment-pointer-reversal-and-origin-rotation"),
    Case("dll-elevator-stops", "dll-scan-elevator", "ScanElevator", """
  bool request(int floor);
  bool cancel(int floor);
  std::optional<int> serve_next();
  int current_floor() const;
  int direction() const;
  std::vector<int> pending_route() const;""", "int floor;", "int current_floor_ = 0; int direction_ = 1;", """
ScanElevator::~ScanElevator()=default;bool ScanElevator::request(int){return false;}bool ScanElevator::cancel(int){return false;}std::optional<int> ScanElevator::serve_next(){return std::nullopt;}int ScanElevator::current_floor()const{return 0;}int ScanElevator::direction()const{return 1;}std::vector<int> ScanElevator::pending_route()const{return{};}""", """
bool ScanElevator::request(int floor){if(floor<0||find(floor+1))return false;Node*before=head_;while(before&&before->floor<floor)before=before->next;Node*n=new Node{floor+1,nullptr,nullptr,floor};insert_before(n,before);return true;}bool ScanElevator::cancel(int floor){Node*n=find(floor+1);if(!n)return false;unlink(n);delete n;return true;}std::optional<int> ScanElevator::serve_next(){if(!head_)return std::nullopt;Node*n=nullptr;if(direction_>0){for(Node*p=head_;p;p=p->next)if(p->floor>=current_floor_){n=p;break;}}else{for(Node*p=tail_;p;p=p->prev)if(p->floor<=current_floor_){n=p;break;}}if(!n){direction_=-direction_;n=direction_>0?head_:tail_;}current_floor_=n->floor;int out=n->floor;unlink(n);delete n;return out;}int ScanElevator::current_floor()const{return current_floor_;}int ScanElevator::direction()const{return direction_;}std::vector<int> ScanElevator::pending_route()const{std::vector<int>v;if(direction_>0){for(Node*n=head_;n;n=n->next)if(n->floor>=current_floor_)v.push_back(n->floor);for(Node*n=tail_;n;n=n->prev)if(n->floor<current_floor_)v.push_back(n->floor);}else{for(Node*n=tail_;n;n=n->prev)if(n->floor<=current_floor_)v.push_back(n->floor);for(Node*n=head_;n;n=n->next)if(n->floor>current_floor_)v.push_back(n->floor);}return v;}""", """
ScanElevator e; REQUIRE(e.request(5)); REQUIRE(e.request(2)); REQUIRE(e.request(8)); REQUIRE(e.serve_next()==2); REQUIRE(e.serve_next()==5);""", """
ScanElevator e; REQUIRE_FALSE(e.request(-1)); for(int f:{4,1,7})REQUIRE(e.request(f)); REQUIRE(e.pending_route()==std::vector<int>{1,4,7}); REQUIRE(e.serve_next()==1); REQUIRE(e.serve_next()==4); REQUIRE(e.serve_next()==7); REQUIRE(e.request(3)); REQUIRE(e.serve_next()==3); REQUIRE(e.direction()==-1); REQUIRE_FALSE(e.cancel(99));""",
         "Keep a floor-sorted chain while executing a stateful SCAN traversal that flips direction only when no request lies ahead.", "sorted-scan-direction-state"),
    Case("dll-meeting-agenda", "dll-timed-agenda", "TimedAgenda", """
  bool add(int item_id, int minutes, int before_id);
  bool extend(int item_id, int delta);
  bool split(int item_id, int new_id, int first_minutes);
  bool move_before(int item_id, int before_id);
  int total_minutes() const;
  std::vector<int> order() const;""", "int minutes;", "", """
TimedAgenda::~TimedAgenda()=default;bool TimedAgenda::add(int,int,int){return false;}bool TimedAgenda::extend(int,int){return false;}bool TimedAgenda::split(int,int,int){return false;}bool TimedAgenda::move_before(int,int){return false;}int TimedAgenda::total_minutes()const{return 0;}std::vector<int> TimedAgenda::order()const{return{};}""", """
bool TimedAgenda::add(int id,int minutes,int before_id){if(id<=0||minutes<=0||find(id))return false;Node*b=before_id==0?nullptr:find(before_id);if(before_id!=0&&!b)return false;Node*n=new Node{id,nullptr,nullptr,minutes};insert_before(n,b);return true;}bool TimedAgenda::extend(int id,int delta){Node*n=find(id);if(!n||delta==0||(delta>0&&n->minutes>std::numeric_limits<int>::max()-delta)||n->minutes+delta<=0)return false;n->minutes+=delta;return true;}bool TimedAgenda::split(int id,int new_id,int first){Node*n=find(id);if(!n||new_id<=0||find(new_id)||first<=0||first>=n->minutes)return false;int rest=n->minutes-first;n->minutes=first;insert_after(new Node{new_id,nullptr,nullptr,rest},n);return true;}bool TimedAgenda::move_before(int id,int before_id){Node*n=find(id),*b=before_id==0?nullptr:find(before_id);if(!n||(before_id!=0&&!b)||n==b)return false;unlink(n);insert_before(n,b);return true;}int TimedAgenda::total_minutes()const{int total=0;for(Node*n=head_;n;n=n->next)total+=n->minutes;return total;}std::vector<int> TimedAgenda::order()const{std::vector<int>v;for(Node*n=head_;n;n=n->next)v.push_back(n->id);return v;}""", """
TimedAgenda a; REQUIRE(a.add(1,30,0)); REQUIRE(a.split(1,2,10)); REQUIRE(a.total_minutes()==30); REQUIRE(a.order()==std::vector<int>{1,2});""", """
TimedAgenda a; REQUIRE(a.add(1,20,0)); REQUIRE(a.add(2,15,0)); REQUIRE(a.add(3,5,2)); REQUIRE(a.split(2,4,7)); REQUIRE(a.extend(3,5)); REQUIRE_FALSE(a.extend(3,-10)); REQUIRE(a.move_before(4,1)); REQUIRE(a.order()==std::vector<int>{4,1,3,2}); REQUIRE(a.total_minutes()==45);""",
         "Maintain durations through overflow-safe extension, duration-preserving split, and position mutation.", "duration-split-and-overflow"),
    Case("dll-museum-tour", "dll-accessible-gallery-walk", "AccessibleGalleryWalk", """
  bool append(int gallery_id, bool accessible);
  bool set_accessible(int gallery_id, bool accessible);
  bool select(int gallery_id);
  std::optional<int> next_accessible();
  std::optional<int> previous_accessible();
  std::optional<int> current() const;
  std::vector<int> tour() const;""", "bool accessible;", "Node* current_ = nullptr;", """
AccessibleGalleryWalk::~AccessibleGalleryWalk()=default;bool AccessibleGalleryWalk::append(int,bool){return false;}bool AccessibleGalleryWalk::set_accessible(int,bool){return false;}bool AccessibleGalleryWalk::select(int){return false;}std::optional<int> AccessibleGalleryWalk::next_accessible(){return std::nullopt;}std::optional<int> AccessibleGalleryWalk::previous_accessible(){return std::nullopt;}std::optional<int> AccessibleGalleryWalk::current()const{return std::nullopt;}std::vector<int> AccessibleGalleryWalk::tour()const{return{};}""", """
bool AccessibleGalleryWalk::append(int id,bool accessible){if(id<=0||find(id))return false;insert_after(new Node{id,nullptr,nullptr,accessible},tail_);return true;}bool AccessibleGalleryWalk::set_accessible(int id,bool value){Node*n=find(id);if(!n)return false;n->accessible=value;return true;}bool AccessibleGalleryWalk::select(int id){Node*n=find(id);if(!n)return false;current_=n;return true;}std::optional<int> AccessibleGalleryWalk::next_accessible(){Node*n=current_?current_->next:head_;while(n&&!n->accessible)n=n->next;if(!n)return std::nullopt;current_=n;return n->id;}std::optional<int> AccessibleGalleryWalk::previous_accessible(){Node*n=current_?current_->prev:tail_;while(n&&!n->accessible)n=n->prev;if(!n)return std::nullopt;current_=n;return n->id;}std::optional<int> AccessibleGalleryWalk::current()const{return current_?std::optional<int>(current_->id):std::nullopt;}std::vector<int> AccessibleGalleryWalk::tour()const{std::vector<int>v;for(Node*n=head_;n;n=n->next)v.push_back(n->id);return v;}""", """
AccessibleGalleryWalk w; REQUIRE(w.append(1,true)); REQUIRE(w.append(2,false)); REQUIRE(w.append(3,true)); REQUIRE(w.next_accessible()==1); REQUIRE(w.next_accessible()==3);""", """
AccessibleGalleryWalk w; for(int id:{1,2,3,4})REQUIRE(w.append(id,id%2==0)); REQUIRE(w.next_accessible()==2); REQUIRE(w.set_accessible(2,false)); REQUIRE(w.next_accessible()==4); REQUIRE_FALSE(w.next_accessible()); REQUIRE_FALSE(w.previous_accessible()); REQUIRE(w.set_accessible(2,true)); REQUIRE(w.previous_accessible()==2); REQUIRE(w.current()==2);""",
         "Navigate a cursor across only currently accessible nodes while preserving the full editable tour order.", "filtered-bidirectional-cursor"),
    Case("dll-music-queue", "dll-fair-playback-queue", "FairPlaybackQueue", """
  bool enqueue(int track_id, int artist_id);
  bool postpone(int track_id);
  bool remove(int track_id);
  std::optional<int> play_next();
  std::vector<int> pending() const;""", "int artist;", "bool has_last_ = false; int last_artist_ = 0;", """
FairPlaybackQueue::~FairPlaybackQueue()=default;bool FairPlaybackQueue::enqueue(int,int){return false;}bool FairPlaybackQueue::postpone(int){return false;}bool FairPlaybackQueue::remove(int){return false;}std::optional<int> FairPlaybackQueue::play_next(){return std::nullopt;}std::vector<int> FairPlaybackQueue::pending()const{return{};}""", """
bool FairPlaybackQueue::enqueue(int id,int artist){if(id<=0||artist<=0||find(id))return false;insert_after(new Node{id,nullptr,nullptr,artist},tail_);return true;}bool FairPlaybackQueue::postpone(int id){Node*n=find(id);if(!n)return false;if(n==tail_)return true;unlink(n);insert_after(n,tail_);return true;}bool FairPlaybackQueue::remove(int id){Node*n=find(id);if(!n)return false;unlink(n);delete n;return true;}std::optional<int> FairPlaybackQueue::play_next(){if(!head_)return std::nullopt;Node*n=head_;if(has_last_){Node*p=head_;while(p&&p->artist==last_artist_)p=p->next;if(p)n=p;}int id=n->id;last_artist_=n->artist;has_last_=true;unlink(n);delete n;return id;}std::vector<int> FairPlaybackQueue::pending()const{std::vector<int>v;for(Node*n=head_;n;n=n->next)v.push_back(n->id);return v;}""", """
FairPlaybackQueue q; REQUIRE(q.enqueue(1,7)); REQUIRE(q.enqueue(2,7)); REQUIRE(q.enqueue(3,8)); REQUIRE(q.play_next()==1); REQUIRE(q.play_next()==3);""", """
FairPlaybackQueue q; REQUIRE_FALSE(q.enqueue(0,1)); REQUIRE(q.enqueue(1,1)); REQUIRE(q.enqueue(2,1)); REQUIRE(q.enqueue(3,2)); REQUIRE(q.enqueue(4,3)); REQUIRE(q.play_next()==1); REQUIRE(q.play_next()==3); REQUIRE(q.postpone(2)); REQUIRE(q.pending()==std::vector<int>{4,2}); REQUIRE(q.play_next()==4); REQUIRE(q.play_next()==2);""",
         "Choose the earliest nonrepeating artist when possible, otherwise head, with explicit postponement and deletion.", "fairness-scan-with-last-state"),
    Case("dll-notification-feed", "dll-pinned-unread-feed", "PinnedUnreadFeed", """
  bool publish(int notification_id, bool unread);
  bool pin(int notification_id, bool pinned);
  bool mark_read(int notification_id);
  bool dismiss(int notification_id);
  std::optional<int> next_unread(int after_id) const;
  std::vector<int> order() const;""", "bool unread; bool pinned;", "", """
PinnedUnreadFeed::~PinnedUnreadFeed()=default;bool PinnedUnreadFeed::publish(int,bool){return false;}bool PinnedUnreadFeed::pin(int,bool){return false;}bool PinnedUnreadFeed::mark_read(int){return false;}bool PinnedUnreadFeed::dismiss(int){return false;}std::optional<int> PinnedUnreadFeed::next_unread(int)const{return std::nullopt;}std::vector<int> PinnedUnreadFeed::order()const{return{};}""", """
bool PinnedUnreadFeed::publish(int id,bool unread){if(id<=0||find(id))return false;insert_after(new Node{id,nullptr,nullptr,unread,false},tail_);return true;}bool PinnedUnreadFeed::pin(int id,bool value){Node*n=find(id);if(!n)return false;if(n->pinned==value)return true;unlink(n);n->pinned=value;if(value){Node*last=nullptr;for(Node*p=head_;p&&p->pinned;p=p->next)last=p;insert_after(n,last);}else insert_after(n,tail_);return true;}bool PinnedUnreadFeed::mark_read(int id){Node*n=find(id);if(!n)return false;n->unread=false;return true;}bool PinnedUnreadFeed::dismiss(int id){Node*n=find(id);if(!n)return false;unlink(n);delete n;return true;}std::optional<int> PinnedUnreadFeed::next_unread(int after_id)const{Node*n=after_id==0?head_:find(after_id);if(after_id!=0){if(!n)return std::nullopt;n=n->next;}while(n&&!n->unread)n=n->next;return n?std::optional<int>(n->id):std::nullopt;}std::vector<int> PinnedUnreadFeed::order()const{std::vector<int>v;for(Node*n=head_;n;n=n->next)v.push_back(n->id);return v;}""", """
PinnedUnreadFeed f; REQUIRE(f.publish(1,true)); REQUIRE(f.publish(2,false)); REQUIRE(f.publish(3,true)); REQUIRE(f.pin(3,true)); REQUIRE(f.order()==std::vector<int>{3,1,2});""", """
PinnedUnreadFeed f; for(int id:{1,2,3,4})REQUIRE(f.publish(id,id%2==1)); REQUIRE(f.pin(3,true)); REQUIRE(f.pin(2,true)); REQUIRE(f.order()==std::vector<int>{3,2,1,4}); REQUIRE(f.pin(3,false)); REQUIRE(f.order()==std::vector<int>{2,1,4,3}); REQUIRE(f.next_unread(2)==1); REQUIRE(f.mark_read(1)); REQUIRE(f.next_unread(2)==3); REQUIRE(f.mark_read(3)); REQUIRE_FALSE(f.next_unread(2));""",
         "Maintain a stable pinned prefix independently from unread state and perform nonwrapping unread search.", "stable-partition-plus-unread-search"),
    Case("dll-parking-line", "dll-valet-neighbor-line", "ValetNeighborLine", """
  struct Departure { bool found; std::optional<int> before; std::optional<int> after; };
  bool arrive(int vehicle_id, int after_id);
  Departure depart(int vehicle_id);
  bool swap_with_next(int vehicle_id);
  std::pair<std::optional<int>, std::optional<int>> neighbors(int vehicle_id) const;
  std::vector<int> line() const;""", "", "", """
ValetNeighborLine::~ValetNeighborLine()=default;bool ValetNeighborLine::arrive(int,int){return false;}ValetNeighborLine::Departure ValetNeighborLine::depart(int){return{false,std::nullopt,std::nullopt};}bool ValetNeighborLine::swap_with_next(int){return false;}std::pair<std::optional<int>,std::optional<int>> ValetNeighborLine::neighbors(int)const{return{std::nullopt,std::nullopt};}std::vector<int> ValetNeighborLine::line()const{return{};}""", """
bool ValetNeighborLine::arrive(int id,int after_id){if(id<=0||find(id))return false;Node*a=after_id==0?tail_:find(after_id);if(after_id!=0&&!a)return false;insert_after(new Node{id,nullptr,nullptr},a);return true;}ValetNeighborLine::Departure ValetNeighborLine::depart(int id){Node*n=find(id);if(!n)return{false,std::nullopt,std::nullopt};Departure d{true,n->prev?std::optional<int>(n->prev->id):std::nullopt,n->next?std::optional<int>(n->next->id):std::nullopt};unlink(n);delete n;return d;}bool ValetNeighborLine::swap_with_next(int id){Node*a=find(id);if(!a||!a->next)return false;Node*b=a->next,*before=a->prev,*after=b->next;if(before)before->next=b;else head_=b;b->prev=before;b->next=a;a->prev=b;a->next=after;if(after)after->prev=a;else tail_=a;return true;}std::pair<std::optional<int>,std::optional<int>> ValetNeighborLine::neighbors(int id)const{Node*n=find(id);if(!n)return{std::nullopt,std::nullopt};return{n->prev?std::optional<int>(n->prev->id):std::nullopt,n->next?std::optional<int>(n->next->id):std::nullopt};}std::vector<int> ValetNeighborLine::line()const{std::vector<int>v;for(Node*n=head_;n;n=n->next)v.push_back(n->id);return v;}""", """
ValetNeighborLine l; REQUIRE(l.arrive(1,0)); REQUIRE(l.arrive(2,1)); REQUIRE(l.arrive(3,2)); auto d=l.depart(2); REQUIRE(d.found); REQUIRE(d.before==1); REQUIRE(d.after==3);""", """
ValetNeighborLine l; for(int id:{1,2,3,4})REQUIRE(l.arrive(id,id-1)); REQUIRE(l.swap_with_next(1)); REQUIRE(l.swap_with_next(3)); REQUIRE_FALSE(l.swap_with_next(3)); REQUIRE(l.line()==std::vector<int>{2,1,4,3}); auto d=l.depart(2); REQUIRE_FALSE(d.before); REQUIRE(d.after==1); REQUIRE(l.neighbors(4)==std::make_pair(std::optional<int>(1),std::optional<int>(3)));""",
         "Return neighbors captured before deletion and implement an exact adjacent-node transposition.", "neighbor-report-and-adjacent-transposition"),
    Case("dll-photo-carousel", "dll-selection-carousel", "SelectionCarousel", """
  bool insert(int photo_id, int after_id);
  bool select(int photo_id);
  std::optional<int> step(int delta);
  bool erase(int photo_id);
  std::optional<int> selected() const;
  std::vector<int> cycle() const;""", "", "Node* selected_ = nullptr;", """
SelectionCarousel::~SelectionCarousel()=default;bool SelectionCarousel::insert(int,int){return false;}bool SelectionCarousel::select(int){return false;}std::optional<int> SelectionCarousel::step(int){return std::nullopt;}bool SelectionCarousel::erase(int){return false;}std::optional<int> SelectionCarousel::selected()const{return std::nullopt;}std::vector<int> SelectionCarousel::cycle()const{return{};}""", """
bool SelectionCarousel::insert(int id,int after_id){if(id<=0||find(id))return false;Node*a=after_id==0?tail_:find(after_id);if(after_id!=0&&!a)return false;Node*n=new Node{id,nullptr,nullptr};insert_after(n,a);if(!selected_)selected_=n;return true;}bool SelectionCarousel::select(int id){Node*n=find(id);if(!n)return false;selected_=n;return true;}std::optional<int> SelectionCarousel::step(int delta){if(!selected_)return std::nullopt;int count=0;for(Node*n=head_;n;n=n->next)++count;if(count==0)return std::nullopt;int steps=delta%count;if(steps<0)steps+=count;while(steps-->0)selected_=selected_->next?selected_->next:head_;return selected_->id;}bool SelectionCarousel::erase(int id){Node*n=find(id);if(!n)return false;if(n==selected_)selected_=n->next?n->next:n->prev;unlink(n);delete n;return true;}std::optional<int> SelectionCarousel::selected()const{return selected_?std::optional<int>(selected_->id):std::nullopt;}std::vector<int> SelectionCarousel::cycle()const{std::vector<int>v;for(Node*n=head_;n;n=n->next)v.push_back(n->id);return v;}""", """
SelectionCarousel c; for(int id:{1,2,3})REQUIRE(c.insert(id,id-1)); REQUIRE(c.step(-1)==3); REQUIRE(c.erase(3)); REQUIRE(c.selected()==2);""", """
SelectionCarousel c; REQUIRE_FALSE(c.step(1)); for(int id:{1,2,3,4})REQUIRE(c.insert(id,id-1)); REQUIRE(c.select(2)); REQUIRE(c.step(6)==4); REQUIRE(c.step(-5)==3); REQUIRE(c.erase(3)); REQUIRE(c.selected()==4); REQUIRE(c.erase(4)); REQUIRE(c.selected()==2); REQUIRE(c.cycle()==std::vector<int>{1,2});""",
         "Apply signed modular selection movement and deterministic selected-node deletion fallback.", "signed-wrap-selection-fallback"),
    Case("dll-playlist-editor", "dll-crossfade-playlist", "CrossfadePlaylist", """
  bool append(int track_id, int duration_seconds);
  bool set_crossfade(int left_id, int right_id, int seconds);
  bool move_after(int track_id, int after_id);
  bool erase(int track_id);
  int play_time_seconds() const;
  std::vector<int> tracks() const;""", "int duration; int crossfade;", "", """
CrossfadePlaylist::~CrossfadePlaylist()=default;bool CrossfadePlaylist::append(int,int){return false;}bool CrossfadePlaylist::set_crossfade(int,int,int){return false;}bool CrossfadePlaylist::move_after(int,int){return false;}bool CrossfadePlaylist::erase(int){return false;}int CrossfadePlaylist::play_time_seconds()const{return 0;}std::vector<int> CrossfadePlaylist::tracks()const{return{};}""", """
bool CrossfadePlaylist::append(int id,int duration){if(id<=0||duration<=0||find(id)||play_time_seconds()>std::numeric_limits<int>::max()-duration)return false;insert_after(new Node{id,nullptr,nullptr,duration,0},tail_);return true;}bool CrossfadePlaylist::set_crossfade(int left_id,int right_id,int seconds){Node*l=find(left_id),*r=find(right_id);if(!l||!r||l->next!=r||seconds<0||seconds>=l->duration||seconds>=r->duration)return false;l->crossfade=seconds;return true;}bool CrossfadePlaylist::move_after(int id,int after_id){Node*n=find(id),*a=after_id==0?nullptr:find(after_id);if(!n||(after_id!=0&&!a)||n==a)return false;if(n->prev==a)return true;if(n->prev)n->prev->crossfade=0;n->crossfade=0;unlink(n);if(a)a->crossfade=0;insert_after(n,a);return true;}bool CrossfadePlaylist::erase(int id){Node*n=find(id);if(!n)return false;if(n->prev)n->prev->crossfade=0;unlink(n);delete n;return true;}int CrossfadePlaylist::play_time_seconds()const{int total=0;for(Node*n=head_;n;n=n->next){total+=n->duration;total-=n->crossfade;}return total;}std::vector<int> CrossfadePlaylist::tracks()const{std::vector<int>v;for(Node*n=head_;n;n=n->next)v.push_back(n->id);return v;}""", """
CrossfadePlaylist p; REQUIRE(p.append(1,100)); REQUIRE(p.append(2,80)); REQUIRE(p.append(3,60)); REQUIRE(p.set_crossfade(1,2,10)); REQUIRE(p.play_time_seconds()==230);""", """
CrossfadePlaylist p; for(int id:{1,2,3})REQUIRE(p.append(id,100)); REQUIRE_FALSE(p.set_crossfade(1,3,5)); REQUIRE(p.set_crossfade(1,2,5)); REQUIRE(p.set_crossfade(2,3,6)); REQUIRE(p.play_time_seconds()==289); REQUIRE(p.move_after(3,0)); REQUIRE(p.tracks()==std::vector<int>{3,1,2}); REQUIRE(p.play_time_seconds()==295); REQUIRE(p.erase(1)); REQUIRE(p.play_time_seconds()==200);""",
         "Bind overlap values to current adjacency, subtract valid crossfades from total duration, and clear broken-edge state on movement or deletion.", "adjacency-crossfade-accounting"),
    Case("dll-print-spooler", "dll-priority-spool", "PrioritySpool", """
  bool submit(int job_id, int priority);
  bool reprioritize(int job_id, int priority);
  bool cancel(int job_id);
  std::optional<int> serve();
  std::vector<int> queue() const;""", "int priority; unsigned long long age;", "unsigned long long next_age_ = 0;", """
PrioritySpool::~PrioritySpool()=default;bool PrioritySpool::submit(int,int){return false;}bool PrioritySpool::reprioritize(int,int){return false;}bool PrioritySpool::cancel(int){return false;}std::optional<int> PrioritySpool::serve(){return std::nullopt;}std::vector<int> PrioritySpool::queue()const{return{};}""", """
bool PrioritySpool::submit(int id,int priority){if(id<=0||priority<0||find(id)||next_age_==std::numeric_limits<unsigned long long>::max())return false;Node*n=new Node{id,nullptr,nullptr,priority,next_age_++};Node*b=head_;while(b&&(b->priority>priority||(b->priority==priority&&b->age<n->age)))b=b->next;insert_before(n,b);return true;}bool PrioritySpool::reprioritize(int id,int priority){Node*n=find(id);if(!n||priority<0||next_age_==std::numeric_limits<unsigned long long>::max())return false;unlink(n);n->priority=priority;n->age=next_age_++;Node*b=head_;while(b&&(b->priority>priority||(b->priority==priority&&b->age<n->age)))b=b->next;insert_before(n,b);return true;}bool PrioritySpool::cancel(int id){Node*n=find(id);if(!n)return false;unlink(n);delete n;return true;}std::optional<int> PrioritySpool::serve(){if(!head_)return std::nullopt;Node*n=head_;int id=n->id;unlink(n);delete n;return id;}std::vector<int> PrioritySpool::queue()const{std::vector<int>v;for(Node*n=head_;n;n=n->next)v.push_back(n->id);return v;}""", """
PrioritySpool s; REQUIRE(s.submit(1,2)); REQUIRE(s.submit(2,5)); REQUIRE(s.submit(3,5)); REQUIRE(s.queue()==std::vector<int>{2,3,1}); REQUIRE(s.serve()==2);""", """
PrioritySpool s; REQUIRE_FALSE(s.submit(1,-1)); REQUIRE(s.submit(1,1)); REQUIRE(s.submit(2,1)); REQUIRE(s.submit(3,2)); REQUIRE(s.reprioritize(1,2)); REQUIRE(s.queue()==std::vector<int>{3,1,2}); REQUIRE(s.reprioritize(3,1)); REQUIRE(s.queue()==std::vector<int>{1,2,3}); REQUIRE(s.cancel(2)); REQUIRE(s.serve()==1);""",
         "Maintain stable priority order with monotonic age and re-entry at the end of a tie group.", "stable-priority-reinsertion"),
    Case("dll-revision-timeline", "dll-revision-squash-ledger", "RevisionSquashLedger", """
  bool append(int revision_id, int author_id, int line_delta);
  bool amend(int revision_id, int line_delta);
  bool squash_with_next(int revision_id);
  bool erase(int revision_id);
  std::optional<int> delta(int revision_id) const;
  int net_lines() const;
  std::vector<int> revisions() const;""", "int author; int delta;", "", """
RevisionSquashLedger::~RevisionSquashLedger()=default;bool RevisionSquashLedger::append(int,int,int){return false;}bool RevisionSquashLedger::amend(int,int){return false;}bool RevisionSquashLedger::squash_with_next(int){return false;}bool RevisionSquashLedger::erase(int){return false;}std::optional<int> RevisionSquashLedger::delta(int)const{return std::nullopt;}int RevisionSquashLedger::net_lines()const{return 0;}std::vector<int> RevisionSquashLedger::revisions()const{return{};}""", """
bool RevisionSquashLedger::append(int id,int author,int line_delta){if(id<=0||author<=0||find(id))return false;long long total=static_cast<long long>(net_lines())+line_delta;if(total<std::numeric_limits<int>::min()||total>std::numeric_limits<int>::max())return false;insert_after(new Node{id,nullptr,nullptr,author,line_delta},tail_);return true;}bool RevisionSquashLedger::amend(int id,int line_delta){Node*n=find(id);if(!n)return false;long long total=static_cast<long long>(net_lines())-n->delta+line_delta;if(total<std::numeric_limits<int>::min()||total>std::numeric_limits<int>::max())return false;n->delta=line_delta;return true;}bool RevisionSquashLedger::squash_with_next(int id){Node*n=find(id);if(!n||!n->next||n->author!=n->next->author)return false;long long joined=static_cast<long long>(n->delta)+n->next->delta;if(joined<std::numeric_limits<int>::min()||joined>std::numeric_limits<int>::max())return false;Node*dead=n->next;n->delta=static_cast<int>(joined);unlink(dead);delete dead;return true;}bool RevisionSquashLedger::erase(int id){Node*n=find(id);if(!n)return false;long long remaining=static_cast<long long>(net_lines())-n->delta;if(remaining<std::numeric_limits<int>::min()||remaining>std::numeric_limits<int>::max())return false;unlink(n);delete n;return true;}std::optional<int> RevisionSquashLedger::delta(int id)const{Node*n=find(id);return n?std::optional<int>(n->delta):std::nullopt;}int RevisionSquashLedger::net_lines()const{int total=0;for(Node*n=head_;n;n=n->next)total+=n->delta;return total;}std::vector<int> RevisionSquashLedger::revisions()const{std::vector<int>v;for(Node*n=head_;n;n=n->next)v.push_back(n->id);return v;}""", """
RevisionSquashLedger l; REQUIRE(l.append(1,7,20)); REQUIRE(l.append(2,7,-5)); REQUIRE(l.squash_with_next(1)); REQUIRE(l.delta(1)==15); REQUIRE(l.revisions()==std::vector<int>{1});""", """
RevisionSquashLedger l; REQUIRE_FALSE(l.append(0,1,2)); REQUIRE(l.append(1,1,10)); REQUIRE(l.append(2,2,-4)); REQUIRE(l.append(3,2,6)); REQUIRE_FALSE(l.squash_with_next(1)); REQUIRE(l.squash_with_next(2)); REQUIRE(l.delta(2)==2); REQUIRE(l.amend(1,20)); REQUIRE(l.net_lines()==22); REQUIRE(l.erase(2)); REQUIRE(l.net_lines()==20); REQUIRE(l.revisions()==std::vector<int>{1});""",
         "Store author and signed line deltas, squash only same-author adjacent revisions, and reject every overflowing aggregate atomically.", "author-aware-squash-and-delta-accounting"),
    Case("dll-round-robin-scheduler", "dll-budget-round-robin", "BudgetRoundRobin", """
  bool add(int job_id, int budget);
  bool add_budget(int job_id, int amount);
  std::optional<int> run_slice(int units);
  bool cancel(int job_id);
  std::optional<int> current() const;
  std::vector<std::pair<int,int>> budgets() const;""", "int budget;", "", """
BudgetRoundRobin::~BudgetRoundRobin()=default;bool BudgetRoundRobin::add(int,int){return false;}bool BudgetRoundRobin::add_budget(int,int){return false;}std::optional<int> BudgetRoundRobin::run_slice(int){return std::nullopt;}bool BudgetRoundRobin::cancel(int){return false;}std::optional<int> BudgetRoundRobin::current()const{return std::nullopt;}std::vector<std::pair<int,int>> BudgetRoundRobin::budgets()const{return{};}""", """
bool BudgetRoundRobin::add(int id,int budget){if(id<=0||budget<=0||find(id))return false;insert_after(new Node{id,nullptr,nullptr,budget},tail_);return true;}bool BudgetRoundRobin::add_budget(int id,int amount){Node*n=find(id);if(!n||amount<=0||n->budget>std::numeric_limits<int>::max()-amount)return false;n->budget+=amount;return true;}std::optional<int> BudgetRoundRobin::run_slice(int units){if(!head_||units<=0)return std::nullopt;Node*n=head_;int id=n->id;if(units>=n->budget){unlink(n);delete n;}else{n->budget-=units;unlink(n);insert_after(n,tail_);}return id;}bool BudgetRoundRobin::cancel(int id){Node*n=find(id);if(!n)return false;unlink(n);delete n;return true;}std::optional<int> BudgetRoundRobin::current()const{return head_?std::optional<int>(head_->id):std::nullopt;}std::vector<std::pair<int,int>> BudgetRoundRobin::budgets()const{std::vector<std::pair<int,int>>v;for(Node*n=head_;n;n=n->next)v.push_back({n->id,n->budget});return v;}""", """
BudgetRoundRobin r; REQUIRE(r.add(1,5)); REQUIRE(r.add(2,2)); REQUIRE(r.run_slice(3)==1); REQUIRE(r.budgets()==std::vector<std::pair<int,int>>{{2,2},{1,2}});""", """
BudgetRoundRobin r; REQUIRE_FALSE(r.add(1,0)); REQUIRE(r.add(1,5)); REQUIRE(r.add(2,3)); REQUIRE(r.add(3,7)); REQUIRE(r.run_slice(2)==1); REQUIRE(r.run_slice(3)==2); REQUIRE(r.budgets()==std::vector<std::pair<int,int>>{{3,7},{1,3}}); REQUIRE(r.add_budget(1,4)); REQUIRE(r.run_slice(8)==3); REQUIRE(r.current()==1); REQUIRE(r.cancel(1)); REQUIRE_FALSE(r.current());""",
         "Consume per-node budgets, delete exhausted jobs, and rotate surviving jobs after each slice.", "budget-consumption-and-rotation"),
    Case("dll-support-tickets", "dll-escalation-desk", "EscalationDesk", """
  bool open(int ticket_id, int severity);
  bool escalate(int ticket_id, int delta);
  bool deescalate(int ticket_id, int delta);
  bool resolve(int ticket_id);
  std::optional<int> focus_at_least(int severity) const;
  std::vector<int> queue() const;""", "int severity; unsigned long long age;", "unsigned long long next_age_ = 0;", """
EscalationDesk::~EscalationDesk()=default;bool EscalationDesk::open(int,int){return false;}bool EscalationDesk::escalate(int,int){return false;}bool EscalationDesk::deescalate(int,int){return false;}bool EscalationDesk::resolve(int){return false;}std::optional<int> EscalationDesk::focus_at_least(int)const{return std::nullopt;}std::vector<int> EscalationDesk::queue()const{return{};}""", """
bool EscalationDesk::open(int id,int severity){if(id<=0||severity<0||find(id))return false;Node*n=new Node{id,nullptr,nullptr,severity,next_age_++};Node*b=head_;while(b&&(b->severity>severity||(b->severity==severity&&b->age<n->age)))b=b->next;insert_before(n,b);return true;}bool EscalationDesk::escalate(int id,int delta){Node*n=find(id);if(!n||delta<=0||n->severity>std::numeric_limits<int>::max()-delta)return false;int value=n->severity+delta;unlink(n);n->severity=value;n->age=next_age_++;Node*b=head_;while(b&&(b->severity>value||(b->severity==value&&b->age<n->age)))b=b->next;insert_before(n,b);return true;}bool EscalationDesk::deescalate(int id,int delta){Node*n=find(id);if(!n||delta<=0||delta>n->severity)return false;int value=n->severity-delta;unlink(n);n->severity=value;n->age=next_age_++;Node*b=head_;while(b&&(b->severity>value||(b->severity==value&&b->age<n->age)))b=b->next;insert_before(n,b);return true;}bool EscalationDesk::resolve(int id){Node*n=find(id);if(!n)return false;unlink(n);delete n;return true;}std::optional<int> EscalationDesk::focus_at_least(int severity)const{for(Node*n=head_;n;n=n->next)if(n->severity>=severity)return n->id;return std::nullopt;}std::vector<int> EscalationDesk::queue()const{std::vector<int>v;for(Node*n=head_;n;n=n->next)v.push_back(n->id);return v;}""", """
EscalationDesk d; REQUIRE(d.open(1,2)); REQUIRE(d.open(2,5)); REQUIRE(d.escalate(1,4)); REQUIRE(d.queue()==std::vector<int>{1,2});""", """
EscalationDesk d; for(auto p:std::vector<std::pair<int,int>>{{1,3},{2,3},{3,1}})REQUIRE(d.open(p.first,p.second)); REQUIRE(d.escalate(3,2)); REQUIRE(d.queue()==std::vector<int>{1,2,3}); REQUIRE(d.deescalate(1,3)); REQUIRE(d.queue()==std::vector<int>{2,3,1}); REQUIRE(d.focus_at_least(3)==2); REQUIRE(d.resolve(2)); REQUIRE(d.focus_at_least(3)==3);""",
         "Reposition tickets after checked severity transitions while preserving stable tie order and nonmutating focus queries.", "severity-transition-stable-order"),
    Case("dll-tab-strip", "dll-tab-strip", "TabStrip", """
  bool open(int tab_id, int after_id);
  bool activate(int tab_id);
  bool move_before(int tab_id, int before_id);
  bool close(int tab_id);
  std::optional<int> active() const;
  std::vector<int> tabs() const;""", "", "Node* active_ = nullptr;", """
TabStrip::~TabStrip()=default;bool TabStrip::open(int,int){return false;}bool TabStrip::activate(int){return false;}bool TabStrip::move_before(int,int){return false;}bool TabStrip::close(int){return false;}std::optional<int> TabStrip::active()const{return std::nullopt;}std::vector<int> TabStrip::tabs()const{return{};}""", """
bool TabStrip::open(int id,int after_id){if(id<=0||find(id))return false;Node*a=after_id==0?tail_:find(after_id);if(after_id!=0&&!a)return false;Node*n=new Node{id,nullptr,nullptr};insert_after(n,a);if(!active_)active_=n;return true;}bool TabStrip::activate(int id){Node*n=find(id);if(!n)return false;active_=n;return true;}bool TabStrip::move_before(int id,int before_id){Node*n=find(id),*b=before_id==0?nullptr:find(before_id);if(!n||(before_id!=0&&!b)||n==b)return false;unlink(n);insert_before(n,b);return true;}bool TabStrip::close(int id){Node*n=find(id);if(!n)return false;if(n==active_)active_=n->next?n->next:n->prev;unlink(n);delete n;return true;}std::optional<int> TabStrip::active()const{return active_?std::optional<int>(active_->id):std::nullopt;}std::vector<int> TabStrip::tabs()const{std::vector<int>v;for(Node*n=head_;n;n=n->next)v.push_back(n->id);return v;}""", """
TabStrip t; REQUIRE(t.open(1,0)); REQUIRE(t.open(2,1)); REQUIRE(t.activate(1)); REQUIRE(t.close(1)); REQUIRE(t.active()==2);""", """
TabStrip t; for(int id:{1,2,3,4})REQUIRE(t.open(id,id-1)); REQUIRE(t.activate(2)); REQUIRE(t.move_before(4,1)); REQUIRE(t.tabs()==std::vector<int>{4,1,2,3}); REQUIRE(t.active()==2); REQUIRE(t.close(2)); REQUIRE(t.active()==3); REQUIRE(t.close(3)); REQUIRE(t.active()==1);""",
         "Preserve an activation pointer across order changes and apply right-then-left fallback when the active tab closes.", "active-pointer-close-fallback"),
    Case("dll-text-line-cursor", "dll-line-gap-editor", "LineGapEditor", """
  bool append(int line_id, std::string text);
  bool place_cursor(int line_id);
  bool insert_after_cursor(int line_id, std::string text);
  bool split_cursor(int new_line_id, std::size_t column);
  bool merge_next();
  bool erase_cursor();
  std::optional<int> cursor() const;
  std::vector<std::string> lines() const;""", "std::string text;", "Node* cursor_ = nullptr;", """
LineGapEditor::~LineGapEditor()=default;bool LineGapEditor::append(int,std::string){return false;}bool LineGapEditor::place_cursor(int){return false;}bool LineGapEditor::insert_after_cursor(int,std::string){return false;}bool LineGapEditor::split_cursor(int,std::size_t){return false;}bool LineGapEditor::merge_next(){return false;}bool LineGapEditor::erase_cursor(){return false;}std::optional<int> LineGapEditor::cursor()const{return std::nullopt;}std::vector<std::string> LineGapEditor::lines()const{return{};}""", """
bool LineGapEditor::append(int id,std::string text){if(id<=0||find(id))return false;Node*n=new Node{id,nullptr,nullptr,std::move(text)};insert_after(n,tail_);if(!cursor_)cursor_=n;return true;}bool LineGapEditor::place_cursor(int id){Node*n=find(id);if(!n)return false;cursor_=n;return true;}bool LineGapEditor::insert_after_cursor(int id,std::string text){if(!cursor_||id<=0||find(id))return false;insert_after(new Node{id,nullptr,nullptr,std::move(text)},cursor_);return true;}bool LineGapEditor::split_cursor(int new_id,std::size_t column){if(!cursor_||new_id<=0||find(new_id)||column>cursor_->text.size())return false;std::string suffix=cursor_->text.substr(column);cursor_->text.erase(column);insert_after(new Node{new_id,nullptr,nullptr,std::move(suffix)},cursor_);return true;}bool LineGapEditor::merge_next(){if(!cursor_||!cursor_->next)return false;Node*n=cursor_->next;cursor_->text+=n->text;unlink(n);delete n;return true;}bool LineGapEditor::erase_cursor(){if(!cursor_)return false;Node*n=cursor_;cursor_=n->next?n->next:n->prev;unlink(n);delete n;return true;}std::optional<int> LineGapEditor::cursor()const{return cursor_?std::optional<int>(cursor_->id):std::nullopt;}std::vector<std::string> LineGapEditor::lines()const{std::vector<std::string>v;for(Node*n=head_;n;n=n->next)v.push_back(n->text);return v;}""", """
LineGapEditor e; REQUIRE(e.append(1,"abcd")); REQUIRE(e.split_cursor(2,2)); REQUIRE(e.lines()==std::vector<std::string>{"ab","cd"}); REQUIRE(e.merge_next()); REQUIRE(e.lines()==std::vector<std::string>{"abcd"});""", """
LineGapEditor e; REQUIRE_FALSE(e.erase_cursor()); REQUIRE(e.append(1,"alpha")); REQUIRE(e.append(2,"beta")); REQUIRE(e.place_cursor(1)); REQUIRE(e.insert_after_cursor(3,"mid")); REQUIRE(e.split_cursor(4,2)); REQUIRE(e.lines()==std::vector<std::string>{"al","pha","mid","beta"}); REQUIRE(e.merge_next()); REQUIRE(e.lines()==std::vector<std::string>{"alpha","mid","beta"}); REQUIRE(e.erase_cursor()); REQUIRE(e.cursor()==3);""",
         "Edit text payloads through cursor-local insertion, split, merge, and deterministic cursor fallback.", "payload-split-merge-cursor"),
    Case("dll-train-consist", "dll-consist-block-coupler", "ConsistBlockCoupler", """
  bool attach(int car_id, int after_id);
  std::vector<int> detach_block(int first_id, int last_id);
  bool couple_after(int after_id, const std::vector<int>& cars);
  bool reverse_block(int first_id, int last_id);
  std::vector<int> consist() const;""", "", "", """
ConsistBlockCoupler::~ConsistBlockCoupler()=default;bool ConsistBlockCoupler::attach(int,int){return false;}std::vector<int> ConsistBlockCoupler::detach_block(int,int){return{};}bool ConsistBlockCoupler::couple_after(int,const std::vector<int>&){return false;}bool ConsistBlockCoupler::reverse_block(int,int){return false;}std::vector<int> ConsistBlockCoupler::consist()const{return{};}""", """
bool ConsistBlockCoupler::attach(int id,int after_id){if(id<=0||find(id))return false;Node*a=after_id==0?tail_:find(after_id);if(after_id!=0&&!a)return false;insert_after(new Node{id,nullptr,nullptr},a);return true;}std::vector<int> ConsistBlockCoupler::detach_block(int first_id,int last_id){Node*f=find(first_id),*l=find(last_id);std::vector<int>out;if(!f||!l)return out;bool ok=false;for(Node*n=f;n;n=n->next){out.push_back(n->id);if(n==l){ok=true;break;}}if(!ok)return{};Node*before=f->prev,*after=l->next;if(before)before->next=after;else head_=after;if(after)after->prev=before;else tail_=before;Node*n=f;while(n!=after){Node*next=n->next;delete n;n=next;}return out;}bool ConsistBlockCoupler::couple_after(int after_id,const std::vector<int>&cars){Node*a=after_id==0?tail_:find(after_id);if((after_id!=0&&!a)||cars.empty())return false;for(std::size_t i=0;i<cars.size();++i){if(cars[i]<=0||find(cars[i]))return false;for(std::size_t j=0;j<i;++j)if(cars[j]==cars[i])return false;}for(int id:cars){Node*n=new Node{id,nullptr,nullptr};insert_after(n,a);a=n;}return true;}bool ConsistBlockCoupler::reverse_block(int first_id,int last_id){Node*f=find(first_id),*l=find(last_id);if(!f||!l)return false;bool ok=false;for(Node*n=f;n;n=n->next)if(n==l){ok=true;break;}if(!ok)return false;Node*before=f->prev,*after=l->next,*n=f;while(n!=after){Node*next=n->next;n->next=n->prev;n->prev=next;n=next;}if(before)before->next=l;else head_=l;l->prev=before;if(after)after->prev=f;else tail_=f;f->next=after;return true;}std::vector<int> ConsistBlockCoupler::consist()const{std::vector<int>v;for(Node*n=head_;n;n=n->next)v.push_back(n->id);return v;}""", """
ConsistBlockCoupler c; REQUIRE(c.couple_after(0,{1,2,3})); REQUIRE(c.detach_block(2,3)==std::vector<int>{2,3}); REQUIRE(c.consist()==std::vector<int>{1});""", """
ConsistBlockCoupler c; REQUIRE_FALSE(c.couple_after(0,{})); REQUIRE(c.couple_after(0,{1,2,3,4})); REQUIRE_FALSE(c.couple_after(4,{5,5})); REQUIRE(c.reverse_block(2,4)); REQUIRE(c.consist()==std::vector<int>{1,4,3,2}); REQUIRE(c.detach_block(4,3)==std::vector<int>{4,3}); REQUIRE(c.couple_after(1,{8,9})); REQUIRE(c.consist()==std::vector<int>{1,8,9,2});""",
         "Validate and atomically materialize new blocks, detach inclusive blocks, and reverse a block through pointer relinking.", "block-detach-couple-reverse"),
    Case("dll-warehouse-picks", "dll-precedence-pick-chain", "PrecedencePickChain", """
  bool add_pick(int pick_id, int must_follow_id);
  bool move_after(int pick_id, int after_id);
  bool complete(int pick_id);
  std::optional<int> prerequisite(int pick_id) const;
  std::vector<int> order() const;""", "int must_follow;", "", """
PrecedencePickChain::~PrecedencePickChain()=default;bool PrecedencePickChain::add_pick(int,int){return false;}bool PrecedencePickChain::move_after(int,int){return false;}bool PrecedencePickChain::complete(int){return false;}std::optional<int> PrecedencePickChain::prerequisite(int)const{return std::nullopt;}std::vector<int> PrecedencePickChain::order()const{return{};}""", """
bool PrecedencePickChain::add_pick(int id,int must_follow){if(id<=0||find(id)||(must_follow!=0&&!find(must_follow)))return false;Node*n=new Node{id,nullptr,nullptr,must_follow};insert_after(n,tail_);return true;}bool PrecedencePickChain::move_after(int id,int after_id){Node*n=find(id),*a=after_id==0?nullptr:find(after_id);if(!n||(after_id!=0&&!a)||n==a)return false;Node*old=n->prev;unlink(n);insert_after(n,a);bool valid=true;for(Node*p=head_;p&&valid;p=p->next)if(p->must_follow!=0){Node*q=find(p->must_follow);bool seen=false;for(Node*x=head_;x&&x!=p;x=x->next)if(x==q){seen=true;break;}if(!seen)valid=false;}if(valid)return true;unlink(n);insert_after(n,old);return false;}bool PrecedencePickChain::complete(int id){Node*n=find(id);if(!n)return false;for(Node*p=head_;p;p=p->next)if(p->must_follow==id)return false;unlink(n);delete n;return true;}std::optional<int> PrecedencePickChain::prerequisite(int id)const{Node*n=find(id);if(!n)return std::nullopt;return n->must_follow==0?std::optional<int>(0):std::optional<int>(n->must_follow);}std::vector<int> PrecedencePickChain::order()const{std::vector<int>v;for(Node*n=head_;n;n=n->next)v.push_back(n->id);return v;}""", """
PrecedencePickChain p; REQUIRE(p.add_pick(1,0)); REQUIRE(p.add_pick(2,1)); REQUIRE(p.add_pick(3,1)); REQUIRE_FALSE(p.move_after(1,3)); REQUIRE(p.order()==std::vector<int>{1,2,3});""", """
PrecedencePickChain p; REQUIRE_FALSE(p.add_pick(2,1)); REQUIRE(p.add_pick(1,0)); REQUIRE(p.add_pick(2,1)); REQUIRE(p.add_pick(3,1)); REQUIRE(p.add_pick(4,2)); REQUIRE(p.move_after(3,2)); REQUIRE_FALSE(p.move_after(2,4)); REQUIRE_FALSE(p.complete(1)); REQUIRE_FALSE(p.complete(2)); REQUIRE(p.complete(4)); REQUIRE(p.complete(2)); REQUIRE(p.prerequisite(3)==1); REQUIRE(p.order()==std::vector<int>{1,3});""",
         "Store explicit prerequisites, reject order mutations that invert dependencies, and block completion while dependents remain.", "dependency-constrained-relinking"),
)


assert len(CASES) == 20
assert len({case.task_id for case in CASES}) == 20
assert len({case.logic_tag for case in CASES}) == 20
