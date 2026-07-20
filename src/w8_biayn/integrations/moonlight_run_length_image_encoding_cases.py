"""Twenty task-specific contracts for run-length image remediation v2."""
from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class RleCase:
    legacy_id: str
    task_id: str
    disposition: str
    title: str
    profile: str
    objective: str
    public_api: str
    marker: str
    prompt_terms: tuple[str, ...]
    instructions: str
    header: str
    starter: str
    reference: str
    negative_source: str
    negative_rule: str
    negative_probe: str
    visible_test: str
    hidden_test: str
    negative_test: str


_INCLUDES = """#pragma once
#include <cstddef>
#include <cstdint>
#include <map>
#include <optional>
#include <queue>
#include <set>
#include <string>
#include <tuple>
#include <utility>
#include <vector>
"""


_NEGATIVE_MUTATIONS: dict[str, tuple[str, str, str]] = {
    "canonical-row-encoder-with-histogram": (
        "for(char crop:order)out.histogram.push_back({crop,histogram[crop]});",
        "for(const auto&entry:histogram)out.histogram.push_back(entry);",
        "alphabetically sorts the histogram instead of preserving first-seen crop order",
    ),
    "threshold-column-decoder": (
        "if(column_peak[x]>=threshold)out.push_back(x);",
        "if(column_peak[x]>threshold)out.push_back(x);",
        "uses a strict threshold and drops columns exactly at the storm threshold",
    ),
    "binary-component-box-bfs": (
        "const int dy[4]={-1,1,0,0},dx[4]={0,0,-1,1};",
        "const int dy[4]={0,0,0,0},dx[4]={0,0,-1,1};",
        "labels only horizontal mask runs and fails to join vertical motion pixels",
    ),
    "stack-based-aisle-reachability": (
        "if(y+1<grid.size()&&grid[y+1][x]=='.')",
        "if(false&&y+1<grid.size()&&grid[y+1][x]=='.')",
        "blocks downward aisle movement and therefore computes row-only reachability",
    ),
    "scanline-component-labeling": (
        "if(it->right+1>=box.left&&box.right+1>=it->left)",
        "if(false&&it->right+1>=box.left&&box.right+1>=it->left)",
        "never merges lesion intervals between adjacent scanlines",
    ),
    "two-dimensional-clear-window": (
        "dp[x]=1+std::min({dp[x],dp[x-1],previous_diagonal});",
        "dp[x]=1+std::max({dp[x],dp[x-1],previous_diagonal});",
        "uses a maximum recurrence that mistakes clear arms for filled clear squares",
    ),
    "vertical-horizontal-seam-matrix": (
        "if(y&&image[y-1][x]!=c)++out.vertical;",
        "if(false&&y&&image[y-1][x]!=c)++out.vertical;",
        "counts only horizontal seams and discards vertical quilt transitions",
    ),
    "first-seen-palette-indexing": (
        "return out;",
        "std::sort(out.palette.begin(),out.palette.end());return out;",
        "sorts the palette after assigning indexes, breaking stable first-seen indexing",
    ),
    "integral-image-block-density": (
        "if(n>best.healthy)best={y,x,n};",
        "if(n>=best.healthy)best={y,x,n};",
        "chooses the last densest block rather than the required earliest block",
    ),
    "run-interval-border-perimeter": (
        "++perimeter;else if(!seen",
        "perimeter+=static_cast<std::size_t>(d<2);else if(!seen",
        "counts only vertical exposed edges and omits horizontal fire perimeter",
    ),
    "monotone-stack-vacancy-rectangle": (
        "heights[x]=row[x]=='V'?heights[x]+1:0;",
        "heights[x]=row[x]=='V'?1:0;",
        "resets histogram heights every row and cannot form multi-row vacancy rectangles",
    ),
    "union-find-class-components": (
        "if(x&&cells[i-1]==cells[i])parent[find(i)]=find(i-1);",
        "if(false&&x&&cells[i-1]==cells[i])parent[find(i)]=find(i-1);",
        "does not union horizontal coral neighbors and overcounts components",
    ),
    "panel-interval-projection-merge": (
        "if(!merged_ranges.empty()&&merged_ranges.back().last+1==p)",
        "if(false&&!merged_ranges.empty()&&merged_ranges.back().last+1==p)",
        "leaves touching affected panels as separate ranges",
    ),
    "row-wise-xor-delta-runs": (
        "out.changed_count+=changed;",
        "out.changed_count+=changed&&(row.empty()||row.back().changed!=changed);",
        "counts changed runs instead of changed pixels",
    ),
    "lane-wise-blockage-threshold": (
        "if(longest>=lane_limit)out.push_back(lane);",
        "if(longest>lane_limit)out.push_back(lane);",
        "uses a strict lane limit and misses blockages equal to the configured limit",
    ),
    "ordered-empty-span-index": (
        "if(r.cell=='E'&&r.count>best_span.length)",
        "if(r.cell=='E'&&r.count>=best_span.length)",
        "chooses the later shelf on equal empty-span lengths",
    ),
    "pad-union-connectivity": (
        "if(x&&cells[i-1]=='#')pad_roots[root(i)]=root(i-1);",
        "if(false&&x&&cells[i-1]=='#')pad_roots[root(i)]=root(i-1);",
        "does not union horizontally adjacent conductor pixels",
    ),
    "cross-row-dry-interval-intersection": (
        "std::vector<bool> intersection(width,true),seen(beds.size());",
        "std::vector<bool> intersection(width,false),seen(beds.size());",
        "initializes the common-dry intersection empty, losing every valid span",
    ),
    "transparent-border-crop-validation": (
        "if(image[y][x]!='T')",
        "if(true)",
        "includes transparent pixels in the opaque crop box",
    ),
    "maximum-bottleneck-channel": (
        "int candidate=std::min(score,depth[j]);",
        "int candidate=std::max(score,depth[j]);",
        "propagates maximum depth instead of the path bottleneck",
    ),
}


_NEGATIVE_PROBES: dict[str, str] = {
    "canonical-row-encoder-with-histogram": (
        "auto q=encode_crop_rows({\"BAC\"});"
        "f+=!q||q->histogram.size()!=3||q->histogram[0].first!='B';"
    ),
    "threshold-column-decoder": (
        "auto q=storm_columns({{{2,1}}},1,2);f+=!q||q->size()!=1;"
    ),
    "binary-component-box-bfs": (
        "auto q=motion_boxes({{{true,1}},{{true,1}}},1);"
        "f+=!q||q->size()!=1||q->front().bottom!=1;"
    ),
    "stack-based-aisle-reachability": (
        "auto q=reachable_aisles({{{'.',1}},{{'.',1}}},1,0,0);f+=!q||*q!=2;"
    ),
    "scanline-component-labeling": (
        "auto q=lesion_boxes({{{'L',1}},{{'L',1}}},1);"
        "f+=!q||q->size()!=1||q->front().bottom!=1;"
    ),
    "two-dimensional-clear-window": (
        "auto q=largest_clear_square({{{'.',1},{'C',1}},{{'.',2}}},2,1);"
        "f+=!q||q->side!=1;"
    ),
    "vertical-horizontal-seam-matrix": (
        "auto q=quilt_seams({\"A\",\"B\"});f+=!q||q->vertical!=1;"
    ),
    "first-seen-palette-indexing": (
        "auto q=encode_mosaic_palette({\"BA\"});"
        "f+=!q||q->palette.empty()||q->palette[0]!='B';"
    ),
    "integral-image-block-density": (
        "auto q=densest_canopy_block({{{'H',1}},{{'H',1}}},1,1,1);"
        "f+=!q||q->row!=0;"
    ),
    "run-interval-border-perimeter": (
        "auto q=border_fire_perimeter({{{'F',1}}},1);f+=!q||*q!=4;"
    ),
    "monotone-stack-vacancy-rectangle": (
        "auto q=audit_vacancy_rectangles({{{'V',1}},{{'V',1}}},1);"
        "f+=!q||q->largest.area!=2;"
    ),
    "union-find-class-components": (
        "auto q=coral_component_histogram({{{'B',2}}},2);"
        "f+=!q||q->at('B')!=1;"
    ),
    "panel-interval-projection-merge": (
        "auto q=affected_panel_ranges({{{'D',2}}},{1,1});"
        "f+=!q||q->size()!=1||q->front().last!=1;"
    ),
    "row-wise-xor-delta-runs": (
        "auto q=encode_snow_delta({\"SS\"},{\"..\"});f+=!q||q->changed_count!=2;"
    ),
    "lane-wise-blockage-threshold": (
        "auto q=blocked_lanes({{{true,2}}},{2});f+=!q||q->size()!=1;"
    ),
    "ordered-empty-span-index": (
        "auto q=longest_empty_shelf_span({{{'E',2}},{{'E',2}}});"
        "f+=!q||q->row!=0;"
    ),
    "pad-union-connectivity": (
        "auto q=connected_pad_pairs({{{'#',2}}},2,{{\"a\",0,0},{\"b\",0,1}});"
        "f+=!q||q->size()!=1;"
    ),
    "cross-row-dry-interval-intersection": (
        "auto q=common_dry_spans({{{'D',1}},{{'D',1}}},1,{0,1});"
        "f+=!q||q->size()!=1;"
    ),
    "transparent-border-crop-validation": (
        "auto q=opaque_crop({{{'T',2}},{{'T',2}}},2);f+=!q||q->has_value();"
    ),
    "maximum-bottleneck-channel": (
        "auto q=widest_safe_channel({{{5,1},{1,1}}},2);f+=!q||*q!=1;"
    ),
}


def _negative_reference(profile: str, reference: str) -> tuple[str, str]:
    needle, replacement, rule = _NEGATIVE_MUTATIONS[profile]
    if reference.count(needle) != 1:
        raise ValueError(f"negative mutation for {profile} is not uniquely applicable")
    return reference.replace(needle, replacement), rule


def _case(legacy_id: str, task_id: str, title: str, profile: str, objective: str,
          operation: str, marker: str, terms: tuple[str, ...], rules: str,
          declarations: str, signature: str, empty: str, body: str,
          visible: str, hidden: str) -> RleCase:
    instructions = f"""# Instructions

{objective} {rules}

Every input run is row-local and has a positive count. Adjacent runs with the same value are
non-canonical and invalid. Reject malformed input without returning a partial result. Counts
and derived dimensions must be checked before arithmetic. The terms {', '.join(terms)} are
part of the public contract.
"""
    header = _INCLUDES + "namespace curriculum {\n" + declarations + "\n" + signature + ";\n}\n"
    stub_signature = re.sub(
        r"(&|\bstd::size_t|\bint)\s+[a-z_][a-z0-9_]*(?=[,)])",
        r"\1",
        signature,
    )
    starter = '#include "task.h"\nnamespace curriculum {' + stub_signature + "{" + empty + "}}\n"
    reference = '#include "task.h"\n#include <algorithm>\n#include <limits>\nnamespace curriculum {' + signature + "{" + body + "}}\n"
    negative_source, negative_rule = _negative_reference(profile, reference)
    negative_probe = _NEGATIVE_PROBES[profile]
    test_prefix = '#include "task.h"\nint main(){using namespace curriculum;int f=0;'
    return RleCase(legacy_id, task_id, "replace", title, profile, objective,
                   operation, marker, terms, instructions, header, starter,
                   reference, negative_source, negative_rule, negative_probe,
                   test_prefix + visible + 'return f;}\n',
                   test_prefix + hidden + 'return f;}\n',
                   test_prefix + negative_probe + 'return f;}\n')


CASES = (
_case("image-rle-farm-map", "crop-row-histogram-codec", "Crop Row Histogram Codec",
"canonical-row-encoder-with-histogram", "Encode rectangular crop rows while accumulating a stable crop histogram.",
"encode_crop_rows", "histogram", ("rectangular", "histogram", "row-local"),
"Crops are uppercase A through Z. The result preserves first-seen crop order and the histogram counts every decoded cell.",
"struct CropRun{char crop='.';std::size_t count=0;};struct CropCode{std::size_t width=0;std::vector<std::vector<CropRun>> rows;std::vector<std::pair<char,std::size_t>> histogram;};",
"std::optional<CropCode> encode_crop_rows(const std::vector<std::string>& image)", "return std::nullopt;",
"if(image.empty()||image.front().empty())return std::nullopt;CropCode out;out.width=image.front().size();std::map<char,std::size_t> histogram;std::vector<char> order;for(const auto&row:image){if(row.size()!=out.width)return std::nullopt;std::vector<CropRun> encoded;for(char crop:row){if(crop<'A'||crop>'Z')return std::nullopt;if(!histogram.count(crop))order.push_back(crop);++histogram[crop];if(!encoded.empty()&&encoded.back().crop==crop)++encoded.back().count;else encoded.push_back({crop,1});}out.rows.push_back(encoded);}for(char crop:order)out.histogram.push_back({crop,histogram[crop]});return out;",
"auto x=encode_crop_rows({\"BBA\",\"ACC\"});std::string keys;if(x)for(const auto&e:x->histogram)keys.push_back(e.first);f+=!x||x->rows.size()!=2||x->histogram.size()!=3||keys!=\"BAC\";",
"auto state=encode_crop_rows({\"AB\",\"BA\"});f+=!state;f+=encode_crop_rows({\"AA\",\"A\"}).has_value();f+=encode_crop_rows({\"A.\"}).has_value();f+=!encode_crop_rows({\"Z\"}).has_value();"),

_case("image-rle-weather-radar", "radar-column-threshold-decoder", "Radar Column Threshold Decoder",
"threshold-column-decoder", "Decode reflectivity rows and report columns whose peak reaches a threshold.",
"storm_columns", "column_peak", ("threshold", "column", "reflectivity"),
"Runs carry integer reflectivity from 0 through 9; output columns are ascending and unique.",
"struct RadarRun{int level=0;std::size_t count=0;};",
"std::optional<std::vector<std::size_t>> storm_columns(const std::vector<std::vector<RadarRun>>& rows,std::size_t width,int threshold)", "return std::nullopt;",
"if(rows.empty()||width==0||threshold<0||threshold>9)return std::nullopt;std::vector<int> column_peak(width,-1);for(const auto&row:rows){std::size_t x=0;int previous=-1;for(const auto&run:row){if(run.count==0||run.level<0||run.level>9||run.level==previous||run.count>width-x)return std::nullopt;for(std::size_t k=0;k<run.count;++k)column_peak[x+k]=std::max(column_peak[x+k],run.level);x+=run.count;previous=run.level;}if(x!=width)return std::nullopt;}std::vector<std::size_t> out;for(std::size_t x=0;x<width;++x)if(column_peak[x]>=threshold)out.push_back(x);return out;",
"auto x=storm_columns({{{1,2},{7,1}},{{8,1},{2,2}}},3,7);f+=!x||*x!=std::vector<std::size_t>({0,2});",
"auto state=storm_columns({{{1,1},{2,1}}},2,2);f+=!state||state->size()!=1;f+=storm_columns({{{3,1},{3,1}}},2,2).has_value();f+=storm_columns({{{1,3}}},2,1).has_value();"),

_case("image-rle-security-mask", "mask-component-bounds-codec", "Mask Component Bounds Codec",
"binary-component-box-bfs", "Decode a binary mask and return bounding boxes for four-connected motion components.",
"motion_boxes", "frontier", ("four-connected", "bounding", "binary"),
"Boxes are ordered by the row-major first pixel of each component and use inclusive coordinates.",
"struct MaskRun{bool active=false;std::size_t count=0;};struct Box{std::size_t top=0,left=0,bottom=0,right=0;};",
"std::optional<std::vector<Box>> motion_boxes(const std::vector<std::vector<MaskRun>>& rows,std::size_t width)", "return std::nullopt;",
"if(rows.empty()||width==0)return std::nullopt;std::vector<std::vector<bool>> grid(rows.size(),std::vector<bool>());for(std::size_t y=0;y<rows.size();++y){int prior=-1;for(const auto&r:rows[y]){if(!r.count||int(r.active)==prior||r.count>width-grid[y].size())return std::nullopt;grid[y].insert(grid[y].end(),r.count,r.active);prior=int(r.active);}if(grid[y].size()!=width)return std::nullopt;}std::vector<std::vector<bool>> seen(rows.size(),std::vector<bool>(width));std::vector<Box> out;for(std::size_t sy=0;sy<rows.size();++sy)for(std::size_t sx=0;sx<width;++sx)if(grid[sy][sx]&&!seen[sy][sx]){Box box{sy,sx,sy,sx};std::queue<std::pair<std::size_t,std::size_t>> frontier;frontier.push({sy,sx});seen[sy][sx]=true;while(!frontier.empty()){auto [y,x]=frontier.front();frontier.pop();box.top=std::min(box.top,y);box.left=std::min(box.left,x);box.bottom=std::max(box.bottom,y);box.right=std::max(box.right,x);const int dy[4]={-1,1,0,0},dx[4]={0,0,-1,1};for(int d=0;d<4;++d){long ny=long(y)+dy[d],nx=long(x)+dx[d];if(ny>=0&&nx>=0&&std::size_t(ny)<rows.size()&&std::size_t(nx)<width&&grid[std::size_t(ny)][std::size_t(nx)]&&!seen[std::size_t(ny)][std::size_t(nx)]){seen[std::size_t(ny)][std::size_t(nx)]=true;frontier.push({std::size_t(ny),std::size_t(nx)});}}}out.push_back(box);}return out;",
"auto x=motion_boxes({{{true,2},{false,1}},{{false,1},{true,2}}},3);f+=!x||x->size()!=1||x->front().right!=2;",
"auto state=motion_boxes({{{true,1},{false,2}},{{false,3}}},3);f+=!state||state->size()!=1;f+=motion_boxes({{{true,1},{true,1}}},2).has_value();f+=motion_boxes({},2).has_value();"),

_case("image-rle-warehouse-plan", "aisle-reachability-decoder", "Aisle Reachability Decoder",
"stack-based-aisle-reachability", "Decode aisle rows and count cells reachable from a loading bay.",
"reachable_aisles", "stack", ("loading bay", "reachable", "wall"),
"A dot is open, a hash is a wall, and movement is orthogonal from the supplied bay coordinate.",
"struct AisleRun{char cell='#';std::size_t count=0;};",
"std::optional<std::size_t> reachable_aisles(const std::vector<std::vector<AisleRun>>& rows,std::size_t width,std::size_t bay_row,std::size_t bay_column)", "return std::nullopt;",
"if(rows.empty()||!width||bay_row>=rows.size()||bay_column>=width)return std::nullopt;std::vector<std::string> grid;for(const auto&encoded:rows){std::string row;char prior='?';for(const auto&r:encoded){if(!r.count||(r.cell!='.'&&r.cell!='#')||r.cell==prior||r.count>width-row.size())return std::nullopt;row.append(r.count,r.cell);prior=r.cell;}if(row.size()!=width)return std::nullopt;grid.push_back(row);}if(grid[bay_row][bay_column]=='#')return std::size_t{0};std::vector<std::pair<std::size_t,std::size_t>> stack{{bay_row,bay_column}};grid[bay_row][bay_column]='#';std::size_t total=0;while(!stack.empty()){auto [y,x]=stack.back();stack.pop_back();++total;if(y&&grid[y-1][x]=='.'){grid[y-1][x]='#';stack.push_back({y-1,x});}if(y+1<grid.size()&&grid[y+1][x]=='.'){grid[y+1][x]='#';stack.push_back({y+1,x});}if(x&&grid[y][x-1]=='.'){grid[y][x-1]='#';stack.push_back({y,x-1});}if(x+1<width&&grid[y][x+1]=='.'){grid[y][x+1]='#';stack.push_back({y,x+1});}}return total;",
"auto x=reachable_aisles({{{'.',2},{'#',1}},{{'#',1},{'.',2}}},3,0,0);f+=!x||*x!=4;",
"auto state=reachable_aisles({{{'.',1},{'#',1},{'.',1}}},3,0,2);f+=!state||*state!=1;f+=reachable_aisles({{{'.',2}}},3,0,0).has_value();f+=reachable_aisles({{{'.',1},{'.',1}}},2,0,0).has_value();"),

_case("image-rle-medical-scan", "lesion-component-boxes-codec", "Lesion Component Boxes Codec",
"scanline-component-labeling", "Encode tissue scanlines while merging overlapping lesion runs into component boxes.",
"lesion_boxes", "active_boxes", ("scanline", "lesion", "overlap"),
"Only L runs are lesions; vertical overlap joins current and previous row intervals, including one-column contact.",
"struct TissueRun{char tissue='H';std::size_t count=0;};struct LesionBox{std::size_t top=0,left=0,bottom=0,right=0;};",
"std::optional<std::vector<LesionBox>> lesion_boxes(const std::vector<std::vector<TissueRun>>& rows,std::size_t width)", "return std::nullopt;",
"if(rows.empty()||!width)return std::nullopt;std::vector<LesionBox> active_boxes,done;for(std::size_t y=0;y<rows.size();++y){std::size_t x=0;std::vector<LesionBox> next;char prior='?';for(const auto&r:rows[y]){if(!r.count||(r.tissue!='H'&&r.tissue!='L')||r.tissue==prior||r.count>width-x)return std::nullopt;if(r.tissue=='L'){LesionBox box{y,x,y,x+r.count-1};for(auto it=active_boxes.begin();it!=active_boxes.end();){if(it->right+1>=box.left&&box.right+1>=it->left){box.top=std::min(box.top,it->top);box.left=std::min(box.left,it->left);box.right=std::max(box.right,it->right);it=active_boxes.erase(it);}else ++it;}next.push_back(box);}x+=r.count;prior=r.tissue;}if(x!=width)return std::nullopt;done.insert(done.end(),active_boxes.begin(),active_boxes.end());active_boxes=next;}done.insert(done.end(),active_boxes.begin(),active_boxes.end());std::sort(done.begin(),done.end(),[](const auto&a,const auto&b){return std::tie(a.top,a.left)<std::tie(b.top,b.left);});return done;",
"auto x=lesion_boxes({{{'H',1},{'L',2}},{{'L',2},{'H',1}}},3);f+=!x||x->size()!=1||x->front().bottom!=1;",
"auto state=lesion_boxes({{{'L',1},{'H',2}},{{'H',2},{'L',1}}},3);f+=!state||state->size()!=2;f+=lesion_boxes({{{'L',0}}},1).has_value();f+=lesion_boxes({{{'X',1}}},1).has_value();"),

_case("image-rle-satellite-clouds", "cloud-clear-window-decoder", "Cloud Clear Window Decoder",
"two-dimensional-clear-window", "Decode cloud rows and find the largest all-clear square using rolling dynamic programming.",
"largest_clear_square", "previous_diagonal", ("clear square", "rolling", "cloud"),
"C is cloud and dot is clear; ties choose the smallest bottom row then smallest right column.",
"struct CloudRun{char cell='C';std::size_t count=0;};struct ClearSquare{std::size_t side=0,top=0,left=0;};",
"std::optional<ClearSquare> largest_clear_square(const std::vector<std::vector<CloudRun>>& rows,std::size_t width,int minimum_side)", "return std::nullopt;",
"if(rows.empty()||!width||minimum_side<=0)return std::nullopt;std::vector<std::size_t> dp(width+1);ClearSquare best;for(std::size_t y=0;y<rows.size();++y){std::string row;char prior='?';for(const auto&r:rows[y]){if(!r.count||(r.cell!='C'&&r.cell!='.')||r.cell==prior||r.count>width-row.size())return std::nullopt;row.append(r.count,r.cell);prior=r.cell;}if(row.size()!=width)return std::nullopt;std::size_t previous_diagonal=0;for(std::size_t x=1;x<=width;++x){std::size_t above=dp[x];if(row[x-1]=='.')dp[x]=1+std::min({dp[x],dp[x-1],previous_diagonal});else dp[x]=0;previous_diagonal=above;if(dp[x]>best.side)best={dp[x],y+1-dp[x],x-dp[x]};}}if(best.side<static_cast<std::size_t>(minimum_side))return ClearSquare{};return best;",
"auto x=largest_clear_square({{{'.',2},{'C',1}},{{'.',3}}},3,2);f+=!x||x->side!=2||x->left!=0;",
"auto state=largest_clear_square({{{'C',2}},{{'.',2}}},2,1);if(!state||state->side!=1)++f;if(largest_clear_square({{{'.',1},{'.',1}}},2,1))++f;if(largest_clear_square({{{'.',3}}},2,1))++f;"),

_case("image-rle-quilt-pattern", "quilt-seam-transition-canonicalizer", "Quilt Seam Transition Canonicalizer",
"vertical-horizontal-seam-matrix", "Canonicalize quilt runs and count horizontal and vertical color transitions.",
"quilt_seams", "vertical_seams", ("horizontal", "vertical", "canonical"),
"The report contains canonical rows plus separate horizontal and vertical seam totals.",
"struct QuiltRun{char color='A';std::size_t count=0;};struct SeamReport{std::vector<std::vector<QuiltRun>> rows;std::size_t horizontal=0,vertical=0;};",
"std::optional<SeamReport> quilt_seams(const std::vector<std::string>& image)", "return std::nullopt;",
"if(image.empty()||image.front().empty())return std::nullopt;SeamReport out;const std::size_t width=image.front().size();for(std::size_t y=0;y<image.size();++y){if(image[y].size()!=width)return std::nullopt;std::vector<QuiltRun> encoded;for(std::size_t x=0;x<width;++x){char c=image[y][x];if(c<'A'||c>'F')return std::nullopt;if(!encoded.empty()&&encoded.back().color==c)++encoded.back().count;else encoded.push_back({c,1});if(x&&image[y][x-1]!=c)++out.horizontal;if(y&&image[y-1][x]!=c)++out.vertical;}out.rows.push_back(encoded);}std::size_t vertical_seams=out.vertical;(void)vertical_seams;return out;",
"auto x=quilt_seams({\"AAB\",\"ABB\"});f+=!x||x->horizontal!=2||x->vertical!=1;",
"auto state=quilt_seams({\"ABC\",\"ABC\"});f+=!state||state->vertical!=0||state->horizontal!=4;f+=quilt_seams({\"A\",\"AA\"}).has_value();f+=quilt_seams({\"G\"}).has_value();"),

_case("image-rle-floor-mosaic", "mosaic-palette-row-encoder", "Mosaic Palette Row Encoder",
"first-seen-palette-indexing", "Build a first-seen palette and encode each mosaic row with palette-index runs.",
"encode_mosaic_palette", "palette_index", ("palette", "first-seen", "index"),
"At most 16 colors are allowed; palette indexes are stable across all rows.",
"struct IndexRun{std::uint8_t index=0;std::size_t count=0;};struct MosaicCode{std::vector<char> palette;std::vector<std::vector<IndexRun>> rows;};",
"std::optional<MosaicCode> encode_mosaic_palette(const std::vector<std::string>& image)", "return std::nullopt;",
"if(image.empty()||image.front().empty())return std::nullopt;MosaicCode out;std::map<char,std::uint8_t> palette_index;const std::size_t width=image.front().size();for(const auto&row:image){if(row.size()!=width)return std::nullopt;std::vector<IndexRun> encoded;for(char c:row){auto it=palette_index.find(c);if(it==palette_index.end()){if(out.palette.size()==16)return std::nullopt;std::uint8_t id=static_cast<std::uint8_t>(out.palette.size());out.palette.push_back(c);it=palette_index.emplace(c,id).first;}if(!encoded.empty()&&encoded.back().index==it->second)++encoded.back().count;else encoded.push_back({it->second,1});}out.rows.push_back(encoded);}return out;",
"auto x=encode_mosaic_palette({\"BAA\",\"ACB\"});f+=!x||x->palette!=std::vector<char>({'B','A','C'})||x->rows[0].size()!=2;",
"auto state=encode_mosaic_palette({\"AB\",\"BA\"});f+=!state||state->palette.size()!=2;f+=encode_mosaic_palette({\"A\",\"AA\"}).has_value();std::string many=\"abcdefghijklmnopq\";f+=encode_mosaic_palette({many}).has_value();"),

_case("image-rle-orchard-drone", "canopy-block-density-index", "Canopy Block Density Index",
"integral-image-block-density", "Decode canopy rows and answer the densest fixed-size survey block.",
"densest_canopy_block", "prefix_sum", ("integral", "block", "density"),
"H is healthy canopy and dot is empty; ties choose the smallest top row then left column.",
"struct CanopyRun{char cell='.';std::size_t count=0;};struct DenseBlock{std::size_t row=0,column=0,healthy=0;};",
"std::optional<DenseBlock> densest_canopy_block(const std::vector<std::vector<CanopyRun>>& rows,std::size_t width,std::size_t block_height,std::size_t block_width)", "return std::nullopt;",
"if(rows.empty()||!width||!block_height||!block_width||block_height>rows.size()||block_width>width)return std::nullopt;std::vector<std::vector<std::size_t>> prefix_sum(rows.size()+1,std::vector<std::size_t>(width+1));for(std::size_t y=0;y<rows.size();++y){std::size_t x=0;char prior='?';for(const auto&r:rows[y]){if(!r.count||(r.cell!='H'&&r.cell!='.')||r.cell==prior||r.count>width-x)return std::nullopt;for(std::size_t k=0;k<r.count;++k,++x)prefix_sum[y+1][x+1]=prefix_sum[y][x+1]+prefix_sum[y+1][x]-prefix_sum[y][x]+(r.cell=='H');prior=r.cell;}if(x!=width)return std::nullopt;}DenseBlock best;for(std::size_t y=0;y+block_height<=rows.size();++y)for(std::size_t x=0;x+block_width<=width;++x){std::size_t n=prefix_sum[y+block_height][x+block_width]-prefix_sum[y][x+block_width]-prefix_sum[y+block_height][x]+prefix_sum[y][x];if(n>best.healthy)best={y,x,n};}return best;",
"auto x=densest_canopy_block({{{'H',2},{'.',1}},{{'.',1},{'H',2}}},3,1,2);f+=!x||x->healthy!=2;",
"auto state=densest_canopy_block({{{'.',2}},{{'H',2}}},2,1,2);f+=!state||state->row!=1;f+=densest_canopy_block({{{'H',3}}},2,1,1).has_value();f+=densest_canopy_block({{{'H',1},{'H',1}}},2,1,1).has_value();"),

_case("image-rle-fire-map", "wildfire-border-perimeter-decoder", "Wildfire Border Perimeter Decoder",
"run-interval-border-perimeter", "Decode hazard bands and calculate exposed perimeter for border-connected fire.",
"border_fire_perimeter", "open_intervals", ("border-connected", "perimeter", "hazard"),
"F is fire and dot is safe; only fire connected to an image border contributes.",
"struct FireRun{char cell='.';std::size_t count=0;};",
"std::optional<std::size_t> border_fire_perimeter(const std::vector<std::vector<FireRun>>& rows,std::size_t width)", "return std::nullopt;",
"if(rows.empty()||!width)return std::nullopt;std::vector<std::string> grid;for(const auto&encoded:rows){std::string row;char prior='?';for(const auto&r:encoded){if(!r.count||(r.cell!='F'&&r.cell!='.')||r.cell==prior||r.count>width-row.size())return std::nullopt;row.append(r.count,r.cell);prior=r.cell;}if(row.size()!=width)return std::nullopt;grid.push_back(row);}std::queue<std::pair<std::size_t,std::size_t>> open_intervals;std::vector<std::vector<bool>> seen(rows.size(),std::vector<bool>(width));for(std::size_t y=0;y<rows.size();++y)for(std::size_t x=0;x<width;++x)if((y==0||x==0||y+1==rows.size()||x+1==width)&&grid[y][x]=='F'&&!seen[y][x]){seen[y][x]=true;open_intervals.push({y,x});}std::size_t perimeter=0;while(!open_intervals.empty()){auto [y,x]=open_intervals.front();open_intervals.pop();const int dy[4]={-1,1,0,0},dx[4]={0,0,-1,1};for(int d=0;d<4;++d){long ny=long(y)+dy[d],nx=long(x)+dx[d];if(ny<0||nx<0||std::size_t(ny)>=rows.size()||std::size_t(nx)>=width||grid[std::size_t(ny)][std::size_t(nx)]=='.')++perimeter;else if(!seen[std::size_t(ny)][std::size_t(nx)]){seen[std::size_t(ny)][std::size_t(nx)]=true;open_intervals.push({std::size_t(ny),std::size_t(nx)});}}}return perimeter;",
"auto x=border_fire_perimeter({{{'F',1},{'.',2}},{{'.',3}}},3);f+=!x||*x!=4;",
"auto state=border_fire_perimeter({{{'.',3}},{{'.',1},{'F',1},{'.',1}},{{'.',3}}},3);f+=!state||*state!=0;f+=border_fire_perimeter({{{'F',4}}},3).has_value();f+=border_fire_perimeter({{{'F',1},{'F',1}}},2).has_value();"),

_case("image-rle-seat-chart", "vacancy-rectangle-run-index", "Vacancy Rectangle Run Index",
"monotone-stack-vacancy-rectangle", "Decode seat rows, audit each row's vacant count, and find the largest all-vacant rectangle.",
"audit_vacancy_rectangles", "height_stack", ("vacant", "rectangle", "row audit"),
"V is vacant and O occupied; return every row's vacant count with the rectangle; rectangle ties choose the earlier bottom row and then left edge.",
"struct SeatRun{char state='O';std::size_t count=0;};struct VacancyRectangle{std::size_t area=0,top=0,left=0,bottom=0,right=0;};struct VacancyAudit{VacancyRectangle largest;std::vector<std::size_t> vacant_by_row;};",
"std::optional<VacancyAudit> audit_vacancy_rectangles(const std::vector<std::vector<SeatRun>>& rows,std::size_t width)", "return std::nullopt;",
"if(rows.empty()||!width)return std::nullopt;std::vector<std::size_t> heights(width);VacancyAudit audit;for(std::size_t y=0;y<rows.size();++y){std::string row;char prior='?';for(const auto&r:rows[y]){if(!r.count||(r.state!='V'&&r.state!='O')||r.state==prior||r.count>width-row.size())return std::nullopt;row.append(r.count,r.state);prior=r.state;}if(row.size()!=width)return std::nullopt;std::size_t vacant=0;for(std::size_t x=0;x<width;++x){heights[x]=row[x]=='V'?heights[x]+1:0;vacant+=row[x]=='V';}audit.vacant_by_row.push_back(vacant);std::vector<std::size_t> height_stack;for(std::size_t x=0;x<=width;++x){std::size_t current=x==width?0:heights[x];while(!height_stack.empty()&&heights[height_stack.back()]>current){std::size_t at=height_stack.back();height_stack.pop_back();std::size_t left=height_stack.empty()?0:height_stack.back()+1;std::size_t area=heights[at]*(x-left);if(area>audit.largest.area)audit.largest={area,y+1-heights[at],left,y,x-1};}height_stack.push_back(x);}}return audit;",
"auto x=audit_vacancy_rectangles({{{'V',2},{'O',1}},{{'V',3}}},3);f+=!x||x->largest.area!=4||x->largest.right!=1||x->vacant_by_row!=std::vector<std::size_t>({2,3});",
"auto state=audit_vacancy_rectangles({{{'O',2}},{{'V',2}}},2);f+=!state||state->largest.area!=2||state->vacant_by_row!=std::vector<std::size_t>({0,2});f+=audit_vacancy_rectangles({{{'V',3}}},2).has_value();f+=audit_vacancy_rectangles({{{'O',1},{'O',1}}},2).has_value();"),

_case("image-rle-coral-survey", "coral-component-histogram-codec", "Coral Component Histogram Codec",
"union-find-class-components", "Decode coral classes and count four-connected components per class.",
"coral_component_histogram", "parent", ("union-find", "component", "class"),
"Dots are empty; uppercase class letters are coral and histogram keys are ascending.",
"struct CoralRun{char cell='.';std::size_t count=0;};",
"std::optional<std::map<char,std::size_t>> coral_component_histogram(const std::vector<std::vector<CoralRun>>& rows,std::size_t width)", "return std::nullopt;",
"if(rows.empty()||!width)return std::nullopt;const std::size_t n=rows.size()*width;std::vector<char> cells;for(const auto&encoded:rows){char prior='?';std::size_t used=0;for(const auto&r:encoded){if(!r.count||(!(r.cell=='.'||(r.cell>='A'&&r.cell<='Z')))||r.cell==prior||r.count>width-used)return std::nullopt;cells.insert(cells.end(),r.count,r.cell);used+=r.count;prior=r.cell;}if(used!=width)return std::nullopt;}std::vector<std::size_t> parent(n);for(std::size_t i=0;i<n;++i)parent[i]=i;auto find=[&parent](std::size_t x){while(parent[x]!=x){parent[x]=parent[parent[x]];x=parent[x];}return x;};for(std::size_t y=0;y<rows.size();++y)for(std::size_t x=0;x<width;++x){std::size_t i=y*width+x;if(cells[i]=='.')continue;if(x&&cells[i-1]==cells[i])parent[find(i)]=find(i-1);if(y&&cells[i-width]==cells[i])parent[find(i)]=find(i-width);}std::map<char,std::set<std::size_t>> roots;for(std::size_t i=0;i<n;++i)if(cells[i]!='.')roots[cells[i]].insert(find(i));std::map<char,std::size_t> out;for(const auto&e:roots)out[e.first]=e.second.size();return out;",
"auto x=coral_component_histogram({{{'A',1},{'.',1},{'A',1}},{{'A',1},{'.',2}}},3);f+=!x||x->at('A')!=2;",
"auto state=coral_component_histogram({{{'B',2}},{{'B',2}}},2);f+=!state||state->at('B')!=1;f+=coral_component_histogram({{{'a',1}}},1).has_value();f+=coral_component_histogram({{{'A',2}}},1).has_value();"),

_case("image-rle-paint-inspection", "panel-defect-interval-decoder", "Panel Defect Interval Decoder",
"panel-interval-projection-merge", "Project defect runs onto panel ranges and merge touching affected panels.",
"affected_panel_ranges", "merged_ranges", ("panel", "interval", "touching"),
"Panel widths partition each row; a panel is affected when any D pixel falls inside it.",
"struct PaintRun{char cell='.';std::size_t count=0;};struct PanelRange{std::size_t first=0,last=0;};",
"std::optional<std::vector<PanelRange>> affected_panel_ranges(const std::vector<std::vector<PaintRun>>& rows,const std::vector<std::size_t>& panel_widths)", "return std::nullopt;",
"if(rows.empty()||panel_widths.empty())return std::nullopt;std::size_t width=0;for(std::size_t w:panel_widths){if(!w||w>std::numeric_limits<std::size_t>::max()-width)return std::nullopt;width+=w;}std::vector<bool> affected(panel_widths.size());for(const auto&encoded:rows){std::size_t x=0,panel=0,boundary=panel_widths[0];char prior='?';for(const auto&r:encoded){if(!r.count||(r.cell!='D'&&r.cell!='.')||r.cell==prior||r.count>width-x)return std::nullopt;for(std::size_t k=0;k<r.count;++k,++x){while(x>=boundary){++panel;boundary+=panel_widths[panel];}if(r.cell=='D')affected[panel]=true;}prior=r.cell;}if(x!=width)return std::nullopt;}std::vector<PanelRange> merged_ranges;for(std::size_t p=0;p<affected.size();++p)if(affected[p]){if(!merged_ranges.empty()&&merged_ranges.back().last+1==p)merged_ranges.back().last=p;else merged_ranges.push_back({p,p});}return merged_ranges;",
"auto x=affected_panel_ranges({{{'.',1},{'D',2},{'.',1}}},{2,2});f+=!x||x->size()!=1||x->front().last!=1;",
"auto state=affected_panel_ranges({{{'D',1},{'.',2},{'D',1}}},{1,2,1});f+=!state||state->size()!=2;f+=affected_panel_ranges({{{'.',2}}},{1,0,1}).has_value();f+=affected_panel_ranges({{{'D',5}}},{2,2}).has_value();"),

_case("image-rle-snow-cover", "snow-map-delta-codec", "Snow Map Delta Codec",
"row-wise-xor-delta-runs", "Compare two snow masks and encode only changed cells as row-local delta runs.",
"encode_snow_delta", "changed_count", ("delta", "changed", "two masks"),
"S means snow and dot means clear; unchanged spans are represented explicitly with false runs.",
"struct DeltaRun{bool changed=false;std::size_t count=0;};struct SnowDelta{std::size_t changed_count=0;std::vector<std::vector<DeltaRun>> rows;};",
"std::optional<SnowDelta> encode_snow_delta(const std::vector<std::string>& before,const std::vector<std::string>& after)", "return std::nullopt;",
"if(before.empty()||before.size()!=after.size()||before.front().empty())return std::nullopt;SnowDelta out;const std::size_t width=before.front().size();for(std::size_t y=0;y<before.size();++y){if(before[y].size()!=width||after[y].size()!=width)return std::nullopt;std::vector<DeltaRun> row;for(std::size_t x=0;x<width;++x){if((before[y][x]!='S'&&before[y][x]!='.')||(after[y][x]!='S'&&after[y][x]!='.'))return std::nullopt;bool changed=before[y][x]!=after[y][x];out.changed_count+=changed;if(!row.empty()&&row.back().changed==changed)++row.back().count;else row.push_back({changed,1});}out.rows.push_back(row);}return out;",
"auto x=encode_snow_delta({\"SS.\"},{\"S.S\"});f+=!x||x->changed_count!=2||x->rows[0].size()!=2;",
"auto state=encode_snow_delta({\"..\",\"SS\"},{\"S.\",\"SS\"});f+=!state||state->changed_count!=1;f+=encode_snow_delta({\"S\"},{\"SS\"}).has_value();f+=encode_snow_delta({\"X\"},{\"S\"}).has_value();"),

_case("image-rle-traffic-camera", "lane-blockage-run-auditor", "Lane Blockage Run Auditor",
"lane-wise-blockage-threshold", "Audit encoded traffic lanes for consecutive blocked cells exceeding a lane-specific limit.",
"blocked_lanes", "lane_limit", ("lane", "consecutive", "limit"),
"Each encoded row is one lane; limits align by lane and output lane indexes are ascending.",
"struct LaneRun{bool blocked=false;std::size_t count=0;};",
"std::optional<std::vector<std::size_t>> blocked_lanes(const std::vector<std::vector<LaneRun>>& lanes,const std::vector<std::size_t>& limits)", "return std::nullopt;",
"if(lanes.empty()||lanes.size()!=limits.size())return std::nullopt;std::vector<std::size_t> out;for(std::size_t lane=0;lane<lanes.size();++lane){std::size_t width=0,longest=0;int prior=-1;for(const auto&r:lanes[lane]){if(!r.count||int(r.blocked)==prior||r.count>std::numeric_limits<std::size_t>::max()-width)return std::nullopt;width+=r.count;if(r.blocked)longest=std::max(longest,r.count);prior=int(r.blocked);}std::size_t lane_limit=limits[lane];if(!width||!lane_limit)return std::nullopt;if(longest>=lane_limit)out.push_back(lane);}return out;",
"auto x=blocked_lanes({{{false,2},{true,3}},{{true,1},{false,4}}},{3,2});f+=!x||*x!=std::vector<std::size_t>({0});",
"auto state=blocked_lanes({{{true,2}},{{false,2}}},{2,1});f+=!state||state->size()!=1;f+=blocked_lanes({{{true,1},{true,1}}},{1}).has_value();f+=blocked_lanes({{{true,1}}},{0}).has_value();"),

_case("image-rle-library-shelves", "shelf-empty-span-index", "Shelf Empty Span Index",
"ordered-empty-span-index", "Index maximal empty shelf spans and answer the longest span across all shelf rows.",
"longest_empty_shelf_span", "best_span", ("shelf", "maximal", "empty span"),
"E is empty and B occupied; ties choose row then start column.",
"struct ShelfRun{char cell='B';std::size_t count=0;};struct ShelfSpan{std::size_t row=0,start=0,length=0;};",
"std::optional<ShelfSpan> longest_empty_shelf_span(const std::vector<std::vector<ShelfRun>>& rows)", "return std::nullopt;",
"if(rows.empty()||rows.front().empty())return std::nullopt;std::size_t width=0;for(const auto&r:rows.front()){if(!r.count||r.count>std::numeric_limits<std::size_t>::max()-width)return std::nullopt;width+=r.count;}ShelfSpan best_span;for(std::size_t y=0;y<rows.size();++y){std::size_t x=0;char prior='?';for(const auto&r:rows[y]){if(!r.count||(r.cell!='E'&&r.cell!='B')||r.cell==prior||r.count>width-x)return std::nullopt;if(r.cell=='E'&&r.count>best_span.length)best_span={y,x,r.count};x+=r.count;prior=r.cell;}if(x!=width)return std::nullopt;}return best_span;",
"auto x=longest_empty_shelf_span({{{'B',1},{'E',3}},{{'E',2},{'B',2}}});f+=!x||x->row!=0||x->length!=3;",
"auto state=longest_empty_shelf_span({{{'E',2}},{{'E',2}}});if(!state||state->row!=0)f+=2;if(longest_empty_shelf_span({{{'E',1},{'E',1}}}))++f;while(longest_empty_shelf_span({{{'X',1}}})){++f;break;}"),

_case("image-rle-circuit-layout", "conductor-pad-connectivity-decoder", "Conductor Pad Connectivity Decoder",
"pad-union-connectivity", "Decode conductive pixels and determine which labeled pads share a conductor component.",
"connected_pad_pairs", "pad_roots", ("conductive", "pad", "connectivity"),
"Hash pixels conduct, dots insulate, and every pad coordinate must lie on a conductor.",
"struct CircuitRun{char cell='.';std::size_t count=0;};struct Pad{std::string name;std::size_t row=0,column=0;};",
"std::optional<std::vector<std::pair<std::string,std::string>>> connected_pad_pairs(const std::vector<std::vector<CircuitRun>>& rows,std::size_t width,const std::vector<Pad>& pads)", "return std::nullopt;",
"if(rows.empty()||!width)return std::nullopt;std::vector<char> cells;for(const auto&encoded:rows){std::size_t used=0;char prior='?';for(const auto&r:encoded){if(!r.count||(r.cell!='#'&&r.cell!='.')||r.cell==prior||r.count>width-used)return std::nullopt;cells.insert(cells.end(),r.count,r.cell);used+=r.count;prior=r.cell;}if(used!=width)return std::nullopt;}std::vector<std::size_t> pad_roots(cells.size());for(std::size_t i=0;i<pad_roots.size();++i)pad_roots[i]=i;auto root=[&pad_roots](std::size_t x){while(pad_roots[x]!=x)x=pad_roots[x];return x;};for(std::size_t y=0;y<rows.size();++y)for(std::size_t x=0;x<width;++x){std::size_t i=y*width+x;if(cells[i]!='#')continue;if(x&&cells[i-1]=='#')pad_roots[root(i)]=root(i-1);if(y&&cells[i-width]=='#')pad_roots[root(i)]=root(i-width);}for(const auto&p:pads)if(p.name.empty()||p.row>=rows.size()||p.column>=width||cells[p.row*width+p.column]!='#')return std::nullopt;std::vector<std::pair<std::string,std::string>> out;for(std::size_t i=0;i<pads.size();++i)for(std::size_t j=i+1;j<pads.size();++j)if(root(pads[i].row*width+pads[i].column)==root(pads[j].row*width+pads[j].column))out.push_back({pads[i].name,pads[j].name});return out;",
"auto x=connected_pad_pairs({{{'#',2},{'.',1}}},3,{{\"a\",0,0},{\"b\",0,1}});f+=!x||x->size()!=1;",
"auto state=connected_pad_pairs({{{'#',1},{'.',1},{'#',1}}},3,{{\"a\",0,0},{\"b\",0,2}});f+=!state||!state->empty();f+=connected_pad_pairs({{{'#',1}}},1,{{\"\",0,0}}).has_value();f+=connected_pad_pairs({{{'#',2}}},1,{}).has_value();"),

_case("image-rle-garden-irrigation", "dry-bed-span-merger", "Dry Bed Span Merger",
"cross-row-dry-interval-intersection", "Intersect dry runs across selected garden beds and merge adjacent common spans.",
"common_dry_spans", "intersection", ("dry", "intersection", "bed"),
"D is dry and W wet; selected bed indexes are unique, valid, and nonempty.",
"struct WaterRun{char state='W';std::size_t count=0;};struct DrySpan{std::size_t begin=0,end=0;};",
"std::optional<std::vector<DrySpan>> common_dry_spans(const std::vector<std::vector<WaterRun>>& beds,std::size_t width,const std::vector<std::size_t>& selected)", "return std::nullopt;",
"if(beds.empty()||!width||selected.empty())return std::nullopt;std::vector<bool> intersection(width,true),seen(beds.size());for(std::size_t id:selected){if(id>=beds.size()||seen[id])return std::nullopt;seen[id]=true;std::vector<bool> dry;char prior='?';for(const auto&r:beds[id]){if(!r.count||(r.state!='D'&&r.state!='W')||r.state==prior||r.count>width-dry.size())return std::nullopt;dry.insert(dry.end(),r.count,r.state=='D');prior=r.state;}if(dry.size()!=width)return std::nullopt;for(std::size_t x=0;x<width;++x)intersection[x]=intersection[x]&&dry[x];}std::vector<DrySpan> out;for(std::size_t x=0;x<width;){if(!intersection[x]){++x;continue;}std::size_t begin=x;while(x+1<width&&intersection[x+1])++x;out.push_back({begin,x});++x;}return out;",
"auto x=common_dry_spans({{{'D',2},{'W',1}},{{'W',1},{'D',2}}},3,{0,1});f+=!x||x->size()!=1||x->front().begin!=1;",
"auto state=common_dry_spans({{{'D',3}},{{'D',1},{'W',2}}},3,{0,1});f+=!state||state->front().end!=0;f+=common_dry_spans({{{'D',1}}},1,{0,0}).has_value();f+=common_dry_spans({{{'D',2}}},1,{0}).has_value();"),

_case("image-rle-game-sprite", "transparent-border-crop-decoder", "Transparent Border Crop Decoder",
"transparent-border-crop-validation", "Decode a palette sprite, require a transparent outer border, and return the opaque crop box.",
"opaque_crop", "border_clear", ("transparent", "border", "crop"),
"T is transparent; palette letters A through Z are opaque. An all-transparent sprite has no crop.",
"struct SpriteRun{char pixel='T';std::size_t count=0;};struct CropBox{std::size_t top=0,left=0,bottom=0,right=0;};",
"std::optional<std::optional<CropBox>> opaque_crop(const std::vector<std::vector<SpriteRun>>& rows,std::size_t width)", "return std::nullopt;",
"if(rows.size()<2||width<2)return std::nullopt;std::vector<std::string> image;for(const auto&encoded:rows){std::string row;char prior='?';for(const auto&r:encoded){if(!r.count||(!(r.pixel=='T'||(r.pixel>='A'&&r.pixel<='Z')))||r.pixel==prior||r.count>width-row.size())return std::nullopt;row.append(r.count,r.pixel);prior=r.pixel;}if(row.size()!=width)return std::nullopt;image.push_back(row);}bool border_clear=true;for(std::size_t x=0;x<width;++x)border_clear=border_clear&&image.front()[x]=='T'&&image.back()[x]=='T';for(const auto&row:image)border_clear=border_clear&&row.front()=='T'&&row.back()=='T';if(!border_clear)return std::nullopt;std::optional<CropBox> box;for(std::size_t y=0;y<image.size();++y)for(std::size_t x=0;x<width;++x)if(image[y][x]!='T'){if(!box)box=CropBox{y,x,y,x};else{box->top=std::min(box->top,y);box->left=std::min(box->left,x);box->bottom=std::max(box->bottom,y);box->right=std::max(box->right,x);}}return box;",
"auto x=opaque_crop({{{'T',3}},{{'T',1},{'A',1},{'T',1}},{{'T',3}}},3);f+=!x||!(*x)||(*x)->top!=1;",
"auto state=opaque_crop({{{'T',2}},{{'T',2}}},2);f+=!state||state->has_value();f+=opaque_crop({{{'A',1},{'T',1}},{{'T',2}}},2).has_value();f+=opaque_crop({{{'T',1},{'T',1}},{{'T',2}}},2).has_value();"),

_case("image-rle-harbor-depth", "safe-channel-widest-path-codec", "Safe Channel Widest Path Codec",
"maximum-bottleneck-channel", "Decode depth bands and find the maximum-bottleneck channel from the west to east edge.",
"widest_safe_channel", "best_depth", ("bottleneck", "west", "east"),
"Depth symbols are digits 0 through 9; movement is orthogonal and ties do not change the reported depth.",
"struct DepthRun{int depth=0;std::size_t count=0;};",
"std::optional<int> widest_safe_channel(const std::vector<std::vector<DepthRun>>& rows,std::size_t width)", "return std::nullopt;",
"if(rows.empty()||!width)return std::nullopt;std::vector<int> depth;for(const auto&encoded:rows){std::size_t used=0;int prior=-1;for(const auto&r:encoded){if(!r.count||r.depth<0||r.depth>9||r.depth==prior||r.count>width-used)return std::nullopt;depth.insert(depth.end(),r.count,r.depth);used+=r.count;prior=r.depth;}if(used!=width)return std::nullopt;}using Node=std::pair<int,std::size_t>;std::priority_queue<Node> queue;std::vector<int> best_depth(depth.size(),-1);for(std::size_t y=0;y<rows.size();++y){std::size_t i=y*width;best_depth[i]=depth[i];queue.push({depth[i],i});}while(!queue.empty()){auto [score,i]=queue.top();queue.pop();if(score!=best_depth[i])continue;std::size_t y=i/width,x=i%width;if(x+1==width)return score;const int dy[4]={-1,1,0,0},dx[4]={0,0,-1,1};for(int d=0;d<4;++d){long ny=long(y)+dy[d],nx=long(x)+dx[d];if(ny<0||nx<0||std::size_t(ny)>=rows.size()||std::size_t(nx)>=width)continue;std::size_t j=std::size_t(ny)*width+std::size_t(nx);int candidate=std::min(score,depth[j]);if(candidate>best_depth[j]){best_depth[j]=candidate;queue.push({candidate,j});}}}return 0;",
"auto x=widest_safe_channel({{{5,2},{1,1}},{{4,3}}},3);f+=!x||*x!=4;",
"auto state=widest_safe_channel({{{2,1},{9,1},{2,1}}},3);if(!state){++f;}else if(*state!=2){f+=2;}for(const auto bad:std::vector<int>{10,-1})if(widest_safe_channel({{{bad,1}}},1))++f;if(widest_safe_channel({{{3,1},{3,1}}},2))++f;"),

)

assert len(CASES) == 20
assert set(_NEGATIVE_PROBES) == set(_NEGATIVE_MUTATIONS)
