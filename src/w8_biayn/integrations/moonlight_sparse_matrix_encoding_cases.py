"""Distinct C++17 cases for sparse-matrix-encoding family remediation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SparseCase:
    legacy_id: str
    task_id: str
    title: str
    objective: str
    public_api: str
    profile: str
    marker: str
    instructions: str
    header: str
    reference: str
    visible_test: str
    hidden_test: str
    negative_old: str
    negative_new: str
    negative_reason: str
    disposition: str = "replace"


def _header(declarations: str, includes: str = "<vector>") -> str:
    return f"""#pragma once
#include {includes}
namespace curriculum {{
{declarations}
}}  // namespace curriculum
"""


def _source(body: str, extra: str = "") -> str:
    return f"""#include \"task.h\"
{extra}
namespace curriculum {{
{body}
}}  // namespace curriculum
"""


def _test(body: str, extra: str = "") -> str:
    return f"""#include \"task.h\"
{extra}
int main() {{
  int failures = 0;
  const auto check = [&](bool value) {{ if (!value) ++failures; }};
{body}
  return failures == 0 ? 0 : 1;
}}
"""


CASES = (
    SparseCase(
        legacy_id="sparse-constellation",
        task_id="sparse-constellation",
        title="Constellation sparse bounds",
        objective="Validate unique star coordinates and compute the exact occupied bounding box without constructing a dense sky grid.",
        public_api="ConstellationBounds locate_constellation(int rows, int columns, const std::vector<Star>& stars)",
        profile="coordinate-set validation plus one-pass sparse bounding-box reduction",
        marker="sparse_bounding_box",
        disposition="repair-in-place",
        instructions="""Implement `locate_constellation`. Dimensions must be positive. Every star must be in range and coordinates must be unique; invalid input returns `valid=false` and an otherwise empty result. An empty valid constellation has `empty=true` and all bounds at `-1`. Otherwise return the star count and inclusive minimum/maximum row and column. Do not allocate a dense `rows * columns` grid.""",
        header=_header("""struct Star { int row; int column; };
struct ConstellationBounds { bool valid=false; bool empty=true; int count=0; int min_row=-1; int max_row=-1; int min_column=-1; int max_column=-1; };
ConstellationBounds locate_constellation(int rows, int columns, const std::vector<Star>& stars);"""),
        reference=_source(
            """ConstellationBounds locate_constellation(int rows, int columns, const std::vector<Star>& stars) {
  ConstellationBounds out;
  if (rows <= 0 || columns <= 0) return out;
  std::set<std::pair<int,int>> sparse_bounding_box;
  for (const auto& star : stars) {
    if (star.row < 0 || star.row >= rows || star.column < 0 || star.column >= columns ||
        !sparse_bounding_box.insert({star.row, star.column}).second) return out;
  }
  out.valid = true;
  if (stars.empty()) return out;
  out.empty = false; out.count = static_cast<int>(stars.size());
  out.min_row = out.max_row = stars.front().row;
  out.min_column = out.max_column = stars.front().column;
  for (const auto& star : stars) {
    out.min_row = std::min(out.min_row, star.row); out.max_row = std::max(out.max_row, star.row);
    out.min_column = std::min(out.min_column, star.column); out.max_column = std::max(out.max_column, star.column);
  }
  return out;
}""",
            "#include <algorithm>\n#include <set>\n#include <utility>",
        ),
        visible_test=_test("""  const auto result = curriculum::locate_constellation(8, 9, {{6,1},{2,7},{4,3}});
  check(result.valid && !result.empty && result.count == 3);
  check(result.min_row == 2 && result.max_row == 6 && result.min_column == 1 && result.max_column == 7);"""),
        hidden_test=_test("""  const auto empty = curriculum::locate_constellation(2, 3, {});
  check(empty.valid && empty.empty && empty.min_row == -1);
  check(!curriculum::locate_constellation(0, 3, {}).valid);
  check(!curriculum::locate_constellation(2, 3, {{1,2},{1,2}}).valid);
  const auto edge = curriculum::locate_constellation(2, 3, {{0,2},{1,0}});
  check(edge.valid && edge.min_column == 0 && edge.max_column == 2);"""),
        negative_old="out.min_column = std::min(out.min_column, star.column);",
        negative_new="out.min_column = std::max(out.min_column, star.column);",
        negative_reason="tracks the wrong horizontal bound",
    ),
    SparseCase(
        legacy_id="sparse-power-outages",
        task_id="outage-component-index",
        title="Outage component index",
        objective="Find four-neighbor connected outage components directly over sparse coordinates.",
        public_api="OutageSummary index_outages(int rows, int columns, const std::vector<OutageCell>& cells)",
        profile="sparse coordinate hash plus disjoint-set component union",
        marker="disjoint_parent",
        instructions="""Implement `index_outages`. Positive dimensions and unique in-range outage cells are required. Join cells sharing a vertical or horizontal edge. Return component count, largest component size, and component sizes sorted descending. Empty input is valid. Do not scan or allocate the dense grid.""",
        header=_header("""struct OutageCell { int row; int column; };
struct OutageSummary { bool valid=false; int components=0; int largest=0; std::vector<int> sizes; };
OutageSummary index_outages(int rows, int columns, const std::vector<OutageCell>& cells);"""),
        reference=_source(
            """OutageSummary index_outages(int rows, int columns, const std::vector<OutageCell>& cells) {
  OutageSummary out; if (rows <= 0 || columns <= 0) return out;
  std::map<std::pair<int,int>,int> ids;
  for (int i=0;i<static_cast<int>(cells.size());++i) {
    const auto& c=cells[static_cast<std::size_t>(i)];
    if(c.row<0||c.row>=rows||c.column<0||c.column>=columns||!ids.emplace(std::make_pair(c.row,c.column),i).second)return out;
  }
  std::vector<int> disjoint_parent(cells.size()), weight(cells.size(),1);
  std::iota(disjoint_parent.begin(),disjoint_parent.end(),0);
  const auto find=[&](int value){ while(disjoint_parent[static_cast<std::size_t>(value)]!=value){ disjoint_parent[static_cast<std::size_t>(value)]=disjoint_parent[static_cast<std::size_t>(disjoint_parent[static_cast<std::size_t>(value)])]; value=disjoint_parent[static_cast<std::size_t>(value)]; } return value; };
  const int dr[4]={-1,1,0,0}; const int dc[4]={0,0,-1,1};
  for(int i=0;i<static_cast<int>(cells.size());++i) for(int d=0;d<4;++d){ auto it=ids.find({cells[static_cast<std::size_t>(i)].row+dr[d],cells[static_cast<std::size_t>(i)].column+dc[d]}); if(it!=ids.end()){ int a=find(i),b=find(it->second); if(a!=b){disjoint_parent[static_cast<std::size_t>(b)]=a;weight[static_cast<std::size_t>(a)]+=weight[static_cast<std::size_t>(b)];}}}
  std::map<int,int> totals; for(int i=0;i<static_cast<int>(cells.size());++i)++totals[find(i)];
  for(const auto& item:totals)out.sizes.push_back(item.second);
  std::sort(out.sizes.begin(),out.sizes.end(),std::greater<int>()); out.valid=true; out.components=static_cast<int>(out.sizes.size()); if(!out.sizes.empty())out.largest=out.sizes.front(); return out;
}""",
            "#include <algorithm>\n#include <functional>\n#include <map>\n#include <numeric>\n#include <utility>",
        ),
        visible_test=_test("""  const auto s=curriculum::index_outages(5,5,{{0,0},{0,1},{3,3},{4,3},{2,0}});
  check(s.valid && s.components==3 && s.largest==2);
  check(s.sizes==std::vector<int>({2,2,1}));"""),
        hidden_test=_test("""  check(curriculum::index_outages(2,2,{}).valid);
  check(!curriculum::index_outages(2,2,{{0,0},{0,0}}).valid);
  const auto chain=curriculum::index_outages(4,1,{{0,0},{1,0},{2,0},{3,0}});
  check(chain.valid && chain.components==1 && chain.largest==4);
  check(!curriculum::index_outages(2,2,{{2,0}}).valid);"""),
        negative_old="const int dr[4]={-1,1,0,0}; const int dc[4]={0,0,-1,1};",
        negative_new="const int dr[4]={0,0,0,0}; const int dc[4]={0,0,-1,1};",
        negative_reason="drops vertical component adjacency",
    ),
    SparseCase(
        legacy_id="sparse-farm-irrigation",
        task_id="irrigation-gap-ledger",
        title="Irrigation gap ledger",
        objective="Merge sparse watered intervals and report uncovered column intervals.",
        public_api="GapLedger irrigation_gaps(int columns, const std::vector<WaterSpan>& spans)",
        profile="sorted interval union followed by complement emission",
        marker="merged_water",
        instructions="""Implement `irrigation_gaps` for one field row. `columns` must be nonnegative. Water spans are inclusive, in range, and may overlap or touch. Merge their union and return maximal inclusive dry gaps from left to right plus the number of dry cells. Invalid spans return `valid=false` without partial output.""",
        header=_header("""struct WaterSpan { int first; int last; bool operator==(const WaterSpan&o)const{return first==o.first&&last==o.last;} };
struct GapLedger { bool valid=false; int dry_cells=0; std::vector<WaterSpan> gaps; };
GapLedger irrigation_gaps(int columns, const std::vector<WaterSpan>& spans);"""),
        reference=_source(
            """GapLedger irrigation_gaps(int columns, const std::vector<WaterSpan>& spans) {
  GapLedger out; if(columns<0)return out; std::vector<WaterSpan> merged_water=spans;
  for(const auto& s:merged_water)if(s.first<0||s.last<s.first||s.last>=columns)return out;
  std::sort(merged_water.begin(),merged_water.end(),[](const auto&a,const auto&b){return a.first!=b.first?a.first<b.first:a.last<b.last;});
  std::vector<WaterSpan> united; for(const auto&s:merged_water){if(united.empty()||s.first>united.back().last+1)united.push_back(s);else united.back().last=std::max(united.back().last,s.last);}
  int cursor=0; for(const auto&s:united){if(cursor<s.first)out.gaps.push_back({cursor,s.first-1});cursor=s.last+1;} if(cursor<columns)out.gaps.push_back({cursor,columns-1});
  for(const auto&g:out.gaps){out.dry_cells+=g.last-g.first+1;} out.valid=true; return out;
}""",
            "#include <algorithm>",
        ),
        visible_test=_test("""  const auto g=curriculum::irrigation_gaps(10,{{1,2},{5,7},{2,4}});
  check(g.valid && g.dry_cells==3);
  check(g.gaps==std::vector<curriculum::WaterSpan>({{0,0},{8,9}}));"""),
        hidden_test=_test("""  const auto all=curriculum::irrigation_gaps(4,{{0,3}}); check(all.valid&&all.gaps.empty());
  const auto none=curriculum::irrigation_gaps(3,{}); check(none.valid&&none.dry_cells==3&&none.gaps.size()==1);
  const auto touching=curriculum::irrigation_gaps(5,{{0,1},{2,3}}); check(touching.valid&&touching.gaps==std::vector<curriculum::WaterSpan>({{4,4}}));
  check(!curriculum::irrigation_gaps(4,{{3,2}}).valid);"""),
        negative_old="cursor=s.last+1;",
        negative_new="cursor=s.last;",
        negative_reason="starts a dry complement at an already watered endpoint",
    ),
    SparseCase(
        legacy_id="sparse-library-shelves",
        task_id="shelf-free-run-index",
        title="Shelf free-run index",
        objective="Locate the first sufficiently long free run without materializing a full shelf matrix.",
        public_api="FreeRun first_free_run(int slots, const std::vector<int>& occupied, int required)",
        profile="ordered occupied-position sentinel scan",
        marker="occupied_sentinels",
        instructions="""Implement `first_free_run` for a single shelf. Slot count is nonnegative, occupied indices must be unique and in range, and `required` must be positive. Return the lowest-start maximal free run whose length is at least `required`; return `found=false` when none exists. Invalid input returns `valid=false`.""",
        header=_header("""struct FreeRun { bool valid=false; bool found=false; int first=-1; int last=-1; };
FreeRun first_free_run(int slots, const std::vector<int>& occupied, int required);"""),
        reference=_source(
            """FreeRun first_free_run(int slots,const std::vector<int>& occupied,int required){
  FreeRun out;if(slots<0||required<=0)return out;std::set<int> occupied_sentinels;
  for(int value:occupied)if(value<0||value>=slots||!occupied_sentinels.insert(value).second)return out;
  int begin=0;for(int value:occupied_sentinels){if(value-begin>=required){out.valid=true;out.found=true;out.first=begin;out.last=value-1;return out;}begin=value+1;}
  out.valid=true;if(slots-begin>=required){out.found=true;out.first=begin;out.last=slots-1;}return out;
}""",
            "#include <set>",
        ),
        visible_test=_test("""  const auto r=curriculum::first_free_run(10,{0,3,4,8},2);
  check(r.valid&&r.found&&r.first==1&&r.last==2);"""),
        hidden_test=_test("""  const auto tail=curriculum::first_free_run(5,{0,1},3);check(tail.valid&&tail.found&&tail.first==2&&tail.last==4);
  check(!curriculum::first_free_run(5,{1,1},1).valid);
  const auto none=curriculum::first_free_run(3,{0,2},2);check(none.valid&&!none.found);
  check(!curriculum::first_free_run(3,{},0).valid);"""),
        negative_old="out.first=begin;out.last=value-1;return out;",
        negative_new="out.first=value+1;out.last=value+1;return out;",
        negative_reason="reports the occupied-side endpoint instead of the first free run",
    ),
    SparseCase(
        legacy_id="sparse-transit-delays",
        task_id="transit-csr-delays",
        title="Transit CSR delays",
        objective="Canonicalize sparse stop delays into compressed sparse row form.",
        public_api="DelayCsr build_delay_csr(int routes, int stops, const std::vector<Delay>& delays)",
        profile="duplicate-summing coordinate coalescence into CSR offsets",
        marker="csr_offsets",
        instructions="""Implement `build_delay_csr`. Dimensions are nonnegative and every coordinate must be in range. Sum duplicate route/stop delays; omit entries whose sum is zero. Return row offsets of length `routes+1`, ascending stop indices within each route, matching values, and per-route totals. Invalid input has `valid=false`.""",
        header=_header("""struct Delay { int route; int stop; int minutes; };
struct DelayCsr { bool valid=false; std::vector<int> offsets; std::vector<int> stops; std::vector<int> values; std::vector<int> route_totals; };
DelayCsr build_delay_csr(int routes,int stops,const std::vector<Delay>& delays);"""),
        reference=_source(
            """DelayCsr build_delay_csr(int routes,int stops,const std::vector<Delay>& delays){
  DelayCsr out;if(routes<0||stops<0)return out;std::map<std::pair<int,int>,int> coalesced;
  for(const auto&d:delays){if(d.route<0||d.route>=routes||d.stop<0||d.stop>=stops)return out;coalesced[{d.route,d.stop}]+=d.minutes;}
  std::vector<std::vector<std::pair<int,int>>> rows(static_cast<std::size_t>(routes));for(const auto&item:coalesced)if(item.second!=0)rows[static_cast<std::size_t>(item.first.first)].push_back({item.first.second,item.second});
  std::vector<int> csr_offsets(1,0);out.route_totals.assign(static_cast<std::size_t>(routes),0);
  for(int row=0;row<routes;++row){for(const auto&entry:rows[static_cast<std::size_t>(row)]){out.stops.push_back(entry.first);out.values.push_back(entry.second);out.route_totals[static_cast<std::size_t>(row)]+=entry.second;}csr_offsets.push_back(static_cast<int>(out.values.size()));}
  out.offsets=std::move(csr_offsets);out.valid=true;return out;
}""",
            "#include <map>\n#include <utility>",
        ),
        visible_test=_test("""  const auto c=curriculum::build_delay_csr(3,4,{{2,1,5},{0,3,2},{2,1,4},{1,0,0}});
  check(c.valid&&c.offsets==std::vector<int>({0,1,1,2}));
  check(c.stops==std::vector<int>({3,1})&&c.values==std::vector<int>({2,9})&&c.route_totals==std::vector<int>({2,0,9}));"""),
        hidden_test=_test("""  const auto z=curriculum::build_delay_csr(2,2,{{0,0,3},{0,0,-3}});check(z.valid&&z.values.empty()&&z.offsets==std::vector<int>({0,0,0}));
  check(!curriculum::build_delay_csr(2,2,{{2,0,1}}).valid);
  const auto e=curriculum::build_delay_csr(0,0,{});check(e.valid&&e.offsets==std::vector<int>({0}));"""),
        negative_old="csr_offsets.push_back(static_cast<int>(out.values.size()));",
        negative_new="csr_offsets.push_back(static_cast<int>(rows[static_cast<std::size_t>(row)].size()));",
        negative_reason="stores row sizes instead of cumulative CSR offsets",
    ),
    SparseCase(
        legacy_id="sparse-radar-contacts",
        task_id="radar-quadrant-topk",
        title="Radar quadrant top-K",
        objective="Select the strongest sparse radar contacts per geometric quadrant with stable ties.",
        public_api="QuadrantLeaders select_quadrant_leaders(int height, int width, int origin_row, int origin_column, int k, const std::vector<Contact>& contacts)",
        profile="four bounded min-heaps with confidence and coordinate tie keys",
        marker="quadrant_heaps",
        instructions="""Implement `select_quadrant_leaders`. Dimensions and the origin must be valid, `k` is nonnegative, and contact coordinates are unique and in range. Divide contacts by `row < origin_row` and `column < origin_column` into NW, NE, SW, and SE. Keep up to `k` contacts per quadrant by higher confidence, then lower row and column. Return each quadrant in that order. Invalid input returns `valid=false`.""",
        header=_header("""struct Contact { int row; int column; int confidence; bool operator==(const Contact& o) const { return row==o.row&&column==o.column&&confidence==o.confidence; } };
struct QuadrantLeaders { bool valid=false; std::vector<std::vector<Contact>> leaders; };
QuadrantLeaders select_quadrant_leaders(int height,int width,int origin_row,int origin_column,int k,const std::vector<Contact>& contacts);"""),
        reference=_source(
            """QuadrantLeaders select_quadrant_leaders(int height,int width,int origin_row,int origin_column,int k,const std::vector<Contact>& contacts){
  QuadrantLeaders out;if(height<=0||width<=0||origin_row<0||origin_row>=height||origin_column<0||origin_column>=width||k<0)return out;
  std::set<std::pair<int,int>> seen;std::vector<std::vector<Contact>> quadrant_heaps(4);
  for(const auto&c:contacts){if(c.row<0||c.row>=height||c.column<0||c.column>=width||!seen.insert({c.row,c.column}).second)return out;int q=(c.row>=origin_row?2:0)+(c.column>=origin_column?1:0);quadrant_heaps[static_cast<std::size_t>(q)].push_back(c);}
  const auto better=[](const Contact&a,const Contact&b){if(a.confidence!=b.confidence)return a.confidence>b.confidence;if(a.row!=b.row)return a.row<b.row;return a.column<b.column;};
  for(auto&bucket:quadrant_heaps){std::sort(bucket.begin(),bucket.end(),better);if(static_cast<int>(bucket.size())>k)bucket.resize(static_cast<std::size_t>(k));}
  out.valid=true;out.leaders=std::move(quadrant_heaps);return out;
}""",
            "#include <algorithm>\n#include <set>\n#include <utility>",
        ),
        visible_test=_test("""  const auto q=curriculum::select_quadrant_leaders(6,6,3,3,2,{{0,0,5},{1,2,9},{2,1,9},{4,4,7}});
  check(q.valid&&q.leaders.size()==4&&q.leaders[0]==std::vector<curriculum::Contact>({{1,2,9},{2,1,9}}));
  check(q.leaders[3]==std::vector<curriculum::Contact>({{4,4,7}}));"""),
        hidden_test=_test("""  const auto zero=curriculum::select_quadrant_leaders(2,2,1,1,0,{{0,0,4}});check(zero.valid&&zero.leaders[0].empty());
  check(!curriculum::select_quadrant_leaders(2,2,1,1,1,{{0,0,1},{0,0,2}}).valid);
  const auto tie=curriculum::select_quadrant_leaders(4,4,3,3,1,{{2,2,8},{0,1,8}});check(tie.valid&&tie.leaders[0][0].row==0);"""),
        negative_old="return a.confidence>b.confidence;",
        negative_new="return a.confidence<b.confidence;",
        negative_reason="keeps weakest rather than strongest contacts",
    ),
    SparseCase(
        legacy_id="sparse-paint-defects",
        task_id="defect-column-compressor",
        title="Defect column compressor",
        objective="Canonicalize sparse defects into compressed sparse column form with rejected duplicates.",
        public_api="DefectColumnIndex::build(int rows, int columns, const std::vector<Defect>& defects), with read-only CSC accessors",
        profile="column-major ordering and cumulative CSC pointer construction",
        marker="column_buckets",
        instructions="""Implement `DefectColumnIndex::build`. Dimensions are nonnegative. Defect coordinates must be unique and in range. Omit severity zero. Expose column pointers of length `columns+1`, then row indices and severities ordered by column and row through the read-only accessors. Invalid input returns an index whose `valid()` is false and whose arrays are empty.""",
        header=_header("""struct Defect { int row; int column; int severity; };
class DefectColumnIndex {
 public:
  static DefectColumnIndex build(int rows,int columns,const std::vector<Defect>& defects);
  bool valid() const { return valid_; }
  const std::vector<int>& column_pointers() const { return column_pointers_; }
  const std::vector<int>& row_indices() const { return row_indices_; }
  const std::vector<int>& severities() const { return severities_; }
 private:
  bool valid_=false;
  std::vector<int> column_pointers_;
  std::vector<int> row_indices_;
  std::vector<int> severities_;
};"""),
        reference=_source(
            """DefectColumnIndex DefectColumnIndex::build(int rows,int columns,const std::vector<Defect>& defects){
  DefectColumnIndex out;if(rows<0||columns<0)return out;std::set<std::pair<int,int>> seen;std::vector<std::vector<Defect>> column_buckets(static_cast<std::size_t>(columns));
  for(const auto&d:defects){if(d.row<0||d.row>=rows||d.column<0||d.column>=columns||!seen.insert({d.row,d.column}).second)return out;if(d.severity!=0)column_buckets[static_cast<std::size_t>(d.column)].push_back(d);}
  out.column_pointers_.push_back(0);for(auto&bucket:column_buckets){std::sort(bucket.begin(),bucket.end(),[](const auto&a,const auto&b){return a.row<b.row;});for(const auto&d:bucket){out.row_indices_.push_back(d.row);out.severities_.push_back(d.severity);}out.column_pointers_.push_back(static_cast<int>(out.row_indices_.size()));}
  out.valid_=true;return out;
}""",
            "#include <algorithm>\n#include <set>\n#include <utility>",
        ),
        visible_test=_test("""  const auto c=curriculum::DefectColumnIndex::build(4,3,{{3,0,2},{1,2,5},{0,0,4},{2,1,0}});
  check(c.valid()&&c.column_pointers()==std::vector<int>({0,2,2,3}));
  check(c.row_indices()==std::vector<int>({0,3,1})&&c.severities()==std::vector<int>({4,2,5}));"""),
        hidden_test=_test("""  const auto e=curriculum::DefectColumnIndex::build(0,2,{});check(e.valid()&&e.column_pointers()==std::vector<int>({0,0,0}));
  check(!curriculum::DefectColumnIndex::build(2,2,{{0,1,2},{0,1,3}}).valid());
  check(!curriculum::DefectColumnIndex::build(2,2,{{2,0,1}}).valid());"""),
        negative_old="column_buckets[static_cast<std::size_t>(d.column)].push_back(d);",
        negative_new="column_buckets[static_cast<std::size_t>(d.row % columns)].push_back(d);",
        negative_reason="buckets defects by row instead of column",
    ),
    SparseCase(
        legacy_id="sparse-hospital-beds",
        task_id="ward-occupancy-runs",
        title="Ward occupancy runs",
        objective="Compress occupied beds in a requested ward into maximal consecutive runs.",
        public_api="WardRuns ward_occupancy_runs(int wards, int beds_per_ward, int query_ward, const std::vector<OccupiedBed>& occupied)",
        profile="target-row ordered-set run-length compression",
        marker="ward_beds",
        instructions="""Implement `ward_occupancy_runs`. Dimensions must be positive and the query ward valid. Occupied coordinates must be unique and in range. Return maximal inclusive occupied runs in the query ward, their total bed count, and the longest run. Other wards must not affect the answer. Invalid input returns `valid=false`.""",
        header=_header("""struct OccupiedBed { int ward; int bed; };
struct BedRun { int first; int last; bool operator==(const BedRun&o)const{return first==o.first&&last==o.last;} };
struct WardRuns { bool valid=false; int occupied_count=0; int longest=0; std::vector<BedRun> runs; };
WardRuns ward_occupancy_runs(int wards,int beds_per_ward,int query_ward,const std::vector<OccupiedBed>& occupied);"""),
        reference=_source(
            """WardRuns ward_occupancy_runs(int wards,int beds_per_ward,int query_ward,const std::vector<OccupiedBed>& occupied){
  WardRuns out;if(wards<=0||beds_per_ward<=0||query_ward<0||query_ward>=wards)return out;std::set<std::pair<int,int>> unique;std::set<int> ward_beds;
  for(const auto&b:occupied){if(b.ward<0||b.ward>=wards||b.bed<0||b.bed>=beds_per_ward||!unique.insert({b.ward,b.bed}).second)return out;if(b.ward==query_ward)ward_beds.insert(b.bed);}
  for(int bed:ward_beds){if(out.runs.empty()||bed!=out.runs.back().last+1)out.runs.push_back({bed,bed});else out.runs.back().last=bed;}
  out.occupied_count=static_cast<int>(ward_beds.size());for(const auto&r:out.runs){out.longest=std::max(out.longest,r.last-r.first+1);}out.valid=true;return out;
}""",
            "#include <algorithm>\n#include <set>\n#include <utility>",
        ),
        visible_test=_test("""  const auto r=curriculum::ward_occupancy_runs(3,8,1,{{1,2},{1,3},{0,3},{1,6},{1,4}});
  check(r.valid&&r.occupied_count==4&&r.longest==3);
  check(r.runs==std::vector<curriculum::BedRun>({{2,4},{6,6}}));"""),
        hidden_test=_test("""  const auto none=curriculum::ward_occupancy_runs(2,3,1,{{0,0}});check(none.valid&&none.runs.empty());
  check(!curriculum::ward_occupancy_runs(2,3,1,{{1,2},{1,2}}).valid);
  const auto edge=curriculum::ward_occupancy_runs(1,3,0,{{0,0},{0,2}});check(edge.valid&&edge.runs.size()==2&&edge.longest==1);"""),
        negative_old="bed!=out.runs.back().last+1",
        negative_new="bed!=out.runs.back().last",
        negative_reason="fails to merge consecutive occupied beds",
    ),
    SparseCase(
        legacy_id="sparse-solar-shade",
        task_id="solar-rectangle-sums",
        title="Solar rectangle sums",
        objective="Answer multiple rectangle exposure queries from sparse weighted panel coordinates.",
        public_api="ExposureAnswers rectangle_exposure(int rows, int columns, const std::vector<ShadeCell>& cells, const std::vector<Rectangle>& queries)",
        profile="sparse load followed by two-dimensional inclusion-exclusion prefix table",
        marker="prefix_exposure",
        instructions="""Implement `rectangle_exposure`. Dimensions are nonnegative; shade coordinates must be unique and in range. Each query uses inclusive top/left/bottom/right bounds and must be valid. Return query sums in input order. Invalid cells, duplicates, or rectangles return `valid=false` without answers.""",
        header=_header("""struct ShadeCell { int row; int column; int exposure; };
struct Rectangle { int top; int left; int bottom; int right; };
struct ExposureAnswers { bool valid=false; std::vector<long long> sums; };
ExposureAnswers rectangle_exposure(int rows,int columns,const std::vector<ShadeCell>& cells,const std::vector<Rectangle>& queries);"""),
        reference=_source(
            """ExposureAnswers rectangle_exposure(int rows,int columns,const std::vector<ShadeCell>& cells,const std::vector<Rectangle>& queries){
  ExposureAnswers out;if(rows<0||columns<0)return out;std::set<std::pair<int,int>> seen;std::vector<long long> prefix_exposure(static_cast<std::size_t>((rows+1)*(columns+1)),0);
  const auto at=[&](int r,int c){return static_cast<std::size_t>(r*(columns+1)+c);};
  for(const auto&cell:cells){if(cell.row<0||cell.row>=rows||cell.column<0||cell.column>=columns||!seen.insert({cell.row,cell.column}).second)return out;prefix_exposure[at(cell.row+1,cell.column+1)]=cell.exposure;}
  for(int r=1;r<=rows;++r)for(int c=1;c<=columns;++c)prefix_exposure[at(r,c)]+=prefix_exposure[at(r-1,c)]+prefix_exposure[at(r,c-1)]-prefix_exposure[at(r-1,c-1)];
  for(const auto&q:queries){if(q.top<0||q.left<0||q.bottom<q.top||q.right<q.left||q.bottom>=rows||q.right>=columns)return ExposureAnswers{};out.sums.push_back(prefix_exposure[at(q.bottom+1,q.right+1)]-prefix_exposure[at(q.top,q.right+1)]-prefix_exposure[at(q.bottom+1,q.left)]+prefix_exposure[at(q.top,q.left)]);}
  out.valid=true;return out;
}""",
            "#include <set>\n#include <utility>",
        ),
        visible_test=_test("""  const auto a=curriculum::rectangle_exposure(4,5,{{0,0,3},{1,2,7},{3,4,5}},{{0,0,1,2},{1,2,3,4}});
  check(a.valid&&a.sums==std::vector<long long>({10,12}));"""),
        hidden_test=_test("""  const auto z=curriculum::rectangle_exposure(2,2,{},{{0,0,1,1}});check(z.valid&&z.sums==std::vector<long long>({0}));
  check(!curriculum::rectangle_exposure(2,2,{{0,0,1},{0,0,2}},{}).valid);
  check(!curriculum::rectangle_exposure(2,2,{},{{1,1,0,1}}).valid);
  const auto point=curriculum::rectangle_exposure(1,1,{{0,0,-4}},{{0,0,0,0}});check(point.valid&&point.sums[0]==-4);"""),
        negative_old="+prefix_exposure[at(q.top,q.left)]",
        negative_new="-prefix_exposure[at(q.top,q.left)]",
        negative_reason="uses the wrong inclusion-exclusion corner sign",
    ),
    SparseCase(
        legacy_id="sparse-orchard-pests",
        task_id="orchard-row-groups",
        title="Orchard row groups",
        objective="Group sparse infected-tree columns by row and choose the densest affected row.",
        public_api="PestRows group_infected_rows(int rows, int columns, const std::vector<TreeCell>& infected)",
        profile="ordered row map with canonical per-row coordinate groups and stable argmax",
        marker="row_groups",
        instructions="""Implement `group_infected_rows`. Dimensions are nonnegative and infected coordinates must be unique and in range. Emit only affected rows in ascending row order, with ascending columns. `densest_row` is the lowest row having the most infected trees, or `-1` when empty. Invalid input returns `valid=false`.""",
        header=_header("""struct TreeCell { int row; int column; };
struct InfectedRow { int row; std::vector<int> columns; };
struct PestRows { bool valid=false; int densest_row=-1; std::vector<InfectedRow> groups; };
PestRows group_infected_rows(int rows,int columns,const std::vector<TreeCell>& infected);"""),
        reference=_source(
            """PestRows group_infected_rows(int rows,int columns,const std::vector<TreeCell>& infected){
  PestRows out;if(rows<0||columns<0)return out;std::map<int,std::set<int>> row_groups;
  for(const auto&cell:infected){if(cell.row<0||cell.row>=rows||cell.column<0||cell.column>=columns||!row_groups[cell.row].insert(cell.column).second)return out;}
  std::size_t best=0;for(const auto&item:row_groups){out.groups.push_back({item.first,std::vector<int>(item.second.begin(),item.second.end())});if(item.second.size()>best){best=item.second.size();out.densest_row=item.first;}}
  out.valid=true;return out;
}""",
            "#include <map>\n#include <set>",
        ),
        visible_test=_test("""  const auto p=curriculum::group_infected_rows(5,6,{{3,2},{1,4},{3,0},{1,2},{4,1}});
  check(p.valid&&p.densest_row==1&&p.groups.size()==3);
  check(p.groups[0].row==1&&p.groups[0].columns==std::vector<int>({2,4}));"""),
        hidden_test=_test("""  const auto e=curriculum::group_infected_rows(0,0,{});check(e.valid&&e.densest_row==-1);
  check(!curriculum::group_infected_rows(2,2,{{1,1},{1,1}}).valid);
  const auto tie=curriculum::group_infected_rows(3,3,{{2,0},{0,2}});check(tie.valid&&tie.densest_row==0);
  check(!curriculum::group_infected_rows(2,2,{{-1,0}}).valid);"""),
        negative_old="if(item.second.size()>best)",
        negative_new="if(item.second.size()>=best)",
        negative_reason="breaks densest-row ties toward the highest row",
    ),
    SparseCase(
        legacy_id="sparse-parking-sensors",
        task_id="parking-nearest-vacancy",
        title="Parking nearest vacancy",
        objective="Find the nearest unoccupied bay to a requested position using sparse occupancy.",
        public_api="Vacancy nearest_vacancy(int bays, int preferred, const std::vector<int>& occupied)",
        profile="ordered occupied-set bidirectional distance search",
        marker="occupied_bays",
        instructions="""Implement `nearest_vacancy`. Bay count must be nonnegative, the preferred bay must be in range, and occupied indices must be unique and in range. Search increasing distance from `preferred`; on equal distance choose the lower bay. Return `found=false` only when every bay is occupied. Invalid input returns `valid=false`.""",
        header=_header("""struct Vacancy { bool valid=false; bool found=false; int bay=-1; int distance=-1; };
Vacancy nearest_vacancy(int bays,int preferred,const std::vector<int>& occupied);"""),
        reference=_source(
            """Vacancy nearest_vacancy(int bays,int preferred,const std::vector<int>& occupied){
  Vacancy out;if(bays<0||preferred<0||preferred>=bays)return out;std::set<int> occupied_bays;
  for(int bay:occupied)if(bay<0||bay>=bays||!occupied_bays.insert(bay).second)return out;
  out.valid=true;for(int distance=0;distance<bays;++distance){const int left=preferred-distance;if(left>=0&&!occupied_bays.count(left)){out.found=true;out.bay=left;out.distance=distance;return out;}const int right=preferred+distance;if(right<bays&&!occupied_bays.count(right)){out.found=true;out.bay=right;out.distance=distance;return out;}}return out;
}""",
            "#include <set>",
        ),
        visible_test=_test(
            """  const auto v=curriculum::nearest_vacancy(8,4,{3,4,5,6});check(v.valid&&v.found&&v.bay==2&&v.distance==2);"""
        ),
        hidden_test=_test("""  const auto tie=curriculum::nearest_vacancy(7,3,{3});check(tie.valid&&tie.bay==2);
  const auto full=curriculum::nearest_vacancy(2,0,{0,1});check(full.valid&&!full.found);
  check(!curriculum::nearest_vacancy(3,1,{2,2}).valid);
  const auto self=curriculum::nearest_vacancy(3,1,{});check(self.valid&&self.bay==1&&self.distance==0);"""),
        negative_old="const int left=preferred-distance;",
        negative_new="const int left=-1;",
        negative_reason="ignores the lower-bay tie candidate",
    ),
    SparseCase(
        legacy_id="sparse-warehouse-stock",
        task_id="warehouse-delta-coalescer",
        title="Warehouse delta coalescer",
        objective="Coalesce an ordered sparse stock-delta log into canonical nonzero bin balances.",
        public_api="StockLedger coalesce_stock(int aisles, int bins, const std::vector<StockDelta>& deltas)",
        profile="coordinate-keyed additive log fold with zero cancellation",
        marker="balance_by_bin",
        instructions="""Implement `coalesce_stock`. Dimensions are nonnegative and all delta coordinates must be in range. Apply deltas in input order by addition. Omit zero final balances and return remaining entries in row-major coordinate order, plus their signed checksum. Invalid input returns `valid=false`.""",
        header=_header("""struct StockDelta { int aisle; int bin; int amount; };
struct BinBalance { int aisle; int bin; long long amount; bool operator==(const BinBalance&o)const{return aisle==o.aisle&&bin==o.bin&&amount==o.amount;} };
struct StockLedger { bool valid=false; long long checksum=0; std::vector<BinBalance> balances; };
StockLedger coalesce_stock(int aisles,int bins,const std::vector<StockDelta>& deltas);"""),
        reference=_source(
            """StockLedger coalesce_stock(int aisles,int bins,const std::vector<StockDelta>& deltas){
  StockLedger out;if(aisles<0||bins<0)return out;std::map<std::pair<int,int>,long long> balance_by_bin;
  for(const auto&d:deltas){if(d.aisle<0||d.aisle>=aisles||d.bin<0||d.bin>=bins)return out;balance_by_bin[{d.aisle,d.bin}]+=d.amount;}
  for(const auto&item:balance_by_bin){if(item.second!=0){out.balances.push_back({item.first.first,item.first.second,item.second});out.checksum+=item.second;}}
  out.valid=true;return out;
}""",
            "#include <map>\n#include <utility>",
        ),
        visible_test=_test("""  const auto l=curriculum::coalesce_stock(3,4,{{1,2,5},{0,3,4},{1,2,-2},{2,0,1}});
  check(l.valid&&l.checksum==8&&l.balances==std::vector<curriculum::BinBalance>({{0,3,4},{1,2,3},{2,0,1}}));"""),
        hidden_test=_test("""  const auto cancel=curriculum::coalesce_stock(1,1,{{0,0,7},{0,0,-7}});check(cancel.valid&&cancel.balances.empty()&&cancel.checksum==0);
  check(!curriculum::coalesce_stock(2,2,{{0,2,1}}).valid);
  const auto e=curriculum::coalesce_stock(0,0,{});check(e.valid&&e.balances.empty());"""),
        negative_old="balance_by_bin[{d.aisle,d.bin}]+=d.amount;",
        negative_new="balance_by_bin[{d.aisle,d.bin}]=d.amount;",
        negative_reason="uses last-write-wins instead of additive delta coalescence",
    ),
    SparseCase(
        legacy_id="sparse-flood-markers",
        task_id="flood-shoreline-perimeter",
        title="Flood shoreline perimeter",
        objective="Compute exposed four-neighbor shoreline around sparse inundated cells.",
        public_api="Shoreline measure_shoreline(int rows, int columns, const std::vector<FloodCell>& flooded)",
        profile="sparse membership set with four-edge exposure accounting",
        marker="flood_membership",
        instructions="""Implement `measure_shoreline`. Dimensions are nonnegative; flooded coordinates must be unique and in range. Return the number of flooded cells, total exposed orthogonal edges, and the count of connected components using four-neighbor adjacency. Empty input is valid. Invalid input returns `valid=false`.""",
        header=_header("""struct FloodCell { int row; int column; };
struct Shoreline { bool valid=false; int flooded_cells=0; int perimeter=0; int components=0; };
Shoreline measure_shoreline(int rows,int columns,const std::vector<FloodCell>& flooded);"""),
        reference=_source(
            """Shoreline measure_shoreline(int rows,int columns,const std::vector<FloodCell>& flooded){
  Shoreline out;if(rows<0||columns<0)return out;std::set<std::pair<int,int>> flood_membership;
  for(const auto&c:flooded)if(c.row<0||c.row>=rows||c.column<0||c.column>=columns||!flood_membership.insert({c.row,c.column}).second)return out;
  const int dr[4]={-1,1,0,0};const int dc[4]={0,0,-1,1};std::set<std::pair<int,int>> visited;
  for(const auto&cell:flood_membership){for(int d=0;d<4;++d){if(!flood_membership.count({cell.first+dr[d],cell.second+dc[d]}))++out.perimeter;}if(visited.count(cell))continue;++out.components;std::queue<std::pair<int,int>> work;work.push(cell);visited.insert(cell);while(!work.empty()){auto cur=work.front();work.pop();for(int d=0;d<4;++d){std::pair<int,int> next={cur.first+dr[d],cur.second+dc[d]};if(flood_membership.count(next)&&visited.insert(next).second)work.push(next);}}}
  out.valid=true;out.flooded_cells=static_cast<int>(flood_membership.size());return out;
}""",
            "#include <queue>\n#include <set>\n#include <utility>",
        ),
        visible_test=_test(
            """  const auto s=curriculum::measure_shoreline(4,4,{{1,1},{1,2},{2,1}});check(s.valid&&s.flooded_cells==3&&s.perimeter==8&&s.components==1);"""
        ),
        hidden_test=_test("""  const auto separate=curriculum::measure_shoreline(3,3,{{0,0},{2,2}});check(separate.valid&&separate.perimeter==8&&separate.components==2);
  const auto empty=curriculum::measure_shoreline(0,0,{});check(empty.valid&&empty.perimeter==0);
  check(!curriculum::measure_shoreline(2,2,{{0,0},{0,0}}).valid);
  const auto block=curriculum::measure_shoreline(2,2,{{0,0},{0,1},{1,0},{1,1}});check(block.valid&&block.perimeter==8&&block.components==1);"""),
        negative_old="const int dr[4]={-1,1,0,0};const int dc[4]={0,0,-1,1};",
        negative_new="const int dr[4]={-1,1,-1,1};const int dc[4]={-1,1,1,-1};",
        negative_reason="uses diagonal rather than shoreline edge adjacency",
    ),
    SparseCase(
        legacy_id="sparse-game-terrain",
        task_id="terrain-morton-catalog",
        title="Terrain Morton catalog",
        objective="Encode sparse terrain coordinates into canonical Morton order for power-of-two maps.",
        public_api="MortonCatalog catalog_terrain(int side, const std::vector<TerrainTile>& tiles)",
        profile="bit-interleaving Morton code generation and ordered catalog",
        marker="morton_interleave",
        instructions="""Implement `catalog_terrain`. `side` must be a positive power of two no larger than 32768. Coordinates must be unique and in range. Omit code-zero terrain values. Interleave column bits into even Morton positions and row bits into odd positions. Return entries sorted by Morton code and a code checksum. Invalid input returns `valid=false`.""",
        header=_header("""struct TerrainTile { int row; int column; int terrain; };
struct MortonTile { unsigned int code; int terrain; bool operator==(const MortonTile&o)const{return code==o.code&&terrain==o.terrain;} };
struct MortonCatalog { bool valid=false; unsigned long long checksum=0; std::vector<MortonTile> entries; };
MortonCatalog catalog_terrain(int side,const std::vector<TerrainTile>& tiles);"""),
        reference=_source(
            """MortonCatalog catalog_terrain(int side,const std::vector<TerrainTile>& tiles){
  MortonCatalog out;if(side<=0||side>32768||(side&(side-1))!=0)return out;std::set<std::pair<int,int>> seen;
  const auto morton_interleave=[](unsigned int row,unsigned int column){unsigned int code=0;for(unsigned int bit=0;bit<15;++bit){code|=((column>>bit)&1U)<<(2U*bit);code|=((row>>bit)&1U)<<(2U*bit+1U);}return code;};
  for(const auto&t:tiles){if(t.row<0||t.row>=side||t.column<0||t.column>=side||!seen.insert({t.row,t.column}).second)return out;if(t.terrain!=0)out.entries.push_back({morton_interleave(static_cast<unsigned int>(t.row),static_cast<unsigned int>(t.column)),t.terrain});}
  std::sort(out.entries.begin(),out.entries.end(),[](const auto&a,const auto&b){return a.code<b.code;});for(const auto&e:out.entries){out.checksum+=e.code;}out.valid=true;return out;
}""",
            "#include <algorithm>\n#include <set>\n#include <utility>",
        ),
        visible_test=_test("""  const auto m=curriculum::catalog_terrain(8,{{1,0,4},{0,1,3},{2,2,5},{0,0,0}});
  check(m.valid&&m.entries==std::vector<curriculum::MortonTile>({{1,3},{2,4},{12,5}})&&m.checksum==15);"""),
        hidden_test=_test("""  check(!curriculum::catalog_terrain(6,{}).valid);
  check(!curriculum::catalog_terrain(4,{{0,0,1},{0,0,2}}).valid);
  const auto edge=curriculum::catalog_terrain(2,{{1,1,9}});check(edge.valid&&edge.entries[0].code==3);
  const auto empty=curriculum::catalog_terrain(1,{});check(empty.valid&&empty.entries.empty());"""),
        negative_old="code|=((row>>bit)&1U)<<(2U*bit+1U);",
        negative_new="code|=((row>>bit)&1U)<<(2U*bit);",
        negative_reason="overlays row bits instead of interleaving them",
    ),
    SparseCase(
        legacy_id="sparse-crop-yields",
        task_id="yield-row-dot-product",
        title="Yield row dot product",
        objective="Compute sparse per-field weighted yield totals against a dense column coefficient vector.",
        public_api="YieldTotals weighted_yields(int fields, const std::vector<int>& column_weights, const std::vector<YieldCell>& yields)",
        profile="duplicate-summing sparse row dot products with checked coordinate domain",
        marker="weighted_by_field",
        instructions="""Implement `weighted_yields`. `fields` is nonnegative; column count is `column_weights.size()`. Coordinates must be in range. Sum duplicate yield coordinates before multiplying by the column weight. Return one signed 64-bit total per field and the lowest field attaining the maximum, or `-1` when there are no fields. Invalid input returns `valid=false`.""",
        header=_header("""struct YieldCell { int field; int column; int amount; };
struct YieldTotals { bool valid=false; int best_field=-1; std::vector<long long> totals; };
YieldTotals weighted_yields(int fields,const std::vector<int>& column_weights,const std::vector<YieldCell>& yields);"""),
        reference=_source(
            """YieldTotals weighted_yields(int fields,const std::vector<int>& column_weights,const std::vector<YieldCell>& yields){
  YieldTotals out;if(fields<0)return out;std::map<std::pair<int,int>,long long> coalesced;for(const auto&cell:yields){if(cell.field<0||cell.field>=fields||cell.column<0||cell.column>=static_cast<int>(column_weights.size()))return out;coalesced[{cell.field,cell.column}]+=cell.amount;}
  std::vector<long long> weighted_by_field(static_cast<std::size_t>(fields),0);for(const auto&item:coalesced)weighted_by_field[static_cast<std::size_t>(item.first.first)]+=item.second*column_weights[static_cast<std::size_t>(item.first.second)];
  out.totals=weighted_by_field;if(fields>0){out.best_field=0;for(int row=1;row<fields;++row)if(out.totals[static_cast<std::size_t>(row)]>out.totals[static_cast<std::size_t>(out.best_field)])out.best_field=row;}out.valid=true;return out;
}""",
            "#include <map>\n#include <utility>",
        ),
        visible_test=_test("""  const auto y=curriculum::weighted_yields(3,{2,-1,4},{{0,0,3},{0,2,2},{1,1,5},{0,0,1}});
  check(y.valid&&y.totals==std::vector<long long>({16,-5,0})&&y.best_field==0);"""),
        hidden_test=_test("""  const auto tie=curriculum::weighted_yields(2,{1},{{0,0,3},{1,0,3}});check(tie.valid&&tie.best_field==0);
  const auto nofields=curriculum::weighted_yields(0,{},{});check(nofields.valid&&nofields.best_field==-1);
  check(!curriculum::weighted_yields(1,{2},{{0,1,4}}).valid);
  const auto cancel=curriculum::weighted_yields(1,{3},{{0,0,2},{0,0,-2}});check(cancel.valid&&cancel.totals[0]==0);"""),
        negative_old="coalesced[{cell.field,cell.column}]+=cell.amount;",
        negative_new="coalesced[{cell.field,cell.column}]=cell.amount;",
        negative_reason="drops earlier duplicate yield contributions",
    ),
    SparseCase(
        legacy_id="sparse-network-failures",
        task_id="failure-bipartite-index",
        title="Failure bipartite index",
        objective="Build a sparse rack-to-link index and find a maximum-cardinality repair matching.",
        public_api="RepairMatching match_failures(int racks, int links, const std::vector<FailedEdge>& failures)",
        profile="canonical adjacency lists plus augmenting-path bipartite matching",
        marker="augmenting_owner",
        instructions="""Implement `match_failures`. Dimensions are nonnegative and failed rack/link pairs must be unique and in range. Find a maximum-cardinality matching between racks and links. Visit racks and each rack's links in ascending order, making the returned `(rack,link)` pairs deterministic and sorted by rack. Invalid input returns `valid=false`.""",
        header=_header("""struct FailedEdge { int rack; int link; };
struct RepairPair { int rack; int link; bool operator==(const RepairPair&o)const{return rack==o.rack&&link==o.link;} };
struct RepairMatching { bool valid=false; std::vector<RepairPair> pairs; };
RepairMatching match_failures(int racks,int links,const std::vector<FailedEdge>& failures);"""),
        reference=_source(
            """RepairMatching match_failures(int racks,int links,const std::vector<FailedEdge>& failures){
  RepairMatching out;if(racks<0||links<0)return out;std::vector<std::set<int>> adjacency(static_cast<std::size_t>(racks));
  for(const auto&e:failures)if(e.rack<0||e.rack>=racks||e.link<0||e.link>=links||!adjacency[static_cast<std::size_t>(e.rack)].insert(e.link).second)return out;
  std::vector<int> augmenting_owner(static_cast<std::size_t>(links),-1);
  const auto augment=[&](auto&& self,int rack,std::vector<bool>&seen)->bool{for(int link:adjacency[static_cast<std::size_t>(rack)])if(!seen[static_cast<std::size_t>(link)]){seen[static_cast<std::size_t>(link)]=true;if(augmenting_owner[static_cast<std::size_t>(link)]==-1||self(self,augmenting_owner[static_cast<std::size_t>(link)],seen)){augmenting_owner[static_cast<std::size_t>(link)]=rack;return true;}}return false;};
  for(int rack=0;rack<racks;++rack){std::vector<bool> seen(static_cast<std::size_t>(links),false);augment(augment,rack,seen);}for(int link=0;link<links;++link)if(augmenting_owner[static_cast<std::size_t>(link)]!=-1)out.pairs.push_back({augmenting_owner[static_cast<std::size_t>(link)],link});std::sort(out.pairs.begin(),out.pairs.end(),[](const auto&a,const auto&b){return a.rack<b.rack;});out.valid=true;return out;
}""",
            "#include <algorithm>\n#include <set>",
        ),
        visible_test=_test("""  const auto m=curriculum::match_failures(3,3,{{0,0},{0,1},{1,0},{2,1},{2,2}});
  check(m.valid&&m.pairs.size()==3&&m.pairs==std::vector<curriculum::RepairPair>({{0,1},{1,0},{2,2}}));"""),
        hidden_test=_test("""  const auto shortfall=curriculum::match_failures(3,1,{{0,0},{1,0}});check(shortfall.valid&&shortfall.pairs.size()==1);
  check(!curriculum::match_failures(2,2,{{0,1},{0,1}}).valid);
  const auto empty=curriculum::match_failures(0,0,{});check(empty.valid&&empty.pairs.empty());
  check(!curriculum::match_failures(1,1,{{1,0}}).valid);"""),
        negative_old="for(int rack=0;rack<racks;++rack){std::vector<bool> seen(static_cast<std::size_t>(links),false);augment(augment,rack,seen);}",
        negative_new="if(racks>0){std::vector<bool> seen(static_cast<std::size_t>(links),false);augment(augment,0,seen);}",
        negative_reason="attempts augmenting paths for only the first rack",
    ),
    SparseCase(
        legacy_id="sparse-seat-reservations",
        task_id="cabin-reservation-runs",
        title="Cabin reservation runs",
        objective="Compress sparse reserved seats by cabin into maximal contiguous runs.",
        public_api="CabinRuns compress_reservations(int cabins, int seats, const std::vector<ReservedSeat>& reserved)",
        profile="two-level ordered grouping and per-cabin consecutive run encoding",
        marker="runs_by_cabin",
        instructions="""Implement `compress_reservations`. Dimensions are nonnegative and reserved coordinates must be unique and in range. Emit only nonempty cabins in ascending order; within each cabin emit maximal inclusive seat runs in ascending order. Return total reserved seats. Invalid input returns `valid=false`.""",
        header=_header("""struct ReservedSeat { int cabin; int seat; };
struct SeatRun { int first; int last; bool operator==(const SeatRun&o)const{return first==o.first&&last==o.last;} };
struct CabinEntry { int cabin; std::vector<SeatRun> runs; };
struct CabinRuns { bool valid=false; int reserved_count=0; std::vector<CabinEntry> cabins; };
CabinRuns compress_reservations(int cabins,int seats,const std::vector<ReservedSeat>& reserved);"""),
        reference=_source(
            """CabinRuns compress_reservations(int cabins,int seats,const std::vector<ReservedSeat>& reserved){
  CabinRuns out;if(cabins<0||seats<0)return out;std::map<int,std::set<int>> runs_by_cabin;
  for(const auto&r:reserved)if(r.cabin<0||r.cabin>=cabins||r.seat<0||r.seat>=seats||!runs_by_cabin[r.cabin].insert(r.seat).second)return out;
  for(const auto&item:runs_by_cabin){CabinEntry entry{item.first,{}};for(int seat:item.second){if(entry.runs.empty()||seat>entry.runs.back().last+1)entry.runs.push_back({seat,seat});else entry.runs.back().last=seat;}out.reserved_count+=static_cast<int>(item.second.size());out.cabins.push_back(std::move(entry));}out.valid=true;return out;
}""",
            "#include <map>\n#include <set>\n#include <utility>",
        ),
        visible_test=_test("""  const auto c=curriculum::compress_reservations(3,8,{{2,5},{0,1},{0,2},{2,7},{2,6}});
  check(c.valid&&c.reserved_count==5&&c.cabins.size()==2);
  check(c.cabins[0].cabin==0&&c.cabins[0].runs==std::vector<curriculum::SeatRun>({{1,2}}));
  check(c.cabins[1].runs==std::vector<curriculum::SeatRun>({{5,7}}));"""),
        hidden_test=_test("""  const auto empty=curriculum::compress_reservations(2,2,{});check(empty.valid&&empty.cabins.empty());
  check(!curriculum::compress_reservations(2,2,{{1,1},{1,1}}).valid);
  const auto split=curriculum::compress_reservations(1,5,{{0,0},{0,2},{0,4}});check(split.valid&&split.cabins[0].runs.size()==3);
  check(!curriculum::compress_reservations(1,1,{{0,1}}).valid);"""),
        negative_old="seat>entry.runs.back().last+1",
        negative_new="seat>entry.runs.back().last",
        negative_reason="does not merge adjacent reserved seats",
    ),
    SparseCase(
        legacy_id="sparse-lab-assays",
        task_id="assay-coordinate-transpose",
        title="Assay coordinate transpose",
        objective="Transpose sparse assay wells while resolving duplicate readings by maximum signal.",
        public_api="AssayTranspose transpose_assays(int plates, int wells, const std::vector<AssayReading>& readings)",
        profile="duplicate-max coordinate reduction followed by axis swap and canonical sort",
        marker="transposed_signals",
        instructions="""Implement `transpose_assays`. Dimensions are nonnegative and readings must be in range. Duplicate input coordinates keep the greatest signal. Omit final signal zero. Return output dimensions `wells x plates`, entries ordered by transposed row then column, and the number of duplicate readings consumed. Invalid input returns `valid=false`.""",
        header=_header("""struct AssayReading { int plate; int well; int signal; };
struct TransposedReading { int row; int column; int signal; bool operator==(const TransposedReading&o)const{return row==o.row&&column==o.column&&signal==o.signal;} };
struct AssayTranspose { bool valid=false; int rows=0; int columns=0; int duplicates=0; std::vector<TransposedReading> readings; };
AssayTranspose transpose_assays(int plates,int wells,const std::vector<AssayReading>& readings);"""),
        reference=_source(
            """AssayTranspose transpose_assays(int plates,int wells,const std::vector<AssayReading>& readings){
  AssayTranspose out;if(plates<0||wells<0)return out;std::map<std::pair<int,int>,int> transposed_signals;
  for(const auto&r:readings){if(r.plate<0||r.plate>=plates||r.well<0||r.well>=wells)return out;auto key=std::make_pair(r.plate,r.well);auto it=transposed_signals.find(key);if(it==transposed_signals.end())transposed_signals[key]=r.signal;else{++out.duplicates;it->second=std::max(it->second,r.signal);}}
  for(const auto&item:transposed_signals){if(item.second!=0)out.readings.push_back({item.first.second,item.first.first,item.second});}std::sort(out.readings.begin(),out.readings.end(),[](const auto&a,const auto&b){return a.row!=b.row?a.row<b.row:a.column<b.column;});out.valid=true;out.rows=wells;out.columns=plates;return out;
}""",
            "#include <algorithm>\n#include <map>\n#include <utility>",
        ),
        visible_test=_test("""  const auto t=curriculum::transpose_assays(3,4,{{2,1,5},{0,3,7},{2,1,9},{1,0,4}});
  check(t.valid&&t.rows==4&&t.columns==3&&t.duplicates==1);
  check(t.readings==std::vector<curriculum::TransposedReading>({{0,1,4},{1,2,9},{3,0,7}}));"""),
        hidden_test=_test("""  const auto zero=curriculum::transpose_assays(1,1,{{0,0,0}});check(zero.valid&&zero.readings.empty());
  check(!curriculum::transpose_assays(1,1,{{0,1,2}}).valid);
  const auto dup=curriculum::transpose_assays(1,1,{{0,0,8},{0,0,3}});check(dup.valid&&dup.readings[0].signal==8&&dup.duplicates==1);
  const auto empty=curriculum::transpose_assays(0,2,{});check(empty.valid&&empty.rows==2&&empty.columns==0);"""),
        negative_old="it->second=std::max(it->second,r.signal);",
        negative_new="it->second=r.signal;",
        negative_reason="uses last duplicate rather than maximum signal",
    ),
    SparseCase(
        legacy_id="sparse-fire-hotspots",
        task_id="hotspot-row-sweep",
        title="Hotspot row sweep",
        objective="Find the maximum row heat induced by sparse vertical heat segments.",
        public_api="HotspotPeak sweep_hotspots(int rows, int columns, const std::vector<HeatSegment>& segments)",
        profile="row difference-event sweep over sparse vertical segments",
        marker="row_events",
        instructions="""Implement `sweep_hotspots`. Dimensions are nonnegative. Each segment has an in-range column, inclusive `first_row..last_row`, and signed heat. Add all active segment heat to every covered row. Return the maximum row total and the lowest row attaining it; for zero rows return row `-1` and heat `0`. Invalid input returns `valid=false`.""",
        header=_header("""struct HeatSegment { int column; int first_row; int last_row; int heat; };
struct HotspotPeak { bool valid=false; int row=-1; long long heat=0; };
HotspotPeak sweep_hotspots(int rows,int columns,const std::vector<HeatSegment>& segments);"""),
        reference=_source(
            """HotspotPeak sweep_hotspots(int rows,int columns,const std::vector<HeatSegment>& segments){
  HotspotPeak out;if(rows<0||columns<0)return out;std::map<int,long long> row_events;
  for(const auto&s:segments){if(s.column<0||s.column>=columns||s.first_row<0||s.last_row<s.first_row||s.last_row>=rows)return out;row_events[s.first_row]+=s.heat;row_events[s.last_row+1]-=s.heat;}
  out.valid=true;if(rows==0)return out;long long current=0;out.row=0;out.heat=std::numeric_limits<long long>::lowest();for(int row=0;row<rows;++row){auto it=row_events.find(row);if(it!=row_events.end())current+=it->second;if(current>out.heat){out.heat=current;out.row=row;}}return out;
}""",
            "#include <limits>\n#include <map>",
        ),
        visible_test=_test(
            """  const auto p=curriculum::sweep_hotspots(6,4,{{0,1,3,5},{2,2,5,4},{1,0,0,7}});check(p.valid&&p.row==2&&p.heat==9);"""
        ),
        hidden_test=_test("""  const auto tie=curriculum::sweep_hotspots(3,1,{{0,0,0,2},{0,2,2,2}});check(tie.valid&&tie.row==0&&tie.heat==2);
  const auto neg=curriculum::sweep_hotspots(2,1,{{0,0,1,-3}});check(neg.valid&&neg.row==0&&neg.heat==-3);
  const auto empty=curriculum::sweep_hotspots(0,0,{});check(empty.valid&&empty.row==-1&&empty.heat==0);
  check(!curriculum::sweep_hotspots(2,1,{{1,0,1,2}}).valid);"""),
        negative_old="row_events[s.last_row+1]-=s.heat;",
        negative_new="row_events[s.last_row]-=s.heat;",
        negative_reason="removes heat before the inclusive last row",
    ),
    SparseCase(
        legacy_id="sparse-museum-sensors",
        task_id="museum-latest-snapshot",
        title="Museum latest snapshot",
        objective="Resolve timestamped sparse sensor events into a deterministic latest-value snapshot.",
        public_api="SensorSnapshot latest_sensor_snapshot(int floors, int sensors, const std::vector<SensorEvent>& events)",
        profile="coordinate-keyed timestamp arbitration with equal-time conflict rejection",
        marker="latest_by_sensor",
        instructions="""Implement `latest_sensor_snapshot`. Dimensions are nonnegative; events must be in range and timestamps nonnegative. For each coordinate keep the event with greatest timestamp. Two events at the same coordinate and timestamp but different states invalidate the request; identical repeats count as duplicates. Emit only final `triggered=true` cells in row-major order and report stale/duplicate event count. Invalid input returns `valid=false`.""",
        header=_header("""struct SensorEvent { int floor; int sensor; int timestamp; bool triggered; };
struct TriggeredSensor { int floor; int sensor; int timestamp; bool operator==(const TriggeredSensor&o)const{return floor==o.floor&&sensor==o.sensor&&timestamp==o.timestamp;} };
struct SensorSnapshot { bool valid=false; int ignored_events=0; std::vector<TriggeredSensor> triggered; };
SensorSnapshot latest_sensor_snapshot(int floors,int sensors,const std::vector<SensorEvent>& events);"""),
        reference=_source(
            """SensorSnapshot latest_sensor_snapshot(int floors,int sensors,const std::vector<SensorEvent>& events){
  SensorSnapshot out;if(floors<0||sensors<0)return out;std::map<std::pair<int,int>,SensorEvent> latest_by_sensor;
  for(const auto&e:events){if(e.floor<0||e.floor>=floors||e.sensor<0||e.sensor>=sensors||e.timestamp<0)return out;auto key=std::make_pair(e.floor,e.sensor);auto it=latest_by_sensor.find(key);if(it==latest_by_sensor.end()){latest_by_sensor.emplace(key,e);continue;}if(e.timestamp==it->second.timestamp&&e.triggered!=it->second.triggered)return SensorSnapshot{};if(e.timestamp>it->second.timestamp)it->second=e;else ++out.ignored_events;}
  for(const auto&item:latest_by_sensor){if(item.second.triggered)out.triggered.push_back({item.first.first,item.first.second,item.second.timestamp});}out.valid=true;return out;
}""",
            "#include <map>\n#include <utility>",
        ),
        visible_test=_test("""  const auto s=curriculum::latest_sensor_snapshot(3,4,{{1,2,3,true},{0,1,4,true},{1,2,5,false},{2,0,2,true}});
  check(s.valid&&s.ignored_events==0&&s.triggered==std::vector<curriculum::TriggeredSensor>({{0,1,4},{2,0,2}}));"""),
        hidden_test=_test("""  const auto stale=curriculum::latest_sensor_snapshot(1,1,{{0,0,5,true},{0,0,3,false},{0,0,5,true}});check(stale.valid&&stale.ignored_events==2&&stale.triggered.size()==1);
  check(!curriculum::latest_sensor_snapshot(1,1,{{0,0,2,true},{0,0,2,false}}).valid);
  check(!curriculum::latest_sensor_snapshot(1,1,{{0,0,-1,true}}).valid);
  const auto empty=curriculum::latest_sensor_snapshot(0,0,{});check(empty.valid&&empty.triggered.empty());"""),
        negative_old="if(e.timestamp>it->second.timestamp)it->second=e;",
        negative_new="if(e.timestamp<it->second.timestamp)it->second=e;",
        negative_reason="keeps the earliest rather than latest sensor event",
    ),
)

LEGACY_TO_CASE = {case.legacy_id: case for case in CASES}

if len(CASES) != 20 or len(LEGACY_TO_CASE) != 20 or len({case.task_id for case in CASES}) != 20:
    raise RuntimeError("sparse-matrix-encoding case inventory must contain 20 one-to-one roots")
